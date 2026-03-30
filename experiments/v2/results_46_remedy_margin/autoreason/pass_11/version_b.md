# Notification System Design — Revision 2
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
| Engineering Lead | Lead | Architecture decisions, vendor relationships, executive escalation | Covered by E1 for operational decisions during planned absences; see 7.4 |
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
- Auth SMS (required at launch)

**On the SMS scope conflict:** SMS is operationally live from day one for auth and P0 alerts. Describing it as "cut except for auth" is misleading — the operational burden of a live channel exists regardless of how its scope is framed. What is deferred is expansion of SMS use cases beyond auth and P0. The on-call page conditions for auth SMS failure rate (Section 7.3) reflect this: SMS is a monitored, live channel from launch. The deferred item is scope expansion, not the channel itself.

### 7.3 On-Call Structure

**Rotation:** 2-person on-call at all times. Primary is paged first; secondary paged if primary does not acknowledge within 15 minutes. Rotation cycles weekly among all four engineers.

**Page-worthy conditions:**
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

**Engineering time budget for operations:** The 20% figure is a planning assumption, not an empirical measurement. It is derived from analogous systems at comparable scale where operational work settled at 15–25% once past initial stabilization. This team has no prior operational history for this system, which means the 20% figure could be wrong in either direction during the first 8 weeks. The practical consequence: if any engineer consistently reports more than 25% of their week consumed by operational work for two consecutive weeks during beta, the engineering lead treats this as a delivery risk and escalates — not because 25% is a known threshold, but because two consecutive weeks of overrun is a signal that the assumption is failing. The figure is a tripwire, not a budget.

### 7.4 Engineering Lead Constraints and Single Point of Failure Acknowledgment

The engineering lead owns architecture decisions, vendor relationships, executive escalation, on-call P0 escalation, and approval of infrastructure changes exceeding 20%. This is one person. The proposal does not resolve this — it acknowledges it as a structural constraint of a 4-engineer team and specifies what happens when the lead is unavailable.

**Planned absences:** The lead designates E1 as acting lead for absences of up to one week. E1 has authority to make operational decisions and approve infrastructure changes during this period. Architecture decisions that can wait do wait; those that cannot are made by E1 with a documented rationale reviewed by the lead on return.

**Unplanned unavailability:** If the lead becomes unavailable without designation (medical emergency, etc.), E1 assumes acting lead authority immediately. The executive sponsor is notified within 4 hours. If E1 is simultaneously unavailable, E4 assumes authority. There is no scenario in which the team has no decision-maker — the chain is Lead → E1 → E4.

**What this does not solve:** If the lead is unavailable during a P0 event, E1 handles it. The lead's "always reachable" framing in the prior version overstated the guarantee. The correct framing: the lead is the preferred P0 escalation path; E1 is the fallback with full authority. The executive sponsor is not a technical escalation path — they are a business decision path (see 7.5).

**The honest tradeoff:** A 4-engineer team with one lead has a single point of failure at the architecture and vendor-relationship layer. This is a known risk accepted in exchange for not over-structuring a small team. The mitigation is documentation — architecture decisions are written down in sufficient detail that E1 can execute them without the lead present — not redundancy of the person.

### 7.5 Executive Sponsor Role — Defined

The executive sponsor is referenced at two points: the >3× escalation protocol and the DAU/MAU coordinated capacity review. Their role is defined here once, rather than inline at each reference.

**What the executive sponsor does:**
- Approves resource commitments above a defined threshold (infrastructure spend increases >$10K/month, or headcount additions)
- Removes organizational blockers the engineering team cannot remove (vendor contract issues, budget approval, cross-team dependencies)
- Makes scope reduction decisions when the team cannot deliver the committed feature set in the remaining timeline

**What the executive sponsor does not do:**
- Participate in technical reviews
- Evaluate measurement methodology
- Make architectural decisions

**Availability requirement:** The executive sponsor commits to a 4-hour response SLA for escalations during the 6-month window. If the sponsor is unavailable, they designate a proxy in advance with equivalent authority.

**What happens if the sponsor is unavailable during a 48-hour escalation:** The engineering lead proceeds with the conservative option — the option that avoids irreversible decisions — without sponsor approval. Reversible decisions (adding capacity, pausing beta expansion) do not require sponsor approval. Irreversible decisions (architectural changes, vendor contract changes) wait for sponsor availability up to the 48-hour limit, then default to the conservative option.

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

**The coordinated capacity review — including when it runs long:**

The review covers Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. E1 owns it; the engineering lead approves any recommendation requiring >20% infrastructure change. The one-week completion target assumes normal operating conditions.

If a Scenario A or B event occurs during the review window, the review is suspended and on-call takes priority. The review resumes after the event resolves. The completion window extends by the duration of the suspension, up to a maximum of two additional weeks. If the review has not completed within three weeks of initiation, the engineering lead escalates to the executive sponsor — not because three weeks is a known failure threshold, but because a review that takes three weeks has either encountered a genuine architectural problem or has been repeatedly interrupted, both of which are executive-level concerns.

If the review window coincides with a period where two or more engineers are carrying on-call load simultaneously (which can happen under the 2-person rotation during a sustained event), the engineering lead explicitly pauses non-urgent delivery work for those engineers for the duration. The capacity review is not treated as background work.

### 1.2 The 17/Day Planning Ceiling

#### The Circularity Problem — And What We Actually Do About It

The 17/day ceiling is circular: it is derived from benchmark-based per-tier rates multiplied by tier weights that cannot be validated before the infrastructure decisions that depend on them. The prior version acknowledged this in a callout and then used the 17/day figure as a decision gate input, embedding the circular number in downstream thresholds (17/day, 25/day, 51/day). That is not handling the circularity honestly.

**What changes in this version:**

The 17/day figure is not used as a gate threshold. The decision gate thresholds in Section 1.2c are derived from the worst-modeled scenario (the 15/35/50 tier split, producing a 27/day ceiling) rather than from the 17/day baseline. The 17/day figure is retained as a derivation artifact — it shows the calculation — but it does not anchor any operational decision.

The Phase 1 infrastructure is provisioned at the 15/35/50 scenario ceiling at 60% capacity. This means the system is sized against the worst modeled case, not against a number that depends on the thing being sized. The cost of this is approximately $5–10K/month more than anchoring to the 17/day baseline would produce. That cost is accepted as the direct consequence of treating the circularity honestly rather than papering over it.

The gate thresholds in Section 1.2c are expressed in absolute terms (notifications/sec at peak, queue depth, worker saturation) rather than as multiples of the 17/day figure, so they do not inherit the circularity.

#### Derivation (Retained as Reference — Not as a Sizing Anchor)

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

#### Phased Procurement

**Phase 1 (weeks 3–8):** Provision at the 15/35/50 scenario ceiling, 60% capacity. Approximately 30 P1 workers, Redis cluster sized for 27/day at baseline DAU, RDS at ~2,000 writes/sec. Handles beta cohort up to 500K users.

**Phase 2 trigger (month-3 revisit):** After 8 weeks of live traffic data, provision the remainder based on observed rates. ElastiCache and RDS read replicas are available within days; EC2 worker capacity within hours. The 6-week window between month 3 and month 4.5 is sufficient for managed service provisioning; it is not sufficient for architectural changes.

**The tradeoff explicitly stated:** Running at 60% capacity means the system cannot absorb a full Scenario B spike during weeks 3–8. Delivery latency increases; notifications are not dropped. This is acceptable during a 50K-user beta. It would not be acceptable at full launch.

### 1.2a Queue Equilibrium Under the >3× Case

#### The Overlap Problem — Resolved

With a 15