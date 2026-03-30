# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Synthesis — Incorporating Strongest Elements from Both Versions

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. Decisions A and B interact; the interaction analysis is in §0.3.

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [name] and engineering lead [name], jointly.**

Three options:

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together.
- **Option C (default):** Weighted fair-share during normal operation (identical to Option B), with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**Default if no explicit sign-off within 14 days: Option C.**

Both decision owners must confirm in writing that they have read this section and accept Option C, or nominate an alternative. If neither owner responds within 14 days, Option C is implemented as specified. Non-response does not block implementation. It creates an audit trail and triggers the following: (1) the non-response is documented in the project record, (2) the engineering lead notifies both decision owners' managers [names] that a default fired without acknowledgment. Decision owners retain the ability to override Option C at any point before the implementation milestone in §7.1 (week 4). An override after implementation begins incurs approximately 2 engineer-weeks of rework, documented in §7.1. Whether that cost is recharged between teams is a management decision outside this document's scope.

The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override the default to Option A before the 14-day window closes.

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead [name].**

**Default if no explicit sign-off within 14 days: Sentinel.** Non-response triggers the same consequences as Decision A: option defaults to Sentinel, non-response is documented, engineering lead's manager [name] is notified directly. (Decision A has two joint owners; Decision B has one. The escalation goes to the engineering lead's manager only — the Decision A procedure does not transfer.)

Rationale: operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The failover window is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the difference is a 10–25 second delta in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel if it bypasses the standard queue path via direct dispatch. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional. Decision B cannot be finalized without reading §3.4, which contains the full achievability analysis.

### 0.3 Interaction Analysis

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

The table below distinguishes primetime and off-hours spike scenarios where the absolute load difference changes the analysis. A 3× spike off-hours (909/sec) exceeds the primetime sustained rate (840/sec) in absolute terms — queue dynamics are similar or worse under off-hours spikes, not better. Rows where the distinction is immaterial are combined.

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× in absolute terms | Soft isolation; less severe than primetime 3× in absolute terms |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained; SP queue unbounded | Both tiers unbounded; operational response required | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, no advantage over C in this sub-case | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| PostgreSQL fallback overloaded, Redis recovers | HP workers resume Redis processing immediately; SP workers follow | Both tiers resume Redis together | HP workers resume Redis first via polling discipline |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**Redis failover + 8× spike analysis:** Under all three options, a sustained 8× spike concurrent with Redis failover produces unbounded standard-priority queue growth. This exceeds the design envelope and is not an architecture failure. The operational response procedure is specified in §2.4. Options A and C protect high-priority delivery in this scenario; Option B does not. This is the primary argument for Option A or C over Option B.

**Combined contingency cost if defaults fire and later require upgrade:** Option C implementation (~1.5 engineer-weeks) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks total. Whether this fits within the timeline is shown in §7.1.

---

## Executive Summary

