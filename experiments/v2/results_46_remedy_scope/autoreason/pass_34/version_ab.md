# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: What This Document Is and Is Not

This is a **design document**. It records architectural decisions, their rationale, and the tradeoffs made under staffing and time constraints.

This document is **not an operational runbook**. Incident response procedures, escalation chains, and operator CLI references belong in a separate runbook that is version-controlled independently of this design. The runbook owner, deadline, and fallback are specified in Section 7.1.

**Why this separation matters:** A design document is revised as the system evolves. A runbook embedded in a design document becomes incorrect every time the design changes. Operators under incident conditions cannot afford to discover that the section reference they were given no longer exists.

**The staleness problem recurs one level up:** If the runbook references this document for operational parameters — the 90-second recovery window, Redis failover behavior, worker failure behavior — and this document changes, the runbook inherits the staleness. The solution is that the runbook must be self-contained for parameters operators act on during incidents. The design document is the authoritative source for *why* those values were chosen; the runbook is the authoritative source for *what* they currently are. When a design change affects an operational parameter, the runbook update is part of the same change set, not a follow-on task.

---

## On Fallback Authority

Several decisions in this document have fallbacks. The fallbacks are engineering-specified values. This requires explanation, because the document also states that engineering does not have unilateral authority over product behavior decisions.

The resolution is this: **a fallback is not a product decision. It is an engineering constraint imposed by deployment dependencies.**

When a product owner does not make a decision by a named deadline, the system must deploy in some configuration. Engineering selects that configuration based on one criterion: which value causes the least irreversible harm while the product owner catches up. The fallback is not "what engineering would choose if it were making the product decision." It is "what allows the system to launch without locking in a choice that is expensive to reverse."

Fallback values are therefore selected for reversibility and conservatism, not product optimality:

- The burst allowance fallback of 3 is the lower bound of the recommended range — conservative, easy to raise without a deployment.
- The daily cap fallback of 200 is restrictive — it will suppress some legitimate notifications, but suppression is reversible; spam damage to user retention is not.
- The deduplication window fallback of 24 hours costs more in duplicate-notification risk but less in Redis capacity, and the window can be extended via configuration change without a deployment.

**What the product owner owns when they miss a deadline:** They own the product outcome of the fallback. They do not own the fallback selection itself — engineering owns that, transparently, on the stated criteria. If the product owner disagrees with a fallback value before the deadline, they make a decision. If they disagree after the deadline, they request a configuration change and engineering processes it in the next release cycle.

Engineering owns the fallback selection. Product owners own the consequences of not deciding.

---

## Unresolved Decisions

Six decisions require named humans before the system can launch. Each has a fallback. The fallbacks keep the system operational; they are not optimal product choices.

| # | Decision | Fallback | Authority |
|---|---|---|---|
| 1 | Burst allowance (Section 1.1) | 3 notifications above ceiling per 5-minute window | Product owner (Section 7.1) |
| 2 | Daily spam threshold (Section 1.1) | Hard cap of 200 notifications/user/day, automatic suppression | Product owner (Section 7.1) — SMS budget owner must co-sign per Section 1.2 |
| 3 | Fanout cap option (Section 1.1) | Option A — accept consistency gap | Product owner (Section 7.1) |
| 4 | Cross-channel deduplication retention window (Section 2.2) | 24 hours | Product owner (Section 7.1) — see correctness note below |
| 5 | SMS opt-out compliance owner (Section 5.4) | SMS channel disabled at launch | Legal/compliance owner (Section 7.1) |
| 6 | Runbook authorship (Section 7.1) | Pre-flight runbook gate fails; on-call rotation owner makes written go/no-go decision with stated post-launch deadline | On-call rotation owner (Section 7.1) — see structural constraint below |

**Decision 2 — SMS cost co-sign requirement:** The daily spam threshold directly controls SMS cost exposure quantified in Section 1.2 (up to $75,000/day at 5% SMS share with uncapped power-user volume). Decision 2 therefore requires two signatures: the product owner and the person with budget authority over SMS costs. Section 7.1 names both. If they are the same person, one signature suffices. If they disagree, the more restrictive threshold applies until the disagreement is resolved in writing.

If the SMS budget owner role is not filled before the deadline, the pre-flight checklist gate in Section 7.1 fails explicitly: "SMS budget owner identified and has reviewed Section 1.2 cost table." Engineering cannot resolve organizational gaps; it deploys the conservative fallback, documents why, and notifies the product owner that the SMS budget review did not occur. The product owner is responsible for clearing organizational blockers that appear on the checklist.

**Decision 3 — Fanout cap options:** Events with more than 10,000 recipients (e.g., a post by a user with 500,000 followers) require a decision about how the excess is handled. Two options:

- **Option A — Accept consistency gap:** Process the first 10,000 recipients in the current event cycle. Queue remaining recipients as a lower-priority follow-on job, which runs within 15 minutes under normal load. Recipients beyond position 10,000 receive their notification late. The gap is visible in delivery timestamps but not in final delivery state — everyone eventually gets notified.
- **Option B — Block until complete:** Hold the event in queue until all recipients can be processed in a single atomic batch. Under high load, this can delay the entire fanout by 30–60 minutes and creates head-of-line blocking for unrelated events behind it in the queue.

