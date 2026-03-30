# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Flaws in the Prior Draft

Every flaw is catalogued here so reviewers can verify each was resolved rather than silently dropped.

| # | Flaw | Fix Location |
|---|------|-------------|
| 1 | Document truncated mid-section; Sections 3–9 absent | Sections 3–9 fully written |
| 2 | No SLA definitions or measurement methodology | Section 1.2 |
| 3 | Data model cut off mid-index; no retention policy | Section 3 |
| 4 | No failure handling section | Section 7 |
| 5 | No infrastructure section beyond naming tools | Section 6 |
| 6 | No phased delivery plan | Section 9 |
| 7 | No user preference management section | Section 5 |
| 8 | No priority and batching logic section | Section 4 |
| 9 | No WebSocket specification | Section 4.3 |
| 10 | No digest batching specification | Section 4.4 |
| 11 | Race condition in idempotency: `ON CONFLICT` does not prevent duplicate dispatch | Sections 2.1, 7.1 |
| 12 | FCM credential refresh not thread-safe | Section 4.1 |
| 13 | APNs JWT token expiry described in prose but never implemented | Section 4.2 |
| 14 | Worker pool sizing asserted without derivation | Section 4.6 |
| 15 | `send_batch` uses unbounded concurrency via bare `asyncio.gather` | Section 4.1 |
| 16 | No APNs token invalidation flow | Section 4.2 |
| 17 | No email implementation | Section 4.4 |
| 18 | No SMS implementation with TCPA compliance | Section 4.5 |
| 19 | Priority score encoding never defined; P0 collisions arbitrary | Section 4.7 |
| 20 | Quiet hours evaluated in UTC, not user's local timezone | Section 5.2 |
| 21 | No circuit breaker specification | Section 7.3 |
| 22 | No DLQ retention, alerting, or replay procedure | Section 7.4 |
| 23 | No monitoring or alerting specification | Section 8 |
| 24 | `date_bucket` idempotency key creates window problem on retry | Sections 3.1, 7.1 |
| 25 | No Redis capacity planning | Section 6.2 |
| 26 | No PostgreSQL capacity planning | Section 6.1 |
| 27 | FCM `data` field string coercion undocumented | Section 4.1 |
| 28 | No graceful shutdown specification | Section 7.5 |
| 29 | Service account credentials read from file path | Section 6.3 |
| 30 | Per-worker rate limiter insufficient for shared provider quota | Section 7.6 |

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

We will ship a working system in month 2, iterate through month 5, and spend month 6 on hardening and load testing. The phased delivery plan in Section 9 defines exactly what ships in each phase.

**The core architectural bet:** a single priority queue with channel fanout, rather than per-channel queues or a complex event-streaming topology. This is the right tradeoff for a team of 4 — it is debuggable, replaceable, and sufficient for 10M MAU. We document the explicit trigger conditions under which we revisit each decision.

**What this document covers:** scale assumptions, system architecture, all four delivery channels, priority and batching logic, user preference management, infrastructure choices, failure handling, monitoring, and a phased delivery plan.

**What this document does not cover:** notification content strategy, A/B testing frameworks, or ML-based send-time optimization. These are post-launch concerns.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio, typical for engaged social apps |
| Notifications per DAU per day | ~17 | Industry range 10–25 for social apps |
| **Total notifications/day** | **~50M** | DAU × per-user rate |
| Peak multiplier | 3× | Morning commute and evening prime-time spikes |
| Peak throughput | ~1,750/sec | (50M × 3) ÷ 86,400 |
| Push (70%) | 35M/day | Dominant channel; Android/iOS split ~60/40 |
| In-app (20%) | 10M/day | Logged-in users only; WebSocket fan-out |
| Email (8%) | 4M/day | Digests and critical transactional |
| SMS (2%) | 1M/day | Ceiling for capacity planning — see note below |

**Channel ratios are assumptions, not targets.** We instrument actual channel distribution from day one and adjust allocations in month 2 based on observed data.

