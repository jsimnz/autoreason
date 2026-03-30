# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How This Document Is Organized

Section 7 (Staffing and Operational Surface) appears first because worker counts, queue thresholds, and ownership assignments throughout subsequent sections reference roles defined there. However, Section 7.3 references Scenario A and Scenario B spike types, which are defined in Section 1.1. Readers unfamiliar with those terms should read Section 1.1 before Section 7.3, then return to Section 7.

---

## Section 7: Staffing, Ownership, and Operational Surface

### 7.1 Team Composition and Role Assignments

This is a 4-engineer backend team with a 6-month delivery window. The engineering lead is one of the four engineers, not additional headcount. There is no dedicated SRE, DBA, or security engineer. All operational responsibilities are distributed among the four.

| Role | Designation | Primary Ownership | Secondary Coverage |
|------|-------------|-------------------|-------------------|
| Engineering Lead | Lead | Architecture decisions, vendor relationships, executive escalation | Covers E4 during absence |
| Backend Engineer 1 | E1 | Infrastructure provisioning, capacity monitoring, DAU/MAU tracking, load testing | Covers Lead on operational decisions |
| Backend Engineer 2 | E2 | Queue infrastructure (Redis), worker fleet, failure handling | Covers Lead on non-architecture decisions |
| Backend Engineer 3 | E3 | Channel integrations (FCM/APNs, SendGrid, Twilio), delivery tracking | Covers E1 |
| Backend Engineer 4 | E4 | User preference management, API layer, in-app notification store | Covers E3 |

**Coverage matrix rationale:** The prior version assigned E2 and E3 as mutual-only backups, meaning queue infrastructure and all channel integrations had no coverage if both were simultaneously unavailable. The revised matrix distributes secondary coverage so that E1 and E4 each provide backup into different critical components. No component is covered exclusively by a mutual pair. The Lead and E1 retain cross-coverage on operational decisions.

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
- Read replica configuration for RDS
- Additional Redis nodes beyond initial cluster
- SMS channel expansion beyond auth and P0 alerts

**Explicitly not cut:**
- On-call rotation (defined in 7.3)
- Failure handling and dead letter queue processing
- User preference API (required at launch)
- Auth SMS monitoring (required at launch; see Section 4)

### 7.3 On-Call Structure

**Rotation:** 2-person on-call at all times. Primary is paged first; secondary paged if primary does not acknowledge within 15 minutes. Rotation cycles weekly among all four engineers. The engineering lead is never the sole on-call but is always reachable for P0 escalations.

**On-call time budget — the honest accounting:**

A 4-engineer weekly rotation means each engineer carries primary or secondary on-call responsibility roughly every other week. The proposal elsewhere allocates 20% of each engineer's time to operational work. These two numbers are in direct tension during beta, when incident rates are highest.

The 20% figure is a steady-state target for a stable system, not a beta-period guarantee. The realistic expectation during weeks 3–12 is that on-call engineers will spend 30–40% of their time on operational work in active incident weeks. This is not a planning failure — it is the known cost of running a new system through beta with a small team.

**How the team absorbs this without collapsing delivery:**
- Non-on-call engineers carry development work during weeks when their on-call counterparts are incident-heavy. This requires explicit coordination in the weekly sync.
- If any engineer's operational load exceeds 40% for two consecutive weeks, the engineering lead escalates to the executive sponsor as a delivery risk, not as a staffing complaint.
- The 20% steady-state target is the trigger for that escalation conversation, not a cap the team is expected to honor at all costs during beta.

**This means some features slip during high-incident beta weeks.** That is the correct tradeoff for a 4-engineer team. The alternative — understaffing on-call to protect development velocity — produces worse outcomes.

**Page-worthy conditions** (Scenario A and B are defined in Section 1.1):
- P1 queue depth exceeds 500K items for more than 10 minutes
- Push delivery failure rate exceeds 5% over a 5-minute window
- Any single channel goes fully dark (zero deliveries) for more than 3 minutes
- Auth SMS failure rate exceeds 2% (lower threshold due to security implication)
- Two Scenario A events within 60 minutes
- DAU/MAU 7-day rolling average crosses the calibrated threshold for three consecutive days

**Non-paging conditions (recorded, reviewed in weekly sync):**
- Single Scenario A event resolving within 120 seconds
- P2/P3 queue depth spikes that self-resolve within 15 minutes
- Individual channel provider errors below the 5% threshold
- Redis memory usage crossing 70% (warning only — page at 85%)

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Scenario A and Scenario B are defined here because they are referenced in Section 7.3 and throughout the document.

**Scenario A:** Single viral post fanout. A post by a high-follower user generates a spike of approximately 20× baseline throughput lasting 90–120 seconds. Characterized by a sharp peak and rapid natural decay.

**Scenario B:** Live event or trending topic. Sustained elevated activity at approximately 5× baseline lasting 10–30 minutes. Characterized by a broad plateau rather than a sharp spike.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity analysis below |
| Notifications/user/day | ~17 | Planning ceiling — derivation and limitations in 1.2 |
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

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously under the 35% scenario. No single component breaks, but the system requires coordinated scaling across three components at once — the scenario most likely to create operational confusion under a 4-engineer constraint. The DAU/MAU trigger below is designed to catch this before it becomes simultaneous.

### 1.1b DAU/MAU Trigger — Calibration Timing Corrected

