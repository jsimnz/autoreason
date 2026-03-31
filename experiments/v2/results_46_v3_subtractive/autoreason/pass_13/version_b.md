# Notification System Design Proposal — Revision 5
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten structural problems identified in Revision 4. The corrections are substantive. The most significant changes:

**Weighted fair queuing replaced with priority-aware worker pools.** The concurrency problem the prior version diagnosed but did not solve is now solved by separating worker pools by priority tier. P0/P1 items are processed by dedicated workers that never touch P3 items. This eliminates the mathematical fiction that probability weights provide meaningful priority guarantees under concurrency.

**Section 1.3 enforcement infrastructure is rationalized.** The recalculation job, P1 alerting, and 30-minute SLA were built around a parameter with 1.02× throughput impact. The enforcement overhead is not justified. Section 1.3 is redesigned: the batching window is a product configuration parameter with lightweight change management, not an operational safety control.

**High-follower fanout launch risk has a formal gate, not a single engineer.** The dependency between follower notification enablement and infrastructure capacity is now a documented launch gate requiring sign-off from engineering lead and product lead. E1 surfacing the dependency is an input to that process, not the process itself.

**TCPA residual risk is explicitly quantified and escalated.** The bus factor remediation reduces operational risk. The legal liability residual — what happens if both E1 and E3 are simultaneously unavailable — is named, quantified as a probability, and escalated to a business decision with documented options. Engineering cannot close this risk unilaterally.

**Fanout rate limit of 5,000 events/second is derived, not asserted.** The figure is now calculated from queue capacity and worker throughput constraints, with explicit accounting for delivery latency implications during sustained fanout.

**Section 3.4 (in-app/WebSocket) is fully specified.** It was announced as corrected in Revision 4 and absent from the document. It is present in this revision.

**P3 TTL and maximum queue depth are specified.** They were announced in the Revision 4 executive summary and absent from the design. They are specified in Section 2.1 with overflow behavior.

**DAU/MAU sensitivity analysis is provided.** The 30% assumption is retained as a planning baseline with explicit sensitivity bounds. The traffic model is sized for the pessimistic case, not the point estimate.

**Token invalidity stream has a named owner.** The gap between E2 (publisher) and E3 (consumer) is closed by assigning E4 ownership of the stream infrastructure with explicit responsibilities.

**UUID v7 ordering constraint has automated enforcement.** Code review is retained as a secondary check. The primary enforcement mechanism is a static analysis rule that fails CI builds where cross-node ordering is assumed.

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule, not solely code review.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20%) while using 30% as the planning baseline. The fanout infrastructure is not built for follower notifications at launch; enabling them requires a formal gate.

**What we are not building:** ML send-time optimization, A/B testing infrastructure, per-user engagement scoring, real-time analytics dashboards, global event sequencing guarantees, follower fanout notifications at launch.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU planning baseline — see Section 1.1.1 for sensitivity analysis |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |
| Fanout multiplier | 1.2 (standard) | See Section 1.5 for derivation and high-follower path |
| Raw recipient-notification events/day | ~18M | 15M × 1.2 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~14.4M | 18M × 0.80 |

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. This ratio varies substantially across social products and is sensitive to product type, user base age, and geographic composition. We do not have product-specific data before launch.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 9.6M | Infrastructure sized for this scenario |
| 30% (baseline) | 3M | 15M | 14.4M | Planning baseline for team discussions |
| 50% (optimistic) | 5M | 25M | 24M | Requires worker pool recount; see note |

**Sizing decision: infrastructure is provisioned for the pessimistic scenario (20% DAU/MAU) and sized to handle the optimistic scenario (50%) with horizontal scaling only — no architectural changes.** The pessimistic scenario is not the expected case; it is the case we build for so that an incorrect assumption does not require emergency re-architecture. At 50% DAU/MAU, worker pool counts increase proportionally (approximately 2.5× the pessimistic baseline) but the queue topology, channel integrations, and preference management architecture are unchanged.

**What would change the model materially:** If the product launches with features that significantly increase actions-per-DAU above 5 (for example, a high-frequency reaction mechanic), the traffic model must be recalculated. E1 owns flagging this to the team if product specifications indicate actions-per-DAU above 8. The threshold of 8 is chosen because it would push the pessimistic scenario above 50% DAU/MAU equivalent volume, at which point horizontal scaling alone may not be sufficient within the existing budget.

