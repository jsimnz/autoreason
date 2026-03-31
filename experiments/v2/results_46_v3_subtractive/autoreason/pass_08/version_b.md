# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score. Workers are fungible within a channel; priority is a property of queue position. **Exception:** SMS P0 gets a dedicated worker — but the justification is corrected from the prior draft. The latency problem for SMS P0 is end-to-end pipeline latency, not worker polling interval. The dedicated worker is paired with a fast-path ingestion route that bypasses the standard aggregation window check and uses a pre-warmed preference cache entry, reducing the pipeline to ingestion → router → dedicated worker. This is described in §2.8.
- **At-least-once delivery with idempotency keys.** We cannot atomically claim a database row and deliver a push notification. We accept duplicate delivery as a bounded, logged operational condition. Provider-side idempotency keys bound the duplicate window where supported — but idempotency keys must be stable across the specific crash scenarios we face, including recovery-path re-enqueues. The key construction is specified precisely in §2.4.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets, with a PostgreSQL event log as recovery backstop. AOF rewrite scheduling is addressed as an operational reality, not a stated property with no implementation.
- **Per-channel queues** isolating channel failures.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring.

**What we're explicitly accepting as limitations:** Duplicate delivery is possible in crash scenarios. We bound it, log it, and target a duplicate rate below 0.01% of delivered notifications. The recovery window is bounded and that boundary is monitored with alerting, not silently abandoned.

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

We design for the 20% opt-out scenario (14.4M/day, 500/sec peak).

**Channel distribution — 20% opt-out design ceiling:**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events | ~35 pre-batch |
| SMS | <0.01% | ~1,500 | negligible |

**Email volume and batching:**

The prior draft presented batching reduction multipliers (2.5×, 1.8×, 1.2×) without derivation. These numbers were load-bearing for worker sizing and were not calculated from the Poisson λ values shown alongside them. This section derives them explicitly.

We model per-user email-triggering events as Poisson with rate λ events/day. With a 30-minute batching window, the expected number of events per window is μ = λ/48. We send one email per window if at least one event occurred. The expected number of emails sent per user per day is:

```
emails_per_user_per_day = 48 × P(at least one event in window)
                        = 48 × (1 - e^(-μ))
                        = 48 × (1 - e^(-λ/48))
```

The batching reduction factor is λ / emails_per_user_per_day:

```
reduction = λ / (48 × (1 - e^(-λ/48)))
```

For small λ (λ << 48), e^(-λ/48) ≈ 1 - λ/48, so reduction ≈ 1 (no meaningful batching — most windows have zero events). For large λ (λ >> 48), nearly every window has an event, so emails_per_user_per_day → 48 and reduction → λ/48.

| Email Opt-In Rate | Opted-In DAU | λ (events/user/day) | Calculated Reduction | Emails/User/Day | Delivered/Day |
|-------------------|-------------|---------------------|----------------------|-----------------|---------------|
| 10% | 300K | 4.3 | **1.49×** | 2.89 | ~867K |
| 20% (base case) | 600K | 2.2 | **1.23×** | 1.79 | ~1.07M |
| 40% | 1.2M | 1.1 | **1.11×** | 0.99 | ~1.19M |

**Correction from prior draft:** The prior multipliers (2.5×, 1.8×, 1.2×) were fabricated. The calculated figures show substantially less batching reduction than assumed. At λ=2.2, most users receive 1–2 email-triggering events per day and a 30-minute window rarely catches more than one. The practical implication: email delivered volume is higher than previously estimated (up to ~1.1M/day vs. 720K/day at base case), and email worker sizing must reflect this. We use the 20% opt-in / 1.07M delivered/day figure.

**Delivered email peak rate:** 1.07M/day ÷ 86,400 × 3 ≈ **37/sec peak.** This is within the capacity of a single SES connection at standard throughput limits; the worker sizing in §4 reflects this.

