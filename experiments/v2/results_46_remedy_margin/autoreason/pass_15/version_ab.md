# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Reading Order

Read this document front to back. Section 1 establishes scale assumptions and spike definitions that all subsequent sections reference. Section 7 (staffing) is placed last because it references operational thresholds defined in earlier sections — not because it is less important. The staffing constraints in Section 7 drove every sizing and scope decision in Sections 1–6; placement reflects reading order, not priority.

---

## Section 1: Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Scenario A — Viral post fanout:** A post by a high-follower user generates approximately 20× baseline instantaneous throughput lasting 90–120 seconds. Sharp peak, rapid natural decay.

**Scenario B — Live event or trending topic:** Sustained elevated activity at approximately 5× baseline lasting 10–30 minutes. Broad plateau rather than a sharp spike.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity analysis in 1.1a |
| Notifications/user/day | ~17 | Planning reference only — derivation and limitations in 1.2 |
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

The prior version of this document used a DAU/MAU ratio as the primary capacity trigger. That metric does not directly measure infrastructure stress. A product change that increases DAU without changing notification behavior — a new passive-consumption feature, for example — would fire the trigger without any actual queue, worker, or throughput pressure. Direct infrastructure metrics are available and more reliable. The DAU/MAU ratio is retained as a secondary context metric in the weekly engineering sync but is no longer a primary trigger for capacity review.

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
| 7-day rolling notifications/user/day | > 21/day (25% above 17/day reference) | Review tier composition; may indicate unexpected T1 concentration |
| Redis memory utilization | > 65% for 7 consecutive days | Plan capacity addition; not urgent but trending toward primary trigger |
| DAU/MAU 7-day rolling average | > 33% for 5 consecutive days | Context signal; initiate coordinated capacity review if primary triggers are also elevated |

**Rationale for direct metrics over DAU/MAU as primary trigger:** Queue depth and worker utilization respond to actual load regardless of what caused it. For a 4-engineer team, false-positive capacity reviews consume disproportionate time. The primary triggers above will not fire unless the infrastructure is actually stressed.

---

### 1.2 The 17/Day Planning Reference — Honest Statement of What It Is and Isn't

#### The Circularity Problem — Stated Directly

The 17/day figure is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. There is no prior product data; the benchmarks are from different products at different scales. The 1.7× headroom multiplier is applied to an already-uncertain number.

**Consequence:** These two decisions must be kept separate: (1) what rate to use as a planning reference, and (2) what infrastructure to provision at launch. They have different inputs. Phase 1 infrastructure is anchored to the worst-case modeled scenario — the 15/35/50 tier split — and then calibrated against observed beta traffic before full provisioning is committed. The 17/day figure is a planning reference, not a sizing anchor.

#### The 1.7× Multiplier — Justified

The benchmarks used (Twitter/Instagram early-scale data) reflect products with mature social graphs and established usage patterns. Two factors systematically cause benchmark rates to understate actual rates for a new product:

1. **Onboarding notifications:** New users receive a burst of system-initiated notifications (welcome sequences, friend suggestions, account verification reminders) that do not appear in steady-state benchmarks. Estimated contribution: +15–20% above steady-state rates during the first 60–90 days.

2. **Early-adopter engagement skew:** Beta cohorts are disproportionately T1 users because they are recruited through existing social networks. T1 users generate and receive notifications at ~5× the T3 rate. A beta cohort that is 15% T1 rather than 5% T1 produces materially higher per-user rates than steady-state benchmarks suggest.

Combined, these factors justify a multiplier in the range of 1.5–2.0. The choice of 1.7 reflects a judgment that the onboarding effect is real but time-limited, and that early-adopter skew is significant but not extreme. 1.5 would underweight the early-adopter effect for a social product. 2.0 would overweight it and produce unnecessarily expensive Phase 1 provisioning. 1.6 or 1.8 would be defensible alternatives. **The multiplier does not resolve the benchmark uncertainty** — it adjusts for two specific, named factors. Other sources of uncertainty remain, which is why Phase 1 provisioning is calibrated to observed beta traffic before being finalized.

#### Derivation

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks |
| T2 — Active consumers | Engages regularly, creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 9.7/day × 1.7× = **~17/day planning reference**

**Tier weight sensitivity:**

| Tier split | Weighted avg/day | 1.7× reference | P1 workers | Infrastructure implication |
|------------|-----------------|----------------|------------|---------------------------|
| 5/35/60 (baseline) | 9.7 | ~17 | ~30 | Baseline |
| 10/35/55 | 12.2 | ~21 | ~37 | +25% workers |
| 15/35/50 (early adopter-skewed) | 15.0 | ~27 | ~49 | **Phase 1 sizing anchor** |

The 15/35/50 scenario is used as the Phase 1 sizing anchor and stress test. It is not a prediction. Phase 1 is provisioned to handle this scenario at 60% capacity, then calibrated against observed beta rates per Section 1.2b.

#### The 60% Capacity Framing — Corrected

Phase 1 provisioning is sized to handle 100% of the 15/35/50 worst-case scenario, plus 40% buffer above that level before emergency scaling is required. The 40% buffer is the headroom figure.

