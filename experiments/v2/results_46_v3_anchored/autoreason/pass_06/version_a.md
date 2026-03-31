# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly — estimated at 2–3 engineer-weeks across the build phase, not one day.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Three items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K–105K SMS/day depending on DAU. The architectural commitment to an isolated SMS queue depends on SMS being in scope. If the SMS budget decision is delayed past Week 2, E2's Month 1 work plan must be restructured — this is not a passive gate. The dependency is tracked explicitly in Section 1.2 with a decision deadline. The core cost question is whether $17–24K/month in ongoing SMS costs is within budget, not whether spike risk is manageable.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which a user who has opted out may receive a notification. This is a legal and trust problem. We have a mitigation plan, but it requires deliberate product and legal sign-off on the residual risk — not just an engineering acknowledgment.

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

#### How Peak Throughput Is Calculated

Daily volume is not uniformly distributed. Social app traffic concentrates in morning and evening windows. We model peak load over a **2-hour sustained window** — long enough to stress infrastructure, short enough to reflect observed social app traffic patterns. The 2-hour window is a planning assumption, not a measured value; we instrument actual peak window duration from day one.

If a social app delivers 90% of its push and email notifications across two 2-hour windows, the effective peak rate is:

```
Peak rate = (Daily volume × 0.90) ÷ (2 windows × 7,200 sec/window)
          = Daily volume × 0.0625
```

This is approximately equivalent to a **6× peak multiplier** applied to the average per-second rate, sustained for 2 hours.

**SMS peak multiplier:** SMS is event-triggered by login events, not social traffic patterns. Login spikes are shorter (15–30 minutes) and less correlated with content consumption peaks. We model SMS peak over a **30-minute window** at 2× average rate.

**SMS volume is derived, not asserted:**

```
SMS/day = DAU × login_rate × OTP_rate
        = DAU × 0.30 × 0.10
        = DAU × 0.03
```

Where `login_rate` (0.30) is the fraction of DAU triggering a new session daily, and `OTP_rate` (0.10) is the fraction of logins requiring an OTP. At 2.5M DAU this yields 75K/day — but now as a derived figure with explicit variables we can update from production data.

**Corrected SMS peak/sec:**
```
SMS average rate = 75,000 ÷ 86,400 ≈ 0.87/sec
SMS peak rate (2× over 30-min window) ≈ 1.7/sec
```

SMS is never the throughput constraint. The queue isolation argument for SMS rests on latency requirements (OTP delivery), not throughput.

#### Full Sensitivity Matrix

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Total/day | **Peak/sec (2-hr window)** |
|---------|----------------|-----------------|-----------|---------|-----------|---------------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 45K | ~15.5M | ~267 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 45K | ~26.0M | ~500 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **~41.1M** | **~838** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 105K | ~56.1M | ~1,174 |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 105K | ~108.6M | ~2,346 |

*Sample derivation for planning basis: (37.5M + 3.5M) × 0.0625 = 2,562,500 notifs in the peak window ÷ 7,200 sec = ~838/sec.*

**Sizing target:** We size for **1,500/sec sustained throughput**. This covers the planning basis (838/sec) with 79% headroom and handles the 35%/15 scenario (1,174/sec) with 28% headroom. The 35%/30 scenario (2,346/sec) requires horizontal scaling — at that point, the user base and engagement metrics would indicate a product success that justifies the infrastructure investment.

**On headroom framing:** Headroom is measured against the highest scenario we are explicitly designing for (35%/15 at 1,174/sec). The 35%/30 scenario is acknowledged as requiring redesign, not covered by headroom.

**On the SMS cost question:** The relevant figure is not spike risk but ongoing cost. At $0.0075/message (Twilio US domestic):
- Planning basis (75K/day): ~$17K/month
- 35% DAU scenario (105K/day): ~$24K/month

This is the question requiring budget sign-off. A 2× spike sustained for a full day adds at most ~$1,100–$1,575 above the daily baseline — a rounding error on the monthly total.

#### Calibration Checkpoint (Month 2)