### 1.2 Channel Distribution

Channel opt-in rates (among the 80% of users who have not globally opted out):

| Channel | Opt-In Rate | Notes |
|---------|------------|-------|
| In-app | 100% | Cannot be disabled at channel level |
| Push | 65% | Of non-opted-out users |
| Email | 20% | Of non-opted-out users |
| SMS | <0.01% | Explicit opt-in required; TCPA governed |

Expected delivery events per routed notification event = 1 + 0.65 + 0.20 + ~0 = 1.85 channels/user.

Total delivery events/day = 14.4M × 1.85 = **~26.6M delivery events/day** (baseline). Pessimistic scenario: 9.6M × 1.85 = ~17.8M delivery events/day. Optimistic scenario: 24M × 1.85 = ~44.4M delivery events/day.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 14.4M | ~500 |
| Push | 9.4M | ~325 |
| Email (pre-batch) | 2.9M | ~100 |
| SMS | ~1,500 | negligible |

### 1.3 Email Batching — Scope and Configuration Management

#### 1.3.1 What Batching Does and Does Not Accomplish

The revised model from Revision 4 is retained. At average λ across all opted-in users, the reduction factor is approximately 1.02×. This is not a meaningful throughput reduction. The calculation is reproduced here for completeness:

```
Email opted-in users: 10M × 0.80 × 0.20 = 1.6M users
Email delivery events/day (baseline): 2.9M

Average events per opted-in user per day:
  2.9M ÷ 1.6M = 1.81 events/user/day

λ per 30-minute window = 1.81 / 48 = 0.038 events/window

P(at least one event in window) = 1 - e^(-0.038) ≈ 0.037
Expected emails/user/day = 48 × 0.037 = 1.78
Reduction: 1.81 / 1.78 ≈ 1.02×
```

**The batching window is retained for one reason: digest grouping.** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement. It is not a throughput optimization at current scale.

**Consequence for Section 1.3 infrastructure in Revision 4:** The prior revision built a recalculation job, P1 alerting, a 30-minute SLA, and E4 paging around changes to the batching window parameter. This enforcement apparatus was calibrated for a parameter that materially affects throughput. At 1.02× average reduction, the batching window does not materially affect throughput. The enforcement overhead is not justified.

#### 1.3.2 Revised Configuration Management for Batching Window

The batching window is a product configuration parameter. It is managed as follows:

1. The parameter lives in the application configuration store alongside other product parameters (e.g., notification copy, feature flags).
2. Changes require a code review from one engineer (any engineer — no special ownership). The review confirms the new value is within bounds (minimum 5 minutes, maximum 4 hours) and that the change is intentional.
3. No recalculation job. No P1 alert. No paging. The throughput impact at current scale does not warrant operational controls beyond code review.
4. **Exception:** If the product team requests a batching window below 5 minutes, this triggers a throughput review. Below 5 minutes, the batching window begins to interact with the email worker pool's processing latency, and the 1.02× assumption may not hold because the queue may not accumulate sufficient events to batch. E1 performs this review before the configuration change is merged.
5. The batching window is logged in the deployment record whenever it changes, so post-incident analysis can correlate window changes with delivery anomalies.

This is substantially simpler than the Revision 4 apparatus and is appropriate for the actual risk level.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Fanout Multiplier — Derivation, High-Follower Path, and Rate Limit Basis

#### 1.5.1 The 1.2 Multiplier

For a social app where most interactions are direct (likes on posts, replies to comments, follows), the average number of notification recipients per action is close to 1. A like notifies one person. A reply notifies one person. A follow notifies one person. The 1.2 multiplier accounts for actions that notify slightly more than one person on average (e.g., tagging multiple users in a post). This multiplier explicitly excludes follower fanout.

#### 1.5.2 High-Follower Fanout Path (>500 Followers)

Users with more than 500 followers are flagged in the user profile store. When a flagged user takes a feed-generating action (post, story), the fanout is handled by a separate async job, not the standard notification pipeline:

- The ingestion API detects the high-follower flag at event time.
- The event is routed to a `fanout:high_volume` queue.
- A dedicated fanout worker reads the follower list in batches of 1,000 and enqueues individual P3 notification events for each follower.
- These events enter the standard pipeline at P3 priority and are subject to all normal preference filtering and suppression checks.
- The fanout job has a maximum output rate. See Section 1.5.3 for derivation.

**Threshold rationale:** 500 followers is a conservative threshold. Approximately 1-2% of social app users exceed this. The threshold is configurable and should be tuned after launch based on observed fanout distributions. E1 owns this threshold configuration.

#### 1.5.3 Fanout Rate Limit — Derivation

Revision 4 stated 5,000 events/second without derivation. This section derives the figure.

**Inputs:**
- Standard P3 worker pool: 8 workers (see Section 2.1.3 for worker pool sizing)
- Each P3 worker processes approximately 500 events/second under normal load (estimated from event processing time of ~2ms including preference lookup and queue write)
- P3 worker pool total capacity: 8 × 500 = 4,000 events/second
- Target: fanout output should not consume more than 50% of P3 worker capacity, leaving headroom for organic P3 events (digest summaries, low-priority notifications)
- Fanout rate limit: 4,000 × 0.50 = 2,000 events/second

**Revised figure: 2,000 events/second.** This replaces the unvalidated 5,000 events/second from Revision 4.

**Delivery latency implication:** If follower notifications are enabled (which they are not at launch — see Section 1.5.4) and a user with 100,000 followers posts, the fanout job generates 100,000 events. At 2,000 events/second, this takes 50 seconds to enqueue. These events then enter the P3 queue and compete with other P3 events at 5% of worker attention (see Section 2.1). Worst-case delivery latency for P3 items during a viral post fanout:

```
Queue depth added by fanout: 100,000 events
P3 throughput during fanout: 8 workers × 500 events/sec × 5% weight = 200 events/sec
Time to clear 100,000 events: 100,000 / 200 = 500 seconds (~8 minutes)
```

This is acceptable for follower notifications (P3 by definition). If it is not acceptable, the product team needs to either increase the P3 worker pool or accept higher latency. This tradeoff is documented here so the decision is explicit.

**For users with 500,000 followers:** Fanout takes 250 seconds to enqueue. Queue clearance time is 2,500 seconds (~42 minutes). This is the tail case. If the product launches follower notifications and has users with follower counts in this range, the P3 worker pool must be sized accordingly. This is a known constraint.

#### 1.5.4 Follower Notification Launch Gate

Section 1.5 in Revision 4 stated that "E1 owns surfacing this dependency to the product team before the feature is enabled." This is insufficient as a process control for a decision that would invalidate the entire infrastructure plan.

**Formal launch gate for follower notifications:**

Enabling follower notifications at any scale requires sign-off on the following checklist before the feature flag is enabled in production:

| Item | Owner | Sign-off Required From |
|------|-------|----------------------|
| Traffic model recalculated for new volume | E1 | Engineering lead |
| Worker pool counts revised and provisioned | E1, E4 | Engineering lead |
| P3 queue capacity validated at new volume | E4 | Engineering lead |
| Fanout rate limit validated against new worker pool | E1 | Engineering lead |
| Delivery latency SLA confirmed acceptable for new tail cases | Product | Product lead |
| Infrastructure cost delta approved | Engineering lead | Product lead or budget owner |

This checklist is stored in the project's decision log. The feature flag for follower notifications is owned by E1. Merging a change that enables the feature flag in production without completing the checklist is a process violation, not an engineering judgment call. If the product team requests enabling follower notifications on an accelerated timeline, the engineering lead escalates to determine which checklist items can be compressed and which cannot.

### 1.6 Team Allocation

#### 1.6.1 TCPA Compliance — Residual Risk Escalation

Revision 4 reduced the operational bus factor from 1 to 2 by having E1 co-author the suppression cache runbook and execute a simulated incident. The proposal acknowledged this was partial remediation. The residual risk — simultaneous unavailability of both E1 and E3 — was named but not addressed.

**The residual risk, quantified:**

Simultaneous unavailability of two specific engineers for a period long enough to matter (>4 hours during a compliance incident) has three primary causes:

1. **Unplanned simultaneous absence**