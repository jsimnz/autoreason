# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

This document contains two categories of content that must be kept distinct: **architecture decisions** that are independent of usage profile assumptions, and **sizing calculations** that depend on validated metrics.

Architecture decisions — channel selection, priority schema, delivery logic, infrastructure choices, failure handling — are finalized and ready for implementation planning. They do not change whether DAU/MAU is 15% or 60%, **within the throughput range where the current queue topology holds** (see §1.1.5 for the architectural breakpoint and what changes above it).

Sizing calculations — server counts, queue depths, Redis cluster configuration, WebSocket instance counts, SMS cost projections — use a baseline assumption set (§1.1) and must be recalculated before infrastructure is provisioned. §1.1.3 provides the recalculation procedure.

**What this means in practice:** Engineering can begin implementation work on all sections immediately. Infrastructure provisioning requires §9 resolution. These are different activities with different timelines.

**Four governance items require resolution before specific paths go to production:**

1. **§9 open decisions** (DAU/MAU ratio and geographic distribution): Target resolution 14 days from issue date. If day 14 passes without resolution, Priya Anand (Executive Sponsor) makes the provisional decision unilaterally using the conservative defaults defined in §9. No infrastructure should be provisioned until resolved or until Priya invokes the default path.

2. **Parallel dispatch sign-off (§2.1):** The decision to use parallel multi-channel dispatch for Critical notifications carries real cost and UX consequences — including SMS cost implications quantified in §2.1.1. This requires explicit sign-off from Jordan Rivera (Product Lead) before the Critical notification path goes to production. If Rivera is unavailable, the sign-off authority passes to Priya Anand. The sign-off process is defined in §10. The placeholder in §2.1 must be replaced with a confirmed approval reference before production deployment.

3. **Architectural breakpoint review (§1.1.5):** If validated metrics place the product in a high-throughput cell (marked ⚠ in §1.1.3), queue topology must be reviewed before infrastructure is provisioned. This is not a future concern — it must be resolved concurrently with item 1.

4. **Availability target confirmation:** If 99.9% availability is a hard business requirement, multi-region deployment is required. This exceeds what a 4-person team can sustain alongside feature delivery. The team constraint must be explicitly revisited before Phase 1 design is finalized. See §1.3 for the derivation of the 99.5% target.

---

## Table of Contents

1. Scale and Constraints
2. Delivery Channels
3. Priority and Batching Logic
4. User Preference Management
5. Infrastructure Choices
6. Failure Handling
7. Capacity Planning
8. Phased Delivery Plan
9. Open Decisions
10. Escalation Procedure

---

## 1. Scale and Constraints

### 1.1 Usage Profile

10M monthly active users. The numbers below are planning assumptions derived from industry averages, not measurements. They must be validated against product analytics before infrastructure is provisioned. §1.1.3 shows how to recalculate all downstream sizing figures once real data is available.

**Two compounding unknowns drive all throughput calculations.** The DAU/MAU ratio and the events-per-DAU-per-day figure are independent variables that multiply together. Both are unknown at this stage. §1.1.1 and §1.1.2 treat them independently; §1.1.3 shows how to combine them.

| Metric | Value | Basis |
|---|---|---|
| Daily active users | ~3M | 30% DAU/MAU — provisional, see §1.1.1 |
| Notification events per DAU per day | ~15 | Industry average — provisional, see §1.1.2 |
| Daily notification volume | ~45M events | 3M × 15 |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Geographic concentration peak | ~1,040 events/second | 2.0× average — monitoring threshold only, see §1.1.4 |
| Burst headroom ceiling | ~1,560 events/second | 3.0× average — infrastructure provisioning target, see §1.1.3 for derivation |

**Critical distinction:** The geographic concentration peak (~1,040/sec) is the expected sustained maximum during evening traffic and is used only to set monitoring alert thresholds. The burst headroom ceiling (~1,560/sec) is the infrastructure provisioning target. The relationship between these two numbers is explained in §1.1.3. Do not provision to the geographic peak and assume burst is covered.

#### 1.1.1 DAU/MAU Sensitivity

The DAU/MAU ratio is the first multiplier in every throughput calculation, every server count, and every cost projection. It is borrowed from industry averages and is unknown until instrumented.

| DAU/MAU | DAU | Avg throughput | Geographic peak (monitoring) | Burst ceiling (provisioning) |
|---|---|---|---|---|
| 15% (content-discovery) | 1.5M | ~260/sec | ~520/sec | ~780/sec |
| 30% (baseline) | 3M | ~520/sec | ~1,040/sec | ~1,560/sec |
| 60% (messaging-heavy) | 6M | ~1,040/sec | ~2,080/sec | ~3,120/sec |

