# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months — Revision 3

---

## Executive Summary

This revision addresses nine specific findings from the prior review. Each is addressed directly.

**Finding 1 (Worker pool sizing is circular): Resolved.** Section 2.1 now derives worker pool counts from first principles — processing time estimates, target queue depth, and headroom constraints — before using those counts in the fanout rate limit derivation. The prior truncation is corrected.

**Finding 2 (5% weight contradicts the architectural model): Resolved.** The "5% weight" was a remnant of the discarded weighted fair queuing model. Under the priority-aware worker pool model, P3 throughput during fanout is calculated from the number of P3-tier workers and their processing capacity, not from a probability weight. Section 1.5.3 is recalculated accordingly.

**Finding 3 (Email batching analysis conflates two claims): Resolved.** The throughput analysis and the digest grouping justification are now presented as separate arguments. The 5-minute minimum threshold is justified with a concrete email worker processing latency figure, not an assertion.

**Finding 4 (Opt-out rate applied inconsistently): Resolved.** The document now specifies explicitly that global opt-out and channel-level opt-in are stored and evaluated as independent flags, that they compound multiplicatively in volume calculations, and that this is an architectural constraint on the preference data model, not an assumption.

**Finding 5 (Fail-closed SMS has unexamined failure mode): Resolved.** Section 1.6.1 now specifies the suppression cache architecture (cache as replica of durable store, not authoritative source), the failure detection mechanism, detection latency, and which failure modes the fail-closed recommendation does and does not address. Silent failure modes are named.

**Finding 6 (42-minute P3 clearance accepted without a SLA to sign off against): Resolved.** A P3 delivery latency SLA is now specified. The launch gate checklist references a concrete value rather than an undefined target.

**Finding 7 (Token invalidity ownership gap): Resolved.** The in-flight notification disposition on token invalidity is now specified. The ownership boundary is redrawn to eliminate the gap between E2's detection and E3's consumption.

**Finding 8 (DAU/MAU scaling claim is internally inconsistent): Resolved.** The linear scaling claim is corrected. The optimistic scenario worker pool recount accounts for changed headroom assumptions and is worked through explicitly.

**Finding 9 (Section 2.1 truncated): Resolved.** Section 2.1 is complete. The priority-aware worker pool model is fully specified, including pool sizes, queue topology, and the argument for why it bounds P0 wait time where weighted fair queuing did not.

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20% DAU/MAU) while using 30% as the planning baseline.
- Suppression cache silent failure modes (stale cache, partial failure) are not fully addressed by the fail-closed recommendation. The residual risk and the architectural constraint that mitigates it are specified in Section 1.6.1.

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

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%) and sized to handle the optimistic scenario (50%) with horizontal scaling — no architectural changes required. The worker pool recount for the optimistic scenario is worked through in Section 1.1.2.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 9.6M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 14.4M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 24M | Worker pool recount required; see Section 1.1.2 |

If the product launches with features that push actions-per-DAU above 8, the traffic model must be recalculated before those features ship. E1 owns flagging this threshold.

#### 1.1.2 Worker Pool Recount at Optimistic Volume

The prior version claimed optimistic volume requires "approximately 2.5× the pessimistic worker pool counts" and treated this as proportional scaling. This is incorrect for two reasons: (1) the fanout rate limit reservation (50% of P3 capacity) is not a fixed overhead — it scales with the worker pool, so proportional scaling of the worker pool does not change the headroom ratio; (2) the queue depth constraints at higher volume require more total headroom, not just proportionally more workers, because burst absorption depends on absolute queue depth, not relative capacity.

The correct statement: at 50% DAU/MAU (24M routed events/day), the P3 worker pool must be sized to handle 2.5× the pessimistic event volume at the same headroom ratio. Because the headroom reservation is a ratio (50% of P3 capacity reserved for non-fanout P3 events), the worker pool count scales proportionally with volume for that component. However, the burst absorption requirement — maintaining queue depth below the TTL threshold during a traffic spike — requires an additional buffer. The P3 worker pool at optimistic volume is estimated at 22 workers (versus 8 at pessimistic), not 20 (2.5×), to maintain the same burst absorption margin. Section 2.1 derives the pessimistic pool sizes; the optimistic recount applies the same methodology at 2.5× input volume plus a 10% burst buffer.

P0 and P1 worker pools are not sensitive to this volume change because their event rates are determined by action types (security alerts, direct messages), not by DAU volume scaling linearly. P2 worker pool scales with DAU volume and requires a recount at optimistic volume using the same methodology as P3.

### 1.2 Channel Distribution and Preference Model

#### 1.2.1 Independence of Global Opt-Out and Channel-Level Opt-In

**This is an architectural constraint, not an assumption.** Global opt-out and channel-level opt-in are stored as independent boolean flags in the user preference store. Evaluation order at routing time is:

1. Check global opt-out flag. If set, no notifications are sent on any channel. Processing stops.
2. For each candidate channel, check channel-level opt-in flag. If not set, skip that channel.
3. Apply notification-type preferences (see Section 3.3).

The volume calculations below treat these flags as compounding multiplicatively because that is how the routing logic evaluates them. If the preference store or routing logic were changed to evaluate them differently, the volume calculations would need to be recalculated. E3 owns the preference store schema and routing evaluation logic; any change to evaluation order requires a traffic model review by E1.

**Consequence for in-app channel:** In-app is listed at 100% opt-in and is not disableable at the channel level. This means the in-app channel opt-in flag is always set for all users. Global opt-out still applies to in-app. The 8M figure (10M × 0.80) is the number of users for whom in-app notifications are eligible. The 14.4M routed events/day figure is the correct volume for in-app delivery because routed events already have global opt-out applied.