This document designs a notification system for a 10M MAU social app, handling approximately 34.6M dispatch operations per day at the base case across push, email, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized for sustained load at the upper bound of the validated range; the sizing argument is in §1.3. Under spike conditions the architecture accumulates queue depth and drains post-spike — the delay figures below are the explicit cost of that choice.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets backed by Redis Sentinel. A circuit breaker routes to a PostgreSQL fallback queue with separate tables per priority tier when Redis is unavailable. Worker allocation defaults to Option C: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | 34.6M/day | ±50% | §1.1 |
| Sustained primetime rate | ~840/sec | ±50% | §1.2 |
| Worker capacity (100 workers) | 1,300–3,500/sec | Wide range; derivation in §1.2 | §1.2 |
| Planning figure (100 workers) | 1,800/sec | Below-midpoint conservative bound; see §1.2 | §1.2 |
| Standard-priority delay, primetime 3× spike | 47 min (CI: 18–95 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | 49 min (CI: 19–98 min) | Queue model; off-hours 3× exceeds primetime sustained rate in absolute terms | §1.2, §2.3 |
| High-priority delay, primetime 3× spike | 14 min (CI: 5–28 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | ~4 hours before operational response | Scenario analysis; §2.4 | §2.4 |
| Queue depth trigger for operational response | 500K messages | Derivation in §2.4 | §2.4 |
| Redis Sentinel failover window | 10–30 seconds | Vendor-documented | §5.3 |
| SMS p99 delivery target | <60 seconds | SLA commitment; achievability analysis in §3.4 | §3.4 |

**Notes on planning figure:** The worker capacity range of 1,300–3,500/sec reflects genuine uncertainty in per-worker throughput. The planning figure of 1,800/sec sits below the midpoint of that range (~2,400/sec on a uniform distribution), providing a conservative buffer against the lower end of the capacity distribution. The prior claim that 2,000/sec represented "approximately the 50th percentile" was arithmetically wrong and has been corrected. Full derivation is in §1.2.

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

**Five unvalidated assumptions** drive the majority of volume uncertainty. They are listed in §1.1 with validation commitments, pass/fail criteria, named owners, and remediation procedures.

---

## 1. Scale Assumptions and Constraints

### 1.1 Volume Model

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Five assumptions drive the majority of sizing uncertainty. Each is flagged explicitly as unvalidated and presented with a validation commitment, pass/fail criterion, named owner, and remediation procedure.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. The 8× scenario is extrapolation beyond cited data and is treated as such in §2.4.

#### The Five Unvalidated Assumptions

**Assumption 1: DAU/MAU ratio = 30%**
This gives 3M DAU from 10M MAU. Reference range from cited sources: 20–50% for social apps. This is the dominant volume uncertainty — push is 77% of total dispatch volume, and push volume scales directly with DAU. A 10-percentage-point swing changes total volume by approximately 25%.

*Validation commitment:* Measure from beta cohort data at week 18. Owner: data engineering lead [name]. Pass criterion: ratio falls within 25–40%. Fail criterion: ratio falls outside 20–50%.

*Remediation if ratio falls outside 20–50%:* Engineering lead has authority to adjust worker count without further sign-off. Lead time required: 2 weeks (procurement and provisioning). For a ratio below 20% (≤2M DAU), the derived worker count is 55; for a ratio above 50% (≥5M DAU), the derived count is 140. Both figures are derived in §1.2 using the same capacity model as the base case — they are not asserted independently. If the ratio exceeds 60%, escalate to architecture review; the queue model assumptions change qualitatively at that point.

*Timeline interaction:* Validation occurs at week 18 of 24. If the ratio falls outside the pass range, remediation (2 weeks) consumes weeks 18–20, leaving a 4-week buffer before launch. Assumptions 2–5 are validated at week 14 so their findings can propagate into the queue model and SLA review before the Assumption 1 window opens.

If any Assumption 2–5 remediation is not complete by week 16 (two weeks before the Assumption 1 window), the engineering lead escalates to the product lead and both managers. The options at that point are: (a) accept that Assumption 1 validation will be compressed to less than 2 weeks, (b) delay launch by the remediation overage, or (c) accept the current worker count as-is and monitor post-launch. This is a management decision. The engineering lead's responsibility is to surface it with two weeks of lead time, not to resolve it unilaterally.

**Assumption 2: Notifications per DAU = 8/day**
Anchored by the Twitter/X lower-bound reference and the Braze upper-quartile figure. Treated as the midpoint of a plausible range of 5–12/day.

*Validation commitment:* Measure from beta cohort event logs at week 14. Owner: product lead [name]. Pass criterion: 5–12/day. Fail criterion: outside that range.

*Remediation:* If above 12/day, reassess batching thresholds in §2.2 before launch. If below 5/day, no infrastructure change required — this is a favorable outcome.

**Assumption 3: Push opt-in rate = 52%**
iOS opt-in rates post-ATT range from 40–65% for social apps (Liftoff Mobile Gaming Apps Report, 2022; AppsFlyer State of App Marketing, 2023). Android opt-in is higher but Android's share of the user base is unknown. 52% is a conservative midpoint.

*Validation commitment:* Measure from beta permission-prompt flow at week 14. Owner: mobile engineering lead [name]. Pass criterion: 40–65%. Fail criterion: outside that range.

*Remediation:* Volume scales linearly with opt-in rate. Engineering lead adjusts worker count using the same authority and lead time as Assumption 1.

**Assumption 4: Session-distribution fractions**
The email routing model requires an estimate of how many MAU have no active session at notification time. We assume 40% of MAU are inactive at any given routing moment during primetime. This determines email volume.

*Validation commitment:* Measure session activity distribution from beta session logs at week 14. Owner: backend engineering lead [name]. Pass criterion: 30–55% inactive fraction. Fail criterion: outside that range.

**Assumption 5: Email routing model**
Email is routed only to users with no active session at routing time, to avoid double-dispatch. The routing rule and its volume implications are derived in §1.1 below from first principles.

*Validation commitment:* Audit routing logs from beta for double-dispatch rate at week 14. Owner: backend engineering lead [name]. Pass criterion: double-dispatch rate below 0.5%. Fail criterion: above 2%.

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call. It does not add to the dispatch count.

A given notification event dispatches to at most one of {push, email} per user. In-app delivery is additive for users in active session who also receive push — they see the push alert and the in-app badge — but it generates no additional dispatch operation.

#### Email Volume Construction

Email volume is derived from the session-distribution model, not reverse-engineered from a target figure. The construction proceeds from first principles.

**Step 1: Email-eligible population.** 10M MAU × 60% with verified email = 6M email-eligible users.

**Step 2: Reachable fraction.** Of the 6M email-eligible users, those in active session at routing time receive push or in-app and are not routed to email. With a 40% inactive fraction (Assumption 4), approximately 2.4M email-eligible users are reachable via email at any given primetime routing moment.

**Step 3: Email dispatch rate.** Email is not sent for every notification event — only for digest-eligible events batched per the rules in §2.2. The digest batching model and resulting email dispatch rate are derived in §2.2.

---

## 2. Priority, Batching, and Queue Architecture

### 2.1