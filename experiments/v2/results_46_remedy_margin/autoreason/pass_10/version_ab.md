# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How This Document Is Organized

Section 7 (Staffing and Operational Surface) appears first because every sizing assumption, ownership assignment, and operational threshold in subsequent sections is grounded against the actual team. References to E1–E4 and "the engineering lead" throughout refer to roles defined there.

---

## Section 7: Staffing, Ownership, and Operational Surface

### 7.1 Team Composition and Role Assignments

This is a 4-engineer backend team with a 6-month delivery window. The engineering lead is one of the four engineers, not additional headcount. There is no dedicated SRE, DBA, or security engineer. All operational responsibilities are distributed among the four.

| Role | Designation | Primary Ownership | Secondary Coverage |
|------|-------------|-------------------|-------------------|
| Engineering Lead | Lead | Architecture decisions, vendor relationships, executive escalation | Covers E1 during absence |
| Backend Engineer 1 | E1 | Infrastructure provisioning, capacity monitoring, DAU/MAU tracking, load testing | Covers Lead on operational decisions |
| Backend Engineer 2 | E2 | Queue infrastructure (Redis), worker fleet, failure handling | Covers E3 |
| Backend Engineer 3 | E3 | Channel integrations (FCM/APNs, SendGrid, Twilio), delivery tracking | Covers E2 |
| Backend Engineer 4 | E4 | User preference management, API layer, in-app notification store | Covers Lead on non-architecture decisions |

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

**Page-worthy conditions:**
- P1 queue depth exceeds 500K items for more than 10 minutes
- Push delivery failure rate exceeds 5% over a 5-minute window
- Any single channel goes fully dark (zero deliveries) for more than 3 minutes
- Auth SMS failure rate exceeds 2% (lower threshold due to security implication)
- Two Scenario A events within 60 minutes (recurrence detector — see Section 2)
- DAU/MAU 7-day rolling average crosses the calibrated threshold for three consecutive days

**Non-paging conditions (recorded, reviewed in weekly sync):**
- Single Scenario A event resolving within 120 seconds
- P2/P3 queue depth spikes that self-resolve within 15 minutes
- Individual channel provider errors below the 5% threshold
- Redis memory usage crossing 70% (warning only — page at 85%)

**Engineering time budget for operations:** Each engineer allocates approximately 20% of time to operational work. If operational work consistently exceeds 20% for any engineer, the engineering lead escalates to the executive sponsor as a delivery risk.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

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

### 1.1b DAU/MAU Trigger — Calibrated, Not Assumed

E1 runs a calibration pass in weeks 1–3 of beta using the following procedure:

1. Record daily DAU/MAU for all available beta days.
2. Compute the standard deviation of the daily ratio.
3. Set the trigger threshold at: 30% + (1.5 × observed standard deviation), rounded to the nearest 0.5%.
4. If the 7-day rolling average crosses this threshold for three consecutive days, trigger the coordinated capacity review.

**Fallback if fewer than 14 days of beta data by week 3:** Use a threshold of 33% with a five-consecutive-day rule. This errs toward missing a gradual trend rather than generating false alarms during an instrumentation-sparse period.

**If calibration fails** (standard deviation > 5%), E1 reports this to the engineering lead as a signal that the DAU/MAU metric is too noisy for this trigger, and the trigger is replaced with an absolute DAU count threshold.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. Completes within one week. E1 owns it; the engineering lead approves any recommendation requiring >20% infrastructure change.

### 1.2 The 17/Day Planning Ceiling

#### The Circularity Problem — Stated Directly

The 17/day ceiling is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. The 1.7× headroom multiplier is applied to a number that is already uncertain. This cannot be fixed by better derivation — there is no prior product data, and the benchmarks are from different products at different scales.

**Consequence:** Phase 1 sizing is anchored to the worst modeled scenario (the 15/35/50 tier split, producing a 27/day ceiling) at 60% capacity — not to 60% of the 17/day baseline. This means Phase 1 is not undersized at day one of beta even if tier composition is heavily skewed toward power users. The 17/day figure is retained as a planning reference and decision gate input, not as a sizing anchor.

**What this costs:** Approximately 65% more in Phase 1 infrastructure spend than anchoring to the 17/day baseline would produce — roughly $5–10K/month additional at the $8–15K/month managed services range. This is the direct cost of treating the circularity problem honestly.

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

#### The Sparsity Argument Applied Symmetrically

Sparsity suppresses T1 notification counts in early cohorts — fewer followers means fewer downstream notifications per post. This has two implications:

1. A reading at or below 17/day does not confirm the ceiling; it means no strong evidence of catastrophic error.
2. A reading above the ceiling despite sparsity suppression is a stronger alarm than the same multiple would imply in a dense graph. The steady-state rate is the sparse-graph reading *plus* a suppression correction whose magnitude is unknown. Above-ceiling readings therefore trigger responses at lower multiples than would apply in a mature network.

