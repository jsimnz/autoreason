# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural Gaps

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — a correctness decision, not a scale decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct, ElastiCache, RDS. Engineering time goes to integration quality, not infrastructure plumbing.
3. **Incremental delivery** — working system by month 2, iterated through month 5, hardened in month 6.

**Revision 2 addresses nine structural problems identified in review.** The most significant changes are:

- The APNs cold-start failure path is fully implemented with retry loops and fallback behavior.
- Block suppression is architecturally separated from preference caching — they now use different code paths, not asserted separation.
- In-app and push notification consistency is handled explicitly via a coordination record and reconciliation job.
- Viral spike math is recalculated per-queue, not as a uniform distribution assumption.
- P1 and P2 worker counts now have explicit derivations matching the P0 methodology.
- The SMS budget cap is a concrete technical mechanism, not a description of intent.
- The APNs Redis TTL bug (3600s vs. 2700s) is corrected.
- The month-2 recalibration has a named decision owner, a 72-hour decision window, and an explicit contingency for the Kafka scenario.
- E4's scope is restructured to remove the circular resolution.

**Two honest statements retained from Revision 1:**

The 17 notifications/user/day figure is a planning assumption, not a measured fact. We instrument from day one and recalibrate at month 2. Every sizing decision should be read as "correct at estimated volume, revisable at month 2."

The operational surface is at the edge of what 4 engineers can safely own. Section 7 names what we cut and why. If scope is added mid-project, something named there gets dropped — we say it explicitly rather than silently accept overcommitment.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Planning assumption; see calibration note |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike multiplier | 20× | 90-second burst; see spike handling |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### The 17/Day Figure: Calibration and Uncertainty

This number drives queue worker counts, Redis sizing, database partitioning, and cost projections. Getting it wrong by 3× means every sizing decision is wrong simultaneously.

**What we do about it:** instrument notification volume per user per day from the first week of beta. At month 2, recalibrate against measured data.

**Decision owner:** E1, as the engineer responsible for core pipeline architecture. The decision window is 72 hours from the moment measured volume crosses a threshold — not 72 hours from the monthly review meeting. E1 is empowered to act within that window without a committee decision for the ≤2× and 2–5× cases. The >5× case requires explicit sign-off from the engineering lead because the contingency invalidates the 6-month plan.

| Actual Volume | Action Required | Decision Owner | Window |
|---------------|-----------------|----------------|--------|
| ≤ 2× estimate (≤ 100M/day) | Increase P1/P2 worker counts; Redis capacity unchanged | E1 | 72 hours |
| 2–5× estimate (100–250M/day) | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier | E1 | 72 hours |
| > 5× estimate (> 250M/day) | See contingency below | Engineering lead | 72 hours |

**The >5× contingency, stated plainly:** discovering at month 2 that volume is 250M+/day means the queue infrastructure described in this document is undersized and the 6-month plan is invalid. A Kafka migration is a 3–4 month project. There is no version of this where we finish the original scope on the original timeline. The response is: (1) immediately cap notification volume via aggressive batching and rate limiting to keep the existing system stable; (2) begin Kafka migration planning immediately, treating it as a plan replacement, not a plan addition; (3) communicate explicitly to stakeholders that the timeline has changed. We do not paper over this with optimism. The table in Revision 1 presented this as a tidy branch; it is not.

### Spike Handling: Diurnal vs. Event-Driven

**Diurnal peaks (3×, ~1,750/sec):** Handled by steady-state worker pool sizing. Workers are always running; they absorb the curve.

**Event-driven spikes (up to 20×, ~11,700/sec, lasting 60–120 seconds):** The queue is the absorber. The router continues accepting events and enqueuing them during a spike — queue depth grows, worker pools process at their maximum sustained rate, and the queue drains over the following minutes.

**Revised spike math — per-queue, not uniform distribution:**

