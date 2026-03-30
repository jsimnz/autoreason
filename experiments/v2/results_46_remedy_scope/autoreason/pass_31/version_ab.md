# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: What This Document Is and Is Not

This is a **design document**. It records architectural decisions, their rationale, and the tradeoffs made under staffing and time constraints.

This document is **not an operational runbook**. Incident response procedures, escalation chains, and operator CLI references belong in a separate runbook that is version-controlled independently of this design. The pre-flight checklist in Section 7.1 includes a gate requiring the runbook to exist and be linked before production deployment.

**Why this separation matters:** A design document is revised as the system evolves. A runbook embedded in a design document becomes incorrect every time the design changes. Operators under incident conditions cannot afford to discover that the section reference they were given no longer exists.

---

## Unresolved Decisions

Five decisions require named humans before the system can launch. Each has a fallback. The fallbacks keep the system operational; they are not optimal product choices.

The authority to select the fallback is held by the named owner in each row. Engineering does not have unilateral authority to make product behavior decisions. Engineering does have authority to block deployment if a decision is not made by the deadline in Section 7.1. If the named owner makes no selection by that deadline, the fallback is deployed — because silence is itself a choice that the named owner owns.

| # | Decision | Fallback | Authority |
|---|---|---|---|
| 1 | Burst allowance (Section 1.1) | 3 notifications above ceiling per 5-minute window | Product owner (Section 7.1) |
| 2 | Daily spam threshold (Section 1.1) | Hard cap of 200 notifications/user/day, automatic suppression | Product owner (Section 7.1) |
| 3 | Fanout cap option (Section 1.1) | Option A — accept consistency gap | Product owner (Section 7.1) |
| 4 | Cross-channel deduplication retention window (Section 2.2) | 24 hours | Product owner (Section 7.1) |
| 5 | SMS opt-out compliance owner (Section 5.4) | SMS channel disabled at launch | Legal/compliance owner (Section 7.1) |

**Infrastructure sizing dependency chain:** Two decisions affect provisioning in sequence. First, the deduplication retention window (decision 4) determines Redis key volume. Second, FCM rate verification (Section 1.4) determines which Redis sizing branch applies. If FCM verification is not complete before launch, Branch B sizing (Section 6.1) is the default. Branch B remains in force until the explicit migration trigger in Section 6.1 is met.

**FCM/APNs rate limit caveat:** Rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are estimates until the verification procedure there is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

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

**The staffing constraint is a design input, not a caveat.** Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. That arithmetic is not circular: it starts from a fixed budget of engineer-weeks, subtracts non-feature work (testing, on-call, code review, deployment), and derives the maximum number of deployments that can be built and safely operated within the remaining capacity. The architectural decisions follow from that bound; the bound does not follow from the decisions.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. Token bucket parameters — refill rates, bucket sizes, and the conditions under which P2/P3 can still be deferred despite the token bucket — are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that bound is in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches (A and B) with stated capacity bounds, depending on the FCM rate verification outcome in Section 1.4. The FCM uncertainty range and its effect on branch selection are quantified in Section 1.4.

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

**Revised methodology:** Divide daily volume by active hours — hours in which send rate exceeds 10% of the hourly average. This document uses 14 active hours as the conservative (higher-peak) planning estimate.

**Limitation:** 14 active hours is itself an assumption from general social-app patterns, not a measured value for this application. If actual active hours are 16–18, computed peak rates are 14–22% lower than stated. That direction is acceptable for capacity planning — the system would be sized conservatively — but the magnitude is unknown until month-1 data is available. All peak rate figures carry **±25% uncertainty** until month-1 recalibration.

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

The extreme row's peak rate (~9,643/sec) is approximately 4.9× the plan row's (~1,964/sec) while daily volume is only 3.6× higher. Both daily volume and the peak multiplier are higher in the extreme row, and the multiplier compounds against the higher base. This is expected behavior of the methodology, not an error.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.0× | ~595/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **2.2×** | **~1,964/sec** |
| High engagement | 50% | 5M | 20 | 100M | 2.5× | ~4,960/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 3.0× | ~9,643/sec |

*All peak rates use the 14-active-hours formula. All figures carry ±25% uncertainty until month-1 recalibration.*

**Planning decision:** Size for 45M/day (~1,964/sec sustained peak). The traffic response matrix in Section 1.3 covers the full range from plan through 162M/day with explicit infrastructure states at each threshold. There is no gap between the 80M/day threshold and the 162M/day extreme.

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day stresses per-user queue partitioning, Redis key distribution, and daily spam controls. These are two distinct problems requiring two distinct decisions.

