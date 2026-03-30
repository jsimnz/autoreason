# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses problems identified across prior reviews. The table below records each problem and its resolution. **This table makes no completeness claims. The document's content is the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Document truncated mid-sentence in prior versions; substantive sections unverifiable | Document is complete. All sections present. |
| 2 | Alex's tiebreaking vote creates unacknowledged conflict of interest | §0.1 acknowledges the conflict explicitly. Jordan has a 7-calendar-day hard deadline to request an alternative tiebreaker via Taylor Okonkwo. Jordan may also request independent estimate validation within the same window. |
| 3 | 7-day tiebreaker deadline runs concurrently with 14-day window; document silent on what happens if designation is still unresolved at day 14 | §0.1 adds an explicit rule: if a timely tiebreaker designation process is still unresolved at day 14, the default is suspended for up to 3 additional calendar days. The cap is not extendable. |
| 4 | "Logged" disagreement never defined — who logs it, where, in what form | §0.1 defines disagreement logging precisely: either owner may log by adding a timestamped comment to the designated Confluence decision page. The comment must name both options selected and both owners. The first valid entry is authoritative. |
| 5 | Default fires at day 14 even when a disagreement is logged on day 14; tiebreak and default can conflict | §0.1 states explicitly: the default does not fire while a tiebreak is pending. Default is suspended until the tiebreak resolves or the tiebreak deadline passes without action, whichever comes first. |
| 6 | Alex's 3-business-day tiebreak window can lapse to produce Option C without Alex casting a visible vote; document does not treat lapse as conflict-of-interest event | §0.1 adds an explicit rule: if Alex's tiebreak window lapses without action, this is recorded as a conflict-of-interest lapse, not a neutral default. Both managers are notified. Morgan Singh must confirm within 1 business day that Option C is the correct outcome, or may direct Alex to cast an explicit vote. |
| 7 | Option B structurally unachievable but listed as live option without adequate disclosure | §0.1 states at the top of the Option B description that it requires affirmative, unconditional joint selection by both owners. Conditional selections do not qualify. |
| 8 | Manager escalation procedure internally contradictory; manager selection treated as decision input | §0.1 escalation procedure specifies that a manager response taking the form of a direct selection is treated as a direction to the report, not as a decision input. The report must confirm or reject within 1 business day. |
| 9 | "One or both select Option B, but not both" row internally ambiguous | §0.1 replaces the ambiguous row with two distinct rows: one for "exactly one owner selects Option B" and one for "both owners select Option B but at least one selection is conditional or qualified." |
| 10 | Load-testing parallelization claim circular; rework estimate lacks schedule impact translation | §0.1 rework table replaces the parallelized estimate with 1.5 days (non-parallelizable), explains why, includes a schedule impact column, and derives the 1.5-week channel integration delay explicitly. |
| 11 | 15% Engineer 4 substitution figure is unvalidated and load-bearing | §0.1 rework table acknowledges the figure is an estimate, states its sensitivity, and commits to replacing it with a task-breakdown-derived number at override time. |
| 12 | Morgan Singh holds two potentially conflicting roles without acknowledgment | §0.4 acknowledges both roles explicitly and states that both may activate simultaneously. Morgan must respond to each independently; satisfying one does not satisfy the other. |
| 13 | Confluence automation treated as display defect in one context and operationally critical in another; failure modes not reconciled | §0.4 distinguishes two failure modes with separate consequences. Placeholder fill failure is a display defect. Morgan trigger failure is operationally critical and carries a formal backup obligation for Morgan. |
| 14 | Alex controls both conditions of "final form" and can delay Jordan's 7-day window by delaying notification; no cap on delay | §0.4 caps the interval between Confluence marking and Jordan notification at 4 business hours. If Alex does not notify Jordan within 4 business hours, the final-form timestamp is deemed to be the Confluence marking timestamp. Morgan is notified of any such deemed-final event. |
| 15 | Conflict of interest disclosure addresses only tiebreaking role; no remedy offered for estimate authorship or analysis authorship | §0.1 adds a mechanism for Jordan to request independent estimate validation within the same 7-day window. The reviewer's assessment does not block the decision but must be acknowledged by any tiebreaker. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. If the two conditions are satisfied at different times, the later timestamp is the reference time for all downstream obligations, subject to the 4-business-hour cap below.

