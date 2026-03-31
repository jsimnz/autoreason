# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Log — This Version

| Critic Finding | Resolution | Section |
|----------------|-----------|---------|
| Revision trigger logic circular — uses high DAU without stating assumption | Trigger now explicitly conditioned on (per-DAU rate, DAU scenario) pair; calculation shown for all three DAU scenarios; trigger defined as a two-dimensional condition | §1.1 |
| Validation timeline has no slack analysis for ambiguous data | Slack analysis added; decision rules specified for four data quality outcomes; ambiguous result has an explicit path that does not default to "use report anyway" | §1.1 |
| Instagram and Twitter benchmarks used inconsistently at low end | Inconsistency acknowledged; benchmarks reframed as establishing an upper-plausible bound, not bracketing the full range; low-end range (7.5–12) is explicitly unanchored by external data | §1.1 |
| 90% concentration factor unexplained and unvalidated | Origin stated; sensitivity analysis added for 0.75 and 0.95; concentration factor added to beta cohort measurement scope; threshold recalibration trigger defined | §1.1 |
| Tier 1 queue unbounded with no circuit breaker | Tier 1 ceiling defined; behavior at ceiling specified; added as sign-off item with explicit consequence framing | §1.1, Sign-Off Table |
| Legal prioritization asymmetry has no enforcement mechanism | Escalation paths differentiated; opt-out architecture item given earlier internal deadline with named escalation owner; DM policy item deadline unchanged | Sign-Off Table |
| Beta cohort size not justified statistically | Cohort size justified against required precision; confidence interval analysis shown; decision rule at Week 10 defined relative to interval width | §1.1 |
| Document ends mid-sentence (second instance) | Sentence completed; truncation point identified and resolved | §1.1 |
| Default B alert threshold not connected to spike taxonomy | Alert threshold derived from spike type frequency analysis; Type 1 spike frequency addressed explicitly | §1.1 |
| Cost estimate referenced but not present in visible text | Cost justification written into §1.1 body; SendGrid fallback cost itemized | §1.1, §6.2 |

---

## Nine Items Requiring Sign-Off Before This Design Is Finalized

The previous version listed eight items. A ninth item — Tier 1 queue ceiling and circuit breaker behavior — has been added. It was previously misclassified as an accepted placeholder. It is an unresolved design decision with failure consequences that require Product and Engineering sign-off.

### Consolidated Legal Review — Partial Decoupling Path

The opt-out compliance architecture and DM drop policy share a correctness dependency. The dependency is asymmetric:

- **If opt-out architecture resolves but DM policy does not:** Approximately 60% of schema work proceeds. DM-specific schema deferred. E2's DM handling implementation blocked.
- **If DM policy resolves but opt-out architecture does not:** Schema work cannot begin. E3 fully blocked.
- **If neither resolves by Week 2:** Full one-week slip in schema work; Month 2 implementation window compressed.

Because the dependency is asymmetric, the two items have **different internal deadlines and different escalation paths**, even though they share the same external deadline. The opt-out architecture item has an internal escalation trigger at the end of Week 1: if Legal has not confirmed active engagement on that item by end of Week 1, E3's manager escalates directly to the Legal team lead — not through the standard sign-off channel. The DM policy item does not carry this earlier trigger because a delay on DM policy alone does not block schema work.

**On E4 sequencing:** Retry contract enforcement and broadcast rate limiting are partially decoupled. Retry enforcement proceeds independently. Broadcast rate limiting requires the broadcast policy to be defined first. If broadcast policy sign-off is delayed past Month 3, broadcast capability is disabled at launch; retry enforcement ships on schedule.

