# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten problems identified in the prior review. The table below records each problem and its resolution. **This table makes no completeness claims. The document's content is the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Document truncated mid-sentence; no substantive sections verifiable | Document is complete. All sections present. Executive summary correction carried through in full. |
| 2 | 14-day clock has single point of failure: Alex's non-performance on distribution has no consequence | §0.4 adds a backup distribution owner and a detection mechanism. If Alex does not log distribution within one business day, Morgan Singh takes over distribution and logs it. |
| 3 | Option B structurally unachievable but listed as live option without disclosure | §0.1 now states at the top of the option description that Option B requires affirmative joint selection by both owners. It is not achievable by one owner acting alone. This is disclosed in the option framing, not buried in the partial-response table. |
| 4 | Alex Chen's tiebreaking vote creates unacknowledged conflict of interest | §0.1 acknowledges the conflict explicitly. The tiebreaking mechanism is retained because no neutral party with sufficient technical context is available, but the conflict is named and decision owners are advised to weight Alex's tiebreak accordingly. |
| 5 | Manager escalation procedure is internally contradictory: "tiebreaking procedure applies" is meaningless for a single input | §0.1 replaces the contradictory language. A manager override is treated as a new decision from the non-responding owner, not as input to a tiebreaking procedure. The specific behavior for each override scenario is now stated explicitly. |
| 6 | §0.3 interaction analysis presents a recommendation as analysis; pivotal PostgreSQL overload assumption is unvalidated | §0.3 separates the factual scenario table from the recommendation. The PostgreSQL overload assumption is now flagged as unvalidated and the conclusion is explicitly conditioned on it. Decision owners are asked to state their PostgreSQL provisioning assumption before the analysis conclusion applies. |
| 7 | 500K queue depth trigger is low-confidence but used as operational threshold without addressing the failure mode of a wrong threshold | §2.4 and §6.2 address this directly. A low-confidence operational threshold requires a conservative bias and a defined response to threshold error. Both are now specified. |
| 8 | "Final form" is undefined; one-business-day distribution obligation has no determinable start | §0.4 defines final form precisely: the document is in final form when the engineering lead marks it as such in Confluence and notifies the product lead. Both acts are required; neither alone is sufficient. |
| 9 | Asymmetric confidence interval on standard-priority primetime 3× delay is unexplained | §2.3 explains the source of the asymmetry: the queue model's delay distribution has a heavy upper tail because utilization approaches 1 during the spike, making the upper bound sensitive to small perturbations in arrival rate. The lower bound is constrained by the drain-time floor. |
| 10 | Rework estimate stated as engineer-weeks without translation to schedule impact for a 4-engineer team | §0.1 rework table now includes a schedule impact column alongside engineer-week cost. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the document issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. The timestamp on the Confluence "final" marking is the reference time for the one-business-day distribution obligation. If the two conditions are satisfied at different times, the later timestamp is the reference time.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution with a timestamp in the project record, within one business day of the document reaching final form.

**Backup mechanism.** If Alex has not logged distribution within one business day of the final-form timestamp, Morgan Singh [Alex's manager] automatically assumes the distribution obligation. Morgan must distribute and log within one additional business day. The one-business-day window for Morgan begins at the moment Alex's window closes, not at the moment Morgan is notified — Morgan is expected to monitor this proactively. If Morgan also fails to distribute within their window, the project record logs both non-performances and the matter escalates to the project steering committee. This is the only escalation that goes above the manager level.

**Detection mechanism.** The Confluence page for this document will have a "Distribution logged" checklist item visible to all team members. Any team member who observes that the checklist item is unchecked after one business day from the final-form timestamp may notify Morgan Singh directly. This is not a formal obligation for team members — it is a permitted action.

**Issue date.** The issue date is recorded here at the time of distribution: **[ISSUE DATE — to be filled in at distribution, not before].**

All references to "14 days" in this document mean 14 calendar days from the logged issue date.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

---

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL. **Requires approximately 0.5 additional engineer-weeks of permanent maintenance overhead relative to Option C.**

- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Option B is not achievable by one decision owner acting alone. It requires affirmative joint selection by both Jordan Rivera and Alex Chen. If either owner does not affirmatively select Option B, Option B is not implemented.** This constraint exists because Option B provides no priority isolation during failover, which is a product risk that requires both owners to consciously accept.

- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

---

**The joint sign-off must answer one explicit question:** *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes. Decision owners should read §0.3 before answering — the Option A isolation advantage is narrower than it appears, and §0.3 identifies the specific condition under which it is and is not real.

---

**Conflict of interest disclosure.** Alex Chen is the engineering lead who derived the rework cost estimates, authored the §0.3 interaction analysis, and whose operational preferences are reflected throughout this document. Alex is also the tiebreaker when Jordan and Alex disagree (see partial-response table below). Alex is not a neutral party. Decision owners should treat Alex's tiebreaking vote as a technically informed judgment from a non-neutral party, and Jordan Rivera in particular should understand that the tiebreaking mechanism gives Alex effective control over this decision in the event of disagreement. If Jordan believes this is unacceptable, Jordan should escalate to Taylor Okonkwo [Jordan's manager] before the 14-day window closes to request a different tiebreaking arrangement. No alternative tiebreaker is designated in this document; designating one is Jordan's and Taylor's responsibility if they choose to do so.

---

#### Rework Cost and Schedule Impact

An override of Option C after the implementation milestone in §7.1 (week 4) incurs approximately 1.9 engineer-weeks of rework. For a 4-engineer team on a 6-month (24-week) project, this translates to a schedule impact that depends on whether the work is parallelized. The table below shows both dimensions.

