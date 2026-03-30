# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three architectural bets, stated with their actual limitations:

1. **Separate Redis instances per priority tier** — isolation is real only with separate infrastructure. Section 2.1 explains the cost and what it buys. Three queues on one instance is not isolation; it is labeling.

2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs, ElastiCache, RDS. Engineering time goes to integration quality, not plumbing.

3. **Validation before commitment** — the week-2 cohort checkpoint precedes infrastructure procurement. This section now states what the cohort can and cannot tell us, including the social graph density problem that tier reweighting cannot fix.

**Ten honest statements before the detail:**

The 17 notifications/user/day figure is derived from a three-tier model with per-tier rates and industry benchmarks. The derivation is in Section 1.2. The cohort validation cannot confirm this number is correct — it can only detect if the actual rate is dramatically higher. The social graph sparsity problem means the cohort will likely *underestimate* steady-state rates, making the 17/day ceiling the more defensible direction of error. Section 1.2 explains the logic.

The tier weights (5% / 35% / 60%) are a planning assumption, not a measurement. Section 1.2 states the basis and the sensitivity: if the actual split is 15/35/50, the planning ceiling increases to approximately 27/day and the infrastructure implications are material.

The 30% DAU/MAU ratio is load-bearing and uncertain. Section 1.1 treats a 35% ratio as a system-wide stress test with compounding effects across Redis, RDS, and worker counts. The trigger for action is a leading indicator, not a lagging one.

The viral spike model sizes for 5× sustained, not 10×. Section 1.3 provides complete quantitative analysis for both scenarios. The 350/sec per-worker figure is a benchmark assumption; Section 2.3 derives it and Section 1.3 shows the spike math sensitivity to that figure being wrong.

The >5× validation failure case produces a gap between the 1–2 week decision window and a 5–7 month rebuild. Section 1.2a describes the interim operating mode. The batching throughput reduction claim is now derived, not asserted, and the batch-boundary spike problem is addressed.

Redis Lists with BRPOP give LIFO behavior under accumulation. For social notifications, this is likely an accidental feature rather than a defect — the system preferentially delivers fresher content. Section 2.2 examines this properly, including what happens to the oldest items during multi-minute accumulation.

The Scenario A alert pages an on-call engineer for an event that is already over. The previous version kept this alert anyway and called it documentation. This version replaces it with a non-paging observability record. Section 1.3 explains the change.

The manual scaling response time range for 10× events (4–16 minutes) is an assumption. Section 1.3 now includes the 25-minute case and states what it costs.

SMS costs range from $240K to $1.38M/month. Auth SMS is exempt from the budget cap. Section 1.4 is now complete, including all three business-decision outcomes.

The operational surface is at the edge of what 4 engineers can safely own. Section 7 names what is cut and why.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — see sensitivity analysis below |
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

### 1.1a DAU/MAU Sensitivity: Compounding Effects and Leading Triggers

A 35% DAU/MAU ratio does not produce independent adjustments to individual components — it stresses multiple components simultaneously. The correct analysis is a system-wide stress test.

**Baseline (30%):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory at 2M item spike ceiling: ~4GB
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario — compounded:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)
- 36 P1 workers at 350/sec: 12,600/sec — headroom holds at 5×
- Scenario B arrival rate at 10×: ~20,800/sec — drain time extends to ~29 minutes vs. ~24 minutes at baseline

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously. The 35% scenario does not break any single component, but it creates a situation where Redis needs additional nodes *and* RDS needs read replica offloading *and* worker counts need adjustment — all at once.

**The trigger problem with lagging indicators:** The previous version of this design proposed triggering a capacity review after two consecutive weeks of 32%+ DAU/MAU. By that point, the system has already been operating under elevated stress for at least two weeks. The correct trigger is a leading indicator.

**Revised trigger for action:** E1 monitors a 7-day rolling DAU/MAU average. If this average crosses 30% for three consecutive days — before it reaches 32% — E1 initiates a coordinated capacity review covering Redis, RDS, and workers together, not sequentially. The review completes within one week. Three days of elevated signal is sufficient to distinguish a trend from noise; waiting for two full weeks is not justified when the compounding effects are known in advance.

