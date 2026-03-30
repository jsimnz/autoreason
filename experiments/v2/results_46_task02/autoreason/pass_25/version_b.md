# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3

---

## Revision Notes

This revision addresses ten structural problems identified in the prior draft. Each problem is listed with the resolution applied and, where relevant, why a simpler resolution was chosen over a more elaborate one.

| Problem | Resolution |
|---------|------------|
| NSTL coordination load not accounted for in engineering budget | NSTL duties redistributed: scheduling and escalation assigned to Engineering Manager; NSTL retains only technical gate verification. Engineering budget in Section 5 reflects reduced NSTL engineering capacity (10–15%). |
| Conflict-of-interest clause addressed an impossible scenario | Clause removed. Role boundary is real: gate owners are product/analytics/security. Clause was dead text and has been deleted. |
| Gate 0 slip consequence identical to baseline state | Gate 0 now has a distinct escalation consequence: Engineering Manager initiates daily check-ins and presents a revised project schedule to the full team within two business days. |
| Slip analysis treated integration testing duration as fixed without justification | Section 0.5 now addresses whether integration testing can be compressed and identifies the hard constraint that prevents it. |
| Gate 1 consequence relied on unverified retention assumption | Assertion replaced with a conditional: if email is part of the re-engagement strategy, Gate 1 deferral is not safe. A check is now required before accepting the deferral. |
| Sensitivity table was truncated | Table is now complete. All cells in the 45% row are filled. |
| R=3 upper bound treated as conservative when the range itself depends on R | Section 1.3a now bounds the risk: if R falls outside 1–5, the in-app fraction estimate is unreliable and Gate 3 is escalated to a blocking dependency rather than a sizing refinement. |
| Runbook repository not defined | Repository defined in Section 0.1. Access procedure for non-engineering gate owners specified. |
| Gate 4 dual-owner requirement had no tiebreak | Tiebreak procedure added: 48-hour resolution window, then Engineering Manager decides. |
| Section 5 was referenced but absent | Section 5 is now present and complete. |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the **notification-system runbook repository** (internal Git repository at `eng/runbooks/notification-system/`, read access for all engineering staff, write access granted to gate owners upon confirmation in Gate 0), referencing this document as `notification-system-design-v3`, with a timestamp.

**For non-engineering gate owners** (Product Owner, Analytics Owner, Security Lead) who do not have routine write access to the engineering repository: the NSTL grants write access to the `gates/` subdirectory upon Gate 0 resolution. The NSTL documents this access grant in the tracker. If a gate owner cannot access the repository, they notify the NSTL, who posts the acknowledgment on their behalf with the gate owner cc'd on the commit notification. A gate resolved by proxy in this way is marked `[proxy]` in the gate log. This is not a preferred resolution method; it is a fallback to prevent the repository access requirement from becoming a bureaucratic barrier.

Verbal commitments, Slack messages, and meeting notes do not resolve gates.

### 0.2 Enforcement: Honest Account

**Division of responsibilities between NSTL and Engineering Manager:**

The prior draft assigned both technical gate verification and project coordination to the NSTL. With four engineers on a six-month project, those two functions cannot both be carried by the same person without reducing that person's engineering output. This revision separates them.

**The NSTL (one of four backend engineers) is responsible for:**

- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Confirming that gate resolutions meet the written-acknowledgment standard (Section 0.1)
- Escalating to the Engineering Manager if a gate owner is unresponsive within 48 hours of a deadline

**The Engineering Manager is responsible for:**

- Initiating contact with unresponsive gate owners
- Recalculating and presenting the project schedule when a gate slips (within two business days of the slip)
- Making the final call on Gate 4 tiebreaks (Section 0.4, Gate 4)
- Activating scope reductions when slip thresholds are crossed (Section 5.3)

**Engineering budget impact:** The NSTL's coordination duties consume approximately 10–15% of one engineer's time across the project. This is accounted for in Section 5.1. The Engineering Manager's duties are outside the engineering budget.

