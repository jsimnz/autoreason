# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Reading Order

Read this document front to back. Section 1 establishes scale assumptions and spike definitions that all subsequent sections reference. Section 7 (staffing) is placed last because it references operational thresholds defined in earlier sections — not because it is less important. The staffing constraints in Section 7 were used to make every sizing and scope decision in Sections 1–6; the placement reflects reading order, not priority.

---

## Section 1: Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Scenario A — Viral post fanout:** A post by a high-follower user generates approximately 20× baseline instantaneous throughput lasting 90–120 seconds. Sharp peak, rapid natural decay.

**Scenario B — Live event or trending topic:** Sustained elevated activity at approximately 5× baseline lasting 10–30 minutes. Broad plateau rather than a sharp spike.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity analysis in 1.1a |
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
1. Record daily DAU/MAU for all available beta days.
2. Compute the standard deviation of the daily ratio.
3. Set revised threshold at: observed mean + (1.5 × standard deviation), rounded to the nearest 0.5%.
4. If the result falls below 31% or above 36%, flag to the engineering lead before applying — either extreme suggests measurement noise.

**If calibration fails** (standard deviation > 5%): The DAU/MAU ratio is too noisy to use as a trigger. Substitute an absolute threshold of 3.5M daily active users, five-consecutive-day rule. This figure is not derived from the failed calibration — it is the 35% DAU/MAU scenario from Section 1.1a, chosen as a conservative absolute equivalent. It is a pre-chosen fallback, not an adaptive output. The engineering lead should note this explicitly when communicating the switch.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. Completes within one week. E1 owns it; the engineering lead approves any recommendation requiring more than 20% infrastructure change.

### 1.2 The 17/Day Planning Ceiling

#### The Circularity Problem — Stated Directly

The 17/day ceiling is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. There is no prior product data; the benchmarks are from different products at different scales. The 1.7× headroom multiplier is applied to an already-uncertain number.

**Consequence:** Phase 1 sizing is anchored to the worst modeled scenario (the 15/35/50 tier split, producing a 27/day ceiling) at 60% capacity — not to 60% of the 17/day baseline. Phase 1 is not undersized at beta day one even if tier composition is heavily skewed toward power users. The 17/day figure is retained as a planning reference and decision gate input, not as a sizing anchor.

#### Why 60% Capacity

60% is the tradeoff point between two failure modes: provisioning too tight (no headroom for spikes, worker saturation under Scenario A or B) and provisioning too loose (wasted cost on a system with unvalidated traffic assumptions). At 60% of the 27/day worst-case ceiling, the system handles the full worst-case scenario with 40% headroom before any emergency scaling is required. 70% would reduce that headroom to 30% — acceptable but leaving less time to respond during a Scenario B event. 50% would add approximately $3–5K/month in infrastructure cost for headroom that is unlikely to be needed even under the worst modeled scenario. 60% is the point where emergency scaling time is adequate and cost is defensible. This is a judgment call, not a derived constant. If the executive sponsor prefers a different risk/cost tradeoff, 55% or 65% are reasonable alternatives.

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

#### Decision Gate

| Observed Rate | Action | Owner | Window |
|---------------|--------|-------|--------|
| ≤ 17/day | Proceed with Phase 1 provisioning as anchored to 15/35/50 scenario | E1 | — |
| 17–25/day | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day | Pause beta expansion; add Redis node; architectural review | E1 + Lead | 1 week |
| > 51/day | 48-hour technical review — see Section 1.2a | Lead + executive sponsor | 48 hours |

**Why the escalation threshold is 3× (51/day) rather than 5× (85/day):** In a sparse early-beta social graph, T1 users have fewer followers, so each post generates fewer downstream notifications than it will at steady state. Observed per-user rates during beta understate what the system will face when the social graph densifies. The magnitude of this suppression cannot be quantified before densification occurs. The 3× threshold reflects this asymmetry: a 3× reading in a sparse graph is more alarming than it would be in a mature network, because the steady-state rate is higher still by an unknown amount. The 3× figure is not derived from the suppression magnitude — which is unknown — but from the asymmetry of risk. Acting at 3× costs engineering time. Acting at 5× after the graph densifies may mean launching with undersized infrastructure. This is a judgment call; the honest alternative is to use 5× and accept that risk explicitly.

