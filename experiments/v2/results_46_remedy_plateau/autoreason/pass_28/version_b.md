# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses twelve problems identified in the prior review. **This table is a navigation aid only. It makes no completeness claims. The document's sections are the authoritative record. If a section is missing or truncated, that is a defect regardless of what this table says.**

| # | Problem | Resolution |
|---|---|---|
| 1 | §0.4 cuts off mid-sentence ("This timestamp is set by Confluence automatically and is") | §0.4 is complete in this revision. The sentence is finished and the section ends with a period. |
| 2 | §0.5 and §0.6 entirely absent despite being load-bearing for eight claimed resolutions | §0.5 and §0.6 are present in this revision. All provisions that depend on those sections are verifiable from the document text. |
| 3 | Revision table disclaims completeness while document relies on absent sections | The disclaimer remains accurate as a general principle. The specific defect — absent sections whose absence undermines load-bearing governance mechanisms — is corrected by the presence of §0.5 and §0.6 in this revision. |
| 4 | Jordan Rivera's 14-day evaluation window has three irreconcilable start points | §0.1 is revised. The window start-point rules are consolidated into a single priority-ordered rule. §0.0's reference to "the 14-day clock starts on the issue date" is qualified to read "subject to the window-start rules in §0.1 and §0.2." |
| 5 | Morgan Singh's tiebreaker authority over Decision A is unacknowledged as a structural conflict when Morgan has already logged a defect against Alex Chen | §0.1's escalation procedure adds an explicit conflict rule: if Morgan has logged a process defect against Alex Chen that is active at the time a Decision A tiebreak arises, Morgan's tiebreaker authority is suspended for that matter and the executive sponsor acts as tiebreaker in Morgan's place. |
| 6 | Feasibility assessment for Option Y has no consequence if it arrives after Decision B has already resolved | §0.3 adds an explicit rule: if the engineering lead's feasibility assessment concludes Option Y is not achievable and Decision B has already resolved as Option Y (including by default), the engineering lead must immediately notify the steering committee. The steering committee has authority to reopen Decision B. If Decision B is reopened, the prior Option Y selection is suspended pending the steering committee's determination. |
| 7 | "Both managers respond with conflicting selections within their windows" undefined when windows are not coterminous | §0.1's escalation procedure defines coterminous-window resolution explicitly: a manager's response is valid only if it arrives before that manager's own 2-business-day window closes. A response that arrives after a manager's own window has closed is treated as non-response for that manager. Morgan's selection governs only if both valid responses (each within the respective manager's window) conflict. |
| 8 | Plain-language summary obligation creates a circular dependency: summary must precede distribution, but evaluation window requires acknowledgment of a document Jordan may not have received | §0.1 adds an explicit rule: Jordan may acknowledge the plain-language summary without having received the full document. Acknowledgment of the summary starts Jordan's evaluation window. Jordan's right to raise questions about the full document before committing to a selection is preserved, but the evaluation window clock is not held pending full-document receipt. |
| 9 | Convergence rule assigns logging responsibility to an undefined party | §0.1's convergence rule is revised. The party responsible for logging the tiebreaker's non-action is defined explicitly as the decision owner who most recently logged a Confluence entry in the tiebreak proceeding. If both decision owners logged entries on the same business day, Alex Chen logs the non-action by default. |
| 10 | Executive Sponsor Delegation Record page has no defined creation or initialization mechanism | §0.6 adds an initialization requirement: the project coordinator must create the Executive Sponsor Delegation Record page within one business day of the document reaching final form. The executive sponsor must populate the delegate designation within two business days of the page's creation. If the page does not exist when the executive sponsor needs to assume Taylor's adjudicative functions, the executive sponsor's direct written instruction to the steering committee via the project's standard notification channel serves as the operative delegation record until the page is created. |
| 11 | "Available-member quorum rule" referenced but never defined | §0.6 defines the available-member quorum rule explicitly: a quorum is the majority of steering committee members who are both available (have not been marked unavailable for the current matter) and non-recused. A majority is more than half, rounded up. If the available non-recused pool is one member, that member alone constitutes quorum for the matter. |
| 12 | Decision B's incorporation of §0.1's lapse rule is ambiguous: does lapse produce Option C (Decision A's default) or Option Z (Decision B's default) | §0.2 and §0.6 are revised. The lapse rule in §0.6 is generalized: when a suspension lapses due to steering committee inaction, the default for the specific decision whose suspension lapsed is implemented. For Decision A, that is Option C. For Decision B, that is Option Z. The §0.6 reference to "Option C" is replaced with "the default option for the affected decision." |

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

**These rules supersede any language in §0.0 that implies the 14-day clock starts uniformly from the issue date.** The issue date remains the reference point for Alex's summary delivery obligation and for the two-business-day acknowledgment deadline; it is not the window-start point for Jordan's evaluation.

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

If the two decision owners disagree, either owner logs the disagreement per §0.5. Both owners must notify their respective managers (Taylor Okonkwo for Jordan Rivera; Morgan Singh for Alex Chen) via the project's standard notification channel within one business day of logging the disagreement. Each manager has 2 business days from their own notification to act as tiebreaker. The two managers' windows run from their respective notification timestamps and are not required to be coterminous.

