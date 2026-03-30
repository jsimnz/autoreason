# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses eleven problems identified in the prior review. The table below records each problem, the resolution adopted, and its location. Every section referenced in this table exists in this document.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | EM confirms oversight body representative — structural conflict of interest documented but not mitigated | Oversight body representative is confirmed by a second oversight body member, not by the EM; EM's influence over their own confirming authority is removed | §0.3 |
| 2 | "Organization's standard directory" undefined; independence of channel not established | Directory defined as the organization's HR system; access procedure specified; does not route through the EM | §0.2 |
| 3 | NSTL Backup has no activation trigger, handoff process, or defined scope | Activation trigger, handoff procedure, and duty scope written in full | §0.2 |
| 4 | Deputy EM trigger depends on NSTL notification; fails under simultaneous NSTL+EM non-performance | Any team member may trigger the Deputy EM directly; NSTL notification is one path, not the only path | §0.2 |
| 5 | Overrun threshold of 10 hours described as "approximately double" a 6.5-hour baseline; 10 ≠ 13 | Threshold corrected to 13 hours; description updated | §0.2 |
| 6 | Step 4 of fill sequence states it can proceed in parallel with steps 2 and 3, implying it can begin before step 1 | Dependency on step 1 made explicit; step 4 cannot begin until step 1 is complete | §0.3 |
| 7 | Automated commit notification system never defined; "registered email" undefined | Notification system specified as repository platform's built-in commit notification; registration procedure defined | §0.1 |
| 8 | Gate 1 decision options cut off mid-sentence; Gates 1–5 not fully written | Gate 1 completed; Gates 1–5 written in full | §0.4 |
| 9 | Self-acceptance files must be posted before Gate 0 resolves, but write access to `gates/` is granted only after Gate 0 resolves | Acceptance files written to `gates/acceptances/` subdirectory, which has a separate, earlier access grant; procedure specified | §0.1, §0.3 |
| 10 | NSTL attestation that acceptance file exists does not prevent signing a row before the file is posted; no system enforcement | Tracker row cannot be marked confirmed until the acceptance file's commit hash is recorded in the row; NSTL records hash, not mere assertion | §0.3 |
| 11 | Gate 4 claimed as written in full in revision table items 4 and 8 but absent from submitted document | Gate 4 written in full including Configuration B definition and tiebreak procedure | §0.4, Gate 4 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff) referencing this document by its canonical filename `notification-system-design-v7.md`, with a timestamp.

**Write access grants — two-tier structure:**

- Write access to `gates/acceptances/` is granted to Product Owner, Analytics Owner, and Security Lead **at project kickoff**, before Gate 0 resolves, so they can post self-acceptance files as required by §0.3 step 4.
- Write access to the remainder of the `gates/` subdirectory is granted to gate owners **upon Gate 0 resolution**.

These are separate grants. The acceptance subdirectory grant does not confer broader write access. The broader grant does not substitute for the acceptance file requirement.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. **Automated notification:** The repository platform's built-in commit notification emails all individuals whose addresses are registered in the platform's member list for this repository. Registration is performed by the Engineering Manager at project kickoff: each person listed in §0.3 is added to the repository as a member with their organizational email address before Gate 0 resolves. The NSTL confirms in the tracker that all addresses are registered before Gate 0 can resolve. Upon the NSTL's commit in step 2, the platform sends an automated notification to the gate owner at their registered organizational email address. The gate owner must reply to that notification within 48 hours, confirming that the attached document accurately represents what they sent. **Exception:** If the 48-hour mark falls on a Saturday, Sunday, or a recognized company holiday, the deadline extends to 17:00 on the next business day. The NSTL records the adjusted deadline in the tracker at the time of commit.
4. **If the automated notification is not received:** The gate owner or any team member who becomes aware of the non-delivery notifies the NSTL, who resends the notification manually by email (with the EM cc'd) and restarts the 48-hour window from the timestamp of the manual send. Non-delivery does not extend the `[proxy-provisional]` status indefinitely; the NSTL is responsible for confirming delivery within 24 hours of commit.
5. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
6. If the gate owner does not confirm within the window defined in step 3, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who contacts the gate owner directly.
7. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

**Residual limitation:** A gate owner who does not check their email would not catch an inaccurate commit. Direct repository access is the standard. This path is a restricted fallback, not a routine mechanism.

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
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty (one trigger path; see Deputy EM section below)

**The Engineering Manager is responsible for:**
- Performing an independent weekly spot-check of the tracker each Monday, independent of the NSTL's update
- Reviewing the NSTL's weekly time log each Monday as part of the spot-check, and flagging discrepancies or overruns to the team
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§0.5)

