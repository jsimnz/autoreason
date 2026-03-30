# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three architectural bets, stated with their actual limitations:

1. **Separate Redis instances per priority tier** — isolation is real only with separate infrastructure. Three queues on one instance is labeling, not isolation. Section 2 explains the cost and what it buys.

2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs, ElastiCache, RDS. Engineering time goes to integration quality, not plumbing.

3. **Phased procurement under acknowledged uncertainty** — the week-2 cohort checkpoint precedes infrastructure commitment. Procurement is phased, not committed upfront, because the validation cannot confirm the planning ceiling — only detect catastrophic overruns. Section 1.2 explains the hedge, its cost, and what it buys.

**Twelve honest statements before the detail:**

The 17/day planning ceiling is derived from a three-tier model with a 1.7× headroom multiplier. The derivation is in Section 1.2. The cohort validation cannot confirm this number. A measurement at or below 17/day means "no strong evidence of catastrophic error," not "confirmed." Procurement proceeds under acknowledged uncertainty, hedged by phased commitment.

The tier weights (5%/35%/60%) are unvalidatable before the infrastructure decisions that depend on them. The resolution is not better measurement — it is designing infrastructure to be re-sizable within the 6-month window. Section 1.2 specifies the re-sizing path, lead times, and decision criteria for the month-3 revisit.

Social graph sparsity means the week-2 cohort will structurally underestimate steady-state rates. The validation is most useful as an upper-bound alarm. A measurement above 17/day is a stronger signal than it appears, because it is elevated despite sparsity suppressing it.

The 30% DAU/MAU ratio is load-bearing and uncertain. A 35% ratio stresses Redis, RDS, and worker counts simultaneously — not independently. The trigger is a 7-day rolling average crossing 30% for three consecutive days, initiating a coordinated capacity review across all three components.

The 350/sec per-worker assumption was previously unjustified. Section 1.3 derives it from first principles and specifies a month-1 load test that validates or replaces it before any downstream sizing depends on it.

The viral spike model sizes for 5× sustained, not 10×. Section 1.3 provides complete quantitative analysis for both scenarios, including sensitivity to the per-worker assumption.

The interim operating mode (>5× case) contained an unacknowledged contradiction: 15-minute batch cycles with 42–58 minute drain times means multiple batches accumulate simultaneously. Section 1.2a now analyzes queue equilibrium under this overlap condition and states the conditions for stability.

The >5× validation failure triggers a 48-hour technical review, not a week-long confirmatory measurement. A week of delay at >5× overrun consumes the most valuable response time. The review either confirms the finding or identifies a specific documented artifact explaining it. General claims of noise are not valid artifacts.

Redis Lists with BRPOP give LIFO behavior under accumulation. For social notifications this is likely an accidental feature — the system preferentially delivers fresher content. Section 2.2 specifies the queue depth threshold above which LIFO behavior produces unacceptable P1 delivery latency and the mitigation.

Auth SMS is exempt from the budget cap and tracked on a separate counter with a hard ceiling and fraud detection trigger. The prior fallback — push notification when the budget cap is hit — does not work for auth: a user requesting an auth code typically has no active session to receive push.

The Scenario A alert (20× instantaneous, 90–120 seconds) is replaced with a non-paging observability record for single occurrences. A recurrence detector is added: two Scenario A events within 60 minutes triggers a page. A single event is already over before intervention is possible; a pattern is actionable.

The operational surface is at the edge of what 4 engineers can safely own. Section 7 names every cut, which engineer owns what, and the on-call structure. Every operational assumption in the other sections is grounded against this staffing reality.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — see Section 1.1a |
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
- P1 workers required: ~30 | Redis P1 queue memory at 2M-item spike ceiling: ~4GB
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario — compounded:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)
- 36 P1 workers at 350/sec: 12,600/sec capacity — headroom holds at 5× under the 350/sec assumption; see Section 1.3 for sensitivity
- Scenario B arrival rate at 10×: ~20,800/sec — drain time extends to ~29 minutes vs. ~24 minutes at baseline

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously. The 35% scenario does not break any single component, but creates a situation where Redis needs additional nodes *and* RDS needs read replica offloading *and* worker counts need adjustment — all at once. If a Scenario B spike occurs while running at 35% DAU/MAU, combined load on Redis (queue depth) and RDS (status writes) is approximately 40% above baseline planning figures.

