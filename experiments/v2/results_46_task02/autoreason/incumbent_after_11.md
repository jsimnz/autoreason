# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. The revision addresses eleven specific problems in the prior draft: the truncated TTL section is completed, all arithmetic is shown end-to-end, contradictions in the P0 failover model are resolved, the FCM per-device deduplication is fully specified, the 26-worker resource claim is backed with per-worker accounting, the tertiary alerting path is designed rather than named, the SMS spend cap race condition is closed, and the missing Section 1.4 is written.

**What changed and why:**

| Problem | Prior state | Resolution |
|---------|-------------|------------|
| Viral model inputs were asserted | Three unvalidated estimates multiplied together | Inputs are now explicitly labeled as estimates with stated uncertainty; the stress case logic is restructured to acknowledge this |
| TTL section truncated mid-sentence | "TTL = 2 hours (7,200 seconds) is" | Section completed with full derivation and consequence analysis |
| 3× queue arithmetic unverifiable | Redis runway cited without capacity basis | cache.r6g.large capacity derived; runway arithmetic shown |
| P0 failover contradicts hash routing | Consistent hash + drain-on-failure are incompatible | Replaced with priority queue routing; failover path specified |
| FCM deduplication stated but not designed | "Must deduplicate by user_id" with no implementation | Deduplication specified in Kafka routing and worker fetch logic |
| 26-worker fit unsupported | "With headroom" asserted | Per-worker resource profile provided; arithmetic shown |
| Tertiary alerting path not designed | Named as solved; no specification | PagerDuty + Twilio failover path fully specified |
| SMS spend cap race condition | Redis counter fails open; eviction policy unspecified | Counter in isolated Redis instance with no eviction; TTL and failsafe specified |
| Section 1.4 missing | Referenced four times; never written | Written in full |
| APNs 800/sec figure unvalidated pre-launch | Validated "in month 2" after launch | Validation moved to month 1 pre-launch; contingency connections pre-provisioned |
| Receipt decoupling consistency risk unacknowledged | Async receipts presented as pure upside | Lag SLO, monitoring, and outage behavior specified |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark | Validate against product analytics before provisioning final instance sizes; see Section 1.4 for re-sizing triggers |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark for social apps | Validate against registration data in month 1; see Section 1.4 for what changes at 40/60 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (modeled ceiling) | ~1,100/sec | Derived in Section 1.2; inputs are estimates |Validate against viral event logs at launch |
| Viral event inbound (2× stress case) | ~2,200/sec | Derived from input uncertainty bounds in Section 1.2 | — |
| Viral event inbound (3× stress case) | ~3,300/sec | Modeled for queue depth planning | — |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 1 pre-launch |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and connection count | Load test in month 1 pre-launch |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

**The iOS/Android split matters for the delivery model.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. Section 1.4 specifies what changes if the actual split is 40/60.

**The 17 notifications/DAU/day figure drives the entire sizing model.** Section 1.4 specifies what changes at 8/day and 35/day and defines a hard re-sizing trigger.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Inputs Explicitly Labeled as Estimates

**The honest framing:** The viral inbound model is built from three inputs that cannot be validated before launch. Multiplying estimates together produces an estimate, not a derivation. The value of showing the arithmetic is not that it makes the result more reliable — it is that it makes the inputs challengeable and the consequences of being wrong calculable.

**Inputs and their uncertainty:**

| Input | Point estimate | Uncertainty | Basis |
|-------|---------------|-------------|-------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Could plausibly be 2–10% of DAU (60K–300K) | No historical data; social platform benchmarks vary widely |
| Baseline notifications/sec per user in cohort | 34/day = 0.000394/sec | Depends on actual heavy-user distribution | Assumed 2× average; validate against user distribution in month 1 |
| Viral spike multiplier | 8× personal baseline | Could be 4–20× depending on content type and network structure | Sustained 15-minute spike; no pre-launch data |

**Modeled inbound ceiling (point estimate):**

```
Viral cohort inbound = 150,000 × 0.000394/sec × 8 = ~473/sec
Remaining DAU inbound = 2,850,000 × 17/day / 86,400 = ~560/sec
Total = ~1,033/sec → rounded to ~1,100/sec

With 20% infrastructure margin: ~1,320/sec as queue-sizing ceiling
```

