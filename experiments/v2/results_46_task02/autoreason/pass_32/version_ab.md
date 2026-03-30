# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses the problems identified across prior reviews. The table below records each problem, the resolution adopted, and its location. Every section referenced in this table exists in this document.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | EM confirms oversight body representative — structural conflict of interest | Oversight body representative confirmed by a second oversight body member, not the EM; EM cannot influence their own confirming authority | §0.3 |
| 2 | "Organization's standard directory" undefined; independence of channel not established | Directory defined as the organization's HR system; access procedure specified; does not route through the EM | §0.2 |
| 3 | NSTL Backup activation by any team member under simultaneous EM and NSTL non-performance is unverifiable | Activation requires written statement of observed facts sent to NSTL Backup and copied to oversight body contact; NSTL Backup waits 4 business hours before assuming duties to allow contest | §0.2 |
| 4 | Deputy EM trigger depends solely on NSTL notification; fails under simultaneous NSTL+EM non-performance | Any team member may trigger the Deputy EM directly; NSTL notification is one path, not the only path | §0.2 |
| 5 | 13-hour monthly threshold conceals real spike in Month 2 when Gate 3 event plus normal duties may reach 9.5–10.5 hours | Threshold restructured: single-month spike threshold of 8 hours applies to any individual month; Month 2 breach is anticipated and requires advance EM decision at Month 1 check-in | §0.2 |
| 6 | Proxy confirmation path has circular dependency: gate owner awareness depends on automated notification functioning | NSTL assigned affirmative duty to contact gate owner directly within 4 hours of proxy commit, independent of automated notification; automated notification is supplementary | §0.1 |
| 7 | Automated commit notification system undefined; "registered email" undefined | Notification system specified as repository platform's built-in commit notification; registration procedure defined | §0.1 |
| 8 | Step 4 of fill sequence incomplete; dependency on step 1 not explicit | Step 4 completed in full; dependency on step 1 made explicit | §0.3 |
| 9 | Steps 2 and 3 of fill sequence both require countersigning the Deputy EM row; no mechanism resolves discrepancy between signers | Steps 2 and 3 merged into a single step requiring two oversight body signatures on the same row simultaneously; discrepancy procedure written | §0.3 |
| 10 | Self-acceptance files must be posted before Gate 0 resolves, but write access to `gates/` granted only after Gate 0 resolves | Acceptance files written to `gates/acceptances/` subdirectory with a separate, earlier access grant | §0.1, §0.3 |
| 11 | NSTL attestation that acceptance file exists does not prevent signing a row before the file is posted | Tracker row cannot be marked confirmed until the acceptance file's commit hash is recorded in the row; NSTL records hash, not mere assertion | §0.3 |
| 12 | Return of duties after NSTL absence conditioned on EM acknowledgment; EM non-performance creates ambiguous dual-holding state | EM acknowledgment replaced with documented handoff entry signed by both NSTL and NSTL Backup; handoff valid without EM acknowledgment if EM is non-performing; Deputy EM notified | §0.2 |
| 13 | Overrun threshold based entirely on self-reported time log; no standard for implausibility defined in EM spot-check | EM spot-check given three defined implausibility tests using independently verifiable tracker events as reference points | §0.2 |
| 14 | Escalation endpoint if general inbox fails not documented | If general inbox produces no valid representative within two business days, any team member may escalate to the organization's CEO or equivalent executive authority | §0.2 |
| 15 | Gate 4 absent from submitted document | Gate 4 written in full including Configuration B definition and tiebreak procedure | §0.4 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff) referencing this document by its canonical filename `notification-system-design-v9.md`, with a timestamp.

**Write access grants — two-tier structure:**

- Write access to `gates/acceptances/` is granted to Product Owner, Analytics Owner, and Security Lead **at project kickoff**, before Gate 0 resolves, so they can post self-acceptance files as required by §0.3 step 4.
- Write access to the remainder of the `gates/` subdirectory is granted to gate owners **upon Gate 0 resolution**.

