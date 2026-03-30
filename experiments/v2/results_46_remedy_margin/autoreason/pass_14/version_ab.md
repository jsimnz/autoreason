# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Reading Order

Read this document front to back. Section 1 establishes scale assumptions and spike definitions that all subsequent sections reference. Section 7 (staffing) appears last because it references operational thresholds defined in earlier sections — not because it is less important. The staffing constraints in Section 7 were used to make every sizing and scope decision in Sections 1–6.

**What this document is:** Several foundational inputs — per-user notification rates, tier distributions, the headroom multiplier — cannot be validated before beta. This document is explicit about which numbers are uncertain, what that uncertainty implies for sizing decisions, and what the detection mechanisms are for when the estimates are wrong. Where a number is a judgment call rather than a derived value, it is labeled as such.

---

## Section 1: Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Scenario A — Viral post fanout:** A post by a high-follower user generates approximately 20× baseline instantaneous throughput lasting 90–120 seconds. Sharp peak, rapid natural decay.

**Scenario B — Live event or trending topic:** Sustained elevated activity at approximately 5× baseline lasting 10–30 minutes. Broad plateau rather than a sharp spike.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity in 1.1a |
| Notifications/user/day | ~17 | Planning ceiling — derivation and limitations in 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Scenario A instantaneous | 20× baseline | Single viral post fanout |
| Scenario B sustained | 5× baseline, 10–30 min | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### 1.1a DAU/MAU Sensitivity

**Baseline (30% DAU/MAU):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory (raw payload): ~4GB at 2M item spike ceiling
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory (raw payload): ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously under the 35% scenario. No single component breaks, but the system requires coordinated scaling across three components at once — the scenario most likely to create operational confusion under a 4-engineer constraint.

**Note on Redis memory figures:** The 4GB and 4.8GB figures are raw payload estimates only. Section 3.2 accounts for Redis overhead, key expiry metadata, and non-queue data structures when establishing actual provisioned capacity.

### 1.1b DAU/MAU Trigger — Calibration

**Purpose:** This trigger initiates a coordinated capacity review. It is not a paging condition. It belongs in the weekly engineering sync, not the on-call runbook. See Section 7.3 for the distinction between page-worthy and sync-review conditions.

**Pre-beta threshold (beta start through week 6):** DAU/MAU 7-day rolling average exceeds 33% for five consecutive days. This errs toward missing a gradual trend rather than generating false alarms during the first weeks of a new system.

**Week-6 calibration (requires 28+ days of beta data):**

Standard deviations computed from daily DAU/MAU ratios are not statistically independent — consecutive days are serially correlated, because the same users drive both numerator and denominator across days. Using a naive standard deviation on autocorrelated data produces an interval that is too narrow, which means the threshold triggers more frequently than designed.

To correct for this:

1. Record daily DAU/MAU for all available beta days.
2. Compute the lag-1 autocorrelation coefficient (ρ) of the daily ratio series.
3. Compute the effective sample size: n_eff = n × (1 − ρ) / (1 + ρ), where n is the number of observations.
4. Compute the standard deviation of the series using the full n observations, then scale it by √(n / n_eff) to produce an autocorrelation-adjusted standard deviation.
5. Set the revised threshold at: observed mean + (1.5 × adjusted standard deviation), rounded to the nearest 0.5%.
6. If the result falls below 31% or above 36%, flag to the engineering lead before applying — either extreme suggests measurement noise.

**If calibration fails** (adjusted standard deviation > 5%, or n_eff < 10): The series is too noisy or too short to produce a reliable threshold. Substitute an absolute threshold of 3.5M daily active users, five-consecutive-day rule. This is the 35% DAU/MAU scenario from Section 1.1a expressed as an absolute count. It is a pre-chosen fallback, not an adaptive output. The engineering lead should note this explicitly when communicating the switch.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. Completes within one week. E1 owns it; the engineering lead approves any recommendation requiring more than 20% infrastructure change.

---

### 1.2 The 17/Day Planning Ceiling

#### The Estimation Problem — Stated Directly

The 17/day ceiling is built on three layers of uncertainty that compound rather than cancel.