#### 1.2.2 Channel Volumes

Channel opt-in rates are rates among users who have not globally opted out (8M users at baseline):

| Channel | Opt-In Rate | Eligible Users | Notes |
|---------|------------|----------------|-------|
| In-app | 100% | 8M | Not disableable at channel level; global opt-out applies |
| Push | 65% | 5.2M | Device token required |
| Email | 20% | 1.6M | Address required |
| SMS | <0.01% | <800 | Explicit opt-in; TCPA governed |

Email opted-in user count: 10M × 0.80 × 0.20 = 1.6M. This compounds correctly: channel opt-in is evaluated only after global opt-out is confirmed not set.

Expected delivery events per routed notification event: 1 (in-app) + 0.65 (push) + 0.20 (email) + ~0 (SMS) = **1.85 channels/user**.

Total delivery events/day: 14.4M × 1.85 = **~26.6M** (baseline). Pessimistic: 9.6M × 1.85 = ~17.8M. Optimistic: 24M × 1.85 = ~44.4M.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 14.4M | ~500 |
| Push | 9.4M | ~325 |
| Email (pre-batch) | 2.9M | ~100 |
| SMS | ~1,500 | negligible |

### 1.3 Email Batching

#### 1.3.1 Two Separate Justifications for Retaining a Batching Window

The prior version presented the throughput analysis as the basis for the configuration management decision. This conflated two separate arguments. They are separated here.

**Argument 1 — Digest grouping (product requirement):** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement independent of throughput. A batching window is required to implement it. This is the primary reason the batching window exists.

**Argument 2 — Throughput impact (infrastructure consideration):** The batching window has approximately 1.02× average throughput reduction across all opted-in users. This is not a meaningful infrastructure benefit. It does not justify the batching window on infrastructure grounds. It also does not argue against the batching window — the window is retained for the digest grouping reason above, and the throughput impact is small enough to be irrelevant in either direction.

These arguments are independent. The configuration management policy in Section 1.3.2 is based on Argument 1. The throughput analysis informs the minimum window threshold but does not determine whether batching exists.

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

For high-engagement users receiving 20 events/day (λ = 0.42/window), the per-user reduction is approximately 1.7×. The aggregate reduction across all users is bounded between 1.02× (lower bound, average user) and approximately 1.4× (estimated upper bound). Infrastructure is sized for the lower bound.

#### 1.3.3 Configuration Management and Minimum Window Threshold

The batching window is a product configuration parameter. Changes require:

1. Code review from one engineer confirming the new value is within bounds (minimum 5 minutes, maximum 4 hours).
2. No recalculation job. No P1 alert. No paging.
3. Window changes are logged in the deployment record.

**The 5-minute minimum threshold — derivation, not assertion:**

Email workers process batched events by: (a) reading accumulated events from the batch store, (b) rendering the digest template, (c) making the SES API call, and (d) writing the delivery record. Steps (a) through (d) have the following latency estimates based on comparable SES integrations:

| Step | Estimated Latency |
|------|------------------|
| Batch store read (Redis, 10–50 events) | 2–5ms |
| Template rendering | 5–15ms |
| SES API call (p50) | 80–120ms |
| Delivery record write | 5–10ms |
| **Total per email** | **~100–150ms** |

At a 5-minute batching window, the email worker pool processes approximately 1.6M users / (48 windows/day × workers) emails per window. With 4 email workers (see Section 2.1), each worker handles approximately 8,300 emails per window. At 150ms per email, that is approximately 1,250 seconds of processing time per worker per 300-second window. This means 4 email workers cannot keep pace at a 5-minute window — they would require approximately 17 workers.

The 5-minute threshold therefore triggers a worker pool review, not an automatic rejection. Below 5 minutes, the window begins to interact with email worker capacity constraints and the digest grouping requirement starts to break down (events that should be grouped arrive after the window closes). E1 performs the worker pool review before any change below 5 minutes merges.

**Note on worker pool sizing for the current 30-minute window:** At a 30-minute window, each of 4 email workers handles approximately 8,300 emails per window with 1,800 seconds available. At 150ms per email, processing time is approximately 1,245 seconds — within the 1,800-second window with margin. If SES p95 latency is 300ms rather than 120ms, processing time rises to approximately 2,490 seconds, which exceeds the window. E4 owns a latency alert on SES p95 that pages if it exceeds 200ms sustained for more than 5 minutes.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Fanout Multiplier, High-Follower Path, and Rate Limit

#### 1.5.1 The 1.2 Multiplier

For a social app where most interactions are direct, the average notification recipients per action is close to 1. A like notifies one person. A reply notifies one person. A follow notifies one person. The 1.2 multiplier accounts for actions that notify slightly more than one person on average (e.g., tagging multiple users). This multiplier explicitly excludes follower fanout, which is a post-launch feature.

#### 1.5.2 High-Follower Fanout Path (>500 Followers)

Users with more than 500 followers are flagged in the user profile store. When a flagged user takes a feed-generating action:

- The ingestion API detects the high-follower flag at event time.
- The event is routed to a `fanout:high_volume` queue.
- A dedicated fanout worker reads the follower list in batches of 1,000 and enqueues individual P3 notification events.
- These events enter the standard pipeline at P3 priority and are subject to all normal preference filtering and suppression checks.
- The fanout job has a maximum output rate of 2,000 events/second (derived in Section 1.5.3).

The 500-follower threshold is configurable. E1 owns this configuration.

#### 1.5.3 Fanout Rate Limit