# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: What This Document Is and Is Not

This is a **design document**. It records architectural decisions, their rationale, and the tradeoffs made under staffing and time constraints.

This document is **not an operational runbook**. Incident response procedures, escalation chains, and operator CLI references belong in a separate runbook that is version-controlled independently of this design. The runbook owner, deadline, and fallback are specified in Section 7.1.

---

## On Fallback Authority

Several decisions in this document have fallbacks. The fallbacks are engineering-specified values. This requires explanation, because the document also states that engineering does not have unilateral authority over product behavior decisions.

The resolution is this: **a fallback is not a product decision. It is an engineering constraint imposed by deployment dependencies.**

When a product owner does not make a decision by a named deadline, the system must deploy in some configuration. Engineering selects that configuration based on one criterion: which value causes the least irreversible harm while the product owner catches up. The fallback is not "what engineering would choose if it were making the product decision." It is "what allows the system to launch without locking in a choice that is expensive to reverse."

This means fallback values are selected for reversibility and conservatism, not for product optimality. The burst allowance fallback of 3 is the lower bound of the recommended range — conservative, easy to raise. The daily cap fallback of 200 is restrictive — it will suppress some legitimate notifications, but suppression is reversible; spam damage to user retention is not. The deduplication window fallback of 24 hours is shorter than the engineering recommendation of 48 hours — it costs more in duplicate notification risk but less in Redis capacity, and the window can be extended in a configuration change without a deployment.

**What the product owner owns when they miss a deadline:** They own the product outcome of the fallback. They do not own the fallback selection itself — engineering owns that, transparently, on the stated criteria. If the product owner disagrees with a fallback value before the deadline, they make a decision. If they disagree after the deadline, they request a configuration change and engineering processes it in the next release cycle.

This is not a governance fiction. It is an explicit acknowledgment that deployment deadlines create forcing functions, that forcing functions produce defaults, and that defaults have owners. Engineering owns the fallback selection. Product owners own the consequences of not deciding.

---

## Unresolved Decisions

Six decisions require named humans before the system can launch.

| # | Decision | Fallback | Authority |
|---|---|---|---|
| 1 | Burst allowance (Section 1.1) | 3 notifications above ceiling per 5-minute window | Product owner (Section 7.1) |
| 2 | Daily spam threshold (Section 1.1) | Hard cap of 200 notifications/user/day, automatic suppression | Product owner (Section 7.1) — SMS budget owner must co-sign per Section 1.2 |
| 3 | Fanout cap option (Section 1.1) | Option A — accept consistency gap | Product owner (Section 7.1) |
| 4 | Cross-channel deduplication retention window (Section 2.2) | 24 hours | Product owner (Section 7.1) — see correctness note below |
| 5 | SMS opt-out compliance owner (Section 5.4) | SMS channel disabled at launch | Legal/compliance owner (Section 7.1) |
| 6 | Runbook authorship (Section 7.1) | Pre-flight runbook gate fails; on-call rotation owner makes written go/no-go decision | On-call rotation owner (Section 7.1) |

**Decision 2 — SMS cost co-sign requirement:** The daily spam threshold directly controls SMS cost exposure quantified in Section 1.2 (up to $75,000/day at 5% SMS share with uncapped power-user volume). Decision 2 therefore requires two signatures: the product owner and the person with budget authority over SMS costs. Section 7.1 names both people. If they are the same person, one signature suffices. If they disagree, the more restrictive threshold applies until the disagreement is resolved in writing. If the SMS budget owner role does not exist or is not filled before the deadline, Decision 2 falls back to the 200/day cap — the conservative choice — and the product owner is notified that the SMS budget review did not occur. Engineering does not resolve organizational gaps; it deploys the conservative fallback and documents why.

**Decision 4 — Deduplication window correctness note:** The 24-hour fallback has a product correctness consequence. If a user receives a push notification and opens the app more than 24 hours later, the deduplication key has expired and the system will generate a duplicate in-app notification for an event the user already received via push.

Whether this is acceptable depends on a question engineering can answer without product input: **is the notification feed deduplicated at read time by event ID?** Engineering must answer this before framing it as a product decision. If the feed deduplicates at read time, the infrastructure window is irrelevant and the 24-hour fallback is acceptable. If the feed is append-only, duplicates are visible to users and the 48-hour window is strongly preferred. Engineering's answer to this question must be recorded in Section 7.1 before the pre-flight checklist closes. If engineering cannot determine the feed architecture before the deadline — because the feed is owned by a separate team, or because it has not been built yet — then the question becomes a product owner decision with the consequence stated above.

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

**The staffing constraint is a design input, not a caveat.** Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. That arithmetic is present in this document; the conclusion that 6 is the correct number under these constraints is verifiable there.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. Token bucket parameters — refill rates, bucket sizes, and deferral conditions — are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that window is in Section 4.2. Worst-case delivery outcome under crash recovery is duplication, not loss. This holds for crash recovery and for the Redis failover scenario in Section 6.2 under the conditions specified there. There is one failure mode — a Redis primary failure during the replication promotion window — where in-flight entries can be lost rather than duplicated. Section 6.2 specifies the conditions under which this occurs, the estimated probability given stated replication lag bounds, and the recovery procedure.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is reduced priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches (A and B) depending on the FCM rate verification outcome in Section 1.4.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The sensitivity table uses joint scenarios for the bounding cases. However, the table also includes two intermediate scenarios that the correlated structure would otherwise obscure: a high-retention app with conservative notification policy, and a moderate-retention app with aggressive re-engagement. These are real operating modes, not edge cases.

