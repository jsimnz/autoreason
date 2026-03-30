# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Document

This document is a synthesis of two prior versions. The revision notes tables from those versions are not reproduced here. This document supersedes both prior versions in full. **Sections are the authoritative record. If a section is missing or truncated, that is a defect regardless of any summary language elsewhere in this document.**

---

## Enforcement-Critical Personnel Fields

These fields must be populated before this document reaches final form. Distribution with either field containing placeholder text is prohibited. The pre-distribution automation test defined in §0.4 must verify both fields are non-empty and do not contain the strings "TBD," "placeholder," "to be determined," or any bracketed text.

**Executive Sponsor:** Priya Anand, VP Engineering

**Project Coordinator:** Sam Delgado, Program Management Office

*If either field above contains placeholder text, this document has not reached final form and must not be distributed.*

---

## 0. Open Decisions

Three decisions require explicit sign-off before implementation begins. The 14-day clock for each decision starts as defined in §0.1 and §0.2 respectively — not uniformly from the issue date. **§0.0's reference to a 14-day clock is a summary only; the authoritative window-start rules are in §0.1 (Decision A) and §0.2 (Decision B), and those rules govern in the event of any conflict with this summary.** Decisions A and B interact; the interaction analysis is in §0.3.

---

## §0.1 Decision A: Worker Allocation Strategy

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Options.**

- **Option A:** Dedicate two of four backend engineers exclusively to the notification system for the full six months.
- **Option B:** Rotate all four engineers through notification work on a two-week sprint cycle, with no engineer dedicated full-time.
- **Option C** *(default)*: Assign two engineers as notification leads with two engineers available for shared infrastructure work, reviewed at the 90-day mark.

**Default if no explicit joint sign-off within 14 days of the evaluation window start: Option C.**

---

**Evaluation window start — authoritative rule.**

The following rules apply in priority order. The first rule whose conditions are satisfied governs.

1. If Jordan Rivera acknowledges receipt of the plain-language summary (per the acknowledgment requirement below) on or before the second business day after the issue date, Jordan's 14-day evaluation window begins at the timestamp of that acknowledgment.
2. If Jordan has not acknowledged by the end of the second business day after the issue date, the window begins at the two-business-day mark regardless of acknowledgment status, and the non-acknowledgment is logged as a process defect per §0.4.
3. The window never begins earlier than the issue date under any circumstance.

**These rules supersede any language in §0.0 that implies the 14-day clock starts uniformly from the issue date.** The issue date remains the reference point for Alex's summary delivery obligation and for the two-business-day acknowledgment deadline; it is not itself the window-start point for Jordan's evaluation.

---

**Plain-language summary obligation.**

Alex Chen must prepare a plain-language summary of Decision A — including a description of each option in non-technical terms, the cost and staffing implications of each option, and the reason Option C is the default — and deliver it to Jordan Rivera within one business day of the issue date. Delivery is via the project's standard notification channel with a Confluence comment logged simultaneously. Alex must not delay delivery of the summary until distribution of the full document; the summary obligation is independent of the distribution obligation in §0.4.

**Acknowledgment and full-document receipt.** Jordan may acknowledge the plain-language summary without having received the full document. Acknowledgment of the summary is sufficient to start Jordan's evaluation window under rule 1 above. Jordan's right to ask questions about the full document before committing to a Decision A selection is preserved; however, the evaluation window clock is not held pending Jordan's receipt of or questions about the full document. If Jordan raises questions about the full document before the window closes, Alex must respond within one business day, but the window continues to run.

**Acknowledgment requirement.** Jordan must acknowledge receipt of the plain-language summary via a Confluence comment within one business day of receiving it. If Jordan does not acknowledge within one business day, Alex must follow up via the project's standard notification channel and log the follow-up attempt in Confluence. If Jordan does not acknowledge within two business days of the original delivery, Alex notifies Taylor Okonkwo (Jordan's manager). Taylor's receipt of that notification starts a one-business-day window for Taylor to confirm Jordan has received and reviewed the summary.

**Consequence for non-delivery of summary.** If Alex does not deliver the plain-language summary within one business day of the issue date, this is a process defect. Morgan Singh logs the defect per §0.4. Alex's failure to deliver the summary does not extend the 14-day evaluation window, but Jordan may raise the non-delivery as a mitigating factor in any subsequent tiebreak proceeding.

---

**Default suspension rule.**

If a disagreement between owners is logged in Confluence per §0.5 before the 14-day window closes, the default does not fire at day 14. The default is suspended while the tiebreak procedure is pending. The default fires when the tiebreaker acts, or when the tiebreaker's 3-business-day deadline passes without action, whichever comes first. This rule applies regardless of whether managers have been notified and regardless of whether managers have responded. If the default is suspended and both managers are notified and both managers fail to respond within their 2-business-day windows, the default remains suspended; it does not fire due to manager non-response. Manager non-response in this state is logged and escalates to the project steering committee per §0.6 as a separate matter. **The default fires only when the tiebreak resolves or the tiebreaker's deadline passes.**

