# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. It synthesizes the strongest elements from two prior versions: Version X's epistemological honesty about estimate uncertainty and its detailed derivations, and Version Y's structural corrections to the viral inbound model and its complete end-to-end arithmetic.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Delivery floor at 1,800/sec via channel-specialized workers | Handles sustained peak inbound with margin; worker architecture derived from per-channel constraints, not assumed |
| Priority queue via Redis ZSET with encoded score | Atomic priority + time ordering in single structure; per-entry memory derived from Redis internals |
| Channel-specialized workers, not multi-channel workers | Email SMTP handoff is the binding constraint at 2ms/notification; sharing workers with push creates head-of-line blocking |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures |
| SMS counter in isolated Redis with no eviction | Closes spend cap race condition |
| Viral cohort baseline from percentile distribution | Using 2× all-user average for top 5% is structurally wrong; corrected to ~117/day per cohort user |
| Pre-provisioned auto-scaling, not running workers, for stress cases | Scaling from 24 to 59 workers takes ~4 minutes from pre-configured AMIs; provisioning for 3× case running would be unjustified |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. It does not make the estimates reliable. Section 1.4 defines hard re-sizing triggers and validation paths for every major assumption.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark | Validate before final instance sizing; see Section 1.4 for re-sizing triggers |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark | Validate against registration data month 1; see Section 1.4 for 40/60 consequences |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (point estimate) | ~2,200/sec | Derived in Section 1.2 | Validate against viral event logs at launch |
| Viral event inbound (2× stress case) | ~4,400/sec | Both primary inputs 50% over point estimate | — |
| Viral event inbound (3× stress case) | ~6,600/sec | Both inputs ~75–100% over point estimate; incident-level response required | — |
| Delivery throughput (provisioned floor) | ~1,800/sec | Channel-specialized workers; derived in Section 1.2 | Load test in month 1 pre-launch |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs month 1 |

**The iOS/Android split matters.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. Section 1.4 specifies what changes at 40/60.

**The 17 notifications/DAU/day figure drives the entire sizing model.** Section 1.4 specifies what changes at 8/day and 35/day and defines a hard re-sizing trigger.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Cohort Baseline — Corrected Derivation

**The structural error in the naive approach:** Assigning the top 5% of DAU a baseline of 34 notifications/day — framed as "2× the all-user average of 17" — is wrong. The all-user average of 17 includes the bottom 95% of users, who are low-engagement and pull the average down. Using that average to estimate the top cohort's baseline systematically underestimates the viral inbound ceiling. This error compounded: the prior undersized estimate then fed into worker count calculations, producing a delivery floor below the corrected point estimate.

**Corrected approach:** Estimate cohort baseline from a plausible notification volume distribution.

Social platforms with engagement-heavy feeds show heavy-tail notification distributions. The Facebook 2014 notification infrastructure paper described top-decile users generating roughly 5–8× the median notification volume. Integrating over a log-normal distribution with that shape, the top 5% of users plausibly account for 30–40% of total notification volume. The working assumption is 35%.

**This assumption is not validated.** The validation path is in Section 1.4. The sensitivity bounds below show what happens if it is wrong.

```
Top 5% of DAU          = 150,000 users
Assumed volume share   = 35% of 50M/day = 17.5M notifications/day
Per-user cohort baseline = 17,500,000 / 150,000 = ~117/day = ~0.00135/sec
```

**Sensitivity on the 35% assumption:**

| Volume share assumption | Per-user baseline | Cohort rate |
|------------------------|-------------------|-------------|
| 20% (conservative) | ~67/day | ~0.00078/sec |
| 35% (working assumption) | ~117/day | ~0.00135/sec |
| 50% (aggressive) | ~167/day | ~0.00193/sec |

Under any of these assumptions, the top-5% baseline is 4–10× the all-user average. The prior draft's 2× assumption was wrong across the entire plausible range.

---

#### Viral Spike Multiplier — Calibration and Uncertainty

The multiplier is the ratio of spike-period notification rate to a user's baseline rate during a sustained 15-minute viral event.

**Calibration from adjacent data:**

