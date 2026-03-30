# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. Decisions A and B interact; the full interaction analysis is in §0.3.

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead and engineering lead jointly.**

Three options:

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together.
- **Option C (default):** Weighted fair-share during normal operation (identical to Option B), with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**Default if no explicit sign-off within 14 days: Option C.**

This default requires active acknowledgment, not silence. Both decision owners must confirm in writing that they have read this section and accept Option C, or nominate an alternative. An unread or unacknowledged 14-day window does not constitute sign-off.

**Escalation procedure when decision owners remain non-responsive:** If the engineering lead escalates before the window closes and both decision owners remain non-responsive at window close, the following occurs automatically: (1) Option C is implemented as specified, (2) the non-response is documented in the project record as a known governance failure, (3) the engineering lead notifies both decision owners' managers that a default fired without acknowledgment. The "active acknowledgment" requirement is a process control, not a veto — non-response does not block implementation, it creates an audit trail and management visibility. Decision owners retain the ability to override Option C at any point before the implementation milestone in §7.1 (week 4), but an override after implementation begins incurs the full 2 engineer-week cost of switching to Option A. This cost is borne by the overriding party's team budget.

**Rationale for Option C as default:** It closes the interaction gap identified in §0.3 — no priority isolation during failover under Option B — at lower operational cost than Option A. The upgrade path from C to A requires approximately 2 engineer-weeks if validation data shows polling-discipline isolation is insufficient. The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override the default to Option A before the window closes.

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead.**

**Default if no explicit sign-off within 14 days: Sentinel.** Same acknowledgment and escalation requirements as Decision A.

**Rationale:** Operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The failover window is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the difference is a 10–25 second delta in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional — SMS cannot meet its SLA through the standard queue path during a Sentinel failover window.

### 0.3 Interaction Analysis

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

The 8× spike row reflects the highest-risk scenario identified in §2.4 and represents the compounded worst case of concurrent Redis failover and extreme load.

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, 3× spike | Full isolation | Soft isolation | Soft isolation |
| Redis failover, 10–30 sec | Partial isolation (HP workers retry Redis) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained; SP queue unbounded | Both tiers unbounded; operational response required | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded | HP workers continue retrying Redis; SP workers queue in PG | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**Redis failover + 8× spike analysis:** Under all three options, a sustained 8× spike concurrent with Redis failover produces unbounded standard-priority queue growth. This is not an architecture failure — it is a scenario that exceeds the design envelope. The operational response procedure is specified in §2.4. The critical difference between options in this scenario is that Options A and C protect high-priority delivery; Option B does not. This is the strongest argument for Option A or C over Option B.

**Combined contingency cost if defaults fire and later require upgrade:** Option C implementation (~1.5 engineer-weeks) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks total. Whether this fits within the timeline is shown in §7.1.

---

## Executive Summary

