# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten problems identified in the prior review. Each resolution is described below. **This table does not establish completeness and does not attempt to. The table is a navigation aid. The document's sections are the authoritative record. Verify completeness by reading the sections.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Alternative tiebreaker has no stated deadline to act; tiebreak window may extend past day 14 | §0.1 assigns the alternative tiebreaker the same 3-business-day window as Alex. The window starts from the same trigger: the moment disagreement is logged in Confluence per §0.5. The default suspension rule is updated to reference the alternative tiebreaker's deadline explicitly. |
| 2 | Confluence automation described as if it exists but has no verified existence; silent failure produces no backup | §0.4 adds a pre-distribution verification requirement: the automation must be tested before the document is marked final. Test record must be linked in Confluence. §0.4 also adds a human-readable daily check by Morgan Singh as a parallel non-automated backstop during the one-business-day window, eliminating sole dependence on the automation. |
| 3 | "One business day" undefined: no timezone, no calendar, no holiday rule | §0.4 defines the governing timezone (UTC), the governing holiday calendar (the project calendar maintained in Confluence), and the calculation method. All parties are bound by UTC regardless of their local timezone. |
| 4 | Conflict of interest remedy requires Jordan to act before having realistic opportunity to evaluate the effects | §0.1 extends Jordan's tiebreaker-objection window to 10 calendar days. The 7-day window was too short given the document's complexity. The 10-day window still fits within the 14-day decision window with margin. §0.1 also requires Alex to provide a written summary of the §0.3 analysis in plain language, delivered to Jordan at the time of distribution, so Jordan is not required to derive the technical implications independently. |
| 5 | Manager non-response when default is suspended by tiebreak: suspension rule and manager non-response rule unreconciled | §0.1 adds an explicit rule: if the default is suspended by a logged disagreement, manager non-response does not fire the default. The default remains suspended until the tiebreak resolves or the tiebreaker's deadline passes. Manager non-response in this state is logged and the non-response itself escalates to the project steering committee. The truncated sentence ("the default fires regardless") is completed. |
| 6 | 15% substitution figure unverifiable; task breakdown not included | §0.1 rework table adds a footnote citing the specific Confluence page and section where the task breakdown lives. The 15% figure is replaced with a range (10–20%) and the range bounds are explained. The 1.5-week estimate is restated as a range (1.4–1.75 weeks) consistent with the substitution range. |
| 7 | Tiebreaker selecting Option B is not a valid selection; tiebreak and Option B joint-selection constraint unreconciled | §0.1 partial-response table adds the missing scenario. A tiebreaker selecting Option B is treated as a selection of Option C, because Option B requires affirmative joint selection by both owners and the tiebreaker is not a joint owner. This rule is stated in the Option B description and in the tiebreak procedure. |
| 8 | "Distribution logged" checklist item has no access control; any team member can falsely check it | §0.4 restricts the checklist item to Alex Chen (write permission) and Morgan Singh (write permission for the backup obligation). All other team members have read-only access. The Confluence page permission configuration is specified and must be verified as part of the pre-distribution automation test. |
| 9 | Disagreement log has no neutral, independently verifiable mechanism; 3-business-day clock may never start | §0.5 (new section) defines the disagreement logging mechanism: a dedicated Confluence comment thread on this page, tagged with a defined label. Either owner may create the log entry. The entry is valid when it contains the required fields (see §0.5). The Confluence timestamp on the comment is the authoritative start of the 3-business-day tiebreak clock. Both owners and both managers receive an automated Confluence notification when a tagged entry is created. |
| 10 | Revision table asserts completeness while simultaneously disclaiming the assertion | The resolution entry for problem 1 in prior versions ("Document is complete. All sections present.") is removed. No completeness claim is made anywhere in this document. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. If the two conditions are satisfied at different times, the later timestamp is the reference time for all downstream obligations.

**Issue date and authoritative timestamp.** The issue date is the timestamp recorded in the Confluence page metadata at the moment Alex applies the "final" marking. This timestamp is set by Confluence automatically and is not editable after the fact. Decision owners must not rely on the document body for the authoritative timestamp — they must check the Confluence page metadata directly. The document body contains the following placeholder, which the Confluence distribution automation fills in from the metadata timestamp at the moment of distribution:

> **Issue date: [FILLED AUTOMATICALLY FROM CONFLUENCE METADATA AT DISTRIBUTION — do not edit manually]**