**Why three days, not one:** A single day above 30% is plausibly a weekend effect or a minor content event. Three consecutive days indicates a sustained shift in user behavior. This is a judgment call; the specific threshold should be confirmed with E1 based on observed day-of-week variance during beta.

**Decisions not sensitive to this ratio:** Queue architecture, channel selection logic, preference management design, failure handling. These are correct across the plausible range.

### 1.2 The 17/Day Ceiling: Derivation, Tier Weights, and Cohort Limitations

#### Derivation of 17/day

The 17/day figure is derived from a three-tier user model with per-tier notification rates benchmarked against comparable social apps at similar scale stages.

**Tier definitions and per-tier rates:**

| Tier | Definition | Daily Active Users | Notifications/Day | Basis |
|------|------------|-------------------|-------------------|-------|
| T1 — Power users | Creates content, large follower count; generates significant fanout | 5% of DAU = 150K | ~50/day | Twitter/Instagram power user benchmarks at early scale; each post generates ~30–80 downstream notifications |
| T2 — Active consumers | Engages regularly (likes, comments, DMs) but creates rarely | 35% of DAU = 1.05M | ~12/day | Mid-tier engagement benchmarks; primarily receiving social graph activity |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% of DAU = 1.8M | ~5/day | Minimum engagement: digest emails, occasional DM, auth notifications |

**Weighted average:**

