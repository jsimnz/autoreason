# Notification System Design — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten specific criticisms of the prior version. Each section heading notes what changed and why. The prior version was intellectually honest about epistemic problems and then ignored them in the action columns. This version attempts to close that gap — where it cannot, it says so explicitly rather than deferring to absent sections.

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The three architectural bets are unchanged. What changed is the honesty about what we do not know and what we have decided to do anyway.

**Twelve honest statements before the detail:**

The 17/day planning ceiling cannot be confirmed by cohort validation before procurement. The validation gate at ≤17/day does not mean "confirmed" — it means "no strong evidence of catastrophic error." Procurement proceeds under acknowledged uncertainty. The hedge is purchasing initial capacity in phases with a 6-week expansion window rather than committing to full capacity upfront. Section 1.2 explains what this costs and what it buys.

The tier weights (5/35/60) are unvalidatable before the infrastructure decisions that depend on them. The resolution is not better measurement — it is designing the infrastructure to be re-sizable within the 6-month window. Section 1.2 specifies the re-sizing path, lead times, and decision criteria for the month-3 revisit, including what data will be available and what thresholds trigger action.

The 350/sec per-worker assumption was previously unjustified. Section 1.3 now derives it from first principles, states its sensitivity, and specifies a month-1 load test that validates or replaces it before any sizing decisions downstream depend on it.

The interim operating mode arithmetic in Section 1.2a contained an unacknowledged contradiction: overlapping batch releases under a 15-minute cycle with 42–58 minute drain times means up to three batches accumulate simultaneously. Section 1.2a now analyzes queue equilibrium under this overlap condition and states the conditions under which it is stable.

The false positive protection for the >5× decision required a week-3 confirmatory measurement while the system was already under severe stress. This is replaced: a >5× measurement triggers an immediate 48-hour technical review, not a week-long confirmatory measurement. The review either confirms the finding or identifies a specific, documented artifact that explains it. Section 1.2 specifies what constitutes a valid artifact.

Auth SMS is exempt from the budget cap. The prior version left this as an unmonitored cost vector. Section 1.4 now specifies a hard ceiling on the auth SMS counter, a review cadence, and the fraud detection trigger that escalates before the ceiling is reached.

Redis Lists BRPOP LIFO behavior was called an "accidental feature" without defining when it becomes unacceptable. Section 2.2 now specifies the queue depth threshold above which LIFO behavior produces unacceptable P1 delivery latency, and the mitigation.

The month-3 tier weight revisit had no stated decision criteria. Section 1.2 now specifies the measurement methodology, threshold triggers, decision owner, action lead times, and whether 3 months is sufficient to act on the finding.

The Scenario A alert replacement lost information about recurring extreme fanout patterns. The non-paging observability record is retained for single occurrences, but a recurrence detector is added: two Scenario A events within 60 minutes triggers a page. Section 1.3 explains the logic.

Section 7 was absent. It is now present. It names specifically what is cut from the operational surface, which engineer owns what, and what the on-call structure looks like. Every operational assumption in the other sections is grounded against this staffing reality.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — see sensitivity analysis |
| Notifications/user/day | ~17 | Planning ceiling — derivation in Section 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike — Scenario A | 20× instantaneous, 90–120 sec | Single viral post fanout |
| Viral spike — Scenario B | 5× sustained, 10–30 min | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### 1.1a DAU/MAU Sensitivity

**Baseline (30%):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory at 2M item spike ceiling: ~4GB
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario — compounded:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)
- 36 P1 workers at 350/sec: 12,600/sec — headroom holds at 5× under the 350/sec assumption; see Section 1.3 for the sensitivity of this claim to the per-worker figure
- Scenario B arrival rate at 10×: ~20,800/sec — drain time extends to ~29 minutes vs. ~24 minutes at baseline

The compounding risk: Redis memory and RDS write throughput both approach thresholds simultaneously. The 35% scenario does not break any single component, but creates a situation where Redis needs additional nodes *and* RDS needs read replica offloading *and* worker counts need adjustment — all at once.