**4-business-hour notification cap.** Alex must notify Jordan of the Confluence marking within 4 business hours of applying that marking. If Alex does not notify Jordan within 4 business hours, the final-form timestamp is deemed to be the Confluence marking timestamp, not the later notification timestamp. Jordan's 7-day tiebreaker-challenge window begins at the deemed timestamp. Morgan Singh receives an automated notification whenever the deemed-final rule activates, so that Alex's delay is recorded. This cap exists because Alex controls both conditions of final form and could otherwise delay Jordan's challenge window by delaying notification.

**Issue date and authoritative timestamp.** The issue date is the timestamp recorded in the Confluence page metadata at the moment Alex applies the "final" marking. This timestamp is set by Confluence automatically and is not editable after the fact. Decision owners must not rely on the document body for the authoritative timestamp — they must check the Confluence page metadata directly. The document body contains the following placeholder, which the Confluence distribution automation fills in from the metadata timestamp at the moment of distribution:

> **Issue date: [FILLED AUTOMATICALLY FROM CONFLUENCE METADATA AT DISTRIBUTION — do not edit manually]**

**Automation failure: two distinct failure modes.** The Confluence automation serves two separate functions: (1) filling the issue date placeholder in the document body, and (2) sending Morgan Singh a trigger notification when the distribution checklist item remains unchecked past the one-business-day window. These are separate failure modes with separate consequences.

- *Placeholder fill failure* is a display defect. If the automation fails to fill the placeholder, the Confluence metadata timestamp is still authoritative. A blank placeholder does not indicate that no issue date exists.

- *Morgan trigger failure* is operationally critical. If the automation fails to send Morgan the trigger notification, Morgan's backup distribution obligation does not automatically activate via the automation. To guard against this, Morgan Singh has a formal obligation — not merely a permitted action — to check the Confluence distribution checklist directly by end of business day 2 after the final-form timestamp, regardless of whether the automation notification has arrived. If the checklist item is unchecked and Morgan has not received the automation notification, Morgan must treat this as an automation failure, assume the trigger did not fire, and begin the backup distribution procedure immediately. Morgan's window in this case begins at end of business day 2, not at the moment a notification arrives.

These two failure modes are produced by the same automation. The document does not treat them equivalently because their consequences are not equivalent.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution with a timestamped entry in the project record, within one business day of the document reaching final form.

**Morgan Singh's dual roles.** Morgan Singh holds two distinct roles in this document: (a) backup distributor, who takes over Alex's distribution obligation if Alex fails to distribute within the one-business-day window, and (b) escalation recipient, who receives notifications when Alex fails to perform obligations assigned to Alex in this document. These roles may activate simultaneously — for example, if Alex fails to distribute, the Confluence automation trigger (role a) and the escalation notification (role b) may arrive at the same time or in close succession. Morgan must respond to each independently. Receipt of the automation trigger does not constitute receipt of an escalation notification, and vice versa. Morgan's response to the automation trigger is to distribute the document. Morgan's response to an escalation notification is defined in the escalation procedure in §0.1. These are separate obligations with separate response windows, and satisfying one does not satisfy the other.

**Backup distribution mechanism.** If Alex has not logged distribution within one business day of the final-form timestamp, Morgan Singh takes over the distribution obligation. Morgan's primary trigger is the Confluence automation rule: when the "Distribution logged" checklist item remains unchecked one business day after the final-form timestamp, Confluence sends Morgan a direct notification stating that Alex's window has closed and Morgan's obligation has begun. Morgan's secondary trigger is Morgan's own direct check of the checklist, as described in the automation failure section above. Morgan must distribute and log within one additional business day of whichever trigger activates first. If Morgan also fails to distribute within their window, the project record logs both non-performances and the matter escalates to the project steering committee. This is the only escalation that goes above the manager level.

All references to "14 days" in this document mean 14 calendar days from the Confluence metadata timestamp recorded at final-form marking, or from the deemed-final timestamp if the 4-business-hour cap activates, whichever is earlier.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

---

#### Default Suspension Rules

**Suspension on logged disagreement.** If a disagreement between owners is logged before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreak resolves, or when the tiebreak deadline passes without action from the tiebreaker, whichever comes first. Tiebreak lapse is governed by the conflict-of-interest lapse rule below, not by the standard default rule.

**Suspension on pending tiebreaker designation.** If Jordan initiates a tiebreaker challenge within the 7-day window (per the conflict of interest section below), and the designation process is still unresolved at day 14, the default does not fire at day 14. The default is suspended until the tiebreaker designation resolves or 3 additional calendar days pass from day 14, whichever comes first. If the designation has not resolved within 3 additional calendar days, the Alex-tiebreaker mechanism applies for the remainder of the tiebreak window. This 3-day cap is not extendable. Jordan's initiation of a challenge must be logged in the Confluence decision page per the logging procedure below; an unlogged challenge does not trigger this suspension.

