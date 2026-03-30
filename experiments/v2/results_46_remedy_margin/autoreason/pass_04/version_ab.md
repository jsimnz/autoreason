# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — a correctness decision, not a scale decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct, ElastiCache, RDS. Engineering time goes to integration quality, not infrastructure plumbing.
3. **Incremental delivery** — working system by month 2, iterated through month 5, hardened in month 6.

**Three honest statements upfront:**

The 17 notifications/user/day figure that drives all sizing is a planning assumption, not a measured fact. We instrument a 50K-user cohort from day one of beta and review at week 2 — before architecture decisions are locked, not after they are deployed. Every sizing decision should be read as "correct at estimated volume, subject to week-2 revision."

The spike model assumes a specific shape (smooth ramp, 90-second duration, 20× peak). Real viral events may not conform. Section 1.3 describes what happens when they don't, including a sustained-load scenario that drives worker count decisions.

The operational surface described here is at the edge of what 4 engineers can safely own. Section 7 names what we cut and why. If scope is added mid-project, something on that list gets dropped — we say it explicitly rather than silently accept overcommitment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Planning assumption; see Section 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike multiplier | 20× instantaneous | See Section 1.3 for shape assumptions |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### 1.2 The 17/Day Figure: Early Validation, Not Month-2 Discovery

This number drives queue worker counts, Redis sizing, database partitioning, and cost projections. Getting it wrong by 3× means every sizing decision is wrong simultaneously. Discovering that at month 2 — after architecture is built and partially deployed — leaves no room to respond.

**What we do instead:** We instrument a 50K-user cohort from the first day of beta and measure actual notifications generated per active user per day. This is behavioral measurement, not a load test. A 50K cohort is large enough to capture the distribution across heavy, casual, and dormant users, and to detect whether the true figure is 5/day or 50/day.

**The decision gate:** At the end of week 2, E1 reviews cohort data. If the measured per-user rate differs from 17/day by more than 2×, the architecture decision is revisited before full beta launch. This is a concrete checkpoint, not a monitoring intention.

**What this does not fully solve:** A 50K cohort may not capture viral dynamics or power-user behavior at scale. The week-2 figure is a better estimate, not a guaranteed accurate one. We maintain the recalibration table below, but thresholds now trigger against the week-2 measured figure, not the original planning assumption.

**Decision owner:** E1, as the engineer responsible for core pipeline architecture. The decision window is 72 hours from the moment measured volume crosses a threshold — not 72 hours from the next review meeting. The >5× case requires explicit sign-off from the engineering lead because it invalidates the 6-month plan.

| Actual Volume vs. Week-2 Estimate | Action Required | Decision Owner | Window |
|-----------------------------------|-----------------|----------------|--------|
| ≤ 2× week-2 estimate | Increase P1/P2 worker counts; Redis capacity unchanged | E1 | 72 hours |
| 2–5× week-2 estimate | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier | E1 | 72 hours |
| > 5× week-2 estimate | See contingency below | Engineering lead | 72 hours |

**The >5× contingency, stated plainly:** Discovering that volume exceeds 5× the week-2 estimate means the queue infrastructure is undersized. A Kafka migration for a team of 4 engineers running a live system at 250M+ notifications/day while building new infrastructure is realistically 5–7 months — not the 3–4 month figure that appears in optimistic plans. This does not fit inside the remaining project timeline under any scenario.

The honest response: (1) immediately cap notification volume via aggressive batching and rate limiting to keep the existing system stable; (2) treat the timeline as broken and communicate this explicitly to stakeholders — not as a risk, but as a fact; (3) decide whether to hire additional engineers or reduce product scope before beginning migration planning. The week-2 checkpoint exists specifically to surface this scenario before the 6-month plan is locked.

### 1.3 Spike Handling: Shape Assumptions and Their Limits

Diurnal peaks and viral spikes are different problems requiring different solutions.

**Diurnal peaks (3×, ~1,750/sec):** Handled by steady-state worker pool sizing. Workers are always running; they absorb the curve.

**Viral spikes:** The queue is the absorber, not the worker pool. The router continues accepting events and enqueuing them during a spike. We do not auto-scale worker pools to chase a short spike — container startup time (30–60 seconds) means auto-scaled workers arrive after the spike has passed.

**Two spike scenarios we design for:**

*Scenario A — Short burst:* A single viral post fans out through the social graph. Generation rate spikes to 20× (~35,000/sec instantaneous) for 60–120 seconds, then drops to near-normal. The queue absorbs the burst; workers drain over the following minutes.

*Scenario B — Sustained elevated rate:* A live event or trending topic holds 5–10× above peak for 10–30 minutes. This is not a burst the queue absorbs — it is a sustained load that tests whether worker throughput is sufficient to keep pace. Scenario B drives the P1 worker count decision.

**The honest limit:** We cannot design for every possible spike shape. We instrument queue depth in real time and maintain a runbook for manual worker scaling if depth grows faster than workers can drain. The runbook is written before launch.

**Spike volume distribution:** A viral spike is not uniformly distributed across priority levels. It concentrates in P1 social notifications. P0 security events are uncorrelated with viral content.

| Queue | Spike Share | Spike Arrival Rate (20×) | Capacity (workers × throughput) | Net Accumulation |
|-------|-------------|--------------------------|----------------------------------|-----------------|
| P0 | 2% | ~234/sec | ~3,200/sec (8 workers) | None — capacity far exceeds arrival |
| P1 | 90% | ~10,530/sec | ~5,250/sec (15 workers) | ~5,280/sec during spike |
| P2 | 8% | ~936/sec | ~7,000/sec (20 workers) | None at Scenario A duration |

