# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. Working system ships in month 2, iterated through month 5, hardened in month 6.

The core architectural bet: **three priority-partitioned queues with channel fanout per priority tier**. This is what the implementation actually requires — per-priority worker pools need per-priority queues — and we say so clearly rather than claiming a simplicity we don't have. We revisit per-channel queues at 50M MAU.

The most important correctness decision: **the transactional outbox pattern** bridges the atomicity gap between PostgreSQL and Redis. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure, but it does not eliminate *all* failure modes. Two distinct failure modes require two distinct solutions:

| Mechanism | Prevents | Does Not Prevent |
|-----------|----------|-----------------|
| Outbox pattern | Lost notifications | Duplicate delivery |
| Idempotency keys (worker layer) | Duplicate delivery | Lost notifications |

Both are specified completely in this document.

**Key design decisions and tradeoffs, stated upfront:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Outbox pattern over dual writes | ~100ms added latency on P1/P2; eliminated in exchange for correctness |
| Three priority queues, not one | Real operational overhead (3 DLQs, 3 alert thresholds); required by per-priority worker pools |
| PostgreSQL as system of record | Redis durability becomes a performance decision, not a correctness one |
| Synchronous preference check at routing | Couples routing latency to cache health; cache unavailability has explicit DB fallback |
| 4-instance poller fleet | 17× headroom over peak; explicit backlog drain capacity after recovery |
| In-app written in same transaction | If push relay fails permanently, user has in-app record but no push — product must validate this |

**What is not yet decided and requires product sign-off before implementation:**

- Behavior when outbox relay exhausts retries for auth OTPs — silent failure or escalation path? (Section 3.6)
- Whether "in-app visible, push failed" is acceptable for users who have push enabled but in-app disabled (Section 2.3)
- SMS spend caps and daily budget limits (Section 3.4)

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 | Industry avg for *engaged* users — see caveat |
| **Total notifications/day** | **~50M** | Used as planning baseline |
| Peak multiplier | 3× sustained, 6× burst | See distribution caveat |
| Peak sustained throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Peak burst throughput | ~3,500/sec | Capacity ceiling design |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

**Distribution caveat — the 17/day figure is not uniformly applicable to all DAU.** The 17 notifications/user/day figure comes from engaged-user benchmarks. Applied uniformly to 3M DAU it produces ~51M/day, which we use as a planning baseline. But the realistic distribution is skewed: the top 10–20% of users likely generate 50–60% of notification volume. This means:

1. The 50M/day aggregate is probably approximately correct — high-volume users compensate for low-volume ones
2. The 3× sustained peak multiplier underestimates burst load for the high-activity cohort, which may spike 8–10× their personal average
3. We design for a **6× burst ceiling** at the infrastructure layer even though the fleet average is 3×

We instrument notification volume per-user-percentile from day one and revisit these assumptions in month 2. The 6× burst ceiling is the hedge against being wrong.

### SMS Cost Reality

Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is likely $0.02–$0.04/message. At 1M SMS/day, realistic daily cost is **$20,000–$40,000** — not the $7,500 a domestic-only estimate implies. SMS is treated as a tightly controlled premium channel with hard spend caps defined in Section 3.4. Spend caps require finance and product sign-off before launch.

### Team Allocation

| Engineer | Primary Responsibility | Secondary (Cross-Training) |
|----------|----------------------|---------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (E2 backup) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (E1 backup) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (E4 backup) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (E3 backup) |

**Cross-training and the month-2 gap.** The working system ships in month 2. Cross-training through paired on-call is planned for month 3. This creates a **one-month window where engineers are on-call for a live production system before their designated backups are qualified.** We address this directly:

- Month 1: E1 and E2 co-build queue infrastructure together, not in parallel. E1 does not own it alone. Same for E3 and E4 on the preference system.
- Month 2 launch: All four engineers are on shared on-call rotation. No solo on-call until month 3.
- Runbooks for all critical components are written by the primary engineer and reviewed by the secondary **before** month 2 launch — not after.

This is still a real risk. A month-2 incident requiring deep queue infrastructure knowledge will be handled by E1 and E2 together, not E2 alone. We accept this constraint explicitly.

No dedicated QA — engineers own quality. All engineers rotate on-call.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting
  - Per-user rate limiting
     │
     ▼
[Notification Router]
  - Preference check (Redis cache → DB fallback → fail closed)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ▼
[PostgreSQL — single transaction]
  ├── notifications table (in-app record + system of record)
  ├── notification_outbox table (relay instructions for push/email/SMS)
  └── notification_payloads table (payload store)
     │
     ▼
[Outbox Poller Fleet — 4 general instances + 1 dedicated P0 instance]
  - FOR UPDATE SKIP LOCKED, batch 500
  - Writes payload to Redis with 2-hour TTL
  - Enqueues notif_id to priority sorted set
  - Marks outbox row relayed
  - On Redis failure: does NOT mark relayed; retries next cycle
     │
     ▼
[Priority Queues — 3 Redis Sorted Sets, AOF-persisted, Sentinel HA]
  notification_queue:p0  (auth OTPs, security alerts)
  notification_queue:p1  (direct messages, mentions)
  notification_queue:p2  (likes, follows, digests)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2 Worker Pool (10 workers)
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

### 2.1 Queue Design: Three Queues, Not One

We use three separate Redis sorted sets (`notification_queue:p0`, `notification_queue:p1`, `notification_queue:p2`) with separate worker pools. We name this clearly because the operational implications differ from a single queue.

**What three queues gives us:**
- Worker pools are independently sized per priority without competing for the same ZRANGEBYSCORE calls
- P0 can have a dedicated poller and dedicated workers without complex score-range filtering
- Per-priority backlog monitoring is straightforward