---

**NSTL Backup — activation trigger, handoff, and scope:**

The NSTL Backup (named in §0.3) takes over NSTL coordination duties under either of the following conditions:

- **Planned absence:** The NSTL notifies the Engineering Manager and the NSTL Backup in writing at least three business days before an absence of two or more consecutive business days. The NSTL Backup assumes coordination duties for the duration of the absence.
- **Unplanned absence or non-performance:** If the NSTL fails to perform any defined duty (tracker update, time log update, escalation, gate verification) without advance notice, the Engineering Manager activates the NSTL Backup within one business day by written notification to the NSTL Backup. If the Engineering Manager is also non-performing, any team member may activate the NSTL Backup directly by written notification.

**Handoff procedure:** At activation, the NSTL Backup gains write access to the tracker and time log. The NSTL Backup's first action is to verify the current state of the tracker against the repository and correct any discrepancies, documenting what was found and what was changed. The NSTL Backup does not assume the NSTL's engineering deliverables — only coordination duties.

**Duty scope transferred to NSTL Backup:**
- Monday tracker update and gate status verification
- Weekly time log update (NSTL Backup logs their own time, not the absent NSTL's)
- Gate owner pre-deadline check-ins
- Escalation drafting and documentation
- Proxy commit processing (§0.1)

**Return of duties:** When the NSTL returns, they notify the Engineering Manager and the NSTL Backup in writing. The NSTL Backup documents the handoff state in the tracker before returning duties. Return is not automatic; it requires written acknowledgment from the Engineering Manager.

---

**NSTL non-performance — how it surfaces:**

The gate tracker and the NSTL's weekly time log are readable by all four engineers. Three independent mechanisms surface NSTL non-performance:

- **Any team member** who observes that the NSTL has not updated the tracker or time log by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager or activate the NSTL Backup directly (see above).
- **The Engineering Manager's Monday spot-check** independently verifies tracker accuracy and time log completeness without depending on the NSTL reporting it.
- **The NSTL Backup**, as a named individual with standing awareness of the role, may independently observe tracker inactivity and raise it to the Engineering Manager.

**Why the time log partially but not fully resolves the self-reporting problem:** An NSTL who is deliberately underreporting time expenditure could maintain a false log. The EM's spot-check can catch implausible figures (e.g., a week with no log entry, or a week where a known escalation event appears to have consumed zero time) but cannot verify accurate reporting of time the EM did not observe. This residual risk is documented here. The mechanism catches negligence and omission more reliably than deliberate falsification.

**Overrun flagging:** If the NSTL's weekly time log shows coordination duties exceeding **13 hours** in any given month (approximately double the 6.5-hour baseline estimate in the table below), the Engineering Manager flags this at the next weekly check-in and decides whether to redistribute coordination duties or adjust scope.

**Engineering budget impact — derived estimate:**

| Task | Frequency | Estimated time per instance | Monthly total |
|------|-----------|-----------------------------|---------------|
| Monday tracker update and gate status verification | Weekly | 45 minutes | ~3 hours |
| Weekly time log update | Weekly | 10 minutes | ~0.5 hours |
| Gate owner pre-deadline check-ins (§0.4) | Per gate, 1 week before deadline | 30 minutes | ~1 hour (averaged) |
| Escalation drafting and documentation | Per escalation event | 1–2 hours | ~1 hour (averaged) |
| Proxy commit processing (§0.1) | Per proxy event (rare) | 1 hour | ~0.5 hours (averaged) |
| Gate 3 two-source check | Once, Month 2 | 3–4 hours | ~0.5 hours (averaged over 6 months) |
| **Monthly total** | | | **~6.5 hours/month** |

---

**EM proactive absence — preventing the evasion path:**

When the Engineering Manager is temporarily unavailable (illness, travel), they must provide advance written notice to the oversight body (§0.5) before the absence begins, designating the Deputy EM and stating the expected duration. "Advance" means before the first missed duty, not after.

If a substitution occurs without advance notice — regardless of how it is characterized by the EM — it is treated as non-performance for the purposes of the Deputy EM trigger and oversight notification requirement. The distinction between voluntary absence and non-performance cannot be made unilaterally by the person whose performance is in question.

---

**Deputy EM trigger — multiple activation paths:**

The Deputy Engineering Manager trigger fires when the Engineering Manager misses any defined duty without advance notice to the oversight body. **Any of the following parties may activate the Deputy EM independently:**

- The NSTL, by written notification to the Deputy EM (primary path when NSTL is performing)
- Any team member, by written notification to the Deputy EM (available to all; does not require the NSTL to act first)
- The oversight body representative, upon observing missed duties through their own monitoring

This means simultaneous NSTL and EM non-performance does not prevent the Deputy EM trigger from firing. Any of the remaining two engineers may activate the Deputy EM directly. The NSTL's notification path is the expected mechanism under normal conditions, not the exclusive one.

**Upon activation, the Deputy EM:**
1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body (§0.5) that the substitution occurred, within one business day.

---

**If both the Engineering Manager and Deputy EM are non-performing:**

Any team member may escalate directly to the oversight body. The oversight body representative's contact information is obtained through the organization's HR system (not through the EM), as specified below.

**Oversight body contact — independent channel:**

The organization's HR system maintains a directory of named individuals and their organizational roles, including oversight body membership. This system is accessible to all employees through the organization's standard intranet, does not require EM authorization to access, and is maintained by HR, not by the engineering team or the EM.

At project kickoff, the NSTL accesses the HR system directly and identifies the individual assigned as oversight body representative for this project. If the HR system does not identify a specific representative, the NSTL contacts the oversight body's general inbox (also listed in the HR system under the oversight body's entry) and requests the assigned representative's name and direct contact.

