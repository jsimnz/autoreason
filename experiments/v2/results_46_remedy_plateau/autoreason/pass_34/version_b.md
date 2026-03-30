# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

This document contains two categories of content that must be kept distinct: **architecture decisions** that are independent of usage profile assumptions, and **sizing calculations** that depend on validated metrics.

Architecture decisions — channel selection, priority schema, delivery logic, infrastructure choices, failure handling — are finalized and ready for implementation planning. They do not change whether DAU/MAU is 15% or 60%, **within the throughput range where the current queue topology holds** (see §1.1.5 for the architectural breakpoint and what changes above it).

Sizing calculations — server counts, queue depths, Redis cluster configuration, WebSocket instance counts, SMS cost projections — use a baseline assumption set (§1.1) and must be recalculated before infrastructure is provisioned. §1.1.3 provides the recalculation procedure. The two open decisions in §9 affect sizing only, not architecture — again, within the range described in §1.1.5.

**What this means in practice:** Engineering can begin implementation work on all sections immediately. Infrastructure provisioning requires §9 resolution. These are different activities with different timelines.

**Three governance items require resolution before specific paths go to production:**

1. **§9 open decisions** (DAU/MAU ratio and geographic distribution): Target resolution 14 days from issue date. No infrastructure should be provisioned until resolved.

2. **Parallel dispatch sign-off (§2.1):** The decision to use parallel multi-channel dispatch for Critical notifications carries real cost and UX consequences — including SMS cost implications not previously captured in cost projections. This decision requires explicit sign-off from Jordan Rivera (Product Lead) before the Critical notification path goes to production. The sign-off process is defined in §10 (Escalation Procedure). The placeholder in §2.1 must be replaced with a confirmed approval reference before production deployment.

3. **Architectural breakpoint review (§1.1.5):** If validated metrics place the product in the high-throughput cell (60% DAU/MAU, 50 events/DAU), queue topology must be reviewed before infrastructure is provisioned. This is not a future concern — it must be resolved at the same time as item 1.

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
| Geographic concentration peak | ~1,040 events/second | 2.0× average — see §1.1.4 |
| Burst headroom ceiling | ~1,560 events/second | 3.0× average — infrastructure provisioning target |

**Critical distinction:** The geographic concentration peak (~1,040/sec) is the expected sustained maximum during evening traffic. The burst headroom ceiling (~1,560/sec) is the infrastructure provisioning upper bound — the number used to size queues and autoscaling limits. Do not provision to the geographic peak and assume burst is covered.

#### 1.1.1 DAU/MAU Sensitivity

The DAU/MAU ratio is the first multiplier in every throughput calculation, every server count, and every cost projection. It is borrowed from industry averages and is unknown until instrumented.

| DAU/MAU | DAU | Avg throughput | Geographic peak | Burst ceiling |
|---|---|---|---|---|
| 15% (content-discovery) | 1.5M | ~260/sec | ~520/sec | ~780/sec |
| 30% (baseline) | 3M | ~520/sec | ~1,040/sec | ~1,560/sec |
| 60% (messaging-heavy) | 6M | ~1,040/sec | ~2,080/sec | ~3,120/sec |

These figures assume 15 events/DAU/day. See §1.1.3 for combined sensitivity.

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this is a greenfield launch with no historical data, provision for 30% with autoscaling configured to handle 60% without manual intervention.

#### 1.1.2 Events-per-DAU Sensitivity

The events-per-DAU-per-day figure is the second multiplier in all throughput calculations. It varies significantly by product type and is as uncertain as the DAU/MAU ratio.

| App type | Events/DAU/day | Basis |
|---|---|---|
| Content-discovery (likes, follows) | 5–8 | Low social graph density, passive consumption |
| General social (baseline assumption) | 15 | Mixed engagement and messaging |
| Messaging-heavy | 50–100 | Direct message threads, group chats |

This document assumes 15. A messaging-heavy product at 15 events/DAU/day is significantly underestimated. If the product roadmap includes real-time messaging, this assumption must be revisited before Phase 2 infrastructure is provisioned (see §8 for phase definitions and the explicit trigger for this revisitation).

#### 1.1.3 Combined Sensitivity and Recalculation Procedure

The two unknowns compound. The table below shows burst ceiling (the infrastructure provisioning target) across the plausible range. Cells above the architectural breakpoint threshold are marked — see §1.1.5.

