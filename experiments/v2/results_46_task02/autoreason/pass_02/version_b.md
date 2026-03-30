# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

**What changed from v1:** Eleven specific problems were identified in the prior draft. This revision addresses each one directly. The most significant changes are: a throughput-analyzed outbox poller design with explicit capacity math; a clarified in-app atomicity model that resolves the contradiction between bypass routing and transactional guarantees; a complete payload storage design; a Lua-based atomic recovery sweeper; explicit PostgreSQL write budget analysis with PgBouncer configuration; a redesigned P0 overload path with actual load shedding; cross-training requirements for team resilience; a complete SMS spend cap mechanism; a defined DLQ operational process; and a preference cache invalidation strategy with compliance controls.

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

**These ratios are estimates.** We instrument from day one and adjust channel budgets in month 2.

### SMS Cost Reality

Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is likely $0.02–$0.04/message. At 1M SMS/day, realistic daily cost is **$20,000–$40,000** — not the $7,500 a domestic-only estimate implies. The spend cap mechanism that enforces this budget is defined in full in Section 3.4.

### Team Allocation

| Engineer | Primary Responsibility | Secondary (Cross-Training) |
|----------|----------------------|---------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (E2 backup) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (E1 backup) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (E4 backup) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (E3 backup) |

**Cross-training requirement:** Each engineer must be able to independently diagnose and mitigate incidents in their secondary area within 30 days of system launch. This is enforced through paired on-call shifts in month 3, where primary and secondary owners respond to incidents together before rotating solo. Runbooks for all critical components are owned jointly by primary and secondary engineers and reviewed monthly. No component has a single person who understands it.

All engineers rotate on-call. No dedicated QA — engineers own quality.

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
  ├── notifications table (in-app record)
  ├── notification_outbox table (push/email/SMS relay)
  └── notification_payloads table (payload store)
     │
     ▼
[Outbox Poller Fleet — 4 instances]
  - FOR UPDATE SKIP LOCKED, batch 500
  - Writes payload to Redis with TTL
  - Enqueues notif_id to priority sorted set
  - Marks outbox row relayed
     │
     ▼
[Priority Queue — Redis Sorted Set, AOF-persisted]
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
   [Delivery Log]          [Dead-Letter Queue]
   (PostgreSQL + S3)       (Redis + operational runbook)
          │
          ▼
   [Feedback Processor]
   (bounces, delivery receipts, token invalidations)
```

---

## 3. Core Subsystems

### 3.1 Atomicity: The Transactional Outbox Pattern

#### The In-App Channel and Atomicity — Clarified

The prior draft contained a contradiction: it claimed the outbox pattern provided atomicity guarantees, while simultaneously routing in-app notifications through a "bypass" path described as not needing retry logic. These are incompatible positions.

**The correct model:** In-app notifications are written inside the same PostgreSQL transaction as the outbox entry. This is not a bypass — it is the same atomic write, with in-app being one output and the outbox being the relay mechanism for push/email/SMS. The transaction either commits all three (in-app record, outbox entry, payload record) or none.

The consequence of this design is explicit: if the outbox relay fails permanently after 5 retry exhaustions, the user has an in-app notification but no push or email. This is the correct failure mode — in-app is the most reliable channel (no external dependency), so the user is not completely dark. Push and email are best-effort amplifiers. SMS, being P0-only, has a separate escalation path described below.

What we do not do: put in-app outside the transaction and call it "cheap." That was the prior draft's error. A partial write — in-app committed, outbox not — is worse than no write, because the system's state is inconsistent and the failure is invisible.

#### Schema

```sql
-- In-app notification record (also serves as system of record)
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
-- Stored here rather than in outbox to avoid duplicating large blobs
-- across outbox and Redis; Redis holds only the serialized form with TTL
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
        # 1. Write in-app record
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
        # Only written if external channels are selected
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

**This is the section the prior draft omitted entirely.** Without capacity math, the poller design is fiction.

#### Required Throughput

At 50M notifications/day average throughput, the outbox poller must relay:

- **Average:** 578 rows/second
- **Peak (3×):** 1,750 rows/second
- **Per 100ms interval at peak:** 175 rows

A single poller with batch size 100 and 100ms sleep cannot sustain peak load. The math is straightforward: 100 rows / 100ms = 1,000 rows/second maximum theoretical throughput, with zero time for the actual database queries, Redis writes, and outbox updates. In practice, a single poller instance with realistic query latency (5–15ms for a batched SELECT + UPDATE on a warm index) achieves roughly 400–600 rows/second before falling behind.

**Solution: a fleet of 4 poller instances with a larger batch size.**

Each instance runs `FOR UPDATE SKIP LOCKED`, which means they partition the work automatically without coordination. With 4 instances and batch size 500:

- Per-instance throughput target: ~450 rows/second (1,750 / 4)
- Per-instance batch interval: 500 rows / 450 rows/sec ≈ 1.1 seconds per cycle
- Measured cycle time budget: SELECT (10–20ms) + Redis pipeline write (5–10ms) + UPDATE (10–20ms) ≈ 30–50ms per cycle
- **Actual per-instance throughput: ~500 rows/100ms × 10 cycles/second = 5,000 rows/second**

At 4 instances, fleet capacity is approximately **20,000 rows/second** — an 11× headroom over peak. This headroom is intentional: the poller must also drain accumulated backlog after a recovery event.

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
                # fall back to PostgreSQL for payload retrieval (see Section 3.3)
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
            # Transaction commits here; both the Redis writes and the
            # outbox update are best-effort consistent. If the UPDATE
            # fails after Redis writes succeed, the poller will re-process
            # the same rows and attempt duplicate enqueues. Workers handle
            # this via idempotency keys (see Section 3.3).

        time.sleep(sleep_ms / 1000)
```

**Backlog monitoring:** A Prometheus gauge tracks `MAX(created_at) - NOW()` for unrelayed outbox rows, segmented by priority. Alert thresholds: P0 > 30 seconds, P1 > 5 minutes, P2 > 30 minutes. If P1 backlog exceeds 10 minutes, the fleet auto-scales to 8 poller instances via a simple process supervisor rule. This is a manual scaling step, not Kubernetes autoscaling — the team does not have the operational overhead budget for complex autoscaling in month 1.

---

### 3.3 Payload Storage and Worker Design

**The prior draft left this entirely unspecified.** Workers referenced `redis.get(f"ntf:{notif_id}")` with no explanation of when or how that key was written. This section defines it completely.

#### Payload Lifecycle

1. **Written by the router transaction** into `notification_payloads` (PostgreSQL, authoritative).
2. **Copied to Redis by the outbox poller** as `ntf:payload:{notification_id}` with a **2-hour TTL**.
3. **Read by workers** from Redis (fast path). If the key is missing (TTL expired or Redis restart), workers fall back to PostgreSQL.
4. **Never deleted from PostgreSQL** — payloads are retained for 30 days alongside the notification record, then archived to S3.

The 2-hour TTL is chosen based on the expectation that workers drain the queue within minutes under normal operation. A 2-hour window handles Redis restarts, poller delays, and moderate backlog scenarios. If