**Trigger for action:** E1 monitors a 7-day rolling DAU/MAU average. If this average crosses 30% for three consecutive days, E1 initiates a coordinated capacity review covering Redis, RDS, and workers together — not sequentially. The review completes within one week. Three consecutive days distinguishes a trend from noise; a single day above 30% is plausibly a weekend effect. The specific threshold should be confirmed against observed day-of-week variance during beta.

**Decisions not sensitive to this ratio:** Queue architecture, channel selection logic, preference management design, failure handling. These are correct across the plausible range.

---

### 1.2 The 17/Day Ceiling: Derivation, Validation Limits, and the Procurement Hedge

#### Derivation

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count; significant fanout | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks; each post generates ~30–80 downstream notifications |
| T2 — Active consumers | Engages regularly (likes, comments, DMs), creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 2.5 + 4.2 + 3.0 = **9.7/day**

The 17/day planning ceiling applies a 1.7× headroom multiplier for three reasons:

1. **Social graph super-linear growth:** Notification volume scales with network density. A user with 100 followers generates more downstream notifications than 10 users each with 10 followers. Per-user rates increase as the network matures even if individual behavior does not change.
2. **Feature expansion:** New notification types are easier to add than to remove. Planning at the model estimate invites infrastructure surprises as the product surface grows.
3. **Model uncertainty:** Per-tier rates are benchmarks, not measurements. A 1.7× buffer is conservative but not extravagant given zero prior product data.

**Tier weight sensitivity:**

| Tier split | Weighted avg/day | 1.7× ceiling | P1 workers | Infrastructure implication |
|------------|-----------------|--------------|------------|---------------------------|
| 5/35/60 (baseline) | 9.7 | ~17 | ~30 | Baseline sizing |
| 10/35/55 | 12.2 | ~21 | ~37 | +25% workers |
| 15/35/50 (early adopter-skewed) | 15.0 | ~27 | ~49 | Different Redis sizing; material |

The 15/35/50 split is plausible for a product that has not yet reached mass market. At 27/day, total notifications/day rises to ~81M, sustained peak to ~2,840/sec. This is material and must be revisited at month 3.

#### What the Validation Can and Cannot Do

The week-2 cohort measurement will structurally underestimate steady-state rates due to social graph sparsity. A T1 power user in a 50K cohort might generate 20 downstream notifications per post; the same user in a mature 10M MAU network might generate 200. This is not a sampling bias problem — it is a network effect that makes early measurements structurally lower than steady-state rates.

Two opposing biases operate simultaneously: sparsity suppresses rates (especially for T1 users whose volume scales with follower count); early-adopter engagement inflation elevates rates (especially for T3 users whose baseline is low enough that selection effects dominate). The net direction is uncertain, with sparsity likely dominating for T1 and inflation likely dominating for T3. No correction fully accounts for both simultaneously.

The validation gate is therefore calibrated to act only on large deviations. The gate uses raw observed rates without tier reweighting, because the reweighting assumptions are themselves uncertain.

**The decision gate:**

| Observed Rate (raw, uncorrected) | Signal | Action | Owner | Window |
|----------------------------------|--------|--------|-------|--------|
| ≤ 17/day | No strong evidence of catastrophic error | Proceed with Phase 1 procurement | E1 | — |
| 17–34/day (≤ 2×) | Ceiling likely wrong | Increase worker counts in Phase 1; Redis sizing unchanged | E1 | 72 hours |
| 34–85/day (2–5×) | Ceiling significantly wrong | Delay Phase 1; add Redis nodes; revisit architecture | E1 + lead | 1 week |
| >85/day (>5×) | Ceiling fundamentally wrong | 48-hour technical review; see Section 1.2a | Engineering lead + executive sponsor | 48 hours |

