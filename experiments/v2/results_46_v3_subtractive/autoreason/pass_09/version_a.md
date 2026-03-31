# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score. Workers are fungible within a channel; priority is a property of queue position. **Exception:** SMS P0 gets a dedicated worker paired with a fast-path ingestion route that bypasses the standard aggregation window check and uses a pre-warmed preference cache entry, reducing the pipeline to ingestion → router → dedicated worker. This is not a contradiction — it is the correct application of the principle: use dedicated workers when end-to-end pipeline latency requirements cannot be met by the standard path, and only then.
- **At-least-once delivery with idempotency keys.** We cannot atomically claim a database row and deliver a push notification. We accept duplicate delivery as a bounded, logged operational condition. Provider-side idempotency keys bound the duplicate window where supported. Key construction must be stable across recovery-path re-enqueues; the exact construction is specified in §2.4.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets, with a PostgreSQL event log as recovery backstop.
- **Per-channel queues** isolating channel failures. APNs degradation affects push workers only; email workers continue unaffected.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring. These require a functioning baseline. We build the baseline.

**What we're explicitly accepting as limitations:** Duplicate delivery is possible in crash scenarios. We bound it, log it, and target a duplicate rate below 0.01% of delivered notifications.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Event generation (actor side):**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU, typical social apps |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |

**Notification fanout:** We do not send per-follower notifications for posts. Only direct interactions (follows, comments, mentions, likes on your content) generate notifications. Average fanout is approximately 1.2.

**Recipient-notification events/day: 15M × 1.2 = ~18M events/day**

**Opt-out sensitivity:**

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | **Design ceiling — highest load** | ~14.4M | ~500/sec |
| 40% | Base case | ~10.8M | ~375/sec |
| 60% | Lower bound | ~7.2M | ~250/sec |

We design for the 20% opt-out scenario (14.4M/day, 500/sec peak). Architecture does not change as we scale; only worker pool sizing and Redis provisioning change.

**Channel distribution — 20% opt-out design ceiling:**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events | ~35 pre-batch |
| SMS | <0.01% | ~1,500 | negligible |

**Email volume and batching:**

We model per-user email-triggering events as Poisson with rate λ events/day. With a 30-minute batching window, the expected number of events per window is μ = λ/48. We send one email per window if at least one event occurred:

```
emails_per_user_per_day = 48 × (1 - e^(-λ/48))
reduction = λ / (48 × (1 - e^(-λ/48)))
```

For small λ (λ << 48), reduction ≈ 1 — most windows have zero events, so batching provides little benefit. For large λ, nearly every window has an event and reduction → λ/48.

| Email Opt-In Rate | Opted-In DAU | λ (events/user/day) | Calculated Reduction | Emails/User/Day | Delivered/Day |
|-------------------|-------------|---------------------|----------------------|-----------------|---------------|
| 10% | 300K | 4.3 | 1.49× | 2.89 | ~867K |
| 20% (base case) | 600K | 2.2 | 1.23× | 1.79 | ~1.07M |
| 40% | 1.2M | 1.1 | 1.11× | 0.99 | ~1.19M |

At λ=2.2, most users receive 1–2 email-triggering events per day and a 30-minute window rarely catches more than one. We use the 20% opt-in / 1.07M delivered/day figure for worker sizing and recalibrate after Phase 1.

**Delivered email peak rate:** 1.07M/day ÷ 86,400 × 3 ≈ **37/sec peak.** This is within the capacity of a single SES connection at standard throughput limits.

**Note on batching window:** A 30-minute window is a product decision, not a derived one. Shorter windows reduce batching benefit further; longer windows improve batching but degrade perceived responsiveness. We expose it as a configurable parameter.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; suppression cache invalidation |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; connection pool management; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group with explicit ACK and a configured pending entry timeout. Neither engineer writes directly into the other's domain.

**Timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §6 for explicit contingencies.

---

## 2. System Architecture

