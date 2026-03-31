# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision. Dedicated priority pools create idle workers for rare high-priority events; fungible workers with priority-ordered dequeue are simpler and correct.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets, with a PostgreSQL event log as recovery backstop — with a claim-based protocol that eliminates the duplicate-delivery race.
- **WebSocket connection registry with explicit gap detection**, distinguishing "connecting" from "connected" from "offline."
- **Per-channel queues** isolating channel failures. APNs degradation affects push workers only; email workers continue unaffected.

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

We design for the 20% opt-out scenario (14.4M/day, 500/sec peak). We measure actual opt-out during Phase 1 rollout and recalibrate before scaling to full MAU. Architecture does not change; only worker pool sizing and Redis provisioning change.

**Channel distribution — 20% opt-out design ceiling:**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events → ~1.0M delivered | ~35/sec peak |
| SMS | <0.01% | ~1,500 | negligible |

**Email batching — derivation:**

Batching consolidates notifications to the same recipient within a 15-minute window. The reduction factor depends on how many distinct actors interact with the same recipient's content within that window.

Working from first principles:
- 1.3M email-eligible events/day across ~1M distinct recipients = 1.3 events/recipient/day average
- Events per recipient per 15-minute window: 1.3 ÷ 96 = 0.014 on average
- Modeling a Poisson distribution with λ=1.3: P(>1 event/day) ≈ 37%. Within a 15-minute window with λ=0.014, P(>1 event/window) ≈ 1%. Batching's consolidation effect is real but modest at this volume.

**Revised batching reduction estimate: 1.3× (range: 1.1×–1.6×)**

Delivered emails/day: 1.3M ÷ 1.3 = **~1.0M emails/day**. Peak delivery rate: ~35/sec. Email worker provisioning, SES throughput limits, and IP warming ramp are calculated against this figure in §3.2.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes durable suppression records. Neither engineer writes directly into the other's domain.

**Timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §6 for explicit contingencies.

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

The event log and delivery log will accumulate hundreds of millions of rows over six months. Without partitioning, the recovery job query ("events in state enqueued with no delivery log entry") degrades from milliseconds to minutes as the table grows — and runs at exactly the worst moment, after a crash under load.

```sql
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
    PRIMARY KEY (event_id, created_at)
) PARTITION BY RANGE (created_at);

-- Daily partitions created by E4's maintenance job, 7 days ahead
CREATE TABLE notification_events_2024_01_15
    PARTITION OF notification_events
    FOR VALUES FROM ('2024-01-15') TO ('2024-01-16');

-- Partial indexes per partition
CREATE INDEX ON notification_events (state, created_at)
    WHERE state = 'enqueued';
CREATE INDEX ON notification_events (worker_id, claimed_at)
    WHERE state = 'claimed';  -- for stuck-worker detection
```

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. The active table never exceeds ~30 days of data. At 14.4M events/day, 30 days = ~430M rows across ~30 partitions — manageable with per-partition indexes.

**Recovery query with partition pruning:**

```sql
-- Scans at most two daily partitions due to created_at filter
SELECT event_id, channel, priority FROM notification_events
WHERE state = 'enqueued'
  AND created_at > NOW() - INTERVAL '2 hours'
  AND claimed_at IS NULL;
```

### 2.3 Recovery Protocol — Corrected for Duplicate-Delivery Race

**The problem with a naive design:** If a recovery job queries for events with `state=enqueued` and no delivery log entry, then re-enqueues them, there is a race: a worker dequeues an event and is mid-processing when the recovery job fires. The recovery job finds no delivery log entry yet, classifies the event as undelivered, and re-enqueues it. The original worker delivers it; the re-enqueued copy delivers it again. This is not idempotent.

**The fix: explicit claim step.**

Workers claim events before processing using an atomic conditional update. The recovery job only re-enqueues events that are genuinely unclaimed or stuck.

**Worker claim protocol:**

