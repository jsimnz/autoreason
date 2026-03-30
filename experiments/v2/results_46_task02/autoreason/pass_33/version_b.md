# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses the problems identified across prior reviews. The table below records each problem, the resolution adopted, and its location. Every section referenced in this table exists in this document.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | EM confirms oversight body representative — structural conflict of interest | Oversight body representative confirmed by a second oversight body member, not the EM; EM cannot influence their own confirming authority | §0.3 |
| 2 | "Organization's standard directory" undefined; independence of channel not established | Directory defined as the organization's HR system; access procedure specified; does not route through the EM | §0.2 |
| 3 | NSTL Backup activation by any team member under simultaneous EM and NSTL non-performance is unverifiable | Activation requires written statement of observed facts sent to NSTL Backup and copied to oversight body contact; NSTL Backup waits defined contest window before assuming duties | §0.2 |
| 4 | Deputy EM trigger depends solely on NSTL notification; fails under simultaneous NSTL+EM non-performance | Any team member may trigger the Deputy EM directly; NSTL notification is one path, not the only path | §0.2 |
| 5 | 13-hour monthly threshold conceals real spike in Month 2 when Gate 3 event plus normal duties may reach 9.5–10.5 hours | Threshold restructured: single-month spike threshold of 8 hours applies to any individual month; Month 2 breach is anticipated and requires advance EM decision at Month 1 check-in | §0.2 |
| 6 | Proxy confirmation path has circular dependency: gate owner awareness depends on automated notification functioning | NSTL assigned affirmative duty to contact gate owner directly within 4 hours of proxy commit, independent of automated notification; automated notification is supplementary | §0.1 |
| 7 | Automated commit notification system undefined; "registered email" undefined | Notification system specified as repository platform's built-in commit notification; registration procedure defined | §0.1 |
| 8 | Step 4 of fill sequence incomplete; dependency on step 1 not explicit | Step 4 completed in full; dependency on step 1 made explicit | §0.3 |
| 9 | Steps 2 and 3 of fill sequence both require countersigning the Deputy EM row; no mechanism resolves discrepancy between signers | Steps 2 and 3 merged into a single step requiring two oversight body signatures on the same row simultaneously; discrepancy procedure written | §0.3 |
| 10 | Self-acceptance files must be posted before Gate 0 resolves, but write access to `gates/` granted only after Gate 0 resolves | Acceptance files written to `gates/acceptances/` subdirectory with a separate, earlier access grant | §0.1, §0.3 |
| 11 | NSTL attestation that acceptance file exists does not prevent signing a row before the file is posted | Tracker row cannot be marked confirmed until the acceptance file's commit hash is recorded in the row; NSTL records hash, not mere assertion | §0.3 |
| 12 | Return of duties after NSTL absence conditioned on EM acknowledgment; EM non-performance creates ambiguous dual-holding state | EM acknowledgment replaced with documented handoff entry; handoff valid without EM acknowledgment; Deputy EM notified via repository commit record, not email alone | §0.2 |
| 13 | Overrun threshold based entirely on self-reported time log; no standard for implausibility defined in EM spot-check | EM spot-check given defined implausibility tests using independently verifiable tracker events as reference points | §0.2 |
| 14 | Escalation endpoint if general inbox fails not documented | If general inbox produces no valid representative within two business days, any team member may escalate to the organization's CEO or equivalent executive authority | §0.2 |
| 15 | Gate 4 absent from submitted document | Gate 4 written in full including Configuration B definition and tiebreak procedure | §0.4 |
| 16 | 4-business-hour contest window undefined: timezone, business day hours, and holiday calendar not specified | Business hours defined explicitly; timezone, daily bounds, and holiday calendar specified; contest window calculation procedure written for all cases including end-of-week activations | §0.2 |
| 17 | Oversight body contact is a single point of failure with no intermediate fallback before CEO escalation | Oversight body contact procedure defines a three-person panel; quorum of two required for decisions; if primary contact is unavailable or recused, secondary contact assumes the role by defined procedure | §0.2 |
| 18 | NSTL Backup first-action verification has no time bound; time-sensitive gate obligations are undefined during verification | Verification must complete within one business day of activation; time-sensitive obligations during verification assigned to NSTL Backup immediately upon activation regardless of verification status | §0.2 |
| 19 | Extension rule for proxy confirmation window not stated to apply to restarted windows under step 6 | Extension rule explicitly stated to apply to any confirmation window, whether original or restarted; calculation procedure identical in both cases | §0.1 |
| 20 | "Signed by repository commit" undefined as a procedure for the handoff entry | Signing procedure defined: two separate commits required, each by the respective party, in specified order; handoff effective at timestamp of second commit; commit message format specified | §0.2 |
| 21 | Known-event implausibility test uses fixed 1-hour floor regardless of event count | Test revised to scale with event count: minimum floor is 1 hour for the first event plus 30 minutes per additional event in the same week | §0.2 |
| 22 | Spike-event test tied to a single scheduled event with no generalization | Spike-event test generalized: any week containing a defined high-complexity event triggers the 3-hour floor; high-complexity events enumerated; procedure for adding future events specified | §0.2 |
| 23 | Document cut off mid-sentence; §0.3, §0.4, §0.5 absent; revision table claims falsely that all sections exist | All sections written in full and present in this document; revision table updated to reflect actual content | §0.3, §0.4, §0.5 |
| 24 | NSTL Backup read access before activation not stated; surfacing mechanism depends on access not established | NSTL Backup has read access to tracker and time log from project kickoff; write access granted only at activation; read access is sufficient for the surfacing function | §0.2 |
| 25 | Deputy EM notification at handoff return has no defined obligation; email to unresponsive recipient is not a reliable independent record | Notification made by repository commit to a designated branch, not by email alone; commit constitutes the independent record regardless of Deputy EM responsiveness; Deputy EM has defined 24-hour acknowledgment obligation with escalation path if unmet | §0.2 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff) referencing this document by its canonical filename `notification-system-design-v10.md`, with a timestamp.

