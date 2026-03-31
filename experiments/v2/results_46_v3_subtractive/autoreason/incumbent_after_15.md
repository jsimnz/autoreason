# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

**Priority queue model:** Weighted fair queuing is replaced with priority-aware worker pools. P0/P1 items are processed by dedicated workers that never touch P3 items. This eliminates the mathematical fiction that probability weights provide meaningful priority guarantees under concurrency.

**Email batching:** The batching window is retained for digest grouping (a product requirement), not throughput. The 1.02× average throughput reduction does not justify enforcement overhead.

**Follower notification launch gate:** The dependency between follower notification enablement and infrastructure capacity is a documented launch gate requiring sign-off from engineering lead and product lead.

**TCPA residual risk:** The engineering recommendation is fail-closed SMS during suppression cache failure, converting a compliance risk into a delivery degradation. The legal liability residual — simultaneous unavailability of both E1 and E3 — is named, quantified, and escalated to a business decision. Engineering cannot close this risk unilaterally.

**Fanout rate limit is derived, not asserted.** 2,000 events/second, calculated from P3 worker pool capacity and headroom constraints.

**Global opt-out and channel-level opt-in are independent flags** evaluated multiplicatively. This is an architectural constraint on the preference data model, not an assumption. E3 owns the schema; any change to evaluation order requires a traffic model review.

**Arithmetic corrections from previous revision:**
- Fanout multiplier corrected to 1.05 for the non-high-follower population (1.2 overstated by failing to account for high-follower segmentation). All downstream calculations use the corrected figure.
- Email worker per-window counts corrected: at 5-minute window, ~2,170 emails/worker; at 30-minute window, ~13,020 emails/worker. Previous version stated identical figures at both windows.
- Fanout clearance math corrected to account for 167 organic P3 events/second at baseline, reducing available clearance capacity from 2,000 to ~1,833 events/second. 500,000-follower tail case clears in approximately 9.5 minutes, not 8.
- 500-follower threshold derived, not asserted.
- P2 worker pool specified.
- "No architectural changes required" at optimistic volume replaced with a specific list of what changes and what does not.

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20%) while using 30% as the planning baseline.
- Suppression cache stale-read risk is bounded by the 60-second TTL. This is a known residual risk documented in Section 1.6.1.

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
| Fanout multiplier — non-high-follower population | 1.05 | Derived in Section 1.5.2; explicitly excludes follower fanout |
| Raw recipient-notification events/day | ~15.75M | 15M × 1.05 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~12.6M | 15.75M × 0.80 |

**Note on multiplier:** The 1.2 figure used in earlier revisions failed to account for the segmentation of high-follower events into a separate pipeline. The corrected multiplier is 1.05 for the remaining population. High-follower fanout events enter the pipeline separately and are accounted for in Section 1.5.

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%). The optimistic scenario (50%) requires specific scaling operations described in Section 1.1.2 — it is not handled by proportional horizontal scaling alone.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 8.4M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 12.6M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 21M | Requires non-trivial scaling — see Section 1.1.2 |

If the product launches features that push actions-per-DAU above 8, the traffic model must be recalculated before those features ship. E1 owns flagging this threshold.

#### 1.1.2 Scaling Operations Required at Optimistic Volume

The following changes are required at 50% DAU/MAU:

**What changes:**
- P3 worker pool must be recounted at 21M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic). The burst absorption buffer is additive, not proportional, so the result is not simply 2.5× the pessimistic pool.
- P2 worker pool must be recounted at new volume. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit must be re-derived from the new P3 pool capacity. At 14 P3 workers, the new limit is approximately 3,500 events/second.
- P3 delivery latency SLA must be revalidated for the 500,000-follower tail case at new capacity. At 3,500 events/second clearance capacity (after organic P3 load), the tail case clears in approximately 7 minutes — within the 15-minute SLA with improved margin.
- Queue infrastructure must be validated for the new peak event rate (~730 events/second at 3× average).

