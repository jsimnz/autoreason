# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Synthesis Document

---

## Revision Notes

This document synthesizes two prior drafts. The primary structural improvements over both are:

| Problem Addressed | Resolution |
|-------------------|------------|
| Gate enforcement was illusory (tracker-as-mechanism) | Enforcement is owned by a named human role (NSTL) with explicit conflict-of-interest handling |
| Owner assignment had no gate of its own | Gate 0 added; all other gates are inert until it resolves |
| R=3 in Bayes derivation was presented as validated | R=3 is now an unvalidated working assumption; sizing uses the upper bound of the sensitivity range pending Gate 3 |
| Provisioned floor arithmetic used two inconsistent headroom framings | Single formula used throughout; both figures reconciled in one table |
| Flag thresholds were defined relative to the provisioned floor (circular) | Thresholds now defined in terms of re-sizing lead time, independently of the floor |
| Gate 2 fallback (20/day) itself triggered a downstream review | Fallback replaced: provision for messaging-primary upper bound (25/day); present cost to product owner as a direct consequence of the unresolved decision |
| Gate slip had no recovery analysis | Two-week and four-week slip scenarios analyzed against the six-month engineering budget |
| Named individuals were not named | Named individuals table is now a prerequisite; gate system is explicitly inert until filled |
| Section 1.3b was absent | Email volume, SMS volume, and spend caps for all three configurations now complete |
| In-app worker sizing proceeded without establishing whether it was a binding constraint | Section 1.3a now establishes binding-constraint status before deriving the correction |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the runbook repository, referencing this document by version number, with a timestamp. Verbal commitments, Slack messages, and meeting notes do not resolve gates.

### 0.2 Enforcement: Honest Account

The actual enforcement mechanism is a named human role: the **Notification System Technical Lead (NSTL)**. This is one of the four backend engineers. Project trackers record state; they do not enforce it. The NSTL enforces it. The tracker makes the NSTL's actions auditable.

**The NSTL is responsible for:**

- Verifying gate status each Monday morning and updating the tracker to reflect actual state
- Rejecting verbal or informal resolutions and requiring written runbook entries
- Escalating to the engineering manager if a gate owner is unresponsive within 48 hours of a deadline
- Recalculating the project schedule when a gate slips and presenting the updated schedule to the full team within two business days of the slip

**Conflict-of-interest handling:** Gate owners are product, analytics, or security roles — not engineering. If the NSTL is somehow assigned ownership of a gate item, a second engineer assumes enforcement responsibility for that gate only.

**The limit of this mechanism:** If the NSTL is pressured to accept an informal resolution, the system can fail. The mitigation is that the NSTL's enforcement actions are visible to the full team in the tracker, creating social accountability. This is not a perfect mechanism. It is an honest one.

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can be assigned to an owner.

| Role | Name | Email | Confirmed by (NSTL signature) | Date Confirmed |
|------|------|-------|-------------------------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | | |
| Engineering Manager (escalation target) | [FILL BEFORE ACTIVE] | | | |

**Instructions:** The engineering manager fills in the NSTL row. The NSTL fills in all other rows after confirming each person's acceptance of their role. No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

