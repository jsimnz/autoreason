# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: What This Document Is and Is Not

This is a **design document**. It records architectural decisions, their rationale, and the tradeoffs made under staffing and time constraints.

This document is **not an operational runbook**. Incident response procedures, escalation chains, and operator CLI references belong in a separate runbook that is version-controlled independently of this design. The runbook must be authored and maintained separately; its section numbers will not track changes to this document. The pre-flight checklist in Section 7.1 includes a gate requiring the runbook to exist and be linked before production deployment.

**Why this separation matters:** A design document is revised as the system evolves. A runbook embedded in a design document becomes incorrect every time the design changes. Operators under incident conditions cannot afford to discover that the section reference they were given no longer exists.

**Runbook authorship is a named, tracked commitment, not an implied dependency.** The runbook owner, deadline, and fallback are specified in Section 7.1 alongside all other named commitments. It has an owner, a deadline, and a consequence if the deadline is missed. The consequence of a missing runbook is not "nothing deploys" — it is that the pre-flight checklist in Section 7.1 fails its runbook gate, and the on-call rotation owner makes the go/no-go call with explicit knowledge that operators will be working without documented procedures. That is a risk the on-call rotation owner can accept in writing; it is not a risk engineering accepts silently.

---

## Unresolved Decisions

Six decisions require named humans before the system can launch. Each has a fallback. The fallbacks keep the system operational; they are not optimal product choices.

For each decision, the authority to select the fallback is held by the owner named in Section 7.1. Engineering does not have unilateral authority to make product behavior decisions. What engineering does have is authority to block deployment if a decision is not made by the deadline in Section 7.1 — and the fallback is what gets deployed if the owner makes no selection by that deadline, because the owner's silence is itself a choice that the owner owns.

| # | Decision | Fallback | Authority |
|---|---|---|---|
| 1 | Burst allowance (Section 1.1) | 3 notifications above ceiling per 5-minute window | Product owner (Section 7.1) |
| 2 | Daily spam threshold (Section 1.1) | Hard cap of 200 notifications/user/day, automatic suppression | Product owner (Section 7.1) |
| 3 | Fanout cap option (Section 1.1) | Option A — accept consistency gap | Product owner (Section 7.1) |
| 4 | Cross-channel deduplication retention window (Section 2.2) | 24 hours | Product owner (Section 7.1) — see correctness note below |
| 5 | SMS opt-out compliance owner (Section 5.4) | SMS channel disabled at launch | Legal/compliance owner (Section 7.1) |
| 6 | Runbook authorship (Section 7.1) | Pre-flight runbook gate fails; on-call rotation owner makes written go/no-go decision | On-call rotation owner (Section 7.1) |

**Decision 4 correctness note — deduplication window:** The 24-hour fallback has a product correctness consequence the product owner must understand before accepting it. If a user receives a push notification and opens the app more than 24 hours later, the deduplication key has expired. The system will generate a duplicate in-app notification for an event the user already received via push. Whether this is acceptable depends on how the product surfaces the notification feed. If the feed is append-only and users scroll back, duplicates are visible and confusing. If the feed is deduplicated at read time by event ID, the infrastructure window matters less. The product owner must answer this question before accepting the 24-hour fallback. Engineering's recommendation is 48 hours; the Redis cost difference is quantified in Section 6.1.

**Decision 2 and SMS cost routing:** The daily spam threshold (Decision 2) is a product owner decision, but it has direct financial consequences for SMS costs that may exceed the product owner's budget authority. Section 1.2 quantifies the exposure: up to $75,000/day in unbudgeted SMS costs from uncapped power-user volume. Before the product owner finalizes Decision 2, the SMS cost exposure must be reviewed by whoever owns the SMS cost budget. Section 7.1 names that person. If the budget owner and product owner disagree, the more restrictive threshold applies until the disagreement is resolved. Engineering does not adjudicate budget disputes; it enforces whichever threshold is in the configuration at deployment time.