These are separate grants. The acceptance subdirectory grant does not confer broader write access. The broader grant does not substitute for the acceptance file requirement.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

---

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. **Automated notification:** The repository platform's built-in commit notification emails all individuals whose addresses are registered in the platform's member list for this repository. Registration is performed by the Engineering Manager at project kickoff: each person listed in §0.3 is added to the repository as a member with their organizational email address before Gate 0 resolves. The NSTL confirms in the tracker that all addresses are registered before Gate 0 can resolve. Upon the NSTL's commit in step 2, the platform sends an automated notification to the gate owner at their registered organizational email address. This notification is supplementary to the NSTL's direct contact in step 4; it is not the operative trigger.
4. **NSTL affirmative contact — independent of automated notification:** Within 4 hours of the proxy commit in step 2, the NSTL must contact the gate owner directly by email, not relying on the automated notification, stating: the commit was made, the commit hash, and the 48-hour confirmation window. This contact is logged in the tracker with a timestamp. The gate owner's 48-hour confirmation obligation begins from the timestamp of this direct NSTL contact, not from receipt of the automated notification. This eliminates the circular dependency in which the gate owner's awareness of the proxy commit depended on the automated system functioning correctly.
5. The gate owner must reply to the NSTL's direct contact within 48 hours, confirming that the attached document accurately represents what they sent. **Exception:** If the 48-hour mark falls on a Saturday, Sunday, or a recognized company holiday, the deadline extends to 17:00 on the next business day. The NSTL records the adjusted deadline in the tracker at the time of commit.
6. **If neither the automated notification nor the NSTL's direct contact produces a response:** The NSTL notifies the Engineering Manager, who contacts the gate owner through an alternative channel (phone, in-person, team messaging platform). The NSTL restarts the 48-hour window from the timestamp of confirmed receipt through the alternative channel and records this in the tracker.
7. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
8. If the gate owner does not confirm within the applicable window, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who escalates to the oversight body under §0.5.
9. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

**Residual limitation:** A gate owner who does not respond to the NSTL's direct contact, the automated notification, or the Engineering Manager's alternative-channel contact has exhausted the available mechanisms. The gate remains unresolved and the Engineering Manager escalates to the oversight body under §0.5. Direct repository access is the standard path; this proxy procedure is a restricted fallback, not a routine mechanism.

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
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§0.5)

---

**NSTL Backup — activation trigger, handoff, and scope:**

The NSTL Backup (named in §0.3) takes over NSTL coordination duties under either of the following conditions:

- **Planned absence:** The NSTL notifies the Engineering Manager and the NSTL Backup in writing at least three business days before an absence of two or more consecutive business days. The NSTL Backup assumes coordination duties for the duration of the absence.
- **Unplanned absence or non-performance:** If the NSTL fails to perform any defined duty (tracker update, time log update, escalation, gate verification) without advance notice, the Engineering Manager activates the NSTL Backup within one business day by written notification to the NSTL Backup. If the Engineering Manager is also non-performing, any team member may activate the NSTL Backup directly, subject to the verification procedure below.

**Activation by a non-NSTL, non-EM team member — verification procedure:** When neither the NSTL nor the EM is available to perform the activation, the activating team member must:

1. Send a written statement to the NSTL Backup by email describing the specific observed facts that constitute non-performance (e.g., "Monday tracker update was not made as of 17:00; no advance notice was given; the NSTL has not responded to direct message sent at 14:00").
2. Copy that written statement simultaneously to the oversight body contact stored in the tracker (see oversight body contact procedure below).
3. The NSTL Backup, upon receiving this statement, waits **4 business hours** before assuming duties. During this window, the NSTL or EM may contest the activation in writing to the NSTL Backup. If no contest is received within 4 business hours, the NSTL Backup assumes coordination duties and records the activation time in the tracker.
4. If the activation is contested, the NSTL Backup notifies the oversight body contact and does not assume duties until the oversight body representative resolves the dispute.