**Stress case multipliers — derived from input uncertainty bounds:**

The stress cases are not arbitrary safety factors. They are the output of asking: how wrong could the inputs simultaneously be?

*2× case:* If the cohort is 50% larger than estimated (225,000) and the spike multiplier is 50% higher (12×):
```
225,000 × 0.000394 × 12 = ~1,065/sec viral cohort
1,065 + 560 = ~1,625/sec → approximately 1.5× the point estimate
```
Both inputs being wrong by 50% simultaneously produces a ~1.5× outcome. Both inputs being wrong by ~70% simultaneously produces the 2× case. Given no pre-launch historical data, a 70% error on both inputs is plausible for a first viral event. **The 2× case is the base stress case because it requires inputs to be wrong by approximately 70% simultaneously — plausible but not expected.**

*3× case:* Both inputs wrong by ~120% simultaneously (cohort = 330,000, multiplier = 17.6×). This represents a scenario where the product goes genuinely viral beyond pre-launch estimates. Historical examples exist for new social platforms. **We model it to understand the failure mode; we do not pre-provision for it.**

**The critical implication:** Because the inputs are estimates, the delivery floor must have margin above the modeled ceiling sufficient to absorb the 2× case. The delivery floor of ~1,200/sec is below the 2× inbound ceiling of ~2,200/sec. This means the 2× case produces queue growth. Section 1.2 specifies the response and the runway before action is required.

---

#### Stress Case Queue Arithmetic — Arithmetic Shown End-to-End

**cache.r6g.large capacity derivation:**

A cache.r6g.large provides 13.07 GB of memory. Notification messages in the queue contain: notification_id (16 bytes UUID), user_id (8 bytes), channel (1 byte), priority (1 byte), payload (average 512 bytes for push payload + metadata), retry_count (1 byte), created_at (8 bytes), expires_at (8 bytes). Total per message: approximately 555 bytes. With Redis overhead (hash table entries, per-key overhead, list node pointers): approximately 800 bytes per queued message at the 95th percentile.

Redis also holds: idempotency keys (24 bytes key + 1 byte value = 25 bytes each), user preference cache (approximately 200 bytes per active user), SMS atomic counters (negligible). At 3M DAU with preferences cached: 3,000,000 × 200 bytes = 600 MB. Idempotency keys at 50M/day with 8-hour TTL: at steady state, approximately 24M keys × 25 bytes = 600 MB. Total non-queue Redis usage: ~1.2 GB.

Available for queue storage: 13.07 GB − 1.2 GB = **~11.87 GB**.

At 800 bytes per queued message: **11.87 GB / 800 bytes ≈ 15.6 million messages maximum queue depth.**

**Runway calculations:**

| Scenario | Inbound | Delivery floor | Queue growth rate | Messages to fill Redis | Runway |
|----------|---------|---------------|-------------------|----------------------|--------|
| Derived ceiling (~1,100/sec) | 1,100/sec | 1,200/sec | 0 (net drain of 100/sec) | N/A | Infinite |
| 2× stress (~2,200/sec) | 2,200/sec | 1,200/sec | 1,000/sec | 15.6M messages | **4.3 hours** |
| 3× stress (~3,300/sec) | 3,300/sec | 1,200/sec | 2,100/sec | 15.6M messages | **2.1 hours** |
| 5× stress (~5,500/sec) | 5,500/sec | 1,200/sec | 4,300/sec | 15.6M messages | **1.0 hour** |

**Correction from prior draft:** The prior draft stated "~17 hours" for the 3× case. This was wrong. The correct figure is approximately 2.1 hours. The prior draft did not show the Redis capacity derivation, which concealed the error. **At 3× inbound, the on-call team has approximately 2 hours from queue growth onset to action before Redis fills.** P2 shedding begins at 30 minutes per the response table below; this provides 1.5 hours of buffer before the shedding decision must take effect.

**Response thresholds:**

