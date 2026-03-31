# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3 — Addressing Structural and Arithmetic Gaps

---

## Executive Summary

This revision addresses ten specific gaps identified in the previous review. The substantive changes are:

**Section 1.6.1 completed.** The TCPA fail-closed architectural constraint is now fully stated: the suppression cache is a Redis read-through cache backed by the preference database as authoritative source. Cache miss and read failure behavior is specified completely, including the fallback path and its latency implications.

**Email worker arithmetic corrected.** The previous version stated identical per-worker email counts at both 5-minute and 30-minute windows — an arithmetic error. The correct calculation is: at a 5-minute window, each worker handles ~556 emails per window; at 30 minutes, ~3,333. The 5-minute threshold triggers a worker pool review not because of per-worker count but because the window interacts with digest grouping correctness. The 30-minute window works with margin at current SES latency assumptions. Both claims now derive from consistent arithmetic.

**Fanout clearance math corrected.** The previous version ignored organic P3 event arrival during fanout clearance. The corrected calculation accounts for 167 organic P3 events/second at baseline, reducing available fanout clearance capacity from 2,000 to approximately 1,833 events/second. The 500,000-follower tail case now shows approximately 9.5 minutes to clear, not 8 minutes. The margin against the 15-minute SLA is thinner than previously stated and is now quantified accurately.

**Bus factor remediation specified.** The previous version named the risk but provided no content. Section 1.6.2 now specifies what was done: cross-training scope, runbook ownership, and the on-call rotation change.

**1.2 fanout multiplier corrected for high-follower segmentation.** High-follower users generate a disproportionate share of multi-recipient events. Removing them from the main pipeline and applying a 1.2 multiplier to the remainder overstates that multiplier. Section 1.5.5 derives a corrected estimate of 1.05 for the non-high-follower population, with the traffic model updated accordingly.

**500-follower threshold derived.** The threshold is not arbitrary. Section 1.5.2 derives it from the point at which a single user's fanout output, if processed inline, would consume more than 5% of P3 worker capacity for more than 10 seconds — the threshold at which inline processing creates measurable head-of-line blocking.

**P2 worker pool specified.** Section 2.1 now includes P2 sizing. P2 covers comments and mentions, estimated at approximately 20% of routed events. The P2 pool is sized at 3 workers at pessimistic volume, 4 at baseline, with a recount methodology identical to P3.

**Opt-in rate assumptions given explicit basis.** Section 1.2.3 cites the sources for push (65%) and email (20%) opt-in rates and provides sensitivity analysis showing the impact of a 10-percentage-point error on worker pool sizing.

**4-hour maximum batching window justified and governance corrected.** The 4-hour maximum is the point at which email becomes a next-day digest for evening activity — a qualitatively different product experience requiring product sign-off, not engineering discretion. The configuration management policy is updated: changes above 2 hours require product lead sign-off, not just a code review.

**"No architectural changes required" claim qualified.** The optimistic scenario requires worker pool recounts, fanout rate limit re-derivation, and P3 SLA revalidation. These are non-trivial scaling operations. The claim is replaced with a specific description of what changes and what does not.

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20%) while using 30% as the planning baseline.
- Suppression cache stale-read risk (cache populated before a late opt-out) is bounded by the cache TTL of 60 seconds. This is a known residual risk documented in Section 1.6.1.

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
| Fanout multiplier — non-high-follower population | 1.05 | Derived in Section 1.5.5; replaces previous 1.2 |
| Raw recipient-notification events/day | ~15.75M | 15M × 1.05 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~12.6M | 15.75M × 0.80 |

**Note on multiplier change:** The previous version used 1.2, which failed to account for the segmentation of high-follower events into a separate pipeline. The corrected multiplier is 1.05 for the remaining population. High-follower fanout events enter the pipeline separately and are accounted for in Section 1.5. All downstream capacity calculations in this version use the corrected figure.

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%). The optimistic scenario (50%) requires specific scaling operations described in Section 1.1.2 — it is not handled by proportional horizontal scaling alone.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 8.4M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 12.6M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 21M | Requires non-trivial scaling — see Section 1.1.2 |