**Layer 1 — Benchmark provenance:** The per-tier rates (50/12/5) come from Twitter/Instagram early-scale benchmarks. Those products had different content types, different social graph structures, and different notification policies than this app. The rates are plausible starting points, not validated inputs.

**Layer 2 — Tier weight circularity:** The tier weights (5/35/60 baseline) cannot be validated before the infrastructure decisions that depend on them. Choosing the worst-case row of the sensitivity table (15/35/50) selects a specific uncertain number and calls it conservative — but the 15/35/50 split is itself derived from the same unvalidated benchmarks. The circularity is not resolved by choosing the worst case; it is shifted.

**Layer 3 — The headroom multiplier:** The 1.7× multiplier is a judgment call. It is not derived from a percentile of historical variance, a confidence interval, or a reference benchmark. 1.5× would produce a ceiling of ~15/day; 2.0× would produce ~19/day. These differences are material to worker sizing. The 1.7× figure sits between a multiplier that feels insufficiently conservative and one that would require justifying significantly higher Phase 1 spend. That is the honest basis for it.

**Consequence:** Phase 1 sizing is treated as a provisional commitment, not a derived answer. The real answer comes from 8 weeks of beta data. The sizing below is the minimum defensible starting point.

#### Derivation

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks |
| T2 — Active consumers | Engages regularly, creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 9.7/day × 1.7× headroom = **~17/day**

**Tier weight sensitivity:**

| Tier split | Weighted avg/day | 1.7× ceiling | P1 workers | Infrastructure implication |
|------------|-----------------|--------------|------------|---------------------------|
| 5/35/60 (baseline) | 9.7 | ~17 | ~30 | Baseline |
| 10/35/55 | 12.2 | ~21 | ~37 | +25% workers |
| 15/35/50 (early adopter-skewed) | 15.0 | ~27 | ~49 | Phase 1 sizing anchor |

**Why 60% capacity:** Phase 1 is anchored to the 15/35/50 scenario at 60% capacity. 60% is the tradeoff point between two failure modes: too tight (no headroom for Scenario A or B spikes) and too loose (wasted cost on unvalidated assumptions). At 60% of the 27/day worst-case ceiling, the system handles the full worst-case scenario with 40% headroom before emergency scaling is required. 70% reduces headroom to 30% — acceptable but leaving less response time during a Scenario B event. 50% adds approximately $3–5K/month for headroom that is unlikely to be needed even under the worst modeled scenario. This is a judgment call. If the executive sponsor prefers a different risk/cost tradeoff, 55% or 65% are reasonable alternatives.

#### Decision Gate

| Observed Rate | Action | Owner | Window |
|---------------|--------|-------|--------|
| ≤ 17/day | Proceed with Phase 1 provisioning | E1 | — |
| 17–25/day | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day | Pause beta expansion; add Redis node; architectural review | E1 + Lead | 1 week |
| > 51/day | 48-hour technical review — see Section 1.2a | Lead + executive sponsor | 48 hours |

**Relationship between this gate and Phase 2 provisioning triggers:** The decision gate uses absolute observed rates as thresholds. The Phase 2 provisioning framework uses rates relative to Phase 1 sizing. These are different instruments with different purposes. The decision gate is a real-time alert mechanism during beta. The Phase 2 framework is a structured review at month 3 using accumulated data. If both are active simultaneously — which is possible if a decision gate event occurs near month 3 — the decision gate takes priority. The Phase 2 review is suspended until the decision gate action is resolved. E1 notifies the engineering lead when this condition occurs.

**Why the escalation threshold is 3× (51/day) rather than a higher multiplier:** Beta rates systematically understate steady-state rates because the social graph is sparse during early beta — T1 users have fewer followers, so each post generates fewer downstream notifications than it will at steady state. This suppression is real and directionally certain, but its magnitude cannot be quantified before the graph densifies. A 3× reading in a sparse graph is more alarming than it would appear in a mature network, because the steady-state rate is higher still by an unknown amount. Acting at 3× costs engineering time. Acting at 5× after the graph densifies may mean launching with undersized infrastructure.

