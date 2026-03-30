# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Read This Document

This document is organized so that staffing constraints appear in Section 7, but those constraints drove every sizing and scope decision in Sections 1–6. Readers unfamiliar with the team structure should read Section 7 first, then return to Section 1. Scenario A and Scenario B spike types referenced throughout are defined in Section 1.1. The staffing section is placed last to avoid interrupting the technical narrative, not because it is less important.

---

## Section 7: Staffing, Ownership, and Operational Surface

### 7.1 Team Composition and Role Assignments

This is a 4-engineer backend team with a 6-month delivery window. The engineering lead is one of the four engineers, not additional headcount. There is no dedicated SRE, DBA, or security engineer. All operational responsibilities are distributed across the four.

| Role | Designation | Primary Ownership | Secondary Coverage |
|------|-------------|-------------------|-------------------|
| Engineering Lead | Lead | Architecture decisions, vendor relationships, executive escalation | Covers E4 during absence |
| Backend Engineer 1 | E1 | Infrastructure provisioning, capacity monitoring, DAU/MAU tracking, load testing | Covers Lead on operational decisions |
| Backend Engineer 2 | E2 | Queue infrastructure (Redis), worker fleet, failure handling | Covers Lead on non-architecture decisions |
| Backend Engineer 3 | E3 | Channel integrations (FCM/APNs, SendGrid, Twilio), delivery tracking | Covers E1 |
| Backend Engineer 4 | E4 | User preference management, API layer, in-app notification store | Covers E3 |

**Coverage matrix rationale:** E2 and E3 are not mutual-only backups. The matrix distributes secondary coverage so that no component is owned exclusively by a mutual pair. E1 and E4 each provide backup into different critical components, and the Lead and E1 retain cross-coverage on operational decisions.

### 7.2 What Is Cut from the Operational Surface

A 4-engineer team cannot maintain everything. The following are explicitly out of scope for the 6-month window.

**Cut entirely:**
- Custom push notification infrastructure. FCM and APNs are used as managed services.
- Custom email deliverability optimization. SendGrid handles deliverability; the team does not manage IP warming, DKIM/DMARC tuning beyond initial setup, or inbox placement analytics.
- Real-time analytics dashboards beyond operational metrics. Business intelligence on notification engagement is deferred.
- Multi-region redundancy. Single AWS region with managed service failover only.
- A/B testing infrastructure for notification content.
- Notification scheduling UI for content teams. API-only interface for the 6-month window.

**Deferred to month 4+ (conditional on beta findings):**
- Read replica configuration for RDS.
- Additional Redis nodes beyond initial cluster.
- SMS channel expansion beyond auth and P0 alerts.

**Explicitly not cut:**
- On-call rotation (defined in 7.3).
- Failure handling and dead letter queue processing.
- User preference API (required at launch).
- Auth SMS monitoring (required at launch; see Section 4).

### 7.3 On-Call Structure

**Rotation:** 2-person on-call at all times. Primary is paged first; secondary is paged if primary does not acknowledge within 15 minutes. Rotation cycles weekly among all four engineers. The engineering lead is never the sole on-call but is always reachable for P0 escalations.

**On-call time budget — the honest accounting:**

A 4-engineer weekly rotation means each engineer carries primary or secondary on-call responsibility roughly every other week. The steady-state target is approximately 20% of each engineer's time allocated to operational work. These two numbers are in direct tension during beta, when incident rates are highest.

The 20% figure is a steady-state target for a stable system, not a beta-period guarantee. The realistic expectation during weeks 3–12 is that on-call engineers will spend 30–40% of their time on operational work in active incident weeks. This is not a planning failure — it is the known cost of running a new system through beta with a small team.

**How the team absorbs this without collapsing delivery:**
- Non-on-call engineers carry development work during weeks when their on-call counterparts are incident-heavy. This requires explicit coordination in the weekly sync.
- If any engineer's operational load exceeds 40% for two consecutive weeks, the engineering lead escalates to the executive sponsor as a delivery risk, not as a staffing complaint.
- The 20% steady-state target is the trigger for that escalation conversation, not a cap the team is expected to honor at all costs during beta.
- Some features will slip during high-incident beta weeks. That is the correct tradeoff for a 4-engineer team. The alternative — understaffing on-call to protect development velocity — produces worse outcomes.

**Page-worthy conditions** (Scenario A and B defined in Section 1.1):
- P1 queue depth exceeds 500K items for more than 10 minutes.
- Push delivery failure rate exceeds 5% over a 5-minute window.
- Any single channel goes fully dark (zero deliveries) for more than 3 minutes.
- Auth SMS failure rate exceeds 2% (lower threshold due to security implication).
- Two Scenario A events within 60 minutes.
- DAU/MAU 7-day rolling average crosses the calibrated threshold for three consecutive days.

**Non-paging conditions (recorded, reviewed in weekly sync):**
- Single Scenario A event resolving within 120 seconds.
- P2/P3 queue depth spikes that self-resolve within 15 minutes.
- Individual channel provider errors below the 5% threshold.
- Redis memory usage crossing 70% (warning only; page at 85%).

The distinction between page-worthy and sync-review conditions is a deliberate operational choice. Paging on self-resolving Scenario A events would produce alert fatigue within weeks, training the team to dismiss pages. The thresholds above are calibrated so that a page represents something that requires human intervention within minutes, not something that the system will handle on its own.

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
| Scenario A instantaneous | 20× baseline, 90–120 sec | Single viral post fanout |
| Scenario B sustained | 5× baseline, 10–30 min | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### 1.1a DAU/MAU Sensitivity

