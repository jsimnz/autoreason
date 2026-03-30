# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: What This Document Is and Is Not

This is a **design document**. It records architectural decisions, their rationale, and the tradeoffs made under staffing and time constraints.

This document is **not an operational runbook**. Incident response procedures, escalation chains, and operator CLI references belong in a separate runbook that is version-controlled independently of this design. The runbook owner, deadline, and fallback are specified in Section 7.1.

**Why this separation matters:** A design document is revised as the system evolves. A runbook embedded in a design document becomes incorrect every time the design changes. Operators under incident conditions cannot afford to discover that the section reference they were given no longer exists.

**The separation has a limit that must be stated plainly:** Section 7.1 of this document names the owners, deadlines, and pre-flight checklist that make the governance structure real. That section is not optional supporting material — it is the enforcement surface for every accountability claim in this document. If Section 7.1 is incomplete at launch, the governance structure in this document is decorative. The pre-flight checklist in Section 7.1 therefore includes an explicit gate: Section 7.1 itself must be complete and reviewed before the checklist can pass. A document that references its own governance section as a dependency is circular only if that section is never written. The deadline for completing Section 7.1 is the same as the deadline for all other named decisions: four weeks before launch, per Section 8.

---

## On Fallback Authority

Several decisions in this document have fallbacks. The fallbacks are engineering-specified values. This requires explanation, because the document also states that engineering does not have unilateral authority over product behavior decisions.

The resolution is this: **a fallback is not a product decision. It is an engineering constraint imposed by deployment dependencies.**

When a product owner does not make a decision by a named deadline, the system must deploy in some configuration. Engineering selects that configuration based on one criterion: which value causes the least irreversible harm while the product owner catches up.

**However, this framing has a limit that must be acknowledged directly.** Some fallbacks — specifically the fanout cap options in Decision 3 and the deduplication window in Decision 4 — have consequences that are architectural as well as product-affecting. Engineering is not merely selecting a safe configuration value; it is making a choice that affects consistency guarantees and user-visible duplicate notification behavior. Calling these "engineering constraints" while assigning consequence ownership to product owners would misrepresent what is happening.

The accurate framing: **engineering selects fallback values on the criterion of reversibility. Engineering owns the selection. Product owners own the product outcome of the fallback, but only if they were given an accurate description of what that outcome is before the deadline.** This document provides that description for each decision. If a product owner disputes a fallback after the deadline, the dispute is processed as a configuration change request in the next release cycle — not because engineering is unaccountable, but because post-deadline disputes require the same review process as any other change.

Fallback values are selected for reversibility and conservatism, not product optimality:

- The burst allowance fallback of 3 is the lower bound of the recommended range — conservative, easy to raise without a deployment.
- The daily cap fallback of 200 is restrictive — it will suppress some legitimate notifications, but suppression is reversible; spam damage to user retention is not.
- The deduplication window fallback of 24 hours costs more in duplicate-notification risk but less in Redis capacity, and the window can be extended via configuration change without a deployment.
- The fanout cap fallback of Option A accepts a consistency gap that is defined in full in Section 1.1. Product owners reading this document before the deadline have a complete description of what they are accepting if they do not decide.

**Engineering owns the fallback selection. Product owners own the consequences of not deciding, provided they received an accurate description of those consequences before the deadline. This document is that description.**

---

## Unresolved Decisions

Six decisions require named humans before the system can launch. Each has a fallback. The fallbacks keep the system operational; they are not optimal product choices. Section 7.1 contains the named owner, deadline, and signature line for each decision. **Section 7.1 must be complete before any other pre-flight gate can pass.**

| # | Decision | Fallback | Authority |
|---|---|---|---|
| 1 | Burst allowance (Section 1.1) | 3 notifications above ceiling per 5-minute window | Product owner (Section 7.1) |
| 2 | Daily spam threshold (Section 1.1) | Hard cap of 200 notifications/user/day, automatic suppression | Product owner (Section 7.1) — SMS budget owner must co-sign per Section 1.2 |
| 3 | Fanout cap option (Section 1.1) | Option A — accept consistency gap (defined in full in Section 1.1) | Product owner (Section 7.1) |
| 4 | Cross-channel deduplication retention window (Section 2.2) | 24 hours — see engineering prerequisite below | Product owner (Section 7.1) |
| 5 | SMS opt-out compliance owner (Section 5.4) | SMS channel disabled at launch | Legal/compliance owner (Section 7.1) |
| 6 | Runbook authorship (Section 7.1) | Pre-flight runbook gate fails; on-call rotation owner makes written go/no-go decision | On-call rotation owner (Section 7.1) |

**Decision 2 — SMS cost co-sign requirement:** The daily spam threshold directly controls SMS cost exposure quantified in Section 1.2. Decision 2 therefore requires two signatures: the product owner and the SMS budget owner named in Section 7.1.

If the SMS budget owner and product owner disagree on the threshold, the more restrictive value applies until written resolution. If the SMS budget owner does not respond before the deadline, the following sequence applies: (1) engineering sends a written reminder at T-minus-48-hours to the SMS budget owner and their direct manager, as named in Section 7.1; (2) if no response by the deadline, the 200/day fallback applies and both the SMS budget owner and their manager receive written notification that the SMS cost review did not occur and that they own the cost outcome of the fallback; (3) engineering documents the non-response in the pre-flight checklist. Engineering does not chase organizational gaps indefinitely — it deploys the conservative fallback, documents why, and ensures the right people know. The named manager escalation path exists precisely because "the role is filled but the person did not respond" is the most likely failure mode and it requires a path that does not dead-end.