**What three queues costs us:**
- Three dead-letter queues to monitor
- Three sets of alert thresholds to maintain
- Priority starvation between queues requires explicit handling: P2 workers must not sit idle while P1 is backlogged. Mitigation: P2 workers check P1 queue depth before pulling from P2; if P1 depth exceeds a threshold, P2 workers temporarily pull from P1.

**Why not per-channel queues in addition:** Per-channel queues would give us per-channel rate limiting and independent channel scaling. The cost is 12 queues (4 channels × 3 priorities) plus the monitoring and operational surface that comes with them. At 10M MAU, this is more complexity than the team can maintain. We revisit at 50M MAU.

### 2.2 What the Outbox Pattern Does and Does Not Guarantee

The outbox pattern guarantees: **a notification written to PostgreSQL will eventually be enqueued for delivery.** It prevents the failure mode where the application crashes after writing to PostgreSQL but before writing to Redis — without the outbox, that notification is lost permanently. With the outbox, the poller recovers it on the next cycle.

The outbox pattern does **not** guarantee: **a notification is enqueued exactly once.** If the poller writes to Redis successfully but then fails to commit the `UPDATE SET relayed_at = NOW()` transaction, the same outbox row is processed again on the next cycle, producing a duplicate enqueue. This is an inherent property of at-least-once delivery.

Duplicates are handled at the worker layer via idempotency keys — specified in Section 3.3. The two mechanisms are complementary, not redundant.

### 2.3 In-App Notification Failure Mode — Requires Product Sign-Off

In-app notifications are written in the same PostgreSQL transaction as the outbox entry. This is the correct default: in-app is the most reliable channel (no external dependency), so if the outbox relay fails permanently, the user has an in-app record rather than being completely dark.

However, this produces a failure mode that product must explicitly validate: **a user who has push notifications enabled and in-app notifications disabled.** If the outbox relay fails permanently for their push notification, they receive neither push nor in-app — the in-app record exists in the database but is invisible to them by their own preference. This is the worst-case failure mode for this architecture.

**Alternative approach:** Write in-app notifications in a separate step after outbox relay succeeds. This eliminates the dark-user failure mode but introduces inconsistency risk if the in-app write fails after the outbox write succeeds. We believe the current design's failure modes are more predictable, but this is a judgment call requiring product input.

**Required sign-off before month 2 launch:**
1. Push-enabled, in-app-disabled users when push relay fails permanently — acceptable?
2. All channels fail permanently — is a database record with no visible notification acceptable?

---

## 3. Core Subsystems

### 3.1 Atomicity: The Transactional Outbox Pattern

#### Schema

```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    type            TEXT NOT NULL,
    priority        SMALLINT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    metadata        JSONB,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;

CREATE TABLE notification_outbox (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id     UUID NOT NULL REFERENCES notifications(id),
    priority            SMALLINT NOT NULL,
    channels            TEXT[] NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relayed_at          TIMESTAMPTZ,
    relay_attempts      INT NOT NULL DEFAULT 0,
    relay_error         TEXT,
    -- Explicit dead-letter state, not merely retry exhaustion
    dead_lettered_at    TIMESTAMPTZ,
    dead_letter_reason  TEXT
);

CREATE INDEX idx_outbox_unrelayed
    ON notification_outbox (priority ASC, created_at ASC)
    WHERE relayed_at IS NULL AND dead_lettered_at IS NULL;

CREATE TABLE notification_payloads (
    notification_id UUID PRIMARY KEY REFERENCES notifications(id),
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Idempotency key store: prevents duplicate delivery at worker layer
-- Key: (notification_id, channel) — written before send, checked before each attempt
CREATE TABLE notification_delivery_attempts (
    notification_id UUID NOT NULL REFERENCES notifications(id),
    channel         TEXT NOT NULL,
    attempted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL,   -- 'sent', 'failed', 'bounced'
    provider_id     TEXT,            -- External provider message ID
    PRIMARY KEY (notification_id, channel)
);
```

#### The Atomic Router Transaction

```python
def route_notification(event: NotificationEvent, db: Connection):
    channels = select_channels(event)   # preference + suppression check
    priority = assign_priority(event.type)
    payload = build_payload(event)

    with db.transaction():
        notif_id = db.execute("""
            INSERT INTO notifications
                (user_id, type, priority, title, body, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, [event.user_id, event.type, priority,
              payload["title"], payload["body"], payload.get("metadata")]).scalar()

        db.execute("""
            INSERT INTO notification_payloads (notification_id, payload)
            VALUES (%s, %s)
        """, [notif_id, Json(payload)])

        if channels:
            db.execute("""
                INSERT INTO notification_outbox
                    (notification_id, priority, channels)
                VALUES (%s, %s, %s)
            """, [notif_id, priority, channels])

    # All three rows exist or none do.
    # Redis enqueue happens asynchronously via the outbox poller.
    # In-app record is immediately visible to the user via the notifications table.
```

---

### 3.2 Outbox Poller: Throughput Analysis, Fleet Design, and Failure Handling

#### Required Throughput

| Load condition | Rows/second |
|---------------|-------------|
| Average | 578 |
| Peak sustained (3×) | 1,750 |
| Peak burst (6×) | 3,500 |

**Per-instance throughput estimate:**

A single poller instance with batch size 500 and `FOR UPDATE SKIP LOCKED`:
- SELECT + JOIN on warm index: 15–25ms
- Redis pipeline write (500 SET + 500 ZADD): 20–40ms
- UPDATE 500 rows: 10–20ms
- Total cycle time: ~50–85ms average

Per-instance throughput: 500 rows / 70ms ≈ **~7,100 rows/second**

With 4 general instances: **