**Revised trigger for action:** E1 monitors a 7-day rolling DAU/MAU average. If this average crosses 30% for three consecutive days, E1 initiates a coordinated capacity review covering Redis, RDS, and workers together. The review completes within one week. Three consecutive days distinguishes a trend from noise; the specific threshold should be confirmed with E1 against observed day-of-week variance during beta.

### 1.2 The 17/Day Ceiling: Derivation, Validation Limits, and the Procurement Hedge

#### Derivation of 17/day

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks; each post generates ~30–80 downstream notifications |
| T2 — Active consumers | Engages regularly, creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 2.5 + 4.2 + 3.0 = **9.7/day**

The 17/day planning ceiling applies a 1.7× headroom multiplier for three reasons: social graph super-linear growth, feature expansion over 6 months, and model uncertainty from zero prior product data.

**Tier weight sensitivity:**

| Tier split | Weighted avg/day | 1.7× ceiling | P1 workers | Infrastructure implication |
|------------|-----------------|--------------|------------|---------------------------|
| 5/35/60 (baseline) | 9.7 | ~17 | ~30 | Baseline |
| 10/35/55 | 12.2 | ~21 | ~37 | +25% workers |
| 15/35/50 (early adopter-skewed) | 15.0 | ~27 | ~49 | Different Redis sizing |

#### What the Validation Can and Cannot Do

The week-2 cohort measurement will structurally underestimate steady-state rates due to social graph sparsity — a 50K-user cohort has lower follower counts than a mature 10M MAU network, so T1 users generate fewer downstream notifications per post. This means a measurement at or below 17/day is consistent with the ceiling being correct but does not confirm it. A measurement above 17/day is a stronger signal because it is elevated despite sparsity working in the downward direction.

The validation is an upper-bound alarm, not a confirmation mechanism.

**The decision gate:**

| Observed Rate | Signal | Action | Owner | Window |
|---------------|--------|--------|-------|--------|
| ≤ 17/day | No strong evidence of catastrophic error | Proceed with Phase 1 procurement (see below) | E1 | — |
| 17–34/day (≤ 2×) | Ceiling likely wrong | Increase worker counts in Phase 1 procurement; Redis sizing unchanged | E1 | 72 hours |
| 34–85/day (2–5×) | Ceiling significantly wrong | Delay Phase 1; add Redis nodes; revisit architecture | E1 + lead | 1 week |
| >85/day (>5×) | Ceiling fundamentally wrong | 48-hour technical review; see Section 1.2a | Engineering lead + executive sponsor | 48 hours |

**The >5× false positive protection — revised:**

The prior version required a week-3 confirmatory measurement. This was wrong: at >5× overrun, the system is already under severe stress, and a week of additional delay consumes the most valuable response time. The replacement:

Within 48 hours of a >5× measurement, E1 and the engineering lead conduct a technical review. The review either (a) confirms the finding as representative, or (b) identifies a specific documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains the spike as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. If no valid artifact is identified, the finding is confirmed and the Section 1.2a protocol activates.

#### The Procurement Hedge: Phased Commitment Under Acknowledged Uncertainty

The prior version's ≤17/day action column said "proceed with procurement" — committing full infrastructure based on a number that cannot be confirmed. This revision replaces full upfront commitment with phased procurement.

**Phase 1 (weeks 3–8, immediately after validation gate):** Provision for 60% of baseline sizing — approximately 18 P1 workers, a single Redis cluster, and RDS at baseline write throughput. This handles up to ~30/day observed rates, covers the sparsity-adjusted expected range, and is fully operational for beta.

**Phase 2 trigger (month 3 revisit):** After 8 weeks of live traffic data, provision the remaining 40% or more depending on month-3 findings. The 6-week window between month 3 and month 4.5 is sufficient to procure and configure additional managed instances — ElastiCache scaling and RDS read replicas are available within days; additional EC2 worker capacity is available within hours.

**What this costs:** Running at 60% capacity means the system cannot handle a full Scenario B spike at 5× during weeks 3–8. The mitigation is that Scenario B events — sustained 5× spikes from live events or trending topics — are unlikely during a 50K-user beta. If one occurs, the queue accumulates and delivery latency increases; the system does not drop notifications, it delays them. This is acceptable during beta; it would not be acceptable at full launch.

