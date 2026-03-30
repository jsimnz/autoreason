# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This synthesis resolves structural problems identified across two prior drafts. The table below records each problem, the resolution adopted, and its location. Prior drafts are archived at `eng/runbooks/notification-system/drafts/`.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | Engineering Manager is a single point of failure | Deputy EM role defined with specific triggers; oversight body escalation path extended to EM non-performance | §0.2 |
| 2 | NSTL non-performance has no backstop | Tracker readable by all engineers; any team member may trigger EM escalation; EM performs independent weekly spot-check; NSTL Backup role defined | §0.2 |
| 3 | Gate 0 self-confirmation is structurally compromised | EM row confirmed by oversight body representative, not self-confirming; residual limitation documented | §0.3 |
| 4 | Deputy EM appointment entirely within EM's control | Deputy EM appointment requires countersignature from oversight body representative | §0.3 |
| 5 | NSTL makes underdefined judgment on R=3 validity | Replaced with explicit numeric criteria, two named benchmark sources, app category determination made before Gate 3; appeal path to Engineering Manager | §0.4, Gate 3 |
| 6 | Proxy acknowledgment gives NSTL sole custody of gate owner's email | Gate owner must reply to commit notification within 48 hours; unconfirmed proxy commits flagged `[proxy-provisional]` and do not unblock work | §0.1 |
| 7 | Gate 3 consequence clause contradicts its own caveat | If R=3 reliability is in doubt, Gate 3 is a blocking dependency with no sizing fallback | §0.4, Gate 3 |
| 8 | Gate 2 miss triggers upper-bound sizing and delays Gate 3 simultaneously | Gate 3 deadline does not shift on Gate 2 miss; proceeds against original deadline using provisional upper-bound figure | §0.4, Gates 2 and 3 |
| 9 | Deadline clustering creates structural bottleneck for Product Owner | Gates 1, 2, and 4 staggered across Weeks 2, 3, and 4 of Month 1; load distributed | §0.4 |
| 10 | Four-day compression buffer treated as earned planning asset | Buffer removed from slip scenario tables; conditions required to unlock it defined explicitly | §0.5 |
| 11 | Gate 4 tiebreak default ignores security exposure | Default changed to Configuration B; Deputy EM performs tiebreak if EM misses 48-hour window | §0.4, Gate 4 |
| 12 | Gate 1 consequence ignored unknown intent as a third state | Unknown re-engagement intent defaults to conservative upper-bound sizing, not deferral | §0.4, Gate 1 |
| 13 | Gate 0 escalation path depends on Gate 0 resolving | NSTL obtains oversight body contact at project kickoff, before Gate 0, stored in plaintext in tracker | §0.4, Gate 0 |
| 14 | Named individuals not named | Named individuals table is a prerequisite; gate system explicitly inert until filled | §0.3 |
| 15 | Oversight body structurally undefined | Oversight body defined as a named body with minimum two members; escalation produces a defined action, not a notification | §0.5 |
| 16 | 10–15% NSTL burden estimate has no derivation | Estimate replaced with enumerated task list with time allocations; overrun flagging mechanism defined | §0.2 |
| 17 | Provisioned floor arithmetic used inconsistent headroom framings | Single formula used throughout; figures reconciled in one table | §1.4 |
| 18 | Configuration B tiebreak default justified by wrong scenario | Configuration B justified on its own terms for the two-level process-failure case | §0.4, Gate 4 |
| 19 | Slip analysis assumes independent gate failures | Concurrent failure scenario added for Product Owner holding Gates 1, 2, and 4 | §0.5 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff, write access to `gates/` subdirectory granted to gate owners upon Gate 0 resolution), referencing this document by its canonical filename `notification-system-design-v5.md`, with a timestamp.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. The repository's automated commit notification is sent to the gate owner at their registered email address. The gate owner must reply to that notification within 48 hours, confirming that the attached document accurately represents what they sent.
4. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
5. If the gate owner does not confirm within 48 hours, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who contacts the gate owner directly.
6. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