### 2.1 Priority Classification

The router assigns priority at ingestion time based on event type. Classification is exhaustive — every event type is assigned a priority at definition time. New event types require a pull request that includes a priority assignment; unclassified events are rejected with a logged error, not silently defaulted.

| Priority | Label | Event Types | Target Delivery Latency |
|----------|-------|-------------|------------------------|
| P0 | Critical | Auth codes, account compromise alerts, payment failures | <2 seconds |
| P1 | High | Direct messages, mentions, replies to your content | <30 seconds |
| P2 | Normal | Likes, new followers, comments on your posts | <5 minutes |
| P3 | Bulk | Digest summaries, weekly recaps, promotional notifications | <1 hour |

**Tradeoff:** A static classification table is less flexible than a scoring function. We accept this. A scoring function requires calibration data we do not have yet and introduces a class of bugs (miscalibrated scores, drift over time) that a lookup table does not.

### 2.2 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Assigns event_id (UUID v7, time-ordered)
  - Computes idempotency_key (see §2.4 for exact construction)
  - Writes to PostgreSQL event log (state=enqueued)
  - Enqueues to Redis sorted set as event_id:YYYY-MM-DD with score=timestamp
     │
     ▼
[Notification Router]
  - Priority lookup (static classification table)
  - Preference check (Redis cache, TTL=5min, write-through)
  - Suppression check (Redis Hash, see §3.3 for invalidation)
  - Aggregation window check (bypassed for P0 SMS fast path)
  - Channel selection → enqueue to channel-specific sorted set
     │
     ├──────────────┬──────────────┬─────────────────┐
     ▼              ▼              ▼                  ▼
[Push Queue]  [Email Queue]  [SMS Queue]    [In-App Store]
(Redis sorted  (Redis sorted  (Redis sorted  (PostgreSQL,
 set, AOF)     set, AOF)      set, AOF)      partitioned)
     │              │              │                  │
     ▼              ▼              ▼            Redis Streams
[Push Workers] [Email Workers] [SMS Workers]  → WebSocket
(APNs/FCM)    (SES/Postmark)  (Twilio)         servers
     │              │              │
     └──────────────┴──────────────┘
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archival)
                    │
                    ▼
           [Feedback Processor]
           (bounces, 410s, invalidity
            → suppression cache write + TTL
            → PostgreSQL suppression records)
```

### 2.3 PostgreSQL Schema and Partitioning

The event log will accumulate hundreds of millions of rows over six months. Without partitioning, the recovery query degrades from milliseconds to minutes as the table grows — and runs at exactly the worst moment, after a crash under load.

**Primary key design:** `event_id` alone does not satisfy PostgreSQL's partitioning constraint (partition key must be included in primary key), so the primary key is `(event_id, created_at)`. However, the worker claim protocol uses `WHERE event_id = %s`, which cannot use this composite key efficiently across partitions. We solve this by: (a) storing `event_id:YYYY-MM-DD` in the Redis queue so workers know the partition date, and (b) creating a unique index on `event_id` alone on each child partition, which claim queries target directly.

```sql
-- Parent table
CREATE TABLE notification_events (
    event_id          UUID NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id           BIGINT NOT NULL,
    event_type        TEXT NOT NULL,
    channel           TEXT NOT NULL,
    priority          SMALLINT NOT NULL,
    state             TEXT NOT NULL DEFAULT 'enqueued',
    -- state: enqueued | claimed | delivered | failed | suppressed
    worker_id         TEXT,
    claimed_at        TIMESTAMPTZ,
    attempt_number    INT NOT NULL DEFAULT 0,
    failure_reason    TEXT,
    idempotency_key   TEXT NOT NULL,
    PRIMARY KEY (event_id, created_at)
) PARTITION BY RANGE (created_at);