**The limit of this mechanism:** If the Engineering Manager does not perform their scheduling and escalation duties, the gate system loses its enforcement backbone. This is a real organizational risk. The mitigation is that the Engineering Manager's actions are visible to the full team in the tracker. This is not a perfect mechanism. It is an honest one.

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by (NSTL signature) | Date Confirmed |
|------|------|-------|-------------------------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | Engineering Manager signature | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | | |
| Engineering Manager (escalation target, Gate 4 tiebreak) | [FILL BEFORE ACTIVE] | | N/A — self-confirming | |

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

**Consequence if missed:** Gate 0 being missed means the named individuals table is incomplete. Gates 1–5 are already inert without named owners — this is identical to the baseline state if Gate 0 resolves normally. The additional consequence of a missed Gate 0 is therefore escalatory, not duplicative:

- The Engineering Manager initiates daily check-ins with whoever is blocking the table from being completed.
- The Engineering Manager presents a revised project schedule to the full team within two business days of the missed deadline, showing the impact of delayed gate ownership on Months 2–4 deliverables.
- If Gate 0 is not resolved by the end of Week 4, Month 1, the project is formally flagged to whatever oversight body exists above the Engineering Manager (department head, VP of Engineering, or equivalent). The NSTL documents this escalation in the tracker.

**Why this gate exists:** Gate 0 closes the gap where a gate system has no named subjects. The escalatory consequence distinguishes a missed Gate 0 from the trivially-true observation that gates without owners are inert.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |

**Consequence if missed — conditional on re-engagement strategy check:**

Before accepting the deferral consequence below, the NSTL must verify with the Product Owner: *Is email part of the re-engagement strategy for dormant users?*

- **If yes:** The deferral is not safe. Email is not a low-retention-impact channel for this app. Gate 1 must be escalated immediately to the Engineering Manager, who initiates daily contact. Email channel work begins on a provisional basis sized for the upper bound (Section 1.3b, messaging-primary configuration) to avoid blocking the provider contract and IP warm-up schedule. This provisional sizing is logged as carrying cost uncertainty.

- **If no:** Email channel is deferred to post-launch v1.1. Push, in-app, and SMS launch without email. The deferral is logged as a known gap with the explicit note that this assessment was confirmed by the Product Owner on [date]. The "email least affects retention" claim is not treated as a universal truth; it is a conditional claim that holds only when email is not a re-engagement mechanism for this app's dormant account base.

The re-engagement strategy check must happen at or before the Gate 1 deadline, not after the deadline is missed.

---

#### Gate 2 — App Orientation

| Field | Value |
|-------|-------|
| Decision | Messaging-primary vs. content-discovery |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure; Gate 3 deadline (shifts by the same amount if Gate 2 slips) |

**Consequence if missed:** System is provisioned for the messaging-primary upper bound (25/day). The Product Owner receives a written statement that the over-provisioning cost is a direct consequence of the unresolved decision. The cost differential is calculated in Section 1.3b and presented at escalation. This is not a safe default — it is an expensive one, made visible.

**Why not 20/day as fallback:** 20/day at 30% DAU/MAU produces a sustained average in the ⚠ band, which would itself trigger a re-sizing review. A fallback that generates a downstream review is not a fallback; it moves the uncertainty rather than resolving it. The 25/day upper bound is expensive and stable.

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (shifts by the same duration as any Gate 2 slip) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |

**Consequence if missed:** In-app workers sized for the upper bound of the R-sensitivity range (Section 1.3a), with the caveat described there: the upper bound is only a meaningful conservative estimate if R=3 is within a factor of ~2 of the true value. If Gate 3 is missed *and* there is reason to believe R=3 is substantially wrong, Gate 3 is escalated to a blocking dependency.

---

#### Gate 4 — SMS 2FA Configuration