The prior version specified a calibration procedure requiring 14+ days of beta data "by week 3 of beta," with a fallback for fewer than 14 days. This was incoherent: if beta starts in week 3, there cannot be 14 days of beta data at week 3. The fallback was therefore the guaranteed condition, not a contingency.

**Revised approach:** The trigger threshold is set before beta begins, using pre-beta data where available and the conservative default otherwise. Calibration against live beta data happens at week 6, not week 3.

**Pre-beta threshold (used from beta start through week 6):** 33%, five-consecutive-day rule. This is not a fallback — it is the intended starting threshold. It errs toward missing a gradual trend rather than generating false alarms during the first weeks of a new system.

**Week-6 calibration (if 28+ days of beta data are available):**
1. Record daily DAU/MAU for all available beta days.
2. Compute the standard deviation of the daily ratio.
3. Set the revised threshold at: observed mean + (1.5 × standard deviation), rounded to the nearest 0.5%.
4. If this produces a threshold below 31% or above 36%, flag it to the engineering lead before applying — either extreme suggests measurement noise rather than a meaningful signal.

**If calibration fails** (standard deviation > 5%): The DAU/MAU metric is too noisy for this trigger. Replace with an absolute DAU count threshold of 3.5M daily active users, same five-consecutive-day rule.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. Completes within one week. E1 owns it; the engineering lead approves any recommendation requiring more than 20% infrastructure change.

### 1.2 The 17/Day Planning Ceiling

#### The Circularity Problem — Stated Directly

The 17/day ceiling is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. The 1.7× headroom multiplier is applied to a number that is already uncertain. This cannot be fixed by better derivation — there is no prior product data, and the benchmarks are from different products at different scales.

**Consequence:** Phase 1 sizing is anchored to the worst modeled scenario (the 15/35/50 tier split, producing a 27/day ceiling) at 60% capacity — not to 60% of the 17/day baseline. This means Phase 1 is not undersized at day one of beta even if tier composition is heavily skewed toward power users. The 17/day figure is retained as a planning reference and decision gate input, not as a sizing anchor.

**What this costs:** Provisioning at the 15/35/50 worst-case ceiling rather than the 5/35/60 baseline adds infrastructure. The honest cost range is $4–8K/month additional against a baseline managed services spend of $12–18K/month — meaning the conservative approach adds roughly 25–45% to monthly infrastructure cost during Phase 1. The wide ranges reflect genuine uncertainty in both the baseline (which depends on exact worker counts and Redis configuration finalized during provisioning) and the delta (which depends on how far the worst-case scenario exceeds actual observed load). These ranges cannot be narrowed further before beta data is available. The executive sponsor should be informed of this range and the reason it cannot be tightened.

#### Derivation (Retained as Reference)

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

#### The Sparsity Argument — Stated With Its Actual Limitations

In a sparse early-beta social graph, T1 users have fewer followers, so each post generates fewer downstream notifications. This suppresses observed per-user rates below steady-state rates. The implication is that beta measurements understate what the system will face at scale.

**What the suppression correction cannot do:** Because the magnitude of the suppression is unknown before the social graph densifies, the correction cannot be quantified. It cannot be applied as a multiplier to observed rates to produce a reliable steady-state estimate. Invoking it to justify specific threshold multiples — as the prior version did — adds false precision to a genuine uncertainty.

**What the suppression correction can do:** It changes the interpretation of threshold crossings. An observed rate that exceeds the 17/day ceiling despite sparse-graph suppression is more alarming than the same multiple would imply in a mature network, because the steady-state rate is higher still by an unknown amount. This asymmetry justifies setting thresholds conservatively (lower multiples trigger responses) and acting on above-ceiling readings rather than waiting for confirmation.

**The thresholds below are set conservatively for this reason. They are not derived from the suppression magnitude — which is unknown — but from the asymmetry of risk: acting too early costs some engineering time; acting too late risks a launch with undersized infrastructure.**

#### Decision Gate

| Observed Rate | Interpretation | Action | Owner | Window |
|---------------|----------------|--------|-------|--------|
| ≤ 17/day | Within ceiling; sparse suppression means steady-state may still be higher | Proceed with Phase 1 provisioning as anchored to 15/35/50 scenario | E1 | — |
| 17–25/day | Moderate overrun; warrants attention | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day | Significant overrun | Pause beta expansion; add Redis node; architectural review within 1 week | E1 + Lead | 1 week |
| >51/day | Ceiling wrong even before density correction | Escalation protocol — see Section 1.2a | Lead + executive sponsor | 48 hours |

#### Phased Procurement

**Phase 1 (weeks 3–8):** Provision at the 15/35/50 scenario ceiling, 60% capacity. Approximately 30 P1 workers, Redis cluster sized for 27/day at baseline DAU, RDS at ~2,000 writes/sec. Handles beta cohort up to 500K users.

**Phase 2 trigger (month-3 revisit):** After 8 weeks of live traffic data, provision the remainder based on observed rates. ElastiCache and RDS read replicas are available within days; EC2 worker capacity within hours. The 6-week window between month 3 and month 4.5 is sufficient for managed service provisioning; it is not sufficient for architectural changes.

**The tradeoff explicitly stated:** Running at 60% capacity means the system cannot absorb a full Scenario B spike during weeks 3–8. Delivery latency increases; notifications are not dropped. This is acceptable during a 50K-user beta. It would not be acceptable at full