After 3–4 weeks of production data, we assess actual volume against planning basis.

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity + scope decision — see note | All engineers + stakeholders | 48 hours for options; 1 week for stakeholder sign-off |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**What the ">60% above plan" path actually produces:** By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed and cannot be replaced without scrapping 6–8 engineer-weeks of work. The 48-hour window produces a **capacity decision** (worker count, Redis tier, provider throughput limits) and a **scope decision** (which Month 3 features get deferred). The scope decision requires stakeholder sign-off — it is not resolvable by the engineering team alone. If sign-off cannot be obtained within 1 week, the default is horizontal scaling within the existing architecture with no new feature work in Month 3. This default is documented now so it is not a surprise later.

---

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**SMS budget dependency on E2's work plan:**

| SMS Decision Timeline | E2 Month 1–2 Adjustment |
|----------------------|------------------------|
| Approved by Week 2 | Proceed as planned; Twilio integration in Month 1 |
| Decision delayed past Week 2 | E2 deprioritizes Twilio; picks up additional APNs/FCM hardening or SendGrid integration work; Twilio scoped to Month 3 if approved later |
| SMS descoped entirely | E2 absorbs push reliability work; Section 3.4, SMS queue, and SMS-specific DLQ handling are removed; queue justification in Section 2.2 updated to reflect push/email-only isolation argument |

The team lead owns the Week 2 go/no-go call. If no decision has been received by end of Week 2, the team lead escalates and E2 proceeds under the "delayed" path.

**Ownership table for cross-cutting components:**

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Suppression logic (frequency caps, opt-out enforcement) | E3 | E1 |
| Suppression → queue boundary | E3 + E1 | E4 |
| Dead-letter queue infrastructure, retry scheduler | E4 | E1, E2 |
| DLQ triage: push-specific failures (APNs/FCM) | E2 | E4 |
| DLQ triage: email-specific failures (SendGrid) | E2 | E4 |
| DLQ triage: SMS-specific failures (Twilio) | E2 | E4 |
| Preference cache implementation | E3 | E1 |
| Backpressure and rate limiting | E1 | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

**Ownership principles:**

E3 owns suppression logic and preference management — the decisions about what notifications are permitted to enter the queues at all. The boundary is explicit: E3's suppression layer produces a boolean (deliver / suppress) and a channel list; E1's queue layer consumes that output and routes accordingly. Neither engineer makes decisions in the other's domain.

E4 owns DLQ *infrastructure*; E2 owns *triage and resolution* for channel-specific failures. Distinguishing an APNs invalid token (permanent failure, suppress the token) from a transient FCM 503 (retry) from a Twilio carrier rejection (investigate number validity) requires the person who built those integrations. This split is reflected in runbooks, not just this table.

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
  - Preference check  (Redis cache — staleness model in Section 2.4)
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

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure, not a performance tradeoff.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

This justification holds independently of whether SMS is in scope. Push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation on their own. SMS isolation is an additional benefit, not the primary argument.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately 2–3 engineer-weeks across the build phase. The failure isolation benefit is worth it; we accept this overhead explicitly.

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

The preference cache reduces database reads on the hot path. It does not provide strong consistency. This section describes the actual staleness behavior so the system is designed and communicated accurately — and so that legal and product can make an informed sign-off decision on the residual risk.

#### The Race Condition We Cannot Fully Eliminate

The write-through pattern (write DB, delete Redis key) has a structural gap that version fencing only partially addresses:

```
Thread A: writes new prefs to DB (version 4 → 5)
Thread B: reads old prefs from Redis (cache hit, version 4) — stale read
Thread A: Lua script deletes Redis key (correctly)
Thread B: re-caches version 4 prefs with fresh 60s TTL  ← stale data re-cached
```

Thread B's re-caching happens *after* the Lua script has already run. The version fence has no mechanism to intercept or reject that re-population. This is a structural property of any cache that allows concurrent reads during writes — not a bug we can fix with a smarter Lua script.

**A second gap:** When the cache is cold