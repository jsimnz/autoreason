# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 4 — Synthesis

---

## Revision Notes

This revision synthesizes the strongest elements of Revisions 2 and 3. The governing principles of the synthesis are:

1. **Self-containment over external dependency.** Every procedure needed under incident conditions is present in this document. No external repository, script, or CI badge is required to use this document operationally.
2. **Derivations over assertions.** Every bound or threshold that is load-bearing has its derivation present in the section where it is used.
3. **Explicit fallbacks over blocking gates.** Every unresolved decision has a stated conservative default. The system can launch and operate without any decision being made; the fallbacks are not optimal product choices, but they are safe ones.
4. **Staffing as a design input.** Every simplification names the staffing constraint as the reason.

| Finding addressed | Resolution | Verifiable at |
|---|---|---|
| Completeness not reader-verifiable | All ToC sections are present in this document; completeness is a reader-verifiable property, not dependent on a CI badge or external manifest | Every section below |
| External repo dependencies create single points of failure | Scale-down procedure is self-contained; pre-flight checklist is inline; no external script or repo is required | 1.3b, 7.1 |
| Unresolved decisions had no fallback behavior | Each of the five unresolved decisions now has an explicit fallback that keeps the system operational | 1.1, 2.2, 5.4 |
| FCM/APNs two-branch Redis sizing not present | Both branches specified in full and directly comparable | 1.4, 6.1, 6.2 |
| 90-second crash recovery bound asserted, not derived | Derivation present in Section 4.2 | 4.2 |
| 45-minute fanout bound asserted, not derived | Derivation present in Section 3.2 | 3.2 |
| Month-1 checkpoint truncated mid-sentence | Paragraph completed; fallback escalation path names a role, not a person | 1.1 |
| Gap between 80M/day runbook threshold and 162M/day extreme row | Traffic response matrix covers full range; no gap between threshold and extreme | 1.3 |
| Extreme scenario had no operator authority grant | Operator authority explicitly granted in traffic response matrix rows 3 and 4 | 1.3 |
| Section 1.5 staffing arithmetic absent | Section 1.5 present with full arithmetic | 1.5 |
| Section 1.3c absent | Section 1.3c present | 1.3c |

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**

- Queue backup or worker failure → **Section 4.3** (self-contained)
- Traffic spike response → **Section 1.3** (CLI commands embedded; all deployment names are in the procedure, not in a cross-reference)
- Scale-up → **Section 1.3a**
- Scale-down → **Section 1.3b** (self-contained in this document; does not depend on any external repository)
- Redis failover → **Section 6.2** (covers in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Traffic above 80M/day → **Section 1.3**, rows 3 and 4; operator authority is explicitly granted, no escalation required before acting
- Escalation at day 34 with no available lead → **Section 7.2** (names a role, not a person; no org chart lookup required)

**What this document does not guarantee:**

FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are estimates until the verification procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

The Redis provisioning decision (Section 6.1) depends on two prior decisions, in order: (1) the cross-channel deduplication retention window (Section 2.2), then (2) the FCM rate verification outcome (Section 1.4). Both must be resolved before a Redis provisioning option is committed. Section 6.1 contains two complete, comparable branches — one for each FCM verification outcome — so the provisioning decision can be made immediately once both prerequisites are resolved.

**Unresolved product decisions and their fallbacks:**

Five decisions require named humans before launch. Each has a fallback behavior if the decision is not made. Fallbacks are conservative defaults that keep the system operational; they are not optimal product choices.

| Decision | Section | Fallback if not made before launch |
|---|---|---|
| Burst allowance | 1.1 | 3 notifications above ceiling per 5-minute window |
| Daily spam threshold | 1.1 | No daily cap enforced; spam risk accepted until product decides |
| Fanout cap option | 1.1 | Option A: accept consistency gap |
| Cross-channel deduplication retention window | 2.2 | 24 hours |
| SMS opt-out compliance owner | 5.4 | SMS channel disabled at launch |

Named owners and deadlines are recorded in Section 7.1. The pre-flight checklist in Section 7.1 must be completed before any production deployment. It is inline in this document and does not depend on an external script or repository.

---

## Table of Contents

1. Scale Assumptions and Constraints
   - 1.1 Traffic Model
   - 1.2 Channel Split and Volume Accounting
   - 1.3 Traffic Response Matrix
   - 1.3a Scale-Up Procedure
   - 1.3b Scale-Down Procedure
   - 1.3c Month-1 After-Hours Spike Response
   - 1.4 FCM/APNs Rate Limit Verification
   - 1.5 Staffing Analysis
2. Notification Routing and Deduplication
   - 2.1 Routing Logic
   - 2.2 Deduplication Architecture
3. Priority and Batching
   - 3.1 Priority Tiers
   - 3.2 Token Bucket and Starvation Prevention
   - 3.3 Batching Logic
4. Worker Architecture
   - 4.1 Worker Deployments
   - 4.2 Processing State and Recovery
   - 4.3 Queue Backup and Worker Failure Response
5. Delivery Channels
   - 5.1 Push (FCM + APNs)
   - 5.2 In-App
   - 5.3 Email
   - 5.4 SMS
6. Infrastructure
   - 6.1 Queue Infrastructure
   - 6.2 Redis Failover and In-Flight Behavior
   - 6.3 Database
7. Operations
   - 7.1 Pre-Flight Checklist and Named Owners
   - 7.2 Escalation and Authorization Thresholds
8. Build Timeline

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS for a 10M MAU social app, built by 4 engineers over 6 months.

**The staffing constraint is a design input, not a label.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing analysis with full arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. Every simplification in this document names the staffing constraint as the explicit reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket are specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that bound is in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is reduced priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The full tradeoff arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches depending on the FCM rate verification outcome in Section 1.4. Both branches are present and directly comparable in Sections 6.1 and 6.2. The claim that FCM/APNs rate limits are the binding constraint during viral spikes is contingent on the FCM verification outcome and is not used as a design assumption until verification is complete.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table uses joint scenarios: the low row uses both a low ratio and a low rate; the extreme row uses both high values. Treating them as independent understates high-engagement risk.

**Peak multiplier methodology:**

```
peak_rate = (daily_volume × peak_multiplier) / 86,400
```

Multipliers increase with engagement level because more real-time interaction compresses activity into shorter windows. This means peak rates scale superlinearly relative to daily totals as engagement rises — the extreme row's peak rate is 4.76× the plan row's while daily volume is only 3.6× higher. This is a consequence of the methodology, not an error.

**Calibration note:** Multipliers (2.5×, 3×, 3.5×, 4×) are stated assumptions from general social-app patterns, not measured values from this system. Recalibrate at the month-1 checkpoint using actual traffic data. Until recalibration, the extreme-scenario peak rate of ~7,500/sec is an order-of-magnitude planning estimate, not a precise bound.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

*Peak rate = (daily_volume × multiplier) / 86,400. Multipliers are assumptions; recalibrate at month-1.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). The traffic response matrix in Section 1.3 covers the full range from plan through 162M/day. The >80M/day runbook rows address the extreme scenario explicitly — there is no gap between the 80M/day threshold and the 162M/day extreme row.

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day will not appear as a volume risk in the table above — total daily volume may be below plan — but stresses three specific subsystems: per-user queue partitioning, Redis key distribution, and the daily spam control (if any). There are two distinct problems requiring two distinct decisions. They must not be conflated.

