# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels. The revised version addresses ten specific architectural deficiencies identified in review. Changes are called out explicitly where they alter prior decisions.

The core architectural choices remain:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision
- **Redis AOF persistence with fsync=everysec** plus a PostgreSQL event log as recovery backstop — with a corrected recovery protocol that eliminates the duplicate-delivery race
- **WebSocket connection registry with explicit gap detection** — with the "connecting" state deferred check now backed by a durable queue
- **Per-channel queues** isolating channel failures

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring. These require a functioning baseline. We build the baseline.

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

Higher opt-out means lower load. The conservative planning choice maximizes load — the lowest opt-out rate.

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | **Design ceiling — highest load** | ~14.4M | ~500/sec |
| 40% | Base case | ~10.8M | ~375/sec |
| 60% | Lower bound | ~7.2M | ~250/sec |

We design for the 20% opt-out scenario (14.4M/day, 500/sec peak). We measure actual opt-out during Phase 1 rollout and recalibrate before scaling to full MAU.

**Channel distribution — 20% opt-out design ceiling:**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events → delivered emails TBD below | ~18/sec peak |
| SMS | <0.01% | ~1,500 | negligible |

**Email batching — corrected derivation:**

The previous version stated "2.5× batching reduction" without derivation. That number is replaced with a model.

Batching consolidates notifications to the same recipient within a 15-minute window. The reduction factor depends on: (a) how many distinct actors interact with the same recipient's content within a 15-minute window, and (b) how many notifications those interactions generate.

Working from first principles:
- 1.3M email-eligible events/day distributed across 10M users = 0.13 events/user/day average
- Active recipients (those generating email events) are a subset. Assume 1M distinct recipients/day receiving email-eligible events
- Average events per recipient per day: 1.3M ÷ 1M = 1.3 events/recipient/day
- Events per recipient per 15-minute window: 1.3 ÷ 96 windows = 0.014 events/window on average
- Most recipients receive at most one event per window — batching reduces volume only for recipients receiving multiple events in the same window

At 1.3 average events/recipient/day, the distribution is heavily right-skewed: most recipients get 1 event, a small fraction get many. Modeling a Poisson distribution with λ=1.3: P(>1 event/day) ≈ 37%. Within a 15-minute window with λ=0.014, P(>1 event/window) ≈ 1%. Batching's consolidation effect is real but modest at this volume.

**Revised batching reduction estimate: 1.3× (range: 1.1×–1.6×)**

This yields:
- Delivered emails/day: 1.3M ÷ 1.3 = **~1.0M emails/day** (range: 810K–1.18M)
- Peak delivery rate: ~35/sec (versus the prior estimate of ~18/sec)

**This is a meaningful correction.** Email worker provisioning, SES throughput limits, and IP warming ramp are all recalculated against 1.0M/day in §3.2.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers; APNs JWT monitoring |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes durable suppression records. Neither engineer writes directly into the other's domain.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Assigns event_id (UUID)
  - Writes to PostgreSQL event log (state=enqueued, worker_id=NULL)
  - Enqueues to Redis sorted set with event_id as payload
     │
     ▼
[Notification Router]
  - Preference check (Redis cache, TTL=5min, write-through)
  - Suppression check (shared Redis Hash)
  - Priority assignment
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

### 2.2 PostgreSQL Schema and Partitioning

**Previously unaddressed:** The event log and delivery log will accumulate hundreds of millions of rows over six months. Without partitioning and a retention policy, the recovery job query ("events in state enqueued with no delivery log entry") degrades from milliseconds to minutes as the table grows — and this query runs at exactly the worst moment, after a crash under load.

**Event log partitioning:**

```sql
CREATE TABLE notification_events (
    event_id        UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    channel         TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'enqueued',
    -- state: enqueued | claimed | delivered | failed | suppressed
    worker_id       TEXT,           -- set on claim, NULL until then
    claimed_at      TIMESTAMPTZ,    -- set on claim
    PRIMARY KEY (event_id, created_at)
) PARTITION BY RANGE (created_at);

-- Daily partitions, created by E4's partition maintenance job
-- running nightly, creating partitions 7 days ahead
CREATE TABLE notification_events_2024_01_15
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-15') TO ('2024-01-16');

-- Indexes per partition (inherited automatically)
CREATE INDEX ON notification_events (state, created_at)
    WHERE state = 'enqueued';  -- partial index — only unresolved events
CREATE INDEX ON notification_events (worker_id, claimed_at)
    WHERE state = 'claimed';   -- for stuck-worker detection
```

**Retention policy:** Partitions older than 30 days are archived to S3 (Parquet format via pg_partman + a nightly job) and dropped. The active table never exceeds ~30 days of data. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions. Each partition is ~14.4M rows — manageable with per-partition indexes.

**Delivery log:**

```sql
CREATE TABLE delivery_log (
    event_id        UUID NOT NULL,
    channel         TEXT NOT NULL,
    delivered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider_response JSONB,
    PRIMARY KEY (event_id, delivered_at)
) PARTITION BY RANGE (delivered_at);
-- Same partitioning and retention strategy as notification_events
```

**Recovery query with partition pruning:**