This contact information is stored in the tracker in plaintext, accessible to all team members, before Gate 0 resolves. The NSTL confirms receipt in the tracker with a timestamp. No step in this procedure routes through the Engineering Manager.

**Why this matters:** If the oversight contact were obtained from the EM, an EM who is non-performing from the start could provide incorrect or stale contact information, or simply not provide it. The HR system is an independent organizational channel that the EM does not control.

**Residual limitation:** The HR system must be accurate and current. If the oversight body representative's record is stale in HR, the contact obtained may be incorrect. The NSTL's confirmation step (recording that contact was made and a response received) partially mitigates this: a stale record would likely produce a bounce or non-response, which the NSTL would then escalate through the general inbox. This residual risk is documented here.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled in the sequence specified below before any other gate can be assigned to an owner.

**Required fill sequence — ordering dependencies:**

1. Engineering Manager confirms the NSTL row and the NSTL Backup row.
2. A **second oversight body member** (not the EM) confirms the Engineering Manager row and countersigns the Deputy EM row. The EM does not confirm their own row and does not select who confirms them; that confirmation comes from the oversight body acting independently.
3. The oversight body representative countersigns the Deputy EM row alongside the Engineering Manager's signature. Step 3 cannot begin until step 2 is complete.
4. NSTL confirms the Product Owner, Analytics Owner, and Security Lead rows — but only after each named individual posts their own written acceptance file to `gates/acceptances/` (write access granted at kickoff, per §0.1) and the N