**Option A is the fallback.** The consistency gap is visible in logs and delivery receipts but is not user-visible in most product surfaces. Option B's head-of-line blocking risk is a worse tradeoff for a system where P0 notifications (Section 3.1) include time-sensitive content. If the product surface makes delivery timestamp consistency visible to users — for example, a "seen by" list that shows ordered delivery — this decision should be revisited before launch.

**Decision 4 — Deduplication window correctness note:** The 24-hour fallback has a product correctness consequence that depends on whether the notification feed deduplicates at read time by event ID.

**Engineering's prerequisite:** Before this is framed as a product decision, engineering must answer: does the notification feed deduplicate at read time by event ID? This answer must be recorded in Section 7.1 before the pre-flight checklist closes. If the feed deduplicates at read time, the infrastructure window is largely irrelevant and Decision 4 can be resolved by engineering alone with no product owner input required. If the feed is append-only, duplicates are visible to users, the 48-hour window is strongly preferred, and Decision 4 escalates to the product owner with the duplicate-notification risk made explicit. The Redis cost difference between 24-hour and 48-hour windows is quantified in Section 6.1.

If engineering cannot determine the feed architecture before the deadline — because the feed is owned by a separate team or has not been built yet — the question escalates to the product owner, who owns the duplicate-notification risk of the 24-hour fallback.

The pre-flight checklist gate reads: "Engineering has recorded feed deduplication architecture in Section 7.1 and has either resolved Decision 4 independently or escalated to product owner with written risk statement."

**Decision 6 — Runbook gate and structural constraint:** A missing runbook does not block deployment automatically. It causes the pre-flight checklist to fail its runbook gate, and the on-call rotation owner makes the go/no-go call with explicit knowledge that operators will be working without documented procedures. That is a risk the on-call rotation owner can accept in writing. It is not a risk engineering accepts silently.

However, the person who bears operational risk is also the person who can waive the protection designed to manage that risk. This is a structural incentive problem. The constraint applied here: a written waiver must include a post-launch runbook deadline — no more than two weeks after launch — and must name an escalation owner if the deadline is missed. If the on-call rotation owner will not commit to a specific post-launch deadline in writing, the waiver is not valid and the gate remains failed. This does not prevent launch — it prevents the waiver from creating a permanent exception with no closure condition.

**Dependency chain for infrastructure sizing:** Two decisions affect infrastructure provisioning in sequence. The deduplication retention window (Decision 4) determines Redis key volume. FCM rate verification (Section 1.4) determines which Redis sizing branch applies. If FCM verification is not complete before launch, Branch B sizing (Section 6.1) is the default and remains in force until the explicit migration trigger in Section 6.1 is met.

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

**The staffing constraint is a design input, not a caveat.** Section 1.5 contains the staffing arithmetic that drove the reduction from a theoretical 16 worker deployments to 6. That arithmetic starts from a fixed budget of engineer-weeks, subtracts non-feature work (testing, on-call, code review, deployment), and derives the maximum number of deployments that can be built and safely operated within the remaining capacity. The architectural decisions follow from that bound; the bound does not follow from the decisions.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. Token bucket parameters — refill rates, bucket sizes, and deferral conditions — are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that window is in Section 4.2. Worst-case delivery outcome under crash recovery is duplication, not loss. This holds for crash recovery and for the Redis failover scenario in Section 6.2 under the conditions specified there. There is one failure mode — a Redis primary failure during the replication promotion window — where in-flight entries can be lost rather than duplicated. Section 6.2 specifies the conditions under which this occurs, the estimated probability given stated replication lag bounds, and the recovery procedure.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is reduced priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches (A and B) depending on the FCM rate verification outcome in Section 1.4.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The bounding cases in the sensitivity table use joint scenarios. However, the table also includes two intermediate scenarios that the purely correlated structure would otherwise obscure: a high-retention app with a conservative notification policy, and a moderate-retention app with aggressive re-engagement. These are real operating modes that can be reached from the plan baseline without a change in user behavior — only a change in product configuration.

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

**Peak multiplier derivation:** Peak multipliers are not sourced from published data for this application — they are assumptions, and they compound with the DAU/MAU and notifications-per-user assumptions. The values used are derived as follows:

- **2.0× (low engagement row):** A low-engagement app has more uniform traffic distribution. Fewer users, fewer simultaneous peaks. 2.0× is the lower bound of the range observed in general web traffic patterns (2.0–3.5×) and is used conservatively for this scenario.
- **2.2× (plan and high-retention rows):** A social app with moderate engagement exhibits clear daily peaks around morning and evening usage windows. 2.2× is consistent with general social platform patterns where peak hour is roughly 2.2× the average active hour. This is the planning assumption, not a measured value.
- **2.5× (moderate-retention/aggressive re-engagement and high engagement rows):** Higher notification volume creates stronger simultaneous delivery bursts — re-engagement campaigns fire at scheduled times, compressing volume into narrower windows. 2.5× reflects this campaign-driven peaking behavior.
- **3.0× (extreme/viral row):** Viral events create sharp, narrow spikes. A single trending post generating fanout to millions of followers concentrates delivery into minutes. 3.0× is the upper bound assumption for this scenario.

**What this means for the intermediate rows:** The high-retention/conservative row uses 2.2× (same as plan) because conservative notification policy suppresses campaign-driven peaks even with high DAU. The moderate-retention/aggressive re-engagement row uses 2.5× because the aggressive campaign behavior is the source of the higher multiplier, not the DAU level. These multiplier assignments are judgments, not measurements. If month-1 