**Why this structure:** The prior single-custody version gave the NSTL sole control over what was committed in the gate owner's name, with no independent verification. The 48-hour confirmation requirement gives the gate owner an independent check. The `[proxy-provisional]` status prevents unconfirmed commits from unblocking work. The gate owner's confirmation reply is a second document in the repository — both are preserved. This path prevents repository access from becoming a bureaucratic barrier; it does not lower the evidentiary standard.

**Residual limitation:** A gate owner who does not check their email would not catch an inaccurate commit. Direct repository access is the standard. This path is a restricted fallback, not a routine mechanism.

---

### 0.2 Enforcement: Honest Account

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. Prior drafts addressed EM non-performance but not NSTL non-performance. This section addresses both, with distinct escalation paths for each.

**Division of responsibilities:**

**The NSTL (one of four backend engineers) is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Confirming that gate resolutions meet the written-acknowledgment standard (§0.1)
- Escalating to the Engineering Manager within 48 hours if a gate owner is unresponsive at a deadline
- Notifying the Deputy EM in writing if the Engineering Manager misses a defined duty

**The Engineering Manager is responsible for:**
- Performing an independent weekly spot-check of the tracker each Monday, independent of the NSTL's update
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the revised project schedule within two business days of any gate slip
- Making the final call on Gate 4 tiebreaks (§0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (§0.5)

**NSTL non-performance — how it surfaces and what happens:**

The gate tracker is readable by all four engineers. The NSTL's Monday update is visible to everyone. The Engineering Manager's independent Monday spot-check creates a second, independent read of the tracker each week. Either mechanism can surface NSTL non-performance:

- **Any team member** who observes that the NSTL has not updated the tracker by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager directly. There is no requirement to go through the NSTL. This is not a bureaucratic override; it is the natural consequence of making the tracker readable.
- **The Engineering Manager's spot-check** independently catches tracker staleness without depending on anyone reporting it.

If the Engineering Manager determines that the NSTL is not performing coordination duties:
1. The Engineering Manager documents the specific missed duty in the tracker.
2. The Engineering Manager temporarily reassigns NSTL coordination duties to the **NSTL Backup** (named individual in §0.3, designated at project kickoff).
3. The Engineering Manager notifies the oversight body (§0.5) within one business day that a coordination duty reassignment has occurred.

**Why this is not a full solution:** If the Engineering Manager is also non-performing, the NSTL Backup path does not activate automatically. The direct team-member-to-oversight-body escalation path (below) is always open and does not require either the NSTL or EM to initiate it.

**Engineering budget impact — derived estimate:**

The 10–15% NSTL burden figure in prior drafts was asserted without derivation. The following is the enumerated basis:

| Task | Frequency | Estimated time per instance | Monthly total |
|------|-----------|-----------------------------|---------------|
| Monday tracker update and gate status verification | Weekly | 45 minutes | ~3 hours |
| Gate owner pre-deadline check-ins (§0.4) | Per gate, 1 week before deadline | 30 minutes | ~1 hour (averaged) |
| Escalation drafting and documentation | Per escalation event | 1–2 hours | ~1 hour (averaged) |
| Proxy commit processing (§0.1) | Per proxy event (rare) | 1 hour | ~0.5 hours (averaged) |
| Gate 3 two-source check | Once, Month 2 | 3–4 hours | ~0.5 hours (averaged over 6 months) |
| **Monthly total** | | | **~6 hours/month** |

Six hours per month across a six-month project is approximately 36 hours total, roughly 2–3% of one engineer's time at standard utilization. This is lower than the prior 10–15% estimate, which conflated gate-system coordination with the broader technical lead role — architecture decisions, code review, unblocking. Those duties are real but are not gate-system coordination and are not counted here.

**Overrun flagging:** If NSTL coordination duties in any given month exceed 10 hours (approximately double the estimate), the NSTL reports this to the Engineering Manager at the next weekly check-in. The Engineering Manager decides whether to redistribute coordination duties or adjust scope. This prevents silent budget erosion.

**If the Engineering Manager does not perform their duties:**

The **Deputy Engineering Manager (Deputy EM)** is a named individual (row in §0.3) with a standing, specific trigger: if the Engineering Manager misses any defined duty — presenting a revised schedule within two business days of a slip, initiating contact within 48 hours of NSTL escalation, deciding a Gate 4 tiebreak within the 48-hour window, or completing the Monday spot-check — the NSTL notifies the Deputy EM in writing. The Deputy EM then:

1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body (§0.5) that the substitution occurred, within one business day.

The Deputy EM does not replace the Engineering Manager on an ongoing basis. The trigger is specific missed duties. If the Engineering Manager is temporarily unavailable (illness, travel), they designate the Deputy EM proactively; in that case, the Deputy EM acts with full authority and no oversight body notification is required.

**If both the Engineering Manager and Deputy EM are non-performing:** Any team member may escalate directly to the oversight body (§0.5). The oversight body representative's contact information is stored in plaintext in the tracker at project kickoff, accessible to all team members, before Gate 0 resolves. This path does not require either the NSTL or EM to initiate it.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by | Date Confirmed |
|------|------|-------|--------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| NSTL Backup (coordination duty fallback) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Deputy Engineering Manager (Deputy EM) | [FILL BEFORE ACTIVE] | | Engineering Manager signature **+ oversight body representative countersignature** | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Engineering Manager (escalation target; Gate 4 tiebreak) | [FILL BEFORE ACTIVE] | | **Oversight body representative signature** | |
| Oversight Body Representative | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |

**Instructions:**
- The oversight body representative fills in the Engineering Manager row. This eliminates direct self-confirmation: the Engineering Manager cannot be the sole authority confirming their own participation in a system they are responsible for enforcing.
- The Engineering Manager fills in the NSTL row, the NSTL Backup row, the Deputy EM row, and the oversight body representative row.
- The Deputy EM row requires both the Engineering Manager's signature and the oversight body representative's countersignature. This means the Deputy EM appointment cannot be completed without the oversight body representative's knowledge and assent. An EM who is not performing their duties cannot unilaterally install a Deputy EM who will cover for them.
- The NSTL fills in the Product Owner, Analytics Owner, and Security Lead rows after confirming each person's acceptance of their role.
- No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

**Residual limitation:** The oversight body representative row is confirmed by the Engineering Manager, meaning the EM retains one degree of influence over who confirms them. This is an improvement over direct self-confirmation but is not a full structural solution. The improvement is that the oversight body is a defined body with minimum two-member composition and specific authority to act (§0.5); the EM cannot name an individual to the oversight body who does not already hold that role within the organization. The residual risk — that an EM might name a representative who is insufficiently independent — cannot be eliminated by document design alone. It is made visible here so it can be evaluated by the organization.

---

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (§0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | End of Week 2, Month 1 |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |

**Pre-Gate 0 requirement:** The NSTL obtains the oversight body representative's contact information from the Engineering Manager at project kickoff. This information is stored in the tracker in plaintext, accessible to all team members. It is not gated on Gate 0 resolution. The Gate 0 slip escalation path cannot depend on Gate 0 having resolved.

**Consequence if missed:**
- The Engineering Manager initiates daily check-ins with whoever is blocking table completion.
- The Engineering Manager presents a revised project schedule to the full team within two business days of the missed deadline.
- If Gate 0 is not resolved by end of Week 4, Month 1, any team member may escalate directly to the oversight body representative using the contact information obtained at kickoff. The escalating team member documents this in the tracker.

**Why Gate 0 exists:** A gate system with no named subjects is inert. Gate 0 is owned by the Engineering Manager rather than the NSTL because the Engineering Manager has organizational authority to assign roles; the NSTL does not.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End