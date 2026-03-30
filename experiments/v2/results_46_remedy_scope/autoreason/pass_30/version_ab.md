# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**

- Queue backup or worker failure → **Section 4.3** (self-contained; no cross-references required)
- Traffic spike response → **Section 1.3** (all four rows present; CLI commands and deployment names embedded)
- Redis failover → **Section 6.2** (covers in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback embedded in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down needed → **Section 1.3b** (self-contained; no external repository dependency)
- Traffic above 80M/day → **Section 1.3**, rows 3 and 4; operator authority explicitly granted, no escalation required before acting
- Escalation at day 34 with no available lead → **Section 7.2**

**What this document does not guarantee:**

FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are estimates until the verification procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

The Redis provisioning decision (Section 6.1) depends on two prior decisions in order: (1) the cross-channel deduplication retention window (Section 2.2), then (2) the FCM rate verification outcome (Section 1.4). If FCM rate verification is not complete before launch, use Branch B sizing as the fallback. Branch B remains in force until the explicit migration trigger in Section 6.1 is met.

**Unresolved product decisions:**

Five decisions require named humans before the system can launch. Each has a fallback. The fallbacks keep the system operational; they are not optimal product choices.

1. Burst allowance (Section 1.1) — fallback: 3 notifications above ceiling per 5-minute window
2. Daily spam threshold (Section 1.1) — fallback: hard cap of 200 notifications/user/day with automatic suppression
3. Fanout cap option (Section 1.1) — fallback: Option A (accept consistency gap)
4. Cross-channel deduplication retention window (Section 2.2) — fallback: 24 hours
5. SMS opt-out compliance owner (Section 5.4) — fallback: SMS channel disabled at launch; volume redistribution specified in Section 5.4

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

**The staffing constraint is a design input, not a caveat.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. Every simplification in this document names the staffing constraint as its reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The parameters and the conditions under which P2/P3 can still be deferred despite the token bucket are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that bound is in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The full arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches depending on the FCM rate verification outcome in Section 1.4. If verification is not complete before launch, Branch B is the default. The trigger for migrating from Branch B to Branch A post-launch is in Section 6.1.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The sensitivity table uses joint scenarios: the low row uses both a low ratio and a low rate; the extreme row uses both high values. Treating them as independent understates high-engagement risk.

---

**Peak multiplier methodology:**

The prior approach of dividing total daily volume by 24 hours underestimates actual peak rates. A 24-hour denominator includes overnight hours with near-zero traffic, which suppresses the computed average and makes multiplied results appear lower than actual peaks.

**Corrected methodology:** Divide daily volume by the number of active hours, defined as hours in which send rate exceeds 10% of the hourly average. For a social app this is typically 14–16 hours. This document uses 14 active hours as the conservative (higher-peak) estimate.

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

**Note on multiplier values:** Because the denominator is now active hours rather than 24 hours, the multipliers are smaller (2.0–3.0 rather than 2.5–4.0 in a naive 24-hour calculation). The resulting peak rates are higher for equivalent scenarios. This is correct — the 24-hour method was underestimating. Multipliers still increase with engagement level because more real-time interaction compresses activity into shorter windows.

The extreme row's peak rate (~9,643/sec) is approximately 4.9× the plan row's (~1,964/sec) while daily volume is only 3.6× higher. This superlinear scaling is expected: both daily volume and the multiplier are higher in the extreme row. It is a consequence of the methodology, not an error.

**Calibration note:** Active-hours count and multipliers are stated assumptions from general social-app patterns, not measured values. Recalibrate at the month-1 checkpoint using actual traffic data. The month-1 review procedure is in Section 7.1.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.0× | ~595/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **2.2×** | **~1,964/sec** |
| High engagement | 50% | 5M | 20 | 100M | 2.5× | ~4,960/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 3.0× | ~9,643/sec |

*Peak rate uses the corrected active-hours formula. Multipliers are assumptions; recalibrate at month-1.*

**Planning decision:** Size for 45M/day (~1,964/sec sustained peak). The traffic response matrix in Section 1.3 covers the full range from plan through 162M/day. There is no gap between the 80M/day threshold and the 162M/day extreme.

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day stresses per-user queue partitioning, Redis key distribution, and daily spam controls. These are two distinct problems requiring two distinct decisions.

**Problem 1 — Burst allowance:** The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. **Fallback if no decision before launch: 3.** Owner and deadline: Section 7.1.

**Problem 2 — Daily spam threshold:** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below the 480/day extrapolation of that ceiling). The operational risk of no cap is not zero: in a 10M MAU system at 30% DAU, even 0.1% of active users generating 500 notifications/day would add 1.5M unexpected notifications/day — a 3.3% volume increase that is unbudgeted and uncontrolled. At 5% of daily volume at extreme traffic (162M/day), SMS cost exposure alone exceeds $81,000/day (see Section 1.2 for full projections across all traffic scenarios).

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). **Fallback if no decision before launch: engineering enforces a hard cap of 200 notifications/user/day with automatic suppression above that threshold.** Engineering has unilateral authority to enforce this fallback without a product decision. The trigger for unilateral enforcement is any 24-hour period in which more than 0.05% of DAU (150 users at plan DAU) exceed 100 notifications/day — this threshold is observable from existing metrics without additional instrumentation. Owner and deadline: Section 7.1.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. This creates a consistency gap: during the fanout window, some followers have received the notification and others have not. The worst-case fanout completion time under sustained P0/P1 congestion is approximately 45 minutes for a 100,000-recipient event. That bound is derived from token bucket parameters in Section 3.2, not asserted here.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Select one option before launch. **Fallback if no decision: Option A.**

- **Option A — Accept the consistency gap.** The fanout window (5-minute target, ~45-minute worst-case under congestion) is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering work required; frontend work needed.
- **Option C — Set a higher cap.** Product sets the cap. Engineering reviews queue saturation risk; allow one sprint before option is accepted.

Owner and deadline: Section 7.1.

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**Escalation chain:** The backup named in Section 7.1 monitors whether the day-30 review has been documented. If no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 review procedure without waiting for permission. If the backup is also unavailable by day 34, the fallback is in Section 7.2, which names the senior engineer on the current on-call rotation by role, not by name, so it does not require an org chart lookup. The on-call schedule location is specified in Section 7.2. That engineer has explicit authority to execute the month-1 procedure and to make interim decisions on any open product question using the stated fallback values.

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

*Per-channel peak rates derived using the corrected active-hours formula from Section 1.1.*

**Accounting note — in-app:** In-app volume is counted separately because it generates distinct database writes (unread badge count, notification feed row). It does not consume push quota but does consume write throughput. The 9M/day in-app figure is a ceiling; users without active sessions do not generate in-app writes.

**SMS cost projections across all traffic scenarios:**

SMS cost exposure scales with both traffic volume and the SMS share of that volume. The table below projects daily and annual SMS cost at list price (~$0.01/message) across all four sensitivity scenarios, at both the baseline 2% share and a 5% share if SMS adoption grows.

| Scenario | Total/day | SMS at 2% | Daily cost (2%) | Annual cost (2%) | Daily cost (5%) | Annual cost (5%) |
|---|---|---|---|---|---|---|
| Low engagement | 15M | 300K | $3,000 | $1.1M | $7,500 | $2.7M |
| **Plan** | **45M** | **900K** | **$9,000** | **$3.3M** | **$22,500**