**What this buys:** Avoids locking into full infrastructure based on unconfirmable estimates. The cost difference between Phase 1 and Phase 1+2 is approximately 40% of monthly infrastructure spend — on managed services at this scale, roughly $8–15K/month depending on exact configuration. The option value of not over-committing is worth more than this cost.

#### Month-3 Tier Weight Revisit: Decision Criteria, Data, and Action Lead Times

The month-3 revisit was previously specified without decision criteria. This section closes that gap.

**What data will be available at month 3:** Eight weeks of live traffic from the beta cohort, growing from 50K to a target of 200–500K users if the beta ramp proceeds on schedule. At 200K+ users, social graph density is materially higher than the week-2 cohort, making per-T1-user notification rates more representative. Behavioral segmentation data (post frequency, follower counts, engagement rates) will allow direct measurement of tier composition rather than assumption.

**Measurement methodology:** E1 runs a 7-day measurement window in week 9–10, capturing per-user notification rates and segmenting by behavioral tier using the definitions in the table above. The weighted average is computed directly from observed data, not from the benchmark-based model.

**Threshold triggers for action:**

| Month-3 Observed Rate | Finding | Action | Lead Time to Completion |
|-----------------------|---------|--------|------------------------|
| ≤ 17/day | Baseline confirmed | Complete Phase 2 at baseline sizing | 2–3 weeks (managed service provisioning) |
| 17–21/day (≤ 10/35/55 scenario) | Moderate overrun | Complete Phase 2 at +25% worker count | 2–3 weeks |
| 21–27/day (≤ 15/35/50 scenario) | Material overrun | Complete Phase 2 at +60% worker count; add Redis node | 3–4 weeks |
| >27/day | Ceiling wrong at all tier splits | Immediate architecture review; executive escalation | Begin within 1 week |

**Decision owner:** E1 owns the measurement and the initial finding. The engineering lead approves any action requiring >20% infrastructure change. The executive sponsor is notified of any finding above 21/day.

**Is 3 months sufficient to act?** For findings up to the 15/35/50 scenario, yes — 3 months remaining provides sufficient lead time for managed service provisioning (days to weeks) and worker scaling (hours). For a >27/day finding, 3 months is tight but not impossible for infrastructure changes; it is insufficient for architectural changes (queue redesign, new channel infrastructure). A >27/day finding at month 3 means the system launches with known limitations, documented explicitly for the executive sponsor.

### 1.2a The >5× Case: Interim Operating Mode

#### Queue Equilibrium Under Overlapping Batch Releases — The Unacknowledged Contradiction, Now Addressed

The prior version described a 15-minute batch cycle with 42–58 minute drain times and did not analyze whether the queue reaches a stable equilibrium or grows without bound. This section corrects that.

**The overlap condition:** With a 15-minute batch cycle and a 42–58 minute drain time, up to three or four batches are accumulating simultaneously before the first finishes draining. The queue does not shrink monotonically between releases — it grows in steps.

**Equilibrium analysis:**

Let:
- A = post-suppression arrival rate (~875–1,050/sec)
- R = controlled release rate (1,500/sec)
- B = batch accumulation period (900 seconds)
- Items accumulated per batch: A × B = ~787K–945K items

At each 15-minute boundary, a new batch of ~787K–945K items is queued for release. The release process drains at 1,500/sec net of arrivals:
- Net drain rate: R − A = 1,500 − 875 to 1,500 − 1,050 = 450–625/sec
- Time to drain one batch: 787K / 625 to 945K / 450 = 1,259–2,100 seconds = ~21–35 minutes

Since drain time (21–35 minutes) is greater than the batch cycle (15 minutes), at any given moment 1–2 additional batches are accumulating while the first drains. The total queue depth at any moment is bounded by:

**Maximum queue depth = items in active drain + items accumulated during drain time**
= one batch + (drain time / batch period) × one batch
= ~945K + (35