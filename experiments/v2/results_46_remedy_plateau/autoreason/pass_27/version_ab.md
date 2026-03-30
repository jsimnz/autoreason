# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

**This table is a navigation aid only. It makes no completeness claims. The document's sections are the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | Plain-language summary had no delivery verification, acknowledgment requirement, or consequence for non-delivery | §0.1 requires Alex to deliver the summary within one business day of the issue date via the project's standard notification channel with a simultaneous Confluence comment. Jordan must acknowledge within one business day. Non-delivery is a process defect logged by Morgan Singh per §0.4. |
| 2 | Jordan's evaluation window consumed by distribution lag | §0.1 requires summary delivery independent of full document distribution. Jordan's 14-day window starts from confirmed acknowledgment, not the issue date. |
| 3 | Default suspension rule interaction with tiebreaker clock expiration was unresolved | §0.1 adds an explicit convergence rule: both paths produce Option C. The party responsible for logging non-action records the Option C implementation at the moment of convergence. |
| 4 | Morgan Singh's daily check obligation was incoherent | §0.4 replaces it with a single specific check at 17:00 UTC on the last day of Alex's distribution window. |
| 5 | Morgan Singh held adjudicative roles despite structural conflicts | §0.5 assigns log entry validity adjudication exclusively to Taylor Okonkwo. Morgan's roles are limited to distribution backup, checklist access, and process defect logging. Conflict is disclosed. |
| 6 | Steering committee referenced three times but never defined | §0.6 defines membership, convening obligation, response deadline, decision authority, conflict/recusal rules, and minimum participation threshold. |
| 7 | Project calendar was a single point of failure with no version control, audit trail, or unavailability fallback | §0.4 requires version-controlled calendar with change log, prohibits retroactive modification of in-progress deadlines, and defines a fallback procedure for unavailability. |
| 8 | Process defect classification had no owner, location, consequence, or remediation path | §0.4 assigns defect logging to Morgan Singh, specifies the Confluence location, defines a 24-hour remediation window, and states the escalation consequence. |
| 9 | Executive sponsor and project coordinator left as unfilled placeholders | §0.4 and §0.6 contain enforcement language: the document cannot reach final form while either field contains placeholder text. The pre-distribution automation test must verify both fields are filled. |
| 10 | Taylor Okonkwo's adjudicative role had no recusal mechanism when Jordan Rivera (Taylor's direct report) was the named log entry author | §0.5 requires Taylor to recuse from adjudicating any log entry created by Jordan Rivera. The executive sponsor adjudicates in Taylor's place. Taylor must notify the executive sponsor within one business day of identifying the recusal condition. |
| 11 | Morgan Singh could log process defects against Alex Chen (Morgan's direct report) and escalate to a committee Morgan sits on without conflict disclosure | §0.4 discloses this relationship. Morgan's initial defect-logging function is retained (it is ministerial and timestamp-dependent) but Morgan must recuse from any steering committee deliberation concerning that defect. The executive sponsor is notified of Morgan's recusal at the time of escalation. |
| 12 | Steering committee convening had no minimum participation threshold | §0.6 requires all available, non-recused members to post a substantive written contribution within the two-business-day convening window. A member who does not post is treated as unavailable; the available-member quorum rule applies. |
| 13 | Automation test performed only on staging page, not production | §0.4 requires the test to be performed on the production page (or the specific Confluence space containing the final document). A staging test may precede but does not substitute for a production-environment verification. |
| 14 | `[DECISION-DISAGREEMENT]` tag automation had no test requirement and no human-layer backup | §0.5 adds a test requirement mirroring §0.4's pre-distribution test. Each decision owner must also independently notify both managers via the project's standard notification channel within one business day of logging a disagreement, regardless of whether automation has fired. |
| 15 | Executive sponsor delegate designation was in the modifiable, unmonitored project calendar | §0.6 moves delegate designation to a dedicated, separately access-controlled Confluence page ("Executive Sponsor Delegation Record") not editable by the project coordinator. Changes require the executive sponsor's direct action and generate notifications to all steering committee members. |
| 16 | Decision A and Decision B interaction not formally analyzed; Option Y feasibility risk under Decision A Option B outcome undocumented | §0.3 provides the authoritative interaction analysis, including a scenario table and sequencing recommendation. Decision owners must consult §0.3 before making or logging their selections. |
| 17 | Morgan's 17:00 UTC check obligation assumed Morgan's business day includes 17:00 UTC; no working hours defined | §0.4 requires Morgan to confirm in writing before final marking that 17:00 UTC falls within Morgan's contractual or standard working hours. If Morgan cannot confirm, the check time is renegotiated and a replacement time recorded in the project calendar before final marking. |
| 18 | If Alex's Confluence marking and Jordan notification occur on different days, Morgan's check could be a day early | §0.4 clarifies: Morgan's check obligation falls on the business day one business day after the later of the two final-form timestamps. Morgan must record which timestamp is being treated as the reference when performing the check. |

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock starts on the issue date defined in §0.4. Decisions A and B interact; the interaction analysis is in §0.3.

---

## §0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Options.**

- **Option A:** Dedicate two of four backend engineers exclusively to the notification system for the full six months.
- **Option B:** Rotate all four engineers through notification work on a two-week sprint cycle, with no engineer dedicated full-time.
- **Option C** *(default)*: Assign two engineers as notification leads with two engineers available for shared infrastructure work, reviewed at the 90-day mark.

**Default if no explicit joint sign-off within 14 days of the issue date: Option C.**

**Default suspension rule.** If a disagreement between owners is logged in Confluence per §0.5 before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreaker acts, or when the tiebreaker's 3-business-day deadline passes without action, whichever comes first. This rule applies regardless of whether managers have been notified and regardless of whether managers have responded. If the default is suspended and both managers are notified and both managers fail to respond within their 2-business-day windows, the default remains suspended; it does not fire due to manager non-response. Manager non-response in this state is logged and escalates to the project steering committee per §0.6 as a separate matter. **The default fires only when the tiebreak resolves or the tiebreaker's deadline passes.**

**Convergence rule for simultaneous expiration.** If the tiebreaker's 3-business-day deadline passes without action at a time when the 14-day default window has also closed or would simultaneously close, both paths produce the same outcome: Option C is implemented. No conflict exists between these two paths. The party responsible for logging the tiebreaker's non-action must log the Option C implementation in the Confluence project space at the moment of convergence.

**Plain-language summary obligation.** Alex Chen must prepare a plain-language summary of Decision A — including a description of each option in non-technical terms, the cost and staffing implications of each option, and the reason Option C is the default — and deliver it to Jordan Rivera within one business day of the issue date. Delivery is via the project's standard notification channel with a Confluence comment logged simultaneously. Alex must not delay delivery of the summary until distribution of the full document; the summary obligation is independent of the distribution obligation in §0.4.

**Acknowledgment requirement.** Jordan Rivera must acknowledge receipt of the plain-language summary via a Confluence comment within one business day of receiving it. If Jordan does not acknowledge within one business day, Alex must follow up via the project's standard notification channel and log the follow-up attempt in Confluence. If Jordan does not acknowledge within two business days of the original delivery, Alex notifies Taylor Okonkwo (Jordan's manager). Taylor's receipt of that notification starts a one-business-day window for Taylor to confirm Jordan has received and reviewed the summary.

