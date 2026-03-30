# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This synthesis resolves structural problems identified across two prior drafts. The table below records each problem, the resolution adopted, and its location. All sections referenced in this table exist in this document.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | Engineering Manager is a single point of failure | Deputy EM role defined with specific triggers; oversight body escalation path extended to EM non-performance | §0.2 |
| 2 | NSTL non-performance has no backstop | Tracker and weekly time log readable by all engineers; any team member may trigger EM escalation; EM performs independent weekly spot-check including time log review; NSTL Backup role defined | §0.2 |
| 3 | Gate 0 self-confirmation is structurally compromised | EM row confirmed by oversight body representative, not self-confirming; residual limitation documented | §0.3 |
| 4 | Deputy EM appointment entirely within EM's control | Deputy EM appointment requires countersignature from oversight body representative; fill sequence enforces ordering dependency | §0.3 |
| 5 | NSTL makes underdefined judgment on R=3 validity | Replaced with explicit numeric criteria, two named benchmark sources, app category determination made before Gate 3; appeal path to Engineering Manager | §0.4, Gate 3 |
| 6 | Proxy acknowledgment gives NSTL sole custody of gate owner's email | Gate owner must reply to commit notification within 48 hours (extended to next business day if deadline falls on weekend or recognized holiday); unconfirmed proxy commits flagged `[proxy-provisional]` and do not unblock work | §0.1 |
| 7 | Gate 3 consequence clause contradicts its own caveat | If R=3 reliability is in doubt, Gate 3 is a blocking dependency with no sizing fallback | §0.4, Gate 3 |
| 8 | Gate 2 miss triggers upper-bound sizing and delays Gate 3 simultaneously | Gate 3 deadline does not shift on Gate 2 miss; proceeds against original deadline using provisional upper-bound figure | §0.4, Gates 2 and 3 |
| 9 | Deadline clustering creates structural bottleneck for Product Owner | Gates 1, 2, and 4 staggered across Weeks 2, 3, and 4 of Month 1; load distributed | §0.4 |
| 10 | Four-day compression buffer treated as earned planning asset | Buffer removed from slip scenario tables; conditions required to unlock it defined explicitly | §0.5 |
| 11 | Gate 4 tiebreak default ignores security exposure | Default changed to Configuration B; Deputy EM performs tiebreak if EM misses 48-hour window | §0.4, Gate 4 |
| 12 | Gate 1 consequence ignored unknown intent as a third state | Unknown re-engagement intent defaults to conservative upper-bound sizing | §0.4, Gate 1 |
| 13 | Gate 0 escalation path depends on Gate 0 resolving | Oversight body contact obtained directly from oversight body at kickoff, not from EM, before Gate 0; stored in plaintext in tracker | §0.2, §0.4 Gate 0 |
| 14 | Named individuals not named | Named individuals table is a prerequisite; gate system explicitly inert until filled per required sequence | §0.3 |
| 15 | Oversight body structurally undefined | Oversight body defined as a named body with minimum two members; escalation produces a defined action, not a notification | §0.5 |
| 16 | 10–15% NSTL burden estimate has no derivation | Estimate replaced with enumerated task list with time allocations including weekly time log; overrun flagging mechanism defined; EM spot-check extended to cover time log | §0.2 |
| 17 | Provisioned floor arithmetic used inconsistent headroom framings | Single formula used throughout; figures reconciled in one table | §1.4 |
| 18 | Configuration B tiebreak default justified by wrong scenario | Configuration B justified on its own terms for the two-level process-failure case | §0.4, Gate 4 |
| 19 | Slip analysis assumes independent gate failures | Concurrent failure scenario added for Product Owner holding Gates 1, 2, and 4 | §0.5 |
| 20 | NSTL overrun flagging relies solely on NSTL self-reporting | EM's Monday spot-check extended to include time log review; NSTL maintains weekly log readable by all engineers; residual falsification risk documented | §0.2 |
| 21 | NSTL confirms three gate owners unilaterally with no countersignature | Each named gate owner must post their own written acceptance to the repository; NSTL signature records that file exists, does not replace it | §0.3 |
| 22 | Proactive EM absence creates evasion path around oversight notification | Proactive absence requires advance written notice to oversight body before first missed duty; substitutions without advance notice treated as non-performance regardless of characterization | §0.2 |
| 23 | Named individuals table has circular fill dependency | Required fill sequence specified explicitly; Deputy EM row cannot be attempted until oversight body representative row is confirmed | §0.3 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff, write access to `gates/` subdirectory granted to gate owners upon Gate 0 resolution), referencing this document by its canonical filename `notification-system-design-v7.md`, with a timestamp.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. The repository's automated commit notification is sent to the gate owner at their registered email address. The gate owner must reply to that notification within 48 hours, confirming that the attached document accurately represents what they sent. **Exception:** If the 48-hour mark falls on a Saturday, Sunday, or a recognized company holiday, the deadline extends to 17:00 on the next business day. The NSTL records the adjusted deadline in the tracker at the time of commit.
4. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
5. If the gate owner does not confirm within the window defined in step 3, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who contacts the gate owner directly.
6. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