---

**Convergence rule for simultaneous expiration.**

If the tiebreaker's 3-business-day deadline passes without action at a time when the 14-day default window has also closed or would simultaneously close, both paths produce the same outcome: Option C is implemented. No conflict exists between these two paths.

**Logging responsibility for tiebreaker non-action.** The party responsible for logging the tiebreaker's non-action — and therefore responsible for logging the Option C implementation at convergence — is the decision owner who most recently logged a Confluence entry in the tiebreak proceeding prior to the deadline expiration. If both decision owners logged entries on the same business day, Alex Chen logs the non-action and the Option C implementation by default. This definition applies wherever the document refers to "the party responsible for logging the tiebreaker's non-action."

---

**Escalation procedure.**

If the two decision owners disagree, either owner logs the disagreement per §0.5. Both owners must notify their respective managers (Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen) via the project's standard notification channel within one business day of logging the disagreement. Each manager has 2 business days from their own notification timestamp to act as tiebreaker. The two managers' windows run from their respective notification timestamps and are not required to be coterminous.

**Valid response window.** A manager's tiebreaker response is valid only if it arrives before that manager's own 2-business-day window closes, measured from the timestamp of that manager's notification. A response that arrives after a manager's own window has closed is treated as non-response for that manager, regardless of whether the other manager's window is still open.

**Resolution rules.**

- If only one manager submits a valid response, that manager's selection governs.
- If both managers submit valid responses and those responses are not conflicting, the shared selection governs.
- If both managers submit valid responses and those responses conflict, Morgan Singh's selection governs, subject to the Morgan Singh conflict rule below.
- If neither manager submits a valid response, the matter escalates to the project steering committee per §0.6.

**Morgan Singh conflict rule.**

If Morgan Singh has logged an active process defect against Alex Chen at the time a Decision A tiebreak arises — meaning the defect has been logged per §0.4 and has not been resolved or closed per the defect lifecycle defined in §0.4 — Morgan's tiebreaker authority for that Decision A matter is suspended. The executive sponsor (Priya Anand) acts as tiebreaker in Morgan's place.

**Suspension activation point.** The suspension activates at the later of two timestamps: (a) the timestamp at which the disagreement is logged in Confluence per §0.5, and (b) the timestamp at which the relevant process defect is logged per §0.4. If the defect is logged before the disagreement, the suspension activates when the disagreement is logged. If the defect is logged after the disagreement, the suspension activates when the defect is logged. Both timestamps must be recorded in Confluence. Morgan must notify the executive sponsor of the suspension within one business day of the suspension's activation point and must log that notification in Confluence.

**Rationale for later-timestamp rule.** Morgan's tiebreaker authority is suspended because the structural conflict exists, not because Morgan's defect-logging was in bad faith. The suspension cannot activate before the defect exists. Tying the activation to the later timestamp ensures the suspension applies from the first moment both conditions are simultaneously true.

**Ministerial logging preserved.** Morgan's defect-logging function under §0.4 is ministerial and timestamp-dependent and is not reassigned by this rule. The act of logging a defect against Alex does not itself disqualify Morgan from the ministerial logging function; it triggers the tiebreaker suspension only. However, Morgan must recuse from any steering committee deliberation concerning a defect Morgan has logged against Alex Chen. The executive sponsor is notified of Morgan's recusal at the time of escalation.

**Morgan's steering committee participation where Morgan's own conduct is at issue.** When an escalation concerns Morgan's own conduct, Morgan does not self-determine recusal. The party who logged the relevant defect notifies the executive sponsor directly. The executive sponsor determines whether recusal is required. This provision applies independently of the tiebreaker suspension rule above.

---

## §0.2 Decision B: Notification Priority Classification Schema

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Options.**

- **Option X:** Two-tier schema — Critical (delivery within 60 seconds, all channels attempted) and Standard (delivery within 15 minutes, push and in-app only). Classification is set at event-type registration and cannot be overridden at runtime.
- **Option Y:** Three-tier schema — Critical, High, and Standard — with per-tier channel and latency targets as defined in §1 of the main design. Classification may be overridden at runtime by a privileged service account with audit logging.
- **Option Z** *(default)*: Two-tier schema with a runtime override capability restricted to a defined allowlist of event types. Override attempts outside the allowlist are rejected and logged. This is a middle path between Option X's rigidity and Option Y's full runtime flexibility.

**Default if no explicit joint sign-off within 14 days of the evaluation window start: Option Z.**

---

**Evaluation window start.**

The same priority-ordered window-start rules defined in §0.1 apply to Decision B. Rule 1: if Jordan Rivera acknowledges receipt of the Decision B plain-language summary on or before the second business day after the issue date, Jordan's 14-day evaluation window for Decision B begins at the timestamp of that acknowledgment. Rule 2: if Jordan has not acknowledged by the end of the second business day after the issue date, the window begins at the two-business-day mark regardless of acknowledgment status, and the non-acknowledgment is logged as a process defect per §0.4. Rule 3: the window never begins earlier than the issue date. These rules supersede any language in §0.0 that implies the clock starts uniformly from the issue date.

