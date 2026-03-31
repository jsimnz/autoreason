# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 14.4M routed notification events per day across push, email, in-app, and SMS channels. At a 20% email opt-in rate, batching reduces those routed events to approximately 1.07M delivered emails per day — these are distinct figures and are not interchangeable.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score. Workers are fungible within a channel; priority is a property of queue position. **Exception:** SMS P0 gets a dedicated worker paired with a fast-path ingestion route that bypasses the aggregation window check but explicitly retains all suppression checks including TCPA-required opt-out enforcement. This exception exists because P0 SMS end-to-end latency requirements cannot be met by the standard path; dedicated workers are justified only when that is true.
- **At-least-once delivery with idempotency keys, with an explicit scope statement.** Provider-side idempotency keys deduplicate network-level retries within a single delivery attempt. They do not deduplicate across crash-recovery re-enqueues, because each recovery attempt uses a new key. This is intentional: we want re-enqueued items delivered, not silently dropped. Crash-recovery duplicates are bounded by the recovery job's staleness threshold, logged, and targeted below 0.01% of delivered notifications.
- **Redis AOF with `fsync=everysec`** means up to 1 second of queue state can be lost on crash. The PostgreSQL event log is the authoritative recovery source for this window. The `zpopmin`-then-claim design has an explicit crash window between these two operations; the recovery job is the designed closure for that window, not an afterthought.
- **Per-channel queues** isolating channel failures. APNs degradation affects push workers only.
- **Partition-date-free queue members.** Workers store only the `event_id` UUID in Redis. A lightweight routing table (written at ingestion time) maps each event to its partition. This eliminates the silent correctness failure at date boundaries and the SQL injection surface from parsing Redis-supplied partition dates.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring.

**What we're explicitly accepting as limitations:** Duplicate delivery is possible in crash-recovery scenarios. We bound it via the recovery staleness threshold, log every instance, and target a rate below 0.01% of delivered notifications. In-app delivery to offline clients is best-effort with client-side sync on reconnect.

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

**Notification fanout:** Only direct interactions generate notifications. Average fanout is approximately 1.2.

**Recipient-notification events/day: 15M × 1.2 = ~18M events/day**

**Opt-out sensitivity:**

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | **Design ceiling** | ~14.4M | ~500/sec |
| 40% | Base case | ~10.8M | ~375/sec |
| 60% | Lower bound | ~7.2M | ~250/sec |

We design for the 20% opt-out scenario (14.4M routed events/day, 500/sec peak).

**Channel distribution — 20% opt-out design ceiling:**

| Channel | % | Routed Events/Day | Peak Events/sec | Delivered Messages/Day | Notes |
|---------|---|-------------------|-----------------|------------------------|-------|
| Push | 65% | ~9.4M | ~325 | ~9.4M | No batching; 1:1 |
| In-app | 25% | ~3.6M | ~125 | ~3.6M | No batching; 1:1 |
| Email | 9% | ~1.3M routed events | ~35 pre-batch | ~1.07M delivered | Batching reduces sends; see below |
| SMS | <0.01% | ~1,500 | negligible | ~1,500 | No batching for P0 |

**Email: routed events vs. delivered messages are different numbers.** Worker sizing uses delivered volume; queue depth monitoring uses routed event volume. These must not be conflated.

**Email batching math:**

We model per-user email-triggering events as Poisson with rate λ per day. With a 30-minute batching window, expected events per window is μ = λ/48:

```
emails_per_user_per_day = 48 × (1 - e^(-λ/48))
reduction_factor = λ / (48 × (1 - e^(-λ/48)))
```

| Email Opt-In Rate | Opted-In DAU | λ (events/user/day) | Reduction Factor | Emails/User/Day | Delivered/Day |
|-------------------|-------------|---------------------|-----------------|-----------------|---------------|
| 10% | 300K | 4.3 | 1.49× | 2.89 | ~867K |
| 20% (base case) | 600K | 2.2 | 1.23× | 1.79 | ~1.07M |
| 40% | 1.2M | 1.1 | 1.11× | 0.99 | ~1.19M |

At λ=2.2, the 30-minute window rarely catches more than one event per user. The batching window is a configurable product parameter, not a derived one.

**Delivered email peak rate:** 1.07M ÷ 86,400 × 3 ≈ **37/sec peak.**

**SMS cost ceiling:** At $0.0075/message, 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy; partition pre-creation job |
| E2 | Channel integrations (APNs, FCM, SES, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; suppression cache invalidation; TCPA opt-out enforcement |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; recovery job (threshold calibration, runbook); scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group with explicit ACK and a configured pending entry timeout. Neither engineer writes directly into the other's domain.

---

## 2. System Architecture

### 2.1 Priority Classification

The router assigns priority at ingestion time from a static lookup table. Classification is exhaustive — every event type is assigned a priority at definition time. New event types require a pull request that includes a priority assignment; unclassified events are rejected with a logged error, not silently defaulted.

| Priority | Label | Event Types | Target Delivery Latency |
|----------|-------|-------------|------------------------|
| P0 | Critical | Auth codes, account compromise alerts, payment failures | <2 seconds |
| P1 | High | Direct messages, mentions, replies to your content | <30 seconds |
| P2 | Normal | Likes, new followers, comments on your posts | <5 minutes |
| P3 | Bulk | Digest summaries, weekly recaps, promotional notifications | <1 hour |

**Tradeoff:** Static classification is less flexible than a scoring function. We accept this. A scoring function requires calibration data we do not have and introduces miscalibration bugs a lookup table does not.

### 2.2 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Assigns event_id (UUID v7, time-ordered)
  - Validates event type against classification table; rejects unknowns
  - Writes to PostgreSQL notification_events (state=enqueued)
  - Writes one row to event_partition_routing (same transaction)
  - Enqueues event_id (UUID only) to Redis sorted set
  - Score = Unix timestamp (milliseconds)
     │
     ▼
[Notification Router]
  - Priority lookup (static classification table)
  - Preference check (Redis cache, TTL=5min, write-through)
  - Suppression check (Redis Hash; always enforced, including P0 SMS)
  - Aggregation window check (bypassed for P0 only)
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
     │              │              │                  │
     └──────────────┴──────────────┘          [Client sync
                    │                          on reconnect]
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archival)
                    │
                    ▼
           [Feedback Processor]
           (bounces, 410s, invalidity
            → suppression cache write
            → PostgreSQL suppression records)
