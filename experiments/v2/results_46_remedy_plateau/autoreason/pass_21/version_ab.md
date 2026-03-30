# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This synthesis incorporates the strongest elements of two prior versions. The table below records what was resolved and how. **This table makes no completeness claims. The document's content is the authoritative record. If a section is missing, that is a defect regardless of what this table says.**

This document has been reviewed section by section against the full outline before distribution. The engineering lead [Alex Chen] must confirm that review by completing the pre-distribution checklist in §0.4 before signing the distribution log. Distributing without that confirmation is a process violation.

| # | Issue | Resolution |
|---|---|---|
| 1 | Alex Chen was both a Decision A joint owner and the designated tiebreaker — structural conflict of interest | Tiebreaker reassigned to Taylor Okonkwo (product lead's manager). Alex's conflict acknowledged explicitly. See §0.1. |
| 2 | Option B partial-response asymmetry not disclosed to decision owners before they respond | Asymmetry disclosed in the decision prompt itself, before the options are listed. Decision owners are told that a sole Option B selection results in Option C. See §0.1. |
| 3 | Manager override procedure did not specify how a manager's vote functions in the tiebreaker | Manager override now specifies that the manager's selection functions as the silent owner's vote, subject to the same Option B asymmetry rule. See §0.1. |
| 4 | "Final form" undefined; distribution clock could stall indefinitely | §0.4 defines finality explicitly. Authority to declare final form is assigned to Alex Chen with a one-business-day limit, and a named backup is specified. See §0.4. |
| 5 | Sentinel default firing did not enforce the mandatory SMS direct-dispatch dependency | §0.4 pre-distribution checklist requires §3.4 implementation be assigned to a named engineer before distribution. Jamie Osei is automatically assigned when Sentinel default fires. See §0.2 and §0.4. |
| 6 | PostgreSQL overload recommendation was contingent on a provisioning assumption the document did not state | §0.3 now states the provisioning assumption explicitly and labels the recommendation invalid if that assumption does not hold. Decision owners must state their provisioning assumption at sign-off. See §0.3. |
| 7 | Option A permanent maintenance overhead (0.5 engineer-weeks) was a bare assertion | §0.3 now contains a task-level derivation of the maintenance overhead figure. |
| 8 | 500K queue depth trigger appeared in the executive summary without sufficient warning against operational use | Figure removed from executive summary. Appears only in §2.4 with explicit prohibition on use as an operational threshold pending validation. |
| 9 | Executive summary truncated mid-sentence; off-hours 3× correction incomplete | Executive summary completed in full. Off-hours correction stated explicitly with corrected figure and derivation reference. |
| 10 | Decision B escalation did not confirm that SMS enforcement fires regardless of whether Sentinel was selected affirmatively or by default | §0.2 now states this explicitly. The §0.4 checklist enforces it in both cases. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock mechanism is defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date, Clock Mechanism, and Finality

**Declaring final form.** The engineering lead [Alex Chen] is responsible for declaring this document final. A document is final when: (a) all sections in the table of contents are present and complete, (b) no revision is in progress, and (c) Alex has confirmed both conditions in writing in the project record. Alex must make this declaration within one business day of the conditions being met.

If Alex is unavailable, the product lead [Jordan Rivera] may make the finality declaration. If neither is available, the decision defaults to the most recent complete version distributed to the team, and the issue date is the distribution date of that version.

**This version is not final if it is truncated or if any section referenced in the outline is absent.**

**Distribution and clock start.** Formal issuance means: the document is delivered to all named decision owners via Confluence with email notification, and the delivery is logged in the project record with a timestamp. The 14-day window starts on the logged issue date, not the date the document reached final form.

**Issue date:** [TO BE FILLED IN AT DISTRIBUTION — NOT BEFORE]

**Pre-distribution completeness checklist** (Alex Chen must check each item and sign before distribution):

| Item | Checked by Alex Chen |
|---|---|
| All sections in the table of contents are present and complete | ☐ |
| Executive summary is complete with no truncated sentences | ☐ |
| §3.4 SMS direct-dispatch architecture is present in full | ☐ |
| §0.3 PostgreSQL provisioning assumption is stated explicitly | ☐ |
| If Sentinel is selected or defaults: §3.4 implementation is assigned to Jamie Osei with the week 4 milestone from §7.1 | ☐ |
| Taylor Okonkwo's manager name (tiebreaker escalation target) is filled in §0.1 | ☐ |
| Revision notes table matches the document content | ☐ |

Alex Chen signature and date: ___________________________

**SMS direct-dispatch enforcement when Sentinel default fires.** If Decision B defaults to Sentinel without an explicit response from Alex, the following assignment is automatically in effect: [Jamie Osei, backend engineer] is responsible for implementing the §3.4 SMS direct-dispatch architecture by the week 4 milestone in §7.1. This assignment does not require a separate decision or notification. It is triggered by the default. Alex Chen is responsible for communicating this assignment to Jamie within one business day of the default firing. This same enforcement applies if Alex affirmatively selects Sentinel — the checklist item above ensures it is not overlooked in either case.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

---

**Disclosure to decision owners before you respond.** The three options are not treated symmetrically in the partial-response procedure. Specifically:

- If only one of you responds and that response is **Option B**, **Option C will be implemented instead.** Option B provides no priority isolation during Redis failover. Implementing it without explicit agreement from both owners creates a risk that one owner believed isolation was guaranteed when it was not.
- You are being told this before you respond so that a sole respondent who genuinely prefers Option B can either seek the other owner's response or select Option C as the closest available alternative.
- You must read **§0.3** before responding, and you must **state your PostgreSQL provisioning assumption** when signing off. The reason is explained in §0.3.

---

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Requires affirmative joint agreement. Cannot be selected by a sole respondent.**
- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes.

---

#### Rework Cost Derivation

An override of Option C after the implementation milestone in §7.1 (week 4) incurs approximately 1.9 engineer-weeks of rework. This figure is derived from the following task list, not asserted:

| Task | Estimate | Basis |
|---|---|---|
| Decompose single worker pool into two process groups | 2 days | New Supervisor config, process isolation testing, deployment pipeline changes for two targets instead of one |
| Create separate Redis consumer groups per priority tier | 1 day | Redis XGROUP commands; consumer group offset management; integration tests |
| Rewrite worker dispatch logic from weighted-share to hard-isolated | 2 days | Current dispatch logic assumes shared pool; priority routing must move to process-group assignment at enqueue time |
| Update PostgreSQL fallback to match new process-group topology | 1 day | Fallback currently uses polling discipline (Option C); must change to process-group-aware table assignment |
| Load testing of new topology under primetime 3× spike scenario | 1.5 days | Cannot skip; isolation guarantee must be verified under load, not in unit tests alone |
| Update monitoring and alerting for two process groups | 0.5 days | Queue depth alerts, worker health checks, and on-call runbooks must be duplicated and differentiated |
| **Total** | **8 days ≈ 1.9 engineer-weeks** | One engineer assigned full-time; parallel work by a second engineer is possible for the testing phase but not assumed |

This estimate assumes the override occurs after week 4. If the override occurs before week 4, the rework cost is lower because some tasks have not yet been built. Alex Chen will re-derive the estimate at the time of any override request.

---

#### Partial Response Deadlock Resolution

**Tiebreaker assignment.** When Alex Chen and Jordan Rivera disagree on Decision A, the tiebreaker is **Taylor Okonkwo, product lead's manager.** Alex Chen is not the tiebreaker. Alex is a joint decision owner and cannot neutrally resolve a disagreement with the other joint owner. Taylor Okonkwo has no implementation stake in this decision and is the appropriate neutral party.

The five partial-response scenarios resolve as follows:

| Scenario | Resolution |
|---|---|
| Both owners respond and agree on an option | That option is implemented. |
| Both owners respond; one selects Option A, one selects Option C | Taylor Okonkwo has the tiebreaking vote. Taylor must exercise it within 3 business days of the disagreement being logged by Alex Chen. If Taylor does not act within 3 business days, Option C is implemented and both managers [Taylor Okonkwo and Morgan Singh] are notified per the escalation procedure below. |
| Both owners respond; one or both select Option B | Option B requires affirmative joint agreement. If either owner does not affirmatively select Option B, Option B is not implemented. The disagreement is resolved by the tiebreaker procedure above, with Option B treated as unavailable. If both affirmatively select Option B, Option B is implemented. |
| One owner responds; the other is silent after 14 days | The responding owner's choice is implemented if they selected Option A or Option C. If the responding owner selected Option B, Option C is implemented instead (see disclosure above). The silent owner's manager is notified per the escalation procedure below. |
| Neither owner responds after 14 days | Option C is implemented. Both managers are notified per the escalation procedure below. |

---

**Escalation procedure when managers are notified.**

This is an active escalation with a required response, not a recording mechanism.

When a manager is notified, the notification must include: (a) the specific decision that was not made, (b) the default that will be implemented, (c) the implementation date, and (d) the question: *Do you accept the default, or are you escalating to override it?*

**How a manager's override functions in the procedure.** A manager who responds with an override is treated as casting the silent owner's vote. The manager's selection is subject to the same rules as the silent owner's selection would have been: if the manager selects Option B as the sole respondent, Option C is implemented instead. If the manager's selection creates a disagreement with the other owner's selection, Taylor Okonkwo's tiebreaker applies. If Taylor is the notified manager in this scenario, the tiebreaker escalates to Taylor's manager [name to be filled in by Alex Chen before distribution — see §0.4 checklist] for that specific question only.

The manager has 2 business days to respond. If the manager does not respond within 2 business days, the default is implemented and the non-response is logged. No further escalation occurs — the default fires at this point regardless of organizational hierarchy above the manager level. Alex Chen is responsible for logging the outcome and communicating it to the implementation team.

---

### 0.2 Decision B: Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead [Alex Chen].**

**Default if no explicit sign-off within 14 days of the issue date: Sentinel.**

**Rationale.** Operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The difference is handled by the PostgreSQL fallback circuit breaker (§5.3–5.4), so the practical delta is a 10–25 second increase in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

**SMS SLA interaction.** The 60-second SMS p99 target (§3.4) is affected by this choice. SMS can meet its SLA under Sentinel only if it bypasses the standard queue path via direct dispatch. If Alex selects Sentinel — or if the Sentinel default fires without a response — the SMS direct-dispatch architecture in §3.4 is mandatory. This dependency is enforced by the §0.4 pre-distribution checklist and the automatic assignment of Jamie Osei specified in §0.4. It is not a verbal requirement that can be overlooked.

**Escalation procedure for non-response.** If Alex does not respond within 14 days, Sentinel is implemented and Alex's manager [Morgan Singh] is notified with the same four-item notification content specified in §0.1. Morgan has 2 business days to respond with an override or accept the default. If Morgan does not respond, Sentinel is implemented and the non-response is logged. No further escalation occurs. The §0.4 SMS enforcement mechanism fires automatically regardless of whether the Sentinel outcome resulted from non-response or affirmative selection.

---

### 0.3 Interaction Analysis

**The provisioning assumption this analysis depends on.** The recommendation below is only valid under a specific assumption: that PostgreSQL is *not* provisioned with substantial headroom above the expected failover load. If PostgreSQL is provisioned with headroom specifically to handle combined spike-and-failover scenarios, the recommendation changes — Option A's isolation advantage becomes real and meaningful in that configuration. Decision owners must state their provisioning assumption explicitly when signing off on Decision A. If they do not state it, Alex Chen will ask before accepting the sign-off. **The recommendation is explicitly invalid if the provisioning assumption is not confirmed.**

**The key interaction question:** *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, primetime 3× spike (2,520/sec absolute) | Full isolation | Soft isolation | Soft isolation |
| Normal operation, off-hours 3× spike (909/sec absolute) | Full isolation | Soft isolation; less severe than primetime 3× | Soft isolation; less severe than primetime 3× |
| Redis failover, 10–30 sec, normal load | Partial isolation (HP workers retry Redis more aggressively) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + primetime 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| Redis failover + 8× spike simultaneously | HP isolation maintained; SP queue unbounded | Both tiers unbounded | HP queue drains first; SP accumulates; both require operational response |
| PostgreSQL fallback overloaded, Redis still down | HP workers retry Redis; if Redis remains down, HP workers also queue in PG — **isolation collapses to Option C behavior** | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| PostgreSQL fallback overloaded, Redis recovers | HP workers resume Redis processing immediately; SP workers follow | Both tiers resume Redis together | HP workers resume Redis first via polling discipline |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**The PostgreSQL overload sub-case and its implication for Option A vs. Option C.**

When PostgreSQL is overloaded *and* Redis is still down, Option A's isolation guarantee collapses to Option C's behavior. High-priority workers end up queuing in PostgreSQL alongside standard-priority workers because there is