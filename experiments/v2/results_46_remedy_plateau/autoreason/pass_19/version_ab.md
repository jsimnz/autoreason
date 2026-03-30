# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Synthesis — Incorporating Best Elements of Both Versions

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock for each decision starts on the **document issue date defined in §0.4**. Decisions A and B interact; the interaction analysis is in §0.3.

### 0.4 Document Issue Date and Clock Mechanism

**The 14-day window for Decisions A and B starts on the date this document is formally issued to the decision owners.** Formal issuance means: the document is delivered to all named decision owners via the team's standard document distribution channel (currently Confluence with email notification), and the delivery is logged in the project record with a timestamp.

The issue date is recorded here at the time of distribution: **[ISSUE DATE — to be filled in at distribution, not before].**

Distributing a draft does not start the clock. The engineering lead [Alex Chen] is responsible for ensuring distribution occurs and the issue date is logged within one business day of this document reaching its final form. All references to "14 days" in this document mean 14 calendar days from the logged issue date.

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

Three options:

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together.
- **Option C (default):** Weighted fair-share during normal operation (identical to Option B), with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**Default if no explicit sign-off within 14 days of the issue date: Option C.**

Both decision owners must confirm in writing that they have read this section and accept Option C, or nominate an alternative. If neither owner responds within 14 days, Option C is implemented as specified. Non-response is documented in the project record, and both decision owners' managers [Taylor Okonkwo (product) and Morgan Singh (engineering)] are notified directly. Decision owners retain the ability to override Option C at any point before the implementation milestone in §7.1 (week 4). An override after implementation begins incurs approximately 2 engineer-weeks of rework, documented in §7.1. Whether that cost is recharged between teams is a management decision outside this document's scope.

The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override the default to Option A before the 14-day window closes.

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead [Alex Chen].**

**Default if no explicit sign-off within 14 days of the issue date: Sentinel.** Non-response is documented in the project record, and the engineering lead's manager [Morgan Singh] is notified directly. Because Decision B has a single owner, there is no second decision owner to involve — escalation goes to the manager only.

Rationale: operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The failover window is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the difference is a 10–25 second delta in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel if it bypasses the standard queue path via direct dispatch. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional. §3.4 contains the full achievability analysis. Decision B cannot be finalized without reading §3.4.

### 0.3 Interaction Analysis

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× because absolute load is lower | Soft isolation; less severe than primetime 3× |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained; SP queue unbounded | Both tiers unbounded; operational response required | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, HP workers queue in PG — no advantage over C in this sub-case | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| PostgreSQL fallback overloaded, Redis recovers | HP workers resume Redis processing immediately; SP workers follow | Both tiers resume Redis together | HP workers resume Redis first via polling discipline |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**Redis failover + 8× spike analysis:** Under all three options, a sustained 8× spike concurrent with Redis failover produces unbounded standard-priority queue growth. This exceeds the design envelope. The operational response procedure is specified in §2.4. Options A and C protect high-priority delivery in this scenario; Option B does not. This is the primary argument for Option A or C over Option B.

**Combined contingency cost if defaults fire and later require upgrade:** Option C implementation (~1.5 engineer-weeks) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks total. Whether this fits within the timeline is shown in §7.1.

---

## Executive Summary