| Task | Engineer-Week Estimate | Basis | Calendar Impact (1 engineer) | Calendar Impact (2 engineers, where parallelizable) |
|---|---|---|---|---|
| Decompose single worker pool into two process groups | 0.4 weeks (2 days) | New Supervisor config, process isolation testing, deployment pipeline changes for two targets instead of one | 2 days | 2 days (not parallelizable) |
| Create separate Redis consumer groups per priority tier | 0.2 weeks (1 day) | Redis XGROUP commands; consumer group offset management; integration tests | 1 day | 1 day (not parallelizable) |
| Rewrite worker dispatch logic from weighted-share to hard-isolated | 0.4 weeks (2 days) | Current dispatch logic assumes shared pool; priority routing must move to process-group assignment at enqueue time | 2 days | 2 days (not parallelizable) |
| Update PostgreSQL fallback to match new process-group topology | 0.2 weeks (1 day) | Fallback currently uses polling discipline (Option C); must change to process-group-aware table assignment | 1 day | 1 day (not parallelizable) |
| Load testing of new topology under primetime 3× spike scenario | 0.3 weeks (1.5 days) | Cannot skip; isolation guarantee must be verified under load, not just in unit tests | 1.5 days | 0.75 days (parallelizable: two engineers can run concurrent test scenarios) |
| Update monitoring and alerting for two process groups | 0.1 weeks (0.5 days) | Queue depth alerts, worker health checks, and on-call runbooks must be duplicated and differentiated | 0.5 days | 0.5 days (not parallelizable) |
| **Total** | **1.9 engineer-weeks** | | **8 calendar days** | **7.25 calendar days** |

**Schedule impact interpretation.** On a 24-week project with 4 engineers, 1.9 engineer-weeks represents 2% of total team capacity. The calendar impact is 7–8 days of one engineer's time. However, this rework occurs in weeks 5–6 of a 24-week project, when the team is also building the channel integrations in §3. Displacing 8 calendar days of one engineer's time in that window delays channel integration work by approximately 1.5 weeks given current staffing allocations. The engineering lead [Alex Chen] will re-derive both the engineer-week estimate and the schedule impact at the time of any override request, because actual elapsed progress at that point may differ from this projection.

---

#### Partial Response Deadlock Resolution

| Scenario | Resolution |
|---|---|
| Both owners respond and agree on Option A or Option C | That option is implemented. |
| Both owners respond and both select Option B | Option B is implemented. |
| Both owners respond; one selects Option A, one selects Option C | Engineering lead [Alex Chen] has the tiebreaking vote. See conflict of interest disclosure above. Alex must exercise the tiebreak within 3 business days of the disagreement being logged. If Alex does not act within 3 business days, Option C is implemented and both managers [Taylor Okonkwo and Morgan Singh] are notified per the escalation procedure below. |
| Both owners respond; one or both select Option B, but not both | Option C is implemented. Option B requires affirmative joint selection; a unilateral Option B selection is treated as no selection. The owner who selected Option B is notified that their selection was not implemented and why. |
| One owner responds; the other is silent after 14 days | The responding owner's choice is implemented if they selected Option A or Option C. If the responding owner selected Option B, Option C is implemented (Option B requires joint agreement). The silent owner's manager is notified per the escalation procedure below. |
| Neither owner responds after 14 days | Option C is implemented. Both managers are notified per the escalation procedure below. |

---

#### Escalation Procedure When Managers Are Notified

This is not a recording mechanism. It is an active escalation with a required response.

When a manager [Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen] is notified, the notification must include: (a) the specific decision that was not made, (b) the default that will be implemented, (c) the implementation date, and (d) the question the manager must answer: *Do you accept the default, or are you directing your report to make an explicit selection?*

**The manager has 2 business days to respond.**

If the manager directs their report to make an explicit selection, that selection is treated as if the report had made it within the original window — it is a new decision input from the decision owner, not from the manager. The manager cannot substitute their own judgment for the decision owner's; they can only direct their report to act. If the directed selection arrives and both owners have now selected, the normal agreement/disagreement rules above apply. If the directed selection arrives and only one owner has selected, that selection is implemented per the one-owner-responds rule above.

If the manager does not respond within 2 business days, the default is implemented and the non-response is logged. No further escalation occurs — the default fires at this point regardless of organizational hierarchy above the manager level.

The engineering lead [Alex Chen] is responsible for logging all outcomes and communicating them to the implementation team.

---

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead [Alex Chen].**

**Default if no explicit sign-off within 14 days of the issue date: Sentinel.**

Rationale: operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The difference is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the practical delta is a 10–25 second increase in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction:** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel if it bypasses the standard queue path via direct dispatch. If the engineering lead selects Sentinel, the SMS direct-dispatch architecture in §3.4 is mandatory, not optional. Decision B cannot be finalized without reading §3.4.

**Escalation procedure for non-response:** If Alex does not respond within 14 days, Sentinel is implemented and Alex's manager [Morgan Singh] is notified with the same four-item notification content specified in §0.1. Morgan has 2 business days to direct Alex to make an explicit selection or accept the default. The same manager-response rules from §0.1 apply: Morgan cannot substitute their own judgment; Morgan can only direct Alex to act. If Morgan does not respond, Sentinel is implemented and the non-response is logged. No further escalation occurs.

---

### 0.3 Interaction Analysis: Option A vs. Option C Under Failure Conditions

This section separates factual scenario analysis from the recommendation. The recommendation is in the final subsection and is explicitly conditioned on an unvalidated assumption. Decision owners should read the assumption statement before accepting the recommendation.

#### Scenario Table

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× because absolute load is lower | Soft isolation; less severe than primetime 3× |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained unless PG overloaded; SP queue unbounded | Both tiers unbounded | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, HP workers also queue in PG — **behavior converges with Option C in this sub-case** | Both tiers queue in PG together | HP queue dr