---

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (Section 0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | End of Week 2, Month 1 |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |
| Consequence if Missed | All gates 1–4 are treated as unresolved as of their own deadlines. Schedule is recalculated immediately. See Section 0.5 for slip analysis. |

**Why this gate exists:** A gate system with no named subjects is inert. Gate 0 closes that gap. It is owned by the engineering manager rather than the NSTL because the engineering manager has organizational authority to assign roles; the NSTL does not.

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
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure; Gate 3 deadline (shifts by the same amount if Gate 2 slips) |
| Consequence if Missed | System is provisioned for the messaging-primary upper bound (25/day). The product owner receives a written statement that the over-provisioning cost is a direct consequence of the unresolved decision. The cost differential is calculated in Section 1.3b and presented at escalation. This is not a safe default — it is an expensive one, made visible. The prior fallback (20/day) is rejected because 20/day at 30% DAU/MAU falls in the ⚠ band and would itself trigger a re-sizing review; a fallback that generates a downstream review is not a fallback. |

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (two weeks after Gate 2 deadline; shifts by the same duration if Gate 2 slips — see Section 0.5) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |
| Consequence if Missed | In-app workers sized for the upper bound of the R-sensitivity range (Section 1.3a). This produces at most 2× over-provisioning of the in-app tier. Given that in-app workers are not the most expensive tier, this is an acceptable cost of the unresolved decision. |

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

### 0.5 Slip Analysis: Gate 2 / Gate 3 Chain

The Gate 2 → Gate 3 chain gates in-app worker sizing, which is on the critical path for integration testing. Integration testing is scheduled to begin in Month 4.

**Two-week slip scenario:**

| Event | Original Date | Slipped Date |
|-------|--------------|--------------|
| Gate 2 resolves | End Week 4, Month 1 | End Week 2, Month 2 |
| Gate 3 resolves | End Week 2, Month 2 | End Week 4, Month 2 |
| In-app sizing finalized | End Week 2, Month 2 | End Week 4, Month 2 |
| Integration testing starts | Beginning Month 4 | Beginning Month 4 + 2 weeks |
| Integration testing ends (4-week duration) | End Month 4 | Mid-Month 5 |
| Hardening, load testing, launch prep window | ~4.5 weeks | ~2.5 weeks |

**Conclusion:** A two-week slip on Gate 2 reduces the hardening window by 44%. This is recoverable only if the scope reductions in Section 5.3 are activated simultaneously with the slip — not after integration testing reveals problems.

**Four-week slip scenario:** Integration testing ends in the last week of Month 5. Hardening window is approximately 0.5 weeks. This is not recoverable without scope reduction. Section 5.3 scope reductions must activate immediately on the day the missed deadline is confirmed.

**The NSTL is responsible for presenting this slip analysis to the engineering manager on the day Gate 2 misses its deadline, not retroactively.**

---

## Executive Summary

This design handles approximately 45–60M push and in-app notifications per day, plus additive email and SMS volume, for a 10M MAU social application. The provisioned floor is **5,200/sec**.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor: 5,200/sec | Peak demand at working assumption is 3,126/sec. Headroom = (5,200 − 3,126) / 5,200 = 40%. Derivation in Section 1.4. |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted |
| In-app fraction: 6.5% working assumption, sized at upper bound (9%) pending Gate 3 | Derived using activity-correlation model with R=3 (unvalidated). Sensitivity range 5–9%. Provisioned for upper bound until Gate 3 resolves. |
| APNs and FCM as separate worker tiers | Distinct rate limits, token invalidation behaviors, failure modes. ~2 days engineering cost. Aggregate modeling masks platform-specific bottlenecks. |
| Email volume additive to push/in-app | Different mechanism, different population base (MAU not DAU), different timescale |
| SMS spend cap calculated for all three configurations | Section 1.3b |
| Gate 0 before all other gates | Owner assignment is the most critical dependency and now has its own gate |
| Gate 2 fallback provisions for 25/day, not 20/day | 20/day fallback itself triggers a re-sizing review; an expensive-but-stable fallback is preferable to a nominally-safe one that generates downstream uncertainty |
| Two-week Gate 2 slip analyzed explicitly | Reduces hardening window by 44%. Recovery requires immediate scope reduction activation. |
| Four-engineer, six-month constraint stress-tested | Section 5 contains explicit engineering budget; three components deferred to post-launch |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude Mobile Benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z Consumer Benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. The provisioned floor remains adequate through the 40% DAU/MAU, 15/day scenario without re-sizing. Scenarios marked ⚠ or ✗ in Section 1.2 are planning triggers with defined response actions, not emergencies.

---

### 1.2 Notifications Per Active User Per Day

**Basis:** The Braze 2023 Mobile Marketing Report reports aggregate median notification volumes across app categories. The aggregate figure for social apps is approximately 15–20 notifications/day for active users. This is an aggregate across app subtypes — it does not segment messaging-heavy from content-discovery within the social category.

The 15/day working figure is selected as a conservative estimate for a content-discovery orientation, on the reasoning that content-discovery apps generate fewer per-user events than messaging-heavy apps. If Gate 2 confirms messaging-primary orientation, revise to 20–25/day before finalizing worker sizing.

**⚠ Gate 2 dependency:** This figure cannot be confirmed without Gate 2 resolution.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average |
|------------------------------|------------------|------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

**Flag thresholds — defined independently of provisioned floor:**

Thresholds are defined in terms of re-sizing lead time. Re-sizing lead time (infrastructure procurement and worker deployment) is approximately 3 weeks post-launch.

- **✓:** Peak demand below 3,500/sec. Provisioned floor (5,200/sec) provides more than 32% headroom. No action required.
- **⚠:** Peak demand between 3,500/sec and 5,200/sec. Headroom is shrinking. Re-sizing review must be initiated immediately. If this scenario is identified post-launch, the system may be under-provisioned for up to 3 weeks during the re-sizing window. This consequence should be stated to stakeholders, not obscured.
- **✗:** Peak demand exceeds 5,200/sec. Provisioned floor is breached. Re-sizing is urgent. Post-launch discovery of this scenario means the system is operating over capacity. Immediate escalation and emergency re-sizing required.
- **⚠→:** Cell within 5% of the next flag boundary. Treat as the higher flag category for planning purposes.

**Combined sensitivity — sustained average in req/sec, with flags:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 ✓ | ~347 ✓ | ~463 ✓ | ~579 ⚠→ |
| 30% | ~347 ✓ | **~521 ✓** | ~694 ⚠ | ~868 ⚠ |
| 40% | ~463 ✓ | ~694 ⚠ | ~926 ✗ | ~1,157 ✗ |
| 45% | ~521 ✓ |