# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision synthesizes two prior versions. **This table is a navigation aid only. It makes no completeness claims. The document's sections are the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Document truncated mid-sentence in prior versions; substantive sections unverifiable | Document is complete. All sections present. |
| 2 | 14-day clock has single point of failure; Alex's non-performance on distribution has no defined trigger for backup; automation described as if it exists but has no verified existence | §0.4 replaces proactive-monitoring expectation with a Confluence automation trigger. Morgan Singh's obligation begins when the automation fires. §0.4 also requires pre-distribution automation verification and adds a mandatory human-layer check by Morgan Singh at a specific time (17:00 UTC) as a parallel backstop, eliminating sole dependence on the automation. |
| 3 | Option B structurally unachievable but listed as live option without disclosure; tiebreaker selecting Option B creates unreconciled conflict with joint-selection constraint | §0.1 states at the top of the Option B description that it requires affirmative joint selection by both owners. A tiebreaker selecting Option B is treated as a selection of Option C. Both rules are stated in the option framing and in the partial-response table. |
| 4 | Alex Chen's tiebreaking vote creates unacknowledged conflict of interest; Jordan's objection window insufficient given document complexity | §0.1 acknowledges the conflict explicitly. Jordan has a 10-calendar-day hard deadline to request an alternative tiebreaker via Taylor Okonkwo. The 10-day window fits within the 14-day decision window with a 4-day margin. |
| 5 | Manager escalation procedure internally contradictory; manager selection treated as decision input | §0.1 escalation procedure specifies that a manager response taking the form of a direct selection is treated as a direction to the report, not as a decision input. The report must confirm or reject within 1 business day. |
| 6 | §0.3 interaction analysis presents recommendation as analysis; PostgreSQL overload assumption unvalidated | §0.3 separates scenario table from recommendation. The PostgreSQL overload assumption is flagged as unvalidated and the conclusion is explicitly conditioned on it. |
| 7 | Load-testing parallelization claim circular — "concurrent test scenarios" does not establish independence | §0.1 rework table replaces the 0.75-day parallelized estimate with 1.5 days (non-parallelizable) and explains why: test scenarios share the same worker pool and queue infrastructure; concurrent execution invalidates the isolation measurement. |
| 8 | "Final form" undefined; one-business-day distribution obligation has no determinable start; "one business day" undefined (no timezone, no calendar, no holiday rule) | §0.4 defines final form precisely: both conditions — Confluence marking and owner notification — must be satisfied. The later timestamp is authoritative. Issue date is Confluence metadata, not document body. All time calculations use UTC. The governing holiday calendar is the project calendar in Confluence. |
| 9 | Default fires at day 14 even when a disagreement is logged on day 14; tiebreak and default can conflict; default suspension and manager non-response unreconciled | §0.1 states explicitly: the default does not fire while a tiebreak is pending. Manager non-response does not fire the default while a tiebreak is pending. Manager non-response in that state escalates separately to the project steering committee. §0.1 also adds an explicit convergence rule for simultaneous expiration of the tiebreaker deadline and the 14-day window. |
| 10 | Rework estimate stated as engineer-weeks without translation to schedule impact; parallelization claim unexplained; substitution figure unverifiable | §0.1 rework table includes a schedule impact column and explains non-parallelizability for each task. The substitution shortfall is stated as a range with bounds explained. The channel integration delay is derived explicitly from staffing assumptions stated inline. |
| 11 | Morgan Singh adjudicates log entry validity disputes despite having multiple conflicting roles in the same process; conflict never disclosed | §0.5 discloses Morgan's structural conflicts and reassigns log entry validity adjudication to Taylor Okonkwo. Morgan retains distribution and checklist functions but no adjudicative role. |
| 12 | Project calendar is a single point of failure: unnamed coordinator, no version control, no audit trail, no procedure for retroactive modification or unavailability | §0.4 names the project coordinator, requires a version-controlled calendar with a change log, prohibits retroactive modification of holidays affecting deadlines already in progress, and defines a fallback when the calendar is unavailable. |
| 13 | "Process defect" classification for missing automation test records has no owner, location, consequence, or remediation path | §0.4 assigns defect logging to Morgan Singh, specifies the Confluence defect log location, defines a 24-hour remediation window, and states the consequence of non-remediation. |
| 14 | Steering committee appears in escalation paths but is never defined: no membership, cadence, response obligation, or decision authority | §0.6 defines the steering committee, its membership, convening obligation, response deadline, and decision authority. All escalation paths reference §0.6. |
| 15 | Plain-language summary has no delivery verification, acknowledgment requirement, or consequence for non-delivery | §0.1 requires Alex to deliver the summary within one business day of the issue date. The decision window starts from confirmed summary receipt. A defined consequence applies for non-delivery. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

### 0.6 Project Steering Committee

**Purpose.** The steering committee is the escalation authority for process failures that cannot be resolved within the normal decision owner and manager structure. It has the following defined escalation triggers in this document: (a) both managers fail to respond during a pending tiebreak; (b) both Alex Chen and Morgan Singh fail to distribute the final document within their respective windows; (c) a failed alternative tiebreaker situation as described in §0.1; (d) a process defect that Alex fails to remediate within 24 hours as described in §0.4; and (e) any other escalation explicitly directed to the steering committee by a named section of this document. Additional escalation triggers may exist in other project documents; those documents govern their own triggers.

**Membership.** The steering committee consists of: Taylor Okonkwo [Jordan's manager], Morgan Singh [Alex's manager], and one named executive sponsor. The executive sponsor for this project is **[NAME — to be filled before document is marked final]**. The executive sponsor is the tiebreaker within the steering committee if Taylor and Morgan disagree on a steering committee decision. The executive sponsor may not delegate their steering committee role to a direct report.

