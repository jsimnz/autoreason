# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten problems identified in the prior review. The table below records each problem and its resolution. **This table makes no completeness claims. The document's content is the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | §0.3 scenario table truncated mid-cell | §0.3 table is complete. The truncated PostgreSQL-overloaded row is written out in full. |
| 2 | Morgan Singh has a proactive monitoring obligation with no defined trigger mechanism | §0.4 replaces the proactive-monitoring expectation with a defined system trigger: Confluence automation sends Morgan a direct notification at the moment Alex's window closes. Morgan's obligation is reactive, not proactive. |
| 3 | Jordan is told to escalate to Taylor for an alternative tiebreaker, but Taylor has no defined authority, no deadline, and no fallback | §0.1 replaces the open-ended escalation with a closed procedure: Jordan has 7 calendar days from document issue to request an alternative tiebreaker via Taylor. If no alternative is designated within those 7 days, the Alex-tiebreaker mechanism stands for the remainder of the window. The fallback is explicit. |
| 4 | No mechanism prevents or detects a manager substituting their own judgment instead of directing their report | §0.1 escalation procedure now specifies that any manager response that takes the form of a selection rather than a direction is treated as a direction to the report to make that selection. The report must then confirm or reject that direction. The manager's selection alone is not recorded as a decision input. |
| 5 | Load-testing parallelization claim is circular — "concurrent test scenarios" does not establish independence | §0.1 rework table replaces the 0.75-day parallelized estimate with 1.5 days (non-parallelizable) and explains why: the test scenarios share the same worker pool and queue infrastructure and cannot run concurrently without invalidating the isolation measurement. |
| 6 | "1.5-week delay to channel integration" has no derivation and references a staffing allocation table that does not exist | §0.1 replaces the derived figure with an explicit staffing assumption and a visible derivation. The staffing allocation is stated inline. |
| 7 | Decision B's mandatory §3.4 dependency may be unsatisfiable if §3.4 is absent when Alex reads the section | §0.2 now includes the relevant §3.4 content inline rather than by reference. Alex can satisfy the dependency without navigating to a separate section. |
| 8 | Tiebreak window can extend past day 14, but the document does not resolve whether the default fires at day 14 when a disagreement is logged on day 14 | §0.1 now states explicitly: the default does not fire while a tiebreak is pending. If a disagreement is logged before the 14-day window closes, the tiebreak window opens and the default is suspended until the tiebreak resolves or the tiebreak deadline passes without action, whichever comes first. |
| 9 | Both-managers-notified scenarios do not address conflicting manager directions | §0.1 escalation procedure now addresses this case: if both managers are notified and give conflicting directions, the resulting owner selections are treated as a live disagreement subject to the normal tiebreak procedure. The manager layer does not introduce a new tiebreaking authority. |
| 10 | Issue date field is blank at distribution, making the 14-day window indeterminate at the moment it begins | §0.4 resolves this by separating the issue date from the document body. The issue date is recorded in the Confluence page metadata at the time of the "final" marking, not in the document text. Decision owners are directed to the Confluence metadata for the authoritative timestamp. The document body contains a placeholder that is filled in by the distribution script, not by hand. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient.

**Issue date and authoritative timestamp.** The issue date is the timestamp recorded in the Confluence page metadata at the moment Alex applies the "final" marking. This timestamp is set by Confluence automatically and is not editable after the fact. Decision owners must not rely on the document body for the authoritative timestamp — they must check the Confluence page metadata directly. The document body contains the following placeholder, which the Confluence distribution automation fills in from the metadata timestamp at the moment of distribution:

> **Issue date: [FILLED AUTOMATICALLY FROM CONFLUENCE METADATA AT DISTRIBUTION — do not edit manually]**

If the automation fails and the placeholder is not filled, the Confluence metadata timestamp is still authoritative. A blank placeholder is a display defect, not an indication that no issue date exists.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution with a timestamp in the project record, within one business day of the document reaching final form.