---

**Plain-language summary obligation for Decision B.**

Alex Chen must prepare a plain-language summary of Decision B — including a description of each option in non-technical terms, the engineering complexity and staffing implications of each option, the interaction with Decision A as described in §0.3, and the reason Option Z is the default — and deliver it to Jordan Rivera within one business day of the issue date. Delivery is via the project's standard notification channel with a Confluence comment logged simultaneously. This obligation runs concurrently with the Decision A summary obligation; Alex must deliver both summaries within the same one-business-day window.

**Compounded delivery burden acknowledged.** The requirement to deliver two separate plain-language summaries within one business day is a compounded burden. This document acknowledges that burden and does not treat it as trivial. The following partial-delivery rules apply:

- If Alex delivers the Decision A summary on time but not the Decision B summary, the Decision A window starts per §0.1's rules. The Decision B summary non-delivery is logged as a process defect per §0.4. The Decision B evaluation window does not start until the Decision B summary is delivered or the two-business-day fallback triggers, whichever comes first. Alex's failure to deliver the Decision B summary on time does not extend the Decision A window or affect Decision A's timeline in any way.
- If Alex delivers the Decision B summary on time but not the Decision A summary, the Decision B window starts per this section's rules. The Decision A summary non-delivery is logged as a process defect per §0.4 and the consequences defined in §0.1 apply. The Decision B window is unaffected.
- If Alex delivers neither summary on time, both non-deliveries are logged as separate process defects. Each decision's window is governed independently by the fallback rule.

**Acknowledgment requirement.** Jordan must acknowledge receipt of the Decision B plain-language summary via a Confluence comment within one business day of receiving it. If Jordan does not acknowledge within one business day, Alex must follow up via the project's standard notification channel and log the follow-up attempt in Confluence. If Jordan does not acknowledge within two business days of the original delivery, Alex notifies Taylor Okonkwo (Jordan's manager). Taylor's receipt of that notification starts a one-business-day window for Taylor to confirm Jordan has received and reviewed the Decision B summary.

**Consequence for non-delivery.** If Alex does not deliver the Decision B plain-language summary within one business day of the issue date, Morgan Singh logs the defect per §0.4. Alex's failure does not extend the Decision B evaluation window, but Jordan may raise the non-delivery as a mitigating factor in any subsequent tiebreak proceeding concerning Decision B.

---

**Default suspension rule.**

The same default suspension rule defined in §0.1 applies to Decision B. If a disagreement between owners is logged in Confluence per §0.5 before the Decision B 14-day window closes, the default does not fire at day 14. The default fires when the tiebreaker acts, or when the tiebreaker's 3-business-day deadline passes without action. Manager non-response escalates to the steering committee per §0.6. When the suspension lapse rule in §0.6 applies to Decision B, "the default option for the affected decision" means Option Z, not Option C.

---

**Escalation procedure.**

The same escalation procedure defined in §0.1 applies to Decision B, with the following Decision B-specific provisions.

**Alex Chen's manager for Decision B escalation.** Taylor Okonkwo serves as Jordan Rivera's manager for both Decision A and Decision B. Alex Chen's manager for Decision B escalation purposes is the same person designated as Alex's manager for Decision A escalation purposes, namely Morgan Singh, subject to the Morgan Singh conflict rule in §0.1. If Morgan's tiebreaker authority is suspended at the time a Decision B disagreement arises, the executive sponsor (Priya Anand) acts as tiebreaker in Morgan's place, on the same terms and timeline as defined in §0.1's Morgan Singh conflict rule.

**Simultaneous Decision A and Decision B escalations.** If both decisions are simultaneously in a suspended-default state, the steering committee may consolidate the two matters into a single proceeding at its discretion. Consolidation does not alter any individual deadline. Where consolidation occurs and the two decisions have different suspension start dates, the posting obligation for asynchronous steering committee participation (defined in §0.6) runs from the earlier suspension start date, and all members must meet the participation threshold within the two-business-day window measured from that earlier date.

**Interaction with Decision A.** The three-tier schema (Option Y) requires more engineering capacity to implement and maintain than the two-tier schemas. If Decision A resolves as Option B (rotating all four engineers), Alex Chen must notify Jordan Rivera within two business days that Option Y may not be achievable within the six-month window. Jordan must factor this notification into the Decision B selection. The full interaction analysis is in §0.3.

---

## §0.3 Interaction Analysis: Decisions A and B

**Purpose.** This section is the authoritative analysis of the interaction between Decisions A and B. Decision owners must consult this section before making or logging their selections.

**The dependency.** Decision B's options differ in engineering complexity. Option Y (three-tier schema with full runtime override) requires the most engineering capacity: estimated at approximately 30% more implementation time than Option X or Option Z, based on the engineering lead's assessment at the time of this document's drafting. Decision A determines how engineering capacity is allocated. The interaction is therefore asymmetric: Decision A constrains Decision B, but Decision B does not constrain Decision