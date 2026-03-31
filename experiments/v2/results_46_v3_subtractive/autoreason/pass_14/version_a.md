# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses structural problems from the prior version. The most significant changes:

**Priority queue model redesigned.** Weighted fair queuing is replaced with priority-aware worker pools. P0/P1 items are processed by dedicated workers that never touch P3 items. This eliminates the mathematical fiction that probability weights provide meaningful priority guarantees under concurrency.

**Email batching enforcement rationalized.** The recalculation job, P1 alerting, and 30-minute SLA in the prior version were built around a parameter with 1.02× throughput impact. The enforcement overhead is not justified. The batching window is now a product configuration parameter with lightweight change management.

**Follower notification launch gate formalized.** The dependency between follower notification enablement and infrastructure capacity is now a documented launch gate requiring sign-off from engineering lead and product lead. E1 surfacing the dependency is an input to that process, not the process itself.

**TCPA residual risk explicitly quantified and escalated.** The bus factor remediation reduces operational risk. The legal liability residual — simultaneous unavailability of both E1 and E3 — is named, quantified, and escalated to a business decision. Engineering cannot close this risk unilaterally.

**Fanout rate limit is derived, not asserted.** The 5,000 events/second figure from the prior version is replaced with 2,000 events/second, calculated from P3 worker pool capacity and headroom constraints.

**Section 3.4 (in-app/WebSocket) is fully specified.** It was announced as corrected in the prior version and absent from the document. It is present here.

**P3 TTL and maximum queue depth are specified.** They were announced in the prior executive summary and absent from the design. They are specified in Section 2.1.

**DAU/MAU sensitivity analysis provided.** The 30% assumption is retained as a planning baseline. Infrastructure is sized for the pessimistic case (20%).

**What we are accepting as limitations, with measurement:**
- Duplicate delivery is possible in crash-recovery scenarios. Target: <0.01% of delivered events. Measurement specified in Section 5.
- UUID v7 is used for log correlation and time-bucketing only. No cross-node ordering assumption. Enforced via CI static analysis rule, not solely code review.
- The traffic model is sized for the pessimistic DAU/MAU scenario (20%) while using 30% as the planning baseline.

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
| Fanout multiplier | 1.2 (standard) | See Section 1.5 |
| Raw recipient-notification events/day | ~18M | 15M × 1.2 |
| Global opt-out rate | 20% | Conservative floor |
| Routed notification events/day | ~14.4M | 18M × 0.80 |

#### 1.1.1 DAU/MAU Sensitivity Analysis

The 30% DAU/MAU ratio is the planning baseline. This ratio varies substantially across social products and is sensitive to product type, user base age, and geographic composition.

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 20% (pessimistic) | 2M | 10M | 9.6M | Infrastructure sized for this scenario |
| 30% (baseline) | 3M | 15M | 14.4M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 24M | Requires worker pool recount; no architectural changes |

**Sizing decision: infrastructure is provisioned for the pessimistic scenario and sized to handle the optimistic scenario with horizontal scaling only — no architectural changes.** At 50% DAU/MAU, worker pool counts increase approximately 2.5× the pessimistic baseline but the queue topology, channel integrations, and preference management architecture are unchanged.

If the product launches with features that push actions-per-DAU above 8, the traffic model must be recalculated. E1 owns flagging this if product specifications indicate that threshold will be exceeded.

### 1.2 Channel Distribution

Channel opt-in rates (among the 80% of users who have not globally opted out):

| Channel | Opt-In Rate | Notes |
|---------|------------|-------|
| In-app | 100% | Cannot be disabled at channel level |
| Push | 65% | Of non-opted-out users |
| Email | 20% | Of non-opted-out users |
| SMS | <0.01% | Explicit opt-in required; TCPA governed |

Expected delivery events per routed notification event = 1 + 0.65 + 0.20 + ~0 = 1.85 channels/user.

Total delivery events/day: baseline 14.4M × 1.85 = **~26.6M**. Pessimistic: ~17.8M. Optimistic: ~44.4M.

Per-channel delivery volumes (baseline):

| Channel | Delivery Events/Day | Peak (3× avg)/sec |
|---------|--------------------|--------------------|
| In-app | 14.4M | ~500 |
| Push | 9.4M | ~325 |
| Email (pre-batch) | 2.9M | ~100 |
| SMS | ~1,500 | negligible |