#### Decision Gate — Sparsity-Adjusted

| Observed Rate | Sparsity-Corrected Interpretation | Action | Owner | Window |
|---------------|----------------------------------|--------|-------|--------|
| ≤ 17/day | No strong evidence of error; sparse suppression means steady-state could still be higher | Proceed with Phase 1 provisioning as anchored to 15/35/50 scenario | E1 | — |
| 17–25/day (~1.5×) | Moderate overrun; steady-state likely 25–40/day | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day (1.5–3×) | Significant overrun; steady-state likely 40–80/day | Pause beta expansion; add Redis node; architectural review within 1 week | E1 + Lead | 1 week |
| >51/day (>3×) | Ceiling wrong even before density correction | 48-hour technical review — see Section 1.2a | Lead + executive sponsor | 48 hours |

The prior 5× threshold for the highest tier is replaced with 3× because the sparsity correction means a 3× sparse-graph reading implies a steady-state rate that exceeds the worst modeled scenario.

#### The >3× False Positive Protocol

Within 48 hours of a >3× measurement, E1 and the engineering lead conduct a technical review. The review either (a) confirms the finding as representative, or (b) identifies a specific documented artifact — a single viral event during the measurement window, a measurement script error, an anomalous content event — that explains the spike as non-representative. A valid artifact requires a specific mechanism, not a general claim of noise. Default presumption favors confirming the finding. If no valid artifact is identified within 48 hours, the finding is confirmed and the Section 1.2a escalation protocol activates.

#### Phased Procurement

**Phase 1 (weeks 3–8):** Provision at the 15/35/50 scenario ceiling, 60% capacity. Approximately 30 P1 workers, Redis cluster sized for 27/day at baseline DAU, RDS at ~2,000 writes/sec. Handles beta cohort up to 500K users.

**Phase 2 trigger (month-3 revisit):** After 8 weeks of live traffic data, provision the remainder based on observed rates. ElastiCache and RDS read replicas are available within days; EC2 worker capacity within hours. The 6-week window between month 3 and month 4.5 is sufficient for managed service provisioning; it is not sufficient for architectural changes.

**The tradeoff explicitly stated:** Running at 60% capacity means the system cannot absorb a full Scenario B spike during weeks 3–8. Delivery latency increases; notifications are not dropped. This is acceptable during a 50K-user beta. It would not be acceptable at full launch.

### 1.2a Queue Equilibrium Under the >3× Case

#### The Overlap Problem — Resolved

With a 15-minute batch cycle and 42–58 minute drain times, multiple batches accumulate simultaneously before the first finishes draining. The prior version did not analyze whether the queue reaches stable equilibrium or grows without bound. This section completes that analysis.

**Parameters:**
- Post-suppression arrival rate (A): ~875–1,050/sec
- Controlled release rate (R): 1,500/sec
- Batch accumulation period (B): 900 seconds
- Items accumulated per batch: A × B = ~787K–945K items

**Net drain rate:** R − A = 450–625/sec

**Time to drain one batch:** 787K / 625 to 945K / 450 = ~21–35 minutes

Since drain time (21–35 min) exceeds batch cycle (15 min), 1–2 additional batches accumulate while the first drains.

**Maximum queue depth:**
= items in active drain + items accumulated during drain time
= ~945K + (35 min / 15 min) × 945K
= ~945K + ~2.2M
= **~3.1M items**

**Equilibrium condition:** The queue is stable — it does not grow without bound — because the release rate (1,500/sec) exceeds the arrival rate (1,050/sec). The queue reaches a steady-state depth of approximately 3.1M items and holds there until the event subsides. At ~200 bytes per queued item, this requires ~620MB of Redis memory, within the provisioned 4GB ceiling.

**The LIFO problem at this depth:** Redis Lists using BRPOP exhibit LIFO behavior under high concurrency. At queue depths above ~1M items, recently-queued P1 notifications are processed before older ones, producing unbounded latency for the oldest items. This is unacceptable for P1 delivery. **Mitigation:** At queue depths above 500K items, workers switch to a round-robin polling pattern across multiple sub-queues (partitioned by notification ID modulo N), distributing processing across the queue depth rather than consuming from the head. E2 owns this implementation.

### 1.2b Month-3 Tier Weight Revisit

**What data will be available:** Eight weeks of live traffic from a beta cohort growing from 50K toward 200–500K users. At 200K+ users, social graph density is materially higher than week-2, making per-T1-user rates more representative. Behavioral segmentation data allows direct tier composition measurement.

**Measurement methodology:** E1 runs a 7-day measurement window in weeks 9–10, capturing per-user notification rates and segmenting by behavioral tier using the definitions in Section 1.2. The weighted average is computed from observed data, not benchmark models.

**Decision criteria:**