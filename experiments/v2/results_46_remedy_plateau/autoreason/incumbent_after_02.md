# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–120M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Key design decisions made explicitly:**
- Peak multiplier is 10×, not 3×, because notification spikes are correlated and event-driven
- Infrastructure is provisioned from a load-tested model before launch, not after collecting production data
- SMS caps are enforced with atomic Lua scripts to eliminate race conditions in distributed routing
- In-app notifications bypass the queue but share a unified delivery event log and identical retry semantics
- "Revisit at 50M MAU" deferrals are replaced with explicit triggers, owners, and lead times
- E4's scope is reduced to two delivery channels plus deployment pipelines; reliability monitoring moves to E1

We ship a working system by end of month 2, iterate through month 5, and harden in month 6. No engineer owns more than two channel integrations. Every integration has a documented runbook by end of month 1.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Fabricating a precise number and designing to it is a false precision trap. Three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change:

| Scenario | Notifs/DAU/day | DAU (30% of MAU) | Total/day | Peak/sec |
|----------|---------------|-------------------|-----------|----------|
| Conservative | 5 | 3M | 15M | ~1,500 |
| **Base case** | **17** | **3M** | **51M** | **~5,000** |
| High | 40 | 3M | 120M | ~11,700 |

#### 1.1.1 Peak Multiplier: 10×, Not 3×

A 3× multiplier is borrowed from general web traffic patterns. It is wrong for notification systems.

Notification spikes are **correlated and event-driven**, not smoothly distributed. A single viral post generates a burst of like/comment/share notifications to the original poster and all participants simultaneously. A celebrity with 2M followers joins the platform and triggers follow-suggestion notifications in bulk. A breaking news event drives millions of simultaneous app opens, generating concurrent comment activity.

The 10× multiplier is derived as follows:

- Base rate: 51M/day ÷ 86,400 sec ≈ 590/sec average
- Notification activity concentrates in a 3-hour primetime window (~50% of daily volume in 11% of the day): 25.5M ÷ 10,800 sec ≈ 2,360/sec sustained during primetime
- A correlated spike (viral event) drives 4–5× primetime rate for 5–10 minutes: ~10,000–12,000/sec

We provision for **5,000/sec sustained** (8.5× average) and **12,000/sec burst** (20× average). Queue depth is the shock absorber; workers drain the backlog after the spike rather than requiring capacity to process it in real time. This is the correct tradeoff: over-provisioning workers is expensive and wasteful 99% of the time; over-provisioning queue depth costs almost nothing.

**Infrastructure implication:** Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge (benchmarks show >100K ops/sec for simple sorted set operations). Worker pool sizing targets 5,000/sec throughput; bursts above that queue and drain within minutes.

#### 1.1.2 Infrastructure Provisioning: Load Test Before Launch, Tune After

The previous version said "do not finalize Redis cluster sizing until two weeks of production data" while committing to shipping in month 2. These conflict: launching in month 2 requires infrastructure provisioned before month 2, which is before production data exists.

**Resolution:** Provision infrastructure from the model above before launch. Validate with synthetic load testing before launch. Tune with production data after launch.

- **Before month 1 ends:** Provision ElastiCache r6g.xlarge, RDS db.r6g.2xlarge, and 40 delivery workers across priority tiers
- **End of month 1:** Run a synthetic load test at 2× base case (3,500/sec) against staging. This validates sizing without requiring production data
- **Weeks 1–2 post-launch:** Instrument actual event rates. If sustained rates exceed 3,000/sec, trigger the scale-up runbook (§7) before end of month 2
- **Scale-up path without architectural change:** ElastiCache supports vertical scaling with <60-second failover; worker count scales horizontally. Neither requires code changes

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications (likes, follows) would cost: 2% of 51M/day = 1M SMS/day × $0.0079 = $2.9M/year. That is not a notification system design problem — it is a business model problem. We treat SMS as a privileged channel reserved for authentication and security.

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---------|-------------|------------|-----------|------------|-------|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

