# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Synthesis

---

## Revision Notes

This document synthesizes two prior drafts. The table below records which version contributed each structural improvement and why the resolution was chosen.

| Problem | Resolution | Source |
|---------|------------|--------|
| Gate enforcement was illusory (tracker-as-mechanism) | Enforcement split between NSTL (technical verification) and Engineering Manager (scheduling, escalation, tiebreaks). Both roles are visible in the tracker. | Y |
| NSTL coordination load not accounted for in engineering budget | NSTL retains only technical gate verification (~10–15% of one engineer's time). Scheduling and escalation assigned to Engineering Manager. Section 5.1 reflects this. | Y |
| Owner assignment had no gate of its own | Gate 0 added; all other gates are inert until it resolves. | X |
| Gate 0 slip consequence was identical to baseline state | Gate 0 slip now triggers distinct escalatory consequence: daily check-ins and revised schedule within two business days. | Y |
| Conflict-of-interest clause addressed an impossible scenario | Clause removed. Gate owners are product/analytics/security by design; the scenario cannot arise. | Y |
| R=3 in Bayes derivation presented as validated | R=3 is an unvalidated working assumption. If R=3 is wrong by more than a factor of ~2, the sensitivity range itself is unreliable and Gate 3 becomes a blocking dependency. | Y |
| Provisioned floor arithmetic used two inconsistent headroom framings | Single formula used throughout; both figures reconciled in one table. | X |
| Flag thresholds defined relative to provisioned floor (circular) | Thresholds defined in terms of re-sizing lead time, independently of the floor. | X |
| Gate 2 fallback (20/day) itself triggered a downstream review | Fallback replaced: provision for messaging-primary upper bound (25/day); cost presented to Product Owner as direct consequence of unresolved decision. | X |
| Gate 1 consequence relied on unverified retention assumption | Consequence now conditional on re-engagement strategy check before accepting deferral. | Y |
| Gate 4 dual-owner requirement had no tiebreak | Tiebreak procedure added: 48-hour window, then Engineering Manager decides. Default on tiebreak failure is Configuration A, logged as such. | Y |
| Gate slip had no recovery analysis | Two-week and four-week slip scenarios analyzed. Integration testing compression ceiling (~4 days) identified and justified. | Y |
| Runbook repository not defined | Repository defined in Section 0.1. Access procedure for non-engineering gate owners specified, including proxy fallback. | Y |
| Named individuals not named | Named individuals table is a prerequisite; gate system explicitly inert until filled. | X |
| Sensitivity table truncated | Table complete; all cells in the 45% row filled. | Y |
| Section 5 absent | Section 5 present and complete. | Y |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (internal Git repository at `eng/runbooks/notification-system/`, read access for all engineering staff, write access granted to gate owners upon Gate 0 resolution), referencing this document as `notification-system-design-synthesis`, with a timestamp.

**For non-engineering gate owners** (Product Owner, Analytics Owner, Security Lead) who do not have routine write access: the NSTL grants write access to the `gates/` subdirectory upon Gate 0 resolution and documents the access grant in the tracker. If a gate owner cannot access the repository, they notify the NSTL, who posts the acknowledgment on their behalf with the gate owner cc'd on the commit notification. A gate resolved by proxy is marked `[proxy]` in the gate log. This is a fallback, not a preferred path; it exists to prevent repository access from becoming a bureaucratic barrier.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

---

### 0.2 Enforcement: Honest Account

**Division of responsibilities:**

The NSTL and Engineering Manager hold distinct, non-overlapping enforcement functions. Combining both functions in one engineer on a four-person team would reduce that engineer's technical output to an unacceptable degree.

**The NSTL (one of four backend engineers) is responsible for:**
- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Confirming that gate resolutions meet the written-acknowledgment standard (Section 0.1)
- Escalating to the Engineering Manager if a gate owner is unresponsive within 48 hours of a deadline

**The Engineering Manager is responsible for:**
- Initiating contact with unresponsive gate owners after NSTL escalation
- Recalculating and presenting the project schedule when a gate slips, within two business days of the slip
- Making the final call on Gate 4 tiebreaks (Section 0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (Section 5.3)

**Engineering budget impact:** NSTL coordination duties consume approximately 10–15% of one engineer's time across the project. This is accounted for in Section 5.1. The Engineering Manager's duties are outside the engineering budget.

**The limit of this mechanism:** If the Engineering Manager does not perform their scheduling and escalation duties, the gate system loses its enforcement backbone. The mitigation is that the Engineering Manager's actions are visible to the full team in the tracker, creating social accountability. This is not a perfect mechanism. It is an honest one.

---

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by | Date Confirmed |
|------|------|-------|--------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | NSTL signature | |
| Engineering Manager (escalation target; Gate 4 tiebreak) | [FILL BEFORE ACTIVE] | | N/A — self-confirming | |

**Instructions:** The Engineering Manager fills in the NSTL row and their own row. The NSTL fills in all other rows after confirming each person's acceptance of their role. No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

---

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (Section 0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | End of Week 2, Month 1 |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |

**Consequence if missed:** Gates 1–5 are already inert without named owners; that is the baseline state. A missed Gate 0 therefore requires a distinct escalatory response, not merely a restatement of the baseline:

- The Engineering Manager initiates daily check-ins with whoever is blocking the table from being completed.
- The Engineering Manager presents a revised project schedule to the full team within two business days of the missed deadline, showing the impact of delayed gate ownership on Months 2–4 deliverables.
- If Gate 0 is not resolved by end of Week 4, Month 1, the project is formally flagged to the oversight body above the Engineering Manager (department head, VP of Engineering, or equivalent). The NSTL documents this escalation in the tracker.

**Why this gate exists:** A gate system with no named subjects is inert. Gate 0 closes that gap. It is owned by the Engineering Manager rather than the NSTL because the Engineering Manager has organizational authority to assign roles; the NSTL does not.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |

**Consequence if missed — conditional on re-engagement strategy check:**

Before accepting the deferral consequence below, the NSTL must verify with the Product Owner: *Is email part of the re-engagement strategy for dormant users?* This check must occur at or before the Gate 1 deadline, not after it is missed.

- **If yes:** The deferral is not safe. Gate 1 is escalated immediately to the Engineering Manager, who initiates daily contact. Email channel work begins on a provisional basis sized for the upper bound (Section 1.3b, messaging-primary configuration) to avoid blocking the provider contract and IP warm-up schedule. This provisional sizing is logged as carrying cost uncertainty.

- **If no:** Email channel is deferred to post-launch v1.1. Push, in-app, and SMS launch without email. The deferral is logged as a known gap, with the explicit note that the Product Owner confirmed email is not a re-engagement mechanism for this app on [date]. The claim that email is low-retention-impact is treated as a conditional claim specific to this app's confirmed strategy, not a universal truth.

---

#### Gate 2 — App Orientation

| Field | Value |
|-------|-------|
| Decision | Messaging-primary vs. content-discovery |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure; Gate 3 deadline (shifts by the same duration if Gate 2 slips) |

**Consequence if missed:** System is provisioned for the messaging-primary upper bound (25/day). The Product Owner receives a written statement that the over-provisioning cost is a direct consequence of the unresolved decision. The cost differential is calculated in Section 1.3b and presented at escalation.

**Why not 20/day as fallback:** 20/day at 30% DAU/MAU produces a sustained average in the ⚠ band, which itself triggers a re-sizing review. A fallback that generates a downstream review moves the uncertainty rather than resolving it. The 25/day upper bound is expensive and stable. This is not a safe default — it is an expensive one, made visible.

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (shifts by the same duration as any Gate 2 slip) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |

**Consequence if missed:** In-app workers are sized for the upper bound of the R-sensitivity range (Section 1.3a), producing at most 2× over-provisioning of the in-app tier. However, this upper bound is only a meaningful conservative estimate if R=3 is within a factor of ~2 of the true value. If Gate 3 is missed *and* there is reason to believe R=3 is substantially wrong, Gate 3 is escalated to a blocking dependency rather than a sizing refinement. The NSTL makes this determination and documents it.

---

#### Gate 4 — SMS 2FA Configuration

| Field | Value |
|-------|-------|
| Decision | Configuration A (SMS-only), B (SMS + authenticator app, SMS default), or C (SMS + authenticator app, authenticator default with nudge) |
| Owner Role | Product Owner + Security Lead (both must sign) |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | SMS spend cap; SMS worker sizing; authenticator app integration (if C) |

**Tiebreak procedure:** If both parties are actively engaged but in disagreement at the deadline, the gate is blocked, not merely missed. This is a distinct failure mode requiring a distinct procedure:

1. Both parties document their positions in writing in the runbook repository within 24 hours of the deadline.
2. The Engineering Manager has 48 hours from the deadline to review both positions and make a binding decision.
3. If the Engineering Manager does not decide within 48 hours, the system defaults to Configuration A. This default is logged with the explicit note that it resulted from a tiebreak failure, not a considered decision.

**Consequence if missed (no active engagement):** Default to Configuration A. SMS-only. Higher spend, simpler implementation. Cost documented and presented to both owners at escalation.

---

#### Gate 5 — SMS 2FA Nudge Timeline (Configuration C only)

| Field | Value |
|-------|-------|
| Decision | Timeline and messaging for nudging users from SMS to authenticator app |
| Owner Role | Security Lead |
| Hard Deadline | End of Week 2, Month 2 |
| Dependent Work | Configuration C launch-period spend cap; nudge implementation |
| Condition | Required only if Gate 4 resolves as Configuration C |
| Consequence if Missed | Treat as Configuration B for spend cap purposes. Log as known underestimate. |

---

### 0.5 Slip Analysis: Gate 2 / Gate 3 Chain

The Gate 2 → Gate 3 chain gates in-app worker sizing, which is on the critical path for integration testing. Integration testing is scheduled to begin in Month 4.

**Integration testing duration: is four weeks compressible?**

The four-week duration covers: end-to-end channel testing across APNs, FCM, email, and SMS; load testing at 1×, 3×, and 6× sustained average; failure injection testing for each failure mode in Section 4; and preference system validation. These categories are not uniformly compressible:

- **Load testing** validates the provisioned floor directly. Not removable.
- **Failure injection testing** validates Section 4 failure handling. Not removable.
- **Preference system validation** can be reduced from one week to three days without material risk, saving approximately four days.
- **End-to-end channel testing** can be partially parallelized, saving approximately two to three days with additional coordination overhead.

**Compression ceiling: approximately four days.** Integration testing cannot be compressed by two weeks without dropping load testing or failure injection, which would invalidate the provisioned floor and failure handling assumptions. Four weeks is the correct planning figure. The four-day compression buffer is held in reserve for minor schedule recovery only.

**Two-week slip scenario:**

| Event | Original Date | Slipped Date |
|-------|--------------|--------------|
| Gate 2 resolves | End Week 4, Month 1 | End Week 2, Month 2 |
| Gate 3 resolves | End Week 2, Month 2 | End Week 4, Month 2 |
| In-app sizing finalized | End Week 2, Month 2 | End Week 4, Month 2 |
| Integration testing starts | Beginning Month 4 | Beginning Month 4 + 2 weeks |
| Integration testing ends (4 weeks, −4 days compression available) | End Month 4 | ~Mid-Month 5 + 3 days |
| Hardening, load testing, launch prep window | ~4.5 weeks | ~2 weeks |

**Conclusion:** A two-week slip on Gate 2 reduces the hardening window by approximately 55%. This is recoverable only if the scope reductions in Section 5.3 are activated simultaneously with the slip. The Engineering Manager activates scope reductions on the day Gate 2 misses its deadline, not after integration testing reveals problems.

**Four-week slip scenario:** Integration testing ends in the last week of Month 5. Hardening window is approximately three to four days. This is not recoverable without scope reduction. Even with full scope reduction, launch should be treated as at risk. The Engineering Manager notifies stakeholders on the day Gate 2 misses its deadline.

---

## Executive Summary

This design handles approximately 45–75M push and in-app notifications per day, plus additive email and SMS volume, for a 10M MAU social application. The provisioned floor is **5,200/sec**.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor: 5,200/sec | Peak demand at working assumption is 3,126/sec. Headroom = (5,200 − 3,126) / 5,200 = 40%. Derivation in Section 1.4. |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted. |
| In-app fraction: 6.5% working assumption, sized at upper bound (9%)