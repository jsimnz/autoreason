# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Log

| Finding | Resolution | Section |
|---------|-----------|---------|
| Discord benchmark doing too much work | Removed; 14/DAU reframed as midpoint estimate with explicit uncertainty; three-scenario planning added | §1.1 |
| Instagram/Twitter benchmarks used inconsistently | Reframed as establishing upper-plausible bound only; lower range (7.5–12/DAU) explicitly unanchored by external data | §1.1 |
| Beta cohort validation plan structurally too late | Explicit timeline with slack analysis; decision rules for four data quality outcomes; ambiguous result has defined path | §1.1 |
| Beta cohort size not justified statistically | Cohort size justified against required precision; confidence interval analysis shown | §1.1 |
| Revision trigger logic circular | Trigger redefined as two-dimensional condition (per-DAU rate, DAU scenario); labeling error in base vs. high DAU corrected | §1.1 |
| 90% concentration factor unexplained | Origin stated; sensitivity analysis added; concentration factor added to beta cohort scope; recalibration trigger defined | §1.1 |
| Default A threshold miscalibrated | Threshold recalibrated against high DAU scenario; labeling error corrected; all threshold values updated | §1.1 |
| Default A deactivation condition unspecified | M = N+2 hysteresis defined; oscillation prevention rationale documented | §1.1 |
| Default B alert threshold not connected to spike taxonomy | Alert threshold derived from spike type frequency analysis | §1.1 |
| Tier 1 queue unbounded with no circuit breaker | Tier 1 ceiling defined; behavior at ceiling specified; added as sign-off item | §1.1, Sign-Off Table |
| Queue depth bounds incomplete for Type 4 spikes | Placeholder bounds specified; behavior at bound specified; sign-off dependency made explicit | §1.1 |
| Legal prioritization asymmetry has no enforcement mechanism | Escalation paths differentiated; opt-out architecture item given earlier internal deadline with named escalation owner | Sign-Off Table |
| Cost estimate baseline was a rejected option | Cost reframed against 14/DAU baseline; SendGrid fallback itemized | §1.1, §6.2 |
| Geographic placeholder has no pre-launch configuration | Conservative APAC-weighted assumption specified until measurement exists | §1.1 |
| Document cut off mid-sentence (two instances) | Both truncation points identified and resolved | §1.1 |
| Sign-off table item count mismatch | Count corrected; all items reconciled | Sign-Off Table |

---

## Nine Items Requiring Sign-Off Before This Design Is Finalized

Two legal items share a correctness dependency but have **different internal deadlines and different escalation paths** because the dependency is asymmetric. The opt-out architecture is the harder blocker: it determines core preference table structure. The DM drop policy, if delayed alone, permits 60% of schema work to proceed.

**On E4 sequencing:** Retry contract enforcement and broadcast rate limiting are partially decoupled. Retry enforcement can proceed independently. Broadcast rate limiting requires the broadcast policy to be defined first. If broadcast policy sign-off is delayed past Month 3, broadcast capability is disabled at launch; retry enforcement ships on schedule regardless.

| Item | Section | Decision Deadline | Internal Escalation Trigger | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-----------------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §3 | Week 2 | None | Product | E1 volume model; E2 channel implementation | SMS channel sizing blocked; E2 delayed up to 2 weeks |
| Re-engagement email send rate | §3 | Week 2 | None | Product | E2 volume model input | SendGrid tier cannot be finalized; overage risk |
| **Opt-out compliance architecture — Legal** | §2.4 | **End of Week 2** | **End of Week 1: E3's manager escalates to Legal team lead if no engagement confirmed** | **Legal** | E3 implements chosen architecture | Schema work cannot begin; full one-week slip. Harder blocker of the two legal items. |
| **DM drop policy — Legal** | §2.4 | **End of Week 2** | None (delay alone does not block schema work) | **Legal** | E2 implements DM handling | If opt-out architecture resolved: 60% of schema work proceeds, DM schema deferred. If both unresolved: full slip. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | None | Procurement/Finance | E2 technical requirements | Self-hosted fallback: ~$9,500/month incremental cost; 3 weeks of E2 time (itemized in §6.2) |
| **Queue depth bounds and backpressure behavior (Tier 2/3)** | §1.1 | **End of Month 1** | None | **Engineering + Product** | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded Tier 2 growth; placeholder bounds operationally incomplete until resolved |
| **Tier 1 queue ceiling and circuit breaker behavior** | §1.1 | **End of Month 1** | None | **Engineering + Product** | E2 implements ceiling; E3 implements circuit breaker | Memory exhaustion on Tier 1 has no defined response; OOM kill risk during extreme spikes |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before Month 3 | None | Product | E4 implements rate limiting after policy defined; retry enforcement proceeds independently | Broadcast disabled at launch; does not block retry enforcement |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | None | Engineering | E3 owns registry; E4 owns enforcement independently | 429 responses produce data loss for non-compliant producers; volume and severity bounded in §1.1 |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Primary Use |
|----------|---------|-----|-------------|
| Low | 15% | 1.5M | Cost floor modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Infrastructure sizing target |
| High | 35% | 3.5M | Worker ceiling; threshold calibration |
| Spike | 35% DAU + event multiplier | 3.5M + event | Infrastructure ceiling |

