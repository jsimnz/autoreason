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

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption.
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
| Fanout multiplier — non-high-follower population | 1.05 | Derived in Section 1.5.1; explicitly excludes follower fanout |
| Raw recipient-notification events/day | ~15.75M | 15M × 1.05 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~12.6M | 15.75M × 0.80 |

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%). The optimistic scenario (50%) requires specific scaling operations described in Section 1.1.2 — it is not handled by proportional horizontal scaling alone.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 8.4M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 12.6M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 21M | Requires non-trivial scaling — see Section 1.1.2 |

**Lower-bound sensitivity:** If DAU/MAU falls to 15% (1.5M DAU), routed events drop to approximately 6.3M/day. The P3 worker pool is over-provisioned by approximately 25% and the P2 pool by approximately 33%. This is accepted. Provisioning for 15% and scaling up if engagement improves carries more operational risk than the cost of idle capacity during a 6-month launch window. If DAU/MAU remains below 20% for eight consecutive weeks post-launch, E1 initiates a capacity right-sizing review.

**Actions-per-DAU sensitivity:** If actions-per-DAU falls to 3, routed events fall to approximately 7.6M/day — handled by existing pessimistic provisioning. If actions-per-DAU exceeds 8, the traffic model must be recalculated before features that drive this threshold ship. E1 owns flagging this.

#### 1.1.2 Scaling Operations Required at Optimistic Volume

**What changes:**
- P3 worker pool recounted at 21M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic). The burst absorption buffer is additive, not proportional.
- P2 worker pool recounted. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit re-derived from new P3 pool capacity. At 14 workers, estimated new limit: ~3,500 events/second.
- P3 delivery latency SLA revalidated for 500,000-follower tail case. At 3,500 events/second clearance capacity after organic P3 load, tail case clears in approximately 7 minutes — within the 15-minute SLA.
- Queue infrastructure validated for new peak event rate (~730 events/second at 3× average).

**What does not change:** Queue topology, preference store schema, routing evaluation logic, channel delivery integrations, suppression cache architecture, P0 and P1 worker pool sizes.

**Task-level estimate:**

| Task | Owner | Engineer-Days |
|------|-------|---------------|
| Recount P3 and P2 worker pools, update Terraform configs | E4 | 1 |
| Re-derive fanout rate limit, update rate limiter config | E1 | 0.5 |
| Revalidate P3 latency SLA for tail case at new capacity | E1 | 1 |
| Validate queue infrastructure at new peak event rate (load test) | E4 | 2 |
| Update capacity documentation and runbooks | E4 | 1 |
| Deploy worker pool changes to staging, run regression suite | E4 | 1–2 |
| Deploy to production with canary rollout, monitor for 48 hours | E1 + E4 | 2–3 |
| **Total** | | **8.5–10.5 engineer-days (≈ 11–15 calendar days with review overhead)** |

E1 and E4 are the owners. During this window, E2 and E3 absorb routine on-call and maintenance responsibilities. If E1 or E4 is unavailable, scaling work is deferred by one sprint — the trigger condition provides sufficient lead time.

**Trigger condition and enforcement:** The trigger condition is: DAU/MAU ratio exceeds 35% for two consecutive weeks.

*Monitoring owner:* E2. The analytics pipeline emits a weekly DAU/MAU ratio metric. An automated alert fires to #eng-notifications and pages E2 if the ratio exceeds 35% in any given week. E2 confirms whether the condition has persisted for two consecutive weeks and, if so, escalates to E1 to initiate scaling work.

*Missed alert escalation:* If the weekly metric is not emitted, the monitoring system alerts E2 within 24 hours via a separate heartbeat check. E2 manually pulls the DAU/MAU figure within 48 hours of a missed emission.

*Why two consecutive weeks:* A single week above 35% may be a promotional spike. Two consecutive weeks indicates a sustained shift. Given scaling work takes 11–15 calendar days, the two-week trigger provides approximately zero buffer at the outer bound. If the ratio reaches 40% in a single week, E2 escalates immediately without waiting for the second week.

### 1.2 Channel Distribution and Preference Model

#### 1.2.1 Independence of Global Opt-Out and Channel-Level Opt-In

**This is an architectural constraint, not an assumption.** Global opt-out and channel-level opt-in are stored as independent boolean flags in the user preference store. Evaluation order at routing time:

1. Check global opt-out flag. If set, no notifications are sent on any channel. Processing stops.
2. For each candidate channel, check channel-level opt-in flag. If not set, skip that channel.
3. Apply notification-type preferences (Section 3.3).

Any change to evaluation order requires a traffic model review by E1. E3 owns the preference store schema and routing evaluation logic.

**In-app channel non-disableable — justification and legal risk:**

In-app notifications are not disableable at the channel level. Global opt-out still suppresses in-app notifications.

*Product decision rationale:* In-app notifications are delivered only while the user is actively using the application. Unlike push, email, or SMS, they do not interrupt the user outside the product context. The product team (decision owner: Product Lead) determined that suppressing in-app notifications while a user is actively present degrades core social functionality — specifically, real-time like and comment counters — in a way that is qualitatively different from suppressing background channels. The implementation cost of making in-app disableable is low (one additional preference flag and one routing check). The decision not to do so is deliberate.

*Legal risk:* Some jurisdictions require users to be able to suppress all non-transactional notifications, including in-app. GDPR and CCPA may apply depending on notification content and jurisdiction. **A legal compliance review of the in-app non-disableable constraint is required before launch.** Owner: Legal Lead. Gate: review must be completed before the preference management UI is finalized. If legal review requires in-app to be disableable, the implementation change is estimated at 2 engineer-days (E3).

#### 1.2.2 Channel Volumes

Channel opt-in rates among users who have not globally opted out (8M users at baseline):

| Channel | Opt-In Rate | Eligible Users | Notes |
|---------|------------|----------------|-------|
| In-app | 100% | 8M | Not disableable at channel level — see Section 1.2.1 |
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

**Push opt-in (65%):** Industry benchmarks for consumer social apps (OneSignal 2023; Airship 2023) range from 50–75%. iOS 15+ explicit permission prompts suppress iOS opt-in to approximately 45–55%; Android (pre-Android 13) defaults to enabled at 75–85%. A 65% blended rate assumes approximately equal iOS/Android split.

**Email opt-in (20%):** Industry data shows 15–30% for social apps (Mailchimp 2023). 20% is the midpoint.

**Sensitivity analysis:**

| Push opt-in rate | Push delivery events/day | P3 worker pool impact |
|-----------------|--------------------------|----------------------|
| 55% (−10pp) | 6.9M | −1 worker |
| 65% (baseline) | 8.2M | baseline |
| 75% (+10pp) | 9.5M | +1 worker |

Worker pool sizing is not sensitive to single-digit percentage errors in opt-in rates. A 10-percentage-point error in push opt-in changes push delivery volume by approximately 15%, requiring at most one additional worker.

### 1.3 Email Batching

#### 1.3.1 Two Separate Justifications

**Argument 1 — Digest grouping (product requirement):** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement independent of throughput. A batching window is required to implement it.

**Argument 2 — Throughput impact (infrastructure consideration):** The batching window has approximately 1.01–1.02× average throughput reduction across all opted-in users. This is not a meaningful infrastructure benefit and does not justify the batching window on infrastructure grounds alone.

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

For high-engagement users receiving 20 events/day (λ = 0.42/window), the per-user reduction is approximately 1.7×. Aggregate reduction is bounded between 1.01× and approximately 1.4×. Infrastructure is sized for the lower bound (no reduction).

#### 1.3.3 Email Worker Arithmetic and Minimum Window Threshold

**Parallelism model:** The email worker pool processes emails in parallel. Each worker independently dequeues and processes one email at a time. The per-worker load figure below represents each worker's share of the total window volume; all four workers process their shares concurrently.

**Per-worker email counts:**

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
At 5-minute window (300 seconds available per worker):
  2,170 emails × 150ms = 326 seconds per worker
  Available window: 300 seconds
  → 4 workers marginally insufficient; pool review required before deploying this window

At 30-minute window (1,800 seconds available per worker):
  13,020 emails × 150ms = 1,953 seconds per worker
  With 4 workers processing in parallel: completes in ~490 seconds, leaving ~1,310 seconds margin
```

**The 5-minute minimum threshold** triggers a worker pool review before the change merges, not an automatic rejection. Below 5 minutes, the window also interacts with digest grouping: events that should be grouped arrive after the window closes.

**SES latency alert:** E4 owns a latency alert on SES p95. Alert threshold: 120ms (the p50 ceiling in the processing model). Secondary alert at 180ms. If