```python
def process_notification(event_id: str, worker_id: str):
    # Atomic claim — only succeeds if state is still 'enqueued'
    rows_updated = db.execute("""
        UPDATE notification_events
        SET state = 'claimed',
            worker_id = %s,
            claimed_at = NOW()
        WHERE event_id = %s
          AND state = 'enqueued'
    """, (worker_id, event_id))

    if rows_updated == 0:
        return  # another worker claimed it; discard silently

    try:
        deliver(event_id)
        db.execute("""
            UPDATE notification_events SET state = 'delivered'
            WHERE event_id = %s
        """, (event_id,))
        db.execute("""
            INSERT INTO delivery_log (event_id, channel, provider_response)
            VALUES (...)
        """)
    except Exception as e:
        db.execute("""
            UPDATE notification_events
            SET state = 'failed', failure_reason = %s
            WHERE event_id = %s
        """, (str(e), event_id))
        raise  # re-queue for retry
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

**Why this is correct:** The claim UPDATE is atomic and conditional on `state = 'enqueued'`. If two workers race, exactly one succeeds. The stuck-worker path only resets `claimed_at` older than 10 minutes — a live worker will have completed or failed within that window. The recovery job's own UPDATE is conditional, so it cannot race with a live worker's claim.

**Tradeoff:** One additional PostgreSQL write per notification (the claim UPDATE) at ~500/sec peak. PostgreSQL handles tens of thousands of writes/sec on modest hardware; this does not move the needle.

### 2.4 Queue Persistence

```
redis.conf (notification queue Redis instance):
  appendonly yes
  appendfsync everysec
  no-appendfsync-on-rewrite no
  auto-aof-rewrite-percentage 100
  auto-aof-rewrite-min-size 64mb
```

On crash, we lose at most ~1 second of enqueued notifications (~500 at peak). The PostgreSQL event log with the corrected recovery protocol handles these safely. The claim step ensures recovery can run at any time without duplicate delivery.

**Why not Redis Cluster:** Cluster with replicas provides availability, not durability. AOF on a single instance with a PostgreSQL backstop gives durability with predictable latency at our scale. Cluster becomes relevant when we exceed single-instance throughput limits; at 500/sec peak we do not.

### 2.5 Priority Enforcement

Workers within a channel pool are fungible. Priority is a property of the queue, not the worker. Each worker executes the same dequeue loop:

```python
def dequeue_loop(redis_client, channel):
    queues = [
        f"notify:{channel}:p0",
        f"notify:{channel}:p1",
        f"notify:{channel}:p2",
        f"notify:{channel}:p3",
    ]
    while True:
        notification = None
        for queue in queues:  # strict priority order
            result = redis_client.zpopmin(queue, count=1)
            if result:
                notification = result[0]
                break
        if notification:
            process(notification)
        else:
            time.sleep(0.01)  # 10ms backoff when all queues empty
```

P0 notifications are always processed before P1, regardless of which worker picks them up. No worker sits idle waiting for P0 events that rarely arrive.

**What we give up:** If all workers are busy on P1 and a P0 arrives, it waits ~50ms. Acceptable for push and email. Not acceptable for SMS, which is the designated channel for P0 security events (auth codes, account compromise alerts).

**SMS P0 exception:** SMS gets one dedicated P0 worker processing only `notify:sms:p0`, plus two general workers for P1–P3. The "negligible volume" characterization is correct for P1–P3 SMS but wrong as a reason to deprioritize P0 SMS delivery latency. A dedicated worker costs nothing at this scale and removes the contradiction.

**Worker pool sizing — 20% opt-out design ceiling:**

| Channel | Peak Volume/sec | Time/notification | Workers needed | Provisioned |
|---------|----------------|-------------------|----------------|-------------|
| Push | ~325 | 50ms | 17 | 30 |
| Email | ~35 | 100ms | 4 | 8 |
| SMS | <1 | 200ms | 1 | 3 (1 dedicated P0) |

Push is over-provisioned (30 vs. 17) for retry burst headroom and APNs/FCM latency spikes. Email is recalculated against the corrected 1.0M/day figure. E4 owns a post-Phase-1 calibration task: measure actual processing times under load and resize. These are starting points.

### 2.6 WebSocket Fan-Out

**The routing problem:** WebSocket connections are stateful. A naive stream consumer group distributes messages across all consumers — servers may dequeue messages for users connected elsewhere, filter them, and discard them silently.

**The gap detection problem:** "No registry entry" conflates two states: (a) user is genuinely offline, and (b) user is mid-handshake and the registry entry hasn