A viral spike (a celebrity posts, a major live event triggers engagement) is not uniformly distributed across notification types. It is concentrated in P1 social notifications: likes, comments, shares, follows. The steady-state channel mix does not apply during a viral event.

Revised assumption: during a viral spike, 90% of spike volume hits the P1 queue, 8% hits P2 (digests and batch social), 2% hits P0 (security events are uncorrelated with viral content).

| Queue | Spike Share | Spike Volume (20×, 90 sec) | Additional Items |
|-------|-------------|---------------------------|-----------------|
| P0 | 2% | ~234/sec | ~21,000 |
| P1 | 90% | ~10,530/sec | ~947,700 |
| P2 | 8% | ~936/sec | ~84,240 |

**P1 drain time during viral spike:**

P1 workers sustain approximately 350 notifications/sec per worker at real APNs/FCM throughput with network latency (derived in Section 2 — worker sizing). With 15 P1 workers, sustained P1 throughput is ~5,250/sec.

Spike arrival rate into P1: ~10,530/sec.
Net accumulation rate during spike: 10,530 − 5,250 = ~5,280/sec.
Spike duration: 90 seconds.
Total P1 backlog at spike end: ~475,200 items.

Drain time after spike ends (P1 workers at full capacity, no new arrivals): 475,200 / 5,250 ≈ **91 seconds**.

Total P1 delay for an item at the back of the queue: up to ~3 minutes from spike start. This is acceptable for a social notification (someone liked your photo). It is not acceptable for P0 content, which is why P0 isolation matters.

**P0 behavior during viral spike:** P0 workers receive 2% of spike volume, or ~234/sec. With 8 P0 workers at ~400/sec each, P0 capacity is ~3,200/sec — far exceeding spike P0 volume. P0 latency is unaffected by viral events. This is the architectural guarantee of separate queues.

### SMS Cost Reality

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. The blended rate depends entirely on geographic distribution:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

The range is $240K–$1.38M/month. The SMS budget enforcement mechanism is specified in Section 3.4.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, month-2 recalibration authority |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), SMS budget enforcement |
| E3 | Preference management, user-facing API, suppression logic, notification coordination records |
| E4 | ElastiCache configuration and capacity planning, RDS schema and query performance, Datadog configuration |

**E4 scope — the honest version:**

Revision 1 acknowledged E4's scope was too large, then resolved it by switching to managed services while describing the residual scope as "a full-time job." That is not a resolution. Here is the actual restructuring:

ElastiCache and RDS on managed services eliminate operational tasks (replication management, backup configuration, failover mechanics, patching). What remains for E4 is: capacity planning reviews (monthly, 2 hours each), query performance investigation (reactive, estimated 4 hours/week average), Datadog dashboard and alert configuration (front-loaded in months 1–2, then maintenance), and on-call rotation participation shared across all 4 engineers.

This is not a full-time job. It is approximately 60% of one. The remaining 40% is E4's contribution to feature development — specifically, the reconciliation job for notification consistency (Section 2, in-app bypass), the partition management automation, and the month-2 monitoring instrumentation.

If query performance issues become a sustained time sink (more than 8 hours/week for more than two consecutive weeks), that is a signal that the schema or query patterns are wrong, not that E4 needs to work more hours. E1 and E3 are on the hook to fix the underlying problem.