**Backup mechanism.** If Alex has not logged distribution within one business day of the final-form timestamp, Morgan Singh [Alex's manager] takes over the distribution obligation. Morgan's window is triggered by a Confluence automation rule, not by proactive monitoring: when the "Distribution logged" checklist item (see below) remains unchecked one business day after the final-form timestamp, Confluence sends Morgan a direct notification stating that Alex's window has closed and Morgan's obligation has begun. Morgan's window begins at that notification, not at the moment Alex's window closed. Morgan must distribute and log within one additional business day of receiving the notification. If Morgan also fails to distribute within their window, the project record logs both non-performances and the matter escalates to the project steering committee. This is the only escalation that goes above the manager level.

**Detection mechanism.** The Confluence page for this document has a "Distribution logged" checklist item visible to all team members. This checklist item is the trigger for the Confluence automation rule described above. Any team member who observes that the checklist item is unchecked and believes the automation may have failed may notify Morgan Singh directly. This is not a formal obligation — it is a permitted action and a backup to the automation.

All references to "14 days" in this document mean 14 calendar days from the Confluence metadata timestamp recorded at final-form marking.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

**Default suspension rule.** If a disagreement between owners is logged before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreak resolves, or when the tiebreak deadline passes without action from the tiebreaker, whichever comes first. This rule exists to prevent the default from firing mid-tiebreak when both owners have responded and the decision is actively in process.

---

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL. **Requires approximately 0.5 additional engineer-weeks of permanent maintenance overhead relative to Option C.**

- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Option B is not achievable by one decision owner acting alone. It requires affirmative joint selection by both Jordan Rivera and Alex Chen. If either owner does not affirmatively select Option B, Option B is not implemented.** This constraint exists because Option B provides no priority isolation during failover, which is a product risk that requires both owners to consciously accept.

- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

---

**The joint sign-off must answer one explicit question:** *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes. Decision owners should read §0.3 before answering.

---

**Conflict of interest disclosure.** Alex Chen is the engineering lead who derived the rework cost estimates, authored the §0.3 interaction analysis, and whose operational preferences are reflected throughout this document. Alex is also the tiebreaker when Jordan and Alex disagree. Alex is not a neutral party. Decision owners should treat Alex's tiebreaking vote as a technically informed judgment from a non-neutral party, and Jordan Rivera in particular should understand that the tiebreaking mechanism gives Alex effective control over this decision in the event of disagreement.

**If Jordan believes this is unacceptable**, Jordan must request an alternative tiebreaking arrangement from Taylor Okonkwo [Jordan's manager] within 7 calendar days of the document issue date. Jordan and Taylor must designate an alternative tiebreaker and notify Alex Chen and Morgan Singh of the designation within those 7 days. If no alternative tiebreaker is designated and communicated to both parties within 7 calendar days of the issue date, the Alex-tiebreaker mechanism applies for the remainder of the 14-day window without further opportunity to object. This deadline is hard: a request initiated on day 8 or later is not actionable under this document.

No alternative tiebreaker is pre-designated here. Designating one is Jordan's and Taylor's responsibility, subject to the 7-day deadline above.

---

#### Rework Cost and Schedule Impact

An override of Option C after the implementation milestone in §7.1 (week 4) incurs approximately 1.9 engineer-weeks of rework. The table below shows engineer-week cost and calendar impact. Load testing is treated as non-parallelizable; the basis for this is explained in the table.

| Task | Engineer-Week Estimate | Basis | Calendar Impact (1 engineer) | Calendar Impact (2 engineers) |
|---|---|---|---|---|
| Decompose single worker pool into two process groups | 0.4 weeks (2 days) | New Supervisor config, process isolation testing, deployment pipeline changes for two targets instead of one | 2 days | 2 days (not parallelizable: single deployment pipeline) |
| Create separate Redis consumer groups per priority tier | 0.2 weeks (1 day) | Redis XGROUP commands; consumer group offset management; integration tests | 1 day | 1 day (not parallelizable: shared Redis state) |
| Rewrite worker dispatch logic from weighted-share to hard-isolated | 0.4 weeks (2 days) | Current dispatch logic assumes shared pool; priority routing must move to process-group assignment at enqueue time | 2 days | 2 days (not parallelizable: single dispatch codepath) |
| Update PostgreSQL fallback to match new process-group topology | 0.2 weeks (1 day) | Fallback currently uses polling discipline (Option C); must change to process-group-aware table assignment | 1 day | 1 day (not parallelizable: single fallback path) |
| Load testing of new topology under primetime 3× spike scenario | 0.3 weeks (1.5 days) | Cannot skip; isolation guarantee must be verified under load, not just in unit tests. **Not parallelizable:** the test scenarios share the same worker pool and queue infrastructure. Running two engineers' test scenarios concurrently would cause the workers from one scenario to interfere with the queue measurements from the other, invalidating the isolation measurement. The 1.5-day estimate assumes sequential execution of the required test scenarios. | 1.5 days | 1.5 days (not parallelizable: shared infrastructure) |
| Update monitoring and alerting for two process groups | 0.1 weeks (0.5 days) | Queue depth alerts, worker health checks, and on-call runbooks must be duplicated and differentiated | 0.5 days | 0.5 days (not parallelizable: single runbook author needed for consistency) |
| **Total** | **1.9 engineer-weeks** | | **8 calendar days** | **8 calendar days** |

**Schedule impact derivation.** This rework occurs in weeks 5–6 of the project if an override is requested after the week 4 milestone. During weeks 5–6, the staffing allocation is as follows based on the implementation plan in §7: Engineer 1 (queue infrastructure owner) is on channel integrations; Engineer 2 (channel integrations) is on channel integrations; Engineer 3 (monitoring and reliability) is on observability work; Engineer 4 (flexible) is supporting channel integrations. The rework tasks above fall primarily on Engineer 1 (process group decomposition, Redis consumer groups, dispatch logic, PostgreSQL fallback) and Engineer 3 (monitoring updates), with load testing requiring Engineer 1 and the test environment held by Engineer 4.

Displacing Engineer 1 for 7 of the 8 rework days during weeks 5–6 removes the primary channel integration contributor from that work for approximately 1.75 weeks of their individual schedule. Engineer 4 partially covers, but Engineer 4 is not the primary owner of channel integration and cannot substitute fully. The net delay to channel integration completion is estimated at **1.5 weeks**, derived as: 1.75 weeks of Engineer 1 displacement × 0.85 substitution shortfall (Engineer 4 covers approximately 15% of displaced work based on current task breakdown) = 1.49 weeks, rounded to 1.5 weeks. This estimate will be re-derived by Alex Chen at the time of any actual override request, because actual elapsed progress may differ from this projection.

---

#### Partial Response Deadlock Resolution

| Scenario | Resolution |
|---|---|
| Both owners respond and agree on Option A or Option C | That option is implemented. |
| Both owners respond and both select Option B | Option B is implemented. |
| Both owners respond; one selects Option A, one selects Option C | Disagreement is logged. Default is suspended per the default suspension rule above. Engineering lead [Alex Chen] has the tiebreaking vote (subject to any alternative tiebreaker designated within the 7-day window per the conflict of interest section). Alex must exercise the tiebreak within 3 business days of the disagreement being logged. If Alex does not act within 3 business days, Option C is implemented and both managers are notified per the escalation procedure below. |
| Both owners respond; one or both select Option B, but not both | Option C is implemented. Option B requires affirmative joint selection; a unilateral Option B selection is treated as no selection. The owner who selected Option B is notified that their selection was not implemented and why. |
| One owner responds; the other is silent after 14 days | The responding owner's choice is implemented if they selected Option A or Option C. If the responding owner selected Option B, Option C is implemented. The silent owner's manager is notified per the escalation procedure below. |
| Neither owner responds after 14 days | Option C is implemented. Both managers are notified per the escalation procedure below. |

---

#### Escalation Procedure When Managers Are Notified

This is not a recording mechanism. It is an active escalation with a required response.

When a manager [Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen] is notified, the notification must include: (a) the specific decision that was not made, (b) the default that will be implemented, (c) the implementation date, and (d) the question the manager must answer: *Do you accept the default, or are you directing your report to make an explicit selection?*

**The manager has 2 business days to respond.**

**Form of a valid manager response.** A manager response is valid only if it takes one of two forms: (1) "I accept the default," or (2) "I am directing [report name] to make an explicit selection." A manager response that takes the form of a direct selection — for example, "implement Option A" — is not a valid decision input. Such a response is treated as form (2): the manager is recorded as having directed their report to make that selection, and the report must then confirm or reject the selection within 1 business day. The report's confirmation or rejection is the decision input; the manager's statement of preference is not. This rule exists because managers are not decision owners for this decision and cannot substitute their judgment for that of the designated decision owner.

**Conflicting manager directions.** If both managers are notified simultaneously and give conflicting directions — for example, Taylor directs Jordan to select Option A and