#### Section 1.2a — The >51/Day Protocol

**Trigger:** Observed per-user notification rate exceeds 51/day (3× ceiling) during beta.

**Step 1 — False positive check (0–48 hours):** E1 and the engineering lead conduct a technical review. The review either (a) confirms the finding as representative, or (b) identifies a specific documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains the spike as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. Default presumption favors confirming the finding.

**If the 48-hour window is missed:** The finding is automatically confirmed. There is no extended review period. The lead notifies the executive sponsor that the review did not complete and that the escalation protocol is activating on schedule.

**Step 2 — If confirmed:** The engineering lead notifies the executive sponsor within 24 hours with the following specific information:
- Observed rate and measurement methodology
- Implied steady-state rate range (confirmed rate × 1.3–2.0 to account for graph densification)
- Specific infrastructure components that require expansion before full launch
- Cost estimate for required expansion (point estimate with ±30% range)
- Two options: (a) pause beta expansion and resize before proceeding, or (b) proceed with beta at current scale with defined risk acceptance

**Step 3 — Executive sponsor decision:** The sponsor chooses between options (a) and (b) within 48 hours of receiving the notification. If no decision is received, option (a) activates by default. The lead does not proceed with option (b) without explicit sponsor approval.

**Step 4 — If option (b) is chosen:** The lead documents the risk acceptance in writing, including the sponsor's name, the date, and the specific risk accepted. This document is retained for post-launch review.

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
| P1 | Direct user actions | DMs, @mentions, direct replies | < 60 seconds | Never batched |
| P2 | Social engagement | Likes, reposts, follows | < 5 minutes | Batched — see 2.2 |
| P3 | Digests and recommendations | Weekly digest, content recommendations | Hours-scale | Batched — see 2.2 |

P0 and P1 notifications bypass the batching system entirely. They enter dedicated queues with dedicated workers. P0 uses SMS and push only. P1 uses push and in-app; email is not used for P1 due to delivery latency.

### 2.2 Batching Logic

**P2 batching window:** 5 minutes. Within a 5-minute window, multiple P2 notifications for the same user are collapsed into a single delivery. Collapse logic: if a user receives 3 or more P2 notifications within the window, deliver a summary ("3 people liked your post") rather than individual notifications. If fewer than 3, deliver individually.

**P3 batching window:** User-configurable within bounds of [1 hour, 24 hours]. Default is daily at a time chosen by the user during onboarding (default 9am local time if not chosen). P3 notifications are never delivered between 10pm and 7am local time regardless of user preference setting. This quiet hours rule is enforced at the dispatcher, not at the preference layer, so it cannot be disabled by user preference changes.

**Batching tradeoff:** Batching P2 notifications reduces push delivery volume by an estimated 40–60% during peak periods (multiple engagements on viral content). This reduces FCM/APNs costs and reduces notification fatigue. The cost is that individual P2 notifications may arrive up to 5 minutes late. For a social app, this is acceptable. For a platform where P2 latency matters (e.g., live auctions), it would not be.

### 2.3 Scenario A Queue Behavior — Reconciled with Thresholds

A Scenario A spike at 20× sustained peak (1,750/sec) produces approximately 35,000 notifications/sec instantaneously. This lasts 90–120 seconds. Total notifications generated during the spike: approximately 35,000 × 105 seconds = ~3.7M.

Of these, the split by priority is approximately:
- P1 (viral post replies and direct mentions): ~15% = ~555K items
- P2 (likes, reposts): ~80% = ~2.96M items
- P3 (recommendations triggered by trending): ~5% = ~185K items

**P1 queue behavior during Scenario A:**
- 30 P1 workers, each processing approximately 50 notifications/sec = 1,500/sec total drain rate
- P1 queue fill rate during spike: 35,000/sec × 15% = 5,250/sec
- Net queue growth rate during spike: 5,250 − 1,500 = 3,750 items/sec
- Spike duration: ~105 seconds
- Peak P1 queue depth at spike end: ~394K items
- Post-spike drain rate at 1,500/sec with no new arrivals: ~394K / 1,500 = ~263 seconds to drain

**Result:** P1 