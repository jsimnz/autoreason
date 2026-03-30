# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses nine problems identified in the prior review. **This table is a navigation aid only. It makes no completeness claims. The document's sections are the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Rework cost table truncated; §0.1 resolution for prior problem 10 unverifiable | Table is complete in this revision. All rows and columns present. |
| 2 | Plain-language summary has no delivery verification, acknowledgment requirement, quality check, or consequence for non-delivery | §0.1 adds a delivery logging requirement (Confluence comment), a Jordan acknowledgment requirement, a 48-hour maximum gap between issue date and summary receipt, and a defined consequence for non-delivery. |
| 3 | 10-day objection window and plain-language summary sequenced such that Jordan may not receive the summary until day 3, losing meaningful evaluation time | §0.1 requires Alex to deliver the summary within one business day of the issue date — not at distribution — so Jordan's evaluation time is not consumed by distribution lag. The window is also recalibrated to start from confirmed summary receipt. |
| 4 | Morgan Singh's daily check obligation incoherent — "once per business day during a one-business-day window" is redundant or undefined | §0.4 replaces the daily-check framing with a single specific check obligation tied to a defined time of day (UTC), eliminating the ambiguity. |
| 5 | Alternative tiebreaker clock interaction unresolved when tiebreak clock expires simultaneously with default window | §0.1 adds an explicit reconciliation rule: when the tiebreaker's deadline passes without action, Option C is implemented immediately regardless of whether the 14-day default window is also pending. The two paths converge on the same outcome; no conflict exists once this is stated. |
| 6 | Morgan Singh adjudicates log entry validity disputes despite having multiple conflicting roles in the same process; conflict never disclosed | §0.5 discloses Morgan's structural conflicts and reassigns log entry validity adjudication to Taylor Okonkwo. Morgan retains distribution and checklist functions but no adjudicative role. |
| 7 | Project calendar is a single point of failure: unnamed coordinator, no version control, no audit trail, no procedure for retroactive modification or unavailability | §0.4 names the project coordinator, requires a version-controlled calendar with a change log, prohibits retroactive modification of holidays affecting deadlines already in progress, and defines a fallback when the calendar is unavailable. |
| 8 | "Process defect" classification for missing automation test records has no owner, location, consequence, or remediation | §0.4 assigns defect logging to Morgan Singh, specifies the Confluence defect log location, defines a 24-hour remediation window, and states the consequence of non-remediation. |
| 9 | Steering committee appears three times but is never defined: no membership, cadence, response obligation, or decision authority | §0.6 defines the steering committee, its membership, convening obligation, response deadline, and decision authority. All three escalation paths now reference §0.6. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.6 Project Steering Committee

**Purpose.** The steering committee is the escalation authority for process failures that cannot be resolved within the normal decision owner and manager structure. It has three defined escalation triggers in this document: (a) both managers fail to respond during a pending tiebreak, (b) both Alex Chen and Morgan Singh fail to distribute the final document within their respective windows, and (c) a failed alternative tiebreaker situation as described in §0.1. Additional escalation triggers may exist in other project documents; those documents govern their own triggers.

**Membership.** The steering committee consists of: Taylor Okonkwo [Jordan's manager], Morgan Singh [Alex's manager], and one named executive sponsor. The executive sponsor for this project is [NAME — to be filled before document is marked final]. The executive sponsor is the tiebreaker within the steering committee if Taylor and Morgan disagree on a steering committee decision. The executive sponsor may not delegate their steering committee role to a direct report.

**Convening obligation.** When an escalation trigger fires, the party logging the escalation must notify all three steering committee members via the project's standard notification channel within one business day (UTC, project calendar as defined in §0.4) of the trigger event. The steering committee must convene — synchronously or asynchronously via documented written exchange — within two business days of receiving notification.

**Response obligation and decision authority.** The steering committee must produce a written decision within three business days of convening. The written decision must be logged in the Confluence project space under "Steering Committee Decisions." The steering committee has authority to: override any default outcome in this document, extend any deadline in this document by a stated number of days with stated reasons, designate replacement decision owners or tiebreakers, and escalate further to organizational leadership outside the project. The steering committee does not have authority to alter the substance of technical options or cost estimates without involving the relevant engineers.

**Steering committee member conflicts.** Taylor Okonkwo and Morgan Singh are themselves named in various roles throughout this document. If a steering committee decision directly concerns the conduct of Taylor or Morgan (e.g., a failure to respond that is itself the subject of the escalation), the conflicted member must recuse from that specific decision. The executive sponsor decides in the absence of a quorum due to recusal. If both Taylor and Morgan are conflicted, the executive sponsor decides alone and documents the basis.