**Why this structure:** The prior single-custody version gave the NSTL sole control over what was committed in the gate owner's name, with no independent verification. The confirmation requirement gives the gate owner an independent check. The `[proxy-provisional]` status prevents unconfirmed commits from unblocking work. The gate owner's confirmation reply is a second document in the repository — both are preserved. The business-day extension prevents a gate owner from being penalized for a weekend gap they cannot control.

**Residual limitation:** A gate owner who does not check their email would not catch an inaccurate commit. Direct repository access is the standard. This path is a restricted fallback, not a routine mechanism.

---

### 0.2 Enforcement: Honest Account

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. This section addresses NSTL non-performance, EM non-performance, and the specific failure mode where the EM is non-performing from the start.

**Division of responsibilities:**

**The NSTL (one of four backend engineers) is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Maintaining a weekly time log of coordination duties, readable by all engineers, updated each Monday alongside the tracker
- Confirming that gate resolutions meet the written-acknowledgment standard (§0.1)
- Escalating to the Engineering Manager within 48 hours if a gate owner is unresponsive at a deadline
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty

**The Engineering Manager is responsible for:**
- Performing an independent weekly spot-check of the tracker each Monday, independent of the NSTL's update
- Reviewing the NSTL's weekly time log each Monday as part of the spot-check, and flagging discrepancies or overruns to the team
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§0.5)

**NSTL non-performance — how it surfaces and what happens:**

The gate tracker and NSTL weekly time log are readable by all four engineers. Two independent mechanisms surface NSTL non-performance without requiring anyone to report it through the NSTL:

- **Any team member** who observes that the NSTL has not updated the tracker or time log by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager directly. There is no requirement to go through the NSTL.
- **The Engineering Manager's Monday spot-check** independently verifies tracker accuracy and time log completeness without depending on anyone reporting it. Because the time log is maintained by the NSTL and readable by the EM, the EM can identify missing entries or implausible figures without the NSTL initiating the report.

**Why the time log partially but not fully resolves the self-reporting problem:** An NSTL who is deliberately underreporting time expenditure could maintain a false log. The EM's spot-check can catch implausible figures — a week with no log entry, or a week where a known escalation event appears to have consumed zero time — but cannot verify accurate reporting of time the EM did not observe. This residual risk is documented here. The mechanism catches negligence and omission more reliably than deliberate falsification.

If the Engineering Manager determines that the NSTL is not performing coordination duties:
1. The Engineering Manager documents the specific missed duty in the tracker.
2. The Engineering Manager temporarily reassigns NSTL coordination duties to the **NSTL Backup** (named individual in §0.3, designated at project kickoff).
3. The Engineering Manager notifies the oversight body (§0.5) within one business day that a coordination duty reassignment has occurred.

**Engineering budget impact — derived estimate:**

| Task | Frequency | Estimated time per instance | Monthly total |
|------|-----------|-----------------------------|---------------|
| Monday tracker update and gate status verification | Weekly | 45 minutes | ~3 hours |
| Weekly time log update | Weekly | 10 minutes | ~0.5 hours |
| Gate owner pre-deadline check-ins (§0.4) | Per gate, 1 week before deadline | 30 minutes | ~1 hour (averaged) |
| Escalation drafting and documentation | Per escalation event | 1–2 hours | ~1 hour (averaged) |
| Proxy commit processing (§0.1) | Per proxy event (rare) | 1 hour | ~0.5 hours (averaged) |
| Gate 3 two-source benchmark check | Once, Month 2 | 3–4 hours | ~0.5 hours (averaged over 6 months) |
| **Monthly total** | | | **~6.5 hours/month** |

