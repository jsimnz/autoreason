# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated ~50M notifications/day across push, email, in-app, and SMS channels. Three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — a correctness decision, not a scale decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct, ElastiCache, RDS. Engineering time goes to integration quality, not infrastructure plumbing.
3. **Incremental delivery** — working system by month 2, iterated through month 5, hardened in month 6.

**Four honest statements upfront:**

The 17 notifications/user/day figure that drives all sizing is a planning assumption, not a measured fact. We get early signal in week 2 of beta from a 50K-user cohort — not month 2. The architecture has a validated checkpoint before full commitment. Every sizing decision should be read as "correct at estimated volume, subject to week-2 revision."

The spike model assumes a specific shape (smooth ramp, 90-second duration, 20× peak). Real viral events may not conform to this shape. Section 1.3 describes what happens when they don't.

P0 worker throughput is derived from the actual P0 channel mix (SMS + email), not from push benchmarks. The 350/sec push figure does not apply to P0.

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

**The problem with month-2 calibration:** The previous version of this document acknowledged that the 17/day figure drives every sizing decision, then proposed validating it at month 2 — after the architecture was designed, built, and partially deployed. The >5× contingency explicitly invalidated the 6-month plan if the figure was wrong. Honesty about the risk is not a substitute for reducing it.

**What we do instead:** We get signal before committing to the architecture, not after.

**Week 2 of beta:** We instrument a 50K-user cohort from the first day of beta. This is not a large-scale load test — it is behavioral measurement. We measure actual notifications generated per active user per day and extrapolate to full scale. A 50K cohort is large enough to capture the distribution (heavy users, casual users, dormant users) and detect if the true figure is 5/day or 50/day.

**The decision gate:** At the end of week 2, E1 reviews the cohort data. If the measured per-user rate differs from 17/day by more than 2×, the architecture decision is revisited before the full beta launch. This is a concrete checkpoint, not a monitoring intention.

**Why this works:** Notification generation rate is driven by user behavior (posting, liking, following) and application logic (what events trigger notifications). Both are measurable from a small cohort. The 50K cohort does not need to stress-test the infrastructure — it needs to produce a reliable behavioral signal.

**Why this is not a complete solution:** A 50K cohort may not capture viral dynamics or power-user behavior at scale. The week-2 figure is a better estimate, not a guaranteed accurate one. We still maintain the recalibration table below, but the thresholds now trigger against measured data from week 2, not against the original planning assumption.

| Actual Volume vs. Week-2 Estimate | Action Required | Decision Owner | Window |
|-----------------------------------|-----------------|----------------|--------|
| ≤ 2× week-2 estimate | Increase P1/P2 worker counts; Redis capacity unchanged | E1 | 72 hours |
| 2–5× week-2 estimate | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier | E1 | 72 hours |
| > 5× week-2 estimate | See contingency below | Engineering lead | 72 hours |

**The >5× contingency, restated with accurate timelines:**

Discovering at month 2 that volume exceeds 5× the week-2 estimate means the queue infrastructure is undersized. The previous version of this document stated a Kafka migration would take "3–4 months." That estimate was not grounded. For a team of 4 engineers running a live system at 250M+ notifications/day while simultaneously building new infrastructure, a realistic Kafka migration is 5–7 months. This does not fit inside the remaining project timeline under any optimistic scenario.

The honest response: (1) immediately cap notification volume via aggressive batching and rate limiting to keep the existing system stable; (2) treat the timeline as broken and communicate this explicitly to stakeholders — not as a risk, but as a fact; (3) decide whether to hire additional engineers or reduce product scope before beginning migration planning. We do not paper over this with an optimistic timeline.

The week-2 checkpoint exists specifically to surface this scenario before the 6-month plan is locked, not after.

### 1.3 Spike Handling: Shape Assumptions and Their Limits

**Two types of peaks require different handling.**

**Diurnal peaks (3× sustained, ~1,750/sec):** Handled by steady-state worker pool sizing. Workers are always running; they absorb the curve.

**Viral spikes:** The previous version of this document modeled a viral spike as 20× peak multiplier lasting 90 seconds, then derived drain times from that shape. The shape assumption was never justified. We correct that here.

**What we actually know about viral spike shapes:**

A celebrity post or coordinated sharing event can produce a near-step-function increase in notification generation, not a smooth ramp. The 90-second duration assumption is plausible for a single viral post that fans out through a social graph — the fanout completes, then the rate drops. But a sustained viral event (a live event, a breaking news story, a trending topic) can hold elevated rates for 10–30 minutes, not 90 seconds.

**Two spike scenarios we design for:**

*Scenario A — Short burst (the 90-second model):* A single viral post fans out through the social graph. Generation rate spikes to 20× (~35,000/sec instantaneous) for 60–120 seconds, then drops to near-normal. The queue absorbs the burst; workers drain over the following minutes.

*Scenario B — Sustained elevated rate:* A live event or trending topic holds 5–10× above peak for 10–30 minutes. This is not a burst the queue absorbs — it is a sustained load that tests whether worker throughput is sufficient to keep pace.