**Steering committee unavailability.** If the steering committee cannot convene within the required window because one or more members are unavailable, the available members may act. If no member is available, the executive sponsor's delegate (designated in advance by the executive sponsor and named in the project calendar) may act in the executive sponsor's place for purposes of convening only. A steering committee that fails to produce a written decision within its three-business-day window must log the failure in the Confluence project space; the default outcome for the underlying decision then applies.

---

### 0.5 Disagreement Logging Mechanism

**Purpose.** The 3-business-day tiebreak clock and the default suspension rule both depend on a disagreement being "logged." This section defines what a valid log entry is, how the clock starts, and who adjudicates disputes about validity.

**Logging location.** Disagreements are logged as comments in the dedicated comment thread on this Confluence page. The thread is labeled with the tag `[DECISION-DISAGREEMENT]`. Either decision owner may create a log entry. A log entry is valid when it contains all of the following fields:

- Decision identifier (e.g., "Decision A: Worker Allocation Strategy")
- The logging owner's name and role
- The logging owner's stated selection
- A statement that the other owner has communicated a conflicting selection, or that the logging owner believes a conflicting selection exists and has not been resolved

**Authoritative timestamp.** The Confluence comment timestamp (UTC) on a valid log entry is the authoritative start of the 3-business-day tiebreak clock. Neither owner may dispute the timestamp by claiming a different time of awareness.

**Automated notification.** When a comment tagged `[DECISION-DISAGREEMENT]` is created on this page, a Confluence automation rule sends a notification to both decision owners and both managers (Taylor Okonkwo and Morgan Singh). This notification is informational — it does not start any manager obligation. Manager obligations begin only as described in the escalation procedure in §0.1.

**Disputed validity.** If a decision owner believes a log entry is invalid (e.g., missing required fields), they must raise the dispute in the same comment thread within one business day (UTC, project calendar) of receiving the automated notification. **Taylor Okonkwo adjudicates disputes about log entry validity.** Taylor's adjudication is final for purposes of determining whether the clock has started. Taylor must respond within two business days of receiving a validity dispute notification. If Taylor does not respond within two business days, the log entry is treated as valid and the clock is treated as running from the original comment timestamp.

**Morgan Singh's role in this section.** Morgan Singh has no adjudicative function in this section. Morgan's roles in this document are limited to: backup distribution, checklist access, and process defect logging as defined in §0.4. These roles are structurally separate from the disagreement logging and validity adjudication process. **Disclosure:** Morgan Singh is the backup distributor, holds checklist write access, and receives escalation notifications. Concentrating adjudicative authority over log entry validity in the same person would create a conflict between Morgan's interest in the distribution process running smoothly and the need for neutral validity adjudication. That conflict is avoided by assigning adjudication to Taylor Okonkwo, who has no distribution role.

---

### 0.4 Document Issue Date and Clock Mechanism

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. If the two conditions are satisfied at different times, the later timestamp is the reference time for all downstream obligations.

**Issue date and authoritative timestamp.** The issue date is the timestamp recorded in the Confluence page metadata at the moment Alex applies the "final" marking. This timestamp is set by Confluence automatically and is not editable after the fact. Decision owners must not rely on the document body for the authoritative timestamp — they must check the Confluence page metadata directly. The document body contains the following placeholder, which the Confluence distribution automation fills in from the metadata timestamp at the moment of distribution:

> **Issue date: [FILLED AUTOMATICALLY FROM CONFLUENCE METADATA AT DISTRIBUTION — do not edit manually]**

If the automation fails and the placeholder is not filled, the Confluence metadata timestamp is still authoritative. A blank placeholder is a display defect, not an indication that no issue date exists.

**Timezone and business day calendar.** All time calculations in this document use UTC. All parties are bound by UTC regardless of their local timezone or location. The governing holiday calendar is the project calendar maintained in the Confluence project space under "Project Calendar." The project calendar is maintained by **[PROJECT COORDINATOR NAME — to be filled before document is marked final]**. A business day is any day that is not a Saturday, Sunday, or a holiday listed in that calendar. If a deadline falls on a non-business day, the deadline moves to the next business day.

**Project calendar integrity requirements.** The project calendar must be maintained under Confluence page version control. Every modification to the project calendar must include a dated change log entry stating: the modifier's name, the date of modification (UTC), and the nature of the change. **Retroactive modification is prohibited:** a holiday may not be added to the project calendar if the addition would alter a deadline that has already been communicated to any decision owner or that is currently in progress. "Currently in progress" means the deadline window has opened but not yet closed at the time of the proposed modification. If a modification is made in violation of this rule, the pre-modification calendar governs for all deadlines that were already communicated or in progress. Morgan Singh is responsible for detecting and flagging retroactive modifications; Taylor Okonkwo adjudicates disputes about whether a modification was retroactive.

