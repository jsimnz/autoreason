# Notification System Design — Revised v2
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Two items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K SMS/day. The architectural commitment to an isolated SMS queue depends on SMS being in scope. Critically, if the SMS budget decision is delayed past Week 2, E2's Month 1 work plan must be restructured — this is not a passive gate. The dependency is tracked explicitly in Section 1.2 with a decision deadline.

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

We use 25% (2.5M DAU) as our planning basis. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case.

**Benchmarks for notifications per active user per day:**
- Conservative estimate for a new social app: 10–15
- Mid-range social app: ~15
- High-engagement product: 30+

We use 15 as our planning basis.

**Volume calculation uses channel-appropriate denominators:**

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU + lapsed users | Works regardless of app activity |
| SMS | Event-triggered, any user | Auth events happen to inactive users |

#### Full Sensitivity Matrix

*Note on SMS peak multiplier:* SMS volume is event-triggered (OTPs, auth alerts) and follows login event patterns, not social traffic patterns. A 3× multiplier for SMS would imply 225K SMS at peak — a $3,375 single-period Twilio cost driven by a login spike, not a viral content moment. SMS uses a 1.5× multiplier based on login event variance; all other channels use 3×. This distinction matters for both cost modeling and queue sizing.

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | **Total/day** | Push+In-App Peak (3×) | SMS Peak (1.5×) | **Peak/sec** |
|---------|----------------|-----------------|-----------|---------|--------------|----------------------|-----------------|-------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 75K | ~15.6M | 36M | 113K | ~420/sec |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 75K | ~26.1M | 67.5M | 113K | ~780/sec |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **~41.1M** | **112.5M** | **113K** | **~1,300/sec** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 75K | ~56.1M | 157.5M | 113K | ~1,820/sec |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 75K | ~108.6M | 315M | 113K | ~3,640/sec |

*Previous version had identical totals for the 15% DAU/15 notif and 25% DAU/15 notif rows — an arithmetic error. These rows now reflect their correct distinct values: 1.5M × 15 = 22.5M push+in-app vs. 2.5M × 15 = 37.5M push+in-app.*

**Sizing target:** We size for 2,500/sec sustained throughput. This covers the planning basis (1,300/sec) with 92% headroom, handles the 35%/15 scenario (1,820/sec) comfortably, and requires horizontal scaling only if we reach the 35%/30 scenario — a point at which revenue projections would have been dramatically exceeded and scaling budget would exist. The 3× peak multiplier for push/email reflects observed social app traffic patterns (morning and evening spikes, viral content moments). It is a planning assumption, not a measured value; we instrument actual peak-to-average ratios from day one and revisit at the Month 2 checkpoint.

**Calibration checkpoint (Month 2):** After 3–4 weeks of production data, we assess actual volume against planning basis.

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | See Section 1.1 note below | All engineers | Synchronous decision within 48 hours |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**Note on the ">60% above plan" escalation path:** The previous version described this as an "architectural review" — implying the architecture could be revisited in 48 hours. That is not realistic. By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed and cannot be replaced without scrapping 6–8 engineer-weeks of work. What the 48-hour window actually produces is a *capacity decision*, not an architectural one: how many workers to add, whether to upgrade Redis tier, and whether to negotiate increased SendGrid/FCM throughput limits. If the 35%/30 scenario materializes at Month 2, the honest response is horizontal scaling within the existing architecture plus a scope reduction in Month 3 to absorb the operational load. We document this accurately so the team isn't surprised by the constraint.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**SMS budget dependency on E2's work plan:**

E2's Month 1–2 scope includes Twilio integration. If the SMS budget decision is not resolved by **Week 2 of Month 1**, E2's work plan must be restructured to avoid speculative implementation. The contingency is explicit:

| SMS Decision Timeline | E2 Month 1–2 Adjustment |
|----------------------|------------------------|
| Approved by Week 2 | Proceed as planned; Twilio integration in Month 1 |
| Decision delayed past Week 2 | E2 deprioritizes Twilio; picks up additional APNs/FCM hardening or SendGrid integration work; Twilio scoped to Month 3 if approved later |
| SMS descoped entirely | E2 absorbs push reliability work; Section 3.4, SMS queue, and SMS-specific DLQ handling are removed; queue justification in Section 2.2 updated to reflect push/email-only isolation argument |

The team lead owns the Week 2 go/no-go call. This is not a passive gate — if no decision has been received by end of Week 2, the team lead escalates and E2 proceeds under the "delayed" path to avoid blocking Month 1 delivery.

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

**Rationale for DLQ triage ownership change:** The previous version assigned DLQ ownership entirely to E4, with E2 absent from the DLQ row. DLQ entries for push, email, and SMS require channel-specific knowledge to triage: distinguishing an APNs invalid token (permanent failure, suppress the token) from a transient FCM 503 (retry) from a Twilio carrier rejection (investigate number validity) requires the person who built those integrations. E4 owns the DLQ *infrastructure* — the dead-letter queues themselves, the retry scheduler, the alerting. E2 owns *triage and resolution* for channel-specific failures and is the documented on-call contact for 2am alerts on those queues. This is reflected in runbooks, not just this table.

The principle: E1 owns the path that works; E4 owns the path that fails at the infrastructure level; E2 owns the path that fails at the provider level. Disputes escalate to a 30-minute sync, not a Slack thread.

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
  - Preference check  (Redis cache, see Section 2.4 for staleness model)
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

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

This justification holds independently of whether SMS is in scope. Push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation on their own. SMS isolation is an additional benefit, not the primary argument.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately one engineer-day to set up; the failure isolation benefit is worth it.

### 2.3 In-App Notifications — Queued, Not Direct Write

In-app notifications use a Redis List queue (FIFO, no priority tiers needed within this channel). Workers dequeue and write to PostgreSQL asynchronously. The router is never blocked by PostgreSQL write pressure.

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
Thread A: Lua script deletes Redis key (correctly)
Thread B: re-caches version 4 prefs with fresh 60s TTL  ← stale data re-cached
```

Thread B's re-caching happens *after* the Lua script has already run. The version fence has no mechanism to intercept or reject that re-population. This is a structural property of any cache that allows concurrent reads during writes, not a bug we can fix with a smarter Lua script.

**A second gap:** When the cache is cold and `get_user_preferences` reads from the database and populates Redis, there is no atomic guard on the population step. If the read hits a replica with replication lag — which is the common case under write pressure — the cache is populated with a stale version and a fresh TTL. The version fencing mechanism is bypassed entirely at the most vulnerable moment.

#### What Version Fencing Actually Provides

Version fencing with a Lua script controls one specific scenario: a *delayed invalidation* from write N should not delete a cache entry that was populated by write N+1. Without it:

```
Write 1: version 4 → 5, invalidation fires
Write 2: version 5 → 6, populates cache with version 6
Write 1's delayed invalidation: deletes cache key (removes valid version 6)
Reader: re-populates from replica with replication lag, gets version 5
```

With strict less-than fencing (`stored_version < new_version`), write 1's invalidation evaluates `6 < 5` — false — and correctly leaves the cache alone.

**Why strictly less-than (`<`) and not less-than-or-equal (`<=`):** With `<=`, write 2's own invalidation would evaluate `6 <= 6` — true — and delete the entry it just wrote, causing an unnecessary cache miss. Under write pressure, this produces thundering herd DB reads. More dangerously, if a reader re-populates from a lagged replica, we cache a stale version despite having just written a newer one. Strict less-than prevents this: an invalidation only evicts entries it knows are older than itself.

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

def update_user_preferences(user_id: str, updates: dict) -> int:
    new_version = db.execute("""