| | 5 events/DAU/day | 15 events/DAU/day | 50 events/DAU/day |
|---|---|---|---|
| 15% DAU/MAU | ~260/sec | ~780/sec | ~2,600/sec ⚠ |
| 30% DAU/MAU | ~520/sec | ~1,560/sec | ~5,200/sec ⚠ |
| 60% DAU/MAU | ~1,040/sec | ~3,120/sec ⚠ | ~10,400/sec ⚠ |

⚠ = Exceeds ~2,500/sec; queue topology review required before provisioning. See §1.1.5.

**Burst ceiling formula:**
```
burst_ceiling = (MAU × DAU/MAU_ratio × events_per_DAU_per_day / 86,400) × 3.0
```

The 3.0× multiplier is the burst headroom factor applied to average throughput. It already accounts for geographic concentration — it is not multiplied by the geographic peak multiplier separately. The geographic peak figures in §1.1 and §1.1.4 describe the expected sustained maximum; the 3.0× burst ceiling is provisioned above that peak. Applying both multipliers would compound them incorrectly.

To derive the geographic peak for monitoring and alerting purposes (not provisioning):
```
geographic_peak = (MAU × DAU/MAU_ratio × events_per_DAU_per_day / 86,400) × geographic_multiplier
```

where `geographic_multiplier` is drawn from §1.1.4. The burst ceiling is always provisioned at 3.0× average, regardless of geographic multiplier.

When validated figures are available, substitute them into the burst ceiling formula and recalculate §7 directly. No other sections require recalculation — architecture decisions are independent of these figures within the range described in §1.1.5.

**If launching without historical data:** Provision for the (30% DAU/MAU, 15 events/DAU) cell with autoscaling configured to reach the (60% DAU/MAU, 15 events/DAU) cell without manual intervention. If the product roadmap includes messaging features that could push events/DAU toward 50, schedule the §1.1.5 architectural review for the Phase 1/Phase 2 boundary regardless of whether metrics have been validated by then.

#### 1.1.4 Peak Throughput and Geographic Concentration

Geographic distribution affects the peak-to-average ratio: a geographically concentrated user base produces sharper evening peaks than a globally distributed one. This multiplier is used to set monitoring alert thresholds and to validate that the burst ceiling is genuinely above the expected peak — it is not a separate factor in the provisioning formula.

| User distribution | Geographic peak multiplier | Geographic peak (baseline 520/sec avg) | Notes |
|---|---|---|---|
| US-only | 2.0× | ~1,040/sec | Single timezone concentration |
| US + Western Europe | 1.6× | ~830/sec | Two peak windows, partially offset |
| Global, distributed | 1.3× | ~675/sec | Smoothed across timezones |

**Important:** Adding European users to a US-only base increases *total volume* even as it decreases the peak multiplier. The multiplier reduction reflects smoother distribution of a larger total — it does not mean absolute peak throughput decreases when the user base expands geographically. When the product expands to new geographies, recalculate average throughput first (from the updated MAU and events/DAU figures), then apply the new multiplier to that higher base. Do not apply a lower multiplier to the old average and conclude that peak throughput has decreased.

**Action required:** Engineering must obtain geographic user distribution from the product team before finalizing §7.

#### 1.1.5 Architectural Breakpoint: When the Queue Topology Changes

The claim that architecture is independent of sizing holds up to approximately **2,500 events/second burst ceiling**. Above this threshold, the single-queue-per-priority SQS topology requires modification.

**Why 2,500/sec is the threshold:**

SQS standard queues support effectively unlimited throughput, but the constraint is not SQS itself — it is the consumer side. A single consumer pool processing messages from one queue has practical limits based on worker count, message processing time, and the SQS `ReceiveMessage` API call rate (each call returns up to 10 messages; at high throughput, the polling pattern creates overhead). At ~2,500/sec sustained, a single-queue-per-priority design requires enough consumer instances that operational complexity begins to rival a partitioned design. The crossover point is not a hard SQS limit; it is an operational manageability threshold for a 4-person team.

**What changes above the threshold:**

