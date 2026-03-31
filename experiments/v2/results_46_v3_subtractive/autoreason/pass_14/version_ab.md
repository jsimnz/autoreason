# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

**Priority queue model redesigned.** Weighted fair queuing is replaced with priority-aware worker pools. P0/P1 items are processed by dedicated workers that never touch P3 items. This eliminates the mathematical fiction that probability weights provide meaningful priority guarantees under concurrency.

**Email batching enforcement rationalized.** The batching window is retained for digest grouping (a product requirement), not throughput. The 1.02× average throughput reduction does not justify enforcement overhead. The window is a product configuration parameter with lightweight change management.

**Follower notification launch gate formalized.** The dependency between follower notification enablement and infrastructure capacity is a documented launch gate requiring sign-off from engineering lead and product lead.

**TCPA residual risk explicitly quantified and escalated.** The bus factor remediation reduces operational risk. The legal liability residual — simultaneous unavailability of both E1 and E3 — is named, quantified, and escalated to a business decision. Engineering cannot close this risk unilaterally. The engineering recommendation is fail-closed SMS during suppression cache failure, converting a compliance risk into a delivery degradation.

**Fanout rate limit is derived, not asserted.** 2,000 events/second, calculated from P3 worker pool capacity and headroom constraints.

**Global opt-out and channel-level opt-in are independent flags** evaluated multiplicatively. This is an architectural constraint on the preference data model, not an assumption. E3 owns the schema; any change to evaluation order requires a traffic model review.

**Email worker capacity is specified concretely.** The 5-minute minimum batching window threshold is derived from SES API latency estimates and worker processing time, not asserted.

**P3 delivery latency SLA is specified.** The launch gate checklist references a concrete value.

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20%) while using 30% as the planning baseline.
- Suppression cache silent failure modes (stale cache, partial failure) are not fully addressed by the fail-closed recommendation. The residual risk and architectural constraint that mitigates it are specified in Section 1.6.1.

**What we are not building:** ML send-time optimization, A/B testing infrastructure, per-user engagement scoring, real-time analytics dashboards, global event sequencing guarantees, follower fanout notifications at launch.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU planning baseline — see Section 1.1.1 |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |
| Fanout multiplier | 1.2 (standard) | See Section 1.5; explicitly excludes follower fanout |
| Raw recipient-notification events/day | ~18M | 15M × 1.2 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~14.4M | 18M × 0.80 |

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%) and sized to handle the optimistic scenario (50%) with horizontal scaling — no architectural changes required.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 9.6M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 14.4M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 24M | Worker pool recount required; see Section 1.1.2 |

If the product launches with features that push actions-per-DAU above 8, the traffic model must be recalculated before those features ship. E1 owns flagging this threshold.

#### 1.1.2 Worker Pool Recount at Optimistic Volume

Proportional scaling of the worker pool is not sufficient at optimistic volume for two reasons: (1) the fanout rate limit reservation (50% of P3 capacity) is a ratio, so it scales with the worker pool and does not change the headroom ratio; (2) burst absorption depends on absolute queue depth, not relative capacity, so higher volume requires additional buffer beyond proportional scaling.

At 50% DAU/MAU (24M routed events/day), the P3 worker pool is estimated at 22 workers (versus 8 at pessimistic) rather than 20 (2.5×), to maintain the same burst absorption margin. Section 2.1 derives the pessimistic pool sizes; the optimistic recount applies the same methodology at 2.5× input volume plus a 10% burst buffer.

P0 and P1 worker pools are not sensitive to this volume change because their event rates are determined by action types (security alerts, direct messages), not by linear DAU scaling. P2 worker pool scales with DAU volume and requires a recount at optimistic volume using the same methodology as P3.

### 1.2 Channel Distribution and Preference Model

#### 1.2.1 Independence of Global Opt-Out and Channel-Level Opt-In

**This is an architectural constraint, not an assumption.** Global opt-out and channel-level opt-in are stored as independent boolean flags in the user preference store. Evaluation order at routing time is:

1. Check global opt-out flag. If set, no notifications are sent on any channel. Processing stops.
2. For each candidate channel, check channel-level opt-in flag. If not set, skip that channel.
3. Apply notification-type preferences (see Section 3.3).