| Field | Value |
|-------|-------|
| Decision | Configuration A (SMS-only), B (SMS + authenticator app, SMS default), or C (SMS + authenticator app, authenticator default with nudge) |
| Owner Role | Product Owner + Security Lead (both must sign) |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | SMS spend cap; SMS worker sizing; authenticator app integration (if C) |

**Tiebreak procedure:** If both parties are actively engaged but in disagreement at the deadline, the gate is not "missed" in the temporal sense — it is blocked. This is a distinct failure mode. The procedure is:

1. Both parties document their positions in writing in the runbook repository within 24 hours of the deadline.
2. The Engineering Manager has 48 hours from the deadline to review both positions and make a binding decision.
3. If the Engineering Manager does not decide within 48 hours, the system defaults to Configuration A. The default is logged with the explicit note that it resulted from a tiebreak failure, not from a considered decision.

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

**Integration testing duration: is four weeks a hard constraint?**

The four-week duration is not arbitrary. It covers: end-to-end channel testing across APNs, FCM, email, and SMS; load testing at 1×, 3×, and 6× sustained average; failure injection testing for each failure mode in Section 4; and preference system validation. Compressing this to two weeks would require dropping at least one full test category. The least-removable categories are load testing (directly validates the provisioned floor) and failure injection (validates the failure handling in Section 4). The most compressible category is preference system validation, which could be reduced from one week to three days without material risk, saving approximately four days.

**Conclusion on compression:** Integration testing can be compressed by approximately four days, not two weeks. Treating it as a fixed four-week duration is appropriate for planning. The four-day buffer is held in reserve for minor schedule recovery only.

**Two-week slip scenario:**

| Event | Original Date | Slipped Date |
|-------|--------------|--------------|
| Gate 2 resolves | End Week 4, Month 1 | End Week 2, Month 2 |
| Gate 3 resolves | End Week 2, Month 2 | End Week 4, Month 2 |
| In-app sizing finalized | End Week 2, Month 2 | End Week 4, Month 2 |
| Integration testing starts | Beginning Month 4 | Beginning Month 4 + 2 weeks |
| Integration testing ends (4 weeks, −4 days compression available) | End Month 4 | ~Mid-Month 5 + 3 days |
| Hardening, load testing, launch prep window | ~4.5 weeks | ~2 weeks |

**Conclusion:** A two-week slip on Gate 2 reduces the hardening window by approximately 55%. This is recoverable only if the scope reductions in Section 5.3 are activated simultaneously with the slip — not after integration testing reveals problems. The Engineering Manager activates scope reductions on the day Gate 2 misses its deadline.

**Four-week slip scenario:** Integration testing ends in the last week of Month 5. Hardening window is approximately three to four days. This is not recoverable without scope reduction. Section 5.3 scope reductions must activate immediately on the day the missed deadline is confirmed. Even with full scope reduction, launch should be treated as at risk and the Engineering Manager must notify stakeholders on the day of the missed Gate 2 deadline.

---

## Executive Summary

This design handles approximately 45–75M push and in-app notifications per day, plus additive email and SMS volume, for a 10M MAU social application. The provisioned floor is **5,200/sec**.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor: 5,200/sec | Peak demand at working assumption is 3,126/sec. Headroom = (5,200 − 3,126) / 5,200 = 40%. Derivation in Section 1.4. |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted. |
| In-app fraction: 6.5% working assumption, sized at upper bound (9%) pending Gate 3 | Derived using activity-correlation model with R=3 (unvalidated). Sensitivity range 5–9% is itself R-dependent; if R=3 is wrong by more than a factor of ~2, the range is wrong. See Section 1.3a. |
| APNs and FCM as separate worker tiers | Distinct rate limits, token invalidation behaviors, failure modes. ~2 days engineering cost. Aggregate modeling masks platform-specific bottlenecks. |
| Email volume additive to push/in-app | Different mechanism, different population base (MAU not DAU), different timescale. |
| SMS spend cap calculated for all three configurations | Section 1.