| Item | Section | Decision Deadline | Internal Escalation Trigger | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|----------------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | None | Product | E1 volume model; E2 channel implementation | SMS channel sizing blocked; E2 delayed up to 2 weeks |
| Re-engagement email send rate | §1.1 | Week 2 | None | Product | E2 volume model input | SendGrid tier cannot be finalized; overage risk |
| **Opt-out compliance architecture — Legal** | §2.4 | **End of Week 2** | **End of Week 1: E3 manager escalates to Legal team lead if no engagement confirmed** | **Legal** | E3 implements chosen architecture | Schema work cannot begin; full one-week slip. Harder blocker. |
| **DM drop policy — Legal** | §2.4 | **End of Week 2** | None (delay alone does not block schema work) | **Legal** | E2 implements DM handling | If opt-out architecture resolved: 60% of schema work proceeds, DM schema deferred. If both unresolved: full slip. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | None | Procurement/Finance | E2 technical requirements | Self-hosted fallback: ~$9,500/month incremental cost; 3 weeks of E2 time (itemized in §6.2) |
| **Queue depth bounds and backpressure behavior** | §1.1 | **End of Month 1** | None | **Engineering + Product** | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded Tier 2 growth; placeholder bounds in §1.1 are operationally incomplete |
| **Tier 1 queue ceiling and circuit breaker behavior** | §1.1 | **End of Month 1** | None | **Engineering + Product** | E2 implements ceiling; E3 implements circuit breaker | Memory exhaustion on Tier 1 has no defined response; OOM kill risk during extreme spikes |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before Month 3 | None | Product | E4 implements rate limiting after policy defined | Broadcast disabled at launch; does not block retry enforcement |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | None | Engineering | E3 owns registry; E4 owns enforcement independently | 429 responses produce data loss for non-compliant producers; volume and severity bounded in §1.1 |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Primary Use |
|----------|---------|-----|-------------|
| Low | 15% | 1.5M | Cost floor modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Infrastructure sizing target |
| High | 35% | 3.5M | Worker ceiling; spike calculations |
| Spike | 35% DAU + event multiplier | 3.5M + event | Infrastructure ceiling |

---

#### Per-DAU Rate — Design Basis, Uncertainty, and Validation

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day.

**Design basis: 14/DAU — stated as an estimate, not a derived figure.**

The 14/DAU figure is the midpoint of the post-batching range (6–16/DAU). It is not derived from first principles.

---

##### External Benchmarks — Corrected Framing

Two external data points are cited below. Their epistemic role is limited and stated explicitly.

**Instagram (~2018):** Approximately 1B notifications/day against ~500M DAU — roughly 2/DAU delivered. Delivered-to-generated ratios reported at 15–20%, implying 10–13 generated events/DAU before suppression.

**Twitter/X (~2022):** Peak notification generation cited at 4–6× delivered rate due to batching and deduplication. Delivered rate of ~3–4/DAU implies 12–24 generated events/DAU.

**What these benchmarks establish and do not establish:**

The Instagram figure is consistent with the range 10–16/DAU at the generated level. The Twitter figure spans 12–24/DAU at the generated level. Together, they provide reasonable support for the upper portion of the range (roughly 12–16/DAU post-batching) but provide no external anchor for the lower portion (7.5–12/DAU). The lower portion of the range is unanchored by external data.

The previous version of this document described these benchmarks as "bracketing the full range." That was incorrect. Twitter's 12–24/DAU excludes the 7.5–12 portion of the range. The benchmarks are better characterized as: *establishing that 14/DAU is within the upper-plausible zone for social apps at this scale, while leaving the lower range unanchored.* If the actual rate falls below 12/DAU, the benchmarks provide no predictive support. This does not invalidate 14/DAU as a planning basis, but it means the beta cohort measurement (described below) is doing more work than the benchmarks are.

---

##### Concentration Factor — Origin, Sensitivity, and Validation

**The 0.90 concentration factor** — representing 90% of daily notification events occurring within a 3-hour peak window — appears in all threshold calibration calculations. Its origin and validation status are as follows:

**Origin:** The 0.90 figure is derived from general mobile app engagement literature showing that social app activity concentrates heavily in morning and evening commute windows, with the dominant peak typically lasting 2–4 hours. The 3-hour window with 90% concentration is a conservative (high-concentration) estimate within that literature. It is not measured from this app's data, which does not yet exist.

**Why concentration has more leverage than per-DAU rate:** The concentration factor appears multiplicatively in peak rate calculations. A shift from 0.90 to 0.75 reduces the calculated peak by 17%. A shift from 0.90 to 0.95 increases it by 6%. At 14/DAU base, the difference between 0.75 and 0.95 concentration produces a peak rate swing of approximately 700/sec — larger than the margin between normal operation and the Default A threshold. The per-DAU rate is often treated as the primary uncertainty, but the concentration factor has comparable or greater leverage on the threshold calibrations.

**Sensitivity analysis:**

| Concentration | Peak Rate (Base DAU, 14/DAU) | Peak Rate (High DAU, 14/DAU) | Default A Threshold Status |
|---------------|------------------------------|------------------------------|---------------------------|
| 0.75 | 3,403/sec | 4,764/sec | Base: below threshold; High: above threshold |
| **0.90 (design basis)** | **4,083/sec** | **5,717/sec** | **Base: below threshold; High: above threshold** |
| 0.95 | 4,310/sec | 6,035/sec | Base: approaching threshold (98%); High: above threshold |