The volume calculations below treat these flags as compounding multiplicatively because that is how the routing logic evaluates them. Any change to evaluation order requires a traffic model review by E1. E3 owns the preference store schema and routing evaluation logic.

**Consequence for in-app channel:** In-app is not disableable at the channel level. The in-app channel opt-in flag is always set. Global opt-out still applies. The 14.4M routed events/day figure is the correct in-app delivery volume because routed events already have global opt-out applied.

#### 1.2.2 Channel Volumes

Channel opt-in rates among users who have not globally opted out (8M users at baseline):

| Channel | Opt-In Rate | Eligible Users | Notes |
|---------|------------|----------------|-------|
| In-app | 100% | 8M | Not disableable at channel level; global opt-out applies |
| Push | 65% | 5.2M | Device token required |
| Email | 20% | 1.6M | Address required |
| SMS | <0.01% | <800 | Explicit opt-in; TCPA governed |

Email opted-in user count: 10M × 0.80 × 0.20 = 1.6M. This compounds correctly: channel opt-in is evaluated only after global opt-out is confirmed not set.

Expected delivery events per routed notification event: 1 + 0.65 + 0.20 + ~0 = **1.85 channels/user**.

Total delivery events/day: 14.4M × 1.85 = **~26.6M** (baseline). Pessimistic: ~17.8M. Optimistic: ~44.4M.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 14.4M | ~500 |
| Push | 9.4M | ~325 |
| Email (pre-batch) | 2.9M | ~100 |
| SMS | ~1,500 | negligible |

### 1.3 Email Batching

#### 1.3.1 Two Separate Justifications

**Argument 1 — Digest grouping (product requirement):** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement independent of throughput. A batching window is required to implement it. This is the primary reason the batching window exists.

**Argument 2 — Throughput impact (infrastructure consideration):** The batching window has approximately 1.02× average throughput reduction across all opted-in users. This is not a meaningful infrastructure benefit and does not justify the batching window on infrastructure grounds. It also does not argue against it — the window is retained for the digest grouping reason above.

These arguments are independent. The configuration management policy is based on Argument 1.

#### 1.3.2 Throughput Analysis

```
Email opted-in users: 1.6M
Email delivery events/day: 2.9M

Average events per opted-in user per day:
  2.9M ÷ 1.6M = 1.81 events/user/day

λ per 30-minute window = 1.81 / 48 = 0.038 events/window

P(at least one event in window) = 1 - e^(-0.038) ≈ 0.037
Expected emails/user/day = 48 × 0.037 = 1.78
Reduction factor: 1.81 / 1.78 ≈ 1.02×
```

For high-engagement users receiving 20 events/day (λ = 0.42/window), the per-user reduction is approximately 1.7×. Aggregate reduction is bounded between 1.02× and approximately 1.4×. Infrastructure is sized for the lower bound.

#### 1.3.3 Configuration Management and Minimum Window Threshold

The batching window is a product configuration parameter. Changes require:

1. Code review from one engineer confirming the new value is within bounds (minimum 5 minutes, maximum 4 hours).
2. No recalculation job. No P1 alert. No paging.
3. Window changes are logged in the deployment record.

**The 5-minute minimum threshold — derivation:**

Email workers process batched events by: (a) reading accumulated events from the batch store, (b) rendering the digest template, (c) making the SES API call, (d) writing the delivery record.

| Step | Estimated Latency |
|------|------------------|
| Batch store read (Redis, 10–50 events) | 2–5ms |
| Template rendering | 5–15ms |
| SES API call (p50) | 80–120ms |
| Delivery record write | 5–10ms |
| **Total per email** | **~100–150ms** |

At a 5-minute window with 4 email workers, each worker handles approximately 8,300 emails per window. At 150ms per email, that is approximately 1,250 seconds of processing time per worker per 300-second window — 4 workers cannot keep pace and would require approximately 17. The 5-minute threshold therefore triggers a worker pool review before the change merges, not an automatic rejection. Below 5 minutes, the window also interacts with digest grouping: events that should be grouped arrive after the window closes.