**Why this matters for sizing:** Scenario A is handled by queue depth. Scenario B requires worker throughput to match or exceed the elevated arrival rate, or the queue grows unboundedly. We size P1 workers for Scenario B at 5× sustained (see Section 2.3), which also handles Scenario A.

**The honest limit:** We cannot design for every possible spike shape. What we can do is instrument queue depth in real time and have a runbook for manual worker scaling if depth grows faster than workers can drain. The runbook is written before launch.

**Revised spike math — P1 queue under Scenario B (10× sustained for 10 minutes):**

P1 arrival rate at 10× sustained peak: ~17,500/sec. With 15 P1 workers at P1-appropriate throughput (see Section 2.3), sustained P1 capacity is ~5,250/sec. Net accumulation: ~12,250/sec. Over 10 minutes: ~7.35M items in queue.

This is not acceptable. It drives the worker count decision in Section 2.3 — we size P1 workers to handle sustained elevated load, not just burst absorption.

**P0 behavior during any spike scenario:** P0 workers receive security and account compromise events. These are uncorrelated with viral content spikes. P0 queue depth is unaffected by viral events. This is the architectural guarantee of separate queues.

### 1.4 SMS Cost Reality

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. The blended rate depends entirely on geographic distribution:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

The range is $240K–$1.38M/month. The SMS budget enforcement mechanism is described in full in Section 3.4 — it is a concrete technical gate, not a statement of intent.

### 1.5 Team Allocation

| Engineer | Primary Responsibility | Explicit Exclusions |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, week-2 recalibration authority | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), SMS budget enforcement (Section 3.4) | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic, notification coordination records | Delivery workers |
| E4 | ElastiCache configuration and capacity planning, RDS schema and query performance, Datadog configuration, reconciliation job (Section 2.5), partition management automation | See scope note below |

**The E4 scope problem, corrected:**

The previous version of this document claimed E4's residual scope after managed services was "approximately 60% of one engineer's time," with the remaining 40% going to reconciliation job development, partition management automation, and production monitoring instrumentation. This arithmetic was wrong. Reconciliation job development (Section 2.5) is a 3–4 week engineering effort. Partition management automation is 2–3 weeks. Production monitoring instrumentation is front-loaded but substantial. These are not 40% tasks.

**Actual E4 allocation by month:**

| Month | Primary Focus | Estimated Hours/Week |
|-------|--------------|---------------------|
| 1 | RDS schema design, ElastiCache configuration, Datadog setup | 40 |
| 2 | Reconciliation job development (Section 2.5) | 40 |
| 3 | Partition management automation, query performance work | 40 |
| 4–5 | Ongoing monitoring, performance investigation, capacity planning | 30 |
| 6 | Hardening, runbook completion, load testing support | 35 |

This is a full-time allocation with no slack. What this means concretely: E4 cannot absorb unplanned work without dropping something scheduled. If query performance issues become a sustained time sink (more than 8 hours/week for more than two consecutive weeks), E1 and E3 are responsible for fixing the underlying schema or query pattern — not E4 working extra hours. E4's schedule has no buffer to absorb problems that belong to other owners.

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
  - Block suppression check (Postgres direct — enforcement path,
    structurally isolated from preference cache; see Section 2.2)
  - Preference check (Redis cache, 5-min TTL, write-through)
  - Priority assignment
  - Channel selection
  - Coordination record creation (for multi-channel events)
     │
     ├─► [P0 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P0 Worker Pool (8 workers — see Section 2.3)
     │
     ├─► [P1 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P1 Worker Pool (30 workers — see Section 2.3)
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

**Block suppression isolation — technical enforcement, not convention:**

The previous version of this document stated that block suppression and preference caching were "different code paths, not asserted separation," then acknowledged this provided no technical guarantee against a future engineer caching the block check. This is a real problem: the safety property degrades silently if the code path is modified.

We enforce the separation structurally. The block suppression check is implemented as a call to a `BlockSuppression` service interface whose only implementation queries PostgreSQL directly. The `BlockSuppression` interface has no cache parameter, no TTL parameter, and no method signature that would accept a cache layer. The preference cache is accessed through a separate `PreferenceCache` interface. These are not the same interface with different implementations — they are different interfaces with different contracts, enforced at the type level.

This does not prevent a future engineer from writing a new `CachedBlockSuppression` implementation. What it does: makes the safety violation visible and deliberate rather than accidental. A code review that sees `CachedBlockSuppression` being wired in has a clear signal to reject it. A code review that sees `blockSuppression.check()` being replaced with `preferenceCache.check()` would fail the type checker.

The test suite includes an integration test that verifies block suppression bypasses cache under load. This test runs in CI on every commit.

### 2.3 Worker Count Derivations

**P0 workers — corrected throughput model:**

The previous version of this document derived P0 worker counts using the 350 notifications/sec per worker figure from APNs/FCM HTTP/2 benchmarks.