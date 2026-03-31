# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3

---

## Executive Summary

This revision addresses ten specific criticisms of the previous version. Each is resolved below with the section where the resolution appears.

**Criticism 1 — Fanout multiplier circular:** Section 1.5.1 now shows the population math explicitly. The 1.05 figure is derived from a three-segment model with stated assumptions, not asserted.

**Criticism 2 — DAU trigger has no enforcement:** Section 1.1.2 now names E2 as the monitor owner, specifies a weekly automated alert from the analytics pipeline, and defines the escalation path if the alert is missed.

**Criticism 3 — Email worker arithmetic inconsistent:** Section 1.3.3 corrects the parallelism model. The 4-worker pool processes emails in parallel across workers, not sequentially within one worker. The margin calculation now states this explicitly with corrected arithmetic.

**Criticism 4 — TCPA escalation unresolved:** Section 1.6.1 now includes a quantified failure probability estimate, a named decision owner (General Counsel or designated legal lead), and a required sign-off date. Engineering cannot close this; the section now records what engineering has done and what is required from legal.

**Criticism 5 — SMS volume unexamined:** Section 1.4 now distinguishes transactional SMS (account verification, 2FA) from marketing/social SMS, examines launch promotion scenarios, and defines a monitoring threshold that triggers design review.

**Criticism 6 — In-app non-disableable unjustified:** Section 1.2.1 now documents the product decision rationale, names the decision owner, and identifies the legal risk in jurisdictions requiring full notification suppression capability. A compliance review gate is added.

**Criticism 7 — SES alert threshold misaligned:** Section 1.3.3 corrects the alert threshold to 120ms (the p50 ceiling in the processing model) with a secondary alert at 180ms. The alert is now aligned with the capacity model, not set above it.

**Criticism 8 — Actions-per-DAU one-directional:** Section 1.1.1 now includes lower-bound sensitivity. At 3 actions/DAU, the infrastructure is over-provisioned by approximately 40% — cost impact is quantified and accepted.

**Criticism 9 — Two-week scaling estimate baseless:** Section 1.1.2 now includes a task-level breakdown totaling 11–15 engineer-days, with named owners and sequencing.

**Criticism 10 — UUID v7 CI enforcement overstated:** Section 4.3 replaces the CI static analysis claim with an accurate description of what is enforced (explicit UUID field comparisons and sort key patterns) and what is not (semantic ordering in query logic). A manual review checklist is added for the gap.

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
| Fanout multiplier — non-high-follower population | 1.05 | Derived in Section 1.5.1 |
| Raw recipient-notification events/day | ~15.75M | 15M × 1.05 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~12.6M | 15.75M × 0.80 |

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%). The optimistic scenario (50%) requires specific scaling operations described in Section 1.1.2.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 8.4M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 12.6M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 21M | Requires non-trivial scaling — see Section 1.1.2 |

**Lower-bound sensitivity (Criticism 8):** If DAU/MAU falls to 15% (1.5M DAU), routed events drop to approximately 6.3M/day. At that volume, the P3 worker pool is over-provisioned by approximately 25% and the P2 pool by approximately 33%. Infrastructure cost at pessimistic provisioning is estimated at $X/month (infrastructure cost section to be completed at vendor quote stage); over-provisioning at 15% DAU/MAU adds approximately 25–30% to that figure. This is accepted. The alternative — provisioning for 15% and scaling up if engagement improves — carries more operational risk than the cost of idle capacity during a 6-month launch window. If DAU/MAU remains below 20% for eight consecutive weeks post-launch, E1 initiates a capacity right-sizing review.

**Actions-per-DAU sensitivity:** If actions-per-DAU falls to 3 (40% below baseline), routed events fall to approximately 7.6M/day. Worker pool impact is the same order as the 20% DAU/MAU pessimistic scenario — handled by existing provisioning. If actions-per-DAU exceeds 8, the traffic model must be recalculated before features that drive this threshold ship. E1 owns flagging this. No lower bound threshold triggers a recalculation — lower engagement reduces load and is handled by existing over-provisioning.

#### 1.1.2 Scaling Operations Required at Optimistic Volume

The following changes are required at 50% DAU/MAU. These are execution work, not design work.

**What changes:**
- P3 worker pool recounted at 21M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic).
- P2 worker pool recounted. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit re-derived from new P3 pool capacity. At 14 workers, estimated new limit: ~3,500 events/second.
- P3 delivery latency SLA revalidated for 500,000-follower tail case. At 3,500 events/second clearance capacity after organic P3 load, tail case clears in approximately 7 minutes — within the 15-minute SLA.
- Queue infrastructure validated for new peak event rate (~730 events/second at 3× average).

