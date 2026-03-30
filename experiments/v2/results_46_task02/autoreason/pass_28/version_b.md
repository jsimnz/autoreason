# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten structural problems identified in the prior draft. The table below records each problem, the resolution adopted, and its location. Prior drafts are archived at `eng/runbooks/notification-system/drafts/`.

| # | Problem | Resolution | Location |
|---|---------|------------|----------|
| 1 | NSTL non-performance has no backstop | Weekly gate status is readable by all engineers; any team member may trigger EM escalation; EM performs independent weekly spot-check | §0.2 |
| 2 | Gate 3 two-source check hides discretion inside lookup task | Discretion acknowledged explicitly; specific benchmark sources named in advance; app category determination made before Gate 3 by Product Owner; range [1.5, 6] labeled as a conventional bound, not a derived value | §0.4, Gate 3 |
| 3 | Oversight body is structurally undefined | Oversight body defined as a named body with specific authority; minimum two members required; escalation produces a defined action, not a notification | §0.5 |
| 4 | Proxy acknowledgment gives NSTL sole custody of gate owner's email | Gate owner must reply to NSTL's commit notification within 48 hours to confirm accuracy; unconfirmed proxy commits are flagged as provisional | §0.1 |
| 5 | Gate 2 miss triggers upper-bound sizing and delays Gate 3 simultaneously | Gate 3 deadline does not shift on Gate 2 miss; Gate 3 proceeds against original deadline using provisional upper-bound figure | §0.4, Gates 2 and 3 |
| 6 | Deputy EM appointment is entirely within EM's control | Deputy EM appointment requires countersignature from oversight body representative, independent of EM | §0.3 |
| 7 | Deadline clustering creates structural bottleneck regardless of intent | Gates 1, 2, and 4 staggered across Weeks 2, 3, and 4 of Month 1; Product Owner load distributed | §0.4 |
| 8 | 10–15% NSTL burden estimate has no derivation | Estimate derived from enumerated task list with time allocations; flagging mechanism defined for overrun | §0.2 |
| 9 | Configuration B tiebreak default borrows justification from wrong scenario | Configuration B justified specifically for the two-level process-failure case, on its own terms | §0.4, Gate 4 |
| 10 | EM self-confirmation resolved one step removed, presented as full resolution | Limitation acknowledged explicitly; structural improvement documented with residual risk stated | §0.3 |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (`eng/runbooks/notification-system/`, read access for all engineering staff, write access to `gates/` subdirectory granted to gate owners upon Gate 0 resolution), referencing this document by its canonical filename `notification-system-design-v4.md`, with a timestamp.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

**Proxy acknowledgment — restricted path:** If a gate owner cannot access the repository at the time of resolution:

1. The gate owner sends written confirmation of their decision to the NSTL via email, with the Engineering Manager cc'd.
2. The NSTL attaches that email to the repository commit as `gates/attachments/gate-[N]-owner-confirmation-[date].eml` and marks the commit `[proxy-provisional]`.
3. The repository's automated commit notification is sent to the gate owner at their registered email address. The gate owner must reply to that notification within 48 hours, confirming that the attached document accurately represents what they sent.
4. Upon confirmed reply, the NSTL updates the commit status from `[proxy-provisional]` to `[proxy-confirmed]` and attaches the confirmation reply as `gates/attachments/gate-[N]-owner-confirmation-[date]-verified.eml`.
5. If the gate owner does not confirm within 48 hours, the commit remains `[proxy-provisional]`. A `[proxy-provisional]` resolution does not unblock dependent work. The NSTL notifies the Engineering Manager, who contacts the gate owner directly.
6. The NSTL grants the gate owner direct write access within 48 hours of any proxy resolution so future resolutions do not require this path.

**Why this addresses the custody problem:** In the prior version, the NSTL held sole custody of the gate owner's email at the moment of commitment, with no mechanism for the gate owner to verify accuracy. The 48-hour confirmation requirement gives the gate owner an independent check on what was committed in their name. The `[proxy-provisional]` status prevents unconfirmed commits from unblocking work. The gate owner's confirmation reply is a second document in the repository, not an amendment to the first — both are preserved.

**Residual limitation:** The confirmation reply is still routed through the NSTL's commit. A gate owner who never checks their email would not catch an inaccurate commit. This path is a restricted fallback, not a routine mechanism. Direct repository access is the standard.

---

### 0.2 Enforcement: Honest Account

**The core problem:** On a four-person team over six months, any enforcement mechanism that depends on a single person performing their duties without independent verification is a single point of failure. Prior drafts identified EM non-performance as a failure mode and created a Deputy EM backstop. They did not address NSTL non-performance. This section addresses both.

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
- Activating scope reductions when slip thresholds are crossed (§5.3)

**NSTL non-performance — how it surfaces and what happens:**

The gate tracker is readable by all four engineers. The NSTL's Monday update is visible to everyone. The Engineering Manager's independent Monday spot-check creates a second, independent read of the tracker each week. Either of these mechanisms can surface NSTL non-performance:

- **Any team member** who observes that the NSTL has not updated the tracker by end of day Monday, or that a gate status appears inaccurate, may notify the Engineering Manager directly. There is no requirement to go through the NSTL. This is not a bureaucratic override; it is the natural consequence of making the tracker readable.
- **The Engineering Manager's spot-check** independently catches tracker staleness without depending on anyone reporting it.

If the Engineering Manager determines that the NSTL is not performing coordination duties:
1. The Engineering Manager documents the specific missed duty in the tracker.
2. The Engineering Manager reassigns NSTL coordination duties temporarily to a second engineer, designated at project kickoff as the **NSTL backup** (row in §0.3).
3. The Engineering Manager notifies the oversight body (§0.5) within one business day that a coordination duty reassignment has occurred.

