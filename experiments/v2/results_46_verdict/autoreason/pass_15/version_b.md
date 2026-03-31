# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51–61M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**Core architectural decision: per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

**Circuit breaker threshold:** The P2 circuit breaker fires at **5,440/sec**—exactly 85% of the 6,400/sec provisioned ceiling. Shed P2 notifications are deferred to the next off-peak window, not dropped. Section 2.4 analyzes what happens to the deferred queue under sustained overload, including the bounded failure mode when the deferred queue itself fills.

**The compound worst-case scenario is not protected by the circuit breaker.** The 50% DAU/MAU + 2-hour peak window + 3× burst scenario produces 15,300/sec—2.4× the provisioned ceiling. The circuit breaker fires at 5,440/sec, well below this level. Section 2.5 specifies what happens when instantaneous demand exceeds 6,400/sec. We accept this as a tail risk rather than a provisioning target, and name the failure mode explicitly. The classification of the 2-hour window scenario as "not a tail risk individually" is reconciled with this in §1.1b: the 2-hour window alone produces 12,750/sec at baseline DAU—still above the provisioned ceiling—and is therefore treated in the provisioning response, not deferred. What we accept as a tail risk is the full compound scenario requiring all three pessimistic conditions simultaneously.

**WebSocket scaling caveat stated upfront:** The horizontal WebSocket scaling described in §1.1a is valid only for the delivery model in scope at launch. Cross-instance fan-out—required when a notification targets a user whose connection is on a different instance—is not in the launch architecture. The fan-out trigger and the validation sequencing problem it creates are addressed explicitly in §1.1a: the month 2 DAU/MAU trigger initiates architectural planning, not deployment; deployment is gated on month 3 load test validation of per-connection memory figures.

**The P0 taxonomy is a prerequisite for the entire priority architecture.** The 3-hour timebox for the taxonomy session is not arbitrary: it bounds the time we spend on a decision that has a known fallback (the interim taxonomy in §3.1) rather than blocking infrastructure provisioning. The timebox is not "time sufficient to achieve perfect consensus"—it is time sufficient to either achieve working consensus or escalate to a decision owner with a 48-hour deadline.

**Launch sequencing is explicit.** System launch occurs at end of month 4. Load testing occurs in month 3, before launch. Section 7 specifies this sequencing in full.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations—push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio—see §1.1a for sensitivity analysis |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~3 (launch), ~5 (target) | Conservative at launch; ramp gated on opt-out data |
| **Push volume/day** | **~21M (launch), ~35M (target)** | 7M × 3 / 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M (30% ratio), ~25M (50% ratio)** | See §1.1a |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback analyzed in §1.1c |
| **Total/day (launch, 30% ratio)** | **~37M** | Sum across channels at launch |
| **Total/day (target, 30% ratio)** | **~51M** | Sum across channels at target frequency |
| **Total/day (target, 50% ratio)** | **~61M** | High-engagement scenario; see §1.1a |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals. Section 1.1a specifies exactly what gets re-provisioned if actuals diverge materially.

---

### 1.1a DAU/MAU Ratio Sensitivity Analysis

The 30% DAU/MAU ratio is the single assumption doing the most work in this model. Industry data shows 20–55% across social app categories. We cannot know our ratio before launch. This section bounds the error and states the provisioning response for each scenario.

**Why 30% as the planning baseline:** We use 30% because it is the conservative end of the range for social apps with active engagement loops. If we are wrong low, we over-provision in-app capacity—a recoverable error. If we are wrong high, we under-provision—the more dangerous error, which is why we model it explicitly.

**Sensitivity table:**

| DAU/MAU ratio | DAU | In-app volume/day | Total/day (target) | Infrastructure delta vs. baseline |
|---------------|-----|-------------------|--------------------|----------------------------------|
| 20% | 2M | 10M | 46M | Under-provisioned; in-app consumers can be reduced |
| **30% (baseline)** | **3M** | **15M** | **51M** | **Design baseline** |
| 40% | 4M | 20M | 56M | In-app consumers scaled ~33%; WebSocket pool expanded; fan-out planning initiated |
| 50% | 5M | 25M | 61M | In-app consumers scaled ~67%; WebSocket pool expanded; fan-out required before scaling proceeds |