(0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 2.5 + 4.2 + 3.0 = **9.7/day**

This weighted average is approximately 10/day. The 17/day planning ceiling applies a 1.7× headroom multiplier over the model estimate, for three reasons:

1. **Social graph growth:** Notification volume scales super-linearly with network density. A user with 100 followers generates more notifications than 10 users each with 10 followers. As the network matures, per-user rates increase even if behavior does not change.

2. **Feature expansion:** The notification surface will grow over 6 months. New notification types are easier to add than to remove; planning at the model estimate invites infrastructure surprises.

3. **Model uncertainty:** The per-tier rates are benchmarks, not measurements. A 1.7× buffer is conservative but not extravagant given zero prior product data.

**The 17/day figure is therefore a ceiling with explicit headroom, not a point estimate.** Infrastructure is sized to 17/day. If actual rates land at the model estimate (~10/day), the system is over-provisioned by approximately 40% on worker counts — acceptable given the engineering cost of under-provisioning.

**Tier weight sensitivity:**

The 5/35/60 split is a planning assumption. The basis is industry data on social app user distributions at early scale — the long tail of passive users typically dominates once a product moves past early adopter cohorts. But for a product that has not reached scale, this is genuinely uncertain.

| Tier split assumption | Weighted avg notifications/day | 1.7× ceiling |
|-----------------------|-------------------------------|---------------|
| 5 / 35 / 60 (baseline) | 9.7 | 16.5 → 17 |
| 10 / 35 / 55 (more active mix) | 12.2 | 20.7 |
| 15 / 35 / 50 (early adopter-skewed) | 15.0 | 25.5 → ~27 |

If the actual user mix is 15/35/50 — plausible for a social app that has not yet achieved mass market penetration — the planning ceiling should be approximately 27/day, not 17/day. At 27/day, total notifications/day rises to ~81M, sustained peak throughput rises to ~2,840/sec, and P1 worker requirements increase to approximately 49. This is a material difference that requires a different Redis sizing and a different worker fleet.

**The week-2 cohort validation cannot resolve tier weight uncertainty** for the reasons described below. The tier weight assumption must be revisited at month 3 using whatever behavioral data is available from the beta, with explicit acknowledgment that the data will be early and noisy.

#### What the Cohort Validation Can and Cannot Do

**The social graph sparsity problem — not fixable by reweighting:**

A 50K-user beta cohort has structurally different social graph density than a 10M MAU network. In a sparse early network, each user has fewer followers and follows fewer people. A T1 power user in a 50K cohort might generate 20 downstream notifications per post (limited by sparse follower count); the same user in a mature 10M MAU network might generate 200. This is not a sampling bias problem — it is a network effect that makes early measurements structurally lower than steady-state.

Tier reweighting adjusts for having too many power users in the cohort. It cannot adjust for the fact that all users in the cohort, including the passive ones, are operating in a sparser network than they eventually will be.

**The consequence for the validation logic:** The week-2 cohort measurement will likely *underestimate* steady-state notification rates, not overestimate them. This inverts the naive concern about early adopter bias. The practical implication:

- A measurement below 17/day does not confirm the ceiling is correct. It is consistent with the ceiling being correct, but the social graph sparsity effect means the ceiling could still be too low.
- A measurement above 17/day is a strong signal that the ceiling is wrong, because it is elevated despite the sparsity effect working in the downward direction.
- The validation is therefore most useful as an upper-bound alarm, not as a confirmation mechanism.

**The within-tier inflation problem:**

Early adopters in every tier — including T3 passive users — are likely more engaged than the eventual general population in the same tier. A T3 early adopter chose to try a new social app; a T3 general population user may have been invited by a friend and barely uses it. The within-tier rates observed in week 2 are probably inflated across all tiers.

Combined with the sparsity effect (which pushes rates down) and the within-tier inflation effect (which pushes rates up), the direction of the net bias is uncertain. The sparsity effect is likely larger for T1 power users (whose notification volume scales with follower count) and the inflation effect is likely larger for T3 passive users (whose baseline engagement is low enough that early adopter selection dominates). No correction fully accounts for both effects simultaneously.

**The decision gate, revised:**

At end of week 2, E1 reviews the raw observed rate from the cohort — without tier reweighting, because the reweighting assumptions are themselves uncertain. The gate is calibrated to act only on large deviations, because the measurement is noisy in multiple directions.

| Observed Rate (raw, uncorrected) | Signal | Action | Owner | Window |
|----------------------------------|--------|--------|-------|--------|
| ≤ 17/day | Consistent with ceiling; sparsity effect means actual may be higher, but no immediate action required | Proceed with procurement; revisit at month 3 | E1 | — |
| 17–34/day (≤ 2×) | Ceiling is likely wrong even accounting for sparsity suppression | Increase worker counts before procurement; Redis sizing unchanged | E1 | 72 hours |
| 34–85/day (2–5×) | Ceiling is significantly wrong | Delay procurement; add Redis nodes; revisit architecture | E1 + lead | 1 week |
| >85/day (>5×) | Ceiling is fundamentally wrong | See Section 1.2a | Engineering lead + executive sponsor | See below |

**Timing:** The week-2 checkpoint fires before infrastructure procurement. If the checkpoint is missed or delayed, procurement is also delayed — not accelerated.

**False positive risk:** Before triggering the rebuild decision, E1 runs a second measurement in week 3 with a larger cohort sample if available, and reviews the raw event distribution for obvious outliers (a single viral event during the measurement window can distort the average significantly). The rebuild decision requires two consistent measurements or one measurement with a clear mechanistic explanation.

### 1.2a The >5× Case: Interim Operating Mode

If the week-2 measurement exceeds 85/day, the existing queue infrastructure cannot handle full volume during the 5–7 month rebuild. The interim operating mode is deliberate volume reduction.

**Batching throughput reduction — derived, not asserted:**

The previous version claimed aggressive batching reduces instantaneous throughput by "roughly 8–10×." This figure was not derived. The correct analysis:

At steady state with 1,750 notifications/sec arriving continuously, switching from near-real-time delivery to 15-minute batch delivery does not reduce the *average* throughput — it changes the *temporal distribution*. If notifications arrive smoothly, a 15-minute batch accumulates 1,750 × 900 = 1.575M items and releases them at the batch boundary as a spike, not as a smooth stream.

The throughput reduction claim requires an additional mechanism: **batch-boundary rate limiting**. When the batch releases, the worker pool does not attempt to drain the entire batch instantly. Instead, it processes at a controlled rate — for example, 500/sec instead of the maximum ~10,500/sec — spreading the 1.575M-item batch release over approximately 52 minutes. The next batch begins accumulating during this drain period.

This works only if the controlled release rate (500/sec) exceeds the accumulation rate at the reduced notification volume. After suppressing social engagement notifications (estimated 40–50% of volume), the arrival rate drops to approximately 875–1,050/sec. A 500/sec controlled release does not drain fast enough