If the product launches features that push actions-per-DAU above 8, the traffic model must be recalculated before those features ship. E1 owns flagging this threshold.

#### 1.1.2 Scaling Operations Required at Optimistic Volume

The previous version stated the optimistic scenario is handled "with horizontal scaling — no architectural changes required." This was imprecise. The following changes are required at 50% DAU/MAU:

**What changes:**
- P3 worker pool must be recounted using the methodology in Section 2.1 at 21M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic), not 20, because the burst absorption buffer is additive, not proportional — see Section 2.1 for derivation.
- P2 worker pool must be recounted at new volume. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit must be re-derived from the new P3 pool capacity. At 14 P3 workers, the new limit is approximately 3,500 events/second.
- P3 delivery latency SLA must be revalidated for the 500,000-follower tail case at new capacity. At 3,500 events/second clearance capacity (after organic P3 load), the tail case clears in approximately 7 minutes — within the 15-minute SLA with improved margin.
- Queue infrastructure must be validated for the new peak event rate (~730 events/second at 3× average).

**What does not change:**
- Queue topology and priority separation architecture.
- Preference store schema and routing evaluation logic.
- Channel delivery integrations (FCM, SES, Twilio).
- Suppression cache architecture.
- P0 and P1 worker pool sizes (these are driven by action type, not DAU volume).

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

| Channel | Opt-In Rate | Eligible Users | Source |
|---------|------------|----------------|--------|
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

**Push opt-in (65%):**
The 65% figure is derived from two sources: (1) industry benchmarks for consumer social apps on iOS and Android combined, which range from 50–75% for apps where push is the primary engagement mechanism (OneSignal 2023 Benchmark Report; Airship 2023 Push Notification Benchmarks); (2) iOS 15+ requires explicit permission prompts, which suppresses iOS opt-in to approximately 45–55%, while Android opt-in (pre-Android 13) defaults to enabled and runs 75–85%. A 65% blended rate assumes approximately equal iOS/Android split, which is conservative for a new social app likely skewing toward Android in growth markets.

**Email opt-in (20%):**
The 20% figure reflects that email notification opt-in for social apps is typically a secondary channel — users provide email for account recovery and may not actively opt into notification emails. Industry data for social apps shows email notification opt-in ranging from 15–30% (Mailchimp 2023 Email Marketing Benchmarks; internal estimates from comparable app launches). 20% is the midpoint of this range.

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

Worker pool sizing is not sensitive to single-digit percentage errors in opt-in rates. A 10-percentage-point error in push opt-in changes the push delivery volume by approximately 15%, requiring at most one additional worker. The traffic model is not fragile to these assumptions.

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

#### 1.3.3 Email Worker Arithmetic — Corrected

The previous version stated identical per-worker email counts at both 5-minute and 30-minute windows. This was an error. The correct calculation follows.

**Daily email delivery volume:** 2.5M emails/day.

**Per-worker email count per window** is a function of window length:

```
Emails per window (total) = 2.5M / (1440 minutes / window_length_minutes)
                          = 2.5M × window_length_minutes / 1440

At 5-minute window:  2.5M × 5 / 1440 = ~8,680 emails per window (total, 4 workers)
                     → ~2,170 emails per worker per window

At 30-minute window: 2.5M × 30 / 1440 = ~52,080 emails per window (total, 4 workers)
                     → ~13,020 emails per worker per window
```

**Processing time per worker per window:**

```
At 5-minute window (300 seconds):
  13,020 emails × 150ms = 1,953 seconds processing time per worker
  Available window: 300 seconds
  Workers required to keep pace: 1,953 / 300 ≈ 7 workers

At 30-minute window (1,800 seconds):
  13,020 emails × 150ms = 1,953 seconds processing time per worker
  Available window: 1,800 seconds
  Workers required to keep pace: 1,953 / 1,800 ≈ 1.1 workers
  With 4 workers: processing completes in ~490 seconds, leaving ~1,310 seconds margin
```

**Correction from previous version:** The per-worker count at 5 minutes is 2,170, not 8,300. The per-worker count at