Six and a half hours per month across a six-month project is approximately 39 hours total, roughly 2–3% of one engineer's time at standard utilization. This is lower than earlier estimates that conflated gate-system coordination with the broader technical lead role — architecture decisions, code review, unblocking. Those duties are real but are not gate-system coordination and are not counted here.

**Overrun flagging:** If the NSTL's weekly time log shows coordination duties exceeding 10 hours in any given month (approximately double the baseline), the Engineering Manager flags this at the next weekly check-in and decides whether to redistribute coordination duties or adjust scope. This prevents silent budget erosion.

**EM proactive absence — preventing the evasion path:**

When the Engineering Manager is temporarily unavailable (illness, travel), they must provide advance written notice to the oversight body (§0.5) before the absence begins, designating the Deputy EM and stating the expected duration. "Advance" means before the first missed duty, not after.

If a substitution occurs without advance notice — regardless of how it is characterized by the EM — it is treated as non-performance for the purposes of the Deputy EM trigger and oversight notification requirement. The distinction between voluntary absence and non-performance cannot be made unilaterally by the person whose performance is in question.

**If the Engineering Manager does not perform their duties:**

The **Deputy Engineering Manager (Deputy EM)** is a named individual (row in §0.3) with a standing, specific trigger: if the Engineering Manager misses any defined duty without advance notice to the oversight body, the NSTL notifies the Deputy EM in writing. The Deputy EM then:

1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body (§0.5) that the substitution occurred, within one business day.

The Deputy EM does not replace the Engineering Manager on an ongoing basis. The trigger is specific missed duties.

**If both the Engineering Manager and Deputy EM are non-performing:**

Any team member may escalate directly to the oversight body. The oversight body representative's contact information is **obtained directly from the oversight body at project kickoff, not from the Engineering Manager.** The procedure is:

1. At project kickoff, the NSTL contacts the oversight body through the organization's standard directory — not through the EM — and requests the name and direct contact of the representative assigned to this project.
2. This information is stored in the tracker in plaintext, accessible to all team members, before Gate 0 resolves.
3. The NSTL confirms receipt of this information in the tracker with a timestamp.

**Why this matters:** If the oversight contact is obtained from the EM, an EM who is non-performing from the start could provide incorrect or stale contact information, or simply not provide it. Obtaining it through an independent organizational channel removes the EM from this dependency entirely. The Gate 0 escalation path cannot depend on Gate 0 having resolved.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled in the sequence specified below before any other gate can be assigned to an owner.

**Required fill sequence — ordering dependency:**

The Deputy EM row requires the oversight body representative's countersignature. The oversight body representative row must therefore be confirmed before the Deputy EM row can be completed. The required sequence is:

1. Engineering Manager confirms the NSTL row and the NSTL Backup row.
2. Oversight body representative confirms the Engineering Manager row (the EM does not self-confirm).
3. Oversight body representative countersigns the Deputy EM row alongside the Engineering Manager's signature.
4. NSTL confirms the Product Owner, Analytics Owner, and Security Lead rows — but only after each named individual provides their own written acceptance (see below).

Steps 1 and 2 can proceed in parallel. Step 3 cannot begin until step 2 is complete. Step 4 can proceed in parallel with steps 1–3.

**Gate owner self-acceptance requirement:** For the Product Owner, Analytics Owner, and Security Lead rows, the NSTL's signature records that the named individual was contacted and accepted the role. It does not substitute for that acceptance. Each named individual must post their own written acceptance to `gates/acceptances/[role]-acceptance-[date].txt` in the repository before their row is considered confirmed. The NSTL's signature in the table records that this file exists; it does not replace it.

**Why this matters:** This closes the asymmetry between how the NSTL is confirmed (by the EM, a person with organizational authority over the appointment) and how gate owners were previously confirmed (by the NSTL alone, without the gate owner's own record). A gate owner who later disputes their role cannot point to the absence of their own acceptance document.

| Role | Name | Email | Confirmed by | Acceptance file / countersign