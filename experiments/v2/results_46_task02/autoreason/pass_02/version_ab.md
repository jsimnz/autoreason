# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. Working system ships in month 2, iterated through month 5, hardened in month 6.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

The most important correctness decision: **the transactional outbox pattern** bridges the atomicity gap between PostgreSQL and Redis. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure entirely.

**Key design principles and their tradeoffs, stated upfront:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Outbox pattern over dual writes | ~100ms added latency on P1/P2; eliminated in exchange for correctness |
| Redis sorted set over per-channel queues | Loses per-channel rate limiting; gained in exchange for operational simplicity |
| PostgreSQL as system of record | Redis durability becomes a performance decision, not a correctness one |
| Synchronous preference check at routing | Couples routing latency to cache health; eliminated wasted queue capacity |
| 4-instance poller fleet | 11× headroom over peak; explicit backlog drain capacity after recovery |
| In-app inside same transaction | No "cheap bypass" path; failure modes are consistent and visible |

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

These ratios are estimates. We instrument from day one and adjust channel budgets in month 2.

### SMS Cost Reality

Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is likely $0.02–$0.04/message. At 1M SMS/day, realistic daily cost is **$20,000–$40,000** — not the $7,500 a domestic-only estimate implies. SMS is treated as a tightly controlled premium channel with hard spend caps defined in Section 3.4.

### Team Allocation

| Engineer | Primary Responsibility | Secondary (Cross-Training) |
|----------|----------------------|---------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (E2 backup) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (E1 backup) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (E4 backup) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (E3 backup) |

**Cross-training requirement:** Each engineer must be able to independently diagnose and mitigate incidents in their secondary area within 30 days of launch. Enforced through paired on-call shifts in month 3, where primary and secondary owners respond to incidents together before rotating solo. Runbooks for all critical components are owned jointly by primary and secondary engineers and reviewed monthly. No component has a single person who understands it.

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given the timeline.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting (Layer 1 backpressure)
  - Per-user rate limiting (Layer 3 backpressure)
     │
     ▼
[Notification Router]
  - Preference check (Redis cache, TTL-bounded, write-through)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ▼
[PostgreSQL — single transaction]
  ├── notifications table (in-app record + system of record)
  ├── notification_outbox table (relay instructions for push/email/SMS)
  └── notification_payloads table (payload store, referenced by notif_id)
     │
     ▼
[Outbox Poller Fleet — 4 instances + 1 dedicated P0 instance]
  - FOR UPDATE SKIP LOCKED, batch 500
  - Writes payload to Redis with 2-hour TTL
  - Enqueues notif_id to priority sorted set
  - Marks outbox row relayed
     │
     ▼
[Priority Queue — Redis Sorted Set, AOF-persisted, Sentinel HA]
     │
     ├── P0 Worker Pool (10 workers) — auth OTPs, security alerts
     ├── P1 Worker Pool (20 workers) — direct messages, mentions
     └── P2 Worker Pool (10 workers) — likes, follows, digests
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — spend-capped)
          │
          ▼
   [Delivery Log]              [Dead-Letter Queue]
   (PostgreSQL + S3)           (Redis sorted set + operational runbook)
          │
          ▼
   [Feedback Processor]
   (bounces, delivery receipts, token invalidations)
```

### Core Architectural Decisions and Their Tradeoffs

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with priority-encoded scores handles 50M items comfortably. We revisit when per-channel rate limiting becomes necessary at 50M+ MAU.

**Synchronous preference check at routing time, not at delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means consuming queue capacity for a notification you'll discard — at 50M/day, that waste compounds. The cost is coupling routing latency to cache health; mitigated by the TTL-bounded cache design in Section 3.5.

**In-app notifications written in the same PostgreSQL transaction as the outbox entry.** This is not a cheap bypass path. In-app is the most reliable channel (no external dependency), so if the outbox relay fails permanently after retry exhaustion, the user has an in-app notification but no push or email. That is the correct failure mode — the user is not completely dark, and the system's state is consistent. A partial write — in-app committed, outbox not — would be worse than no write because the failure is invisible.

**Redis is a delivery accelerator, not the system of record.** Any notifications lost from Redis on a crash are re-enqueued by the outbox poller on recovery. This makes Redis durability configuration a performance decision rather than a correctness decision.

---

## 3. Core Subsystems

### 3.1 Atomicity: The Transactional Outbox Pattern

#### Schema

```sql
-- In-app notification record and system of record
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    type            TEXT NOT NULL,
    priority        SMALLINT NOT NULL,   -- 0, 1, 2
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    metadata        JSONB,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;

-- Outbox: relay instructions for external channels
-- Payload stored separately to avoid duplicating large blobs
CREATE TABLE notification_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id),
    priority        SMALLINT NOT NULL,
    channels        TEXT[] NOT NULL,       -- ['push', 'email', 'sms']
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relayed_at      TIMESTAMPTZ,
    relay_attempts  INT NOT NULL DEFAULT 0,
    relay_error     TEXT
);

CREATE INDEX idx_outbox_unrelayed
    ON notification_outbox (priority ASC, created_at ASC)
    WHERE relayed_at IS NULL;

