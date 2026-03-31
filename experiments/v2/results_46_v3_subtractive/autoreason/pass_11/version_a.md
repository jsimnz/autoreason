# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 14.4M routed notification events per day across push, email, in-app, and SMS channels. The revision addresses eleven specific structural weaknesses in the prior version: the recovery job is now fully specified including its own failure modes; the routing table failure mode is analyzed with a recovery path; TCPA suppression latency is characterized and bounded by a separate write path; channel distribution math is corrected to treat multi-channel users correctly; the idempotency key limitation is stated honestly with compensating controls; the WebSocket delivery path is designed; team ownership conflicts are resolved; and archival and partition pre-creation failure modes are addressed.

**Core architectural choices and their honest tradeoffs:**

- **Per-channel worker pools** with priority enforced via sorted set score. SMS P0 gets a dedicated worker with a fast-path ingestion route that bypasses the aggregation window check but retains all suppression checks. The suppression check for P0 SMS reads from a write-path-updated cache (TTL=30 seconds, not 5 minutes) that is written synchronously by the preference API on opt-out. This is the TCPA compliance mechanism.
- **At-least-once delivery.** Provider-side idempotency keys deduplicate network-level retries within a single attempt only. They provide zero protection against crash-recovery duplicates, because each recovery attempt uses a new key. The 0.01% duplicate target is enforced by the staleness threshold and is an operational target, not a guarantee. This is stated explicitly.
- **Redis AOF with `fsync=everysec`** means up to 1 second of queue state can be lost on crash. PostgreSQL is the recovery source. The recovery job is fully specified, including its own failure modes and scheduling.
- **Routing table as a correctness mechanism** with an acknowledged failure mode: if the routing table write fails, the event is unroutable. This is addressed by writing both tables in a single transaction with a compensating recovery query.
- **WebSocket delivery path** is designed with consumer group configuration, crash handling, and online/offline determination specified.

**What we are deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring.

**What we are explicitly accepting as limitations:** Duplicate delivery is possible in crash-recovery scenarios. The mechanism that bounds it (staleness threshold) is specified. In-app delivery to offline clients is best-effort with client-side sync on reconnect, with the reconnect protocol specified.

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

**Opt-out sensitivity (applied to raw events before channel expansion):**

| Opt-Out Rate | Routed Events/Day | Peak (3×) |
|-------------|-------------------|-----------|
| 20% | ~14.4M | ~500/sec |
| 40% | ~10.8M | ~375/sec |
| 60% | ~7.2M | ~250/sec |

We design for the 20% opt-out scenario.

### 1.2 Channel Distribution — Corrected for Multi-Channel Users

**The prior version's error:** Applying channel percentages to routed events as if they were mutually exclusive. A user with push and email enabled generates one push event and one email event from a single notification. Channel distribution is not a partition of users; it is a set of independent opt-in rates, and a single notification generates one delivery event per enabled channel per user.

**Corrected model:**

We model independent channel opt-in rates among the users who have not globally opted out (the 80% who remain after the 20% global opt-out).

| Channel | Opt-In Rate (of non-opted-out users) | Routed Events/Day | Peak Events/sec |
|---------|--------------------------------------|-------------------|-----------------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 100% (all active sessions) | ~14.4M | ~500 |
| Email | 20% | ~2.9M routed events | ~100 pre-batch |
| SMS | <0.01% | ~1,500 | negligible |

**Total routed events/day: ~27.2M** (up from 14.4M in the prior version, which incorrectly treated channels as mutually exclusive). The 14.4M figure was the count of recipient-notification events before channel expansion; this is a distinct number from routed delivery events and must not be conflated with it.

**In-app clarification:** In-app events are generated for all non-opted-out users regardless of other channel preferences, because in-app is the baseline experience. Users who have also enabled push receive both. This is intentional product behavior, not a modeling artifact.

**Revised email delivered volume:**

At 20% email opt-in, opted-in DAU = 600K. Email-triggering events per opted-in user per day: 2.9M ÷ 600K ≈ 4.8 events/user/day.

```
λ = 4.8 events/user/day
μ = λ/48 = 0.1 events per 30-minute window
emails_per_user_per_day = 48 × (1 - e^(-0.1)) ≈ 48 × 0.095 ≈ 4.57
reduction_factor = 4.8 / 4.57 ≈ 1.05×
delivered_emails/day ≈ 600K × 4.57 ≈ 2.74M
delivered_email_peak ≈ 2.74M ÷ 86,400 × 3 ≈ 95/sec peak
```