| Scenario | Queue growth rate | Alert at | Required action | Time to Redis full from alert |
|----------|-----------------|----------|-----------------|-------------------------------|
| 2× stress | 1,000/sec | 15 minutes | Page on-call; evaluate horizontal scaling | ~4 hours |
| 3× stress | 2,100/sec | 15 minutes | P2 shedding enabled at 30 minutes | ~1.5 hours after shedding |
| 5× stress | 4,300/sec | Immediate | Emergency scaling + incident protocol | ~45 minutes |

P2 shedding at 3× reduces effective inbound by approximately 20% (P2 is ~20% of volume by design). This brings net queue growth from 2,100/sec to approximately 1,400/sec, extending runway from 2.1 hours to approximately 3.1 hours — sufficient time to scale horizontally.

---

#### P0 Failover Routing — Contradiction Resolved

**The problem with the prior design:** Consistent hashing on `notification_id % 2` assigns notifications deterministically to APNs connections. A drain-on-failure model moves all Workers 1A/1B traffic to APNs-2 when APNs-1 fails. These two mechanisms are incompatible without rehashing, because:
- In-flight notifications assigned to APNs-1 by hash that are mid-retry will be requeued to APNs-2, creating duplicates unless the idempotency key catches them.
- The idempotency key catches them only if the key has not expired, which depends on retry timing.
- Under connection failure, retry timing is non-deterministic.

**Resolution: Replace hash routing with priority queue routing.**

Consistent hashing is appropriate for distributing load across stateless workers. It is not appropriate for routing to a stateful resource (a persistent APNs connection) where failover must be handled. The correct model is:

```
P0 Push Architecture:
  APNs-1 (primary):   Worker-1A (active), Worker-1B (hot standby)
  APNs-2 (secondary): Worker-2A (active), Worker-2B (hot standby)

  Routing: Workers consume from a single P0 push queue.
           Worker-1A and Worker-1B hold APNs-1.
           Worker-2A and Worker-2B hold APNs-2.
           Each worker fetches from the queue independently.
           Load distributes naturally by fetch rate.

  Failover trigger: APNs-1 write errors exceed 3 in 10 seconds.
  Failover action:
    1. Worker-1A stops fetching from the P0 queue.
    2. Worker-1B stops fetching from the P0 queue.
    3. Workers 2A and 2B increase fetch rate to compensate.
    4. In-flight notifications on APNs-1 that have not received
       an APNs receipt are requeued to the P0 queue with their
       original notification_id preserved.
    5. Workers 2A/2B will fetch and attempt delivery.
    6. Idempotency key on notification_id prevents duplicate
       delivery if APNs-1 had already delivered before the error.
    7. Pager fires immediately.

  Failover consequence: Notifications in-flight on APNs-1 at
  the moment of failure experience at most one additional
  delivery attempt latency (the requeue-and-refetch cycle,
  typically <5 seconds). Duplicate delivery is prevented by
  the idempotency layer. Missed delivery is prevented because
  requeue is mandatory before Worker-1A/1B stop fetching.
```

**Why this is not circular with idempotency:** The idempotency key is written when the notification is first dispatched to a worker, not when APNs acknowledges delivery. The key records "this notification_id has been attempted." If APNs-1 delivered successfully but the receipt was lost in the connection failure, the idempotency key prevents re-dispatch. If APNs-1 failed to deliver, the key is present but delivery has not occurred — the retry logic must distinguish between "attempted and delivered" and "attempted and failed." This is done by checking the APNs receipt before writing the idempotency key as "delivered."

**Failure mode table:**

| Failure | Detection | Response | P0 impact |
|---------|-----------|----------|-----------|
| Worker-1A crashes | Heartbeat miss within 5 seconds | Worker-1B promotes; pager fires | Zero: Worker-1B holds APNs-1 |
| APNs-1 connection drops | Write error on Worker-1A | Worker-1A reconnects (<2 seconds HTTP/2); Worker-1B takes load | <2 seconds degradation |
| APNs-1 endpoint unavailable (>10 seconds) | 3 errors in 10 seconds | Workers drain to APNs-2; requeue in-flight; pager fires | <5 seconds latency spike |
| Both APNs connections fail | All P0 writes fail | Incident protocol; FCM fallback where token exists; SMS fallback for security alerts | Degraded; Section 5 |

---

#### APNs 800/sec/Connection — Validation Moved Pre-Launch

**The prior draft deferred validation to month