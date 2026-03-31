# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 14.4M–18M notifications/day across push, email, in-app, and SMS channels.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision. Workers are fungible within a channel; priority is a property of the queue position, not the worker. **Exception:** SMS P0 gets a dedicated worker because the general dequeue loop's ~5ms average detection latency is unacceptable for security-critical events (auth codes, account compromise alerts). This exception is not a contradiction — it is the correct application of the principle: use dedicated workers when latency requirements cannot be met by polling intervals, and only then.
- **Claim-based delivery with idempotency keys**, not a claim-then-deliver sequence. The fundamental limit is that we cannot atomically claim a database row and deliver a push notification — these are two different systems. We accept at-most-once delivery as the default and implement provider-side idempotency keys to bound the duplicate delivery window for at-least-once retries.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets, with a PostgreSQL event log as recovery backstop. AOF rewrites are scheduled during off-peak hours to avoid ingestion latency spikes.
- **Per-channel queues** isolating channel failures. APNs degradation affects push workers only; email workers continue unaffected.
- **WebSocket connection registry** with explicit three-state tracking (connecting / connected / offline) and gap detection via sequence numbers.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring. These require a functioning baseline. We build the baseline.

**What we're explicitly accepting as limitations:** Duplicate delivery is possible in crash scenarios. We bound it, log it, and treat it as a known operational condition rather than claiming to have eliminated it.

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

**Email volume and batching — corrected derivation:**

The previous version computed batching reduction using total unique recipients as the denominator. This is wrong. The relevant denominator is email-opted-in users, because only they receive email notifications.

Working from first principles:
- Email is 9% of 14.4M = ~1.3M email-eligible events/day
- Email opt-in rate: we do not know this at design time. We will measure it during Phase 1. For planning purposes, we model three scenarios:

| Email Opt-In Rate | Opted-In Users (of 3M DAU) | Events/User/Day | λ (Poisson) | Batching Reduction | Delivered/Day |
|-------------------|---------------------------|-----------------|-------------|-------------------|---------------|
| 10% (conservative) | 300K | 4.3 | 4.3 | ~2.5× | ~520K |
| 20% (base case) | 600K | 2.2 | 2.2 | ~1.8× | ~720K |
| 40% (high opt-in) | 1.2M | 1.1 | 1.1 | ~1.2× | ~1.1M |

**The previous 1.3× estimate was derived with an incorrect denominator and is withdrawn.** The batching reduction is meaningfully sensitive to opt-in rate. We use the 20% opt-in / 1.8× reduction / 720K delivered/day figure for worker sizing, and we recalibrate after Phase 1 measurement.

**Batching reduction derivation at λ=2.2 (base case):**
- Events/user/15-minute window: 2.2 ÷ 96 = 0.023
- P(>1 event in a window) = 1 - P(0) - P(1) = 1 - e^(-0.023) - 0.023·e^(-0.023) ≈ 2.6% of windows
- But we batch across the full day's events, not just within windows. A user receiving 2.2 events/day receives on average 1 digest email if all events fall within one window, or up to 2.2 emails if each arrives in a different window. The effective reduction is 2.2/1.8 ≈ 1.2 emails/user/day.

**Delivered email peak rate:** 720K/day ÷ 86,400 × 3 (peak factor) ≈ **25/sec peak**. Worker sizing is computed against this figure in §3.2.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic; PostgreSQL partitioning strategy |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group with explicit ACK and a configured pending entry timeout. Neither engineer writes directly into the other's domain. The reliability contract for this stream is specified in §5.3.

**Timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §6 for explicit contingencies.

---

## 2. System Architecture

### 2.1 Priority Classification

The router assigns priority at ingestion time based on event type. Priority must be defined explicitly — if engineers disagree about where an event type falls, the priority system provides no actual latency differentiation.

| Priority | Label | Event Types | Target Delivery Latency |
|----------|-------|-------------|------------------------|
| P0 | Critical | Auth codes, account compromise alerts, payment failures, security events | <2 seconds |
| P1 | High | Direct messages, mentions, replies to your content | <30 seconds |
| P2 | Normal | Likes on your content, new followers, comments on your posts | <5 minutes |
| P3 | Bulk | Digest summaries, weekly recaps, promotional notifications | <1 hour |

**Classification is exhaustive.** Every event type in the system is assigned a priority at definition time, not at routing time. The router performs a lookup, not a judgment call. New event types require a pull request that includes a priority assignment — unclassified events are rejected with a logged error, not silently defaulted.

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

**The partitioning index problem:**

In PostgreSQL, a partial index defined on a partitioned parent table is *not* automatically propagated to child partitions in versions prior to 11, and even in versions 11+, behavior varies by index type. We do not rely on parent-level partial indexes. Instead, E4's partition creation job creates the appropriate indexes on each child partition at creation time, before data is written to that partition.

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
-- Run by E4's maintenance job for each new partition
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

**Why this matters:** The recovery query scans for `state = 'enqueued'` events within a 2-hour window. Without the partial index on the child partition, this is a full partition scan at exactly the moment we need it most — after a crash under load, when the partition contains millions of rows. With the index, it's an index scan of a small fraction of rows.

**Retention:** Partitions older than 30 days are archived to S3 (Parquet) and dropped. The active table never exceeds ~30 days of data.

### 2.4 Delivery Semantics — What We Can and Cannot Guarantee

**The fundamental constraint:** Delivering a notification and recording that delivery are operations against two different systems (a push provider and PostgreSQL). There is no atomic transaction spanning both. This means:

- **At-most-once** (claim, deliver, then record): If the worker crashes after delivery but before recording, the notification was delivered but we have no record. Recovery re-enqueues it. It is not re-delivered because we cannot know it was delivered. **Result: possible lost delivery.**
- **At-least-once** (record attempt, deliver, record completion): If the worker crashes after delivery but before recording completion, recovery re-enqueues it. It is delivered again. **Result: possible duplicate delivery.**

We choose **at-least-once with idempotency keys**. Duplicate delivery is bounded and detectable; lost delivery for P0 events (security alerts) is worse. The idempotency key is passed to providers that support it (APNs `apns-collapse-id`, FCM `collapse_key`, SES `ClientRequestToken`) — the provider deduplicates on its end for the retry window it supports.

**What this means operationally:** Users may occasionally receive the same notification twice. This is logged, monitored, and surfaced in our duplicate rate metric. We target a duplicate rate below 0.01% of delivered notifications. We do not claim to have eliminated duplicates.

### 2.5 Worker Claim Protocol — Honest Design

The claim step serves two purposes: (1) preventing two workers from delivering the same notification concurrently, and (2) enabling the recovery job to detect stuck workers. It does not prevent duplicate delivery in crash scenarios — see §2.4.

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
        # Another worker claimed it; discard silently
        return

    try:
        # Pass idempotency_key to provider; provider deduplicates
        # within its supported window if this is a retry
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

**The crash window:** If the worker crashes after `deliver()` returns but before the `UPDATE state = 'delivered'` completes, the event stays in `claimed` state. After the stuck-worker threshold (see §2.