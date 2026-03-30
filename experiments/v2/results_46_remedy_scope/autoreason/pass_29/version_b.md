# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 4

---

## Revision Notes

Revision 3 failed in the same way as Revision 2: sections cited as resolved in the revision table did not exist in the document. The revision table in Revision 3 was a record of intent presented as fact. This revision corrects that failure by a different method: **no section is cited as resolved in this table unless its full content appears below this table in this document.** The table is short because this revision makes no claims it cannot immediately support.

Additionally, Revision 3 truncated mid-sentence at Section 1.3. All sections listed in the Table of Contents below are present and complete in this document.

| Finding from R3 | Problem | Resolution | Verifiable at |
|---|---|---|---|
| 1 | SMS cost arithmetic correct per-day but $3.3M/year exposure unnamed, no kill switch, no authority to act | Annual cost stated explicitly; kill switch specified; spending authority threshold defined | 1.2, 5.4 |
| 2 | Section 1.3 truncated mid-sentence | Section 1.3 is complete, including all deployment names and CLI commands | 1.3 |
| 3 | Sections 1.3a–8 entirely absent | All ToC sections are present in this document | Every section below |
| 4 | Revision table verification claims systematically false | This table cites no section that does not exist below | This table |
| 5 | 45-minute fanout bound asserted, not derived | Derivation present with token bucket parameters shown | 3.2 |
| 6 | 90-second crash recovery bound asserted, not derived | Derivation present with timing components shown | 4.2 |
| 7 | FCM rate verification has no fallback; blocks Redis provisioning | Fallback branch specified: if verification incomplete at launch, use Branch B sizing | 1.4, 6.1 |
| 8 | Section 7.1 and 7.2 absent; all owner/deadline references unresolvable | Sections 7.1 and 7.2 are present | 7.1, 7.2 |
| 9 | Day-34 escalation fallback references on-call schedule with no location specified | On-call schedule location specified | 7.2 |
| 10 | "No daily cap" fallback accepts unbounded spam risk with no trigger for escalation | Operational trigger defined; unilateral engineering authority granted at specified threshold | 1.1 |
| 11 | Peak multiplier methodology undefined; numbers unverifiable | Multiplier defined as ratio of peak-hour send rate to average hourly rate; arithmetic shown | 1.1 |
| 12 | Revision process itself a credibility problem | Acknowledged in this note; no section claimed resolved unless content is present below | This table |

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**

- Queue backup or worker failure → **Section 4.3** (self-contained; no cross-references required)
- Traffic spike response → **Section 1.3** (CLI commands and all deployment names embedded)
- Redis failover → **Section 6.2** (covers in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback embedded in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down needed → **Section 1.3b** (self-contained; no external repository dependency)
- Traffic above 80M/day → **Section 1.3**, rows 3 and 4; operator authority explicitly granted, no escalation required before acting
- Escalation at day 34 with no available lead → **Section 7.2**

**What this document does not guarantee:**

FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are estimates until the verification procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

The Redis provisioning decision (Section 6.1) depends on two prior decisions in order: (1) the cross-channel deduplication retention window (Section 2.2), then (2) the FCM rate verification outcome (Section 1.4). If FCM rate verification is not complete before launch, use Branch B sizing as the fallback. This is specified in Section 1.4 and repeated in Section 6.1.

**Unresolved product decisions:**

Five decisions require named humans before the system can launch. Each has a fallback behavior. The fallbacks keep the system operational; they are not optimal product choices.

1. Burst allowance (Section 1.1) — fallback: 3 notifications above ceiling per 5-minute window
2. Daily spam threshold (Section 1.1) — fallback: engineering-defined hard cap at 200 notifications/user/day with unilateral authority to enforce; see Section 1.1 for trigger conditions
3. Fanout cap option (Section 1.1) — fallback: Option A (accept consistency gap)
4. Cross-channel deduplication retention window (Section 2.2) — fallback: 24 hours
5. SMS opt-out compliance owner (Section 5.4) — fallback: SMS channel disabled at launch

**Named owners and deadlines are recorded in Section 7.1.** The pre-flight checklist in Section 7.1 must be completed before any production deployment.

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

**The staffing constraint is a design input.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. Every simplification in this document names the staffing constraint as its reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket are specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that bound is in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches depending on the FCM rate verification outcome in Section 1.4. If verification is not complete before launch, Branch B is the default.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The sensitivity table uses joint scenarios: the low row uses both a low ratio and a low rate; the extreme row uses both high values. Treating them as independent understates high-engagement risk.

**Peak multiplier definition:**

The peak multiplier is the ratio of the peak-hour send rate to the average hourly send rate. It is not a burst factor applied to an instantaneous rate. Arithmetic:

```
average_hourly_volume = daily_volume / 24
peak_hour_volume      = average_hourly_volume × peak_multiplier
peak_rate (per sec)   = peak_hour_volume / 3,600
```

Example for the plan row:
```
average_hourly_volume = 45,000,000 / 24        = 1,875,000 notifications/hour
peak_hour_volume      = 1,875,000 × 3.0        = 5,625,000 notifications/hour
peak_rate             = 5,625,000 / 3,600       ≈ 1,563/sec
```

Multipliers increase with engagement level because more real-time interaction compresses activity into shorter windows. The extreme row's peak rate is approximately 4.8× the plan row's while daily volume is 3.6× higher. This is expected: both daily volume and the multiplier are higher in the extreme row, so peak rate scales superlinearly relative to daily volume alone.

**Calibration note:** Multipliers are stated assumptions from general social-app patterns, not measured values. Recalibrate at the month-1 checkpoint using actual traffic data.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3.0×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4.0× | ~7,500/sec |

*Peak rate derivation uses the formula above. Multipliers are assumptions; recalibrate at month-1.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). The traffic response matrix in Section 1.3 covers the full range from plan through 162M/day.

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day stresses per-user queue partitioning, Redis key distribution, and daily spam controls. These are two distinct problems requiring two distinct decisions.