**The actual cost/headroom tradeoff:** Increasing the buffer from 40% to 70% adds approximately $3–5K/month in infrastructure cost and reduces the probability of needing emergency scaling during a Scenario B event from an estimated 8% to an estimated 3%. Decreasing the buffer to 20% saves approximately $1–2K/month and increases that probability to an estimated 18%. These probability estimates are rough; they are included to make the tradeoff explicit, not to imply precision. 40% is the selected tradeoff. If the executive sponsor prefers a different risk/cost balance, 35% or 45% are reasonable alternatives.

### 1.2b Observed Rate Decision Gate

**This gate uses observed beta traffic, not modeled estimates.**

A minimal viable infrastructure (approximately 15 P1 workers, single Redis node, RDS at 1,000 writes/sec) handles the first 4 weeks of beta up to 100K users. After 4 weeks of beta traffic, E1 measures observed per-user notification rates and applies the following gate:

| Observed Rate (4-week beta average) | Phase 1 Provisioning Action | Owner | Window |
|--------------------------------------|-----------------------------|-------|--------|
| ≤ 17/day | Size to observed rate + 40% buffer | E1 | 1 week |
| 17–25/day | Size to observed rate + 40% buffer; flag T1 concentration for month-3 review | E1 | 1 week |
| 25–51/day | Pause beta expansion; add Redis node; architectural review before proceeding | E1 + Lead | 2 weeks |
| > 51/day | Section 1.2c escalation protocol | Lead + executive sponsor | 48 hours |

**Why 51/day as the escalation threshold:** In a sparse early-beta social graph, each post reaches fewer followers, so observed per-user rates understate what the system will face when the graph densifies. The magnitude of this suppression cannot be quantified before densification occurs. At 51/day (3× the 17/day reference), the implied steady-state rate after graph densification exceeds 66/day even under a conservative 30% densification uplift. At that level, the infrastructure assumptions underlying this design require fundamental revision, not incremental scaling. Acting at 3× costs engineering time. Acting at 5× after graph densification may mean launching with undersized infrastructure. This is a judgment call; the honest alternative is to use a higher threshold and explicitly document the accepted risk.

**Graph densification note:** Beta rates understate steady-state rates because the social graph is sparse during beta. The threshold is set conservatively because a high beta-period reading in a sparse graph is more alarming than the same reading in a mature network. The specific value of 51/day is not derived from the suppression magnitude — which is unknown — but from the point at which incremental infrastructure responses become inadequate.

### 1.2c The >51/Day Protocol

**Trigger:** Observed per-user notification rate exceeds 51/day during the beta measurement period.

**Step 1 — False positive check (0–48 hours):** E1 and the engineering lead review the measurement. The review either (a) confirms the finding as representative, or (b) identifies a specific, documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains the rate as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. The default presumption favors confirming the finding. If the 48-hour window passes without a completed review, the finding is automatically confirmed and the escalation protocol activates on schedule. There is no extended review period.

**Step 2 — If confirmed:** The engineering lead notifies the executive sponsor and the designated backup decision-maker within 24 hours with:
- Observed rate and measurement methodology
- Implied steady-state rate range (confirmed rate × 1.3–1.6 to account for graph densification; the range reflects that densification magnitude is unknown)
- Specific infrastructure components requiring expansion before full launch
- Cost estimate for required expansion (point estimate with ±30% range)
- Two options: (a) pause beta expansion and resize before proceeding; (b) proceed with beta at current scale with documented risk acceptance

**Step 3 — Decision authority and escalation path:** The executive sponsor holds primary decision authority. The designated backup decision-maker — identified by name at project kickoff, before this protocol is needed — holds authority if the sponsor is unreachable for more than 24 hours after notification. If neither is reachable within 48 hours of notification, option (a) activates by default. The engineering lead documents the activation, including notification attempts made and their timestamps. The lead does not proceed with option (b) without explicit approval from the sponsor or designated backup.

**Why the backup decision-maker is named at kickoff:** Naming a backup before any urgency exists eliminates ambiguity about who holds authority without creating a default-to-pause that silently halts beta expansion if the sponsor is simply slow to respond.

**Step 4 — If option (b) is chosen:** The approving party documents the risk acceptance in writing, including their name, the date, and the specific risk accepted. This document is retained for post-launch review.

### 1.2d Phase 2 Capacity Review

**Trigger:** 8 weeks after beta launch — not tied to the >51/day threshold.

E1 conducts a capacity review covering observed per-user rates, actual tier distribution, Redis memory utilization, and RDS write throughput. The review produces a specific provisioning recommendation for full launch scale. The engineering lead approves recommendations requiring more than 20% infrastructure change; the executive sponsor approves recommendations requiring budget increases above the range established at project start.

**Phase 2 provisioning targets (conditional on review findings):**

| Observed vs. Phase 1 Sizing | Action |
|-----------------------------|--------|
| Within 25% | Add RDS read replica; increase worker count by 20%; no Redis expansion required |
| 25–75% above | Add Redis node; double worker count; add RDS read replica |
| More than 75% above | Treat as Section 1.2c escalation even if the 51/day threshold was not crossed during beta — the Phase 2 review is the trigger |

---

## Section 2: Priority and Batching Logic

### 2.1 Priority Tiers

| Priority | Description | Examples | Target Delivery | Batching |
|----------|-------------|----------|-----------------|---------|
| P0 | Security and auth | OTP, password reset, suspicious login | < 10 seconds | Never batched |
| P1 | Direct user actions | DMs, @mentions, direct replies | < 60 seconds | Never batched |
| P2 | Social engagement | Likes, reposts, follows | < 5 