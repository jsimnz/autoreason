# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Two items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K SMS/day. The per-channel queue architecture is justified independently by push/email isolation, but the isolated SMS queue and OTP-isolation argument both depend on SMS being in scope. Critically, if the SMS budget decision is delayed past **Week 2 of Month 1**, E2's work plan must be restructured — this is not a passive gate. The contingency plan is documented explicitly in Section 1.2.

- **QA approach (Section 7):** Covered separately; carries real risk if approved without deliberate acknowledgment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. Two inputs drive the volume model: notifications per active user per day, and the DAU/MAU ratio. Both are variables, not constants.

#### DAU/MAU Ratio Sensitivity

| App Stage / Category | Typical DAU/MAU | DAU at 10M MAU |
|---------------------|----------------|----------------|
| Early-stage social app | 15–20% | 1.5M–2M |
| Mid-stage social app | 25–35% | 2.5M–3.5M |
| Mature, high-retention social | 40–50% | 4M–5M |

We use **25% (2.5M DAU)** as our planning basis — conservative for a mature product, realistic for a growth-stage app. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case. Using 30% would be optimistic for an app at this stage; if actual DAU/MAU exceeds 30% in production, we have headroom.

**Benchmarks for notifications per active user per day:**
- Conservative estimate for a new social app: 10–15
- Mid-range social app: ~15
- High-engagement product: 30+ (often with churn consequences)

We use **15** as our planning basis.

**Volume calculation uses channel-appropriate denominators:**

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU + lapsed users | Works regardless of app activity |
| SMS | Event-triggered, any user | Auth events happen to inactive users |

#### Peak Multiplier Rationale

The 3× peak multiplier for push and email reflects observed social app traffic patterns: morning and evening spikes, viral content moments, and coordinated events. SMS volume is event-triggered (OTPs, auth alerts) and follows login event patterns, not social traffic patterns. A 3× multiplier for SMS would imply ~225K SMS at peak — a $3,375 single-period Twilio cost driven by a login spike. SMS uses a **1.5× multiplier** based on login event variance; all other channels use 3×. Both are planning assumptions, not measured values. We instrument actual peak-to-average ratios from day one and revisit at the Month 2 checkpoint.

#### Full Sensitivity Matrix

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | **Total/day** | Push+Email Peak (3×) | SMS Peak (1.5×) | **Peak/sec** |
|---------|----------------|-----------------|-----------|---------|--------------|----------------------|-----------------|-------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 75K | ~15.6M | 46.5M | 113K | ~540/sec |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 75K | ~26.1M | 78M | 113K | ~905/sec |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **~41.1M** | **123M** | **113K** | **~1,430/sec** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 75K | ~56.1M | 168M | 113K | ~1,950/sec |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 75K | ~108.6M | 325.5M | 113K | ~3,770/sec |

**Sizing target:** We size for **2,500/sec sustained throughput**. This covers the planning basis (1,430/sec) with 75% headroom, handles the 35%/15 scenario (1,950/sec) comfortably, and requires horizontal scaling only if we reach the 35%/30 scenario — a point at which revenue projections would have been dramatically exceeded and scaling budget would exist.

#### Calibration Checkpoint (Month 2)

After 3–4 weeks of production data, we assess actual volume against planning basis. This is not a passive review — it has a defined decision process:

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity decision (see note below) | All engineers | Synchronous decision within 48 hours |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**Note on the ">60% above plan" path:** This window produces a *capacity decision*, not an architectural one. By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed and cannot be replaced without scrapping 6–8 engineer-weeks of work. What the 48-hour window actually produces is: how many workers to add, whether to upgrade Redis tier, and whether to negotiate increased SendGrid/FCM throughput limits. If the 35%/30 scenario materializes at Month 2, the honest response is horizontal scaling within the existing architecture plus scope reduction in Month 3 to absorb the operational load. We document this accurately so the team isn't surprised by the constraint.

The ±30% threshold is chosen because it represents a difference of ~400/sec at peak — within our headroom without worker changes. E4 owns the checkpoint report; the team lead owns the go/no-go decision for Month 3 scope.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**SMS budget dependency on E2's work plan:**

E2's Month 1–2 scope includes Twilio integration. If the SMS budget decision is not resolved by **Week 2 of Month 1**, E2's work plan must be restructured to avoid speculative implementation:

| SMS Decision Timeline | E2 Month 1–2 Adjustment |
|----------------------|------------------------|
| Approved by Week 2 | Proceed as planned; Twilio integration in Month 1 |
| Decision delayed past Week 2 | E2 deprioritizes Twilio; picks up APNs/FCM hardening or SendGrid integration work; Twilio scoped to Month 3 if approved later |
| SMS descoped entirely | E2 absorbs push reliability work; Section 3.4, SMS queue, and SMS-specific DLQ handling are removed |

The team lead owns the Week 2 go/no-go call. If no decision has been received by end of Week 2, the team lead escalates and E2 proceeds under the "delayed" path to avoid blocking Month 1 delivery.

**Ownership boundaries for cross-cutting components:**

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Dead-letter queue handlers, retry logic | E4 | E1, E2 |
| DLQ triage: push-specific failures (APNs/FCM) | E2 | E4 |
| DLQ triage: email-specific failures (SendGrid) | E2 | E4 |
| DLQ triage: SMS-specific failures (Twilio) | E2 | E4 |
| Backpressure and rate limiting | E1 | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

