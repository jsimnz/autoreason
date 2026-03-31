# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 14.4M routed notification events per day across push, email, in-app, and SMS channels. The routed event count and delivered message count are distinct figures and are not interchangeable.

**Core architectural choices and their honest tradeoffs:**

- **Per-channel worker pools** with priority enforced via sorted set score. SMS P0 gets a dedicated worker with a fast-path ingestion route that bypasses the aggregation window check but retains all suppression checks. The suppression check for P0 SMS reads from a write-path-updated cache (TTL=30 seconds, not 5 minutes) that is written synchronously by the preference API on opt-out. This is the TCPA compliance mechanism.
- **At-least-once delivery.** Provider-side idempotency keys deduplicate network-level retries within a single attempt only. They provide zero protection against crash-recovery duplicates, because each recovery attempt uses a new key. The 0.01% duplicate target is an operational target, not a guarantee.
- **Redis AOF with `fsync=everysec`** means up to 1 second of queue state can be lost on crash. PostgreSQL is the recovery source. The recovery job is the designed closure for that window.
- **Partition-date-free queue members.** Workers store only the `event_id` UUID in Redis. A routing table written at ingestion time maps each event to its partition. This eliminates silent correctness failures at date boundaries and the SQL injection surface from parsing Redis-supplied partition dates.
- **Routing table as a correctness mechanism** with an acknowledged failure mode: the routing table and event log are written in a single transaction. If the transaction fails, the caller receives a 503 and retries. The failure mode "event written, routing entry missing" cannot occur under this design.

**What we are deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring.

**What we are explicitly accepting as limitations:** Duplicate delivery is possible in crash-recovery scenarios. The mechanism that bounds it (staleness threshold) is specified. In-app delivery to offline clients is best-effort with client-side sync on reconnect.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Event generation:**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU, typical social apps |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |
| Fanout multiplier | 1.2 | Direct interactions only |
| Raw recipient-notification events/day | ~18M | 15M × 1.2 |

**Opt-out sensitivity:**

| Opt-Out Rate | Routed Events/Day | Peak (3×) |
|-------------|-------------------|-----------|
| 20% | ~14.4M | ~500/sec |
| 40% | ~10.8M | ~375/sec |
| 60% | ~7.2M | ~250/sec |

We design for the 20% opt-out scenario.

### 1.2 Channel Distribution — Multi-Channel Users

Channel opt-in rates are independent, not mutually exclusive. A single notification generates one delivery event per enabled channel per user. Applying channel percentages as a partition of routed events undercounts total delivery volume.

We model independent channel opt-in rates among users who have not globally opted out:

| Channel | Opt-In Rate | Routed Events/Day | Peak Events/sec |
|---------|-------------|-------------------|-----------------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 100% (all active sessions) | ~14.4M | ~500 |
| Email | 20% | ~2.9M routed events | ~100 pre-batch |
| SMS | <0.01% | ~1,500 | negligible |

**Total routed delivery events/day: ~27.2M.** The 14.4M figure is recipient-notification events before channel expansion; these are distinct numbers and must not be conflated.

**In-app** is generated for all non-opted-out users regardless of other channel preferences. Users who have also enabled push receive both. This is intentional product behavior.

**Email batching math:**

At 20% email opt-in, opted-in DAU = 600K. Email-triggering events per opted-in user per day: 2.9M ÷ 600K ≈ 4.8 (λ). With a 30-minute batching window, μ = λ/48:

```
emails_per_user_per_day = 48 × (1 - e^(-μ))
= 48 × (1 - e^(-0.1)) ≈ 48 × 0.095 ≈ 4.57
delivered_emails/day ≈ 600K × 4.57 ≈ 2.74M
delivered_email_peak ≈ 2.74M ÷ 86,400 × 3 ≈ 95/sec peak
reduction_factor ≈ 1.05×
```

The low reduction factor reflects that 30-minute windows rarely accumulate multiple events per user at this λ. The batching window's primary value at this scale is latency control, not volume reduction.

**The batching window is a configurable product parameter.** When product changes this value, worker sizing and queue depth thresholds must be recalculated. The batching window value is stored in a configuration service; a configuration-change event triggers a recalculation job that outputs revised worker count recommendations and updated alert thresholds. This produces a recommendation requiring human review — it is not automatic — but ensures the dependency is not invisible. E1 owns this job.

**Worker sizing uses delivered volume. Queue depth monitoring uses routed event volume. These are different numbers and must not be conflated.**

### 1.3 SMS Cost Ceiling

At $0.0075/message, 1,500/day = ~$340/month. This does not constrain design choices.

### 1.4 Team Allocation

