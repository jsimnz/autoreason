# Notification System Design Proposal (Revised)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. We will ship a working system in month 2, iterate through month 5, and spend month 6 on hardening.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

This revision addresses ten specific failure modes identified in review: non-atomic pipeline operations, queue durability gaps, broken priority math, SMS cost exposure, in-app table scaling, WebSocket race conditions, digest state accumulation, missing backpressure, and incorrect APNs JWT terminology.

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

**SMS cost reality:** Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU social app with meaningful international distribution, blended cost is likely $0.02–$0.04/message, not $0.0075. At 1M SMS/day, realistic cost is $20,000–$40,000/day — not $7,500. We treat SMS as a tightly controlled premium channel with hard spend caps described in Section 3.4.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given timeline.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Rate limiting / backpressure (Section 2.4)
     │
     ▼
[Notification Router]
  - Preference check
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[Outbox Table]                               [In-App Store]
(PostgreSQL — durable, transactional)        (PostgreSQL — separate)
     │
     ▼
[Outbox Poller / Relay]
  - Reads committed rows
  - Enqueues to Redis
  - Marks relayed
     │
     ▼
[Priority Queue]
  (Redis Sorted Set — AOF-persisted)
     │
     ├── P0 Worker Pool (10 workers, with DLQ)
     ├── P1 Worker Pool (20 workers, with DLQ)
     └── P2 Worker Pool (10 workers, with DLQ)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log]
   (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures)
```

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 sets of dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with priority-encoded scores handles 50M items comfortably. We revisit when we need per-channel rate limiting at scale (50M+ MAU).

**Synchronous preference check at routing time, not at delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. The alternative — checking at delivery — means you've already consumed queue capacity for a notification you'll discard.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They're cheap, don't need retry logic, and benefit from immediate consistency. Putting them through the same queue as push adds latency for no benefit.

**The outbox pattern bridges the atomicity gap.** This is the most important architectural decision in the system. See Section 2.1.

### 2.1 Atomicity: The Outbox Pattern

The naive implementation — write to Redis queue and PostgreSQL in-app store as separate operations — guarantees data loss at scale. At 50M/day, even a 0.01% crash rate between the two writes is 5,000 lost or duplicated notifications per day. We solve this with the transactional outbox pattern.

**How it works:**

The router writes a single row to an `outbox` table inside the same PostgreSQL transaction that writes the in-app notification. Both writes commit atomically or neither does. A separate outbox poller reads committed outbox rows and enqueues them to Redis, then marks the rows as relayed.

```sql
-- Outbox table
CREATE TABLE notification_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id),
    payload         JSONB NOT NULL,
    priority        SMALLINT NOT NULL,
    channels        TEXT[] NOT NULL,   -- ['push', 'email', 'sms']
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relayed_at      TIMESTAMPTZ,       -- NULL = not yet relayed
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
    channels = select_channels(event)  # preference + suppression check
    priority = assign_priority(event.type)

    with db.transaction():
        # Write in-app notification
        notif_id = db.execute("""
            INSERT INTO notifications (user_id, type, priority, title, body, ...)
            VALUES (%s, %s, %s, %s, %s, ...)
            RETURNING id
        """, [...]).scalar()

        # Write outbox entry — same transaction
        db.execute("""
            INSERT INTO notification_outbox
                (notification_id, payload, priority, channels)
            VALUES (%s, %s, %s, %s)
        """, [notif_id, build_payload(event), priority, channels])

    # Transaction committed. Both rows exist or neither does.
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
            FOR UPDATE SKIP LOCKED
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

        time.sleep(0.1)  # 100ms polling interval
```

**Tradeoffs of this approach:**
- Introduces up to ~100ms of additional latency before Redis enqueue. Acceptable for P1/P2; for P0 we use a shorter poll interval (10ms) on a dedicated poller thread.
- Adds a second PostgreSQL write per notification. At 50M/day, that's 100M writes/day total — within range for a properly configured Postgres instance with connection pooling.
- `FOR UPDATE SKIP LOCKED` prevents multiple poller instances from double-processing the same row. We run two poller instances for redundancy; they naturally partition work via lock contention.
- The outbox table grows. We delete rows where `relayed_at IS NOT NULL AND relayed_at < NOW() - INTERVAL '7 days'` in a nightly cleanup job.

**What we do not use:** distributed transactions (two-phase commit across Redis and Postgres). The complexity cost is too high for a team of 4. The outbox pattern achieves the same durability guarantee with simpler failure modes.

### 2.2 Queue Durability

Redis with default configuration is not durable. A restart loses the queue. We require:

```
# redis.conf — required settings, not optional
appendonly yes
appendfsync everysec          # fsync every second; 1-second data loss window on crash
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Replication
# Run Redis in a primary-replica configuration with Redis Sentinel for failover
# replica-lazy-flush no (default — ensures replica stays consistent)
```

**Why `appendfsync everysec` and not `always`:** `always` fsyncs on every write. At 1,750 writes/sec peak, this would saturate disk I/O on most instance types. `everysec` gives us a maximum 1-second data loss window on a hard crash. Given that the outbox table in PostgreSQL is the authoritative source of truth, any notifications lost from Redis on a crash will be re-enqueued by the outbox poller on restart — the durability window is bounded by the poller recovery time, not by Redis persistence alone.

**Operational implication:** Redis is a delivery accelerator, not the system of record. The outbox is the system of record. This separation is what makes the Redis durability configuration a performance decision rather than a correctness decision.

### 2.3 Dequeue Atomicity and Dead-Letter Handling

The pipeline-based dequeue shown in the original proposal is not atomic — it batches round trips but does not prevent a worker from crashing after removing items from the sorted set but before processing them. We replace it with a Lua script that atomically moves items from the work queue to a per-worker processing set, and with explicit dead-letter handling.

**Two-phase dequeue with Lua:**

```lua
-- atomic_dequeue.lua
-- Moves top N items from work queue to a per-worker "in-flight" set
-- with a visibility timeout. If the worker crashes, items expire back.