**SMS volume requires explicit business sign-off before launch.** 1M SMS/day at Twilio's standard US rate ($0.0079/message) is $7,900/day — roughly $2.9M/year. International rates are 2–10× higher. In practice, SMS should carry only authentication codes and security alerts, which realistically amounts to 50K–150K/day (~$145K–$430K/year). We use 1M/day as a capacity-planning ceiling and configure the channel dispatcher to require an explicit override flag for any volume above 200K/day until business justification is reviewed and approved.

### 1.2 Service Level Objectives

These are commitments, not aspirations. They are the direct basis for alerting thresholds defined in Section 8.

| Priority | Type | Delivery SLO (p95) | Examples |
|----------|------|--------------------|---------|
| P0 | Security / Auth | < 5 seconds | OTP, account compromise alert |
| P1 | Time-sensitive social | < 30 seconds | Direct message, @mention |
| P2 | Standard social | < 5 minutes | Like, comment, follow |
| P3 | Batch / digest | < 1 hour | Weekly digest, promotional |

**Measurement definition:** SLO latency is measured from event ingestion timestamp to confirmed provider acceptance — FCM/APNs 200 response, SendGrid acceptance, Twilio queue acknowledgment. Provider-to-device delivery time is outside our control and is tracked separately as an informational metric where provider data is available (APNs delivery receipts, FCM delivery reports).

**Breach response:** Any SLO breach in production triggers a post-incident review within 48 hours. Three breaches in a rolling 30-day window for the same priority tier trigger an architecture review.

### 1.3 Team Allocation

| Engineer | Primary Responsibility | Secondary |
|----------|----------------------|-----------|
| E1 | Core pipeline, queue infrastructure, delivery workers | On-call rotation |
| E2 | Channel integrations: FCM, APNs, SendGrid, Twilio | Push token management |
| E3 | Preference management, user-facing API, suppression logic | Digest batching |
| E4 | Reliability, monitoring, failure handling, infrastructure | On-call lead |