**Hard SMS cap — atomically enforced:**

The naive approach has a race condition: two simultaneous routing decisions for the same user both read a count of 2 and both decide to send, exceeding the per-user cap of 3. We eliminate this with a Redis Lua script:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded
-- Key expires at midnight UTC to reset daily counts

local key = KEYS[1]       -- "sms_cap:{user_id}:{date}"
local cap = tonumber(ARGV[1])  -- 3 for non-auth SMS
local ttl = tonumber(ARGV[2])  -- seconds until midnight UTC

local current = redis.call('GET', key)
if current == false then
    redis.call('SET', key, 1, 'EX', ttl)
    return 1
elseif tonumber(current) < cap then
    redis.call('INCR', key)
    return 1
else
    return 0
end
```

This executes atomically on a single Redis node. Two simultaneous routing decisions serialize on this script. Auth SMS (OTP) bypasses this check entirely, using a separate key with a cap of 10/day to prevent OTP abuse.

**Global daily cap** of 200K non-auth SMS is enforced via a separate atomic counter at the router. When the global cap is reached, non-auth SMS is **dropped, not queued to the next day** — carrying over creates unbounded accumulation. Auth SMS is always exempt.

### 1.3 Team Allocation

Assigning all four channel integrations to one engineer creates a single point of failure on the critical path. The previous version grouped email, SMS, reliability, and DevOps with E4 because they're "webhook-heavy." That is an organizational rationalization, not a workload analysis. Email alone involves webhook processing, bounce handling, suppression list sync, IP warming, and deliverability monitoring. Adding reliability engineering makes E4's scope undeliverable.

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary / Backup |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, reliability/monitoring infrastructure | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user-facing API, suppression logic, in-app notifications, WebSocket layer | Backup: E4 |
| E4 | Email (SendGrid) + SMS (Twilio), webhook processing, deployment pipelines | Backup: E2 |

**Rationale for changes:**
- Reliability and monitoring moves to E1, who owns the core pipeline. You should monitor the system you built.
- E3 absorbs in-app and WebSocket — both are user-facing read/write paths, adjacent to preference management E3 already owns.
- E4 retains email and SMS but loses reliability/monitoring. Deployment pipelines stay with E4 because both channels require coordinated deployment (IP warming schedules, Twilio webhook registration).

**Capacity check:** Email integration (weeks 1–4) and SMS integration (weeks 3–6) overlap. The delivery schedule in §6 staggers these: email webhooks are the month-1 priority; SMS STOP handling and carrier error processing are month-2 work. E2 is documented on the email webhook schema by end of month 1.

**Bus factor mitigation:** Each engineer produces a runbook for their integration by end of month 1. Month 2 includes explicit cross-training sessions (2 hours/week, scheduled). We accept month-1 knowledge silos and address them on a fixed schedule.

### 1.4 Scaling Triggers

"Revisit at 50M MAU" is not an action item. It has no owner, no tracking mechanism, and no lead time estimate. If growth is faster than expected, multiple deferred decisions become urgent simultaneously. We replace all deferrals with explicit triggers:

| Decision | Trigger | Owner | Lead Time | Action |
|----------|---------|-------|-----------|--------|
| Per-channel queues | Sustained queue depth >100K during non-spike periods, OR per-channel rate limiting is a product requirement | E1 | 6 weeks | Migrate to per-channel Redis sorted sets; routing logic change only, no data migration |
| SendGrid → SES | Monthly email cost >$5K AND bounce rate <1% AND spam rate <0.05% for 60 days | E4 | 8 weeks | SES migration with parallel-send validation period |
| Self-operated infrastructure | Team >12 engineers AND managed service costs >$30K/month AND a specific operational limitation is documented | E1 + EM | 12 weeks | Evaluate specific service; do not migrate wholesale |
| Direct push → managed push | Advanced segmentation on product roadmap AND direct integration maintenance >0.5 engineer/quarter | E2 | 4 weeks | Evaluate OneSignal/Braze at actual MAU pricing |

**Tracking:** A 30-minute monthly metrics review (E1 runs it) checks each trigger. MAU is tracked via the existing analytics pipeline.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  ├── Preference check (Redis cache, write-through)
  ├── Suppression check
  ├── Deduplication check
  ├── Priority assignment
  ├── SMS atomic cap check (Lua script)
  └── Channel selection
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[Priority Queue]                              [In-App Write Path]
  (Redis sorted set — Lua atomic ops)          (PostgreSQL, partitioned)
     │                                              │
     ├── P0 Workers (10)                            ├── Write to DB (with retry)
     ├── P1 Workers (20)                            ├── Publish to Redis Pub/Sub
     └── P2/P3 Workers (10)                         └── Client polls on reconnect
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log + Feedback Processor]
   (PostgreSQL + S3 archive)
          │
          └── Unified delivery event log
              (all channels, all paths)
```