**Graph densification detection mechanism:** To avoid discovering this problem only at full launch, E1 will track the ratio of observed-to-modeled notifications per T1 user weekly starting at beta week 2. If a T1 user with 500 followers generates 30 notifications/day in beta but the model predicts 50, the suppression factor is approximately 0.6. As follower counts grow, this ratio should trend toward 1.0. If it remains below 0.7 at week 8, E1 flags to the engineering lead that steady-state rates are likely to exceed beta rates by more than 30%, and the Phase 2 review is initiated early. This converts an undetectable risk into a monitored one.

#### Section 1.2a — The >51/Day Protocol

**Trigger:** Observed per-user notification rate exceeds 51/day (3× ceiling) during beta.

**Step 1 — False positive check (0–48 hours):** E1 and the engineering lead conduct a technical review. The review either (a) confirms the finding as representative, or (b) identifies a documented artifact explaining the spike as non-representative.

**The artifact problem:** In practice, almost any beta spike will have a plausible specific mechanism available — a viral content event, a measurement window artifact, a single high-follower post. The risk is not that engineers fail to find a mechanism; it is that they find one that is technically accurate but insufficient to explain the full magnitude of the spike. To address this:

- An artifact explanation must account for the full magnitude of the spike, not merely its existence. If the artifact explains a 1.5× spike and the observed rate is 3×, the remaining factor must be explained separately or the finding is confirmed.
- The artifact explanation must be written down with specific numbers: what the artifact contributed, what the residual unexplained rate is, and why the residual is within normal variance.
- If two engineers disagree on whether an artifact explanation is sufficient, the finding is confirmed. Disagreement resolves to confirmation, not to continued investigation.

**If the 48-hour window is missed:** The finding is automatically confirmed. There is no extended review period. The lead notifies the executive sponsor that the review did not complete and that the escalation protocol is activating on schedule.

**Step 2 — If confirmed:** The engineering lead notifies the executive sponsor within 24 hours with:
- Observed rate and measurement methodology
- Implied steady-state rate range (confirmed rate × 1.3–2.0 to account for graph densification)
- Specific infrastructure components requiring expansion before full launch
- Cost estimate (point estimate with ±30% range)
- Two options: (a) pause beta expansion and resize before proceeding, or (b) proceed at current scale with defined risk acceptance

**Step 3 — Executive sponsor decision:** The sponsor chooses between options within 48 hours of receiving the notification. If no decision is received, option (a) activates by default. The lead does not proceed with option (b) without explicit sponsor approval.

**Step 4 — If option (b) is chosen:** The lead documents the risk acceptance in writing, including the sponsor's name, date, and specific risk accepted. This document is retained for post-launch review.

#### Phased Procurement

**Phase 1 (weeks 3–8):** Provision at the 15/35/50 scenario ceiling, 60% capacity. Approximately 30 P1 workers, Redis cluster sized for 27/day at baseline DAU with full overhead accounting (see Section 3.2), RDS at ~2,000 writes/sec. Handles beta cohort up to 500K users.

**Phase 2 trigger (month-3 revisit):** After 8 weeks of live traffic data, E1 conducts a capacity review covering observed per-user rates, actual tier distribution, Redis memory utilization, and RDS write throughput. The review produces a specific provisioning recommendation for full launch scale. The engineering lead approves recommendations requiring more than 20% infrastructure change; the executive sponsor approves recommendations requiring budget increases above the approved range established at project start.

**Phase 2 provisioning targets (conditional on Phase 2 review findings):**
- If observed rates are within 25% of Phase 1 sizing: add read replica to RDS, increase worker count by 20%, no Redis expansion required
- If observed rates are 25–75% above Phase 1 sizing: add Redis node, double worker count, add RDS read replica
- If observed rates exceed Phase 1 sizing by more than 75%: treat as a Section 1.2a escalation even if the 51/day threshold was not crossed during beta — the Phase 2 review is the trigger

---

## Section 2: Priority and Batching Logic

### 2.1 Priority Tiers

| Priority | Description | Examples | Target Delivery | Batching |
|----------|-------------|----------|-----------------|---------|
| P0 | Security and auth | OTP, password reset, suspicious login | < 10 seconds | Never batched |
| P1 | Direct user actions | DMs, @mentions, direct