**Note on batching window choice:** A 30-minute window is a product decision, not a derived one. Shorter windows (5 minutes) reduce batching benefit further; longer windows (2 hours) improve batching but degrade perceived responsiveness. We use 30 minutes as a reasonable default and expose it as a configurable parameter. The formulas above apply at any window size.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; suppression cache invalidation |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; connection pool management; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream with a `MAXLEN` cap (see §2.9). E3's feedback processor consumes them via a named consumer group with explicit ACK and a configured pending entry timeout. Neither engineer writes directly into the other's domain. The suppression cache invalidation path for user-initiated re-enablement is E3's responsibility and is described in §3.3.

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

### 2.2 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Assigns event_id (UUID v7, time-ordered)
  - Computes idempotency_key (see §2.4 for exact construction)
  - Writes to PostgreSQL event log (state=enqueued)
  - Enqueues to Redis sorted set with score=timestamp
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

**Corrected primary key design:** The prior draft defined `PRIMARY KEY (event_id, created_at)`. This was incorrect. In PostgreSQL, a composite primary key on `(event_id, created_at)` means `event_id` alone does not uniquely identify a row. The worker claim protocol uses `WHERE event_id = %s`, which cannot use this primary key and must scan across all partitions — exactly the performance problem the partitioning was meant to solve.

**Correct approach:** `event_id` is a UUID v7 (time-ordered). We partition by the timestamp embedded in the UUID, extracted at insert time into `created_at`. The primary key is `(event_id, created_at)` only in the sense required by PostgreSQL's partitioning constraint — but we add a **unique index on `event_id` alone** on each partition, which is what the worker claim protocol actually uses. We also add `created_at` as a NOT NULL column with a check constraint ensuring it matches the partition range, so `event_id` lookups hit at most one partition when combined with a `created_at` filter, and the unique index handles the single-partition case.

**More precisely:** Because UUID v7 embeds a millisecond timestamp, and our partitions are daily, we know `created_at` for any given `event_id` within ~1 day of precision. The recovery query always includes a `created_at` range filter, so partition pruning applies. The worker claim protocol receives `event_id` from the Redis queue entry, which we store as `event_id:created_at_date` (see §2.5) to enable single-partition targeting.

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

-- Recovery query index: state + created_at for range scans
CREATE INDEX idx_ne_20240122_state_created
    ON notification_events_2024_01_22 (state, created_at)
    WHERE state IN ('enqueued', 'claimed');
```

**Redis queue entry format:** Instead of storing bare `event_id` as the sorted set member, we store `event_id:YYYY-MM-DD`. Workers parse this to extract both the `event_id` and the partition date, enabling single-partition claim queries:

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
    SET state = 'claimed', worker_id = %s, claimed_at = NOW()
    WHERE event_id = %s AND state = 'enqueued'
""", (worker_id, event_id))
```

This is a minor increase in member size (~46 bytes vs. 36 bytes for a UUID string) with a significant correctness and performance benefit: claims hit a single partition using the unique index.

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions. The active table never exceeds ~30 days of data.

### 2.4 Idempotency Key Construction

**The problem with the prior draft:** The idempotency key was defined as `event_id + channel + attempt_number`, with `attempt_number` incremented on retry. But the recovery job resets `state = 'enqueued'` without incrementing `attempt_number`, meaning re-enqueued events reuse the same idempotency key. This defeats provider-side deduplication for the exact crash scenarios the system is designed to handle.

**Correct construction:** The idempotency key must change on every delivery attempt, including recovery-path re-enqueues. We track `attempt_number` in the database and increment it atomically during the claim step:

```python
# During claim (single UPDATE, returns new attempt_number)
result = db.execute(f"""
    UPDATE {table}
    SET state = 'claimed',
        worker_id = %s,
        claimed_at = NOW(),
        attempt_number = attempt_number + 1
    WHERE event_id = %s AND state = 'enqueued'