**Why this is not a full solution:** The Engineering Manager's spot-check and the team's read access are both necessary but not sufficient. If the Engineering Manager is also non-performing, the NSTL backup path does not activate. The NSTL-to-oversight-body escalation path (§0.2, EM non-performance) remains open for any team member to use. But a scenario in which both the NSTL and EM are non-performing simultaneously would require direct team-member escalation to the oversight body. That path is always open and does not require either the NSTL or EM to initiate it.

**Engineering budget impact — derived estimate:**

The 10–15% NSTL burden figure in the prior draft was asserted without derivation. The following is the enumerated basis:

| Task | Frequency | Estimated time per instance | Monthly total |
|------|-----------|-----------------------------|---------------|
| Monday tracker update and gate status verification | Weekly | 45 minutes | ~3 hours |
| Gate owner pre-deadline check-ins (§0.4) | Per gate, 1 week before deadline | 30 minutes | ~1 hour (averaged) |
| Escalation drafting and documentation | Per escalation event | 1–2 hours | ~1 hour (averaged) |
| Proxy commit processing (§0.1) | Per proxy event (rare) | 1 hour | ~0.5 hours (averaged) |
| Gate 3 two-source check | Once, Month 2 | 3–4 hours | ~0.5 hours (averaged over 6 months) |
| **Monthly total** | | | **~6 hours/month** |

Six hours per month across a six-month project is approximately 36 hours total, or roughly 2–3% of one engineer's time at standard utilization. This is lower than the 10–15% estimate in the prior draft. The prior estimate likely conflated coordination overhead with the broader technical lead role (architecture decisions, code review, unblocking). Those duties are not gate-system coordination and are not counted here.

**Overrun flagging:** If NSTL coordination duties in any given month exceed 10 hours (approximately double the estimate), the NSTL reports this to the Engineering Manager at the next weekly check-in. The Engineering Manager decides whether to redistribute coordination duties or adjust scope. This prevents silent budget erosion.

**If the Engineering Manager does not perform their duties:**

The **Deputy Engineering Manager (Deputy EM)** is a named individual (row in §0.3) with a standing, specific trigger: if the Engineering Manager misses any defined duty — presenting a revised schedule within two business days of a slip, initiating contact within 48 hours of NSTL escalation, deciding a Gate 4 tiebreak within the 48-hour window, or completing the Monday spot-check — the NSTL notifies the Deputy EM in writing. The Deputy EM then:

1. Performs the missed duty within 24 hours of notification.
2. Notifies the oversight body (§0.5) that the substitution occurred, within one business day.

The Deputy EM does not replace the Engineering Manager on an ongoing basis. If the Engineering Manager is temporarily unavailable (illness, travel), they designate the Deputy EM proactively; in that case, the Deputy EM acts with full authority and no oversight body notification is required.

**If both the Engineering Manager and Deputy EM are non-performing:** Any team member may escalate directly to the oversight body (§0.5). The oversight body representative's contact information is stored in plaintext in the tracker at project kickoff, accessible to all team members, before Gate 0 resolves.

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
- The oversight body representative fills in the Engineering Manager row. This eliminates direct self-confirmation.
- The Engineering Manager fills in the NSTL row, the NSTL Backup row, the Deputy EM row, and the oversight body representative row.
- The Deputy EM row requires both the Engineering Manager's signature and the oversight body representative's countersignature. This means the Deputy EM appointment cannot be completed without the oversight body representative's knowledge and assent. An EM who is not performing their duties cannot unilaterally install a Deputy EM who will cover for them.
- The NSTL fills in the Product Owner, Analytics Owner, and Security Lead rows after confirming each person's acceptance of their role.
- No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

**Residual limitation — EM control over the oversight body representative row:** The oversight body representative row is confirmed by the Engineering Manager. This means the EM still has one degree of influence over who confirms them: they name the oversight body representative. This is an improvement over direct self-confirmation but is not a full structural solution. The improvement is that the oversight body representative is a named individual with independent standing and, as defined in §0.5, minimum two-member composition with authority to act. The EM cannot name an individual to the oversight body who does not already hold that role within the organization. The residual risk is that an EM might name a representative who is insufficiently independent. This document cannot eliminate organizational politics; it can only make the structure visible.

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

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of **Week 2**, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |

**Deadline rationale:** Prior draft set this deadline at Week 4, Month 1, concurrent with Gates 2 and 4. Gates 1, 2, and 4 all have the Product Owner as owner. Concurrent deadlines for a single owner create a structural bottleneck regardless of that owner's intent — three decisions at the same time means at least one is likely to be deferred or underprepared. Gate 1 is moved to Week 2 because it is the most independent of the three: it does not depend on the notifications-per-user figure (Gate 2) or the SMS configuration (Gate 4). Moving it earlier distributes the Product Owner's decision load and gives the team more time to act on the outcome.

**Pre-deadline check:** At or before the Gate 1 deadline, the NSTL confirms with the Product Owner: *Is email part of the re-engagement strategy for dormant users?* This question must be answered before the deadline. The NSTL documents the answer in the tracker regardless of Gate 1's resolution status.

**Consequence if missed:**

- **If email is confirmed as a re-engagement mechanism:** Gate 1 is escalated immediately to the Engineering Manager. Email channel work begins provisionally sized for the messaging-primary upper bound (§1.3b).
- **If email is confirmed as not a re-engagement mechanism:** Email channel is deferred to post-launch v1.1. Push, in-app, and SMS launch without email.
-