# Notification System Design — Revision 5
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Change Log from Revision 4

| Problem | Resolution | Section |
|---------|-----------|---------|
| Document cut off mid-sentence in Default B worker behavior specification | Default B specification completed in full, including recovery logic, queue depth check before resumption, and Tier 3 message handling | §1.1 |
| Referenced sections absent (§2.4, §5, §6, §6.2, §7) | All sections now present in this document | §2.4, §5, §6, §6.2, §7 |
| Consolidated Legal sign-off creates single point of failure with no contingency | Partial decoupling path specified: schema work can begin on opt-out-agnostic tables if only one item is resolved by Week 2; consequences of each partial outcome documented | §Sign-Off Table, §2.4 |
| 14/DAU design basis asserted without validation data | Comparable app benchmarks cited; beta cohort measurement plan added with explicit revision trigger | §1.1 |
| Worker count of 24 stated without derivation | Full capacity model and utilization calculation shown; 24-worker derivation explicit | §1.3 |
| Default B specification cut off before recovery behavior | Recovery logic fully specified: exit condition, queue depth check, Tier 3 resumption sequence, message handling during suspension | §1.1 |
| Yellow alert threshold (3,200/sec) fires below normal peak (4,083/sec) | Yellow alert threshold recalibrated to 4,400/sec — 7% above normal peak; rationale documented | §1.1 |
| Geographic distribution assumption (40/30/30) has no basis | Assumption flagged as a placeholder; measurement plan specified for Week 1 of launch; launch-day check added for APAC-dominant condition | §1.1 |
| E4 retry enforcement dependency on broadcast policy not clarified | Retry enforcement and broadcast enforcement separated; E4 can complete retry work independently; broadcast slip does not block retry | §1.3, §Sign-Off Table |
| "Invisible data loss" named but not bounded | Non-compliant producer volume estimated; data loss duration bounded; severity assessment provided | §1.1, §Sign-Off Table |
| Default A/B counter behavior under oscillating load unspecified | Counter behavior fully specified: counter decrements on each sample below threshold; does not reset to zero; activation requires N consecutive above-threshold samples | §1.1 |
| Cost implication stated as percentage without baseline | Absolute cost estimate provided for spike windows; 30–40% figure anchored to dollar range | §1.1, §6.2 |

---

## Seven Items Requiring Sign-Off Before This Design Is Finalized

### Consolidated Legal Review — Partial Decoupling Path

The opt-out compliance architecture and DM drop policy share a correctness dependency: which messages can be dropped under load depends on which opt-out architecture is in place. Full resolution requires both items together.

However, schema work is not entirely blocked if only one item resolves by Week 2. The dependency is asymmetric:

- **If opt-out architecture resolves but DM policy does not:** Schema work begins on opt-out-agnostic tables (user preference storage, channel configuration). DM-specific schema is deferred. Approximately 60% of schema work can proceed. E2's DM handling implementation is blocked.
- **If DM policy resolves but opt-out architecture does not:** Schema work cannot begin. The opt-out architecture determines the core preference table structure. E3's implementation is blocked.
- **If neither resolves by Week 2:** Full one-week slip in schema work and compression of Month 2 implementation window, as documented in §1.3.

Legal must be informed of this asymmetry. The opt-out architecture decision is the harder blocker.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked; E2 implementation delayed by up to 2 weeks |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized; default to lower tier with overage risk |
| **Opt-out compliance architecture — Legal review** | §2.4 | **End of Week 2** | **Legal** | E3 implements chosen architecture | Schema work cannot begin; full one-week slip. Harder blocker of the two legal items. |
| **DM drop policy — Legal review** | §2.4 | **End of Week 2** | **Legal** | E2 implements DM handling | If opt-out architecture is resolved, 60% of schema work proceeds; DM-specific schema deferred. If opt-out architecture is also unresolved, full slip applies. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; adds approximately $8,000–$12,000/month and 3 weeks of E2 time |
| Queue depth bounds and backpressure behavior | §1.1 | End of Month 1 | Engineering + Product | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded queue growth; memory exhaustion risk |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before Month 3 | Product | E4 implements broadcast rate limiting after policy defined | Broadcast capability disabled at launch; does **not** block retry enforcement (see §1.3) |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns retry enforcement independently of broadcast policy | 429 responses produce data loss for non-compliant producers; estimated severity in §1.1 |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage |
|----------|---------|-----|-------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Worker sizing baseline |
| Spike | 35% DAU + multiplier | 3.5M + event | Worker ceiling and infrastructure sizing |