**Project calendar unavailability.** If the project calendar is unavailable (e.g., Confluence outage) at the moment a party needs to determine whether a given day is a business day, the party must: (a) document the unavailability with a timestamp, (b) use the most recently accessible version of the calendar, and (c) notify Morgan Singh of the unavailability within four hours. Morgan Singh logs the unavailability in the Confluence project space. If the calendar was unavailable when a deadline was calculated and the calculation was later found to be incorrect due to the unavailability, the deadline is recalculated using the correct calendar and the party who missed the corrected deadline is not penalized, provided they acted in good faith on the best available information.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution by checking the "Distribution logged" checklist item (see below) within one business day (UTC, project calendar) of the document reaching final form.

**Checklist item access control.** The "Distribution logged" checklist item on this Confluence page has restricted write access. Only Alex Chen and Morgan Singh may check or uncheck it. All other team members have read-only access. This permission configuration must be verified as part of the pre-distribution automation test described below. A check by any other party is invalid and must be reported to Morgan Singh immediately.

**Pre-distribution automation verification.** Before Alex marks this document as final, Alex must test the Confluence automation rule described below by triggering it in a test environment or staging page. The test must confirm: (a) the automation fires when the checklist item remains unchecked after the specified interval, (b) Morgan Singh receives the notification, and (c) the checklist item access restrictions are enforced. Alex must link the test record in the Confluence page comments before applying the "final" marking. If the test cannot be completed, Alex must notify Morgan Singh before marking the document final, and Morgan Singh must acknowledge the notification.

**Process defect for missing automation test record.** If Alex marks the document final without a linked test record and without Morgan's written acknowledgment of a test failure, this is a process defect. The defect does not invalidate the final-form timestamp. **Morgan Singh is responsible for logging the defect** in the Confluence project space under "Process Defects" within one business day of observing it. Morgan must also notify Taylor Okonkwo of the defect at the time of logging. Alex has 24 hours from Morgan's defect notification to either (a) provide the missing test record retroactively with an explanation of why it was not linked before marking final, or (b) provide written acknowledgment of the defect with a remediation plan. If Alex does neither within 24 hours, Morgan escalates to the steering committee per §0.6.

**Backup mechanism — automated layer.** When the "Distribution logged" checklist item remains unchecked one business day (UTC, project calendar) after the final-form timestamp, a Confluence automation rule sends Morgan Singh a direct notification stating that Alex's distribution window has closed and Morgan's obligation has begun. Morgan's obligation window begins at the timestamp of that notification.

**Backup mechanism — human layer.** Because the automated layer may fail despite pre-distribution testing, Morgan Singh must also perform a direct check. **Morgan must check the "Distribution logged" checklist item by 17:00 UTC on the business day that constitutes the end of Alex's one-business-day distribution window.** If Morgan observes at that check that the checklist item is unchecked and Alex's window has closed, Morgan's distribution obligation begins immediately regardless of whether the automation has fired. Morgan does not need to wait for an automated notification to begin their obligation if they have independently observed the trigger condition at the 17:00 UTC check.

The 17:00 UTC check time is chosen to allow Morgan to observe the trigger condition with enough of the business day remaining to take initial steps. Morgan's distribution obligation begins at the moment of observation, not at 17:00 UTC; 17:00 UTC is the latest Morgan may perform the check, not the time the obligation begins if the condition is met.

**Morgan's distribution window.** Morgan must distribute and log within one additional business day (UTC, project calendar) of Morgan's obligation beginning — whether that beginning is triggered by the automation or by Morgan's own observation. If Morgan also fails to distribute within their window, Morgan Singh and Alex Chen are both in non-performance. The failure is logged in the Confluence project space under "Process Defects" by Taylor Okonkwo, and the matter escalates to the project steering committee per §0.6.

All references to "14 days" in this document mean 14 calendar days from the Confluence metadata timestamp recorded at final-form marking, measured in UTC.

---

### 0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

**Default suspension rule.** If a disagreement between owners is logged in Confluence per §0.5 before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreaker acts, or when the tiebreaker's 3-business-day deadline passes without action, whichever comes first. This rule applies regardless of whether managers have been notified and regardless of whether managers have responded. If the default is suspended and both managers are notified and both managers fail to respond within their 2-business-day windows, the default remains suspended; it does not fire due to manager non-response. Manager non-response in this state is logged and escalates to the project steering committee per §0.6 as a separate matter. **The default fires only when the tiebreak resolves or the tiebreaker's deadline passes.**

**Convergence rule for simultaneous expiration.** If the tiebreaker's 3-business-day deadline passes without action at a time when the 14-day default window has also closed or would simultaneously close, both paths produce the same outcome: Option C is implemented. There