**Baseline (30%):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory at 2M item spike ceiling: ~4GB (raw payload; Section 3.2 accounts for overhead)
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously under the 35% scenario. No single component breaks, but the system requires coordinated scaling across three components at once — the scenario most likely to create operational confusion under a 4-engineer constraint. The DAU/MAU trigger in Section 1.1b is designed to catch this before the components require simultaneous intervention.

### 1.1b DAU/MAU Trigger — Calibration

**Purpose:** This trigger initiates a coordinated capacity review. It is not a paging condition. It belongs in the weekly engineering sync, not the on-call runbook. See Section 7.3 for the distinction.

**Pre-beta threshold (beta start through week 6):** DAU/MAU 7-day rolling average exceeds 33% for five consecutive days. This is the intended starting threshold, not a fallback. It errs toward missing a gradual trend rather than generating false alarms during the first weeks of a new system.

**Week-6 calibration (requires 28+ days of beta data):**
1. Record daily DAU/MAU for all available beta days.
2. Compute the standard deviation of the daily ratio.
3. Set the revised threshold at: observed mean + (1.5 × standard deviation), rounded to the nearest 0.5%.
4. If the result falls below 31% or above 36%, flag to the engineering lead before applying — either extreme suggests measurement noise rather than a meaningful signal.

**If calibration fails** (standard deviation > 5%): The DAU/MAU ratio is too noisy to use as a trigger. Substitute an absolute threshold of 3.5M daily active users, five-consecutive-day rule. This figure is not derived from the failed calibration — it is the 35% DAU/MAU scenario from Section 1.1a, chosen as a conservative absolute equivalent. It is a pre-chosen fallback, not an adaptive output. The engineering lead should note this explicitly when communicating the switch.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. Completes within one week. E1 owns it; the engineering lead approves any recommendation requiring more than 20% infrastructure change.

### 1.2 The 17/Day Planning Ceiling

#### The Circularity Problem — Stated Directly

The 17/day ceiling is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. The 1.7× headroom multiplier is applied to a number that is already uncertain. This cannot be fixed by better derivation — there is no prior product data, and the benchmarks are from different products at different scales.

**Consequence:** Phase 1 sizing is anchored to the worst modeled scenario (the 15/35/50 tier split, producing a 27/day ceiling) at 60% capacity — not to 60% of the 17/day baseline. Phase 1 is not undersized at beta day one even if tier composition is heavily skewed toward power users. The 17/day figure is retained as a planning reference and decision gate input, not as a sizing anchor.

**What this costs:** Provisioning at the 15/35/50 worst-case ceiling rather than the 5/35/60 baseline adds approximately $4–8K/month against a baseline managed-services spend of $12–18K/month — roughly 25–45% additional monthly infrastructure cost during Phase 1. The ranges are wide because both the baseline (which depends on exact worker counts and Redis configuration) and the delta (which depends on how far the worst case exceeds actual load) cannot be narrowed before beta data is available. The executive sponsor should be informed of this range and the reason it cannot be tightened.

#### Why 60% Capacity

60% is the tradeoff point between two failure modes: provisioning too tight (no headroom for spikes, worker saturation under Scenario A or B) and provisioning too loose (wasted cost on a system with unvalidated traffic assumptions). At 60% of the 27/day worst-case ceiling, the system handles the full worst-case scenario with 40% headroom before emergency scaling is required. 70% would reduce that headroom to 30% — acceptable but leaving less time to respond during a Scenario B event. 50% would add approximately $3–5K/month for headroom that is unlikely to be needed even under the worst modeled scenario. 60% is the point where emergency scaling time is adequate and cost is defensible. This is a judgment call. If the executive sponsor prefers a different risk/cost tradeoff, 55% or 65% are reasonable alternatives.

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

#### The Sparsity Argument — Stated With Its Limitations

In a sparse early-beta social graph, T1 users have fewer followers, so each post generates fewer downstream notifications than it will at steady state. Beta measurements therefore understate what the system will face when the graph densifies.

**What the sparsity correction cannot do:** Because the magnitude of suppression is unknown before densification, it cannot be quantified or applied as a multiplier to produce a reliable steady-state estimate. Invoking it to justify specific threshold multiples adds false precision to a genuine uncertainty.

**What it can do:** It changes the interpretation of threshold crossings. An observed rate that exceeds the 17/day ceiling despite sparse-graph suppression is more alarming than the same multiple would imply in a mature network, because the steady-state rate is higher still by an unknown amount. This asymmetry justifies setting thresholds conservatively. The thresholds below are set for this reason — not derived from the suppression magnitude, but from the asymmetry of risk: acting too early costs engineering time; acting too late risks launching with undersized infrastructure.

#### Decision Gate

| Observed Rate | Sparsity-Adjusted Interpretation | Action | Owner | Window |
|---------------|----------------------------------|--------|-------|--------|
| ≤ 17/day | No strong evidence of error; sparse suppression means steady-state could still be higher | Proceed with Phase 1 provisioning anchored to 15/35/50 scenario | E1 | — |
| 17–25/day | Moderate overrun; steady-state likely 25–40/day | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day | Significant overrun; steady-state likely 40–80/day | Pause beta expansion; add Redis node; architectural review | E1 + Lead | 1 week |
| > 51/day | Ceiling wrong even before density correction | 48-hour technical review — see Section 1.2a | Lead + executive sponsor | 48 hours |

The 3× threshold (rather than 5×) reflects the sparsity correction: a 3× sparse-graph reading implies a steady-state rate that already exceeds the worst modeled scenario before any density adjustment is applied. Acting at 5× after the graph densifies may mean launching with infrastructure sized for