**Decision 4 — Engineering prerequisite with a deadline:** The appropriate deduplication window depends on whether the notification feed deduplicates at read time by event ID. If it does, the infrastructure window is largely irrelevant and the 24-hour fallback is acceptable. If the feed is append-only, duplicates are visible to users and the 48-hour window is strongly preferred.

Engineering must answer this question before framing Decision 4 as a product choice. **This is an engineering deliverable with a named owner and a deadline, not an open question.** The feed architecture owner (named in Section 7.1) is responsible for providing a written answer — "deduplicates at read time" or "append-only" — to the notification system lead by the date specified in Section 7.1, which is two weeks before the product owner's decision deadline. If the feed architecture owner cannot answer by that date (because the feed is owned by a separate team, has not been built, or the architecture is genuinely undecided), the following applies: engineering records "feed architecture unknown" in Section 7.1, the product owner is notified that the framing of Decision 4 is uncertain, and the 24-hour fallback applies with explicit acknowledgment that duplicate-notification risk is unquantified. The product owner then owns the duplicate-notification risk of the 24-hour fallback with full knowledge that the engineering prerequisite was not met. The Redis cost difference between 24-hour and 48-hour windows is quantified in Section 6.1.

**Decision 6 — Runbook gate:** A missing runbook does not block deployment automatically. It causes the pre-flight checklist to fail its runbook gate, and the on-call rotation owner makes the go/no-go call with explicit knowledge that operators will be working without documented procedures. **This path exists because blocking deployment on a missing runbook when the runbook owner is unavailable creates a worse outcome than a documented, deliberate waiver.** It is not an invitation to skip the runbook. The operational safety argument in the preface stands: the runbook matters enough to separate from this document. Decision 6's waiver path acknowledges that a deliberate, written, accountable decision to launch without a runbook is less dangerous than an undocumented assumption that the runbook exists somewhere. The on-call rotation owner who signs the waiver owns the incident response risk, in writing, with that explicit framing.

**Dependency chain for infrastructure sizing:** The deduplication retention window (Decision 4) determines Redis key volume. FCM rate verification (Section 1.4) determines which Redis sizing branch applies. If FCM verification is not complete before launch, Branch B sizing (Section 6.1) is the default. Section 7.1 names the owner responsible for completing FCM verification and the date by which it must be done.

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

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. Token bucket parameters are fully specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. The derivation of that window is in Section 4.2. Worst-case delivery outcome under crash recovery is duplication, not loss. There is one failure mode — a Redis primary failure during the replication promotion window — where in-flight entries can be lost rather than duplicated. Section 6.2 specifies the conditions, estimated probability, and recovery procedure.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is reduced priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. Redis sizing has two explicit branches (A and B) depending on FCM rate verification outcome.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both. The sensitivity table uses joint scenarios. Two intermediate scenarios are included that the purely correlated structure would otherwise obscure: a high-retention app with a conservative notification policy, and a moderate-retention app with aggressive re-engagement. These are real operating modes reachable from the plan baseline through product configuration changes alone, without any change in user behavior.

---

**Peak multiplier methodology:**

Dividing total daily volume by 24 hours suppresses the computed average by including overnight hours with near-zero traffic. This document divides by active hours — hours in which send rate exceeds 10% of the hourly average. Fourteen active hours is the conservative (higher-peak) planning estimate.

**Limitation:** 14 active hours is an assumption from general social-app patterns, not a measured value for this application. If actual active hours are 16–18, computed peak rates are 14–22% lower than stated. All peak rate figures carry ±25% uncertainty until month-1 recalibration.

**How ±25% uncertainty propagates into sizing:** The infrastructure sizing in Section 6.1 and worker capacity analysis in Section 1.5 are derived from plan-row figures. The ±25% uncertainty is absorbed as follows: (a) worker deployments are sized with a 40% headroom above the plan peak rate, which covers the upper bound of the uncertainty range; (b) Redis sizing Branch B (the default) includes an additional 30% key volume buffer above the calculated requirement; (c) the traffic response matrix in Section 1.3 defines explicit triggers for scaling actions before the system reaches capacity limits, so month-1 recalibration feeds directly into a scaling decision rather than a redesign. Sizing numbers in Section 6.1 should be read as "sufficient at plan figures with headroom for ±25% uncertainty," not as exact requirements derived from exact inputs.

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

The extreme row's peak rate (~9,643/sec) is approximately 4.9× the plan row's (~1,964/sec) while daily volume is only 3.6× higher. Both daily volume and the peak multiplier are higher in the extreme row, and the multiplier compounds against the higher base.

**On the 3.0× peak multiplier in the extreme row:** This value is an assumption, not a derived figure. It is sourced from published capacity planning references for social apps at viral growth stages (Twitter's 2013 capacity engineering posts; Meta's 2020 infrastructure scaling retrospective). Viral traffic can produce higher multipliers — 4× to 6× is documented in extreme cases. The 3.0× figure is therefore potentially conservative in the wrong direction: it may understate the true peak. The extreme row should be read as a floor on viral-scenario capacity requirements, not a ceiling. If the app enters a viral growth phase, the traffic response matrix in Section 1.3 should be consulted immediately rather than waiting for the scheduled month-1 recalibration.

**Sensitivity table — six scenarios including intermediate cases:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak mult. | Peak rate | Notes |
|---|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.0× | ~595/sec | Cor