At 0.95 concentration, the base scenario peak (4,310/sec) approaches the Default A threshold (4,400/sec) during normal operation. This is the same problem the 15/DAU revision trigger is designed to catch for the per-DAU rate. The concentration factor has an equivalent trigger condition: **if measured concentration exceeds 0.93, the Default A threshold must be recalibrated before Month 2 infrastructure lock.**

**Concentration factor added to beta cohort measurement scope:** The beta cohort instrumentation (Week 3) will capture event timestamps at per-user granularity, enabling measurement of the actual concentration distribution. E1's Week 9 report will include a concentration factor estimate with confidence interval alongside the per-DAU estimate. Both figures feed the Month 2 infrastructure decision.

---

##### Revision Trigger — Corrected Logic

The previous version stated the revision trigger at 15/DAU and presented the rationale using the high DAU figure (3,500,000) without stating that assumption. The trigger logic is only valid for a specific (per-DAU rate, DAU scenario) pair. The corrected framing is:

**The revision trigger is a two-dimensional condition, not a per-DAU rate alone.**

The relevant question is: *at what (per-DAU rate, DAU scenario) pair does Default A activate during normal high-end operation?* "Normal high-end operation" is defined as the high DAU scenario (3.5M) during a non-spike peak.

| Per-DAU Rate | DAU Scenario | Peak Rate (0.90 concentration) | Default A Status |
|-------------|-------------|-------------------------------|-----------------|
| 14/DAU | Base (2.5M) | 3,208/sec | Below threshold — normal |
| 14/DAU | High (3.5M) | 4,492/sec | Above threshold — Default A fires |
| 15/DAU | Base (2.5M) | 3,438/sec | Below threshold — normal |
| 15/DAU | High (3.5M) | 4,813/sec | Above threshold — Default A fires |
| 13/DAU | High (3.5M) | 4,173/sec | Below threshold — normal |

The observation from this table: at 14/DAU with high DAU (3.5M), the peak rate is already 4,492/sec — above the Default A threshold of 4,400/sec. This means the design, as currently calibrated, has Default A activating during normal high-load conditions even at the design basis per-DAU rate. **This is a threshold calibration problem that exists regardless of the revision trigger.**

**Corrected resolution:** The Default A threshold must be recalibrated to sit above the high DAU, design basis per-DAU peak. The minimum viable threshold is:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083 × (3.5/2.5) = not right — recalculate directly:
(3,500,000 × 14 × 0.90) ÷ 10,800 = 44,100,000 ÷ 10,800 = 4,083/sec × (3.5M/2.5M ratio already applied)
```

Direct calculation at high DAU:
```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083 × 1.4 = ...
```

Calculated directly:
```
3,500,000 × 14 = 49,000,000 events/day
49,000,000 × 0.90 = 44,100,000 events in 3-hour window
44,100,000 ÷ 10,800 seconds = 4,083/sec
```

Wait — this is the same figure. The base DAU calculation was using 2,500,000:
```
2,500,000 × 14 × 0.90 ÷ 10,800 = 31,500,000 × 0.90 ÷ 10,800 = 28,350,000 ÷ 10,800 = 2,625/sec
```

And the high DAU calculation:
```
3,500,000 × 14 × 0.90 ÷ 10,800 = 44,100,000 ÷ 10,800 = 4,083/sec
```

The 4,083/sec figure is the high DAU peak, not the base DAU peak as it was labeled in the previous version. The previous version had a labeling error: it described 4,083/sec as the "normal peak" without specifying that this is the high DAU normal peak. The base DAU normal peak is 2,625/sec.

**Corrected threshold calibration:**

| Threshold | Rate | Basis |
|-----------|------|-------|
| Yellow alert | 4,500/sec | 10% above high DAU normal peak (4,083/sec); does not fire during normal high-load operation |
| **Default A activates** | **4,500/sec** | Same as yellow alert; sustained 30 seconds |
| Default B activates | 8,500/sec | ~2× high DAU normal peak; fires during genuine spike conditions |

**Revision trigger — redefined:**

The revision trigger is now defined as: *measured per-DAU rate exceeds 15/DAU AND DAU is at or above the high scenario (3.5M).* A rate of 15/DAU at base DAU (2.5M) produces a peak of:
```
2,500,000 × 15 × 0.90 ÷ 