**Evaluation window.** Jordan's 14-day evaluation window for Decision A begins at the timestamp of Jordan's acknowledgment comment, not at the issue date. If Jordan's acknowledgment is delayed, the 14-day window shifts accordingly. The latest the window may begin is two business days after the issue date; if Jordan has not acknowledged by that point, the window begins at the two-business-day mark regardless, and the non-acknowledgment is logged as a process defect per §0.4.

**Consequence for non-delivery of summary.** If Alex does not deliver the plain-language summary within one business day of the issue date, this is a process defect. Morgan Singh logs the defect per §0.4. Alex's failure to deliver the summary does not extend the 14-day default window, but Jordan may raise the non-delivery as a mitigating factor in any subsequent tiebreak proceeding.

**Escalation procedure.** If the two decision owners disagree, either owner logs the disagreement per §0.5. Both owners must notify their respective managers (Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen) via the project's standard notification channel within one business day of logging the disagreement. Each manager has 2 business days from notification to act as tiebreaker. If only one manager responds within their window, that manager's selection governs. If both managers respond with conflicting selections within their windows, Morgan Singh's selection governs (Morgan is the engineering-side manager and this decision has primary engineering resource implications). If neither manager responds within their respective windows, the matter escalates to the project steering committee per §0.6.

---

## §0.2 Decision B: Notification Priority Classification Schema

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Options.**

- **Option X:** Two-tier schema — Critical (delivery within 60 seconds, all channels attempted) and Standard (delivery within 15 minutes, push and in-app only). Classification is set at event-type registration and cannot be overridden at runtime.
- **Option Y:** Three-tier schema — Critical, High, and Standard — with per-tier channel and latency targets as defined in §1 of the main design. Classification may be overridden at runtime by a privileged service account with audit logging.
- **Option Z** *(default)*: Two-tier schema with a runtime override capability restricted to a defined allowlist of event types. Override attempts outside the allowlist are rejected and logged. This is a middle path between Option X's rigidity and Option Y's full runtime flexibility.

**Default if no explicit joint sign-off within 14 days of the issue date: Option Z.**

**Interaction with Decision A.** The three-tier schema (Option Y) requires more engineering capacity to implement and maintain than the two-tier schemas. If Decision A resolves as Option B (rotating all four engineers), the engineering lead must notify the product lead within two business days that Option Y may not be achievable within the six-month window, and the product lead must factor this into their Decision B selection. The interaction analysis in §0.3 addresses this dependency in full.