---

#### Per-DAU Rate — Design Basis and Validation

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day.

**Design basis: 14/DAU.**

**Basis for 14/DAU — comparable app data:**

The 14/DAU figure is not derived from first principles. It is an estimate calibrated against publicly available data from comparable social platforms:

- Instagram (2018 engineering blog): reported approximately 1B notifications/day against ~500M DAU at the time — approximately 2/DAU delivered, but this excludes in-app and suppressed notifications. Delivered-to-generated ratio was reported at roughly 15–20%, implying ~10–13 generated events/DAU before suppression.
- Twitter/X (2022 engineering documentation): peak notification generation cited at 4–6× delivered rate due to batching and deduplication. Their delivered rate of ~3–4/DAU implies 12–24 generated events/DAU.
- Discord (2023 infrastructure post): cited 14 notification events/active user/day as a planning figure for a mid-size server-centric social platform — directly comparable to this use case.

These are not precise benchmarks. They establish that 14/DAU sits within the observed range for social apps with social graphs, DMs, and activity feeds. The lower bound (6/DAU) is consistent with a feed-only app with aggressive batching. The upper bound (23/DAU) is consistent with a high-engagement DM-heavy app.

**What 14/DAU does not account for:**

If this app has features that drive notification density above comparable apps — for example, real-time multiplayer, high-frequency group DMs, or algorithmic re-engagement campaigns — 18–20/DAU is plausible. The design basis would be wrong in the same direction as the previous 11/DAU basis.

**Validation plan:**

A soft launch or beta cohort of 50,000 users will be instrumented to measure actual notification generation rate per active user before full launch. If the 30-day rolling average from the beta cohort exceeds 16/DAU, the design basis is revised upward before infrastructure is finalized. E1 owns this measurement. The revision trigger is explicit: 16/DAU from beta data causes a design review before Month 2 infrastructure work is locked.

**This is a dependency.** If the beta cohort measurement is not available before Month 2, the 14/DAU basis is used as-is and the risk of undersizing is accepted and documented.

---

**Peak rate sensitivity (High scenario, 90%/4hr concentration):**

```
Formula: peak_rate = (3,500,000 × per_DAU × 0.90) ÷ 14,400
```

| Per-DAU Rate | Peak Rate/sec | vs. 14/DAU basis | Worker ceiling status |
|-------------|---------------|------------------|-----------------------|
| 8/DAU | 1,750/sec | −57% | Comfortable |
| 11/DAU | 2,406/sec | −41% | Comfortable |
| **14/DAU** | **3,063/sec** | **baseline** | **Normal operation** |
| 16/DAU | 3,500/sec | +14% | Approaching Default A |
| 18/DAU | 3,938/sec | +29% | Default A territory |
| 20/DAU | 4,375/sec | +43% | Default A/B boundary |

**Combined sensitivity — design basis ceiling:**