**Problem 1 — Burst allowance:** The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. **Fallback if no decision before launch: 3.** Authority and deadline: Section 7.1.

**Problem 2 — Daily spam threshold:** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below the 480/day extrapolation of that ceiling). The operational risk of no cap is not zero: in a 10M MAU system at 30% DAU, even 0.1% of active users generating 500 notifications/day would add 1.5M unexpected notifications/day — a 3.3% volume increase that is unbudgeted and uncontrolled.

**SMS cost exposure from uncapped volume:** At 2% SMS share and $0.01/message, 1.5M additional notifications/day adds $15,000/day in unbudgeted SMS cost. At 5% SMS share, that exposure reaches $75,000/day. The full cost projection table is in Section 1.2.

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). **Fallback if no decision before launch: hard cap of 200 notifications/user/day with automatic suppression above that threshold.** The product owner named in Section 7.1 owns the fallback outcome if no selection is made by the deadline specified there.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. The worst-case fanout completion time under sustained P0/P1 congestion is derived from the token bucket parameters in Section 3.2:

```
P2 minimum guaranteed rate (Section 3.2): 200 tokens/sec
Recipients beyond 10,000 cap: up to 90,000 (for a 100,000-recipient event)
Minimum completion time at guaranteed rate: 90,000 / 200 = 450 seconds ≈ 7.5 minutes
Rounded up for queue overhead and batch processing latency: ~10 minutes worst case
```

Under sustained P0/P1 saturation, P2 receives only its guaranteed minimum. At 200/sec, 90,000 remaining recipients complete in approximately 10 minutes. If P2's guaranteed minimum is lowered below 200/sec, this bound increases proportionally.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Select one option before launch. **Fallback if no decision: Option A.**

- **Option A — Accept the consistency gap.** The fanout window (5-minute target, ~10-minute worst-case under sustained congestion) is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering work required; frontend work needed.
- **Option C — Set a higher cap.** Product sets the cap. Engineering reviews queue saturation risk; allow one sprint before option is accepted.

Authority and deadline: Section 7.1.

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**If the day-30 review is not documented by day 33:** The backup named in Section 7.1 executes the review procedure without waiting for permission.

**If the backup is also unavailable by day 34:** The procedure defaults to the escalation path in Section 7.2. Section 7.2 specifies how to identify the responsible engineer from the on-call schedule, where that schedule is maintained, and what to do if the schedule is inaccessible. The escalation path does not depend on this document being accurate about org structure; it depends on the on-call schedule being accurate. The on-call schedule is the authoritative source; this document only points to it.

---

### 1.2 Channel Split and Volume Accounting

**Assumptions:**

- Push is the primary channel. Most social app notifications are push-first because it requires no additional user action after install.
- In-app is generated for every notification delivered to an active session, regardless of channel. It is not a separate routing decision; it is a side effect of session state.
- Email is reserved for digest and account-critical notifications. Real-time social notifications are not emailed by default.
- SMS is opt-in only and used for account security events (login, password reset, 2FA).

**Channel split at 45M/day (plan scenario):**

| Channel | Share | Volume/day | Volume/sec (peak, corrected) |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M | ~1,375/sec |
| In-app | 20% | 9M | ~393/sec |
| Email | 8% | 3.6M | ~157/sec |
| SMS | 2% | 900K | ~39/sec |
| **Total** | **100%** | **45M** | **~1,964/sec** |

*Per-channel peak rates derived using the corrected active-hours formula from Section 1.1. All figures carry ±25% uncertainty until month-1 recalibration.*

**Accounting note — in-app:** In-app volume is counted separately because it generates distinct database writes (unread badge count, notification feed row). It does not consume push quota but does consume write throughput. The 9M/day figure is a ceiling; users without active sessions do not generate in-app writes.

**SMS cost projections across all traffic scenarios:**

SMS cost exposure scales with both traffic volume and SMS share. The table below projects daily and annual SMS cost at list price (~$0.01/message) across all four sensitivity scenarios, at both the baseline 2% share and a 5% share if SMS adoption grows.

| Scenario | Total/day | SMS at 2% | Daily cost (2%) | Annual cost (2%) | Daily cost (5%) | Annual cost (5%) |
|---|---|---|---|---|---|---|
| Low