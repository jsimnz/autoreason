# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51–61M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

**This architecture does not eliminate the classifier as a contention point.** Under FCM backpressure, the push queue backs up while the classifier continues routing into it. Section 2.3 analyzes classifier capacity under this scenario specifically and specifies the backpressure propagation strategy.

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
| **Total/day (launch, 30% ratio)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target, 30% ratio)** | **~51M** | Sum across channels at target frequency |
| **Total/day (target, 50% ratio)** | **~61M** | High-engagement scenario; see §1.1a |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals. Section 1.1a specifies exactly what gets re-provisioned if actuals diverge materially.

---

### 1.1a DAU/MAU Ratio Sensitivity Analysis

The 30% DAU/MAU ratio is the single assumption doing the most work in this model. A messaging-first app and a photo-sharing app have meaningfully different ratios—industry data shows 20–55% across social app categories. We cannot know our ratio before launch. This section bounds the error and states the provisioning response for each scenario.

**Why 30% as the planning baseline:** We use 30% because it is the conservative end of the range for social apps with active engagement loops. A lower ratio is possible for more passive consumption apps; we are not building one. If we are wrong low, we over-provision in-app capacity—a recoverable error. If we are wrong high, we under-provision—the more dangerous error, which is why we model it explicitly.

**Sensitivity table:**

| DAU/MAU ratio | DAU | In-app volume/day | Total/day (target) | Infrastructure delta vs. baseline |
|---------------|-----|-------------------|--------------------|----------------------------------|
| 20% | 2M | 10M | 46M | Under-provisioned; in-app consumers can be reduced |
| **30% (baseline)** | **3M** | **15M** | **51M** | **Design baseline** |
| 40% | 4M | 20M | 56M | In-app queue consumers scaled up ~33%; WebSocket pool expanded—see §1.1a WebSocket note |
| 50% | 5M | 25M | 61M | In-app consumers scaled up ~67%; WebSocket pool expanded; sustained peak rate increases ~20% |

**WebSocket scaling note for 40–50% ratio scenarios:** The baseline connection pool is sized for 3M concurrent peak connections, distributed across 6 WebSocket server instances (500K connections per instance) using sticky sessions via the load balancer. Each instance requires approximately 4GB RAM for connection state at 500K connections, using a process-per-core model. When the DAU/MAU ratio exceeds 40%, we add instances to the pool and update the load balancer configuration—no shared session state is required because connection affinity is maintained at the load balancer layer. The specific constraint is per-instance connection count, not aggregate throughput. Horizontal scaling is valid here because WebSocket connections are stateless between messages; the only state is the connection itself, which is bound to a single instance. If we later need cross-instance fan-out (e.g., broadcasting to a user connected to a different instance than the one receiving the event), we add a Redis pub/sub layer at that point. We do not add it now because it introduces a new failure dependency for a scenario we haven't validated.

**Provisioning response by scenario:**

The in-app channel is the only one materially affected by DAU/MAU variation—push volume is bounded by push-eligible users (7M), email is not DAU-driven, and SMS is restricted by policy.

- **20–30% ratio:** Baseline provisioning. No action.
- **30–40% ratio:** Add in-app consumer instances to the existing queue. This is a configuration change, not an architectural one. Target: completed within 5 business days of month 2 traffic review confirming the ratio.
- **40–50% ratio:** Scale in-app consumers and expand the WebSocket connection pool per the note above. If sustained peak rate exceeds 2,500/sec (our 20% headroom above the baseline ceiling), re-evaluate the burst multiplier. Target: architectural review within 2 weeks of month 2 traffic review, provisioning changes deployed within 4 weeks.
- **Above 50% ratio:** Outside our modeled range. Trigger a full traffic model review immediately; do not apply the scaling rules above without re-deriving the model.

**Month 2 traffic review structure:** This review has a defined owner, format, and consequence mechanism—not just a list of deliverables. See §1.1d for the full specification.

---

### 1.1b Peak Throughput Calculation

The daily volume figures above are inputs. The design ceiling requires a separate derivation—and the derivation has a known weakness that must be stated upfront.

**The fundamental problem:** The peak window assumption is load-bearing and unvalidated. We do not know whether peak traffic is concentrated in a 4-hour window or a 2-hour window. We are provisioning infrastructure in months 1–2 based on a number we acknowledge we do not know. This section quantifies the consequence of being wrong and specifies the pre-launch mitigation.

**Step 1: Identify the peak window.** Morning and evening peaks each occupy approximately 2 hours and together account for approximately 60% of daily volume across a 4-hour window. This is an assumption we will validate in month 2. The 4-hour window and 60% concentration are planning inputs, not validated measurements.

**Step 2: Calculate sustained throughput within the peak window.**

- **4-hour window (baseline assumption):** 51M × 0.60 / (4 × 3,600) = **~2,125/sec sustained**
- **2-hour window (pessimistic scenario):** 51M × 0.60 / (2 × 3,600) = **~4,250/sec sustained**

The 2-hour scenario is not a tail risk. It is the result of the two daily peaks not overlapping—a plausible structure for a social app where morning and evening activity are distinct rather than continuous. We provision to the 4-hour baseline but design the scaling path for the 2-hour scenario.

**Step 3: Determine the burst multiplier.**

The multiplier serves one purpose: handling momentary intra-window spikes from viral events. It does not address traffic model uncertainty—that is handled by the sensitivity analysis and the month 2 review.

**However, the multiplier and the DAU/MAU ratio are not independent.** A viral event on a day with 50% DAU engagement produces compounded load: higher baseline throughput (from the higher DAU) multiplied by the viral spike factor. The correct analysis is:

| Scenario | Sustained peak (4hr window) | Burst (3×) | Burst (2hr window, 3×) |
|----------|----------------------------|------------|------------------------|
| 30% DAU/MAU (baseline) | 2,125/sec | 6,375/sec | 12,750/sec |
| 50% DAU/MAU (high) | 2,550/sec | 7,650/sec | 15,300/sec |

**The 3× burst multiplier is an estimate, not a derived figure.** We do not have incident report data from systems at exactly this scale. The figure is reasonable based on general knowledge of viral event patterns on social platforms, but it carries real uncertainty. We treat the 3× figure as a planning input, validate it in month 5 load testing using synthetic viral spike patterns, and accept that if a real viral event exceeds 3× before month 5, we will be operating in an unvalidated region.

**Design ceiling for provisioning:** 6,400/sec instantaneous, 2,125/sec sustained (baseline scenario). The 2-hour window scenario and the high-DAU scenario are handled by the scaling path, not by initial provisioning.

**Pre-launch mitigation for provisioning risk:** Because we are provisioning before month 2 data is available, we implement a circuit breaker at the classifier that sheds P2 notifications when instantaneous throughput exceeds 4,000/sec. This is not a graceful degradation strategy—it is a safety valve that prevents P0 and P1 notifications from being delayed by P2 volume during a traffic event that exceeds our provisioned ceiling. P2 notifications that are shed are queued for delivery in the next off-peak window, not dropped. The 4,000/sec threshold is reconfigured after month 2 data is available.

---

### 1.1c SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), unrestricted SMS would be an existential budget problem. We restrict SMS to two categories:

**Category 1 — Auth and security (primary channel):** OTP, password reset, suspicious login alerts. 50,000/day × $0.0075 × 30 = **$11,250/month**. These are never suppressed by budget gates.

**Category 2 — P0 push fallback:** SMS sent when push delivery fails after retry exhaustion for P0-classified notifications.

**Note on circular dependency:** The budget scenarios below assume P0 volume percentages (1%, 2%, 5%) that depend on the notification taxonomy defined in §3.1. The taxonomy does not exist yet. This means the budget analysis is built on an unvalidated classification. The response: the budget analysis is treated as a planning estimate that must be rerun after the day-1 taxonomy session (§3.1). If the day-1 session produces a P0 definition narrower or broader than the 2% baseline, the budget scenarios are recalculated before infrastructure decisions are finalized. The infrastructure decisions that depend on this analysis—specifically, the SMS gateway capacity provisioning and the escalation thresholds—are not finalized until the rerun is complete. This adds at most 2 days to the week 1 schedule.

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

The 5% P0 volume / 20% failure rate scenario produces $47,250/month in fallback costs alone, plus $11,250 for auth/security = **$58,500/month total**. This is not a tail-risk scenario; it is reachable under normal operational parameters.

**Tiered response:**

- **Tier 1 — Auth/security SMS:** Unconditionally delivered. Exempt from all budget gates. Fixed cost: $11,250/month.
- **Tier 2 — P0 DM and service alert fallback:** Budget-gated with escalation, not suppression. When monthly P0 fallback spend exceeds $15,000, the system pages on-call engineering. When it exceeds $25,000, it escalates to engineering leadership.

**Escalation gap acknowledgment:** The escalation tiers above do not guarantee the underlying cause gets resolved. An on-call engineer paged at 3am may approve continued spend without investigating, or may not respond within the escalation window. The $47,250/month scenario can be reached even if all escalation steps fire correctly. The mitigation is not to add more escalation tiers—it is to make the on-call engineer's investigation tractable. The monitoring dashboard (§6.3) surfaces the specific failure mode driving spend: token staleness rate, device-state failure rate, and FCM/APNs error rate are broken out separately so the on-call engineer can identify the cause within 5 minutes. If the cause is token staleness (the most common case), the remediation is to run a push token validation sweep, which is a documented runbook action. We do not pretend the escalation structure prevents runaway spend; we make remediation fast enough that spend doesn't run away for long.

**Budget ceiling for planning:** $25,000/month operational target, with no automated hard cap on security-critical notifications. Automated suppression of security notifications based on a spend counter is a security control failure. The ceiling is enforced through human escalation with fast-path remediation tooling.

**Month 2 action:** Measure actual P0 volume as a fraction of push volume. If it exceeds 3%, initiate a P0 classification review.

---

### 1.1d Month 2 Traffic Review — Structure and Enforcement

The month 2 review is the primary mechanism for correcting the provisioning decisions made under uncertainty in months 1–2. For it to be useful, it must have a defined owner, a defined format, and a defined consequence for incomplete output.

**Owner:** E4. Not "the team." E4 is responsible for producing the review deliverables and for scheduling the review meeting. If E4 is unavailable during week 1 of month 2, E1 assumes ownership for that week.

**Format:** A 90-minute synchronous meeting with all four engineers present. Asynchronous review is not acceptable for this review cycle because the provisioning decisions that follow require real-time discussion of tradeoffs. Subsequent quarterly reviews may be asynchronous.

**Quorum:** All four engineers. If one engineer is unavailable, the meeting is rescheduled within 48 hours. If rescheduling within 48 hours is impossible, the meeting proceeds with three engineers and the absent engineer is briefed synchronously within 24 hours of the meeting.

**Required deliverables (the meeting is not complete without all four):**

1. Measured DAU/MAU ratio with 90% confidence interval, based on at least 3 weeks of instrumented data.
2. Measured peak window concentration: what fraction of daily volume occurs in the highest-traffic 2-