These figures assume 15 events/DAU/day and a 2.0× geographic peak multiplier (US-only distribution). See §1.1.3 for combined sensitivity and §1.1.4 for other geographic multipliers.

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this is a greenfield launch with no historical data, provision for 30% with autoscaling configured to handle 60% without manual intervention.

#### 1.1.2 Events-per-DAU Sensitivity

The events-per-DAU-per-day figure is the second multiplier in all throughput calculations. It varies significantly by product type and is as uncertain as the DAU/MAU ratio.

| App type | Events/DAU/day | Basis |
|---|---|---|
| Content-discovery (likes, follows) | 5–8 | Low social graph density, passive consumption |
| General social (baseline assumption) | 15 | Mixed engagement and messaging |
| Messaging-heavy | 50–100 | Direct message threads, group chats |

This document assumes 15. A messaging-heavy product at 15 events/DAU/day is significantly underestimated. If the product roadmap includes real-time messaging, this assumption must be revisited before Phase 2 infrastructure is provisioned (see §8 for phase definitions and the explicit trigger for this revisitation).

#### 1.1.3 Combined Sensitivity, Burst Ceiling Derivation, and Recalculation Procedure

**How the 3.0× burst multiplier relates to the 2.0× geographic peak multiplier:**

These two figures are not independent. The 3.0× burst ceiling multiplier was chosen as 1.5× the 2.0× geographic peak multiplier — that is, it provides 50% headroom above the expected sustained peak during the worst-case evening concentration window. It does not independently account for geography; rather, it is sized to remain above the geographic peak with meaningful margin.

The correct mental model:

```
geographic_peak  = average_throughput × geographic_multiplier          (monitoring threshold)
burst_ceiling    = average_throughput × geographic_multiplier × 1.5    (provisioning target)
                 = average_throughput × 3.0                             (for 2.0× geographic multiplier)
```

For a US + Western Europe distribution (geographic multiplier 1.6×), the burst ceiling formula becomes:

```
burst_ceiling = average_throughput × 1.6 × 1.5 = average_throughput × 2.4
```

The 3.0× shorthand in the provisioning formula is only correct for a US-only (2.0×) geographic concentration. If §9 resolution produces a different geographic distribution, the burst ceiling must be recalculated using the appropriate multiplier from §1.1.4.

**Burst ceiling formula (general form):**

```
burst_ceiling = (MAU × DAU_MAU_ratio × events_per_DAU_per_day / 86,400)
                × geographic_multiplier × 1.5
```

**Combined sensitivity table — burst ceiling (events/sec):**

Cells above the architectural breakpoint threshold are marked ⚠ — see §1.1.5.

| | 5 events/DAU/day | 15 events/DAU/day | 50 events/DAU/day |
|---|---|---|---|
| 15% DAU/MAU | ~260/sec | ~780/sec | ~2,600/sec ⚠ |
| 30% DAU/MAU | ~520/sec | ~1,560/sec | ~5,200/sec ⚠ |
| 60% DAU/MAU | ~1,040/sec | ~3,120/sec ⚠ | ~10,400/sec ⚠ |

⚠ = Exceeds ~2,500/sec; queue topology review required before provisioning. See §1.1.5.

**Recalculation procedure:** When validated figures are available, substitute DAU/MAU ratio, events/DAU/day, and the appropriate geographic multiplier from §1.1.4 into the general burst ceiling formula above. Then recalculate §7 (Capacity Planning) directly. No other sections require recalculation — architecture decisions are independent of these figures within the range described in §1.1.5.

**If launching without historical data:** Provision for the (30% DAU/MAU, 15 events/DAU) cell with autoscaling configured to reach the (60% DAU/MAU, 15 events/DAU) cell without manual intervention. If the product roadmap includes messaging features that could push events/DAU toward 50, schedule the §1.1.5 architectural review for the Phase 1/Phase 2 boundary regardless of whether metrics have been validated by then.

#### 1.1.4 Peak Throughput and Geographic Concentration

Geographic distribution affects the peak-to-average ratio: a geographically concentrated user base produces sharper evening peaks than a globally distributed one. This multiplier feeds into the burst ceiling formula in §1.1.3 and sets monitoring alert thresholds. It is not an independent factor applied on top of the burst ceiling.

| User distribution | Geographic peak multiplier | Geographic peak (baseline 520/sec avg) | Burst ceiling (×1.5 above peak) |
|---|---|---|---|
| US-only | 2.0× | ~1,040/sec | ~1,560/sec |
| US + Western Europe | 1.6× | ~830/sec | ~1,250/sec |
| Global, distributed | 1.3× | ~675/sec | ~1,015/sec |