**Rationale for split DLQ ownership:** DLQ entries require channel-specific knowledge to triage. Distinguishing an APNs invalid token (permanent failure — suppress the token) from a transient FCM 503 (retry) from a Twilio carrier rejection (investigate number validity) requires the person who built those integrations. E4 owns the DLQ *infrastructure* — the dead-letter queues themselves, the retry scheduler, the alerting. E2 owns *triage and resolution* for channel-specific failures and is the documented on-call contact for provider-level failures. This is reflected in runbooks, not just this table.

The principle: E1 owns the path that works; E4 owns the path that fails at the infrastructure level; E2 owns the path that fails at the provider level. Where E1 and E4 overlap (backpressure), E1 owns implementation and E4 owns policy. Disputes escalate to a 30-minute sync, not a Slack thread.

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
  - Preference check  (Redis cache, version-fenced write-through, TTL=60s)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment
  - Channel selection
     │
     ├─→ [Push Queue]    (Redis Sorted Set)  → Push Workers   → APNs / FCM
     ├─→ [Email Queue]   (Redis Sorted Set)  → Email Workers  → SendGrid
     ├─→ [SMS Queue]     (Redis Sorted Set)  → SMS Workers    → Twilio
     └─→ [In-App Queue]  (Redis List)        → In-App Workers → PostgreSQL
                                    │
                          [Delivery Log]
                          (PostgreSQL + S3 archive)
                                    │
                          [Feedback Processor]
                          (bounces, opens, failures → suppression list)
```

### 2.2 Why Per-Channel Queues

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure, not a performance one.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

This justification holds independently of whether SMS is in scope. Push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation on their own. SMS isolation is an additional benefit, not the primary argument.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately one engineer-day to set up; the failure isolation benefit is worth it.

### 2.3 In-App Notifications — Queued, Not Direct Write

In-app notifications use a Redis List queue (FIFO, no priority tiers needed within this channel). Workers dequeue and write to PostgreSQL asynchronously. The router is never blocked by PostgreSQL write pressure.

The "immediate consistency" argument for direct writes is overstated: a 1–2 second delay through a queue is imperceptible to users reading their notification feed. Operational consistency with other channels is worth more than the marginal latency reduction.

```
Queue type:       Redis List (LPUSH/BRPOP — FIFO)
Workers:          4 processes (derivation in Section 5)
Retry on failure: exponential backoff, max 3 attempts, then DLQ
Priority tiers:   None — all in-app notifications are equivalent
```

### 2.4 Preference Cache — Honest Staleness Model

**What caching solves and what it doesn't:**

The preference cache reduces database reads on the hot path. It does not provide strong consistency. This section describes the actual staleness behavior so the system is designed and communicated accurately.

#### The Race Condition We Cannot Fully Eliminate

The write-through pattern (write DB, delete Redis key) has a structural gap that version fencing only partially addresses:

```
Thread A: writes new prefs to DB (version 4 → 5)
Thread B: reads old prefs from Redis (cache hit, version 4) — stale read
Thread A: Lua script deletes Redis key
Thread B: re-caches version 4 prefs with fresh 60s TTL  ← stale data re-cached
```

Thread B's re-caching happens *after* the Lua script has already run. The version fence has no mechanism to intercept this re-population. This is a structural property of any cache that allows concurrent reads during writes, not a bug fixable with a smarter Lua script.

**A second gap:** When the cache is cold and `get_user_preferences` reads from the database and populates Redis, there is no atomic guard on the population step. If the read hits a replica with replication lag — the common case under write pressure — the cache is populated with a stale version and a fresh TTL. The version fencing mechanism is bypassed entirely at the most vulnerable moment.

#### What Version Fencing Actually Provides

Version fencing controls one specific scenario: a *delayed invalidation* from write N should not delete a cache entry populated by write N+1. Without it:

```
Write 1: version 4 → 5, invalidation fires (delayed)
Write 2: version 5 → 6, populates cache with version 6
Write 1's delayed invalidation: deletes cache key (removes valid version 6)
Reader: re-populates from replica with replication lag, gets version 5  ← stale
```

With strict less-than fencing, write 1's invalidation evaluates `6 < 5` — false — and correctly leaves the cache alone.

**Why strictly less-than (`<`) and not less-than-or-equal (`<=`):**

With `<=`, write 2's own invalidation evaluates `6 <= 6` — true — and deletes the entry it just wrote, causing an unnecessary cache miss. Under write pressure, this produces thundering herd DB reads. More critically, if a reader re-populates from a lagged replica after this unnecessary eviction, we cache a stale version despite having just written a newer one. Strict less-than prevents this: an invalidation only evicts entries it knows are strictly older than itself.

```python
# Lua script: delete key only if stored version is strictly older than what we wrote
INVALIDATE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current then
    local data = cjson.decode(current)
    if data.version < tonumber(ARGV[1]) then
        redis.call('DEL', KEYS[1])
        return 1
    end
end
return 0
"""

def update_user_preferences(user_id: str, updates: dict