**The >5× false positive protection:** Within 48 hours of a >5× measurement, E1 and the engineering lead conduct a technical review. The review either confirms the finding as representative, or identifies a specific documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains it as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. If no valid artifact is identified within 48 hours, the finding is confirmed and the Section 1.2a protocol activates.

#### The Procurement Hedge: Phased Commitment Under Acknowledged Uncertainty

The prior approach committed full infrastructure based on a number that cannot be confirmed. This revision replaces full upfront commitment with phased procurement.

**Phase 1 (weeks 3–8, immediately after validation gate):** Provision for 60% of baseline sizing — approximately 18 P1 workers, a single Redis cluster, and RDS at baseline write throughput. This handles up to ~30/day observed rates and covers the sparsity-adjusted expected range. It is fully operational for beta.

**What Phase 1 cannot handle:** A full Scenario B spike at 5× sustained. The mitigation is that Scenario B events — sustained 5× spikes from live events — are unlikely during a 50K-user beta. If one occurs, the queue accumulates and delivery latency increases; the system does not drop notifications, it delays them. Acceptable during beta; not acceptable at full launch.

**Phase 2 trigger (month 3 revisit):** After 8 weeks of live traffic data, provision the remaining 40% or more depending on month-3 findings. ElastiCache scaling and RDS read replicas are available within days; additional EC2 worker capacity within hours. The 6-week window between month 3 and month 4.5 is sufficient for managed service provisioning.

**What this costs:** Running at 60% capacity during beta. Approximately $8–15K/month less than full provisioning, depending on configuration. The option value of not over-committing based on unconfirmable estimates exceeds this cost.

#### Month-3 Tier Weight Revisit: Decision Criteria, Data, and Action Lead Times

**What data will be available at month 3:** Eight weeks of live traffic from a beta cohort expected to reach 200–500K users. At 200K+ users, social graph density is materially higher than the week-2 cohort, making T1 per-user rates more representative. Behavioral segmentation data will allow direct measurement of tier composition rather than assumption.

**Measurement methodology:** E1 runs a 7-day measurement window in weeks 9–10, capturing per-user notification rates segmented by behavioral tier using the definitions above. The weighted average is computed from observed data, not the benchmark-based model.

**Threshold triggers:**

| Month-3 Observed Rate | Finding | Action | Lead Time |
|-----------------------|---------|--------|-----------|
| ≤ 17/day | Baseline confirmed | Complete Phase 2 at baseline sizing | 2–3 weeks |
| 17–21/day | Moderate overrun | Complete Phase 2 at +25% worker count | 2–3 weeks |
| 21–27/day | Material overrun | Complete Phase 2 at +60% workers; add Redis node | 3–4 weeks |
| >27/day | Ceiling wrong at all tier splits | Immediate architecture review; executive escalation | Begin within 1 week |

**Decision owner:** E1 owns the measurement. The engineering lead approves any action requiring >20% infrastructure change. The executive sponsor is notified of any finding above 21/day.

**Is 3 months sufficient to act?** For findings up to the 15/35/50 scenario: yes — 3 months remaining provides sufficient lead time for managed service provisioning (days to weeks) and worker scaling (hours). For a >27/day finding: 3 months is sufficient for infrastructure changes, insufficient for architectural changes. A >27/day finding at month 3 means the system launches with known limitations, documented explicitly for the executive sponsor.

---

### 1.2a The >5× Case: Interim Operating Mode

#### Queue Equilibrium Under Overlapping Batch Releases

The prior version described a 15-minute batch cycle with 42–58 minute drain times without analyzing whether the queue reaches stable equilibrium or grows without bound. This section corrects that.

**The overlap condition:** With a 15-minute batch cycle and a 42–58 minute drain time, up to three or four batches are accumulating simultaneously before the first fin