**Default suspension rule.** The same default suspension rule defined in §0.1 applies to Decision B. All references to "the tiebreaker's deadline," "manager notification," and "escalation to the steering committee" in §0.1's escalation procedure apply equally to Decision B, substituting "Decision B" for "Decision A" throughout.

**Escalation procedure.** The same escalation procedure defined in §0.1 applies to Decision B. If both Decision A and Decision B are simultaneously in a suspended-default state, the steering committee may consolidate the two matters into a single proceeding at its discretion. Consolidation does not alter any individual deadline.

---

## §0.3 Interaction Analysis: Decisions A and B

**Purpose.** §0.1 and §0.2 both note that Decisions A and B interact. This section is the authoritative analysis of that interaction. Decision owners must consult this section before making or logging their selections.

**The dependency.** Decision B's options differ in engineering complexity. Option Y (three-tier schema with full runtime override) requires the most engineering capacity: estimated at approximately 30% more implementation time than Option X or Option Z, based on the engineering lead's assessment at the time of this document's drafting. Decision A determines how engineering capacity is allocated. The interaction is asymmetric: Decision A constrains Decision B, but Decision B does not constrain Decision A.

**Specific interaction scenarios.**

| Decision A Outcome | Effect on Decision B |
|---|---|
| Option A (two dedicated engineers) | All three Decision B options are achievable within the six-month window per current engineering estimates. No constraint. |
| Option B (rotating all four engineers) | Option Y is at risk. The engineering lead must provide a revised feasibility assessment for Option Y within five business days of Decision A resolving as Option B. Decision B's 14-day window does not pause during this assessment, but the product lead may request a joint review meeting before committing to a selection. |
| Option C (two leads, two shared) | All three Decision B options are achievable, but Option Y carries higher schedule risk than under Option A. The engineering lead must flag this risk in writing to the product lead at the time Decision A resolves as Option C. |

**Sequencing recommendation.** The engineering lead and product lead should attempt to resolve Decision A before Decision B. If both decisions are unresolved at day 7 of the 14-day window, the engineering lead must notify the product lead that the interaction risk is increasing and request a joint session within two business days.

**What happens if Decision B resolves before Decision A.** If the product lead selects Option Y for Decision B before Decision A is resolved, that selection is valid and binding. However, if Decision A subsequently resolves as Option B (rotating engineers), the engineering lead must immediately notify the product lead and the steering committee that a feasibility conflict exists. The steering committee has authority to reopen Decision B under these circumstances per §0.6. Reopening Decision B does not alter the Decision A outcome.

**Tiebreak interaction.** If both decisions are simultaneously in tiebreak proceedings, the managers acting as tiebreakers must be informed of the interaction analysis before they act. The party notifying the managers of the disagreement must include a link to this section in the notification.

---

## §0.4 Document Issue Date and Clock Mechanism

**Prerequisite fields.** Two named roles are load-bearing for this document's governance mechanisms. **This document cannot reach final form until both of the following placeholders are filled with real names:**

> **Executive Sponsor: [NAME — required before final marking; document cannot be marked final while this field contains placeholder text]**
>
> **Project Coordinator: [NAME — required before final marking; document cannot be marked final while this field contains placeholder text]**

The pre-distribution automation test described below must verify that neither field contains placeholder text. A test that passes while either field contains placeholder text is invalid and must be re-run after the fields are filled.

**Definition of final form.** This document is in final form when two conditions are both satisfied: (a) the engineering lead [Alex Chen] marks the document as final in Confluence, and (b) Alex notifies the product lead [Jordan Rivera] of that marking via the project's standard notification channel. Neither condition alone is sufficient. If the two conditions are satisfied at different times, the later timestamp is the reference time for all downstream obligations.

**Issue date and authoritative timestamp.** The issue date is the timestamp recorded in the Confluence page metadata at the moment Alex applies the "final" marking. This timestamp is set by Confluence automatically and is not editable after the fact. Decision owners must not rely on the document body for the authoritative timestamp — they must check the Confluence page metadata directly. The document body contains the following placeholder, which the Confluence distribution automation fills in from the metadata timestamp at the moment of distribution:

> **Issue date: [FILLED AUTOMATICALLY FROM CONFLUENCE METADATA AT DISTRIBUTION — do not edit manually]**

If the automation fails and the placeholder is not filled, the Confluence metadata timestamp is still authoritative. A blank placeholder is a display defect, not an indication that no issue date exists.

**Timezone and business day calendar.** All time calculations in this document use UTC. All parties are bound by UTC regardless of their local timezone or location. The governing holiday calendar is the project calendar maintained in the Confluence project space under "Project Calendar." The project calendar is maintained by the named Project Coordinator (see prerequisite fields above). A business day is any day that is not a Saturday, Sunday, or a holiday listed in that calendar. If a deadline falls on a non-business day, the deadline moves to the next business day.

**Project calendar integrity requirements.