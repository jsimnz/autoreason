# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision. Workers are fungible within a channel; priority is a property of queue position, not the worker. **Exception:** SMS P0 gets a dedicated worker because the general dequeue loop's polling latency is unacceptable for security-critical events (auth codes, account compromise alerts). This is not a contradiction — it is the correct application of the principle: use dedicated workers when latency requirements cannot be met by polling intervals, and only then.
- **At-least-once delivery with idempotency keys.** We cannot atomically claim a database row and deliver a push notification — these are two different systems. We accept duplicate delivery as a bounded, logged operational condition rather than claiming to have eliminated it. Provider-side idempotency keys (APNs `apns-collapse-id`, FCM `collapse_key`, SES `ClientRequestToken`) bound the duplicate window where supported.
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

**Notification fanout (recipient side):**

We do not send per-follower notifications for posts. Only direct interactions (follows, comments, mentions, likes on your content) generate notifications. Average fanout is approximately 1.2.

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
| Email | 9% | ~1.3M events | ~35/sec pre-batch |
| SMS | <0.01% | ~1,500 | negligible |

**Email volume and batching:**

The relevant denominator for batching reduction is email-opted-in users, not total recipients. We do not know the opt-in rate at design time; we measure it during Phase 1. For planning purposes:

| Email Opt-In Rate | Opted-In Users (of 3M DAU) | Events/User/Day (λ) | Batching Reduction | Delivered/Day |
|-------------------|---------------------------|---------------------|--------------------|---------------|
| 10% (conservative) | 300K | 4.3 | ~2.5× | ~520K |
| 20% (base case) | 600K | 2.2 | ~1.8× | ~720K |
| 40% (high opt-in) | 1.2M | 1.1 | ~1.2× | ~1.1M |

We use the 20% opt-in / 1.8× reduction / 720K delivered/day figure for worker sizing and recalibrate after Phase 1. Delivered email peak rate: 720K/day ÷ 86,400 × 3 ≈ **25/sec peak**.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group with explicit ACK and a configured pending entry timeout. Neither engineer writes directly into the other's domain.

**Timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §6 for explicit contingencies.

---

## 2. System Architecture

### 2.1 Priority Classification

The router assigns priority at ingestion time based on event type. Classification is exhaustive — every event type is assigned a priority at definition time, not at routing time. The router performs a lookup, not a judgment call. New event types require a pull request that includes a priority assignment; unclassified events are rejected with a logged error, not silently defaulted.

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
  - Assigns idempotency_key (event_id + channel + attempt_number)
  - Writes to PostgreSQL event log (state=enqueued)
  - Enqueues to Redis sorted set with event_id as member
     │
     ▼
[Notification Router]
  - Priority lookup (static classification table)
  - Preference check (Redis cache, TTL=5min, write-through)
  - Suppression check (shared Redis Hash)
  - Aggregation window check
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
            → shared suppression cache
            → PostgreSQL suppression records)
```

### 2.3 PostgreSQL Schema and Partitioning

The event log will accumulate hundreds of millions of rows over six months. Without partitioning, the recovery query degrades from milliseconds to minutes as the table grows — and runs at exactly the worst moment, after a crash under load.

**Partition index propagation:** We do not define indexes on the parent table. In PostgreSQL, parent-level partial index behavior varies by version and index type. E4's partition creation job creates indexes on each child partition explicitly at creation time, before data is written to that partition.

```sql
-- Parent table: no indexes defined here
CREATE TABLE notification_events (
    event_id        UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    channel         TEXT NOT NULL,
    priority        SMALLINT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'enqueued',
    -- state: enqueued | claimed | delivered | failed | suppressed
    worker_id       TEXT,
    claimed_at      TIMESTAMPTZ,
    failure_reason  TEXT,
    idempotency_key TEXT NOT NULL,
    PRIMARY KEY (event_id, created_at)
) PARTITION BY RANGE (created_at);
```

**Partition creation job** (runs daily, creates partitions 7 days ahead):

```sql
CREATE TABLE notification_events_2024_01_22
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-22') TO ('2024-01-23');

-- Indexes created on the child partition explicitly
CREATE INDEX idx_ne_20240122_state_created
    ON notification_events_2024_01_22 (state, created_at)
    WHERE state = 'enqueued';

CREATE INDEX idx_ne_20240122_worker_claimed
    ON notification_events_2024_01_22 (worker_id, claimed_at)
    WHERE state = 'claimed';
