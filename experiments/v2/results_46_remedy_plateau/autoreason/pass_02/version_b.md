# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–120M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Changes from the previous version:** This revision addresses twelve specific criticisms: the infrastructure provisioning contradiction, the unjustified 3× peak multiplier, the SMS cap race condition, inconsistent delivery guarantees for in-app notifications, the WebSocket fallback gap, E4's unrealistic scope, the missing `registered_at` column in APNs token handling, the digest termination edge case, the partition pre-creation failure mode, the inflated OneSignal cost estimate, digest double-send risk, and the untracked "revisit at 50M MAU" deferrals. Each section notes where a change was made and why.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Here are three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change:

| Scenario | Notifs/DAU/day | DAU (30% of MAU) | Total/day | Peak/sec (see §1.1.1) |
|----------|---------------|-------------------|-----------|----------------------|
| Conservative | 5 | 3M | 15M | ~1,500 |
| **Base case** | **17** | **3M** | **51M** | **~5,000** |
| High | 40 | 3M | 120M | ~11,700 |

#### 1.1.1 Peak Multiplier — Revised from 3× to 10×

**[Criticism addressed: #2 — The base case multiplier was unjustified.]**

The previous version used a 3× peak multiplier without justification, apparently borrowed from general web traffic patterns. That is wrong for notification systems.

Notification spikes are **correlated and event-driven**, not smoothly distributed. A single viral post generates a burst of like/comment/share notifications to the original poster and all participants simultaneously. A celebrity account with 2M followers joins the platform and triggers follow-suggestion notifications in bulk. A breaking news event drives millions of users to open the app at the same time, generating simultaneous read-receipts and comment activity.

We use a **10× sustained multiplier for sizing**. This is derived as follows:

- Base rate: 51M/day ÷ 86,400 sec = ~590/sec average
- Notification activity concentrates in a 3-hour primetime window (call it 50% of daily volume in 11% of the day): 25.5M ÷ 10,800 sec = ~2,360/sec sustained during primetime
- A correlated spike (viral event) can drive 4–5× primetime rate for 5–10 minutes: ~10,000–12,000/sec

We provision for **5,000/sec sustained** (8.5× average) and **12,000/sec burst** (20× average, handled by queue depth absorbing the spike rather than requiring worker capacity to process it in real time). Queue depth is our shock absorber; workers drain the backlog after the spike.

**Infrastructure implication:** Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge instance (benchmarks show >100K ops/sec for simple sorted set operations). Worker pool sizing targets 5,000/sec throughput; burst above that queues and drains within minutes.

#### 1.1.2 Infrastructure Provisioning vs. Production Data — Contradiction Resolved

**[Criticism addressed: #1 — "Decision gate" conflicted with month 2 launch commitment.]**

The previous version said "do not finalize Redis cluster sizing until two weeks of production data" while also committing to shipping a working system in month 2. These conflict: if you launch in month 2, you need infrastructure provisioned before month 2, which is before you have production data.

**Resolution:** We provision infrastructure based on the base-case model above before launch, not after. The "decision gate" is removed. Instead:

- **Before month 1 ends:** Provision ElastiCache r6g.xlarge (handles 2,000/sec with headroom), RDS db.r6g.2xlarge for PostgreSQL, and 40 delivery workers total across priority tiers.
- **Month 1 synthetic load test:** Run a load test at 2× base case (3,500/sec) against staging infrastructure before production launch. This validates sizing without requiring production data.
- **Month 2 post-launch:** Instrument actual event rates. If actual rates exceed 3,000/sec sustained during the first two weeks, trigger the scale-up runbook (documented in §7) before end of month 2.
- **Scale-up path without architectural change:** ElastiCache supports vertical scaling with a failover that takes <60 seconds. Worker count scales horizontally. Neither requires code changes.

The real lesson: use load testing to validate pre-launch sizing, and use production data to tune, not to make the initial provisioning decision.

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications (likes, follows) would produce an absurd cost: 2% of 51M/day = 1M SMS/day × $0.0079 = $2.9M/year. We treat SMS as a privileged channel reserved for authentication and security.

Realistic channel mix:

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---------|-------------|------------|-----------|------------|-------|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

**Hard SMS cap — with atomic enforcement:**

**[Criticism addressed: #3 — SMS cap had a race condition with distributed router instances.]**

The previous version said the cap was "enforced at the router" without explaining how distributed router instances would coordinate. Two simultaneous routing decisions for the same user could both read a count of 2 and both decide to send, exceeding the per-user cap of 3.

We enforce the cap using a Redis atomic increment with a conditional check, implemented as a Lua script:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded
-- Key expires at midnight UTC to reset daily counts

local key = KEYS[1]  -- "sms_cap:{user_id}:{date}"
local cap = tonumber(ARGV[1])  -- 3 for non-auth SMS

local current = redis.call('GET', key)
if current == false then
    -- First SMS of the day; initialize with TTL until midnight
    redis.call('SET', key, 1, 'EX', ARGV[2])  -- ARGV[2] = seconds until midnight
    return 1
elseif tonumber(current) < cap then
    redis.call('INCR', key)
    return 1
else
    return 0
end
```

This executes atomically on a single Redis node. Two simultaneous routing decisions for the same user will serialize on this script — one will increment and return 1, the other will see the updated count and return 0 if the cap is reached. Auth SMS (OTP) bypasses this check entirely and uses a separate key with a higher cap (10/day) to prevent OTP abuse.

**Global daily cap** of 200K non-auth SMS messages is enforced via a separate Redis counter on the same atomic pattern, at the router level. When the global cap is reached, non-auth SMS is dropped (not queued to the next day — carrying over creates unbounded accumulation). Auth SMS is always exempt.

### 1.3 Team Allocation — E4 Scope Reduced

**[Criticism addressed: #6 — E4 owned an unrealistic scope.]**

The previous version assigned E4: email integration, SMS integration, reliability engineering, monitoring, and DevOps. Email alone involves webhook processing, bounce handling, suppression list sync, IP warming, deliverability monitoring, and template deployment. SMS involves STOP handling, carrier error codes, and Twilio webhook processing. "Reliability and monitoring" is a full-time role. Grouping these because they're "webhook-heavy" was an organizational rationalization, not a workload analysis.

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary / Backup |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, reliability/monitoring infrastructure | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user-facing API, suppression logic, in-app notifications, WebSocket layer | Backup: E4 |
| E4 | Email (SendGrid) + SMS (Twilio), webhook processing, DevOps/deployment pipelines | Backup: E2 |

**Changes made:**
- Reliability and monitoring infrastructure moves to E1, who owns the core pipeline. Monitoring a system you built is natural; monitoring someone else's system is overhead.
- E3 absorbs in-app and WebSocket, which are closely related (both are user-facing read/write paths). E3 previously owned preference management, which is adjacent.
- E4 retains email and SMS but loses reliability/monitoring. DevOps/deployment is kept with E4 because email and SMS both require careful deployment coordination (IP warming schedules, Twilio webhook endpoint registration).
- E4's scope is still broad but is now bounded to two delivery channels plus deployment. This is manageable for a 6-month engagement where both channels are mature integrations with good SDK support.

**Explicit capacity check:** Email integration (weeks 1–4) and SMS integration (weeks 3–6) overlap. E4 cannot do both simultaneously at full depth. The schedule in §6 staggers these: email webhooks are the month-1 priority; SMS STOP handling and carrier error processing are month-2 work. The backup (E2) is documented on the email webhook schema by end of month 1.

**Bus factor mitigation:** Each engineer produces a runbook for their integration by end of month 1. Month 2 includes explicit cross-training sessions (2 hours/week, scheduled). We accept month-1 knowledge silos and address them on a fixed schedule.

### 1.4 Managed Services and Scaling Triggers

**[Criticism addressed: #12 — "Revisit at 50M MAU" appeared four times without triggers, owners, or lead times.]**

The previous version deferred four architectural decisions to "50M MAU" with no tracking mechanism, no owner, and no lead time estimate. If growth is faster than expected, these could all become urgent simultaneously.

We replace "revisit at 50M MAU" with explicit, owned, time-bounded triggers:

| Decision | Trigger | Owner | Lead Time Needed | Action |
|----------|---------|-------|-----------------|--------|
| Per-channel queues vs. single queue | Sustained queue depth >100K items during non-spike periods, OR per-channel rate limiting becomes a business requirement | E1 | 6 weeks | Migrate to per-channel Redis sorted sets; no data migration needed, just new routing logic |
| SendGrid vs. SES | Monthly email cost exceeds $5K AND deliverability metrics are stable (bounce <1%, spam <0.05%) | E4 | 8 weeks | SES migration with parallel-send validation period |
| Managed services vs. self-operated | Engineering team >12 AND managed service costs exceed $30K/month AND a specific operational limitation is documented | E1 + EM | 12 weeks | Evaluate specific service (e.g., Redis → self-hosted Valkey); do not migrate wholesale |
| Direct push integrations vs. managed push (OneSignal/Braze) | Advanced segmentation or A/B testing features are on the product roadmap AND direct integration maintenance exceeds 0.5 engineer/quarter | E2 | 4 weeks | Evaluate current OneSignal/Braze pricing at actual MAU |

**Tracking:** A monthly metrics review (30 minutes, E1 runs it) checks each trigger. Current MAU is tracked via the analytics pipeline already instrumented for product metrics — no separate tracking needed.

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
     ├─────────────────────────────────────────────┐
     ▼                                             ▼
[Priority Queue]                          [In-App Write Path]
  (Redis sorted set — Lua atomic ops)      (PostgreSQL, partitioned)
     │                                          │
     ├── P0 Workers (10)                        ├── Sync write to DB
     ├── P1 Workers (20)                        ├── Publish to Redis Pub/Sub
     └── P2/P3 Workers (10)                     └── Client polls on reconnect
          │                                          (see §3.3)
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log + Feedback Processor]
   (PostgreSQL + S3 archive)
```

### 2.2 Unified Delivery Guarantee Model

**[Criticism addressed: #4 — In-app bypass created inconsistent delivery guarantees and a second code path with separate monitoring.]**

The previous version routed in-app notifications around the queue entirely, with different retry semantics, different dead-letter handling, and different observability. The stated justification was simplicity, but it actually added a second code path needing its own monitoring and runbook.

**We retain the in-app bypass** — routing 10M/day in-app writes through the same queue as push would add latency for no delivery benefit, since in-app notifications are writes to a database we control directly. However, we now make the delivery guarantees **explicit and documented** for both paths, and we unify observability.

**Two delivery paths, explicitly modeled:**

| Property | Queue-based (Push/Email/SMS) | Direct-write (In-app) |
|----------|-----------------------------|-----------------------|
| Retry on failure | Yes — up to 3 attempts, exponential backoff, then DLQ | Yes — up to 3 attempts at application layer, then error log + alert |
| Dead-letter handling | Redis DLQ, reviewed every 6 hours | PostgreSQL `failed_notifications` table, same review cadence |
| Observability | Unified delivery event log (see below) | Same unified delivery event log |
| Idempotency | Notification ID in queue payload; workers check before processing | Notification ID as upsert key; duplicate writes are no-ops |
| Debugging | Check delivery event log by notification_id | Same — notification_id links both paths |

**Unified delivery event log:** Every notification, regardless of path, writes a row to the `delivery_events` table at each state transition (created, enqueued/written, delivered, failed). This is a write-ahead log pattern: the event is written before the delivery attempt, so a crash mid-delivery leaves a record. Engineers debugging a missed notification check one place regardless of channel.

```sql
CREATE TABLE delivery_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL,
    channel         VARCHAR(32) NOT NULL,  -- 'push', 'email', 'sms', 'in_app'
    event_type      VARCHAR(32) NOT NULL,  --