This document designs a notification system for a 10M MAU social app, handling approximately 34.6M dispatch operations per day at the base case across push, email, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized for sustained load at the upper bound of the validated range; the sizing argument is in §1.3.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets backed by Redis Sentinel. A circuit breaker routes to a PostgreSQL fallback queue with separate tables per priority tier when Redis is unavailable. Worker allocation defaults to Option C: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | 34.6M/day | ±50% | §1.1 |
| Sustained primetime rate | ~840/sec | ±50% | §1.2 |
| Worker capacity (100 workers) | 1,300–3,500/sec | Wide range; derivation in §1.2 | §1.2 |
| Planning figure (100 workers) | 1,800/sec | Derived from operational constraint; see §1.2 | §1.2 |
| Standard-priority delay, primetime 3× spike | 47 min (CI: 18–95 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | 12 min (CI: 5–24 min) | Queue model; see note below | §2.3 |
| High-priority delay, primetime 3× spike | 14 min (CI: 5–28 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | ~4 hours before operational response | Scenario analysis | §2.4 |
| Queue depth trigger for operational response | 500K messages | Derivation in §2.4 | §2.4 |
| Redis Sentinel failover window | 10–30 seconds | Vendor-documented | §5.3 |
| SMS p99 delivery target | <60 seconds | SLA commitment; achievability analysis in §3.4 | §3.4 |

**Correction note — off-hours 3× spike delay:** An earlier draft stated 49 minutes for the off-hours 3× scenario. That figure was wrong — copied from the primetime scenario without adjusting for the substantially different utilization. The off-hours sustained rate is 303/sec. A 3× spike brings it to 909/sec. At 1,800/sec planning capacity, utilization is 909/1,800 = 50.5%. An M/M/c queue at 50.5% utilization does not produce 49-minute delays. The correct figure is approximately 12 minutes at the 50th percentile (CI: 5–24 min). The full derivation is in §2.3.

**Correction note — planning figure basis:** An earlier draft described 2,000/sec as "approximately the 50th percentile" of the 1,300–3,500/sec range. On a uniform distribution, the 50th percentile of that range is 2,400/sec; 2,000/sec is approximately the 32nd percentile. The planning figure is now 1,800/sec, derived from a specific operational constraint in §1.2, with no percentile claim attached.

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

**Five unvalidated assumptions** drive the majority of volume uncertainty. All five are listed in §1.1 with validation commitments, pass/fail criteria, named owners, and remediation procedures.

---

## 1. Scale Assumptions and Constraints

### 1.1 Volume Model

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Five assumptions drive the majority of sizing uncertainty. Each is flagged explicitly as unvalidated.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. The 8× scenario is extrapolation beyond cited data and is treated accordingly in §2.4.

#### The Five Unvalidated Assumptions

**Assumption 1: DAU/MAU ratio = 30%**

This gives 3M DAU from 10M MAU. Reference range from cited sources: 20–50% for social apps. This is the dominant volume uncertainty — push is 77% of total dispatch volume, and push volume scales directly with DAU. A 10-percentage-point swing changes total volume by approximately 25%.

*Validation commitment:* Measure from beta cohort data at week 18. Owner: data engineering lead [Priya Nair]. Pass criterion: ratio falls within 25–40%. Fail criterion: ratio falls outside 20–50%.

*Remediation if ratio falls outside 20–50%:* Engineering lead [Alex Chen] has authority to adjust worker count without further sign-off. Lead time required: 2 weeks (procurement and provisioning). The worker count adjustments are derived in §1.2 alongside the base-case worker sizing, using the same capacity model. For a ratio below 20% (≤2M DAU), the derived figure is 55 workers. For a ratio above 50% (≥5M DAU), the derived figure is 140 workers. If the ratio exceeds 60%, escalate to architecture review — the queue model assumptions change qualitatively at that point.

*Timeline interaction:* Validation occurs at week 18 of 24. Assumptions 2–5 are validated at week 14 so their findings can propagate into the queue model and SLA review before the Assumption 1 window opens. If any Assumption 2–5 remediation is not complete by week 16 (two weeks before the Assumption 1 window), the engineering lead [Alex Chen] escalates to the product lead [Jordan Rivera] and both managers [Taylor Okonkwo and Morgan Singh]. The options at that point are: (a) accept that Assumption 1 validation will be compressed to less than 2 weeks, or (b) delay launch by the remediation overage. This is a management decision. The engineering lead's responsibility is to surface it with two weeks of lead time.

Note: accepting the current worker count as-is when the ratio has been measured outside the acceptable range is not a valid option. If the ratio falls outside 20–50%, worker count adjustment is required. The escalation above is about *timing*, not about whether to remediate.

---

**Assumption 2: Notifications per DAU = 8/day**

Anchored by the Twitter/X lower-bound reference and the Braze upper-quartile figure. Treated as the midpoint of a plausible range of 5–12/day.

*Validation commitment:* Measure from beta cohort engagement data at week 14. Owner: data engineering lead [Priya Nair]. Pass criterion: per-DAU rate falls within 6–10/day. Fail criterion: rate falls outside 4–14/day.

*Remediation if outside 4–14/day:* Re-derive total volume using the measured rate. If total volume exceeds the upper bound of the sizing range (55M/day), escalate to architecture review — the current infrastructure sizing is insufficient. If total volume falls below the lower bound (20M/day), no remediation is required; the system is over-provisioned and can be right-sized at the next procurement cycle.

---

**Assumption 3: Push opt-in rate = 60%**

This is the fraction of MAU who have granted push notification permission. Reference range: 40–70% for social apps post-iOS 14 permission prompt changes (source: Airship State of Customer Engagement 2022). Push opt-in rate is the second-largest volume driver after DAU/MAU ratio. A 10-percentage-point swing changes push volume by approximately 17% and total dispatch volume by approximately 13%.

*Validation commitment:* Measure from beta cohort permission grant data at week 14. Owner: mobile engineering lead [Dana Park]. Pass criterion: opt-in rate falls within 50–70%. Fail criterion: rate falls outside 35–75%.

*Remediation if outside 35–75%:* If opt-in rate is below 35%, total push volume falls below the lower bound of the sizing range — system is over-provisioned, no immediate remediation required. If opt-in rate is above 75%, re-derive push volume and total dispatch volume; if total exceeds 55M/day, escalate to architecture review.

---

**Assumption 4: Email engagement rate = 15% of MAU**

Email is sent to all MAU who have provided an address and not unsubscribed. The 15% figure represents the fraction of MAU who receive at least one email notification per day. Reference range: 10–25% for social apps (source: Mailchimp industry benchmarks 2022, social/community category).

*Validation commitment:* Measure from beta cohort email subscription data at week 14. Owner: data engineering lead [Priya Nair]. Pass criterion: rate falls within 10–20%. Fail criterion: rate falls outside 8–25%.

*Remediation if outside 8–25%:* Email is 18% of total dispatch volume at the base case. A rate above 25% increases total volume by at most 9%; this falls within the sizing buffer and does not require remediation. A rate below 8% reduces volume; no remediation required.

---

**Assumption 5: SMS opt-in rate = 5% of MAU**

SMS is reserved for high-priority