local queue_key = KEYS[1]           -- "notification_queue"
local inflight_key = KEYS[2]        -- "inflight:worker:{worker_id}"
local inflight_ttl = tonumber(ARGV[1])  -- seconds (e.g., 300)
local batch_size = tonumber(ARGV[2])

-- Get top N items from sorted set
local items = redis.call('ZRANGE', queue_key, 0, batch_size - 1, 'WITHSCORES')

if #items == 0 then
    return {}
end

-- Remove from work queue, add to in-flight set with expiry score
local ids = {}
for i = 1, #items, 2 do
    local id = items[i]
    local deadline = tonumber(redis.call('TIME')[1]) + inflight_ttl
    redis.call('ZREM', queue_key, id)
    redis.call('ZADD', inflight_key, deadline, id)
    table.insert(ids, id)
end

-- Set TTL on inflight set itself as a safety net
redis.call('EXPIRE', inflight_key, inflight_ttl * 2)

return ids
```

**Worker lifecycle:**

```python
def worker_loop(worker_id: str, redis: Redis, db: Connection):
    inflight_key = f"inflight:worker:{worker_id}"

    while True:
        # Atomically move batch from queue to inflight set
        ids = redis.eval(
            ATOMIC_DEQUEUE_SCRIPT,
            2,
            "notification_queue",
            inflight_key,
            300,   # 5-minute visibility timeout
            50     # batch size
        )

        if not ids:
            time.sleep(0.05)
            continue

        for notif_id in ids:
            payload = redis.get(f"ntf:{notif_id}")
            if payload is None:
                # Payload TTL expired — log and skip, outbox will not re-enqueue
                # (relayed_at is set; this is an edge case for very old items)
                log.warning("payload_missing", notif_id=notif_id)
                redis.zrem(inflight_key, notif_id)
                continue

            try:
                notification = Notification.parse(payload)
                dispatch_to_channel(notification)

                # Success — remove from inflight set
                redis.zrem(inflight_key, notif_id)

                # Record delivery
                db.execute(
                    "INSERT INTO delivery_log (notification_id, channel, status) "
                    "VALUES (%s, %s, 'delivered')",
                    [notification.id, notification.channel]
                )

            except RetryableError as e:
                # Leave in inflight set — visibility timeout will return it to queue
                # after 5 minutes, up to max_attempts times
                handle_retryable_failure(notif_id, e, redis, db)

            except PermanentError as e:
                # Move to dead-letter queue, do not retry
                move_to_dlq(notif_id, payload, e, redis, db)
                redis.zrem(inflight_key, notif_id)
```

**Visibility timeout recovery:** A separate recovery process runs every 60 seconds and scans all `inflight:worker:*` keys. Items whose deadline score has passed are moved back to the main queue with their original priority, up to `max_attempts` (default: 3 for P1/P2, 5 for P0). After `max_attempts`, they go to the dead-letter queue.

**Dead-letter queue:** A separate Redis sorted set `notification_dlq` with the same schema. E4 owns a daily alert on DLQ depth. Items in DLQ are retained for 7 days for forensic analysis and manual replay.

### 2.4 Backpressure and Ingestion Rate Limiting

The ingestion API has no mechanism to handle load spikes — a viral post, a marketing campaign bug, or a notification loop can grow the queue unboundedly. We implement three layers of protection.

**Layer 1: Per-source rate limiting at the ingestion API**

```python
RATE_LIMITS = {
    "social_events":    (5_000, "per_second"),   # likes, follows, comments
    "messaging":        (2_000, "per_second"),   # DMs, mentions
    "marketing":        (500,   "per_second"),   # campaigns
    "auth":             (1_000, "per_second