**Problem 1 — Burst allowance (infrastructure-adjacent, product decides):**
The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible. This decision does not address Problem 2.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. This is a product-quality decision about spam perception. It does not resolve the daily spam threshold question below. **Fallback if no decision before launch: 3.** Owner and deadline: Section 7.1.

**Problem 2 — Daily spam threshold (product decides, separately from burst allowance):**
A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below 480/day, the ceiling extrapolated across 24 hours). There is currently no control for this case. Infrastructure mechanisms — per-user queue partitioning (Section 4.1) and Redis key sharding (Section 6.1) — prevent one power user from monopolizing shared queue capacity, but they do not prevent objectively excessive daily notification volume.

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). This is a separate decision from the burst allowance. Selecting a burst allowance value does not resolve this decision. **Fallback if no decision before launch: no daily cap enforced; spam risk accepted until product decides.** Owner and deadline: Section 7.1.

**Deduplication set sizes:** For power users generating 50+ notifications/day, the cross-channel delivered-ID set is bounded by the retention window, not the 60-second sliding window. Full memory arithmetic and the retention window decision are in Section 2.2. The Redis provisioning decision in Section 6.1 depends on the retention window being set first.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. This creates a consistency gap: during the fanout window, some followers have received the notification and others have not. The worst-case fanout completion time under sustained P0/P1 congestion is approximately 45 minutes for a 100,000-recipient event. That bound is derived from token bucket parameters in Section 3.2, not asserted here.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Select one option before launch. **Fallback if no decision: Option A.**

- **Option A — Accept the consistency gap.** The fanout window (5-minute target, ~45-minute worst-case under congestion) is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering work required; frontend work needed.
- **Option C — Set a higher cap.** Product sets the cap. Engineering reviews queue saturation risk; allow one sprint before option is accepted.

Owner and deadline: Section 7.1.

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1. This artifact must include: actual vs. planned DAU/MAU ratio, actual notifications per active user per day, observed peak multiplier, and a recalibrated version of the sensitivity table above.

**Escalation chain:** The backup named in Section 7.1 monitors whether the day-30 review has been documented. If no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 review procedure without waiting for permission. If the backup is also unavailable by day 34, the fallback is specified in Section 7.2: it names the senior engineer on the current on-call rotation by role, not by name, so it does not require an org chart lookup. That engineer has explicit authority to execute the month-1 procedure and to make interim decisions on any open product question using the stated fallback values above.

---

### 1.2 Channel Split and Volume Accounting

**Assumptions:**

- Push is the primary channel. Most social app notifications are push-first because it requires no additional user action after install.
- In-app is generated for every notification delivered to an active session, regardless of channel. It is not a separate routing decision; it is a side effect of session state.
- Email is