**What does not change:**
- Queue topology and priority separation architecture.
- Preference store schema and routing evaluation logic.
- Channel delivery integrations (FCM, SES, Twilio).
- Suppression cache architecture.
- P0 and P1 worker pool sizes (driven by action type, not DAU volume).

The scaling operations are execution work, not design work. They require approximately two weeks of E1 and E4 time if triggered. The trigger condition is: DAU/MAU ratio exceeds 35% for two consecutive weeks as measured in the analytics dashboard.

### 1.2 Channel Distribution and Preference Model

#### 1.2.1 Independence of Global Opt-Out and Channel-Level Opt-In

**This is an architectural constraint, not an assumption.** Global opt-out and channel-level opt-in are stored as independent boolean flags in the user preference store. Evaluation order at routing time is:

1. Check global opt-out flag. If set, no notifications are sent on any channel. Processing stops.
2. For each candidate channel, check channel-level opt-in flag. If not set, skip that channel.
3. Apply notification-type preferences (see Section 3.3).

Any change to evaluation order requires a traffic model review by E1. E3 owns the preference store schema and routing evaluation logic.

**Consequence for in-app channel:** In-app is not disableable at the channel level. The in-app channel opt-in flag is always set. Global opt-out still applies.

#### 1.2.2 Channel Volumes

Channel opt-in rates among users who have not globally opted out (8M users at baseline):

| Channel | Opt-In Rate | Eligible Users | Notes |
|---------|------------|----------------|-------|
| In-app | 100% | 8M | Not disableable at channel level |
| Push | 65% | 5.2M | See Section 1.2.3 |
| Email | 20% | 1.6M | See Section 1.2.3 |
| SMS | <0.01% | <800 | Explicit opt-in; TCPA governed |

Expected delivery events per routed notification event: 1 + 0.65 + 0.20 + ~0 = **1.85 channels/user**.

Total delivery events/day: 12.6M × 1.85 = **~23.3M** (baseline). Pessimistic: ~15.5M. Optimistic: ~38.9M.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 12.6M | ~438 |
| Push | 8.2M | ~285 |
| Email (pre-batch) | 2.5M | ~87 |
| SMS | ~1,500 | negligible |

#### 1.2.3 Opt-In Rate Basis and Sensitivity Analysis

**Push opt-in (65%):** Derived from industry benchmarks for consumer social apps (OneSignal 2023; Airship 2023), which range from 50–75%. iOS 15+ explicit permission prompts suppress iOS opt-in to approximately 45–55%; Android (pre-Android 13) defaults to enabled at 75–85%. A 65% blended rate assumes approximately equal iOS/Android split, which is conservative for a new social app likely skewing toward Android in growth markets.

**Email opt-in (20%):** Email notification opt-in for social apps is typically a secondary channel. Industry data shows 15–30% (Mailchimp 2023; comparable app launches). 20% is the midpoint.

**Sensitivity analysis:**

| Push opt-in rate | Push delivery events/day | P3 worker pool impact |
|-----------------|--------------------------|----------------------|
| 55% (−10pp) | 6.9M | −1 worker |
| 65% (baseline) | 8.2M | baseline |
| 75% (+10pp) | 9.5M | +1 worker |

| Email opt-in rate | Email delivery events/day | Email worker pool impact |
|------------------|--------------------------|--------------------------|
| 10% (−10pp) | 1.3M | −1 worker |
| 20% (baseline) | 2.5M | baseline |
| 30% (+10pp) | 3.8M | +1 worker |

Worker pool sizing is not sensitive to single-digit percentage errors in opt-in rates. A 10-percentage-point error in push opt-in changes push delivery volume by approximately 15%, requiring at most one additional worker.

### 1.3 Email Batching

#### 1.3.1 Two Separate Justifications

**Argument 1 — Digest grouping (product requirement):** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement independent of throughput. A batching window is required to implement it.