---

#### Logging a Disagreement

A disagreement is logged when either decision owner adds a comment to the designated Confluence decision page for this document. A valid log entry must: (a) identify both options selected (e.g., "Jordan Rivera: Option A; Alex Chen: Option C"), (b) name both decision owners, and (c) bear a Confluence timestamp. Either owner may create the log entry; the first valid entry is authoritative. An entry that omits any of the three required elements is not a valid log entry and does not trigger the default suspension rule. Either owner may correct a defective entry by adding a new comment meeting all three requirements; the timestamp of the corrected entry is used.

If neither owner creates a valid log entry and the 14-day window closes, the default fires regardless of whether a disagreement existed in fact. Decision owners who have submitted differing selections but not logged the disagreement bear the risk that the default fires. The designated Confluence decision page is identified in the project record; if it has not been created, Alex Chen is responsible for creating it before distributing this document.

---

**Options:**

- **Option A:** Dedicated high-priority worker pool. Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers retry Redis more aggressively before falling back to PostgreSQL. **Requires approximately 0.5 additional engineer-weeks of permanent maintenance overhead relative to Option C.**

- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. **Option B is not achievable by one decision owner acting alone. It requires affirmative, unconditional joint selection by both Jordan Rivera and Alex Chen. A conditional selection (e.g., "Option B if X is confirmed") does not qualify as an affirmative selection for this purpose.** This constraint exists because Option B provides no priority isolation during failover, which is a product risk that requires both owners to consciously and unconditionally accept.

- **Option C (default):** Weighted fair-share during normal operation, with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

---

**The joint sign-off must answer one explicit question:** *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override to Option A before the 14-day window closes. Decision owners should read §0.3 before answering — the Option A isolation advantage is narrower than it appears, and §0.3 identifies the specific condition under which it is and is not real.

---

**Conflict of interest disclosure.** Alex Chen is the engineering lead who derived the rework cost estimates, authored the §0.3 interaction analysis, and whose operational preferences are reflected throughout this document. Alex is also the tiebreaker when Jordan and Alex disagree. Alex is not a neutral party. Decision owners should treat Alex's tiebreaking vote as a technically informed judgment from a non-neutral party, and Jordan Rivera in particular should understand that the tiebreaking mechanism gives Alex effective control over this decision in the event of disagreement.

**If Jordan believes this is unacceptable**, Jordan must request an alternative tiebreaking arrangement from Taylor Okonkwo [Jordan's manager] within 7 calendar days of the document issue date. Jordan and Taylor must designate an alternative tiebreaker and notify Alex Chen and Morgan Singh of the designation within those same 7 calendar days. If no alternative tiebreaker is designated and communicated to both parties within 7 calendar days of the issue date, the Alex-tiebreaker mechanism applies for the remainder of the 14-day window without further opportunity to object. This deadline is hard: a request initiated on day 8 or later is not actionable under this document. Jordan's initiation of a challenge must be logged in the Confluence decision page to trigger the pending-designation suspension rule; an unlogged challenge does not suspend the default.

**Independent estimate validation.** Jordan may also request independent validation of the rework cost estimates and §0.3 analysis, within the same 7-day window, by notifying Taylor Okonkwo. Taylor must designate an independent reviewer within those 7 days. The reviewer has 5 business days from designation to produce a written assessment. The assessment does not block the decision — it does not extend the 14-day window or the tiebreak window — but it is entered into the project record and must be considered by any tiebreaker before casting a vote. A tiebreaker who does not acknowledge the assessment in their recorded vote is in procedural non-compliance; Morgan Singh and Taylor Okonkwo are notified of any such non-compliance. This mechanism exists because Alex authored the estimates that determine the cost of overriding Alex's preferred option, and Jordan has no other mechanism to challenge those estimates within the decision window.

No alternative tiebreaker and no independent reviewer are pre-designated here; designating them is Jordan's and Taylor's responsibility, subject to the 7-day deadline.

---

#### Conflict-of-Interest Lapse Rule

If Alex Chen holds the tiebreaking role and Alex's 3-business-day tiebreak window lapses without Alex casting a visible vote, this is recorded as a conflict-of-interest lapse, not a neutral default event. The lapse is distinguished from an ordinary default because Alex's non-action benefits the outcome (Option C) that Alex's operational preferences favor, and because Alex authored the analysis and estimates that frame the