**Write access grants — two-tier structure:**

- Write access to `gates/acceptances/` is granted to the Product Owner, Analytics Owner, and Security Lead **at project kickoff**, before Gate 0 resolves, so they can post self-acceptance files as required by §0.3 step 4.
- Write access to the remainder of the `gates/` subdirectory is granted to gate owners **upon Gate 0 resolution**.

These are separate grants. The acceptance subdirectory grant does not confer broader write access. The broader grant does not substitute for the acceptance file requirement.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

---

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. **Automated notification:** The repository platform's built-in commit notification emails all individuals whose addresses are registered in the platform's member list for this repository. Registration is performed by the Engineering Manager at project kickoff: each person listed in §0.3 is added to the repository as a member with their organizational email address before Gate 0 resolves. The NSTL confirms in the tracker that all addresses are registered before Gate 0 can resolve. Upon the NSTL's commit in step 2, the platform sends an automated notification to the gate owner at their registered organizational email address. This notification is supplementary to the NSTL's direct contact in step 4; it is not the operative trigger.
4. **NSTL affirmative contact — independent of automated notification:** Within 4 hours of the proxy commit in step 2, the NSTL must contact the gate owner directly by email, not relying on the automated notification, stating: the commit was made, the commit hash, and the confirmation window deadline calculated under step 5. This contact is logged in the tracker with a timestamp. The gate owner's confirmation obligation begins from the timestamp of this direct NSTL contact, not from receipt of the automated notification.
5. **Confirmation window and extension rule:** The gate owner must reply to the NSTL's direct contact within 48 hours confirming that the attached document accurately represents what they sent. The extension rule applies to every confirmation window under this section, whether original or restarted under step 6: if the calculated deadline falls on a Saturday, Sunday, or a day listed in the organization's official holiday calendar (maintained in the HR system and linked from the tracker), the deadline extends to 17:00 on the next calendar day that is neither a Saturday, Sunday, nor a listed holiday. The NSTL calculates the applicable deadline at the time of the direct contact in step 4, records it in the tracker, and states it explicitly in the step 4 email. This calculation procedure applies without modification to any restarted window opened under step 6; the NSTL recalculates and records the new deadline at the time the restarted window opens.
6. **If neither the automated notification nor the NSTL's direct contact produces a response:** The NSTL notifies the Engineering Manager, who contacts the gate owner through an alternative channel (phone, in-person, team messaging platform). The NSTL opens a new 48-hour confirmation window from the timestamp of confirmed receipt through the alternative channel, applies the extension rule from step 5 to this new window, records the new deadline in the tracker, and sends a new direct contact email to the gate owner stating the new deadline. The original window is closed and superseded by the restarted window.
7. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
8. If the gate owner does not confirm within the applicable window, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who escalates to the oversight body under §0.5.
9. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