**P1 drain time under Scenario A (90-second burst):**
Backlog at spike end: ~475,200 items. Drain rate after spike: 5,250/sec. Drain time: ~91 seconds. Total P1 delay for an item at the back of the queue: up to ~3 minutes from spike start. Acceptable for a social notification.

**P1 behavior under Scenario B (10× sustained for 10 minutes):**
At 10× sustained, P1 arrival rate is ~17,500/sec against 5,250/sec capacity. Net accumulation: ~12,250/sec. Over 10 minutes: ~7.35M items. This is not acceptable and is the primary reason P1 is sized at 15 workers rather than the 7–8 that Scenario A alone would require. See Section 2.3 for the full derivation.

**P0 behavior during any spike scenario:** P0 workers receive security and account compromise events. These are uncorrelated with viral content spikes. P0 queue depth is unaffected. This is the architectural guarantee of separate queues.

### 1.4 SMS Cost Reality

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. The blended rate depends entirely on geographic distribution:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

The range is $240K–$1.38M/month. This is not a rounding error. The SMS gating logic in Section 3.4 is designed around a hard monthly budget cap, not a cost-per-message assumption. We set the cap conservatively at launch, measure actual geographic distribution over the first 30 days, and adjust.

### 1.5 Team Allocation

| Engineer | Primary Responsibility | Explicit Exclusions |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, week-2 recalibration authority | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), SMS budget enforcement (Section 3.4) | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic, notification coordination records | Delivery workers |
| E4 | ElastiCache configuration and capacity planning, RDS schema and query performance, Datadog configuration, reconciliation job (Section 2.5), partition management automation | See scope note below |

**The E4 scope problem, stated directly:**

Managed services eliminate replication management, backup configuration, failover mechanics, and patching. What remains for E4: capacity planning reviews (monthly, ~2 hours each), query performance investigation (reactive, estimated 4 hours/week average), Datadog dashboard and alert configuration (front-loaded in months 1–2, then maintenance), and on-call rotation participation.

That is approximately 60% of one engineer's time. The remaining 40% covers: the reconciliation job for notification consistency (Section 2.5) — a 3–4 week engineering effort; partition management automation — 2–3 weeks; and production monitoring instrumentation — front-loaded but substantial.

| Month | E4 Primary Focus | Estimated Hours/Week |
|-------|-----------------|---------------------|
| 1 | RDS schema design, ElastiCache configuration, Datadog setup | 40 |
| 2 | Reconciliation job development (Section 2.5) | 40 |
| 3 | Partition management automation, query performance work | 40 |
| 4–5 | Ongoing monitoring, performance investigation, capacity planning | 30 |
| 6 | Hardening, runbook completion, load testing support | 35 |

This is a full-time allocation with no slack. If query performance issues become a sustained time sink (more than 8 hours/week for more than two consecutive weeks), that is a signal the schema or query patterns are wrong — not that E4 needs to work more hours. E1 and E3 are responsible for fixing the underlying problem.

**On-call:** All 4 engineers rotate. No engineer is the sole on-call for any component.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Block suppression check (Postgres direct — structurally isolated;
    see Section 2.2)
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
     └─► [In-App Store] (PostgreSQL — direct write, bypasses queue;
                         ordering implications described in Section 2.6)
                    │
                    ▼
           [Channel Dispatcher]
             ├── Push (APNs / FCM)
             ├── Email (SendGrid)
             └── SMS (Twilio — budget-gated per Section 3.4)
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
           (every 5 minutes — fully specified in Section 2.5)
```

### 2.2 Why Separate Queues, Not a Single Priority Queue

Workers dequeue in batches of 50. A worker that has claimed 50 P2 items will process all 50 before picking up any P0 item that arrives mid-batch. With 20 P2 workers running at peak, you can have 1,000 P2 items in-flight when a P0 security alert arrives. Under P2 volume at peak, this is a near-constant condition.

Separate queues fix this: P0 workers only consume from the P0 queue. A P0 item is processed within one batch cycle of a P0 worker becoming available — typically under 2 seconds. The cost is monitoring 3 queues instead of 1, which is a reasonable price for correct priority semantics.

**We use Redis Lists (LPUSH/BRPOP), not Sorted Sets.** Lists give O(1) push and pop with blocking semantics. FIFO within a priority level is correct behavior. Sorted Sets would add complexity without benefit.

**Block suppression isolation — structural enforcement, not convention:**

The block suppression check is implemented as a call to a `BlockSuppression` service interface whose only implementation queries PostgreSQL directly. The `BlockSuppression` interface has no cache parameter, no TTL parameter, and no method signature that would accept a cache layer. The preference cache is accessed through a separate `PreferenceCache` interface. These are not the same interface with different implementations — they are different interfaces with different contracts, enforced at the type level.

This does not prevent a future engineer from writing a new `CachedBlockSuppression` implementation. What it does: makes any safety violation visible and deliberate rather than accidental. A code review that sees `CachedBlockSuppression` being wired in has a clear signal to reject it. A code review that sees `blockSuppression.check()` being replaced with `preferenceCache.check()` would fail the type checker.

The test suite includes an integration test that verifies block suppression bypasses cache under load. This test runs in CI on every commit.

**The race condition preference caching does not fully prevent:** Between the PostgreSQL write and the Redis cache invalidation on a preference update, a concurrent read can fetch the old value and cache it with a fresh TTL. The result is a preference change taking up to 10 minutes to propagate in the worst case. We accept this. The consequence is a user receiving one notification they had just disabled — annoying, not dangerous. Block suppression never goes through this path.

### 2.3 Worker Count Derivations

**Methodology:** A single worker using HTTP/2 connection multiplexing to APNs or FCM can sustain approximately 200–400 requests/second under real network conditions. We use 350/sec as our working figure — the midpoint