### 1.3 Email Batching — Scope and Configuration Management

#### 1.3.1 What Batching Does and Does Not Accomplish

At average λ across all opted-in users, the reduction factor is approximately 1.02×. This is not a meaningful throughput reduction.

```
Email opted-in users: 10M × 0.80 × 0.20 = 1.6M users
Email delivery events/day: 2.9M

Average events per opted-in user per day:
  2.9M ÷ 1.6M = 1.81 events/user/day

This is the correct denominator: all opted-in users, not just active ones,
because any opted-in user can receive notifications regardless of their
own activity level.

λ per 30-minute window = 1.81 / 48 = 0.038 events/window

P(at least one event in window) = 1 - e^(-0.038) ≈ 0.037
Expected emails/user/day = 48 × 0.037 = 1.78
Reduction: 1.81 / 1.78 ≈ 1.02×
```

The power-law distribution means a small fraction of high-engagement users receive many more than 1.81 events/day. For a user receiving 20 events/day (λ = 0.42/window), the per-user reduction factor is approximately 1.7×. The aggregate reduction across all users is between 1.02× (lower bound) and roughly 1.4× (estimated upper bound). We size for the lower bound.

**The batching window is retained for one reason: digest grouping.** A user who receives five likes within 30 seconds should receive one email listing all five, not five separate emails. This is a product requirement, not a throughput optimization.

#### 1.3.2 Configuration Management for Batching Window

The prior version built a recalculation job, P1 alerting, and a 30-minute SLA around this parameter. At 1.02× average throughput impact, that enforcement apparatus is not justified.

The batching window is a product configuration parameter:

1. Changes require code review from one engineer confirming the new value is within bounds (minimum 5 minutes, maximum 4 hours).
2. No recalculation job. No P1 alert. No paging.
3. **Exception:** If the batching window is requested below 5 minutes, E1 performs a throughput review before the change merges. Below 5 minutes, the window begins to interact with email worker processing latency and the 1.02× assumption may not hold.
4. Window changes are logged in the deployment record for post-incident correlation.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Fanout Multiplier — Derivation, High-Follower Path, and Rate Limit

#### 1.5.1 The 1.2 Multiplier

For a social app where most interactions are direct, the average notification recipients per action is close to 1. A like notifies one person. A reply notifies one person. A follow notifies one person. The 1.2 multiplier accounts for actions that notify slightly more than one person on average (e.g., tagging multiple users). This multiplier explicitly excludes follower fanout.

#### 1.5.2 High-Follower Fanout Path (>500 Followers)

Users with more than 500 followers are flagged in the user profile store. When a flagged user takes a feed-generating action, the fanout is handled by a separate async job:

- The ingestion API detects the high-follower flag at event time.
- The event is routed to a `fanout:high_volume` queue.
- A dedicated fanout worker reads the follower list in batches of 1,000 and enqueues individual P3 notification events for each follower.
- These events enter the standard pipeline at P3 priority and are subject to all normal preference filtering and suppression checks.
- The fanout job has a maximum output rate of 2,000 events/second (see Section 1.5.3).

The 500-follower threshold is configurable and should be tuned after launch. E1 owns this configuration.

#### 1.5.3 Fanout Rate Limit — Derivation

The prior version stated 5,000 events/second without derivation. This section derives the figure.

**Inputs:**
- Standard P3 worker pool: 8 workers (see Section 2.1 for sizing)
- Each P3 worker processes approximately 500 events/second (estimated from ~2ms processing time including preference lookup and queue write)
- P3 worker pool total capacity: 8 × 500 = 4,000 events/second
- Target: fanout output should not consume more than 50% of P3 worker capacity, leaving headroom for organic P3 events

**Fanout rate limit: 2,000 events/second.**

**Delivery latency implication:** For a user with 100,000 followers, the fanout job takes 50 seconds to enqueue all events. These events then enter the P3 queue. With P3 workers receiving 5% of dedicated attention (see Section 2.1):

```
Queue depth added by fanout: 100,000 events
P3 throughput during fanout: 8 workers × 500 events/sec × 5% weight = 200 events/sec
Time to clear: 100,000 / 200 = 500 seconds (~8 minutes)
```

This is acceptable for P3 follower notifications. For users with 500,000 followers, clearance time is approximately 42 minutes. If the product launches follower notifications with users at this scale, the P3 worker pool must be resized. This is a known constraint documented here so the decision is explicit.