This procedure gives the NSTL Backup a defined basis for confirming the activation is legitimate without requiring the EM's involvement, while preserving a brief window for a false trigger to be corrected.

**Handoff procedure:** At activation, the NSTL Backup gains write access to the tracker and time log. The NSTL Backup's first action is to verify the current state of the tracker against the repository and correct any discrepancies, documenting what was found and what was changed. The NSTL Backup does not assume the NSTL's engineering deliverables — only coordination duties.

**Duty scope transferred to NSTL Backup:**
- Monday tracker update and gate status verification
- Weekly time log update (NSTL Backup logs their own time, not the absent NSTL's)
- Gate owner pre-deadline check-ins
- Escalation drafting and documentation
- Proxy commit processing (§0.1)

**Return of duties after NSTL absence:**

When the NSTL is ready to return, the NSTL and the NSTL Backup jointly create a handoff entry in the tracker documenting: the date of return, the current state of all open gate items, and any outstanding actions. Both the NSTL and the NSTL Backup sign this entry by repository commit before the return takes effect. The NSTL Backup notifies the Deputy EM by email that the handoff is complete.

Engineering Manager acknowledgment is **not required** for the return to be valid. If the EM is non-performing at the time of return, the handoff proceeds without EM acknowledgment and the Deputy EM is notified as described above. The Deputy EM's notification serves as the independent record that the handoff occurred. This eliminates the ambiguous dual-holding state that would result from conditioning return on EM availability.

---

**NSTL non-performance — how it surfaces:**

The gate tracker and the NSTL's weekly time log are readable by all four engineers. Three independent mechanisms surface NSTL non-performance:

- **Any team member** who observes that the NSTL has not updated the tracker or time log by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager or activate the NSTL Backup directly (see above).
- **The Engineering Manager's Monday spot-check** independently verifies tracker accuracy and time log completeness without depending on the NSTL reporting it.
- **The NSTL Backup**, as a named individual with standing awareness of the role, may independently observe tracker inactivity and raise it to the Engineering Manager.

**Why the time log partially but not fully resolves the self-reporting problem:** An NSTL who is deliberately underreporting time expenditure could maintain a false log. The EM's spot-check applies the implausibility tests defined below to catch the most detectable forms of manipulation. Deliberate falsification that is internally consistent with observable events is a residual risk that these tests do not fully eliminate; this is documented.

**EM spot-check implausibility tests:** The Engineering Manager's Monday review of the time log applies three defined tests. A log entry that fails any test is flagged to the team at the next check-in:

1. **Zero-entry test:** Any week in which the NSTL log shows zero hours for coordination duties is implausible unless the NSTL Backup was active for the full week. If the NSTL Backup was not active and no advance absence notice was filed, a zero-entry week is flagged.
2. **Known-event test:** Any week in which a proxy commit, an escalation, or a gate deadline check-in is recorded in the tracker must show at least 1 hour of coordination time in the NSTL's log. If the log shows less than 1 hour in such a week, it is flagged.
3. **Spike-event test:** In any week in which the Gate 3 two-source check is scheduled (occurring in Month 2), the log must show at least 3 hours of coordination time. If the log shows less than 3 hours that week, it is flagged.

These tests use observable, independently verifiable events in the tracker as reference points. They do not depend on the NSTL's self-report being accurate; they compare the self-report against records the NSTL does not exclusively control.

**Overrun thresholds — restructured:**

The prior single monthly threshold of 13 hours is retired because it concealed real workload spikes in individual months. Two thresholds now apply:

- **Single-month spike threshold:** If the NSTL's time log shows coordination duties exceeding **8 hours in any individual month**, the Engineering Manager flags this at the next weekly check-in and decides whether to redistribute coordination duties or adjust scope.
- **Month 2 monitoring point:** The Gate 3 two-source check (3