```

### 2.3 PostgreSQL Schema and Partitioning

The event log will accumulate hundreds of millions of rows over six months. Without partitioning, the recovery query degrades from milliseconds to minutes as the table grows — and runs at exactly the worst moment, after a crash under load.

**Partition-date-free queue design.** Encoding the partition date in the Redis member (`event_id:YYYY-MM-DD`) creates two problems: (1) clock skew or timezone misconfiguration between ingestion and workers can cause silent discard when `rows_updated == 0`; (2) parsing a Redis-supplied string and interpolating it into SQL is a SQL injection surface. The revised design stores only the `event_id` UUID in Redis and uses a routing table written at ingestion time.

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
    PRIMARY KEY (event_id, created_at)
) PARTITION BY RANGE (created_at);

-- Child partition (created by E4's partition job, 7 days ahead)
CREATE TABLE notification_events_2024_01_22
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-22') TO ('2024-01-23');

-- Unique index on event_id within each partition
CREATE UNIQUE INDEX idx_ne_20240122_event_id
    ON notification_events_2024_01_22 (event_id);

-- Partial index for recovery queries on this partition
CREATE INDEX idx_ne_20240122_state_claimed
    ON notification_events_2024_01_22 (claimed_at)
    WHERE state IN ('enqueued', 'claimed');
```

Indexes are created on child partitions at creation time, before data is written.

**Routing table for partition-safe claims:**

```sql
-- Written by ingestion API in the same transaction as the event log insert
-- Never updated after write
CREATE TABLE event_partition_routing (
    event_id        UUID PRIMARY KEY,
    partition_date  DATE NOT NULL
);
```

Workers look up `partition_date` here first, then target the specific partition. The partition date is recorded by the same process that wrote the event — it is not inferred from queue member encoding and is immune to clock skew.

**Alternative considered:** Querying the parent table directly and relying on PostgreSQL partition pruning on `event_id`. Rejected: pruning does not apply to non-partition-key columns. At 30 active partitions this would scan all partitions on every claim. The routing table costs one extra write at ingestion and one extra read at claim; this is the correct tradeoff.

```python
def claim_event(event_id: str, worker_id: str, db) -> Optional[Row]:
    # Step 1: Look up partition date from our own database (not from Redis input)
    routing = db.execute(
        "SELECT partition_date FROM event_partition_routing WHERE event_id = %s",
        (event_id,)
    ).fetchone()

    if not routing:
        logger.error("claim_event: no routing entry for event_id=%s", event_id)
        return None

    # Step 2: Construct table name from a validated date object
    # datetime.date.strftime is safe; no user-controlled input reaches this point
    partition_date = routing.partition_date  # Python datetime.date from psycopg2
    table = "notification_events_" + partition_date.strftime("%Y_%m_%d")

    # Step 3: Atomic claim with attempt increment, using identifier quoting
    from psycopg2 import sql
    rows_updated = db.execute(
        sql.SQL("""
            UPDATE {}
            SET state = 'claimed',
                worker_id = %s,
                claimed_at = NOW(),
                attempt_number = attempt_number + 1
            WHERE event_id = %s AND state = 'enqueued'
        """).format(sql.Identifier(table)),
        (worker_id, event_id)
    ).rowcount

    if rows_updated == 0:
        return None  # Another worker claimed it; discard silently

    return db.execute(
        sql.SQL("SELECT attempt_number, channel FROM {} WHERE event_id = %s")
            .format(sql.Identifier(table)),
        (event_id,)
    ).fetchone()
```

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions. The active table never exceeds ~30 days of data.

### 2.4 Idempotency Key Construction

Provider-side idempotency keys deduplicate network-level retries within a single delivery attempt. A new key is constructed for each recovery re-enqueue — this is intentional. We track `attempt_number` in the database and increment it atomically during the claim step.

```python
# After successful claim, construct delivery-attempt-specific key
idempotency_key = f"{event_id}:{row.attempt_number}"
```

Provider usage:
- **APNs:** `apns-collapse-id` header
- **FCM:** `collapse_key` field
- **SES:** `ClientRequestToken` parameter

### 2.5 Delivery Semantics

**The fundamental constraint:** Delivering a notification and recording that delivery are operations against two different systems. There is no atomic transaction spanning both.

- **At-most-once:** If the worker crashes after delivery but before recording, the notification was delivered but recovery re-enqueues it and it is not re-delivered. **Result: possible lost delivery.**
- **At-least-once:** If the worker crashes after delivery but before recording completion, recovery re-enqueues it and it is delivered again. **Result: possible duplicate delivery.**

We choose **at-least-once**. Duplicate delivery is bounded and detectable; lost