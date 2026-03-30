# Notification System Design — Revised v2
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Reading Order

Read this document front to back. Section 1 establishes scale assumptions and spike definitions that all subsequent sections reference. Section 7 (staffing) is placed last because it references operational thresholds defined in earlier sections. The staffing constraints in Section 7 were used to make every sizing and scope decision in Sections 1–6.

---

## Section 1: Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Scenario A — Viral post fanout:** A post by a high-follower user generates approximately 20× baseline instantaneous throughput lasting 90–120 seconds. Sharp peak, rapid natural decay.

**Scenario B — Live event or trending topic:** Sustained elevated activity at approximately 5× baseline lasting 10–30 minutes. Broad plateau rather than a sharp spike.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity analysis in 1.1a |
| Notifications/user/day | ~17 | Planning reference only — limitations in 1.2 |
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

### 1.1b Infrastructure Monitoring Triggers

**Replacing the DAU/MAU trigger from the previous version.**

The prior version used a DAU/MAU ratio as the primary capacity trigger. That metric does not directly measure infrastructure stress. A product change that increases DAU without changing notification behavior — a new passive-consumption feature, for example — would have fired the trigger without any actual queue, worker, or throughput pressure. Direct infrastructure metrics are available and are more reliable signals. The DAU/MAU ratio is retained as a secondary context metric in the weekly engineering sync but is no longer a trigger for capacity review.

**Primary triggers — paging conditions (immediate response required):**

| Metric | Threshold | Why This Threshold |
|--------|-----------|-------------------|
| P1 queue depth | > 200K items sustained for 60 seconds | At 1,500/sec drain rate, 200K items implies ~133 seconds to drain — exceeding the 60-second P1 SLA. Sustained for 60 seconds distinguishes a spike from a trend. |
| P1 worker CPU | > 85% utilization across fleet for 90 seconds | Headroom for burst without false alarms on transient spikes |
| Redis memory utilization | > 80% of provisioned capacity | Provides time to add capacity before eviction risk |
| RDS write queue depth | > 500 pending writes | Upstream of write latency degradation |

**Secondary triggers — weekly sync review (no immediate action required):**

| Metric | Threshold | Action |
|--------|-----------|--------|
| 7-day rolling P1 p95 delivery latency | > 45 seconds | Review worker sizing; 45 seconds provides buffer before SLA breach |
| 7-day rolling notifications/user/day | > 21/day (25% above 17/day ceiling) | Review tier composition; may indicate unexpected T1 concentration |
| Redis memory utilization | > 65% for 7 consecutive days | Plan capacity addition; not urgent but trending toward primary trigger |

**Rationale for direct metrics over DAU/MAU:** Queue depth and worker utilization respond to actual load regardless of what caused it. DAU/MAU changes can be caused by factors entirely unrelated to notification throughput. For a 4-engineer team, false-positive capacity reviews consume disproportionate time. The triggers above will not fire unless the infrastructure is actually stressed.

### 1.2 The Planning Ceiling — Honest Statement of What It Is and Isn't

#### What the Previous Version Got Wrong

The previous version acknowledged that the 17/day figure was circular — tier weights cannot be validated before the infrastructure decisions that depend on them — and then used those same tier weights to anchor Phase 1 sizing. Disclosure of a circularity is not resolution of it. This version breaks the circularity by separating two decisions that were incorrectly merged: (1) what rate to use as a planning reference, and (2) what infrastructure to provision at launch.

These are now treated as separate decisions with different inputs.

#### The 17/Day Figure: What It Is

The 17/day figure is a planning reference derived from industry benchmarks for products at comparable scale. It is used to estimate order-of-magnitude infrastructure requirements during the design phase. It is not used as a sizing anchor. Phase 1 infrastructure is sized against directly observable beta traffic, not against this estimate. The decision gate in Section 1.2b defines how observed beta rates translate into provisioning decisions.

#### The 1.7× Headroom Multiplier — Justified