**WebSocket sizing and its uncertainty:** The baseline connection pool is sized for 3M concurrent peak connections across 6 WebSocket server instances (500K connections per instance) using sticky sessions via the load balancer. The 500K connections-per-instance figure is a planning estimate derived from general reference architectures for Go-based WebSocket servers with minimal per-connection state. It is not validated for this specific application.

Memory consumption per connection depends on what state is stored per connection, message frequency, TLS session overhead, and Go runtime goroutine stack allocation. The ~4GB RAM estimate (500K connections × ~8KB per connection) is reasonable for a minimal implementation but could be 2× higher if connection state is richer. **Because this estimate could be 2× off, the headroom calculations and scaling triggers below are stated in terms of measured utilization percentages rather than absolute connection counts.** The month 3 load test must produce a validated per-connection memory figure before any scaling trigger is acted upon.

**Sticky session failure mode:** When a WebSocket instance fails, all connections on that instance must reconnect. At 500K connections per instance, an instance failure triggers a reconnection storm against the remaining instances. Mitigations:

1. **Exponential backoff with jitter on client reconnect:** Clients randomize reconnect timing over 5–30 seconds. This is a client-side requirement specified in the mobile SDK contract (§4.2).
2. **Graceful drain before planned restarts:** Deployments drain connections over 60 seconds before terminating an instance, spreading reconnection load gradually. Enforced in the deployment runbook.
3. **Capacity headroom:** Baseline provisioning targets 60% utilization per instance, leaving 40% headroom to absorb reconnection load from a single failed instance. At 500K connections per instance and 6 instances, one failure redistributes those connections across 5 remaining instances—100K additional connections per instance, not 120K. At the 60% utilization baseline, each remaining instance is at approximately 70% post-redistribution, within the headroom margin. **The 60% utilization target is not validated until the month 3 load test confirms the per-connection memory figure. If actual memory per connection is 2× the estimate, the target utilization must be revised downward before this headroom argument holds.**
4. **Accepted residual risk:** An instance failure during a peak period, when remaining instances are already above 80% utilization, can cause cascading reconnection failures. This scenario is not fully mitigated; it is accepted as a known risk and monitored via the instance utilization alert in §6.3 (alert threshold: 75% utilization sustained for 5 minutes).

**Cross-instance fan-out limitation and trigger sequencing:** Without cross-instance fan-out, a notification for user B generated by user A's action is delivered via push if user B's connection is on a different instance. This is the normal case in a distributed deployment. The launch architecture accepts this degradation—in-app delivery falls back to push, which adds latency but does not lose the notification.

The fan-out trigger is: **if the month 2 review shows DAU/MAU ≥ 40%, cross-instance fan-out moves from deferred to active planning.** This trigger initiates architectural planning and infrastructure procurement only—it does not authorize deployment. Deployment of fan-out is gated on the month 3 load test validating per-connection memory consumption and confirming the instance count required. This sequencing resolves the apparent conflict between the month 2 trigger and month 3 validation: we use month 2 data to decide whether to build, and month 3 data to decide how to deploy.

Scaling WebSocket instances beyond the baseline 6 without fan-out in place would increase the silent drop rate proportionally and is not permitted.

**Provisioning response by scenario:**

- **20–30% ratio:** Baseline provisioning. No action.
- **30–40% ratio:** Add in-app consumer instances to the existing queue. Configuration change, not architectural. Target: completed within 5 business days of month 2 traffic review.
- **40–50% ratio:** Scale in-app consumers and initiate fan-out planning. Fan-out deployment gated on month 3 load test results. Architectural review within 2 weeks of month 2 traffic review; provisioning changes deployed within 4 weeks of load test sign-off.
- **Above 50% ratio:** Outside modeled range. Trigger a full traffic model review immediately; do not apply the scaling rules above without re-deriving the model.

---

### 1.1b Peak Throughput Calculation

The daily volume figures above are inputs. The design ceiling requires a separate derivation—and the derivation has a known weakness that must be stated upfront.

**The fundamental problem:** The peak window assumption and the burst multiplier are both planning estimates, not measured values. We are provisioning infrastructure in months 1–2 based on numbers we acknowledge we do not know. This section quantifies the consequence of being wrong, specifies the compound worst-case scenario explicitly, and states the mitigation.

**Step 1: Identify the peak window.** Morning and evening peaks each occupy approximately 2 hours and together account for approximately 60% of daily volume. The 60% figure is a planning estimate based on general social app traffic patterns; it is not sourced from measured data for this application. Whether the morning and evening peaks overlap into a 4-hour continuous window or remain distinct 2-hour windows is unknown. Both scenarios are modeled.

**Sensitivity to the 60% assumption:**

| Peak concentration | Sustained throughput (4hr window) | Delta vs. baseline |
|-------------------|----------------------------------|-------------------|
| 50% | 1,770/sec | −17% |
| **60% (baseline)** | **2,125/sec** | **—** |
| 75% | 2,655/sec | +25% |
| 85% | 3,005/sec | +41% |

At 75% peak concentration, sustained throughput is 2,655/sec—still within the provisioned ceiling of 6,400/sec, but the burst calculation changes materially. The provisioned ceiling remains valid across the plausible range of peak concentration values; the burst multiplier analysis is more sensitive to this assumption.

**Step 2: Calculate sustained throughput within the peak window.**

- **4-hour window (baseline assumption):** 51M × 0.60 / (4 × 3,600) = **~2,125/sec sustained**
- **2-hour window (pessimistic scenario):** 51M × 0.60 / (2 × 3,600) = **~4,250/sec sustained**

**Classification of the 2-hour window scenario:** The 2-hour scenario is not a tail risk in isolation. It is a structurally plausible outcome—morning and evening peaks simply not overlapping—and the 4,250/sec sustained figure it produces is well below the provisioned ceiling of 6,400/sec. We provision to the 4-hour baseline; the 2-hour scenario is handled by the same provisioned infrastructure without requiring scaling action.

However, the 2-hour window scenario becomes a provisioning problem when combined with a burst multiplier. The 2-hour window at 3× burst (baseline DAU) produces 12,750/sec—nearly 2× the provisioned ceiling. This is why we address the 2-hour + burst scenario in the provisioning response and in §2.5, not merely note it. What we accept as a tail risk is specifically the full compound scenario: 50% DAU/MAU + 2-hour window + 3× burst simultaneously, producing 15,300/sec. Each individual condition is handled; their simultaneous occurrence at pessimistic extremes is accepted.

**Step 3: Determine the burst multiplier.**

The 3× figure is a planning estimate based on general knowledge of viral event patterns on social platforms. It is not derived from measurement. It is treated as a planning input and validated in month 3 load testing.

**On correlation between DAU/MAU ratio and burst multiplier:** The document acknowledges that these inputs are correlated—a viral event is more likely on a high-engagement day. The sensitivity table below treats them as independent inputs because we do not have data to model the correlation. This means the compound scenario underestimates the true probability of high-DAU and high-burst coinciding. The correct response to this is not to pretend we have a correlation model; it is to note that the compound scenario is more likely than a naive independence assumption would suggest, and to ensure §2.5 specifies a response rather than just naming the failure.

| Scenario | Sustained peak (4hr window) | Burst (3×) | 2hr window + 3× burst |
|----------|----------------------------|------------|----------------------|
| 30% DAU/MAU (baseline) | 2,125/sec | 6,375/sec | 12,750/sec |
| 50% DAU/MAU (high) | 2,550/sec | 7,650/sec | 15,300/sec |

**Design ceiling for provisioning:** 6,400/sec instantaneous, 2,125/sec sustained (baseline scenario). The 2-hour window scenario at 3× burst exceeds the provisioned ceiling; §2.5 specifies the degradation response.

**Month 3 load test deliverables:**
1. Measured throughput ceiling under sustained 2,125/sec load for 4 hours.
2. Measured per-connection memory consumption for WebSocket instances under load.
3. Measured behavior at 5,440/sec (circuit breaker threshold): circuit breaker activation latency, P0/P1 isolation under shed P2 load.
4. Measured behavior at 6,400/sec instantaneous spike: queue depth growth rate, P0/P1 latency degradation.
5. Measured behavior at 12,750/sec (2-hour window, 3× burst, baseline DAU): how far the system degrades and whether P0/P1 delivery is maintained.
6. Identification of the first component to saturate and its saturation threshold.
7. Go/no-go recommendation on the 3× multiplier assumption, with a revised estimate if the recommendation is no-go.
8. Revised headroom calculations for