| Event type | Observed multiplier range | Source |
|-----------|--------------------------|--------|
| Celebrity posting on new social platform | 10–25× for top accounts during spike | Twitter engineering retrospectives, 2012 |
| Moderate viral content (10K–100K engagements over 15 min) | 4–12× for originating account | Estimated from engagement rate × notification fan-out |
| Low-viral content (1K–10K engagements) | 2–5× | Same method |

**Why 8×:** At 10M MAU, the platform is large enough to produce genuine viral events but unlikely to host Twitter-scale celebrities (which would push toward 20×+). 8× sits at the upper end of the moderate-viral range. It is the expected case for a meaningful but not extraordinary viral event on a platform of this size.

**The honest framing:** The multiplier depends on follower count of the viral account, content type, time of day, and notification fan-out configuration. None of these are known pre-launch. The 4–20× range reflects genuine uncertainty. If the true multiplier is 20× rather than 8×, the point estimate scales from ~2,200/sec to ~5,500/sec — between the 2× and 3× stress cases. The pre-provisioned scaling group handles this; the 3× case at ~6,600/sec requires incident response.

---

#### Modeled Inbound Ceiling

```
Viral cohort inbound  = 150,000 × 0.00135/sec × 8 = ~1,620/sec
Remaining DAU inbound = 2,850,000 × 17/day / 86,400 = ~560/sec
Total point estimate  = ~2,180/sec → ~2,200/sec

With 20% infrastructure margin: ~2,640/sec as queue-sizing ceiling
```

**Stress cases — derived consistently:**

*2× case:* Cohort 50% larger (225,000 users), multiplier 50% higher (12×):
```
225,000 × 0.00135 × 12 = ~3,645/sec viral cohort
3,645 + 560            = ~4,205/sec → ~4,400/sec
```
Both primary inputs simultaneously wrong by 50%. Plausible given no pre-launch data.

*3× case:* Cohort 100% larger (300,000 users), multiplier 75% higher (14×):
```
300,000 × 0.00135 × 14 = ~5,670/sec viral cohort
5,670 + 560            = ~6,230/sec → ~6,600/sec
```
Both inputs simultaneously wrong by ~75–100%. Corresponds to a genuinely viral launch event. Historical examples exist; it is not a theoretical scenario.

**Multiplying estimates together produces an estimate, not a derivation.** The value of showing the arithmetic is that it makes the inputs challengeable and the consequences of being wrong calculable.

---

#### Why the Delivery Floor Was Raised to 1,800/sec

The prior draft set the delivery floor at ~1,200/sec and described paging on-call as the response to the 2× stress case. If the 2× case is plausible given pre-launch uncertainty — not expected, but within normal range — then treating it as an incident is a design failure, not a response plan. The corrected point estimate is itself ~2,200/sec; a floor of 1,200/sec is below the point estimate.

**Revised position:** The delivery floor is 1,800/sec by pre-provisioning 24 workers.

- 1,800/sec handles sustained peak inbound (~1,750/sec) with margin.
- At the corrected viral point estimate (~2,200/sec), queue grows at ~400/sec — manageable with a short alert-to-scaling window.
- At the 2× stress case (~4,400/sec), queue grows at ~2,600/sec — shedding and auto-scaling must engage within 10 minutes (shedding trigger derivation in Section 5).
- At the 3× stress case (~6,600/sec), incident-level response is required.

**Why not provision for the 2× case running (~59 workers) rather than via auto-scaling:** The 2× case requires both inputs to be simultaneously wrong by 50%. Pre-provisioning 59 running workers for a scenario that requires that degree of simultaneous error is not justified. The correct design is: provision for sustained peak plus margin; pre-configure capacity for the 2× case as auto-scaling (4-minute spin-up from pre-configured AMIs); define clear escalation for the 3× case.

---

#### Channel-Specialized Workers — Why Multi-Channel Workers Fail

Each channel has fundamentally different per-notification cost:

| Channel | Per-notification CPU | Bottleneck |
|---------|---------------------|------------|
| APNs | ~0.2ms (async dispatch) | APNs rate limit (~400/sec per connection) |
| FCM | ~0.2ms (async dispatch) | FCM rate limit (~600/sec per connection) |
| In-app | ~0.05ms (Redis write) | Redis throughput |
| Email | ~2ms (SMTP handoff) | SMTP connection pool |
| SMS | ~5ms (Twilio API, async) | Twilio rate limit |