The previous version applied a 1.7× multiplier to the benchmark-derived average without explanation. Here is the explicit rationale:

The benchmarks used (Twitter/Instagram early-scale data) reflect products with mature social graphs and established usage patterns. This product launches with a sparse graph and an early-adopter user base. Two factors systematically cause benchmark rates to understate actual rates for a new product:

1. **Onboarding notifications:** New users receive a burst of system-initiated notifications (welcome sequences, friend suggestions, account verification reminders) that do not appear in steady-state benchmarks. Estimated contribution: +15–20% above steady-state rates during the first 60–90 days.

2. **Early-adopter engagement skew:** Beta cohorts are disproportionately T1 users (high-follower content creators) because they are recruited through existing social networks. T1 users generate and receive notifications at ~5× the T3 rate. A beta cohort that is 15% T1 rather than 5% T1 produces materially higher per-user rates than steady-state benchmarks suggest.

Combined, these factors justify a multiplier in the range of 1.5–2.0. The choice of 1.7 rather than 1.5 or 2.0 reflects a judgment that the onboarding effect is real but time-limited, and that early-adopter skew is significant but not extreme. 1.5 would underweight the early-adopter effect for a social product. 2.0 would overweight it and produce unnecessarily expensive Phase 1 provisioning. 1.7 is a midpoint with a specific rationale, not an arbitrary round number. This remains a judgment call; 1.6 or 1.8 would be defensible alternatives.

**The multiplier does not resolve the benchmark uncertainty.** It adjusts for two specific, named factors. Other sources of uncertainty remain, which is why Phase 1 provisioning is anchored to observed beta traffic rather than to this estimate.

#### Derivation

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks |
| T2 — Active consumers | Engages regularly, creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 9.7/day × 1.7× = **~17/day planning reference**

**Tier weight sensitivity:**

| Tier split | Weighted avg/day | 1.7× reference | Scenario implication |
|------------|-----------------|--------------|----------------------|
| 5/35/60 (baseline) | 9.7 | ~17 | Steady-state assumption |
| 10/35/55 | 12.2 | ~21 | Moderate early-adopter skew |
| 15/35/50 (early adopter-skewed) | 15.0 | ~27 | Heavy early-adopter skew; used as Phase 1 stress test |

The 15/35/50 scenario is used as a stress test to verify that Phase 1 infrastructure does not break under heavy early-adopter skew. It is not the sizing anchor. Phase 1 is sized from observed beta rates per Section 1.2b.

#### The 60% Capacity Framing — Corrected

The previous version stated that provisioning at 60% of the worst-case ceiling provides "40% headroom." That framing conflated a cost decision with a headroom decision. Here is the corrected framing:

Phase 1 provisioning is sized to handle 100% of the observed beta rate at launch, plus 40% buffer above that observed rate before emergency scaling is required. The 40% buffer is the headroom figure. The 60%/40% language referred to a fraction of a modeled ceiling that was itself uncertain — that framing is dropped.

**The actual cost/headroom tradeoff:** Increasing the buffer from 40% to 70% above observed beta rates adds approximately $3–5K/month in infrastructure cost and reduces the probability of needing emergency scaling during a Scenario B event from estimated 8% to estimated 3%. Decreasing the buffer to 20% saves approximately $1–2K/month and increases that probability to an estimated 18%. 40% is the selected tradeoff. These probability estimates are rough; they are included to make the tradeoff explicit, not to imply precision.

### 1.2b Observed Rate Decision Gate

**This gate uses observed beta traffic, not modeled estimates.**

Phase 1 provisioning is not set before beta. A minimal viable infrastructure (approximately 15 P1 workers, single Redis node, RDS at 1,000 writes/sec) handles the first 4 weeks of beta up to 100K users. After 4 weeks of beta traffic, E1 measures observed per-user notification rates and applies the following gate:

| Observed Rate (4-week beta average) | Phase 1 Provisioning Action | Owner | Window |
|--------------------------------------|-----------------------------|-------|--------|
| ≤ 17/day | Size to observed rate + 40% buffer | E1 | 1 week |
| 17–25/day | Size to observed rate + 40% buffer; flag T1 concentration for month-3 review | E1 | 1 week |
| 25–51/day | Size to observed rate + 40% buffer; add Redis node; architectural review before beta expansion | E1 + Lead | 2 weeks |
| > 51/day | Section 1.2c escalation protocol | Lead + executive sponsor | 48 hours |

**Why 51/day as the escalation threshold:** At 51/day, the implied steady-state rate after graph densification exceeds 66/day even under a conservative 30% densification uplift (see Section 1.2b, graph densification note). At that rate, the infrastructure assumptions underlying this design require fundamental revision, not incremental scaling. The 51/day figure is not a precise derivation; it is the point at which incremental responses become inadequate.

**Graph densification note:** Beta rates understate steady-state rates because the social graph is sparse during beta. Each post reaches fewer followers; each user has fewer connections generating inbound notifications. The magnitude of this suppression is unknown and cannot be measured before densification occurs. For the escalation threshold, this asymmetry is handled as follows: the threshold is set conservatively (51/day rather than a higher value) because a high beta-period reading in a sparse graph is more alarming than the same reading would be in a mature network. The specific value of 51/day is not derived from the suppression magnitude — which is unknown — but from the point at which incremental infrastructure responses become inadequate. This is a judgment call. The honest alternative is to use a higher threshold and accept that the system may be undersized at full launch; that risk should be explicitly documented if the threshold is raised.

### 1.2c The >51/Day Protocol

**Trigger:** Observed per-user notification rate exceeds 51/day during beta measurement period.

**Step 1 — False positive check (0–48 hours):** E1 and the engineering lead review the measurement. The review either (a) confirms the finding as representative, or (b) identifies a specific, documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains the rate as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. The default presumption favors confirming the finding. If the 48-hour window passes without a completed review, the finding is automatically confirmed.

**Step 2 — If confirmed:** The engineering lead notifies the executive sponsor and the designated backup decision-maker (see Step 3) within 24 hours with:
- Observed rate and measurement methodology
- Implied steady-state rate range (confirmed rate × 1.3–1.6 to account for graph densification; the range reflects that densification magnitude is unknown)
- Specific infrastructure components requiring expansion before full launch
- Cost estimate for required expansion (point estimate with ±30% range)
- Two options: (a) pause beta expansion and resize before proceeding; (b) proceed with beta at current scale with documented risk acceptance

**Step 3 — Decision authority and escalation path:** The executive sponsor holds primary decision authority. The designated backup decision-maker — identified by name at project kickoff, before this protocol is needed — holds authority if the sponsor is unreachable for more than 24 hours after notification. If neither is reachable within 48 hours of notification, option (a) activates by default. The engineering lead documents the activation, including the notification attempts made and their timestamps. The lead does not proceed with option (b) without explicit approval from the sponsor or designated backup.

**Why the backup decision-maker is named at kickoff:** The previous version had no escalation path for an unavailable sponsor. Default-to-pause protects infrastructure but silently halts beta expansion if the sponsor is simply slow to respond. Naming a backup at kickoff — before any urgency exists — eliminates this gap without creating ambiguity about who holds authority.

**Step 4 — If option (b) is chosen:** The approving party documents the risk acceptance in writing, including their name, the date, and the specific risk accepted. This document is retained for post-launch review.

### 1.2d Phase 2 Capacity Review

**Trigger:** 8 weeks after beta launch (not tied to the >51/day threshold).

E1 conducts a capacity review covering observed per-user rates, actual tier distribution, Redis memory utilization, and RDS write throughput. The review produces a specific provisioning recommendation for full launch scale.

**If Phase 2 review finds rates more than 75% above Phase 1 provisioning:** This triggers an architectural review and executive sponsor notification, using the same notification structure as Section 1.2c Step 2. This is distinct from the Section 1.2c protocol in one important respect: there is no single observation to evaluate for artifactual status, because Phase 2