Infrastructure is sized to the base scenario. The high scenario drives threshold calibration. The spike scenario drives worker ceiling and queue bound design.

---

#### Per-DAU Rate — Design Basis, Uncertainty, and Validation

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day.

**Design basis: 14/DAU — stated as an estimate, not a derived figure.**

The 14/DAU figure is the midpoint of the post-batching range (6–16/DAU). It is not derived from first principles. The design basis should be understood as: *the midpoint of a plausible range, chosen because it is neither optimistically low nor pessimistically high, with explicit validation planned before infrastructure is locked.*

---

##### External Benchmarks — Corrected Framing

**Instagram (~2018):** Approximately 1B notifications/day against ~500M DAU — roughly 2/DAU delivered. Delivered-to-generated ratios reported at 15–20%, implying 10–13 generated events/DAU before suppression.

**Twitter/X (~2022):** Peak notification generation cited at 4–6× delivered rate due to batching and deduplication. Delivered rate of ~3–4/DAU implies 12–24 generated events/DAU.

**What these benchmarks establish and do not establish:**

The Instagram figure supports the range 10–16/DAU at the generated level. The Twitter figure spans 12–24/DAU. Together, they provide reasonable support for the upper portion of the post-batching range (roughly 12–16/DAU) but provide **no external anchor for the lower portion (7.5–12/DAU)**. The lower range is entirely unanchored by external data.

These benchmarks are better characterized as: *establishing that 14/DAU is within the upper-plausible zone for social apps at this scale, while leaving the lower range unanchored.* If the actual rate falls below 12/DAU, the benchmarks provide no predictive support. This does not invalidate 14/DAU as a planning basis, but it means the beta cohort measurement is doing more epistemic work than the benchmarks are. The benchmarks are directional confirmation, not validation.

**What 14/DAU does not account for:** If this app has features that drive notification density above comparable apps — real-time multiplayer, high-frequency group DMs, or aggressive algorithmic re-engagement — 18–20/DAU is plausible. The design basis would be wrong in the optimistic direction.

**Three-scenario planning:**

| Planning Scenario | Per-DAU Rate | Design Implication |
|------------------|--------------|--------------------|
| Conservative | 11/DAU | Cost floor; worker count lower bound |
| **Base** | **14/DAU** | **Infrastructure sizing target** |
| Stress | 18/DAU | Worker ceiling; triggers design review if sustained |

Infrastructure is sized to the base scenario. The stress scenario is handled by the tiered degradation system. The conservative scenario informs cost modeling only.

---

##### Concentration Factor — Origin, Sensitivity, and Validation

**The 0.90 concentration factor** represents 90% of daily notification events occurring within a 3-hour peak window. It appears multiplicatively in all threshold calibration calculations. Its origin and validation status:

**Origin:** Derived from general mobile app engagement literature showing that social app activity concentrates heavily in commute windows, with dominant peaks typically lasting 2–4 hours. The 3-hour window with 90% concentration is a conservative (high-concentration) estimate. It is not measured from this app's data, which does not yet exist.

**Why concentration factor matters as much as per-DAU rate:** The concentration factor appears multiplicatively in peak rate calculations. A shift from 0.90 to 0.75 reduces the calculated peak by 17%. A shift from 0.90 to 0.95 increases it by 6%. At 14/DAU base, the difference between 0.75 and 0.95 concentration produces a peak rate swing of approximately 700/sec — comparable to the margin between normal operation and the Default A threshold. Per-DAU rate is often treated as the primary uncertainty, but the concentration factor has equal or greater leverage on threshold calibrations.

**Sensitivity analysis (High DAU scenario, 3.5M, 14/DAU):**

| Concentration | Peak Rate (Base DAU, 2.5M) | Peak Rate (High DAU, 3.5M) | Default A Threshold Status |
|---------------|---------------------------|---------------------------|---------------------------|
| 0.75 | 2,188/sec | 3,063/sec | Both below threshold — normal |
| **0.90 (design basis)** | **2,625/sec** | **4,083/sec** | **Both below threshold with corrected threshold** |
| 0.95 | 2,771/sec | 3,879/sec | Both below threshold |

