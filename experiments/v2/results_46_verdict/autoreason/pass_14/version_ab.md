# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51–61M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**Core architectural decision: per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

**The classifier is a contention point, not an abstraction.** Under FCM backpressure, the push queue backs up while the classifier continues routing into it. The classifier is stateless and horizontally scalable; the throughput ceiling is not the classifier itself but the coordination overhead of the priority decision. Section 2.3 analyzes classifier capacity under this scenario with numbers, not assertions, and specifies the backpressure propagation strategy.

**Circuit breaker threshold:** The P2 circuit breaker fires at **5,500/sec instantaneous throughput**—85% of the 6,400/sec provisioned ceiling. This threshold is derived from the throughput analysis in §1.1b, not chosen independently. The 85% trigger provides headroom for burst absorption before the ceiling is reached, while ensuring P0 and P1 delivery is protected before queue depth becomes critical. Shed P2 notifications are queued for the next off-peak window, not dropped. Section 2.4 analyzes the bounded failure mode of that deferred queue under sustained overload.

**The compound worst-case scenario is not protected by the circuit breaker.** The 50% DAU/MAU + 2-hour peak window + 3× burst scenario produces 15,300/sec—2.4× the provisioned ceiling. The circuit breaker fires at 5,500/sec, well below this level. Section 2.5 specifies what happens to the system when instantaneous demand exceeds 6,400/sec. This scenario requires three independent conditions to simultaneously occur at their pessimistic extremes; these conditions are not fully independent—a viral event is more likely on a high-engagement day—but the probability of all three simultaneously is materially lower than any individual condition. We accept this as a tail risk rather than a provisioning target, and name the failure mode explicitly rather than leaving it implicit.

**WebSocket scaling caveat stated upfront:** The horizontal WebSocket scaling described in §1.1a is valid only for the delivery model in scope at launch—server-push to a known connected user. It does not cover cross-instance fan-out, which is required when a notification targets a user whose connection is on a different instance. On a social app, this is the normal case: when user A's action generates a notification for user B, user B's connection is on an arbitrary instance. The launch architecture handles this by routing through the push channel when the target user's instance is unknown, accepting push latency rather than building cross-instance coordination before we have measured traffic. The trigger for adding Redis pub/sub cross-instance fan-out is explicit and tied to a measured threshold, not a calendar date: **if the month 2 review shows DAU/MAU ≥ 40%, cross-instance fan-out moves from deferred to in-sprint in month 3.** Scaling WebSocket instances beyond the baseline 6 without fan-out coordination would increase silent drop rate proportionally and is not permitted without fan-out in place.

**The P0 taxonomy is a prerequisite for the entire priority architecture**, not just SMS budgeting. The circuit breaker logic, priority classifier routing rules, and queue configuration all depend on a stable taxonomy. Section 3.1 specifies the taxonomy and the process for locking it. The taxonomy session is scheduled in week 1 and timeboxed to 3 hours. If it stalls, it escalates with a 48-hour resolution deadline. Infrastructure provisioning is not blocked for longer than one week in the worst case.

**Launch sequencing is explicit.** System launch occurs at end of month 4. Load testing occurs in month 3, before launch. The month 3 load test validates the system against synthetic traffic before real users are on it. If we wait until month 5 to load test, a real viral event before validation puts us in an unvalidated capacity region during the live launch window. The delivery plan in §7 specifies this sequencing; it is not left implicit.

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
| 40% | 4M | 20M | 56M | In-app consumers scaled ~33%; WebSocket pool expanded; cross-instance fan-out moves in-sprint |
| 50% | 5M | 25M | 61M | In-app consumers scaled ~67%; WebSocket pool expanded; cross-instance fan-out required before scaling proceeds |

**WebSocket sizing and its uncertainty:** The baseline connection pool is sized for 3M concurrent peak connections across 6 WebSocket server instances (500K connections per instance) using sticky sessions via the load balancer. The 500K connections-per-instance figure is a planning estimate derived from general reference architectures for Go-based WebSocket servers with minimal per-connection state. It is not validated for this specific application. Memory consumption per connection depends on what state is stored per connection, message frequency, TLS session overhead, and Go runtime goroutine stack allocation. The ~4GB RAM estimate (500K connections × ~8KB per connection) is reasonable for a minimal implementation but could be 2× higher if connection state is richer. The month 3 load test must validate this figure before DAU/MAU scaling triggers are acted upon.

**Sticky session failure mode:** When a WebSocket instance fails, all connections on that instance must reconnect. At 500K connections per instance, an instance failure triggers a reconnection storm against the remaining instances. Mitigations:

1. **Exponential backoff with jitter on client reconnect:** Clients randomize reconnect timing over 5–30 seconds. This is a client-side requirement specified in the mobile SDK contract (§4.2).
2. **Graceful drain before planned restarts:** Deployments drain connections over 60 seconds before terminating an instance, spreading reconnection load gradually. Enforced in the deployment runbook.
3. **Capacity headroom:** Baseline provisioning targets 60% utilization per instance, leaving 40% headroom to absorb reconnection load from a single failed instance. At 500K connections per instance and 6 instances, one failure adds ~120K connections to each remaining instance—within the headroom margin.
4. **Accepted residual risk:** An instance failure during a peak period, when remaining instances are already above 80% utilization, can cause cascading reconnection failures. This scenario is not fully mitigated; it is accepted as a known risk and monitored via the instance utilization alert in §6.3 (alert threshold: 75% utilization sustained for 5 minutes).

**Cross-instance fan-out limitation:** Without cross-instance fan-out, a notification for user B generated by user A's action is delivered via push if user B's connection is on a different instance. This is the normal case in a distributed deployment. The launch architecture accepts this degradation—in-app delivery falls back to push, which adds latency but does not lose the notification. Scaling WebSocket instances beyond the baseline 6 without fan-out in place would increase the silent drop rate proportionally; this is not permitted.

**Provisioning response by scenario:**

- **20–30% ratio:** Baseline provisioning. No action.
- **30–40% ratio:** Add in-app consumer instances to the existing queue. Configuration change, not architectural. Target: completed within 5 business days of month 2 traffic review.
- **40–50% ratio:** Scale in-app consumers and expand the WebSocket connection pool. Add Redis pub/sub for cross-instance fan-out before scaling WebSocket instances beyond the baseline 6. Validate revised per-connection memory consumption from month 3 load test before committing to instance count. Target: architectural review within 2 weeks of month 2 traffic review, provisioning changes deployed within 4 weeks.
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

The 2-hour scenario is not a tail risk. It is the result of morning and evening peaks not overlapping—a plausible structure for a social app. We provision to the 4-hour baseline but design the scaling path explicitly for the 2-hour scenario.

**Step 3: Determine the burst multiplier.**

The multiplier handles momentary intra-window spikes from viral events. The 3× figure is a planning estimate based on general knowledge of viral event patterns on social platforms; it is not derived from measurement. It is treated as a planning input and validated in month 3 load testing. The multiplier and the DAU/MAU ratio are not independent—a viral event is more likely on a high-engagement day, which means the compound scenario is correlated, not merely coincidental.

| Scenario | Sustained peak (4hr window) | Burst (3×) | Burst (2hr window, 3×) |
|----------|----------------------------|------------|------------------------|
| 30% DAU/MAU (baseline) | 2,125/sec | 6,375/sec | 12,750/sec |
| 50% DAU/MAU (high) | 2,550/sec | 7,650/sec | 15,300/sec |

**The compound worst-case scenario:** The 50% DAU/MAU + 2-hour window + 3× burst scenario produces **15,300/sec**—2.4× the provisioned ceiling of 6,400/sec. The circuit breaker fires at 5,500/sec, well below this level. Section 2.5 specifies what happens to the system when instantaneous demand exceeds 6,400/sec. We accept this as a tail risk rather than a provisioning target; the response when demand exceeds the provisioned ceiling is specified, not ignored.

**Design ceiling for provisioning:** 6,400/sec instantaneous, 2,125/sec sustained (baseline scenario). The 2-hour window and high-DAU scenarios are handled by the scaling path, not initial provisioning.

**Month 3 load test deliverables:**
1. Measured throughput ceiling under sustained 2,125/sec load for 4 hours.
2. Measured per-connection memory consumption for WebSocket instances under load.
3. Measured behavior at 6,400/sec instantaneous spike: queue depth growth rate, P0/P1 latency degradation, circuit breaker activation.
4. Measured behavior at 12,750/sec (2-hour window, 3× burst, baseline DAU): how far the system degrades and whether P0/P1 delivery is maintained.
5. Identification of the first component to saturate and its saturation threshold.
6. Go/no-go recommendation on the 3× multiplier assumption, with a revised estimate if the recommendation is no-go.

---

### 1.1c SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), unrestricted SMS is an existential budget problem. We restrict SMS to two categories.

**Category 1 — Auth and security (primary channel):** OTP, password reset, suspicious login alerts. 50,000/day × $0.0075 × 30 = **$11,250/month**. These are never suppressed by budget gates. This is a fixed cost of operating the app securely.

**Category 2