-- Payload store: authoritative payload, referenced by notif_id
-- Workers read from Redis fast path; fall back to this on TTL expiry
CREATE TABLE notification_payloads (
    notification_id UUID PRIMARY KEY REFERENCES notifications(id),
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### The Atomic Router Transaction

```python
def route_notification(event: NotificationEvent, db: Connection):
    channels = select_channels(event)   # preference + suppression check
    priority = assign_priority(event.type)
    payload = build_payload(event)

    with db.transaction():
        # 1. Write in-app record (also the system of record)
        notif_id = db.execute("""
            INSERT INTO notifications
                (user_id, type, priority, title, body, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, [event.user_id, event.type, priority,
              payload["title"], payload["body"], payload.get("metadata")]).scalar()

        # 2. Write payload (referenced by workers via notif_id)
        db.execute("""
            INSERT INTO notification_payloads (notification_id, payload)
            VALUES (%s, %s)
        """, [notif_id, Json(payload)])

        # 3. Write outbox entry for external channel delivery
        #    Only written if external channels are selected
        if channels:
            db.execute("""
                INSERT INTO notification_outbox
                    (notification_id, priority, channels)
                VALUES (%s, %s, %s)
            """, [notif_id, priority, channels])

    # All three rows exist or none do.
    # Redis enqueue happens asynchronously via the outbox poller.
```

---

### 3.2 Outbox Poller: Throughput Analysis and Fleet Design

Without capacity math, the poller design is guesswork. Here is the math.

#### Required Throughput

| Load condition | Rows/second |
|---------------|-------------|
| Average | 578 |
| Peak (3×) | 1,750 |
| Per 100ms interval at peak | 175 |

A single poller with batch size 100 and 100ms sleep cannot sustain peak load: 100 rows / 100ms = 1,000 rows/second theoretical maximum, with zero time for the actual database queries and Redis writes. In practice, a single instance with realistic query latency (10–20ms for a batched SELECT + UPDATE on a warm index) achieves roughly 400–600 rows/second before falling behind.

**Solution: a fleet of 4 poller instances with batch size 500, plus a dedicated P0 instance.**

With 4 general instances and `FOR UPDATE SKIP LOCKED` (which partitions work automatically without coordination):

- Per-instance throughput target: ~450 rows/second (1,750 / 4)
- Measured cycle time: SELECT (10–20ms) + Redis pipeline write (5–10ms) + UPDATE (10–20ms) ≈ 30–50ms
- Per-instance sustained throughput: ~500 rows/cycle × ~15 cycles/second ≈ **7,500 rows/second**
- Fleet capacity: ~**30,000 rows/second** — 17× headroom over peak

This headroom is intentional. The poller must also drain accumulated backlog after a recovery event, not merely keep pace with the steady-state rate.

**P0 gets a dedicated poller instance** with a 10ms poll interval and batch size 50. P0 volume is low (authentication OTPs, security alerts) but latency-sensitive. A dedicated poller prevents P0 items from waiting behind a large P1/P2 batch.

#### Poller Implementation

```python
def poll_outbox(
    db: Connection,
    redis: Redis,
    priority_filter: list[int],   # [0] for P0 poller, [1, 2] for general fleet
    batch_size: int = 500,
    sleep_ms: int = 100,
):
    while True:
        with db.transaction():
            rows = db.execute("""
                SELECT
                    o.id,
                    o.notification_id,
                    o.priority,
                    o.channels,
                    p.payload
                FROM notification_outbox o
                JOIN notification_payloads p
                    ON p.notification_id = o.notification_id
                WHERE o.relayed_at IS NULL
                  AND o.relay_attempts < 5
                  AND o.priority = ANY(%s)
                ORDER BY o.priority ASC, o.created_at ASC
                LIMIT %s
                FOR UPDATE OF o SKIP LOCKED
            """, [priority_filter, batch_size]).fetchall()

            if not rows:
                time.sleep(sleep_ms / 1000)
                continue

            # Pipeline all Redis writes: payload store + queue enqueue
            pipe = redis.pipeline(transaction=False)
            for row in rows:
                payload_key = f"ntf:payload:{row.notification_id}"
                queue_key = f"notification_queue:p{row.priority}"
                score = priority_score(row.priority, row.created_at)

                # Write payload to Redis with 2-hour TTL
                # TTL rationale: workers must process within 2 hours or
                # fall back to PostgreSQL (see Section 3.3)
                pipe.setex(payload_key, 7200, row.payload.encode())
                pipe.zadd(queue_key, {str(row.notification_id): score})

            pipe.execute()

            # Mark all rows relayed in a single UPDATE
            relayed_ids = [row.id for row in rows]
            db.execute("""
                UPDATE notification_outbox
                SET relayed_at = NOW()
                WHERE id = ANY(%s)
            """, [relayed_ids])

            # If the UPDATE fails after Redis writes succeed, the poller
            # re-processes the same rows and attempts duplicate enqueues.
            # Workers handle this via idempotency keys (see Section 3.3).

        time.sleep(sleep_ms / 1000)
```

**Backlog monitoring:** A Prometheus gauge tracks `MAX(created_at) - NOW()` for unrelayed outbox rows, segmented by priority. Alert thresholds: P0 > 30 seconds, P1 > 5 minutes, P2 > 30 minutes. If P1 backlog age exceeds 10 minutes, the fleet scales to 8 poller instances via process supervisor. This is a manual scaling step, not Kubernetes autoscaling — the team does not have the operational overhead budget for complex autoscaling in month 1.

---

### 3.3 Payload Storage and Worker Design

#### Payload Lifecycle

1. **Written by the router transaction** into `notification_payloads` (PostgreSQL, authoritative).
2. **Copied to Redis by the outbox poller** as `ntf:payload:{notification_id}` with a **2-hour TTL**.
3. **Read by workers** from Redis (fast path). If the key is missing (TTL expired