**Important:** Adding European users to a US-only base increases total volume even as it decreases the peak multiplier. The multiplier reduction reflects smoother distribution of a larger total — it does not mean absolute peak throughput decreases when the user base expands geographically. When the product expands to new geographies, recalculate average throughput first from the updated MAU and events/DAU figures, then apply the new multiplier to that higher base.

**Action required:** Engineering must obtain geographic user distribution from the product team before finalizing §7.

#### 1.1.5 Architectural Breakpoint: When the Queue Topology Changes

The claim that architecture is independent of sizing holds up to approximately **2,500 events/second burst ceiling**. Above this threshold, the single-queue-per-priority SQS topology requires modification.

**Quantified basis for the 2,500/sec threshold:**

The constraint is not SQS itself — standard queues support effectively unlimited throughput. The constraint is the consumer side: specifically, the SQS long-polling pattern and per-worker processing capacity.

Working through the arithmetic at baseline assumptions (30% DAU/MAU, 15 events/day, 1,560/sec burst ceiling):

- SQS `ReceiveMessage` returns up to 10 messages per call with up to 20-second long-poll
- At 1,560/sec, sustaining consumption requires at minimum 156 parallel `ReceiveMessage` calls in flight continuously
- Assuming a worker processes one message in ~50ms (FCM dispatch + Redis preference lookup + acknowledgment write), each worker thread handles ~20 messages/sec
- To consume 1,560/sec requires ~78 worker threads; with 4 threads per instance, ~20 instances per priority queue
- At 2,500/sec, the same math yields ~125 worker threads and ~32 instances per priority queue — still a single autoscaling group, but monitoring 32 instances per queue across 3 priority queues (96 instances total) approaches the upper bound of what a 4-person team can manage without dedicated tooling

These figures assume 50ms per message. If worker processing time increases — for example, because preference lookups miss the Redis cache and fall through to RDS — throughput per worker drops and instance counts rise proportionally. The 2,500/sec threshold should be treated as the upper bound for a 50ms average processing time; measure actual processing time during Phase 1 load testing and recalculate if it differs materially.

**What changes above the threshold:**

| Aspect | Below ~2,500/sec | Above ~2,500/sec |
|---|---|---|
| Queue topology | One queue per priority tier (3 queues) | Partition by user ID hash; multiple queues per priority tier |
| Consumer scaling | Single autoscaling group per priority | One autoscaling group per partition |
| Operational complexity | Low — 3 queues to monitor | Moderate — 9–12 queues, partition rebalancing |
| Dead letter handling | One DLQ per priority | One DLQ per partition |
| Team impact | Manageable for 4 engineers | Requires dedicated queue management runbook |

**What does not change above the threshold:** Channel selection logic, priority schema, delivery semantics, failure handling, user preference model, and delivery channel integrations are all unchanged. Partitioning affects only the internal routing layer, not interfaces visible to other system components.

**Trigger for this review:** If §9 resolution produces validated metrics placing the product in a ⚠-marked cell in §1.1.3, this review must occur before infrastructure is provisioned. It is not deferred to a later phase.

### 1.2 Team Constraints

Four backend engineers, six months. This is the binding constraint on every architectural decision in this document. Wherever a tradeoff appears, the default choice favors operational simplicity over theoretical optimality. A system two engineers can debug at 2 AM is worth more than one that performs 15% better on paper.

**Explicit scope exclusions:**

- No custom ML-based send-time optimization (fixed quiet hours instead — behavior fully specified in §3.3)
- No real-time A/B testing framework for notification copy
- No multi-region active-active deployment (single region with warm standby — RTO and RPO defined in §6.4)
- No custom SMS aggregator integration (Twilio managed service)
- No custom queue partitioning unless §1.1.5 threshold is exceeded

Each exclusion is a deliberate tradeoff. The cost of building and operating these capabilities within the team and timeline constraint exceeds the benefit. If business requirements change, these exclusions must be revisited explicitly — they are not permanent architectural constraints.

### 1.3 Success Criteria

| Metric | Target | Notes |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.5% (< 44 hours downtime/year) | Derived below |
| User preference changes reflected | < 60 seconds | |

**Availability target derivation:**

The 99.5% figure is derived from component SLAs, not chosen arbitrarily. The calculation:

| Component | SLA | Annualized downtime |
|---|---|---|
| SQS (standard queues) | 99.9% | ~8.8 hours |
| ElastiCache (Multi-AZ) | 99.9% | ~8.8 hours |
| RDS (Multi-