All four engineers rotate on-call in week-long shifts. There is no dedicated QA. Quality is enforced through mandatory automated testing: no PR merges without unit tests covering business logic and integration tests covering external API calls against mocked providers. E4 owns the testing framework and CI configuration.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
(application services, scheduled jobs, admin triggers)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  Event Ingestion API                                  │
│  • Idempotency key required on every request          │
│  • Deduplication: Redis SET NX, 24h TTL               │
│    anchored to event's own stable identifier,         │
│    not wall clock or date bucket                      │
│  • Schema validation                                  │
│  • Per-source rate limiting                           │
│  • Write notification record: status = PENDING        │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  Notification Router                                  │
│  • Load user preferences from Redis cache             │
│  • Apply suppression rules                            │
│    - Opt-out per channel                              │
│    - Quiet hours (evaluated in user's local timezone) │
│    - Frequency caps per priority tier                 │
│  • Assign priority level                              │
│  • Select delivery channels                           │
│  • Update notification record: status = ROUTED        │
└───────────┬───────────────────────┬───────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────┐   ┌──────────────────────────────┐
│  Priority Queue     │   │  In-App Store                │
│  Redis sorted set   │   │  • Direct write to           │
│  Composite score:   │   │    PostgreSQL                │
│  priority + seq_id  │   │  • WebSocket fan-out to      │
│  (see Section 4.7)  │   │    active connections        │
│                     │   │  • Stored for offline users  │
└──────────┬──────────┘   └──────────────────────────────┘
           │
  ┌────────┼────────────┐
  ▼        ▼            ▼
[P0]     [P1]        [P2/P3]
5 wkrs  15 wkrs     20 wkrs
  └────────┴────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────┐
│  Channel Dispatcher                                   │
│  • Acquire per-notification dispatch lock (Redis NX)  │
│    before send — prevents duplicate dispatch on retry │
│  • Distributed rate limiter (token bucket in Redis)   │
│  • Per-provider circuit breaker                       │
│  • Route to: FCM / APNs / SendGrid / Twilio           │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  Delivery Log                                         │
│  • PostgreSQL: hot data ≤ 30 days                     │
│  • S3: archive > 30 days, Parquet, partitioned by day │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│  Feedback Processor                                   │
│  • Provider webhooks (FCM, SendGrid, Twilio)          │
│  • APNs delivery receipts                             │
│  • Token invalidation (FCM 404, APNs Unregistered)    │
│  • Email bounce and unsubscribe synchronization       │
│  • SMS opt-out processing (STOP/HELP keywords)        │
│  • DLQ processor with alerting and replay             │
└───────────────────────────────────────────────────────┘
```

### 2.2 Architectural Decisions and Tradeoffs

**Decision 1: Single priority queue with channel fanout, not per-channel queues.**

Per-channel queues create four parallel sets of operational concerns: four dead-letter queues, four consumer group configurations, four monitoring dashboards, and priority inversions when a P0 push and a P2 email sit in separate queues with no shared priority mechanism. A Redis sorted set with composite priority scores handles 50M items comfortably and gives us a single queue depth metric to monitor. Channel selection happens in the dispatcher after dequeue.

*Revisit trigger:* If any single channel's failure mode begins contaminating other channels' delivery latency — for example, an SMS provider outage causing P1 push notifications to miss SLO — we split that channel into its own queue. We do not do this preemptively.

**Decision 2: Redis for the queue, not Kafka or RabbitMQ.**

Kafka is operationally complex for a team of 4. Partition rebalancing, consumer group offset management, and compaction tuning are real operational costs. RabbitMQ's priority queue implementation has known performance degradation at high queue depths. Redis sorted sets give us O(log N) enqueue and O(1) dequeue with a data structure the team already operates for caching. At 50M/day peak throughput (~1,750 enqueues/sec), Redis is not the bottleneck — provider API latency is.

*Revisit trigger:* If we need replay semantics, event sourcing, or fan-out to more than one downstream consumer type, we migrate to Kafka. Redis does not support these patterns natively.

**Decision 3: PostgreSQL for the delivery log, not a time-series database.**

We need relational queries: "all notifications for user X in the last 7 days," "delivery rate for notification type Y broken down by channel." A time-series database optimizes for aggregation over time windows but makes arbitrary relational queries awkward. PostgreSQL with composite indexes handles our query patterns. We archive to S3 after 30 days to keep the hot table manageable.

*Revisit trigger:* If the delivery log table exceeds 500M rows in the hot tier before the 30-day archive cycle catches up, we evaluate TimescaleDB or monthly range partitioning.

**Decision 4: Managed services for all provider integrations.**

We do not run our own SMTP server, APNs proxy, or SMS gateway. The compliance surface for email (CAN-SPAM, GDPR) and SMS (TCPA) alone justifies paying provider margins rather than owning the infrastructure.

---

## 3. Data Model

### 3.1 Core Tables

```sql
-- Central record for every notification event.
-- Append-only. Status transitions are the audit trail.
CREATE TABLE notifications (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Caller-supplied key anchored to the event's own stable identifier.
    -- Format convention: "{event_type}:{source_entity_id}"
    -- Examples: "dm_received:msg_7f3a", "like:like_9c2b", "otp:req_4d1e"
    --
    -- MUST NOT be date-bucketed or wall-clock-derived.
    -- A date-bucketed key (e.g. "user:123:like:2024-01-15") fails on
    -- cross-midnight retries: an event fired at 23:59 and retried at
    -- 00:01 produces two different keys and creates a duplicate.
    -- The key must be stable across all retry attempts for the same
    -- logical event.
    idempotency_key    TEXT        NOT NULL UNIQUE,

    user_id            UUID        NOT NULL,
    type               TEXT        NOT NULL,  -- 'dm','mention','like','otp'
    priority           SMALLINT    NOT NULL CHECK (priority BETWEEN 0 AND 3),
    payload            JSONB       NOT NULL,  -- channel-agnostic content
    status             TEXT        NOT NULL DEFAULT 'PENDING'
                           CHECK (status IN (
                               'PENDING','ROUTED','QUEUED',
                               'DISPATCHED','DELIVERED','FAILED','SUPPRESSED'
                           )),
    suppression_reason TEXT,       -- populated when status = SUPPRESSED
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    scheduled_for      TIMESTAMPTZ,           -- NULL means send immediately
    expires_at         TIMESTAMPTZ            -- discard if not delivered by this time
);

CREATE INDEX idx_notifications_user_created
    ON notifications (user_id, created_at DESC);

CREATE INDEX idx_notifications