```sql
-- Only scans the current and previous partition due to created_at filter
SELECT event_id FROM notification_events
WHERE state = 'enqueued'
  AND created_at > NOW() - INTERVAL '2 hours'  -- partition pruning
  AND claimed_at IS NULL;                       -- truly unclaimed
```

The 2-hour window limits the scan to at most two daily partitions. The partial index on `(state, created_at) WHERE state = 'enqueued'` makes this fast even within a partition.

### 2.3 Recovery Protocol — Corrected for Duplicate-Delivery Race

**The problem with the previous design:** The recovery job queried for events with `state=enqueued` and no delivery log entry, then re-enqueued them. But delivery workers wrote the delivery log entry *after* processing. During the window between a worker dequeuing an event and writing the delivery log, the recovery job could find that event, classify it as undelivered, and re-enqueue it. The original worker would deliver it; the re-enqueued copy would deliver it again. The previous proposal called this "idempotent" — it is not.

**The fix: explicit claim step using optimistic locking.**

Workers claim events before processing using an atomic state transition. The recovery job only re-enqueues events that are genuinely unclaimed.

**Worker claim protocol:**

```python
def process_notification(event_id: str, worker_id: str):
    # Step 1: Atomic claim — only succeeds if state is still 'enqueued'
    rows_updated = db.execute("""
        UPDATE notification_events
        SET state = 'claimed',
            worker_id = %s,
            claimed_at = NOW()
        WHERE event_id = %s
          AND state = 'enqueued'
    """, (worker_id, event_id))

    if rows_updated == 0:
        # Another worker already claimed this event (race resolved correctly)
        # or recovery job re-enqueued it and another worker claimed it
        return  # discard silently

    # Step 2: Process and deliver
    try:
        deliver(event_id)
        db.execute("""
            UPDATE notification_events SET state = 'delivered' WHERE event_id = %s
        """, (event_id,))
        db.execute("""
            INSERT INTO delivery_log (event_id, channel, provider_response) VALUES (...)
        """)
    except Exception as e:
        db.execute("""
            UPDATE notification_events
            SET state = 'failed', failure_reason = %s
            WHERE event_id = %s
        """, (str(e), event_id))
        raise  # re-queue for retry
```

**Recovery job — safe version:**

```python
def recovery_job():
    # Only targets events that are:
    # (a) in 'enqueued' state (never claimed), OR
    # (b) in 'claimed' state with claimed_at > 10 minutes ago (stuck worker)
    stuck_threshold = datetime.now() - timedelta(minutes=10)

    events = db.execute("""
        SELECT event_id FROM notification_events
        WHERE created_at > NOW() - INTERVAL '2 hours'
          AND (
            state = 'enqueued'
            OR (state = 'claimed' AND claimed_at < %s)
          )
    """, (stuck_threshold,))

    for event in events:
        # Reset claimed events to enqueued before re-enqueueing
        db.execute("""
            UPDATE notification_events
            SET state = 'enqueued', worker_id = NULL, claimed_at = NULL
            WHERE event_id = %s
              AND (state = 'enqueued' OR (state = 'claimed' AND claimed_at < %s))
        """, (event.event_id, stuck_threshold))
        # Only re-enqueue if the UPDATE succeeded (rows_affected > 0)
        if db.rows_affected > 0:
            redis.zadd(f"notify:{event.channel}:p{event.priority}", 
                      {event.event_id: time.time()})
```

**Why this is correct:** The claim UPDATE is atomic and conditional on `state = 'enqueued'`. If two workers race, exactly one succeeds. The recovery job's stuck-worker path resets `claimed_at` only if it's older than 10 minutes — a live worker will have completed or failed within that window. The recovery job's own UPDATE is also conditional, so it cannot race with a live worker's claim.

**Tradeoff:** One additional PostgreSQL write per notification (the claim UPDATE) at ~500/sec peak = ~500 additional writes/sec. At our scale this is acceptable. PostgreSQL handles tens of thousands of writes/sec on modest hardware; 500 additional writes does not move the needle.

### 2.4 Queue Persistence

**Configuration: AOF with fsync=everysec**

```
redis.conf (notification queue Redis instance):
  appendonly yes
  appendfsync everysec
  no-appendfsync-on-rewrite no
  auto-aof-rewrite-percentage 100
  auto-aof-rewrite-min-size 64mb
```

On crash, we lose at most ~1 second of enqueued notifications (~500 at peak). The PostgreSQL event log with the corrected recovery protocol handles these. The claim step ensures recovery is safe to run at any time without duplicate delivery.

### 2.5 Priority Enforcement — Corrected for SMS P0 Contradiction

**Previously identified contradiction:** The proposal accepted that "a P0 email cannot preempt a P1 push in the push worker pool" because P0 events go to SMS or email. But SMS was provisioned at 3 workers for negligible volume, with no preemption mechanism for P0 events competing with P1 SMS. This contradicts the stated rationale.

**Correction: SMS P0 events get a dedicated fast path, not just a priority queue.**

SMS is the designated channel for P0 security events (auth codes, account compromise alerts). The "negligible volume" characterization is correct for P1–P3 SMS but wrong as a reason to deprioritize P0 SMS delivery infrastructure.

**Revised SMS worker design:**

```
SMS Workers:
  - 1 dedicated P0 worker — processes ONLY notify:sms:p0
  - 2 