**Dependency chain for infrastructure sizing:** Two decisions affect infrastructure provisioning in sequence. First, the deduplication retention window (Decision 4) determines Redis key volume. Second, FCM rate verification (Section 1.4) determines which Redis sizing branch applies. If FCM verification is not complete before launch, Branch B sizing (Section 6.1) is the default. Branch B remains in force until the explicit migration trigger in Section 6.1 is met.

---

## Table of Contents

1. Scale Assumptions and Constraints
   - 1.1 Traffic Model
   - 1.2 Channel Split and Volume Accounting
   - 1.3 Traffic Response Matrix
   - 1.4 FCM/APNs Rate Limit Verification
   - 1.5 Staffing Analysis
2. Notification Routing and Deduplication
   - 2.1 Routing Logic
   - 2.2 Deduplication Architecture
3. Priority and Batching
   - 3.1 Priority Tiers
   - 3.2 Token Bucket Parameters and Starvation Prevention
   - 3.3 Batching Logic
4. Worker Architecture
   - 4.1 Worker Deployments
   - 4.2 Processing State and Recovery
   - 4.3 Queue Backup and Worker Failure Behavior
5. Delivery Channels
   - 5.1 Push (FCM + APNs)
   - 5.2 In-App
   - 5.3 Email
   - 5.4 SMS
6. Infrastructure
   - 6.1 Queue Infrastructure and Redis Sizing Branches
   - 6.2 Redis Failover and In-Flight Behavior
   - 6.3 Database
7. Operations
   - 7.1 Pre-Flight Checklist and Named Owners
   - 7.2 On-Call Rotation and Escalation
8. Build Timeline

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS for a 10M MAU social app, built by 4 engineers over 6 months.

**The staffing constraint is a design input, not a caveat.** Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. That arithmetic starts from a fixed budget of engineer-weeks, subtracts non-feature work (testing, on-call, code review, deployment), and derives the maximum number of deployments that can be built and safely operated within the remaining capacity. The architectural decisions follow from that bound; the bound does not follow from the decisions. The arithmetic is present in Section 1.5, not merely cited.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. Token bucket parameters — refill rates, bucket sizes, and the conditions under which P2/P3 can still be deferred despite the token bucket — are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that window is in Section 4.2, not merely cited. Worst-case delivery outcome under crash recovery is duplication, not loss. This claim is qualified: it holds for crash recovery and for the Redis failover scenario in Section 6.2 under the conditions specified there. There is one failure mode — a Redis primary failure during the promotion window where the processing sorted set has not yet replicated — where in-flight entries can be lost rather than duplicated. That scenario, its probability bound, and the recovery procedure are specified in Section 6.2.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches (A and B) with stated capacity bounds for each, depending on the FCM rate verification outcome in Section 1.4. The FCM uncertainty range and its effect on Branch A vs. Branch B sizing are quantified in Section 1.4.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The sensitivity table uses joint scenarios: the low row uses both a low ratio and a low rate; the extreme row uses both high values. Treating them as independent understates high-engagement risk.

---

**Peak multiplier methodology:**

Dividing total daily volume by 24 hours includes overnight hours with near-zero traffic, which suppresses the computed average and causes multiplied results to understate actual peaks.

**Revised methodology:** Divide daily volume by the number of active hours — hours in which send rate exceeds 10% of the hourly average. This document uses 14 active hours as the conservative (higher-peak) planning estimate.

**Limitation:** 14 active hours is an assumption from general social-app patterns, not a measured value for this application. If actual active hours are 16–18, computed peak rates are 14–22% lower than stated. The direction of the correction is acceptable for capacity planning — it means the system is sized conservatively — but the magnitude is unknown until month-1 data is available.

**Calibration requirement:** The on-call rotation owner recalibrates active hours and multipliers at the month-1 checkpoint using actual traffic data. The procedure is specified in Section 7.1. Until recalibration, all peak rate figures carry ±25% uncertainty.