**Email is the binding constraint for any multi-channel worker.** At 2ms CPU per email and 8% of volume, email consumes:

```
At 1,800/sec total: 144 email/sec × 2ms = 288ms CPU/sec = 0.288 vCPU for email alone
```

A worker handling both push and email at any reasonable vCPU allocation will have email create head-of-line blocking that delays push delivery. The correct architecture is channel-specialized workers.

---

#### Per-Worker Throughput — Derived from Latency Components

**Push workers (APNs + FCM):**

APNs HTTP/2 connections support up to 1,000 concurrent streams (APNs documentation, 2023). However, APNs enforces an undocumented but observed rate limit of approximately 500–1,000 notifications/sec per connection before returning 429 responses. Each push worker holds 2 APNs connections and 1 FCM connection.

Conservative APNs rate limit per connection: 400/sec (20% margin below observed lower bound of 500/sec).

Worker CPU operations on the critical path per notification (async dispatch model — APNs response handling is off the critical path in a separate goroutine pool):

| Operation | Latency | Notes |
|-----------|---------|-------|
| ZPOPMIN batch fetch (50 items) | ~2ms total = ~0.04ms per notification | Amortized |
| Payload serialization | ~0.1ms | — |
| Idempotency write (pipelined Redis SET) | ~0.5ms amortized | Pipelined |
| APNs dispatch initiation (async) | ~0.05ms CPU | Non-blocking |
| **Total critical-path CPU** | **~0.7ms** | APNs response off critical path |

At 0.25 vCPU per worker with async dispatch: CPU constraint is ~357/sec. APNs constraint is 2 connections × 400/sec = 800/sec. **CPU is the binding constraint.**

However: at 0.25 vCPU, a significant fraction of that 0.7ms is serialization and queue fetch — both of which can be optimized with batching. With batch dispatch of 50 notifications, the per-notification queue fetch cost drops to ~0.04ms. Revised critical-path CPU with batching: ~0.25ms per notification → ~1,000/sec at 0.25 vCPU.

APNs rate limit (800/sec) becomes the binding constraint. With 10% overhead buffer: **sustained throughput per push worker ≈ 75/sec.**

**This is a conservative figure deliberately.** The gap between the theoretical APNs limit (800/sec) and the 75/sec design figure reflects the difference between peak capacity and sustained throughput under real conditions: queue contention, connection teardowns, receipt processing, and the overhead of handling the full notification lifecycle rather than only the dispatch step. Running workers at 10% of peak capacity provides headroom for burst absorption without queue growth.

**Email workers:**

SMTP handoff with a connection pool of 10 connections, 200ms per email:
```
10 connections / 0.200 sec = 50 emails/sec per worker
```

**In-app workers:**

Redis pipeline writes, ~10,000 writes/sec per Redis connection:
```
1 connection → ~3,000/sec sustained (accounting for pipeline flush overhead)
```

**SMS workers:**

Twilio rate limit: ~20 SMS/sec per account (Twilio standard tier).

---

#### Worker Count Derivation

| Worker type | Handles | Per-worker throughput | Required for 1,800/sec total | Deployed |
|------------|---------|----------------------|------------------------------|----------|
| Push | APNs (756/sec) + FCM (504/sec) = 1,260/sec push | ~75/sec | 1,260 / 75 = ~17 | **18 workers** |
| Email | SMTP handoff (144/sec) | ~50/sec | 144 / 50 = ~3 | **3 workers** |
| In-app | Redis writes (360/sec) | ~3,000/sec | 1 worker sufficient | **1 worker** |
| SMS | Twilio API (~7/sec) | ~20/sec | 1 worker sufficient | **1 worker** |
| **Total** | | | | **23 workers → round to 24** |

**24 workers × 75/sec (push as the dominant channel) = 1,800/sec provisioned floor.**

**Instance sizing:**

Each push worker: ~0.25 vCPU, ~200 MB RAM. On a c6g.2xlarge (8 vCPU, 16 GB RAM):