The low reduction factor (1.05×) at this λ reflects that 30-minute windows rarely accumulate multiple events per user when events are spread across the day. The batching window's primary value at this scale is latency control, not volume reduction.

**The batching window is a configurable product parameter.** The 30-minute value used above is the current default. When product changes this parameter, worker sizing and queue depth thresholds must be recalculated. The mechanism for this is: the batching window value is stored in a configuration service (not hardcoded); a configuration-change event triggers a recalculation job that outputs revised worker count recommendations and updated alert thresholds. E1 owns this job. This is not automatic — it produces a recommendation that requires human review — but it ensures the dependency is not invisible.

**Worker sizing uses delivered volume. Queue depth monitoring uses routed event volume. These are different numbers and must not be conflated.**

### 1.3 SMS Cost Ceiling

At $0.0075/message, 1,500/day = ~$340/month. This is negligible relative to infrastructure costs and does not constrain design choices.

### 1.4 Team Allocation — Resolved Ownership Conflicts

The prior version had two ownership conflicts: E1 and E4 both listed recovery job threshold calibration; and the feedback processor (E3) depended on a token invalidity stream (E2) whose consumer group configuration appeared to belong to E4. These are resolved below.

| Engineer | Primary Responsibility | Explicit Ownership |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, priority scoring, batching logic, partition pre-creation job | Recovery job scheduling, staleness threshold definition, recalculation job for batching window changes |
| E2 | Channel integrations (APNs, FCM, SES, Twilio), token lifecycle | Token invalidity signal detection and structured event publication to `token.invalidated` stream |
| E3 | Preference management, user-facing API, suppression, TCPA compliance | Feedback processor (consumes `token.invalidated` stream); suppression cache write path; preference API opt-out synchronous cache write |
| E4 | Reliability, monitoring, failure handling, DevOps, WebSocket infrastructure | Recovery job runbook and operational response; partition pre-creation job monitoring and alerting; archival job; worker pool autoscaling |

**Resolved conflicts:**
- Recovery job threshold calibration: owned by E1 (design). E4 owns the runbook and operational response when thresholds are breached. These are distinct responsibilities.
- Token invalidity stream consumer group: E2 publishes; E3 configures and operates the consumer group. E4 monitors consumer group lag as an operational metric. No three-engineer dependency chain for the compliance path: the path is E2 (publish) → E3 (consume and write suppression). E4 observes but does not sit in the path.

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
        by preference API on opt-out; see Section 2.6)
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

**Routing table as correctness mechanism — failure mode acknowledged.**

The prior version presented the routing table as a pure improvement. It is a correctness improvement with a new failure mode: if the ingestion transaction fails, the event is not written to either table, and the caller receives a 503 and retries. This is the intended behavior. There is no scenario where `notification_events` is written without `event_partition_routing`, because they are in the same transaction. The failure mode "event written, routing entry missing" cannot occur under this design. The `claim_event` function's `None` return on missing routing entry is therefore a defensive check against data corruption, not a normal code path.

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

**Partition pre-creation job failure — analyzed.**

The partition pre-creation job runs daily and creates partitions 7 days ahead. If this job fails silently, inserts to `notification_events` will fail when the next day's partition does not exist. At 14.4M+ events/day, this is a total outage scenario for new events.

Mitigations:
1. **Alerting:** E4 owns a monitoring check that verifies partitions exist for the next 3 days. Alert fires if fewer than 3 future partitions are present. This gives 3 days of warning before an outage, not 7 days of silent drift followed by surprise.
2. **Fallback partition:** A catch-all partition covering a 90-day future range exists as a permanent safety net. It does not have the performance characteristics of daily partitions (no partial indexes, no targeted archival), but it prevents total outage. On detection of a missing daily partition, the catch-all absorbs traffic while the pre-creation job is repaired. E4 owns the runbook for migrating catch-all rows into the correct daily partition after repair.
3. **Job idempotency:** The pre-creation job checks for existing partitions before creating them. Re-running it is safe.

### 2.4 Recovery Job — Fully Specified

**The prior version's gap:** The recovery job was described as the designed closure for the crash window but its own failure modes were not analyzed.

**What the recovery job does:** It finds events in state `enqueued` or `claimed` whose `claimed_at` is older than the staleness threshold, and re-enqueues them to Redis.

**Staleness threshold definition:**

The staleness threshold must be longer than the maximum expected processing time for a single event, to avoid re-enqueuing events that are being actively processed. Processing time components:
- Claim operation: <50ms (database write)
- Channel API call: <5 seconds (P0 timeout), <30 seconds (P1/P2/P3 timeout)
- State update: <50ms

Conservative maximum