```
active_hours           = 14
active_hour_avg        = daily_volume / active_hours
peak_hour_volume       = active_hour_avg × peak_multiplier
peak_rate (per sec)    = peak_hour_volume / 3,600
```

Example for the plan row:

```
active_hour_avg   = 45,000,000 / 14   = 3,214,286 notifications/hour
peak_hour_volume  = 3,214,286 × 2.2   = 7,071,429 notifications/hour
peak_rate         = 7,071,429 / 3,600 ≈ 1,964/sec
```

The extreme row's peak rate (~9,643/sec) is approximately 4.9× the plan row's (~1,964/sec) while daily volume is only 3.6× higher. Both daily volume and the peak multiplier are higher in the extreme row, and the multiplier compounds against the higher base. This is not an error in the methodology.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.0× | ~595/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **2.2×** | **~1,964/sec** |
| High engagement | 50% | 5M | 20 | 100M | 2.5× | ~4,960/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 3.0× | ~9,643/sec |

*All peak rates use the 14-active-hours formula. All figures carry ±25% uncertainty until month-1 recalibration.*

**Planning decision:** Size for 45M/day (~1,964/sec sustained peak). The traffic response matrix in Section 1.3 covers the full range from plan through 162M/day, with explicit infrastructure states for each threshold.

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day stresses per-user queue partitioning, Redis key distribution, and daily spam controls. These are two distinct problems requiring two distinct decisions.

**Problem 1 — Burst allowance:** The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. **Fallback if no decision before launch: 3.** Authority and deadline: Section 7.1.

**Problem 2 — Daily spam threshold:** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below the 480/day extrapolation of that ceiling). The operational risk of no cap is not zero: in a 10M MAU system at 30% DAU, even 0.1% of active users generating 500 notifications/day would add 1.5M unexpected notifications/day — a 3.3% volume increase that is unbudgeted and uncontrolled.

**SMS cost exposure from uncapped volume:** At 2% SMS share and $0.01/message, 1.5M additional notifications/day adds $15,000/day in unbudgeted SMS cost. At 5% SMS share, that exposure reaches $75,000/day. The full cost table in Section 1.2 provides the basis for these figures. As noted in the Unresolved Decisions table, the SMS budget owner must review this exposure before the product owner finalizes Decision 2.

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). **Fallback if no decision before launch: hard cap of 200 notifications/user/day with automatic suppression above that threshold.** The product owner owns the fallback outcome.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. The worst-case fanout completion time under sustained P0/P1 congestion is derived from the token bucket parameters in Section 3.2:

```
P2 minimum guaranteed rate (Section 3.2): 200 tokens/sec
Recipients beyond 10,000 cap: up to 90,000 (for a 100,000-recipient event)
Minimum completion time at guaranteed rate: 90,000 / 200 = 450 seconds ≈ 7.5 minutes

Under sustained P0/P1 saturation, P2 receives only its guaranteed minimum.
At 200/sec, 90,000 remaining recipients complete in 450 seconds.
With queue overhead and batch processing latency: ~10 minutes worst case.
```

The 200 tokens/sec figure is derived and justified in Section 3.2. If Section 3.2's parameters change, this bound must be recalculated. The dependency is explicit: the fanout SLA is downstream of the token bucket configuration.

**Note on prior drafts:** Any figure of ~45 minutes appearing in earlier versions was an error — it assumed P2 received only a fraction of its guaranteed rate under congestion, which contradicts the token bucket guarantee. The correct worst-case under the parameters in Section 3.2 is approximately 10 minutes. If P2's guaranteed minimum is lowered below 200/sec, this bound increases proportionally.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Select one option before launch. **Fallback if no decision: Option A.**

- **Option A — Accept the consistency gap.** The fanout window (~10-minute worst-case under sustained congestion) is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior