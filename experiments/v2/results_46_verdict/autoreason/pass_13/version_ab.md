# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51–61M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**Core architectural decision: per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

**This architecture does not eliminate the classifier as a contention point.** Under FCM backpressure, the push queue backs up while the classifier continues routing into it. Section 2.3 analyzes classifier capacity under this scenario and specifies the backpressure propagation strategy.

**Circuit breaker threshold:** The P2 circuit breaker fires at **5,500/sec instantaneous throughput**—85% of the 6,400/sec provisioned ceiling. This threshold is derived from the throughput analysis in §1.1b, not chosen independently. The 85% trigger provides headroom for burst absorption before the ceiling is reached, while ensuring P0 and P1 delivery is protected before queue depth becomes critical, not after. Shed P2 notifications are queued for the next off-peak window, not dropped. Section 2.4 analyzes the bounded failure mode of that deferred queue under sustained overload.

**WebSocket scaling caveat stated upfront:** The horizontal WebSocket scaling described in §1.1a is valid only for the delivery model in scope at launch—server-push to a known connected user. It does not cover cross-instance fan-out, which is required when a notification targets a user whose connection is on a different instance. On a social app, this is the normal case: when user A's action generates a notification for user B, user B's connection is on an arbitrary instance. The launch architecture handles this by routing through the push channel when the target user's instance is unknown, accepting push latency rather than building cross-instance coordination before we have measured traffic. The trigger for adding Redis pub/sub cross-instance fan-out is explicit: **if the month 2 review shows DAU/MAU ≥ 40%, cross-instance fan-out moves from deferred to in-sprint in month 3.** Scaling WebSocket instances beyond the baseline 6 without fan-out coordination would increase silent drop rate proportionally.

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

**WebSocket scaling scope and limitation:** The baseline connection pool is sized for 3M concurrent peak connections across 6 WebSocket server instances (500K connections per instance) using sticky sessions via the load balancer. Each instance requires approximately 4GB RAM for connection state at 500K connections. Horizontal scaling by adding instances is valid for the launch delivery model, where the server pushes to a user whose connection is known to be on the current instance.

It is not valid for cross-instance fan-out. Without cross-instance coordination, notifications routed to the wrong instance are silently dropped or fall back to push. The launch architecture deliberately accepts fallback-to-push behavior rather than building coordination infrastructure against unvalidated traffic patterns. The trigger for adding Redis pub/sub is explicit and tied to a measured threshold, not a calendar date.

**Provisioning response by scenario:**

- **20–30% ratio:** Baseline provisioning. No action.
- **30–40% ratio:** Add in-app consumer instances to the existing queue. Configuration change, not architectural. Target: completed within 5 business days of month 2 traffic review.
- **40–50% ratio:** Scale in-app consumers and expand the WebSocket connection pool. Add Redis pub/sub for cross-instance fan-out before scaling WebSocket instances beyond the baseline 6—scaling without fan-out coordination would increase silent drop rate proportionally. Target: architectural review within 2 weeks of month 2 traffic review, provisioning changes deployed within 4 weeks.
- **Above 50% ratio:** Outside modeled range. Trigger a full traffic model review immediately; do not apply the scaling rules above without re-deriving the model.

---

### 1.1b Peak Throughput Calculation

The daily volume figures above are inputs. The design ceiling requires a separate derivation—and the derivation has a known weakness that must be stated upfront.

**The fundamental problem:** The peak window assumption is load-bearing and unvalidated. We are provisioning infrastructure in months 1–2 based on a number we acknowledge we do not know. This section quantifies the consequence of being wrong and specifies the mitigation.

**Step 1: Identify the peak window.** Morning and evening peaks each occupy approximately 2 hours and together account for approximately 60% of daily volume. Whether these overlap into a 4-hour continuous window or remain distinct 2-hour windows is unknown. Both scenarios are modeled.

**Step 2: Calculate sustained throughput within the peak window.**

- **4-hour window (baseline assumption):** 51M × 0.60 / (4 × 3,600) = **~2,125/sec sustained**
- **2-hour window (pessimistic scenario):** 51M × 0.60 / (2 × 3,600) = **~4,250/sec sustained**

The 2-hour scenario is not a tail risk. It is the result of morning and evening peaks not overlapping—a plausible structure for a social app. We provision to the 4-hour baseline but design the scaling path explicitly for the 2-hour scenario.

**Step 3: Determine the burst multiplier.**

The multiplier handles momentary intra-window spikes from viral events. It does not address traffic model uncertainty—that is handled by the sensitivity analysis and the month 2 review. However, the multiplier and the DAU/MAU ratio are not independent: a viral event on a high-engagement day compounds both factors simultaneously.

| Scenario | Sustained peak (4hr window) | Burst (3×) | Burst (2hr window, 3×) |
|----------|----------------------------|------------|------------------------|
| 30% DAU/MAU (baseline) | 2,125/sec | 6,375/sec | 12,750/sec |
| 50% DAU/MAU (high) | 2,550/sec | 7,650/sec | 15,300/sec |

**The 3× burst multiplier is an estimate, not a derived figure.** It is reasonable based on general knowledge of viral event patterns on social platforms, but it carries real uncertainty. We treat it as a planning input and validate it in **month 3 load testing**, not month 5. The rationale: the system launches before month 5. A real viral event before validation puts us in an unvalidated capacity region during the live launch window. We move load testing to month 3, after the month 2 traffic review has produced measured peak window data to anchor the synthetic spike patterns. If month 3 testing shows the 3× multiplier is insufficient, we have months 4–6 to respond architecturally. If we wait until month 5, we have weeks.

**Design ceiling for provisioning:** 6,400/sec instantaneous, 2,125/sec sustained (baseline scenario). The 2-hour window and high-DAU scenarios are handled by the scaling path, not initial provisioning. The circuit breaker at 5,500/sec is the safety valve for the gap between provisioned ceiling and validated capacity.

**Month 3 load test deliverables:**
1. Measured throughput ceiling under sustained 2,125/sec load for 4 hours.
2. Measured behavior at 6,400/sec instantaneous spike: queue depth growth rate, P0/P1 latency degradation, circuit breaker activation.
3. Identification of the first component to saturate and its saturation threshold.
4. Go/no-go recommendation on the 3× multiplier assumption, with a revised estimate if the recommendation is no-go.

---

### 1.1c SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), unrestricted SMS is an existential budget problem. We restrict SMS to two categories.

**Category 1 — Auth and security (primary channel):** OTP, password reset, suspicious login alerts. 50,000/day × $0.0075 × 30 = **$11,250/month**. These are never suppressed by budget gates. This is a fixed cost of operating the app securely.

**Category 2 — P0 push fallback:** SMS sent when push delivery fails after retry exhaustion for P0-classified notifications.

**Note on circular dependency with §3.1 taxonomy:** The budget scenarios below assume P0 volume percentages that depend on the notification taxonomy defined in §3.1. The taxonomy does not exist yet. Taxonomy definition is not a bounded engineering task—it is a product negotiation. What qualifies as P0 determines SMS spend, and product owners have financial and UX incentives that may conflict with engineering's cost constraints. The negotiation has no guaranteed timeline.

We schedule the taxonomy session in week 1 and timebox it to 3 hours. If the session does not produce a stable P0 definition within that window, the session chair escalates to the product owner with a written summary of unresolved disagreements and a 48-hour deadline for resolution. Infrastructure provisioning for SMS is blocked until resolution. This adds at most one week to the schedule in the worst case; it is preferable to provisioning against a definition that gets renegotiated after launch.

**Full sensitivity matrix:**

| P0 volume | Push failure rate | P0 SMS fallback/day | Monthly cost (fallback only) |
|-----------|-----------------|---------------------|------------------------------|
| 1% (210K/day) | 5% | 10,500 | $2,363 |
| 1% (210K/day) | 10% | 21,000 | $4,725 |
| 1% (210K/day) | 20% | 42,000 | $9,450 |
| **2% (420K/day)** | **10%** | **42,000** | **$9,450** |
| 2% (420K/day) | 20% | 84,000 | $18,900 |
| 5% (1.05M/day) | 10% | 105,000 | $23,625 |
| **5% (1.05M/day)** | **20%** | **210,000** | **$47,250** |

The 5% P0 volume / 20% failure rate scenario produces $47,250/month in fallback costs alone, plus $11,250 for auth/security = **$58,500/month total**. This is reachable under normal operational parameters, not a tail risk.

**Budget terminology — target vs. ceiling used precisely:**

- **Operational target ($25,000/month):** The spend level below which no escalation fires. A planning goal, not a hard limit.
- **Escalation threshold ($15,000/month for P0 fallback):** The spend level at which on-call engineering is paged.
- **Hard ceiling:** There is no automated hard ceiling on auth/security SMS. Automated suppression based on a spend counter is a security control failure—an attacker who generates sufficient SMS volume could disable OTP delivery. The ceiling on security-critical SMS is enforced by the type gate (only allowlisted notification types may use SMS as primary channel), not by a spend counter.

**Tiered response:**

- **Tier 1 — Auth/security SMS:** Unconditionally delivered. Exempt from all budget gates. Fixed cost: $11,250/month.
- **Tier 2 — P0 DM and service alert fallback:** Budget-gated with escalation, not suppression. When monthly P0 fallback spend exceeds $15,000, the system pages on-call engineering. When it exceeds $25,000, it escalates to engineering leadership. At no point are P0 DM or service alert notifications suppressed without an explicit human decision. The on-call engineer has three options: (1) investigate and remediate the underlying push failure rate, (2) explicitly approve continued spend with a stated ceiling, or (3) reclassify some notification types from P0 to P1, removing their SMS fallback eligibility—a product decision requiring product owner sign-off.

**Escalation gap acknowledgment:** The escalation tiers do not guarantee the underlying cause gets resolved. The $47,250/month scenario is reachable even if all escalation steps fire correctly. The mitigation is not more escalation tiers—it is making the on-call engineer's investigation tractable. The monitoring dashboard (§6.3) surfaces the specific failure mode driving spend: token staleness rate, device-state failure rate, and FCM/APNs error rate are broken out separately so the on-call engineer can identify the cause within 5 minutes. If the cause is token staleness (the most common case), the remediation is a push token validation sweep, which is a documented runbook action.

**Gate enforcement in the channel dispatcher:**

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fall