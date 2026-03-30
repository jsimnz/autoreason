# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This synthesis resolves ten identified problems. **This table makes no completeness claims. The document's content is the authoritative record. If a section is missing, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | §3.4 referenced but absent; SMS achievability analysis deferred | §3.4 present in full. SMS direct-dispatch architecture and achievability analysis included inline. |
| 2 | Option B structurally unachievable but listed as live option without disclosure | §0.1 states at the top of the Option B description that it requires affirmative joint selection. It is not achievable by one owner acting alone. |
| 3 | Decision A joint sign-off had no deadlock resolution for partial response | §0.1 specifies behavior for all four partial-response combinations explicitly. |
| 4 | Alex Chen's tiebreaking vote creates unacknowledged conflict of interest | §0.1 acknowledges the conflict explicitly. The mechanism is retained because no neutral party with sufficient technical context is available, but the conflict is named. |
| 5 | 2 engineer-week rework cost for Option C override was a bare assertion | §0.1 contains the task-level derivation with schedule impact column. |
| 6 | Option A isolation guarantee collapses to Option C behavior when PostgreSQL is overloaded | §0.3 addresses this directly. The implication for the Option A vs. Option C choice is stated explicitly. |
| 7 | 500K queue depth trigger is low-confidence but used as operational threshold without addressing the failure mode of a wrong threshold | §2.4 applies explicit confidence degradation and specifies conservative bias and defined response to threshold error. |
| 8 | Document issue date had no backup distribution mechanism; single point of failure on Alex's non-performance | §0.4 adds a backup distribution owner (Morgan Singh) and a detection mechanism with explicit time bounds. |
| 9 | Manager escalation procedure was a recording mechanism, not an active escalation | §0.1 and §0.2 specify what managers must do, by when, and what happens if they do not act. |
| 10 | Asymmetric confidence interval on standard-priority primetime 3× delay was unexplained | §2.3 explains the source of asymmetry: heavy upper tail due to utilization approaching 1 during the spike. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the document issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. The timestamp on the Confluence "final" marking is the reference time for the one-business-day distribution obligation. If the two conditions are satisfied at different times, the later timestamp is the reference time.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution with a timestamp in the project record, within one business day of the document reaching final form.