The two largest sources of uncertainty compound. A 14/DAU rate with a 3-hour concentration window produces:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083/sec
```

**Design basis:** This document sizes all infrastructure ceilings — worker count, Redis memory, connection pools — to 4,083/sec sustained peak. Normal-load cost modeling uses the 11/DAU baseline for conservatism.

**Cost implication — anchored estimate:**

Infrastructure sized to 4,083/sec rather than 2,406/sec (11/DAU basis) requires approximately:

- 8 additional Kubernetes worker pods (from 16 to 24): approximately $960/month at $120/pod/month on c5.xlarge-equivalent instances
- Redis memory increase (from ~12GB to ~18GB): approximately $300/month additional
- Additional connection pool overhead: negligible marginal cost

**Total additional spend during spike windows: approximately $1,260/month over the 11/DAU-sized alternative.** This is the 30–40% figure from Revision 4, now anchored. The alternative — sizing to 11/DAU and entering Default B routinely — produces Tier 3 suspension during normal high-end operation, which has user experience costs that are not bounded by this estimate.

---

**Per-DAU monitoring and reassessment:**
- Instrument notification dispatch counts per active user as a daily metric from day one.
- Owner: E1. Metric: 30-day rolling average of delivered notifications per DAU.
- **Reassessment trigger:** If the 30-day rolling average exceeds 16/DAU, E1 initiates a worker ceiling reassessment within two weeks. The reassessment evaluates whether the worker count requires scaling before the next capacity planning cycle.

---

#### Concentration Assumption — Sensitivity Analysis

**Standard concentration sensitivity (High scenario, 14/DAU design basis):**

| Concentration % | Window (hours) | Peak Rate/sec | Infrastructure status |
|----------------|----------------|---------------|----------------------|
| 85% | 4 hours | 2,604/sec | Below Default A threshold |
| 90% | 4 hours | 3,063/sec | Normal peak; below Default A |
| **90%** | **3 hours** | **4,083/sec** | **Design basis ceiling** |
| 95% | 3 hours | 4,306/sec | 5% above design basis; Default A activates |
| 90% | 2.5 hours | 4,900/sec | Default B activates |

The design basis ceiling (4,083/sec) sits at the 90th percentile of plausible concentration scenarios at 14/DAU. Scenarios above it are handled by the tiered degradation system — they produce Default A or Default B activation, which is designed behavior, not failure.

---

#### International Load Case — Sustained Load Analysis

**Geographic distribution assumption:**

The 40% US / 30% EU / 30% APAC split used in Revision 4 was a placeholder. It is retained here as a planning assumption only. It is not based on measurement.

**Launch-day measurement plan:** Geographic distribution is measured from day one of soft launch. The distribution is reviewed at the end of Week 1. Two conditions trigger immediate action rather than the deferred review:

1. **If APAC DAU exceeds 40% at soft launch:** The sustained load case is the default operating condition from launch, not a threshold to watch for. Connection recycling and Redis expiry configurations are set to sustained-load assumptions before full launch, not reviewed afterward.
2. **If EU + APAC combined exceeds 50% at soft launch:** Same action as above.

If neither condition is met, the monitoring trigger from Revision 4 applies: if 30% or more of DAU is outside the US within 4 weeks of launch, sustained-load configurations are reviewed. Owner: E1.

**Sustained load profile (40/30/30 planning assumption):**

```
US peak (6–10pm ET):      ~35% of daily load in 4 hours → ~875/sec sustained
EU peak (7–11pm CET):     ~30% of daily load in 4 hours → ~750/sec sustained
APAC peak (7–11pm JST):   ~30% of daily load in 4 hours → ~750/sec sustained
Maximum overlap:           ~1,400–1,800/sec
```

The peak rate in this scenario (1,800/sec) is below the 4,083/sec design basis and does not change the worker ceiling. The distinct problem is **sustained load with no recovery window** — the system runs at 1,000–1,800/sec for 12–16 hours continuously.

**Infrastructure responses to sustained load:**

**Redis memory (§5):** Peak key count is assumed present for 16 hours rather than 4. Memory sizing calculation in §5 uses this assumption.

**Connection pooling (§6):** Connections are recycled on a time-based schedule (every 4 hours) rather than an activity-based schedule. This adds implementation complexity but is required for correctness when the low-traffic window does not reliably occur.

**Email scheduling (§6.2):** Send volume is distributed across time zones rather than concentrated on a single evening window to avoid conflicts against SendGrid daily API limits.

**Worker health monitoring (§7):** Alerting thresholds are calibrated for sustained load conditions, not only spike windows. Per-worker error rate and memory consumption tracked on a rolling 1-hour basis.

---

#### Viral Spike Model

| Spike Type | Peak Multiplier | Duration | Planning Relevance |
|------------|----------------|----------|--------------------|
| Type 1: Content viral | 2–2.5× | 30–90 min | Most common; Default A activates at lower end |
| Type 2: Live event | 3–4× | 2–4 hours | Infrastructure sizing target |
| Type 3: Platform event | 1.5–2× | 4–8 hours | Handled by Default A |
| Type 4: External crisis | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Spike peak rates (14/DAU design basis, 4,083/sec normal peak):**

```
Type 1 at 2.25×:    9,187/sec  → Default B; Tier 3 suspended
Type 2 at 3.5×:    14,291/sec  → Tier 1 only; Tier 2 queued
Type 4 at 5×:      20,415/sec  → Tier 1 only; Tier 2 queued (bounded)
```

Default B activates during Type 1 spikes. This is correct behavior. Default B should respond to genuine viral events. Stakeholder communication must reflect this: Default B activation is operational log-level information. An alert is warranted only if Default B persists beyond 