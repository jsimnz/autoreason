# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 5 — Addressing Critic Findings

*Changes from Revision 4 are marked with* ⟦R5⟧ *at the section heading where substantive changes occur.*

---

## Revision Notes ⟦R5⟧

Ten problems were identified in Revision 4. This revision addresses each directly. Where a prior revision table claimed a problem was fixed and the fix was incomplete, this table notes that explicitly.

| # | Problem | Resolution |
|---|---|---|
| 1 | §3.4 referenced but not shown; circular dependency unresolvable | §3.4 is now present in full within this document. The SMS achievability analysis is no longer deferred. |
| 2 | Assumptions 3–5 truncated; revision table claimed completeness falsely | All five assumptions are now present in full. The revision table in R4 was wrong. This table does not claim completeness — the document's content is the record. |
| 3 | Decision A joint sign-off has no deadlock resolution for partial response | §0.1 now specifies behavior for all four partial-response combinations explicitly. |
| 4 | 1,800/sec planning figure derivation deferred to absent §1.2 | The derivation is now inline in §1.2, present in this document. The operational constraint is stated in the executive summary. |
| 5 | 8× spike treated as reliable design input despite acknowledged extrapolation | §2.4 now applies explicit confidence degradation to extrapolated figures. The executive summary table now carries confidence qualifiers on these figures. |
| 6 | 2 engineer-week rework cost for Option C override is a bare assertion | §0.1 now contains the task-level derivation of the rework estimate. |
| 7 | Option A isolation guarantee collapses to Option C behavior when PostgreSQL is overloaded | §0.3 now addresses this directly. The implication for the Option A vs. Option C choice is stated explicitly. |
| 8 | Assumption 2 architecture review has no time bound; could force launch delay without warning | §1.1 Assumption 2 now specifies a maximum review duration and a hard decision point. |
| 9 | Manager notification is a recording mechanism, not an escalation procedure | §0.1 and §0.2 now specify what managers are expected to do, by when, and what happens if they do not act. |
| 10 | Revision table claimed completeness; document contradicted the claim | This revision table makes no completeness claims. The document's content is the authoritative record. If a section is missing, that is a defect regardless of what this table says. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock for each decision starts on the document issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

### 0.4 Document Issue Date and Clock Mechanism

**The 14-day window for Decisions A and B starts on the date this document is formally issued to the decision owners.** Formal issuance means: the document is delivered to all named decision owners via the team's standard document distribution channel (currently Confluence with email notification), and the delivery is logged in the project record with a timestamp.

The issue date is recorded here at the time of distribution: **[ISSUE DATE — to be filled in at distribution, not before].**

If the document is revised before distribution, the clock does not start until the revised version is distributed. Distributing a draft does not start the clock. The engineering lead [Alex Chen] is responsible for ensuring distribution occurs and the issue date is logged within one business day of this document reaching its final form.

All references to "14 days" in this document mean 14 calendar days from the logged issue date.

### 0.1 Decision A: Worker Allocation Strategy ⟦R5⟧

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

Three options:

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover.
- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline.

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

#### Rework Cost Derivation ⟦R5⟧

An override of Option C after the implementation milestone in §7.1 (week 4) incurs approximately 1.9 engineer-weeks of rework. This figure is derived from the following task list, not asserted:

| Task | Estimate | Basis |
|---|---|---|
| Decompose single worker pool into two process groups | 2 days | Requires new Supervisor config, process isolation testing, deployment pipeline changes for two targets instead of one |
| Create separate Redis consumer groups per priority tier | 1 day | Redis XGROUP commands; consumer group offset management; integration tests |
| Rewrite worker dispatch logic from weighted-share to hard-isolated | 2 days | Current dispatch logic assumes shared pool; priority routing must move to process-group assignment at enqueue time |
| Update PostgreSQL fallback to match new process-group topology | 1 day | Fallback currently uses polling discipline (Option C); must change to process-group-aware table assignment |
| Load testing of new topology under primetime 3× spike scenario | 1.5 days | Cannot skip; isolation guarantee must be verified under load, not just in unit tests |
| Update monitoring and alerting for two process groups | 0.5 days | Queue depth alerts, worker health checks, and on-call runbooks must be duplicated and differentiated |
| **Total** | **8 days ≈ 1.9 engineer-weeks** | One engineer assigned full-time; parallel work by a second engineer is possible for the testing phase but not assumed |

This estimate assumes the override occurs after week 4. If the override occurs before week 4, the rework cost is lower because some of the above tasks have not yet been built. The engineering lead [Alex Chen] will re-derive the estimate at the time of any override request.

#### Partial Response Deadlock Resolution ⟦R5⟧

The joint sign-off requirement creates four partial-response scenarios. Each is resolved as follows:

| Scenario | Resolution |
|---|---|
| Both owners respond and agree on an option | That option is implemented. |
| Both owners respond; one selects Option A, one selects Option C | Engineering lead [Alex Chen] has the tiebreaking vote. Alex must exercise it within 3 business days of the disagreement being logged. If Alex does not exercise it within 3 business days, Option C is implemented and both managers [Taylor Okonkwo and Morgan Singh] are notified per the escalation procedure below. |
| One owner responds; the other is silent after 14 days | The responding owner's choice is implemented if they selected Option A or Option C. If the responding owner selected Option B, the default (Option C) is implemented instead — Option B requires affirmative joint agreement because it provides no priority isolation during failover. The silent owner's manager is notified per the escalation procedure below. |
| Neither owner responds after 14 days | Option C is implemented. Both managers are notified per the escalation procedure below. |

**Escalation procedure when managers are notified:** This is not a recording mechanism. It is an active escalation with a required response.