**Backup mechanism.** If Alex has not logged distribution within one business day of the final-form timestamp, Morgan Singh [Alex's manager] automatically assumes the distribution obligation. Morgan must distribute and log within one additional business day. Morgan's window begins at the moment Alex's window closes, not at the moment Morgan is notified — Morgan is expected to monitor this proactively. If Morgan also fails to distribute within their window, the project record logs both non-performances and the matter escalates to the project steering committee. This is the only escalation that goes above the manager level.

**Detection mechanism.** The Confluence page for this document will have a "Distribution logged" checklist item visible to all team members. Any team member who observes that the checklist item is unchecked after one business day from the final-form timestamp may notify Morgan Singh directly. This is a permitted action, not a formal obligation.

**Issue date.** The issue date is recorded here at the time of distribution: **[ISSUE DATE — to be filled in at distribution, not before].**

All references to "14 days" in this document mean 14 calendar days from the logged issue date.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL. Requires approximately 0.5 additional engineer-weeks of permanent maintenance overhead relative to Option C.

- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Option B is not achievable by one decision owner acting alone. It requires affirmative joint selection by both Jordan Rivera and Alex Chen. If either owner does not affirmatively select Option B, Option B is not implemented.** This constraint exists because Option B provides no priority isolation during failover, which is a product risk that requires both owners to consciously accept.

- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**The joint sign-off must answer one explicit question:** *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes. Decision owners should read §0.3 before answering — the Option A isolation advantage is narrower than it appears, and §0.3 identifies the specific condition under which it is and is not real.

**Conflict of interest disclosure.** Alex Chen is the engineering lead who derived the rework cost estimates, authored the §0.3 interaction analysis, and whose operational preferences are reflected throughout this document. Alex is also the tiebreaker when Jordan and Alex disagree. Alex is not a neutral party. Jordan Rivera in particular should understand that the tiebreaking mechanism gives Alex effective control over this decision in the event of disagreement. If Jordan believes this is unacceptable, Jordan should escalate to Taylor Okonkwo [Jordan's manager] before the 14-day window closes to request a different tiebreaking arrangement. No alternative tiebreaker is designated in this document; designating one is Jordan's and Taylor's responsibility if they choose to do so.

#### Rework Cost and Schedule Impact

An override of Option C after the implementation milestone in §7.1 (week 4) incurs approximately 1.9 engineer-weeks of rework. This figure is derived from the following task list, not asserted:

| Task | Engineer-Week Estimate | Basis | Calendar Impact (1 engineer) | Calendar Impact (2 engineers, where parallelizable) |
|---|---|---|---|---|
| Decompose single worker pool into two process groups | 0.4 weeks (2 days) | New Supervisor config, process isolation testing, deployment pipeline changes for two targets instead of one | 2 days | 2 days (not parallelizable) |
| Create separate Redis consumer groups per priority tier | 0.2 weeks (1 day) | Redis XGROUP commands; consumer group offset management; integration tests | 1 day | 1 day (not parallelizable) |
| Rewrite worker dispatch logic from weighted-share to hard-isolated | 0.4 weeks (2 days) | Current dispatch logic assumes shared pool; priority routing must move to process-group assignment at enqueue time | 2 days | 2 days (not parallelizable) |
| Update PostgreSQL fallback to match new process-group topology | 0.2 weeks (1 day) | Fallback currently uses polling discipline (Option C); must change to process-group-aware table assignment | 1 day | 1 day (not parallelizable) |
| Load testing of new topology under primetime 3× spike scenario | 0.3 weeks (1.5 days) | Cannot skip; isolation guarantee must be verified under load, not just in unit tests | 1.5 days | 0.75 days (parallelizable) |
| Update monitoring and alerting for two process groups | 0.1 weeks (0.5 days) | Queue depth alerts, worker health checks, on-call runbooks must be duplicated and differentiated | 0.5 days | 0.5 days (not parallelizable) |
| **Total** | **1.9 engineer-weeks** | | **8 calendar days** | **7.25 calendar days** |

**Schedule impact interpretation.** On a 24-week project with 4 engineers, 1.9 engineer-weeks represents 2% of total team capacity. However, this rework occurs in weeks 5–6 when the team is also building channel integrations (§3). Displacing 8 calendar days of one engineer's time in that window delays channel integration work by approximately 1.5 weeks given current staffing allocations. The engineering lead will re-derive both figures at the time of any override request, because actual elapsed progress may differ from this projection.

#### Partial Response Deadlock Resolution

| Scenario | Resolution |
|---|---|
| Both owners respond and agree on Option A or Option C | That option is implemented. |
| Both owners respond and both select Option B | Option B is implemented. |
| Both owners respond; one selects Option A, one selects Option C | Engineering lead [Alex Chen] has the tiebreaking vote. See conflict of interest disclosure above. Alex must exercise the tiebreak within 3 business days of the disagreement being logged. If Alex does not act within 3 business days, Option C is implemented and both managers are notified per the escalation procedure below. |
| Both owners respond; one or both select Option B, but not both | Option C is implemented. Option B requires affirmative joint selection; a unilateral Option B selection is treated as no selection. The owner who selected Option B is notified that their selection was not implemented and why. |
| One owner responds; the other is silent after 14 days | The responding owner's choice is implemented if they selected Option A or Option C. If the responding owner selected Option B, Option C is implemented — Option B requires joint agreement. The silent owner's manager is notified per the escalation procedure below. |
| Neither owner responds after 14 days | Option C is implemented. Both managers are notified per the escalation procedure below. |

#### Escalation Procedure When Managers Are Notified

This is not a recording mechanism. It is an active escalation with a required response.

When a manager [Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen] is notified, the notification must include: (a) the specific decision that was not made, (b) the default that will be implemented, (c) the implementation date, and (d) the question the manager must answer: *Do you accept the default, or are you directing your report to make an explicit selection?*

**The manager has 2 business days to respond.** If the manager directs their report to make an explicit selection, that selection is treated as a new decision input from the decision owner — the manager cannot substitute their own judgment; they can only direct their report to act. If both owners have now selected, the normal agreement/disagreement rules above apply. If the manager does not respond within 2 business days, the default is implemented and the non-response is logged. No further escalation occurs — the default fires at this point regardless of organizational hierarchy above the manager level. The engineering lead [Alex Chen] is responsible for logging all outcomes and communicating them to the implementation team.

---

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead [Alex Chen].**

**Default if no explicit sign-off within 14 days of the issue date: Sentinel.**

**Rationale:** Operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The difference is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the practical delta is a 10–25 second increase in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel if it bypasses the standard queue path via direct dispatch. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional. Decision B cannot be finalized without reading §3.4.

**Escalation procedure for non-response:** If Alex does not respond within 14 days, Sentinel is implemented and Alex's manager [Morgan Singh] is notified with the same four-item notification content specified in §0.1. Morgan has 2 business days to direct Alex to make an explicit selection or accept the default. Morgan cannot substitute their own judgment; Morgan can only direct Alex to act. If Morgan does not respond, Sentinel is implemented and the non-response is logged. No further escalation occurs.

---

### 0.3 Interaction Analysis: Option A vs. Option C Under Failure Conditions

This section separates factual scenario analysis from the recommendation. The recommendation is explicitly conditioned on an unvalidated assumption stated at the end of this section.

#### Scenario Table

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× because absolute load is lower | Soft isolation; less severe than primetime 3× |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained unless PostgreSQL overloaded; SP queue unbounded | Both tiers unbounded | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, HP workers also queue in PostgreSQL — **behavior converges with Option C in this sub-case** | Both tiers queue in PostgreSQL together | HP queue drains first; SP accumulates |
| PostgreSQL fallback overloaded, Redis recovers | HP workers resume Redis processing immediately; SP workers follow | Both tiers resume Redis together | HP workers resume Redis first via polling discipline |

#### The PostgreSQL Overload Sub-Case and Its Implication

When PostgreSQL is overloaded *and* Redis is still down, Option A's isolation guarantee collapses to Option C's behavior: high-priority workers end up queuing in PostgreSQL alongside standard-priority workers because there is nowhere else to go. This is the most realistic concurrent failure mode during a combined spike-and-failover event — spikes are the most common cause of PostgreSQL overload, and spikes are also the most likely trigger for Redis failover due to connection exhaustion.

This means Option A's hard isolation guarantee is unavailable precisely when it is most needed. The isolation advantage of Option A over Option C exists only when: (a) Redis is down, (b) PostgreSQL is not overloaded, and (c) the load is sufficient to saturate a shared queue but not sufficient to saturate the PostgreSQL fallback. This is a narrow condition.

**Implication:** Option A is not worth its additional operational complexity (~0.5 engineer-weeks permanent maintenance overhead) if its primary advantage evaporates in the failure mode it is designed to handle. Option C's polling-discipline isolation is available in all scenarios where Option A's hard isolation is also available, and the two options behave identically in the PostgreSQL-overload sub-case.

**Unvalidated assumption this recommendation depends on:** The PostgreSQL overload sub-case is the most realistic concurrent failure mode only if PostgreSQL is not provisioned with substantial headroom specifically to handle failover load. **This assumption has not been validated against the team's actual PostgreSQL provisioning plan.** If PostgreSQL is provisioned with headroom sufficient to absorb a combined spike-and-failover event without overloading, Option A's advantage is real and the recommendation changes. Decision owners must state their PostgreSQL provisioning assumption explicitly when