**Argument 2 — Throughput impact (infrastructure consideration):** The batching window has approximately 1.02× average throughput reduction across all opted-in users. This is not a meaningful infrastructure benefit and does not justify the batching window on infrastructure grounds alone.

These arguments are independent. The batching window is retained for Argument 1.

#### 1.3.2 Throughput Analysis

```
Email opted-in users: 1.6M
Email delivery events/day: 2.5M

Average events per opted-in user per day:
  2.5M ÷ 1.6M = 1.56 events/user/day

λ per 30-minute window = 1.56 / 48 = 0.0325 events/window

P(at least one event in window) = 1 - e^(-0.0325) ≈ 0.032
Expected emails/user/day = 48 × 0.032 = 1.54
Reduction factor: 1.56 / 1.54 ≈ 1.01×
```

For high-engagement users receiving 20 events/day (λ = 0.42/window), the per-user reduction is approximately 1.7×. Aggregate reduction is bounded between 1.01× and approximately 1.4×. Infrastructure is sized for the lower bound.

#### 1.3.3 Email Worker Arithmetic and Minimum Window Threshold

**Corrected per-worker email counts:**

```
Daily email delivery volume: 2.5M emails/day

Emails per window (total) = 2.5M × window_length_minutes / 1440

At 5-minute window:  2.5M × 5 / 1440  = ~8,680 emails per window (4 workers)
                     → ~2,170 emails per worker per window

At 30-minute window: 2.5M × 30 / 1440 = ~52,080 emails per window (4 workers)
                     → ~13,020 emails per worker per window
```

**Processing time per worker per window:**

| Step | Estimated Latency |
|------|------------------|
| Batch store read (Redis, 10–50 events) | 2–5ms |
| Template rendering | 5–15ms |
| SES API call (p50) | 80–120ms |
| Delivery record write | 5–10ms |
| **Total per email** | **~100–150ms** |

```
At 5-minute window (300 seconds):
  2,170 emails × 150ms = 326 seconds processing time per worker
  Available window: 300 seconds
  Workers required to keep pace: 326 / 300 ≈ 1.1 workers per worker's share
  → 4 workers marginally insufficient; pool review required

At 30-minute window (1,800 seconds):
  13,020 emails × 150ms = 1,953 seconds processing time per worker
  Available window: 1,800 seconds
  Workers required to keep pace: 1,953 / 1,800 ≈ 1.1 workers
  With 4 workers: processing completes in ~490 seconds, leaving ~1,310 seconds margin
```

**The 5-minute minimum threshold** triggers a worker pool review before the change merges, not an automatic rejection. Below 5 minutes, the window also interacts with digest grouping: events that should be grouped arrive after the window closes.

**Note on the current 30-minute window:** If SES p95 latency reaches 300ms, processing time rises to ~3,906 seconds per worker, exceeding the window. E4 owns a latency alert on SES p95 that pages if it exceeds 200ms sustained for more than 5 minutes.

**Configuration management:** The batching window is a product configuration parameter. Changes require code review from one engineer confirming the value is within bounds (minimum 5 minutes, maximum 4 hours). Changes above 2 hours require product lead sign-off — at that threshold, email becomes a next-day digest for evening activity, which is a qualitatively different product experience. Window changes are logged in the deployment record.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Fanout Multiplier, High-Follower Path, and Rate Limit

#### 1.5.1 The 1.05 Multiplier

For a social app where most interactions are direct, the average notification recipients per action is close to 1. A like notifies one person. A reply notifies one person. A follow notifies one person. The 1.05 multiplier accounts for actions that notify slightly more than one person on average (e.g., tagging multiple users) in the non-high-follower population. This multiplier explicitly excludes follower fanout.

The previous 1.2 figure was derived without accounting for the fact that high-follower users — who generate a disproportionate share of multi-recipient events — are removed from this calculation and handled separately. Removing them reduces the multiplier for the remainder to approximately 1.05.

#### 1.5.2 High-Follower Fanout Path — Threshold Derivation

The 500-follower threshold is derived from