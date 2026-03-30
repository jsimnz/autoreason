# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. Working system ships in month 2, iterated through month 5, hardened in month 6.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

The most important correctness decision: **the transactional outbox pattern** bridges the atomicity gap between PostgreSQL and Redis. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure entirely.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

**Tradeoff acknowledged:** These ratios are estimates. We instrument from day one and adjust channel budgets in month 2.

**SMS cost reality:** Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is likely $0.02–$0.04/message. At 1M SMS/day, realistic daily cost is **$20,000–$40,000** — not the $7,500 a domestic-only estimate implies. We treat SMS as a tightly controlled premium channel with hard spend caps described in Section 3.4.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given the timeline.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting / backpressure (Section 2.4)
     │
     ▼
[Notification Router]
  - Preference check (Redis cache)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[Outbox Table]                               [In-App Store]
(PostgreSQL — single transaction)            (PostgreSQL — same transaction)
     │
     ▼
[Outbox Poller / Relay]
  - Reads committed rows (FOR UPDATE SKIP LOCKED)
  - Enqueues to Redis
  - Marks relayed
     │
     ▼
[Priority Queue]
  (Redis Sorted Set — AOF-persisted, Sentinel HA)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2 Worker Pool (10 workers)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log + DLQ]
   (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]
   (bounces, delivery receipts, failures)
```

### Core Architectural Decisions

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with priority-encoded scores handles 50M items comfortably. We revisit when per-channel rate limiting becomes necessary at 50M+ MAU.

**Synchronous preference check at routing time, not at delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means consuming queue capacity for a notification you'll discard — at 50M/day, that waste compounds.

**In-app notifications bypass the delivery queue.** In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They're cheap, don't need retry logic, and benefit from immediate consistency. Routing them through the push/SMS queue adds latency for no benefit.

**Redis is a delivery accelerator, not the system of record.** The outbox table in PostgreSQL is the system of record. This separation makes Redis durability a performance decision rather than a correctness decision — any notifications lost from Redis on a crash are re-enqueued by the outbox poller on recovery.

---

### 2.1 Atomicity: The Transactional Outbox Pattern

The naive implementation — write to Redis and PostgreSQL as separate operations — guarantees data loss at scale. We solve this with the transactional outbox pattern.

**How it works:** The router writes a single row to an `outbox` table inside the same PostgreSQL transaction that writes the in-app notification. Both writes commit atomically or neither does. A separate outbox poller reads committed rows and enqueues them to Redis, then marks them as relayed.

```sql
CREATE TABLE notification_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id),
    payload         JSONB NOT NULL,
    priority        SMALLINT NOT NULL,
    channels        TEXT[] NOT NULL,       -- ['push', 'email', 'sms']
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relayed_at      TIMESTAMPTZ,           -- NULL = not yet relayed
    relay_attempts  INT NOT NULL DEFAULT 0,
    relay_error     TEXT
);

CREATE INDEX idx_outbox_unrelayed
    ON notification_outbox (created_at ASC)
    WHERE relayed_at IS NULL;
```

**The atomic router transaction:**

```python
def route_notification(event: NotificationEvent, db: Connection):
    channels = select_channels(event)   # preference + suppression check
    priority = assign_priority(event.type)

    with db.transaction():
        # Write in-app notification
        notif_id = db.execute("""
            INSERT INTO notifications (user_id, type, priority, title, body, ...)
            VALUES (%s, %s, %s, %s, %s, ...)
            RETURNING id
        """, [...]).scalar()

        # Write outbox entry — same transaction, atomic with above
        db.execute("""
            INSERT INTO notification_outbox
                (notification_id, payload, priority, channels)
            VALUES (%s, %s, %s, %s)
        """, [notif_id, build_payload(event), priority, channels])

    # Both rows exist or neither does.
    # Redis enqueue happens asynchronously via the outbox poller.
```

**The outbox poller:**

```python
def poll_outbox(db: Connection, redis: Redis):
    while True:
        rows = db.execute("""
            SELECT id, notification_id, payload, priority, channels
            FROM notification_outbox
            WHERE relayed_at IS NULL
              AND relay_attempts < 5
            ORDER BY created_at ASC
            LIMIT 100
            FOR UPDATE SKIP LOCKED   -- prevents double-processing across poller instances
        """).fetchall()

        for row in rows:
            try:
                enqueue_to_redis(redis, row)
                db.execute("""
                    UPDATE notification_outbox
                    SET relayed_at = NOW()
                    WHERE id = %s
                """, [row.id])
                db.commit()
            except Exception as e:
                db.execute("""
                    UPDATE notification_outbox
                    SET relay_attempts = relay_attempts + 1,
                        relay_error = %s
                    WHERE id = %s
                """, [str(e), row.id])
                db.commit()

        time.sleep(0.1)   # 100ms for P1/P2; dedicated poller runs at 10ms for P0
```

**Tradeoffs of this approach:**
- Introduces up to ~100ms additional latency before Redis enqueue. Acceptable for P1/P2. P0 uses a dedicated poller thread with a 10ms interval.
- Adds a second PostgreSQL write per notification: 100M writes/day total. Within range for a properly configured Postgres instance with connection pooling.
- `FOR UPDATE SKIP LOCKED` lets two poller instances run for redundancy without double-processing.
- The outbox table grows. A nightly job deletes rows where `relayed_at < NOW() - INTERVAL '7 days'`.

**What we do not use:** distributed transactions (two-phase commit across Redis and Postgres). The complexity cost is too high for a team of 4. The outbox pattern achieves equivalent durability with simpler failure modes.

---

### 2.2 Queue Durability

Redis with default configuration is not durable. A restart loses the queue. Required configuration:

```
# redis.conf
appendonly yes
appendfsync everysec          # fsync every second; max 1-second data loss on crash
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