If the automation fails and the placeholder is not filled, the Confluence metadata timestamp is still authoritative. A blank placeholder is a display defect, not an indication that no issue date exists.

**Timezone and business day calendar.** All time calculations in this document use UTC. All parties are bound by UTC regardless of their local timezone or location. The governing holiday calendar is the project calendar maintained in the Confluence project space under "Project Calendar." A business day is any day that is not a Saturday, Sunday, or a holiday listed in that calendar. If a deadline falls on a non-business day, the deadline moves to the next business day. The project calendar is maintained by the project coordinator and is the sole reference for holiday determinations; local or national calendars do not govern unless they are reflected in the project calendar.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution by checking the "Distribution logged" checklist item (see below) within one business day (UTC, project calendar) of the document reaching final form.

**Checklist item access control.** The "Distribution logged" checklist item on this Confluence page has restricted write access. Only Alex Chen and Morgan Singh may check or uncheck it. All other team members have read-only access to the checklist item. This permission configuration must be verified as part of the pre-distribution automation test described below. A check by any other party is invalid and must be reported to Morgan Singh immediately.

**Pre-distribution automation verification.** Before Alex marks this document as final, Alex must test the Confluence automation rule described below by triggering it in a test environment or staging page. The test must confirm: (a) the automation fires when the checklist item remains unchecked after the specified interval, (b) Morgan Singh receives the notification, and (c) the checklist item access restrictions are enforced. Alex must link the test record in the Confluence page comments before applying the "final" marking. If the test cannot be completed, Alex must notify Morgan Singh before marking the document final, and Morgan Singh must acknowledge the notification. A document marked final without a linked test record or Morgan's acknowledgment of a test failure is a process defect; it does not invalidate the final-form timestamp, but it must be logged.

**Backup mechanism — automated layer.** When the "Distribution logged" checklist item remains unchecked one business day (UTC, project calendar) after the final-form timestamp, a Confluence automation rule sends Morgan Singh a direct notification stating that Alex's distribution window has closed and Morgan's obligation has begun. Morgan's obligation window begins at the timestamp of that notification.

**Backup mechanism — human layer.** Because the automated layer may fail despite pre-distribution testing, Morgan Singh must also perform a direct check: Morgan must look at the "Distribution logged" checklist item once per business day during the one-business-day window following the final-form timestamp. This is a formal obligation, not a permitted action. If Morgan observes the checklist item is unchecked and the one-business-day window has closed, Morgan's distribution obligation begins immediately regardless of whether the automation has fired. Morgan does not need to wait for an automated notification to begin their obligation if they have independently observed the trigger condition.

**Morgan's distribution window.** Morgan must distribute and log within one additional business day (UTC, project calendar) of Morgan's obligation beginning — whether that beginning is triggered by the automation or by Morgan's own observation. If Morgan also fails to distribute within their window, the project record logs both non-performances and the matter escalates to the project steering committee.

All references to "14 days" in this document mean 14 calendar days from the Confluence metadata timestamp recorded at final-form marking, measured in UTC.

---

### 0.5 Disagreement Logging Mechanism

**Purpose.** The 3-business-day tiebreak clock and the default suspension rule both depend on a disagreement being "logged." This section defines what a valid log entry is and how the clock starts.

**Logging location.** Disagreements are logged as comments in the dedicated comment thread on this Confluence page. The thread is labeled with the tag `[DECISION-DISAGREEMENT]`. Either decision owner may create a log entry. A log entry is valid when it contains all of the following fields:

- Decision identifier (e.g., "Decision A: Worker Allocation Strategy")
- The logging owner's name and role
- The logging owner's stated selection
- A statement that the other owner has communicated a conflicting selection, or that the logging owner believes a conflicting selection exists and has not been resolved

**Authoritative timestamp.** The Confluence comment timestamp (UTC) on a valid log entry is the authoritative start of the 3-business-day tiebreak clock. Neither owner may dispute the timestamp by claiming a different time of awareness.

**Automated notification.** When a comment tagged `[DECISION-DISAGREEMENT]` is created on this page, a Confluence automation rule sends a notification to both decision owners and both managers (Taylor Okonkwo and Morgan Singh). This notification is informational — it does not start any manager obligation. Manager obligations begin only as described in the escalation procedure in §0.1.

