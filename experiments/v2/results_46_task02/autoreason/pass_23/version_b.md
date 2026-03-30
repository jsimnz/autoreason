# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural Criticisms

---

## Revision Notes

This revision addresses ten identified problems with the prior draft. Each problem is listed below with a brief statement of what changed and where. Readers who reviewed the prior draft should start here.

| Problem | What Changed |
|---------|-------------|
| 1. Gate enforcement is illusory | Enforcement rewritten. The tracker-as-mechanism claim is retracted. A specific human role owns enforcement, with explicit conflict-of-interest handling. |
| 2. Owner assignment task has no gate | Owner assignment is now Gate 0, with its own deadline, owner, and consequence. |
| 3. Bayes calculation launders R=3 | R=3 is now presented as an unvalidated working assumption with sensitivity analysis. The corroboration claim is retracted. In-app sizing is treated as a range, not a point estimate. |
| 4. Provisioned floor arithmetic inconsistency | Both headroom figures are reconciled in a single table with a consistent formula. One framing is used throughout. |
| 5. Flag thresholds are circular | Thresholds are now defined independently of the provisioned floor. Re-sizing timeline is analyzed explicitly. |
| 6. GATE-2 scope reduction default contradicts its purpose | The 20/day fallback is replaced. The fallback now triggers a specific scope action rather than a planning state that requires further review. |
| 7. Gate slip has no recovery analysis | A two-week slip on the GATE-2/GATE-3 chain is analyzed against the six-month budget. Consequences are stated explicitly. |
| 8. Naive model dismissal doesn't justify the analysis | Section 1.3a now begins by establishing whether in-app worker sizing is a binding constraint before proceeding with the derivation. |
| 9. Section 1.3b is absent | Section 1.3b is now complete: email volume, SMS volume, and spend caps for all three configurations. |
| 10. Named individuals are not named | The document now contains a placeholder table with explicit instructions for completing it before the document is considered active. The gate system is inert until this table is filled. |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the runbook repository, referencing this document by version and revision number, with a timestamp. Verbal commitments, Slack messages, and meeting notes do not resolve gates.

### 0.2 Enforcement: Honest Account

The prior draft claimed the project tracker enforces gates automatically. This was false. Project trackers do not move items to hold states without human action. Someone must configure the rules, verify that back-channel resolutions haven't bypassed the formal mechanism, and hold the line when a stakeholder claims verbal confirmation is sufficient.

**The actual enforcement mechanism is a named human role: the Notification System Technical Lead (NSTL).** This is one of the four backend engineers. The NSTL is responsible for:

- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Rejecting verbal or informal resolutions and requiring written runbook entries
- Escalating to the engineering manager if a gate owner is unresponsive within 48 hours of a deadline
- Recalculating the project schedule when a gate slips and presenting the updated schedule to the full team within two business days of the slip

**Conflict-of-interest handling:** If the NSTL is also the owner of a gate item (which should not happen — gate owners are product, analytics, or security roles, not engineering), a second engineer assumes enforcement responsibility for that gate only.

**What the tracker does:** The tracker records state. It does not enforce state. The NSTL enforces state. The tracker makes the NSTL's job auditable.