**Why `everysec` and not `always`:** `always` fsyncs on every write. At 1,750 writes/sec peak, this saturates disk I/O on most instance types. `everysec` gives a maximum 1-second data loss window on a hard crash. Since the outbox table is the authoritative source of truth, any notifications lost from Redis on a crash are re-enqueued by the outbox poller on restart. Redis durability configuration is a performance decision, not a correctness decision.

**High availability:** Redis in primary-replica configuration with Redis Sentinel for automatic failover. Replica lag monitoring is an E4 responsibility; alert if replica lag exceeds 5 seconds.

---

### 2.3 Dequeue Atomicity and Dead-Letter Handling

A pipeline-based dequeue (`ZRANGE` + `ZREM` in a pipeline) batches round trips but is **not atomic** — a worker can crash after removing items from the sorted set but before processing them. We replace this with a Lua script that atomically moves items to a per-worker in-flight set with a visibility timeout.

**Two-phase dequeue with Lua:**

```lua
-- atomic_dequeue.lua
-- Moves top N items from work queue to a per-worker in-flight sorted set.
-- Score = deadline timestamp. Items not acknowledged before deadline
-- are recovered by the visibility timeout sweeper.

local queue_key    = KEYS[1]    -- "notification_queue"
local inflight_key = KEYS[2]    -- "inflight:worker:{worker_id}"
local ttl_secs     = tonumber(ARGV[1])   -- e.g., 300
local batch_size   = tonumber(ARGV[2])

local items = redis.call('ZRANGE', queue_key, 0, batch_size - 1, 'WITHSCORES')
if #items == 0 then return {} end

local now = tonumber(redis.call('TIME')[1])
local ids = {}

for i = 1, #items, 2 do
    local id       = items[i]
    local deadline = now + ttl_secs
    redis.call('ZREM', queue_key, id)
    redis.call('ZADD', inflight_key, deadline, id)
    table.insert(ids, id)
end

redis.call('EXPIRE', inflight_key, ttl_secs * 2)
return ids
```

**Worker lifecycle:**

```python
def worker_loop(worker_id: str, redis: Redis, db: Connection):
    inflight_key = f"inflight:worker:{worker_id}"

    while True:
        ids = redis.eval(
            ATOMIC_DEQUEUE_SCRIPT, 2,
            "notification_queue", inflight_key,
            300,   # 5-minute visibility timeout
            50     # batch size
        )

        if not ids:
            time.sleep(0.05)
            continue

        for notif_id in ids:
            payload = redis.get(f"ntf:{notif_id}")
            if payload is None:
                # Payload TTL expired — log and skip
                log.warning("payload_missing", notif_id=notif_id)
                redis.zrem(inflight_key, notif_id)
                continue

            try:
                notification = Notification.parse(payload)
                dispatch_to_channel(notification)
                redis.zrem(inflight_key, notif_id)
                record_delivery(db, notification.id, notification.channel, "delivered")

            except RetryableError as e:
                # Leave in inflight set — visibility timeout returns it to queue
                increment_attempt_count(notif_id, e, redis, db)

            except PermanentError as e:
                move_to_dlq(notif_id, payload, e, redis, db)
                redis.zrem(inflight_key, notif_id)
```

**Visibility timeout recovery:** A process running every 60 seconds scans all `inflight:worker:*` keys. Items whose deadline score has passed are moved back to the main queue with their original priority, up to `max_attempts` (3 for P1/P2, 5 for P0). After `max_attempts`, they move to the dead-letter queue.

**Dead-letter queue:** A separate Redis sorted set `notification_dlq`. E4 owns a daily alert on DLQ depth. Items are retained for 7 days for forensic analysis and manual replay.

---

### 2.4 Backpressure and Ingestion Rate Limiting

Without backpressure, a viral post, a marketing campaign bug, or a notification loop can grow the queue unboundedly. Three layers of protection:

**Layer 1: Per-source rate limiting at the ingestion API**

```python
RATE_LIMITS = {
    "social_events":  (5_000, "per_second"),   # likes, follows, comments
    "messaging":      (2_000, "per_second"),   # DMs, mentions
    "marketing":      (500,   "per_second"),   # campaigns
    "auth":           (1_000, "per_second"),   # OTPs, security alerts
}
# Implemented as token buckets in Redis. Exceeded sources receive 429;
# callers are expected to back off and retry with jitter.
```

**Layer 2: Queue depth circuit breaker**

```python
MAX_QUEUE_DEPTHS = {"P0": 10_000, "P1": 500_000, "P2": 2_000_000}

def enqueue(notification: Notification, redis: Redis):
    depth = redis.zcard("notification_queue")
    if depth > MAX_QUEUE_DEPTHS[notification.priority]:
        if notification.priority == "P0":
            # P0 never shed — alert and enqueue anyway
            alert_oncall("P0 queue depth exceeded threshold")
        else:
            metrics.increment("notifications.shed", tags={"priority": notification.priority})
            raise QueueFullError(f"Queue depth {depth} exceeds limit")
    # proceed with enqueue
```

**Layer 3: Per-user notification rate limiting**

```python
USER_RATE_