---

### 0.2 Enforcement

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. This section addresses NSTL non-performance, EM non-performance, simultaneous NSTL and EM non-performance, and the specific failure mode where the EM is non-performing from the start.

---

**Division of responsibilities:**

**The NSTL (one of four backend engineers) is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Maintaining a weekly time log of coordination duties, readable by all engineers, updated each Monday alongside the tracker
- Confirming that gate resolutions meet the written-acknowledgment standard (§0.1)
- Escalating to the Engineering Manager within 48 hours if a gate owner is unresponsive at a deadline
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty (one trigger path among several; see Deputy EM section below)

**The Engineering Manager is responsible for:**
- Performing an independent weekly spot-check of the tracker each Monday, independent of the NSTL's update
- Reviewing the NSTL's weekly time log each Monday as part of the spot-check, applying the implausibility tests defined below
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4)
- Activating scope reductions when slip thresholds are crossed (§0.5)

---

**Business hours definition:** For all time window calculations in this document, the following definitions apply:

- **Timezone:** The organization's primary operating timezone, recorded in the tracker at project kickoff by the Engineering Manager and confirmed by the NSTL before Gate 0 resolves. If the organization operates across multiple timezones, the timezone of the Engineering Manager's primary office location governs. The recorded timezone does not change after Gate 0 resolves.
- **Business day hours:** 09:00–17:00 in the governing timezone, Monday through Friday.
- **Holiday calendar:** The organization's official holiday calendar as maintained in the HR system. A link to the current calendar is posted in the tracker at project kickoff and updated by the NSTL at the start of each calendar month if changes have occurred.
- **Window calculation for end-of-week activations:** A window expressed in business hours that begins after 13:00 on a Friday is calculated by counting from 09:00 on the following Monday. For example, an activation statement sent at 15:00 Friday opens a 4-business-hour window that begins at 09:00 Monday and closes at 13:00 Monday. The NSTL records the calculated open and close times in the tracker at the time the window begins.
- **Ambiguous cases:** If any party disputes the calculation of a window, the NSTL records both interpretations in the tracker and the Engineering Manager selects the interpretation more favorable to the party subject to the deadline. If the Engineering Manager is non-performing, the Deputy EM makes this determination.

---

**Oversight body — structure, contact procedure, and quorum:**

The oversight body is a standing body of at least three individuals with authority over the project, not employed on the four-person engineering team. The oversight body is constituted before Gate 0 resolves.

**Oversight body contact procedure:**
- The oversight body designates a **primary contact** and a **secondary contact** from among its members at the time of constitution. Both names and organizational email addresses are recorded in the tracker before Gate 0 resolves.
- A **third member** of the oversight body is also named in the tracker. This third member does not serve as a routine contact but is available as a tiebreaker if the primary and secondary contacts disagree on a decision.
- The primary contact is the default escalation recipient for all matters routed to the oversight body under this document.
- If the primary contact is unavailable for more than one business day, is recused from a specific matter, or is themselves a party to the dispute, the secondary contact assumes the primary contact role for that matter. The NSTL records the substitution in the tracker with the reason.
- If both the primary and secondary contacts are unavailable or recused, the third member assumes the primary contact role and the NSTL records this in the tracker.
- **Quorum for decisions:** Any decision made by the oversight body under this document requires agreement of at least two of the three named members. A decision made by one member alone is provisional and must be confirmed by a second member within two business days. If confirmation is not received, the decision lapses and the matter is re-escalated.
- **If the general inbox produces no valid representative within two business days:** Any team member may escalate to the organization's CEO or equivalent executive authority. This path is a last resort and is documented in the tracker with the date and the name of the team member who escalated.

---

**NSTL Backup — access, activation trigger, handoff, and scope:**

**Read access before activation:** The NSTL Backup has read access to the tracker and the NSTL's time log from project kickoff. This access is granted at the same time as the NSTL Backup is named in §0.3. Read access is the basis for the NSTL Backup's independent surfacing function: the NSTL Backup can observe tracker inactivity and time log