**Note on the current 30-minute window:** At 30 minutes, each of 4 email workers handles ~8,300 emails per 1,800-second window. At 150ms per email, processing time is approximately 1,245 seconds — within the window with margin. If SES p95 latency reaches 300ms, processing time rises to ~2,490 seconds, exceeding the window. E4 owns a latency alert on SES p95 that pages if it exceeds 200ms sustained for more than 5 minutes.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Fanout Multiplier, High-Follower Path, and Rate Limit

#### 1.5.1 The 1.2 Multiplier

For a social app where most interactions are direct, the average notification recipients per action is close to 1. A like notifies one person. A reply notifies one person. A follow notifies one person. The 1.2 multiplier accounts for actions that notify slightly more than one person on average (e.g., tagging multiple users). This multiplier explicitly excludes follower fanout.

#### 1.5.2 High-Follower Fanout Path (>500 Followers)

Users with more than 500 followers are flagged in the user profile store. When a flagged user takes a feed-generating action:

- The ingestion API detects the high-follower flag at event time.
- The event is routed to a `fanout:high_volume` queue.
- A dedicated fanout worker reads the follower list in batches of 1,000 and enqueues individual P3 notification events.
- These events enter the standard pipeline at P3 priority and are subject to all normal preference filtering and suppression checks.
- The fanout job has a maximum output rate of 2,000 events/second (derived in Section 1.5.3).

The 500-follower threshold is configurable. E1 owns this configuration.

#### 1.5.3 Fanout Rate Limit — Derivation

**Inputs:**
- Standard P3 worker pool: 8 workers (see Section 2.1 for sizing derivation)
- Each P3 worker processes approximately 500 events/second (~2ms processing time including preference lookup and queue write)
- P3 worker pool total capacity: 8 × 500 = 4,000 events/second
- Target: fanout output should not consume more than 50% of P3 worker capacity, leaving headroom for organic P3 events

**Fanout rate limit: 2,000 events/second.**

**P3 delivery latency SLA:** P3 notifications are expected to be delivered within 15 minutes of enqueue under normal load. This is the value referenced in the follower notification launch gate checklist.

**Delivery latency at scale:** For a user with 100,000 followers, the fanout job takes 50 seconds to enqueue all events. P3 workers process those events at 2,000 events/second (the non-fanout half of pool capacity), clearing in approximately 50 seconds after enqueue completes — well within the 15-minute SLA.

For a user with 500,000 followers, enqueue takes ~250 seconds. Clearance at 2,000 events/second takes ~250 seconds after that, for a total of ~500 seconds (~8 minutes). Still within the 15-minute SLA, but with limited margin. If the product launches follower notifications with users at this scale, the P3 worker pool must be resized. This is a known constraint documented here so the decision is explicit.

#### 1.5.4 Follower Notification Launch Gate

Enabling follower notifications requires sign-off before the feature flag is enabled in production:

| Item | Owner | Sign-off Required From |
|------|-------|----------------------|
| Traffic model recalculated for new volume | E1 | Engineering lead |
| Worker pool counts revised and provisioned | E1, E4 | Engineering lead |
| P3 queue capacity validated at new volume | E4 | Engineering lead |
| Fanout rate limit validated against new worker pool | E1 | Engineering lead |
| P3 delivery latency SLA confirmed acceptable for tail cases | Product | Product lead |
| Infrastructure cost delta approved | Engineering lead | Product lead or budget owner |

The feature flag for follower notifications is owned by E1. Enabling it in production without completing this checklist is a process violation.

### 1.6 Team Allocation

#### 1.6.1 TCPA Compliance — Residual Risk

**Fail-closed recommendation and its limits:**

The engineering recommendation is that the SMS sending path fails closed during any suppression cache failure: if the cache cannot be read, SMS sending halts rather than proceeding without suppression verification. This converts a compliance risk into a delivery degradation, which is operationally manageable.

**Architectural constraint required for fail-closed to work:** The suppression cache must be a replica of a durable store (e.g., a Redis read-through cache backed by the preference database), not the authoritative source. This means:

- On cache miss or read failure, the system can fall back to