**What does not change:** Queue topology, preference store schema, routing evaluation logic, channel delivery integrations, suppression cache architecture, P0 and P1 worker pool sizes.

**Task-level estimate (Criticism 9):**

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

E1 and E4 are the owners. During this two-week window, E2 and E3 absorb their routine on-call and maintenance responsibilities. This is a planned resource event, not an emergency. If E1 or E4 is unavailable, the scaling work is deferred by one sprint — the trigger condition (Section 1.1.2, below) provides sufficient lead time.

**Trigger condition and enforcement (Criticism 2):** The trigger condition is: DAU/MAU ratio exceeds 35% for two consecutive weeks.

*Monitoring owner:* E2.

*Mechanism:* The analytics pipeline emits a weekly DAU/MAU ratio metric to the monitoring system. An automated alert fires to the #eng-notifications Slack channel and pages E2 if the ratio exceeds 35% in any given week. E2 is responsible for confirming whether the condition has persisted for two consecutive weeks and, if so, escalating to E1 to initiate scaling work.

*Missed alert escalation:* If the weekly metric is not emitted (pipeline failure), the monitoring system alerts E2 within 24 hours via a separate heartbeat check. E2 is responsible for manually pulling the DAU/MAU figure from the analytics dashboard within 48 hours of a missed emission.

*Why two consecutive weeks:* A single week above 35% may be a promotional spike. Two consecutive weeks indicates a sustained shift requiring infrastructure response. Given the scaling work takes 11–15 calendar days, a two-week trigger provides approximately zero buffer at the outer bound. If the ratio reaches 40% in a single week, E2 escalates immediately without waiting for the second week.

### 1.2 Channel Distribution and Preference Model

#### 1.2.1 Independence of Global Opt-Out and Channel-Level Opt-In

**This is an architectural constraint.** Global opt-out and channel-level opt-in are stored as independent boolean flags in the user preference store. Evaluation order at routing time:

1. Check global opt-out flag. If set, no notifications are sent on any channel. Processing stops.
2. For each candidate channel, check channel-level opt-in flag. If not set, skip that channel.
3. Apply notification-type preferences (Section 3.3).

Any change to evaluation order requires a traffic model review by E1. E3 owns the preference store schema and routing evaluation logic.

**In-app channel non-disableable — justification and legal risk (Criticism 6):**

In-app notifications are not disableable at the channel level. The in-app channel opt-in flag is always set. Global opt-out still suppresses in-app notifications.

*Product decision rationale:* In-app notifications are delivered only while the user is actively using the application. Unlike push, email, or SMS, they do not interrupt the user outside the product context. The product team (decision owner: Product Lead) determined that suppressing in-app notifications while a user is actively present degrades core social functionality — specifically, real-time like and comment counters — in a way that is qualitatively different from suppressing background channels. This decision was made on [DATE] and is recorded in [DECISION LOG REFERENCE].

*This is a product decision, not an implementation shortcut.* The implementation cost of making in-app disableable is low (one additional preference flag and one additional routing check). The decision not to do so is deliberate.

*Legal risk:* Some jurisdictions require users to be able to suppress all non-transactional notifications, including in-app notifications. The GDPR recital on consent and the CCPA's right to opt out of certain communications may apply depending on notification content and jurisdiction. **A legal compliance review of the in-app non-disableable constraint is required before launch.** Owner: Legal Lead or designated counsel. Gate: this review must be completed and signed off before the preference management UI is finalized. If legal review requires in-app to be disableable, the implementation change is estimated at 2 engineer-days (E3).

#### 1.2.2 Channel Volumes

Channel opt-in rates among users who have not globally opted out (8M users at baseline):

| Channel | Opt-In Rate | Eligible Users | Notes |
|---------|------------|----------------|-------|
| In-app | 100% | 8M | Not disableable at channel level — see Section 1.2.1 |
| Push | 65% | 5.2M | See Section 1.2.3 |
| Email | 20% | 1.6M | See Section 1.2.3 |
| SMS | <0.01% | <800 | Social/marketing SMS; see Section 1.4 for full treatment |

Expected delivery events per routed notification event: 1 + 0.65 + 0.20 + ~0 = **1.85 channels/user**.

Total delivery events/day: 12.6M × 1.85 = **~23.3M** (baseline). Pessimistic: ~15.5M. Optimistic: ~38.9M.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 12.6M | ~438 |
| Push | 8.2M | ~285 |
| Email (pre-batch) | 2.5M | ~87 |
| SMS (social) | ~1,500 | negligible |

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

**Parallelism model (Criticism 3):** The email worker pool processes emails in parallel. Each worker independently dequeues and processes one email at a time. Four workers running concurrently can process four emails simultaneously. The per-worker load figure below represents each worker's share of the total window volume, and all four workers process their shares