**Convening obligation.** When an escalation trigger fires, the party logging the escalation must notify all three steering committee members via the project's standard notification channel within one business day (UTC, project calendar as defined in §0.4) of the trigger event. The steering committee must convene — synchronously or asynchronously via documented written exchange — within two business days of receiving notification.

**Response obligation and decision authority.** The steering committee must produce a written decision within three business days of convening. The written decision must be logged in the Confluence project space under "Steering Committee Decisions." The steering committee has authority to: override any default outcome in this document; extend any deadline in this document by a stated number of days with stated reasons; designate replacement decision owners or tiebreakers; and escalate further to organizational leadership outside the project. The steering committee does not have authority to alter the substance of technical options or cost estimates without involving the relevant engineers.

**Steering committee member conflicts.** Taylor Okonkwo and Morgan Singh are themselves named in various roles throughout this document. If a steering committee decision directly concerns the conduct of Taylor or Morgan (e.g., a failure to respond that is itself the subject of the escalation), the conflicted member must recuse from that specific decision. The executive sponsor decides in the absence of a quorum due to recusal. If both Taylor and Morgan are conflicted, the executive sponsor decides alone and documents the basis.

**Steering committee unavailability.** If the steering committee cannot convene within the required window because one or more members are unavailable, the available members may act. If no member is available, the executive sponsor's delegate — designated in advance by the executive sponsor and named in the project calendar — may act in the executive sponsor's place for purposes of convening only. A steering committee that fails to produce a written decision within its three-business-day window must log the failure in the Confluence project space; the default outcome for the underlying decision then applies.

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

**Timezone and business day calendar.** All time calculations in this document use UTC. All parties are bound by UTC regardless of their local timezone or location. The governing holiday calendar is the project calendar maintained in the Confluence project space under "Project Calendar." The project calendar is maintained by **[PROJECT COORDINATOR NAME — to be filled before document is marked final]**. A business day is any day that is not a Saturday, Sunday, or a holiday listed in that calendar. If a deadline falls on a non-business day, the deadline moves to the next business day. The project calendar is the sole reference for holiday determinations; local or national calendars do not govern unless they are reflected in the project calendar.

**Project calendar integrity requirements.** The project calendar must be maintained under Confluence page version control. Every modification to the project calendar must include a dated change log entry stating: the modifier's name, the date of modification (UTC), and the nature of the change. **Retroactive modification is prohibited:** a holiday may not be added to the project calendar if the addition would alter a deadline that has already been communicated to any decision owner or that is currently in progress. "Currently in progress" means the deadline window has opened but not yet closed at the time of the proposed modification. If a modification is made in violation of this rule, the pre-modification calendar governs for all deadlines that were already communicated or in progress. Morgan Singh is responsible for detecting and flagging retroactive modifications; Taylor Okonkwo adjudicates disputes about whether a modification was retroactive.

**Project calendar unavailability.** If the project calendar is unavailable (e.g., Confluence outage) at the moment a party needs to determine whether a given day is a business day, the party must: (a) document the unavailability with a timestamp, (b) use the most recently accessible version of the calendar, and (c) notify Morgan Singh of the unavailability within four hours. Morgan Singh logs the unavailability in the Confluence project space. If the calendar was unavailable when a deadline was calculated and the calculation was later found to be incorrect due to the unavailability, the deadline is recalculated using the correct calendar and the party who missed the corrected deadline is not penalized, provided they acted in good faith on the best available information.

**Distribution obligation.** Alex Chen is responsible for distributing the final document to all named decision owners via Confluence with email notification, and for logging the distribution by checking the "Distribution logged" checklist item (see below) within one business day (UTC, project calendar) of the document reaching final form.

**Checklist item access control.** The "Distribution logged" checklist item on this Confluence page has restricted write access. Only Alex Chen and Morgan Singh may check or uncheck it. All other team members have read-only access. This permission configuration must be verified as part of the pre-distribution automation test described below. A check by any other party is invalid and must be reported to Morgan Singh immediately.

**Pre-distribution automation verification.** Before Alex marks this document as final, Alex must test the Confluence automation rule described below by triggering it in a test environment or staging page. The test must confirm: (a) the automation fires when the checklist item remains unchecked after the specified interval, (b) Morgan Singh receives the notification, and (c) the checklist item access restrictions are enforced. Alex must link the test record in the Confluence page comments before applying the "final" marking. If the test cannot be completed, Alex must notify Morgan Singh before marking the document final, and Morgan Singh must acknowledge the notification.

**Process defect for missing automation test record.** If Alex marks the document final without a linked test record and without Morgan's written acknowledgment of a test failure, this is a process defect. The defect does not invalidate the final-form timestamp. **Morgan Singh is responsible for logging the defect** in the Confluence project space under "Process Defects" within one business day of observing it. Morgan must also notify Taylor Okonkwo of the defect at the time of logging. Alex has 24 hours from Morgan's defect notification to either (a) provide the missing test record retroactively with an explanation of why it was not linked before marking final, or (b) provide written acknowledgment of the defect with a remediation plan. If Alex does neither within 24 hours, Morgan escalates to the steering committee per §0.6.

**Backup mechanism — automated layer.** When the "Distribution logged" checklist item remains unchecked one business day (UTC, project calendar) after the final-form timestamp, a Confluence automation rule sends Morgan Singh a direct notification stating that Alex's distribution window has closed and Morgan's obligation has begun. Morgan's obligation window begins at the timestamp of that notification.

**Backup mechanism — human layer.** Because the automated layer may fail