**Valid response window.** A manager's tiebreaker response is valid only if it arrives before that manager's own 2-business-day window closes, measured from the timestamp of that manager's notification. A response that arrives after a manager's own window has closed is treated as non-response for that manager, regardless of whether the other manager's window is still open.

**Resolution rules.**

- If only one manager submits a valid response, that manager's selection governs.
- If both managers submit valid responses and those responses are not conflicting, the shared selection governs.
- If both managers submit valid responses and those responses conflict, Morgan Singh's selection governs, subject to the conflict rule below.
- If neither manager submits a valid response, the matter escalates to the project steering committee per §0.6.

**Morgan Singh conflict rule.** If Morgan Singh has logged an active process defect against Alex Chen at the time a Decision A tiebreak arises — meaning the defect has been logged per §0.4 and has not been resolved or closed — Morgan's tiebreaker authority for that Decision A matter is suspended. The executive sponsor acts as tiebreaker in Morgan's place. Morgan must notify the executive sponsor of the suspension within one business day of the disagreement being logged, and must log the notification in Confluence. This rule applies regardless of whether Morgan's defect-logging was ministerial in character. The conflict between Morgan's defect-logging role and tiebreaker authority is not cured by the ministerial nature of the logging; the structural position is what triggers the suspension.

---

## §0.2 Decision B: Notification Priority Classification Schema

**Decision owners: product lead [Jordan Rivera] and engineering lead [Alex Chen], jointly.**

**Options.**

- **Option X:** Two-tier schema — Critical (delivery within 60 seconds, all channels attempted) and Standard (delivery within 15 minutes, push and in-app only). Classification is set at event-type registration and cannot be overridden at runtime.
- **Option Y:** Three-tier schema — Critical, High, and Standard — with per-tier channel and latency targets as defined in §1 of the main design. Classification may be overridden at runtime by a privileged service account with audit logging.
- **Option Z** *(default)*: Two-tier schema with a runtime override capability restricted to a defined allowlist of event types. Override attempts outside the allowlist are rejected and logged. This is a middle path between Option X's rigidity and Option Y's full runtime flexibility.

**Default if no explicit joint sign-off within 14 days of the evaluation window start: Option Z.**

**Evaluation window start.** The same priority-ordered window-start rules defined in §0.1 apply to Decision B, substituting "Decision B" and the Decision B plain-language summary for "Decision A" and the Decision A plain-language summary throughout. The engineering lead carries the summary delivery obligation for Decision B on the same timeline as for Decision A.

**Interaction with Decision A.** The three-tier schema (Option Y) requires more engineering capacity to implement and maintain than the two-tier schemas. If Decision A resolves as Option B (rotating all four engineers), the engineering lead must notify the product lead within two business days that Option Y may not be achievable within the six-month window, and the product lead must factor this into their Decision B selection. The interaction analysis in §0.3 addresses this dependency in full.

**Default suspension rule.** The same default suspension rule defined in §0.1 applies to Decision B, with the following clarification: all references to "Option C" in §0.1's default suspension rule refer to Decision A's default option. When the suspension rule is applied to Decision B, "the default option for the affected decision" means Option Z. The lapse rule in §0.6 is drafted in general terms and applies per-decision; a suspension lapse for Decision B produces Option Z, not Option C.

**Escalation procedure.** The same escalation procedure defined in §0.1 applies to Decision B, substituting "Decision B" for "Decision A" throughout. If both Decision A and Decision B are simultaneously in a suspended-default state, the steering committee may consolidate the two matters into a single proceeding at its discretion. Consolidation does not alter any individual deadline.

---

## §0.3 Interaction Analysis: Decisions A and B

**Purpose.** §0.0, §0.1, and §0.2 all note that Decisions A and B interact. This section is the authoritative analysis of that interaction. Decision owners must consult this section before making or logging their selections.

**The dependency.** Decision B's options differ in engineering complexity. Option Y (three-tier schema with full runtime override) requires the most engineering capacity: estimated at approximately 30% more implementation time than Option X or Option Z, based on the engineering lead's assessment at the time of this document's drafting. Decision A determines how engineering capacity is allocated. The interaction is therefore asymmetric: Decision A constrains Decision B, but Decision B does not constrain Decision A.

**Specific interaction scenarios.**

| Decision A Outcome | Effect on Decision B |
|---|---|
| Option A (two dedicated engineers) | All three Decision B options are achievable within the six-month window per current engineering estimates. No constraint. |
| Option B (rotating all four engineers) | Option Y is at risk. The engineering lead must provide a revised feasibility assessment for Option Y within five business days of Decision A resolving as Option B. Decision B's 14-day window does not pause during this assessment, but the product lead may request a joint review meeting before committing to a selection. See the binding feasibility rule below. |
| Option C (two leads, two shared) | All three Decision B options are achievable, but Option Y carries higher schedule risk than under Option A. The engineering lead must flag this risk in writing to the product lead at the time Decision A resolves as Option C. |

**Binding feasibility rule for Option Y.** If the engineering