| Aspect | Below ~2,500/sec | Above ~2,500/sec |
|---|---|---|
| Queue topology | One queue per priority tier (3 queues) | Partition by user ID hash; multiple queues per priority tier |
| Consumer scaling | Single autoscaling group per priority | One autoscaling group per partition |
| Operational complexity | Low — 3 queues to monitor | Moderate — 9–12 queues, partition rebalancing |
| Dead letter handling | One DLQ per priority | One DLQ per partition |
| Team impact | Manageable for 4 engineers | Requires dedicated queue management runbook |

**What does not change above the threshold:** Channel selection logic, priority schema, delivery semantics, failure handling, user preference model, and the delivery channel integrations are all unchanged. The partitioning affects only the internal routing layer, not the interfaces visible to other system components.

**Trigger for this review:** If §9 resolution produces validated metrics placing the product in a ⚠-marked cell in §1.1.3, this review must occur before infrastructure is provisioned. It is not deferred to a later phase.

### 1.2 Team Constraints

Four backend engineers, six months. This is the binding constraint on every architectural decision in this document. Wherever a tradeoff appears, the default choice favors operational simplicity over theoretical optimality. A system two engineers can debug at 2 AM is worth more than one that performs 15% better on paper.

**Explicit scope exclusions:**
- No custom ML-based send-time optimization (fixed quiet hours instead — behavior specified in §3.3)
- No real-time A/B testing framework for notification copy
- No multi-region active-active deployment (single region with warm standby — RTO and RPO defined in §6.4)
- No custom SMS aggregator integration (Twilio managed service)
- No custom queue partitioning unless §1.1.5 threshold is exceeded

### 1.3 Success Criteria

| Metric | Target | Notes |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.5% (< 44 hours downtime/year) | See availability note below |
| User preference changes reflected | < 60 seconds | |

**On the availability target:** The 99.5% figure reflects the realistic ceiling for a single-region deployment with this dependency chain: SQS (99.9% SLA) → ElastiCache (99.9% SLA) → RDS Multi-AZ (99.95% SLA) → FCM/APNs (no formal SLA). End-to-end availability cannot exceed the product of component availabilities, and FCM/APNs introduce uncontrolled variance. The failure mode analysis in §6.4 enumerates recovery time for each component and confirms that 99.5% is achievable; 99.9% is not without multi-region deployment.

**If 99.9% is a hard business requirement:** This requires multi-region deployment, active-active or active-passive with sub-minute failover, and ongoing operational overhead that exceeds what a 4-person team can sustain alongside feature delivery. The team constraint must be explicitly revisited before that target is committed to. This is not a future decision — if 99.9% is required, it must be resolved before Phase 1 design is finalized.

---

## 2. Delivery Channels

### 2.1 Channel Overview and Fallback Logic

Four channels are supported. Selection logic differs by priority tier. The key architectural choice — parallel versus sequential dispatch for Critical notifications — is described here in full because it has cost, complexity, and UX consequences that must be understood together before the decision is confirmed.

**For Critical notifications:** All eligible channels are dispatched in parallel simultaneously. Eligibility is determined before dispatch by checking opt-in status and device token validity.

**This is a deliberate product decision, not a default. It requires explicit sign-off from Jordan Rivera (Product Lead) before the Critical notification path goes to production. The sign-off process is defined in §10. The placeholder below must be replaced with the approval reference number generated by that process before production deployment.**

*Approval reference: [PENDING — see §10 for process. Production deployment of Critical path is blocked until this field is populated.]*

**Rationale for parallel dispatch:**

1. Security events require acknowledged delivery, not just attempted delivery. Redundancy is correct behavior for "unrecognized device login" — a user who receives the same security alert via push, email, and SMS simultaneously understands something happened.
2. Push-only delivery for security events has a known failure mode: users with notification fatigue or disabled push permissions miss critical alerts entirely.
3. Sequential fallback with async push confirmation requires stateful tracking infrastructure disproportionate to this team size. See §2.1.1 for detail.

**SMS cost implication of parallel dispatch — requires explicit accounting:**

Parallel dispatch means every user registered for SMS receives an SMS for every Critical event, regardless of whether push or email delivered successfully. The cost formula is:

```
monthly_SMS_cost = SMS_eligible_users × critical_events_per_user_per_month × SMS_unit_cost
```

**Input assumptions and their basis:**

| Input | Planning assumption | Basis | Risk |
|---|---|---|---|
| SMS opt-in rate | 5% of MAU = 500,000 users | Industry average for security SMS opt-in | Low variance — security SMS opt