This document designs a notification system for a 10M MAU social app, handling approximately 34.6M dispatch operations per day at the base case across push, email, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized for sustained load at the upper bound of the validated range; the sizing argument is in §1.3. Under spike conditions the architecture accumulates queue depth and drains post-spike — the delay figures below are the cost of that design choice.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets backed by Redis Sentinel. A circuit breaker routes to a PostgreSQL fallback queue with separate tables per priority tier when Redis is unavailable. Worker allocation defaults to Option C: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | 34.6M/day | ±50% | §1.1 |
| Sustained primetime rate | ~840/sec | ±50% | §1.2 |
| Worker capacity (100 workers) | 1,300–3,500/sec | Bounded range | §1.2 |
| Planning figure (100 workers) | 2,000/sec | Conservative bound; see §1.2 | §1.2 |
| Standard-priority delay, primetime 3× spike | 47 min (CI: 18–95 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | 49 min (CI: 19–98 min) | Queue model; corrected; see §1.2 | §1.2, §2.3 |
| High-priority delay, primetime 3× spike | 14 min (CI: 5–28 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | ~4 hours before operational response; queue may not drain without intervention | Scenario analysis; §2.4 | §2.4 |
| Queue depth trigger for operational response | 500K messages | Defined in §2.4 | §2.4 |
| Redis Sentinel failover window | 10–30 seconds | Vendor-documented | §5.3 |
| SMS p99 delivery target | <60 seconds | SLA commitment; achievability analysis in §3.4 | §3.4 |

**Corrections from prior drafts noted here for traceability:**
- Worker capacity range corrected to 1,300–3,500/sec. The prior figure of 2,200–4,400/sec used an inconsistent efficiency assumption. See §1.2 for the full derivation.
- Planning figure revised from 3,000/sec to 2,000/sec. The prior figure was described as "conservative" but sat in the upper third of the derived range — an inconsistency. 2,000/sec sits near the midpoint of the range and is genuinely conservative relative to the planning scenario.
- Off-hours 3× spike delay corrected from 28 minutes to 49 minutes. The prior figure was wrong: 3× off-hours load (909/sec) exceeds the primetime sustained rate (840/sec) in absolute terms, so queue dynamics are similar or worse, not better.
- "May not drain" for the 8× spike scenario is now operationally defined: a queue depth of 500K messages triggers the operational response procedure in §2.4.

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

**Five unvalidated assumptions** drive the majority of volume uncertainty. They are listed in §1.1 with validation commitments, pass/fail criteria, named owners, and remediation procedures.

---

## 1. Scale Assumptions and Constraints

### 1.1 Volume Model

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Five assumptions drive the majority of sizing uncertainty. Each is flagged explicitly as unvalidated and presented with a validation commitment.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. The 8× scenario is extrapolation beyond cited data and is treated as such in §2.4.

#### The Five Unvalidated Assumptions

**Assumption 1: DAU/MAU ratio = 30%**
This gives 3M DAU from 10M MAU. Reference range from cited sources: 20–50% for social apps. This is the dominant volume uncertainty — push is 77% of total dispatch volume, and push volume scales directly with DAU. A 10-percentage-point swing changes total volume by approximately 25%.

*Validation commitment:* Measure from beta cohort data at week 18 (8 weeks before launch). Owner: data engineering lead. Pass criterion: ratio falls within 25–40%. Fail criterion: ratio falls outside 20–50%.

*Remediation if ratio falls outside 20–50%:* Engineering lead has authority to adjust worker count without further sign-off. Lead time required: 2 weeks (procurement and provisioning). For a ratio below 20%, reduce to 60 workers; for a ratio above 50%, add 40 workers (to 140 total). If ratio exceeds 60%, escalate to architecture review — the queue model assumptions change qualitatively at that point.

*Timeline interaction:* Validation occurs at week 18 of 24. If the ratio falls outside the pass range, the 2-week remediation consumes the remaining buffer before launch. To prevent this from compressing other assumption validations into the same window, Assumptions 2–5 are validated at week 14. Assumption 1 is last because worker count cannot be finalized until the DAU/MAU ratio is confirmed. The validation sequence is: Assumptions 2–5 at week 14 → findings propagate into queue model and SLA review by week 16 → Assumption 1 validation at week 18 → worker count finalized by week 20 → 4-week buffer before launch. If any Assumption 2–5 validation fails at week 14, remediation must complete by week 18 to avoid compressing the Assumption 1 window. Owner of validation sequencing: engineering lead.

**Assumption 2: Notifications per DAU = 8/day**
Anchored by the Twitter/X lower-bound reference and the Braze upper-quartile figure. Treated as the midpoint of a plausible range of 5–12/day.

*Validation commitment:* Measure from beta cohort event logs at week 14. Owner: product lead. Pass criterion: 5–12/day. Fail criterion: outside that range.

*Remediation:* If above 12/day, reassess batching thresholds in §2.2 before launch. If below 5/day, no infrastructure change required — this is a favorable outcome.

**Assumption 3: Push opt-in rate = 52%**
iOS opt-in rates post-ATT range from 40–65% for social apps (Liftoff Mobile Gaming Apps Report, 2022; AppsFlyer State of App Marketing, 2023). Android opt-in is higher but Android's share of the user base is unknown. 52% is a conservative midpoint.

*Validation commitment:* Measure from beta permission-prompt flow at week 14. Owner: mobile engineering lead. Pass criterion: 40–65%. Fail criterion: outside that range.

*Remediation:* Volume scales linearly with opt-in rate. Engineering lead adjusts worker count using the same authority and lead time as Assumption 1.

**Assumption 4: Session-distribution fractions**
The email routing model requires an estimate of how many MAU have no active session at notification time. We assume 40% of MAU are inactive at any given routing moment during primetime. This determines email volume.

*Validation commitment:* Measure session activity distribution from beta session logs at week 14. Owner: backend engineering lead. Pass criterion: 30–55% inactive fraction. Fail criterion: outside that range.

**Assumption 5: Email routing model**
Email is routed only to users with no active session at routing time, to avoid double-dispatch. The routing rule and its volume implications are constructed below.

*Validation commitment:* Audit routing logs from beta for double-dispatch rate at week 14. Owner: backend engineering lead. Pass criterion: double-dispatch rate below 0.5%. Fail criterion: above 2%.

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call. It does not add to the dispatch count.

A given notification event dispatches to at most one of {push, email} per user. In-app delivery is additive for users in active session who also receive push — they see the push alert and the in-app badge — but it generates no additional dispatch operation.

#### Email Volume Construction

Email volume is derived from the session-distribution model, not treated as a standalone figure. The prior collapsed intermediate (a "78% reachable fraction" figure) obscured the construction; the full derivation follows.

**Step 1: Email-eligible population.** 10M MAU × 60% with verified email = 6M email-eligible users.

**Step 2: Reachable fraction.** Of the 6M email-eligible users, 30% are in active session at any given primetime routing moment and receive push or in-app instead. This leaves 70% of email-eligible users reachable by email at any given moment.

**Step 3: Event fraction.** Email is sent only for high-value events (new follower, direct message, comment on own post) — estimated at 30% of all notification events by type.

**Step 4: Daily volume.** 6M eligible × 70% reachable × 30% high-value event fraction × ~6.3 events/day per eligible user ≈ **8M/day**. The 6.3 events/day figure is derived from 8 events/day per DAU scaled to the email-eligible population, which skews slightly less active.

This is Assumptions 4 and 5 combined. The 8M/