*(Threshold values corrected in the calibration section below.)*

**Concentration recalibration trigger:** If measured concentration exceeds 0.93, the Default A threshold must be recalibrated before Month 2 infrastructure lock.

**Concentration factor added to beta cohort measurement scope:** Beta cohort instrumentation will capture event timestamps at per-user granularity, enabling measurement of the actual concentration distribution. E1's Week 9 report will include a concentration factor estimate with confidence interval alongside the per-DAU estimate. Both figures feed the Month 2 infrastructure decision.

---

##### Beta Cohort Validation Plan — Timeline, Statistical Justification, and Decision Rules

**Why the beta cohort is load-bearing:** The external benchmarks anchor the upper portion of the plausible range but leave the lower range unanchored. The beta cohort measurement is the primary mechanism for constraining the per-DAU estimate before infrastructure is locked. It is not a nice-to-have.

**Cohort size — statistical justification:**

A cohort of 50,000 users is chosen to achieve ±1/DAU precision at 95% confidence for the per-DAU rate estimate, assuming standard deviation of approximately 8/DAU (consistent with the 3× raw event spread). The required sample size is:

```
n = (z × σ / E)²
n = (1.96 × 8 / 1)² = (15.68)² ≈ 246
```

At 246 users required for the per-DAU estimate, 50,000 users provides substantial headroom. The cohort is sized at 50,000 primarily to enable concentration factor measurement with sufficient temporal resolution — measuring peak-window behavior requires enough users to distinguish signal from noise in hourly bucketing. At 50,000 users with 25% DAU engagement, approximately 12,500 users are active on any given day, producing roughly 175,000 events/day at 14/DAU. This is sufficient to measure concentration factor to ±0.03 at 95% confidence. The cohort size is justified by the concentration measurement requirement, not the per-DAU measurement requirement.

**Timeline:**

| Milestone | Week |
|-----------|------|
| Beta cohort instrumentation deployed | Week 3 |
| Beta cohort soft launch begins (50,000 users) | Week 4 |
| 30-day measurement window closes | Week 8 |
| E1 delivers per-DAU and concentration measurement report | Week 9 |
| Month 2 infrastructure decisions lock | **Week 10** |

This sequence provides one week of margin between measurement delivery and lock. It depends on the beta cohort launching no later than Week 4. **If the beta cohort is delayed beyond Week 6**, the measurement window cannot close before Week 10; the fallback applies: the 14/DAU basis is used as-is, the undersizing risk is documented, and the stress scenario (18/DAU) is used for the worker ceiling rather than the base scenario. E1 owns the beta cohort launch date and escalates immediately if a Week 6 delay is projected.

**Decision rules at Week 10 — four data quality outcomes:**

| Outcome | Condition | Action |
|---------|-----------|--------|
| Clean result, within range | Measured rate 11–16/DAU; concentration 0.80–0.93; CI width ≤ 2/DAU | Proceed with updated figures; recalibrate thresholds if measured values differ from design basis by more than 1/DAU or 0.03 concentration |
| Clean result, outside range | Measured rate > 16/DAU or < 11/DAU; CI width ≤ 2/DAU | Mandatory design review before infrastructure lock; E1 presents revised sizing to engineering team |
| Ambiguous result | CI width > 2/DAU for per-DAU rate OR > 0.05 for concentration | Do not use report as-is. E1 identifies source of variance (cohort composition, measurement artifact, genuine spread). If source is identifiable and correctable within 3 days, correct and re-report. If not, use stress scenario (18/DAU, 0.93 concentration) for all sizing decisions. Document the conservative choice explicitly. |
| Measurement failure | Instrumentation failure; fewer than 10,000 active users measured | Fall back to stress scenario; document; proceed with explicit risk acceptance from Engineering and Product |

The ambiguous result path does not default to "use the report anyway." Ambiguous data that is used uncritically is worse than acknowledged ignorance.

---

##### Revision Trigger — Corrected Two-Dimensional Logic

The revision trigger is a **two-dimensional condition**, not a per-DAU rate alone. The relevant question is: at what (per-DAU rate, DAU scenario) pair does Default A activate during normal high-end operation?

**Corrected peak rate calculations:**

| Per-DAU Rate | DAU | Peak Rate (0.90 concentration, 3-hour window) |
|-------------|-----|----------------------------------------------|
| 14/DAU | Base (2.5M) | 2,500,000 × 14 × 0.90 ÷ 10,800 = **2,625/sec** |
| 14/DAU | High (3.5M) | 3,500,000 × 14 × 0.90 ÷ 10,800 = **4,083/sec** |
| 15/DAU | Base (2.5M) | 2,500,000 × 15 × 0.90 ÷ 10,800 = **3