---

**Peak multiplier methodology:**

Dividing total daily volume by 24 hours includes overnight hours with near-zero traffic, which suppresses the computed average and causes multiplied results to understate actual peaks.

**Revised methodology:** Divide daily volume by the number of active hours — hours in which send rate exceeds 10% of the hourly average. This document uses 14 active hours as the conservative (higher-peak) planning estimate.

**Limitation:** 14 active hours is an assumption from general social-app patterns, not a measured value for this application. If actual active hours are 16–18, computed peak rates are 14–22% lower than stated. The direction of the correction is acceptable for capacity planning — it means the system is sized conservatively — but the magnitude is unknown until month-1 data is available. All peak rate figures carry ±25% uncertainty until month-1 recalibration.

```
active_hours        = 14
active_hour_avg     = daily_volume / active_hours
peak_hour_volume    = active_hour_avg × peak_multiplier
peak_rate (per sec) = peak_hour_volume / 3,600
```

Example for the plan row:

```
active_hour_avg  = 45,000,000 / 14  = 3,214,286 notifications/hour
peak_hour_volume = 3,214,286 × 2.2  = 7,071,429 notifications/hour
peak_rate        = 7,071,429 / 3,600 ≈ 1,964/sec
```

**Sensitivity table — six scenarios including intermediate cases:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak mult. | Peak rate | Notes |
|---|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.0× | ~595/sec | Correlated low |
| High-retention, conservative notifications | 50% | 5M | 8 | 40M | 2.2× | ~1,746/sec | Decoupled: high DAU, low notif rate |
| **Plan** | **30%** | **3M** | **15** | **45M** | **2.2×** | **~1,964/sec** | Baseline |
| Moderate-retention, aggressive re-engagement | 25% | 2.5M | 30 | 75M | 2.5× | ~3,720/sec | Decoupled: low DAU, high notif rate |
| High engagement | 50% | 5M | 20 | 100M | 2.5× | ~4,960/sec | Correlated high |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 3.0× | ~9,643/sec | Correlated extreme |

*The high-retention/conservative row shows that 40M/day is reachable without aggressive notification policy. The moderate-retention/aggressive row shows that 75M/day is reachable from a smaller user base if re-engagement campaigns run unconstrained. Both are within the traffic response matrix in Section 1.3.*

---

**Power-user pattern:**

A cohort of highly active users generating 50+ notifications/day stresses per-user queue partitioning, Redis key distribution, and daily spam controls.

**Problem 1 — Burst allowance:** The 20/hour sustained ceiling is a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible. Fallback: 3.

**[PRODUCT DECISION REQUIRED — Decision 1]:** Select a value between 3 and 5. Fallback selection rationale: 3 is the lower bound of the recommended range. It is the most conservative choice and the easiest to raise without a deployment. Authority and deadline: Section 7.1.

**Problem 2 — Daily spam threshold:** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below the 480/day extrapolation of that ceiling). The operational risk of no cap: at 30% DAU, even 0.1% of active users generating 500 notifications/day would add 1.5M unexpected notifications/day — a 3.3% volume increase that is unbudgeted and uncontrolled.

**[PRODUCT DECISION REQUIRED — Decision 2]:** Define what daily notification volume is excessive and what action to take (suppress, hold for review, notify sender). Fallback: hard cap of 200 notifications/user/day with automatic suppression. Fallback selection rationale: suppression is reversible; spam damage to user retention is not. The SMS budget co-sign requirement is stated in the Unresolved Decisions table above.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs at P2 priority. The worst-case fanout completion time under sustained P0/P1 congestion is derived from the token bucket parameters in Section 3.2:

```
P2 minimum guaranteed rate (Section 3.2): 200 tokens/sec
Recipients beyond 10,000 cap: up to 90,000 (for a 100,000-recipient event)
Minimum completion time at guaranteed rate: 90,000 / 200 = 450 seconds ≈ 7.5 minutes
With queue overhead and batch processing latency: ~10 minutes worst case
```

The 200 tokens/sec figure is not assumed here — it is derived in Section 3.2. If those parameters change, this bound must be recalculated.

**[PRODUCT DECISION REQUIRED — Decision 3]:** Select one fanout option. Fallback: Option A.

- **Option A — Accept the consistency gap.** The ~10-minute worst-case fanout window under sustained congestion is acceptable. No prior engineering work required.
- **Option B — Accept the gap with UX mitigation.** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering work required; frontend work needed.
- **Option C — Set a higher cap.** Product sets the cap. **Engineering review required before acceptance because a higher cap changes the queue saturation risk profile.** Options A and B do not require review because they operate within the bounds of the already-derived worst-case analysis: Option A accepts the ~10-minute window; Option B accepts it with a UX wrapper. Option C changes the input to that analysis — specifically, the number of recipients that enter the P2 queue per event — and requires rerunning the saturation model in Section 3.2 against the new cap value. One sprint is the estimate for that review; the sprint is not optional.

Authority and deadline: Section 7.1.

---

**Month-1 recalibration procedure:**

The on-call rotation owner reviews month-1 traffic data by day 30. All peak rate figures carry ±25% uncertainty until this procedure completes.

**Step 1 — Pull hourly send volume.** Query the metrics dashboard for the prior 30 days of per-hour notification send volume. Datadog query: `sum:notifications.sent{*} by {hour}`. Export as CSV.

**Step 2