#### 1.5.4 Follower Notification Launch Gate

Enabling follower notifications requires sign-off on the following before the feature flag is enabled in production:

| Item | Owner | Sign-off Required From |
|------|-------|----------------------|
| Traffic model recalculated for new volume | E1 | Engineering lead |
| Worker pool counts revised and provisioned | E1, E4 | Engineering lead |
| P3 queue capacity validated at new volume | E4 | Engineering lead |
| Fanout rate limit validated against new worker pool | E1 | Engineering lead |
| Delivery latency SLA confirmed acceptable for tail cases | Product | Product lead |
| Infrastructure cost delta approved | Engineering lead | Product lead or budget owner |

The feature flag for follower notifications is owned by E1. Enabling it in production without completing this checklist is a process violation, not an engineering judgment call.

### 1.6 Team Allocation

#### 1.6.1 TCPA Compliance — Residual Risk

The prior version reduced the operational bus factor from 1 to 2 by having E1 co-author the suppression cache runbook and execute a simulated incident. The residual risk — simultaneous unavailability of both E1 and E3 — was named but not addressed.

**The residual risk, quantified:** Simultaneous unavailability of two specific engineers for more than 4 hours during a compliance incident has three primary causes: (1) unplanned simultaneous absence, (2) a team-wide incident consuming all engineering attention, (3) attrition. For a 4-person team, the probability that any two specific engineers are simultaneously unplanned-absent on a given day is low but non-zero, and attrition risk over a 6-month period is material.

**This risk cannot be closed by engineering alone.** The options are: (a) accept the residual risk and document it, (b) engage outside legal/compliance counsel to establish a documented emergency response protocol that does not depend on specific engineers, or (c) implement a technical control that halts SMS sending automatically during any suppression cache failure (fail-closed). Option (c) is the engineering recommendation because it converts a compliance risk into a delivery degradation, which is operationally manageable. The choice between options is a business decision requiring legal input. Engineering escalates this to the business and documents the outcome.

**TCPA bus factor operational remediation (unchanged from prior version):**

1. E1 pairs with E3 during initial implementation of the suppression cache write path.
2. E1 co-authors the TCPA compliance runbook with E3.
3. E1 executes a simulated TCPA incident in staging before go-live. This is a required gate.
4. The runbook is structured as a decision tree with explicit commands, not prose.

This reduces the effective bus factor from 1 to 2. It does not eliminate the residual legal risk described above.

#### 1.6.2 Engineer Ownership

| Engineer | Primary Responsibility | Explicit Ownership |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, priority scoring, batching logic | Recovery job implementation. Priority queue schema. High-follower fanout threshold configuration. Secondary operational owner of TCPA compliance path (joint runbook author). Follower notification feature flag. |
| E2 | Channel integrations (APNs, FCM, SES, Twilio), token lifecycle | Token invalidity detection; publishes structured events to `token.invalidated` stream. Does not own downstream consumers. |
| E3 | Preference management, user-facing API, suppression, TCPA compliance | Primary owner of suppression cache write path. Feedback processor (consumes `token.invalidated` stream). Preference API opt-out synchronous cache write. TCPA compliance runbook (joint author with E1). |
| E4 | Reliability, monitoring, failure handling, DevOps, WebSocket infrastructure | Recovery job runbook and alerting. `token.invalidated` stream infrastructure. Archival job. Worker pool autoscaling. WebSocket server infrastructure. Duplicate rate monitoring. P3 queue depth monitoring and TTL enforcement. |

---

## 2. System Architecture

### 2.1 Priority Classification and Queue Model

**Problem with weighted fair queuing (prior version).** The prior version used weighted round-robin dequeuing across shared workers. The concurrency problem was correctly diagnosed: under concurrent workers, probability weights do not provide priority guarantees. A P0 item arriving while all workers are processing P1 items waits. The proposed fix — workers sample a queue according to weights on each dequeue cycle — does not solve this. It reduces the expected wait time for P0 items but does not bound it. Under concurrency, "60% probability of checking P0" means a P0 item can wait through arbitrarily many P3 dequeue cycles across N workers simultaneously. The proposal acknowledged this and called it acceptable. It is not acceptable for P0 (account security alerts, time-sensitive transactional notifications).

**Revised model: priority-aware worker pools.**

Workers are separated by priority tier. P0/P1 workers exclusively process P0 and P1 queues. P2/