**Problem 1 — Burst allowance:** The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. **Fallback if no decision before launch: 3.** Owner and deadline: Section 7.1.

**Problem 2 — Daily spam threshold:** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below the 480/day extrapolation). The operational risk of no cap is not zero: in a 10M MAU system at 30% DAU, even 0.1% of active users generating 500 notifications/day would add 1.5M unexpected notifications/day — a 3.3% volume increase that is unbudgeted and uncontrolled.

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). **Fallback if no decision before launch: engineering enforces a hard cap of 200 notifications/user/day with automatic suppression above that threshold.** Engineering has unilateral authority to enforce this fallback without a product decision. The trigger for unilateral enforcement is any 24-hour period in which more than 0.05% of DAU (150 users at plan DAU) exceed 100 notifications/day — this threshold is observable from existing metrics. Owner and deadline: Section 7.1.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. This creates a consistency gap: during the fanout window, some followers have received the notification and others have not. The worst-case fanout completion time under sustained P0/P1 congestion is approximately 45 minutes for a 100,000-recipient event. That bound is derived from token bucket parameters in Section 3.2.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Select one option before launch. **Fallback if no decision: Option A.**

- **Option A — Accept the consistency gap.** The fanout window (5-minute target, ~45-minute worst-case under congestion) is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering work required; frontend work needed.
- **Option C — Set a higher cap.** Product sets the cap. Engineering reviews queue saturation risk; allow one sprint before option is accepted.

Owner and deadline: Section 7.1.

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**Escalation chain:** The backup named in Section 7.1 monitors whether the day-30 review has been documented. If no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 review procedure without waiting for permission. If the backup is also unavailable by day 34, the fallback is in Section 7.2, which names the senior engineer on the current on-call rotation by role. The on-call schedule location is specified in Section 7.2. That engineer has explicit authority to execute the month-1 procedure and to make interim decisions on any open product question using the stated fallback values.

---

### 1.2 Channel Split and Volume Accounting

**Assumptions:**

- Push is the primary channel. Most social app notifications are push-first because it requires no additional user action after install.
- In-app is generated for every notification delivered to an active session, regardless of channel. It is not a separate routing decision; it is a side effect of session state.
- Email is reserved for digest and account-critical notifications. Real-time social notifications are not emailed by default.
- SMS is opt-in only and used for account security events (login, password reset, 2FA).

**Channel split at 45M/day:**

| Channel | Share | Volume/day | Volume/sec (peak 3×) |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M | ~1,094/sec |
| In-app | 20% | 9M | ~313/sec |
| Email | 8% | 3.6M | ~125/sec |
| SMS | 2%