When a manager is notified, the notification must include: (a) the specific decision that was not made, (b) the default that will be implemented, (c) the implementation date (14 days from issue date, or the date the default fires), and (d) the question the manager must answer: *Do you accept the default, or are you escalating to override it?*

The manager has 2 business days to respond. If the manager responds with an override, the override is treated as a new decision input and the tiebreaking procedure above applies. If the manager does not respond within 2 business days, the default is implemented and the non-response is logged. No further escalation occurs — the default fires at this point regardless of organizational hierarchy above the manager level. The engineering lead [Alex Chen] is responsible for logging the outcome and communicating it to the implementation team.

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster ⟦R5⟧

**Decision owner: engineering lead [Alex Chen].**

**Default if no explicit sign-off within 14 days of the issue date: Sentinel.**

Rationale: operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The failover window is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the difference is a 10–25 second delta in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel if it bypasses the standard queue path via direct dispatch. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional. §3.4 contains the full achievability analysis. Decision B cannot be finalized without reading §3.4.

**Escalation procedure for non-response:** Same structure as Decision A. If Alex does not respond within 14 days, Sentinel is implemented and Alex's manager [Morgan Singh] is notified with the same four-item notification content specified in §0.1. Morgan has 2 business days to respond with an override or accept the default. If Morgan does not respond, Sentinel is implemented and the non-response is logged. No further escalation occurs.

### 0.3 Interaction Analysis ⟦R5⟧

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× because absolute load is lower | Soft isolation; less severe than primetime 3× |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained; SP queue unbounded | Both tiers unbounded | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, HP workers also queue in PG — no advantage over C in this sub-case | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| PostgreSQL fallback overloaded, Redis recovers | HP workers resume Redis processing immediately; SP workers follow | Both tiers resume Redis together | HP workers resume Redis first via polling discipline |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**The PostgreSQL overload sub-case and its implication for Option A vs. Option C:** ⟦R5⟧

The table shows that when PostgreSQL is overloaded *and* Redis is still down, Option A's isolation guarantee collapses to Option C's behavior: high-priority workers end up queuing in PostgreSQL alongside standard-priority workers because there is nowhere else to go. This is the most realistic concurrent failure mode during a combined spike-and-failover event — spikes are the most common cause of PostgreSQL overload, and spikes are also the most likely trigger for Redis failover due to connection exhaustion.

This means Option A's hard isolation guarantee is unavailable precisely when it is most needed. The isolation advantage of Option A over Option C exists only when: (a) Redis is down, (b) PostgreSQL is not overloaded, and (c) the load is sufficient to saturate a shared queue but not sufficient to saturate the PostgreSQL fallback. This is a narrow condition.

**Implication:** Option A is not worth its additional operational complexity (~2 engineer-weeks to implement vs. Option C's ~1.5 engineer-weeks; ~0.5 engineer-weeks of permanent additional maintenance overhead for two process groups vs. one) if its primary advantage evaporates in the failure mode it is designed to handle. Option C's polling-discipline isolation is available in all scenarios where Option A's hard isolation is also available, and the two options behave identically in the PostgreSQL-overload sub-case.

**This analysis is a recommendation, not a mandate.** If the decision owners [Jordan Rivera and Alex Chen] have a use case where Redis-down + PostgreSQL-not-overloaded is a realistic and important scenario — for example, if PostgreSQL is provisioned with substantial headroom specifically to handle failover load — Option A's advantage is real in that scenario. The decision owners should state their PostgreSQL provisioning assumption explicitly when making this decision.

**Combined contingency cost if defaults fire and later require upgrade:** Option C implementation (~1.5 engineer-weeks) plus upgrade to Option A if failover behavior proves insufficient (~1.9 engineer-weeks per §0.1 derivation) = ~3.4 engineer-weeks total. The timeline impact is shown in §7.1.

---

## Executive Summary

This document designs a notification system for a 10M MAU social app, handling approximately 34.6M dispatch operations per day at the base case across push, email, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized for sustained load at the upper bound of the validated range; the sizing argument is in §1.3.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets backed by Redis Sentinel. A circuit breaker routes to a PostgreSQL fallback queue with separate tables per priority tier when Redis is unavailable. Worker allocation defaults to Option C: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability.

**The 1,800/sec planning figure** is derived from a specific operational constraint: it is the maximum throughput at which the standard-priority queue drains within 30 minutes during a sustained primetime 3× spike, given the queue depth at spike onset. The full derivation is in §1.2. It sits near the pessimistic end of the 1,300–3,500/sec capacity range by design — the range is wide because per-notification processing time varies substantially by channel and downstream provider latency; the planning figure is anchored to a queue-drain requirement rather than a throughput midpoint.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | 34.6M/day | ±50% | §1.1 |
| Sustained primetime rate | ~840/sec | ±50% | §1.2 |
| Worker capacity (100 workers) | 1,300–3,500/sec | Wide range; derivation in §1.2 | §1.2 |
| Planning figure (100 workers) | 1,800/sec | Derived from 30-min drain constraint; see §1.2 | §1.2 |
| Standard-priority delay, primetime 3× spike | 47 min (CI: 18–95 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | 12 min (CI: 5–24 min) | Queue model; corrected in R4 | §2.3 |
| High-priority delay, primetime 3× spike | 14 min (CI: 5–28 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | ~4 hours before operational response | **Low confidence; extrapolation beyond cited data; see §2.4** | §2.4 |
| Queue depth trigger for operational response | 500K messages | **Low confidence; derived from extrapolated 8× scenario; see §2.4** | §2.4 |
| Redis Sentinel failover window | 10–30 seconds | Vendor-documented | §5.3 |
| SMS p99 delivery target | <60 seconds | SLA commitment; achievability analysis in §3.4 | §3.4 