**Disputed validity.** If a decision owner believes a log entry is invalid (e.g., missing required fields), they must raise the dispute in the same comment thread within one business day (UTC, project calendar) of receiving the automated notification. Morgan Singh adjudicates disputes about log entry validity. Morgan's adjudication is final for purposes of determining whether the clock has started.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

**Default suspension rule.** If a disagreement between owners is logged in Confluence per §0.5 before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreaker acts, or when the tiebreaker's 3-business-day deadline passes without action, whichever comes first. This rule applies regardless of whether managers have been notified and regardless of whether managers have responded. If the default is suspended and both managers are notified and both managers fail to respond within their 2-business-day windows, the default remains suspended; it does not fire due to manager non-response. Manager non-response in this state is logged and escalates to the project steering committee as a separate matter. The default fires only when the tiebreak resolves or the tiebreaker's deadline passes.

---

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL. **Requires approximately 0.5 additional engineer-weeks of permanent maintenance overhead relative to Option C.**

- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Option B is not achievable by one decision owner acting alone. It requires affirmative joint selection by both Jordan Rivera and Alex Chen. If either owner does not affirmatively select Option B, Option B is not implemented.** A tiebreaker selecting Option B is treated as a selection of Option C, because a tiebreaker acts alone and Option B requires joint owner selection. This rule applies to Alex Chen acting as tiebreaker and to any alternative tiebreaker designated under the conflict of interest procedure below. **This constraint exists because Option B provides no priority isolation during failover, which is a product risk that requires both owners to consciously accept.**

- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

---

**The joint sign-off must answer one explicit question:** *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes. Decision owners should read §0.3 before answering — the Option A isolation advantage is narrower than it appears, and §0.3 identifies the specific condition under which it is and is not real.

**Plain-language summary obligation.** Because §0.3 is technically complex and Jordan's evaluation window runs concurrently with the tiebreaker-objection window, Alex Chen must deliver a plain-language written summary of the §0.3 analysis to Jordan Rivera at the time of document distribution. The summary must state, in non-technical language: (a) the specific condition under which Option A provides a real isolation advantage over Option C, (b) the specific condition under which it does not, and (c) Alex's recommendation and the reasoning behind it. The summary is advisory; Jordan is not bound by it. Its purpose is to ensure Jordan has a usable starting point for evaluating the decision without first having to decode the technical analysis independently.

---

**Conflict of interest disclosure.** Alex Chen is the engineering lead who derived the rework cost estimates, authored the §0.3 interaction analysis, and whose operational preferences are reflected throughout this document. Alex is also the default tiebreaker when Jordan and Alex disagree. Alex is not a neutral party. Decision owners should treat Alex's tiebreaking vote as a technically informed judgment from a non-neutral party, and Jordan Rivera in particular should understand that the tiebreaking mechanism gives Alex effective control over this decision in the event of disagreement.

**If Jordan believes this is unacceptable**, Jordan must request an alternative tiebreaking arrangement from Taylor Okonkwo [Jordan's manager] within **10 calendar days** of the document issue date. Jordan and Taylor must designate an alternative tiebreaker and notify Alex Chen and Morgan Singh of the designation within those 10 days. If no alternative tiebreaker is designated and communicated to both parties within 10 calendar days of the issue date, the Alex-tiebreaker mechanism applies for the remainder of the 14-day window without further opportunity to object. This deadline is hard: a request initiated on day 11 or later is not actionable under this document.

**The 10-day window is intentional.** It replaces the prior 7-day window. The change exists because Jordan must read and evaluate a technically complex document — including the §0.3 interaction analysis and the plain-language summary — before being in a position to judge whether Alex's role as tiebreaker is problematic. A 7-day window was insufficient given the document's complexity. The 10-day window provides meaningful evaluation time while still fitting within the 14-day decision window with a 4-day margin before the default fires.

**Alternative tiebreaker deadline.** An alternative tiebreaker, once designated, has the same 3-business-day window to act as Alex Chen. The 3-business-day clock starts from the moment disagreement is logged per §0.5 — not from the moment the alternative tiebreaker is designated. If the alternative tiebreaker is designated after disagreement is already logged, the 3-business-day clock is already running. If fewer than 3 business days remain when the alternative tiebreaker is designated, the alternative tiebreaker must act within the remaining time. Jordan and Taylor must account for this when deciding how quickly to designate an alternative tiebreaker after a disagreement is logged. An alternative tiebreaker who cannot act within the remaining window must notify both owners and both managers immediately, at which point Option C is implemented and the failure is logged.

---

#### Rework Cost and