**On-call:** All 4 engineers rotate. No engineer is the sole on-call for any component.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Block suppression check (Postgres, authoritative — not cached)
  - Preference check (Redis cache, 5-min TTL, write-through)
  - Priority assignment
  - Channel selection
  - Coordination record creation (for multi-channel events)
     │
     ├─► [P0 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P0 Worker Pool (8 workers)
     │
     ├─► [P1 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P1 Worker Pool (15 workers)
     │
     ├─► [P2 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P2 Worker Pool (20 workers)
     │
     └─► [In-App Store] (PostgreSQL — direct write, coordinated)
                    │
                    ▼
           [Channel Dispatcher]
             ├── Push (APNs / FCM)
             ├── Email (SendGrid)
             └── SMS (Twilio — budget-gated)
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archive)
                    │
                    ▼
           [Feedback Processor]
           (bounces, opens, failures, token invalidation)
                    │
                    ▼
           [Reconciliation Job]
           (every 5 minutes — resolves split-path consistency)
```

### Why Separate Queues, Not a Single Priority Queue

Workers dequeue in batches of 50. A worker that has claimed 50 P2 items will process all 50 before picking up any P0 item that arrives mid-batch. With 20 P2 workers running at peak, you can have 1,000 P2 items in-flight when a P0 security alert arrives. Under P2 volume at peak, this is a near-constant condition.

Separate queues fix this: P0 workers only consume from the P0 queue. A P0 item is processed within one batch cycle of a P0 worker becoming available — typically under 2 seconds. The cost is monitoring 3 queues instead of 1, which is a reasonable price for correct priority semantics.

**We use Redis Lists (LPUSH/BRPOP), not Sorted Sets.** Lists give O(1) push and pop with blocking semantics. FIFO within a priority level is correct behavior. Sorted Sets would add complexity without benefit.

### Worker Count Derivations — All Three Queues

**Methodology:** A single worker using HTTP/2 connection multiplexing to APNs or FCM can sustain approximately 200–400 requests/second under real network conditions. We use 350/sec as our working figure — the midpoint, discounted slightly for connection setup overhead, retry logic execution, and the fact that not all notifications are push (some route to email/SMS with different throughput characteristics). We validate this figure in load testing during month 1 and adjust before production.

**P0 workers:**

P0 notifications are security alerts and account compromise notices. Expected volume: <0.1% of total, or ~50,000/day at estimate. Burst scenario: 100,000 items arriving over 60 seconds = ~1,667/sec.

Required workers: 1,667 / 350 ≈ 4.8. We provision 8 — double the burst requirement — because P0 is the wrong place to be at capacity. The extra headroom covers the case where a security incident is larger than estimated and the case where individual worker throughput is lower than 350/sec due to provider-side rate limiting.

We do not auto-scale P0 workers. Container startup latency (30–60 seconds) means auto-scaled workers arrive after the incident has passed. The manual expansion runbook is written before launch. A circuit breaker alerts immediately if P0 queue depth exceeds 10,000 items.

**P1 workers:**

P1 notifications are social interactions: likes, comments, follows, mentions. At steady-state peak (1,750/sec total, 70% push through P1 primarily), P1 receives approximately 900/sec in normal operation. Normal P1 throughput requirement: 900 / 350 ≈ 2.6 workers.

We size for the viral spike case, not steady state. As derived in the spike section: during a viral event, P1 receives ~10,530/sec. Required workers to drain the spike within acceptable time: we target drain completion within 5 minutes of spike end. Acceptable drain rate: 475,200 items / 300 seconds = 1,584/sec minimum. Workers required: 1,584 / 350 ≈ 4.5. But we also need to handle ongoing steady-state P1 volume during drain, adding ~900/sec. Total required: (1,584 + 900) / 350 ≈ 7.1 workers.

We provision 15 workers — double the spike-drain requirement. The reasoning: P1 is where viral spikes land, and the cost of under-provisioning P1 is visible user-facing delay on the most engagement-critical notification type. The extra headroom also covers the case where our 350/sec throughput estimate is optimistic.

**P2 workers:**

P2 notifications are digests, batch social updates, and low-urgency content. At steady-state peak, P2 receives approximately 850/sec (the remainder after P0 and P1). Required workers: 850 / 350 ≈ 2.4.

P2 has explicit latency tolerance — items can wait up to 30 minutes. This means P2 workers can process in larger batches and we can afford to run fewer workers. We provision 20 workers, which is more than the steady-state requirement, for two reasons: (1) P2 