-- Child partition (created daily by E4's partition job, 7 days ahead)
CREATE TABLE notification_events_2024_01_22
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-22') TO ('2024-01-23');

-- Unique index on event_id within this partition
-- Worker claims targeting a known partition date use this index
CREATE UNIQUE INDEX idx_ne_20240122_event_id
    ON notification_events_2024_01_22 (event_id);

-- Recovery query index
CREATE INDEX idx_ne_20240122_state_created
    ON notification_events_2024_01_22 (state, created_at)
    WHERE state IN ('enqueued', 'claimed');
```

**Indexes are created on child partitions explicitly at creation time**, before data is written. Parent-level partial index behavior varies by PostgreSQL version; we do not rely on it.

**Redis queue entry format:** Workers store `event_id:YYYY-MM-DD` as the sorted set member. Workers parse this to extract both the `event_id` and the partition date, enabling single-partition claim queries:

```python
# Enqueue
member = f"{event_id}:{created_at.strftime('%Y-%m-%d')}"
redis.zadd(f"notify:{channel}:p{priority}", {member: timestamp})

# Worker dequeue and claim
raw = redis.zpopmin(f"notify:{channel}:p{priority}")
event_id, partition_date = raw[0].split(":")
table = f"notification_events_{partition_date.replace('-', '_')}"

rows_updated = db.execute(f"""
    UPDATE {table}
    SET state = 'claimed', worker_id = %s, claimed_at = NOW(),
        attempt_number = attempt_number + 1
    WHERE event_id = %s AND state = 'enqueued'
""", (worker_id, event_id))
```

This is a minor increase in member size (~46 bytes vs. 36 bytes for a UUID string) with a significant correctness and performance benefit: claims hit a single partition using the unique index.

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions. The active table never exceeds ~30 days of data.

### 2.4 Idempotency Key Construction

The idempotency key must change on every delivery attempt, including recovery-path re-enqueues — otherwise provider-side deduplication is defeated for the exact crash scenarios the system is designed to handle. We track `attempt_number` in the database and increment it atomically during the claim step (see §2.3 claim query above).

```python
# After successful claim, read back the incremented attempt_number
row = db.execute(f"""
    SELECT attempt_number, idempotency_key
    FROM {table} WHERE event_id = %s
""", (event_id,)).fetchone()

# Construct delivery-attempt-specific idempotency key
idempotency_key = f"{event_id}:{row.attempt_number}"
```

Provider usage:
- **APNs:** `apns-collapse-id` header (deduplicates within provider retry window)
- **FCM:** `collapse_key` field
- **SES:** `ClientRequestToken` parameter

These keys are passed at delivery time. The provider deduplicates on its end within its supported retry window; we log the key alongside the delivery attempt for our own audit trail.

### 2.5 Delivery Semantics

**The fundamental constraint:** Delivering a notification and recording that delivery are operations against two different systems. There is no atomic transaction spanning both.

- **At-most-once** (claim, deliver, record): If the worker crashes after delivery but before recording, the notification was delivered but we have no record. Recovery re-enqueues it and it is not re-delivered. **Result: possible lost delivery.**
- **At-least-once** (record attempt, deliver, record completion): If the worker crashes after delivery but before recording completion, recovery re-enqueues it and it is delivered again. **Result: possible duplicate delivery.**

We choose **at-least-once**. Duplicate delivery is bounded and detectable; lost delivery for P0 events is worse.

### 2.6 Worker Claim Protocol

```python
def process_notification(event_id: str, partition_date: str, worker_id: str):
    table = f"notification_events_{partition_date.replace('-', '_')}"

    # Atomic claim + attempt_number increment
    rows_updated = db.execute(f"""
        UPDATE {table}
        SET state = 'claimed',
            worker_id = %s,
            claimed_at = NOW(),
            attempt_number = attempt_number + 1
        WHERE event_id = %s AND state = 'enqueued'
    """, (worker_id, event_id))

    if rows_updated == 0:
        return  # Another worker claimed it; discard silently

    row = db.execute(f"""
        SELECT attempt_number, channel FROM {table} WHERE event_id = %s