```

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. The active table never exceeds ~30 days of data. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions.

**Recovery query with partition pruning:**

```sql
-- Scans at most two daily partitions due to created_at filter
SELECT event_id, channel, priority FROM notification_events
WHERE created_at > NOW() - INTERVAL '2 hours'
  AND (
    state = 'enqueued'
    OR (state = 'claimed' AND claimed_at < NOW() - INTERVAL '10 minutes')
  );
```

### 2.4 Delivery Semantics

**The fundamental constraint:** Delivering a notification and recording that delivery are operations against two different systems. There is no atomic transaction spanning both.

- **At-most-once** (claim, deliver, record): If the worker crashes after delivery but before recording, the notification was delivered but we have no record. Recovery re-enqueues it and it is not re-delivered. **Result: possible lost delivery.**
- **At-least-once** (record attempt, deliver, record completion): If the worker crashes after delivery but before recording completion, recovery re-enqueues it and it is delivered again. **Result: possible duplicate delivery.**

We choose **at-least-once with idempotency keys**. Duplicate delivery is bounded and detectable; lost delivery for P0 events is worse. The idempotency key is passed to providers that support it — the provider deduplicates on its end within its supported retry window.

### 2.5 Worker Claim Protocol

The claim step prevents two workers from delivering the same notification concurrently and enables the recovery job to detect stuck workers. It does not prevent duplicate delivery in crash scenarios — see §2.4.

```python
def process_notification(event_id: str, worker_id: str, idempotency_key: str):
    # Atomic claim: only succeeds if state is still 'enqueued'
    rows_updated = db.execute("""
        UPDATE notification_events
        SET state = 'claimed',
            worker_id = %s,
            claimed_at = NOW()
        WHERE event_id = %s
          AND state = 'enqueued'
    """, (worker_id, event_id))

    if rows_updated == 0:
        return  # Another worker claimed it; discard silently

    try:
        deliver(event_id, idempotency_key=idempotency_key)

        db.execute("""
            UPDATE notification_events SET state = 'delivered'
            WHERE event_id = %s
        """, (event_id,))

        db.execute("""
            INSERT INTO delivery_log
                (event_id, channel, provider_response, idempotency_key)
            VALUES (%s, %s, %s, %s)
        """, (event_id, channel, response, idempotency_key))

    except DeliveryException as e:
        db.execute("""
            UPDATE notification_events
            SET state = 'failed', failure_reason = %s
            WHERE event_id = %s
        """, (str(e), event_id))
        raise  # re-queue for retry with incremented attempt_number
```

**Recovery job:**

```python
def recovery_job():
    stuck_threshold = datetime.now() - timedelta(minutes=10)

    events = db.execute("""
        SELECT event_id, channel, priority FROM notification_events
        WHERE created_at > NOW() - INTERVAL '2 hours'
          AND (
            state = 'enqueued'
            OR (state = 'claimed' AND claimed_at < %s)
          )
    """, (stuck_threshold,))

    for event in events:
        rows_updated = db.execute("""
            UPDATE notification_events
            SET state = 'enqueued', worker_id = NULL, claimed_at = NULL
            WHERE event_id = %s
              AND (state = 'enqueued' OR (state = 'claimed' AND claimed_at < %s))
        """, (event.event_id, stuck_threshold))

        if rows_updated > 0:
            redis.zadd(f"notify:{event.channel}:p{event.priority}",
                      {event.event_id: time.time()})
```

**Tradeoff:** One additional PostgreSQL write per notification (the claim UPDATE) at ~500/sec peak. PostgreSQL handles tens of thousands of writes/sec on modest hardware; this does not move the needle.

### 2.6 Queue Persistence

```
redis.conf (notification queue Redis instance):
  appendonly yes
  appendfsync everysec
  no-appendfsync-on-rewrite no
  auto-aof-rewrite-percentage 100
  auto-aof-rewrite-min-size 64mb
```

AOF rewrites are scheduled during off-peak hours to avoid ingestion latency spikes. On crash, we lose at most ~1 second of enqueued notifications (~500 at peak). The PostgreSQL event log with the recovery protocol handles these safely.

**Why not Redis Cluster:** Cluster provides availability, not durability. AOF on a single instance with a PostgreSQL backstop gives durability with predictable latency at our scale. Cluster becomes relevant when we exceed single-instance throughput limits; at 500/sec peak we do not.

### 2.7 Priority Enforcement

Workers within a channel pool are fungible. Each worker executes the same dequeue loop:

```python
def dequeue_loop(redis_client, channel):
    queues = [
        f"notify:{channel}:p0",
        f"notify:{channel}:p1",
        f"notify:{channel}:p2",
        f"notify:{channel}:p3",
    ]