### 2.2 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues mean 4 queues to monitor, 4 dead-letter queues, and priority inversions between channels. A Redis sorted set with priority-encoded scores handles 50M items comfortably at our scale. The explicit trigger for migrating to per-channel queues is in §1.4.

**Synchronous preference check at routing time, not delivery time.**
User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means consuming queue capacity for notifications we then discard. At 51M/day with a 20% preference-suppression rate, that's ~10M wasted dequeues per day.

**In-app notifications bypass the queue.**
In-app notifications are writes to a partitioned PostgreSQL table. They're read-heavy, need random access by user, and benefit from immediate consistency. Routing 10M/day in-app writes through the same queue as push would add latency for no delivery benefit — if the DB write fails, we retry at the application layer. The tradeoff: two delivery code paths. We accept this and address it by unifying observability and retry semantics (§2.3).

**Managed services throughout.**
ElastiCache, RDS, FCM, APNs, SendGrid, Twilio. A team of 4 does not operate Kafka or Cassandra in month 1. We accept the cost premium for operational simplicity. Explicit triggers for when to re-evaluate are in §1.4.

### 2.3 Unified Delivery Guarantee Model

Two delivery paths with inconsistent semantics and separate monitoring surfaces create a debugging nightmare. We retain the two paths (queue-based and direct-write) but make their guarantees explicit and unify observability.

| Property | Queue-based (Push/Email/SMS) | Direct-write (In-app) |
|----------|-----------------------------|-----------------------|
| Retry on failure | Up to 3 attempts, exponential backoff, then DLQ | Up to 3 attempts at application layer, then `failed_notifications` table |
| Dead-letter handling | Redis DLQ, reviewed every 6 hours | PostgreSQL `failed_notifications`, same review cadence |
| Observability | Unified delivery event log | Same unified delivery event log |
| Idempotency | Notification ID checked before processing | Notification ID as upsert key; duplicate writes are no-ops |
| Debugging | Check delivery event log by notification_id | Same — notification_id links both paths |

**Unified delivery event log:** Every notification, regardless of path, writes a row to `delivery_events` at each state transition. This is a write-ahead log pattern: the event is written before the delivery attempt, so a crash mid-delivery leaves a record.

```sql
CREATE TABLE delivery_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL,
    channel         VARCHAR(32) NOT NULL,  -- 'push', 'email', 'sms', 'in_app'
    event_type      VARCHAR(32) NOT NULL,  -- 'created', 'enqueued', 'delivered', 
                                           -- 'failed', 'dead_lettered'
    provider        VARCHAR(32),           -- 'fcm', 'apns', 'sendgrid', 'twilio', null
    provider_msg_id VARCHAR(256),          -- provider's message ID for correlation
    error_code      VARCHAR(64),
    error_message   TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_delivery_events_notification
    ON delivery_events (notification_id, created_at DESC);
```

---

##