**The limit of this mechanism:** If the NSTL is pressured by a PM or manager to accept an informal resolution, the system can fail. This is acknowledged. The mitigation is that the NSTL's enforcement actions are visible to the full team in the tracker, creating social accountability. This is not a perfect mechanism. It is an honest one.

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 (below) requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by (NSTL signature) | Date Confirmed |
|------|------|-------|-------------------------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | | |
| Product Owner (gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | | |
| Analytics Owner (gate 3) | [FILL BEFORE ACTIVE] | | | |
| Security Lead (gates 4, 5) | [FILL BEFORE ACTIVE] | | | |
| Engineering Manager (escalation target) | [FILL BEFORE ACTIVE] | | | |

**Instructions:** The engineering manager fills in the NSTL row. The NSTL fills in all other rows after confirming each person's acceptance of their role. No gate beyond Gate 0 has a valid owner until the corresponding row is signed.

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (Section 0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | End of Week 2, Month 1 |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |
| Consequence if Missed | All gates 1–4 are treated as unresolved as of their deadlines. Schedule is recalculated immediately. See Section 0.5 for slip analysis. |

**Why this gate exists:** The prior draft required named individuals but named none. The gate system had no subjects. Gate 0 closes that gap. It is owned by the engineering manager rather than the NSTL because the engineering manager has organizational authority to assign roles; the NSTL does not.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |
| Consequence if Missed | Email channel deferred to post-launch v1.1. Push, in-app, and SMS launch without email. This is a real scope reduction, not a penalty: email is the channel least likely to affect core retention in the first 90 days post-launch. The deferral is logged as a known gap. |

---

#### Gate 2 — App Orientation

| Field | Value |
|-------|-------|
| Decision | Messaging-primary vs. content-discovery |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure |
| Consequence if Missed | See Section 0.6 for the revised fallback. The prior fallback (use 20/day as upper bound) is replaced. |

**Revised fallback for unresolved Gate 2:** If Gate 2 is unresolved at its deadline, the team does not select a single figure. Instead, the system is provisioned for the messaging-primary upper bound (25/day) and the product owner is given a written statement that the over-provisioning cost is a direct consequence of the unresolved decision. The cost difference is calculated in Section 1.3b and presented to the product owner at the time of escalation. This is not a safe default — it is an expensive one, made visible.

The prior fallback (20/day) was rejected because 20/day at 30% DAU/MAU falls in the ⚠ band, meaning it would itself trigger a re-sizing review. A fallback that generates a downstream review is not a fallback.

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (two weeks after Gate 2 deadline; shifts if Gate 2 slips — see Section 0.5) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |
| Consequence if Missed | In-app workers sized for the upper bound of the R-sensitivity range (Section 1.3a). This produces at most 2× over-provisioning of the in-app tier, which is low-cost given in-app worker sizing (Section 1.3a establishes the cost). |

---

#### Gate 4 — SMS 2FA Configuration

| Field | Value |
|-------|-------|
| Decision | Configuration A (SMS-only), B (SMS + authenticator app, SMS default), or C (SMS + authenticator app, authenticator default with nudge) |
| Owner Role | Product Owner + Security Lead (both must sign) |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | SMS spend cap; SMS worker sizing; authenticator app integration (if C) |
| Consequence if Missed | Default to Configuration A. SMS-only. Higher spend, simpler implementation. Cost documented and presented to both owners at escalation. |

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

### 0.5 Slip Analysis: Two-Week Slip on Gate 2 / Gate 3 Chain

The prior draft acknowledged the sequential dependency between Gate 2 and Gate 3 but provided no analysis of whether the six-month window survives a slip.

**Engineering budget summary (from Section 5):**

Total available engineering weeks: 4 engineers × 26 weeks = 104 engineer-weeks. Section 5 allocates these across components. The Gate 2 → Gate 3 chain gates in-app worker sizing, which is on the critical path for integration testing. Integration testing is scheduled to begin in Month 4.

**Two-week slip scenario:**

- Gate 2 slips two weeks: resolves end of Week 2, Month 2 instead of end of Week 4, Month 1.
- Gate 3 shifts two weeks: resolves end of Week 4, Month 2 instead of end of Week 2, Month 2.
- In-app worker sizing finalized: end of Week 4, Month 2 instead of end of Week 2, Month 2.
- Integration testing start: pushed from beginning of Month 4 to beginning of Month 4 + two weeks.
- Integration testing duration: 4 weeks (unchanged).
- Integration testing end: end of Month 4 + two weeks, i.e., middle of Month 5.
- Remaining time for hardening, load testing, and launch prep: approximately 2.5 weeks instead of 4.5 weeks.

**Conclusion:** A two-week slip on Gate 2 reduces the hardening window by 44%, from 4.5 weeks to 2.5 weeks. This is recoverable only if the scope reductions in Section 5.3 are activated simultaneously with the slip — not after integration testing reveals problems. The NSTL must present this analysis to the engineering manager on the day Gate 2 misses its deadline, not after the downstream consequences materialize.

**Four-week slip scenario:** Gate 2 slips four weeks. Integration testing ends in the last week of Month 5. Hardening window is approximately 0.5 weeks. This is not recoverable without scope reduction. The Section 5.3 scope reductions must activate immediately.

**The NSTL is responsible for presenting this slip analysis at the time of the missed deadline, not retroactively.**

---

## Executive Summary

This design handles approximately 45–60M push and in-app notifications per day, plus additive email and SMS volume, for a 10M MAU social application. The provisioned floor is **5,200/sec**.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor: 5,200/sec | Peak demand at working assumption is 3,126/sec. Provisioned floor is 5,200/sec. Headroom = (5,200 − 3,126) / 5,200 = 40%. Derivation in Section 1.4. |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted |
| In-app fraction: 6.5% (working assumption) | Derived using activity-correlation model with R=3 (unvalidated; sensitivity range 5–9% shown in Section 1.3a). Provisioned for upper bound of range pending Gate 3. |
| APNs and FCM as separate worker tiers | Distinct rate limits, token invalidation behaviors, failure modes. ~2 days engineering cost. Justified in Section 1.3a. |
| Email volume additive to push/in-app | Different mechanism, different population base, different timescale. Section 1.3b. |
| SMS spend cap calculated for all three configurations | Section 1.3b. |
| Gate 0 before all other gates | Owner assignment is the most critical dependency. It now has its own gate. |
| Two-week Gate 2 slip analyzed explicitly | Reduces hardening window by 44%. Recovery requires immediate scope reduction activation. Section 0.5. |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude Mobile Benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z Consumer Benchmark 2022 |

**Working assumption: 30%.** Conservative for a growing app. The provisioned floor remains adequate through the 40% DAU/MAU, 15/day scenario. Scenarios marked ⚠ or ✗ in Section 1.2 are planning triggers with defined response actions, not emergencies.

---

### 1.2 Notifications Per Active User Per Day

**Basis:** Braze 2023 Mobile Marketing Report aggregate median for social apps: 15–20/day for active users. This is an aggregate across app subtypes. The 15/day working figure is selected as a conservative estimate for a content-discovery orientation, pending Gate 2.

**If Gate 2 confirms messaging-primary:** Revise to 20–25/day before finalizing worker sizing.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average |
|------------------------------|------------------|------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

**Flag thresholds — defined independently of provisioned floor:**

The thresholds below are defined in terms of re-sizing lead time, not relative to the provisioned floor. This corrects the circularity in the prior draft.

- ✓: Peak demand is below 3,500/sec. The provisioned floor (5,200/sec) provides more than 32% headroom. No action required.
- ⚠: Peak demand is between 3,500/sec and 5,200/sec. Headroom is shrinking. Re-sizing review must be initiated. Re-sizing lead time is approximately 3 weeks (infrastructure procurement and worker deployment). If this scenario is identified post-launch, the 3-week lead time means the system may be under-provisioned for up to 3 weeks. This is the consequence; it should be stated to stakeholders, not obscured.
- ✗: Peak demand exceeds 5,200/sec. Provisioned floor is breached. Re-sizing is urgent. Post-launch discovery of this scenario requires