| Engineer | Primary Responsibility | Explicit Ownership |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, priority scoring, batching logic, partition pre-creation job | Recovery job staleness threshold definition; recalculation job for batching window changes |
| E2 | Channel integrations (APNs, FCM, SES, Twilio), token lifecycle | Token invalidity signal detection and structured event publication to `token.invalidated` stream |
| E3 | Preference management, user-facing API, suppression, TCPA compliance | Feedback processor (consumes `token.invalidated` stream); suppression cache write path; preference API opt-out synchronous cache write |
| E4 | Reliability, monitoring, failure handling, DevOps, WebSocket infrastructure | Recovery job runbook and operational response; partition pre-creation job monitoring; archival job; worker pool autoscaling |

**Resolved ownership conflicts:**
- Recovery job threshold calibration: E1 owns the design. E4 owns the runbook and operational response when thresholds are breached. These are distinct responsibilities.
- Token invalidity stream: E2 publishes; E3 configures and operates the consumer group. E4 monitors consumer group lag. No three-engineer dependency chain sits in the compliance path.

---

## 2. System Architecture

### 2.1 Priority Classification

The router assigns priority at ingestion time from a static lookup table. Every event type is assigned a priority at definition time. New event types require a pull request that includes a priority assignment; unclassified events are rejected with a logged error and an HTTP 422 response, not silently defaulted.

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
  - Validates event type against classification table; rejects unknowns (HTTP 422)
  - Single transaction: writes to notification_events AND event_partition_routing
  - On transaction failure: returns HTTP 503; caller retries; no orphaned events
  - Expands to per-channel delivery events based on user's enabled channels
  - Enqueues event_id (UUID only) to Redis sorted set
  - Score = Unix timestamp (milliseconds)
     │
     ▼
[Notification Router]
  - Priority lookup (static classification table)
  - Preference check (Redis cache, TTL=5min, write-through for non-TCPA channels)
  - Suppression check:
      - SMS/TCPA: reads from suppression cache (TTL=30sec, written synchronously
        by preference API on opt-out)
      - All other channels: reads from suppression cache (TTL=5min)
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
[Push Workers] [Email Workers] [SMS Workers]  (per-server
(APNs/FCM)    (SES/Postmark)  (Twilio)        consumer groups)
     │              │              │                  │
     └──────────────┴──────────────┘          [WebSocket servers]
                    │                          (online clients)
                    ▼                                 │
           [Delivery Log]                    [PostgreSQL in-app store]
           (PostgreSQL + S3 archival)        (offline clients; sync
                    │                         on reconnect)
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

-- Routing table (written in same transaction as notification_events insert)
CREATE TABLE event_partition_routing (
    event_id        UUID PRIMARY KEY,
    partition_date  DATE NOT NULL
);

-- Child partition (created by E1's partition job, 7 days ahead)
CREATE TABLE notification_events_2024_01_22
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-22') TO ('2024-01-23');

-- Indexes created at partition creation time, before data is written
CREATE UNIQUE INDEX idx_ne_20240122_event_id
    ON notification_events_2024_01_22 (event_id);

CREATE INDEX idx_ne_20240122_state_claimed
    ON notification_events_2024_01_22 (claimed_at)
    WHERE state IN ('enqueued', 'claimed');
```

**Alternative considered:** Querying the parent table directly and relying on PostgreSQL partition pruning on `event_id`. Rejected: pruning does not apply to non-partition-key columns. At 30 active partitions this would scan all partitions on every claim. The routing table costs one extra write at ingestion and one extra read at claim; this is the correct tradeoff.

**Partition pre-creation failure — analyzed.**

The partition pre-creation job runs daily and creates partitions 7 days ahead. If this job fails silently, inserts to `notification_events` will fail when the next day's partition does not exist — a total outage for new events.

Mitigations:
1. **Alerting:** E4 owns a monitoring check verifying partitions exist for the next 3 days. Alert fires if fewer than 3 future partitions are present. This gives 3 days of warning, not 7 days of silent drift.
2. **Fallback partition:** A catch-all partition covering a 90-day future range exists as a permanent safety net. It lacks the performance characteristics of daily partitions but prevents total outage. E4 owns the runbook for migrating catch-all rows into the correct daily partition after repair.
3. **Job idempotency:** The pre-creation job checks for existing partitions before creating them. Re-running it is safe.

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions. The active table never exceeds ~30 days of data.

**Worker claim logic:**

```python
def claim_event(event_id: str, worker_id: str, db) -> Optional[Row]:
    # Look up partition date from our own database, not from Redis input
    routing = db.execute(
        "SELECT partition_date FROM event_partition_routing WHERE event_id = %s",
        (event_id,)
    ).fetchone()

    if not routing:
        logger.error("claim_event: no routing entry for event_id=%s", event_id)
        return None

    # Construct table name from a validated date object; no user-controlled input here
    partition_date = routing.partition_date  # Python datetime.date from psycopg2
    table = "notification_events_" + partition_date.strftime("%Y_%m_%d")

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

### 2.4 Idempotency Key Construction

Provider-side idempotency keys deduplicate network-level retries within a single delivery attempt. A new key is constructed for each recovery re-enqueue — this is intentional. We want re-enqueued items delivered, not silently dropped. `attempt_number