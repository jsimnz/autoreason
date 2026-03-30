# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived with visible arithmetic or explicitly labeled as an estimate with a stated validation path. Every tradeoff names what is being sacrificed and why that sacrifice is acceptable given the constraints of 4 engineers and 6 months.

**Core design principles:**

1. **Conservatism belongs in the delivery floor, not the inbound ceiling.** An inflated inbound ceiling produces an over-provisioned queue model and conceals the real binding constraints.
2. **Stress cases must be derived, not asserted.** A 2× multiplier with no justification is not conservative — it is arbitrary. Each stress case below is derived from explicit model error bounds.
3. **P0 infrastructure is never shared.** OTPs and security alerts do not compete with social engagement volume under any load condition.
4. **Workers are sized to connections, not to compute.** APNs connections are the binding throughput constraint; excess workers produce idle capacity, not throughput.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Derived viral inbound ceiling (~1,100/sec) rather than asserted round number | Arithmetically honest; produces correct queue sizing and Redis runway |
| Workers sized to APNs connections | APNs connections are the binding constraint; independent worker sizing produces systematic idle capacity |
| P0 gets 2 dedicated APNs connections | Connection-level failures block all workers on that connection; a second connection costs nothing and eliminates this failure mode |
| TTL derived from retry schedule, not asserted | Asserting TTL first and claiming it "covers all scenarios" inverts the logic |
| Priority queue routing for P0, not consistent hashing | Consistent hashing is incompatible with drain-on-failure failover without rehashing; priority queue routing eliminates the contradiction |
| Receipt writes decoupled from delivery path via Kafka | PostgreSQL write latency must not bound delivery throughput |
| Idempotency keys in Redis, not APNs/FCM deduplication | Neither platform provides general-purpose deduplication; idempotency must be owned by the application |
| SMS spend cap via Redis atomic counter in isolated instance + Twilio hard cap | Defense in depth; Redis counter fails open to the Twilio cap, not to unbounded spend |
| Non-AWS tertiary alerting path | An AWS-dependent backup for AWS failures is structurally circular |

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
| Viral event inbound (derived ceiling) | ~1,100/sec | Derived in Section 1.2; inputs explicitly labeled as estimates | Validate against viral event logs at launch |
| Viral event inbound (2× stress case) | ~2,200/sec | Derived from input uncertainty bounds in Section 1.2 | — |
| Viral event inbound (3× stress case) | ~3,300/sec | Modeled for queue depth planning | — |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 1 pre-launch |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and connection count | Load test in month 1 pre-launch |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

**The iOS/Android split matters for the delivery model.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. Section 1.4 specifies what changes if the actual split is 40/60, including which connection pools require rebalancing.

**The 17 notifications/DAU/day figure drives the entire sizing model.** If this figure is wrong by more than 2×, the instance sizes, worker counts, and Redis capacity in this document require revision before launch. Section 1.4 specifies what changes at 8/day and 35/day and defines a hard re-sizing trigger.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Inputs Explicitly Labeled as Estimates

**The honest framing:** The viral inbound model is built from three inputs that cannot be validated before launch. Multiplying estimates together produces an estimate, not a derivation. The value of showing the arithmetic is not that it makes the result more reliable — it is that it makes the inputs challengeable and the consequences of being wrong calculable.

**Inputs and their uncertainty:**

| Input | Point estimate | Plausible range | Basis |
|-------|---------------|-----------------|-------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | 2–10% of DAU (60K–300K) | No historical data; social platform benchmarks vary widely |
| Baseline notifications/sec per user in cohort | 34/day = 0.000394/sec | Depends on actual heavy-user distribution | Assumed 2× average; validate against user distribution in month 1 |
| Viral spike multiplier | 8× personal baseline | 4–20× depending on content type and network structure | Sustained 15-minute spike; no pre-launch data |

**Derivation:**

```
Viral cohort inbound   = 150,000 × 0.000394/sec × 8 = ~473/sec
Remaining DAU inbound  = 2,850,000 × 17/day / 86,400 = ~580/sec
Total inbound ceiling  = ~1,053/sec → rounded to ~1,100/sec

With 20% infrastructure margin: ~1,320/sec as queue-sizing ceiling
```

**What this means operationally:** The derived ceiling (~1,100/sec) is below the expected delivery throughput (~1,400/sec). The system absorbs a modeled viral event in steady state without queue growth. Queue growth only occurs if actual inbound exceeds the delivery floor (~1,200/sec). P0 is on separate infrastructure and is not subject to viral event load.

---

#### Stress Case Multipliers — Derived from Input Error Bounds

A stress case multiplier without justification is arbitrary. The multipliers below are derived by asking: how wrong could the inputs simultaneously be?

**2× case:** If cohort size and spike multiplier are both 100% higher than estimated (cohort = 300,000, multiplier = 16×):
```
300,000 × 0.000394 × 16 = ~1,891/sec viral cohort
1,891 + 580 = ~2,471/sec → approximately 2.2× the derived ceiling
```
Both inputs being simultaneously wrong by 100% is plausible for a first viral event on a new platform with no historical data. **The 2× case is the base stress case.**

**3× case:** Both inputs wrong by ~150% simultaneously (cohort = 375,000, multiplier = 20×). This represents a scenario where the product goes genuinely viral beyond pre-launch estimates. Historical examples exist for new social platforms. We model it to understand the failure mode; we do not pre-provision for it.

**5× and above:** Would require 400,000+ users each generating 32× their baseline simultaneously. At that point, the correct response is emergency scaling and incident protocol, not pre-provisioned capacity. We define the operational response in Section 5.

---

#### Stress Case Queue Arithmetic — Shown End-to-End

**cache.r6g.large capacity derivation:**

A cache.r6g.large provides 13.07 GB of memory. Per queued notification message: notification_id (16 bytes UUID), user_id (8 bytes), channel (1 byte), priority (1 byte), payload (average 512 bytes), retry_count (1 byte), created_at (8 bytes), expires_at (8 bytes) = 555 bytes raw. With Redis overhead (hash table entries, per-key overhead, list node pointers): approximately **800 bytes per queued message** at the 95th percentile.

Non-queue Redis usage:
- User preference cache: 3,000,000 DAU × 200 bytes = 600 MB
- Idempotency keys at 50M/day with 8-hour TTL: ~24M keys × 25 bytes = 600 MB
- Total non-queue usage: **~1.2 GB**

Available for queue storage: 13.07 GB − 1.2 GB = **~11.87 GB**

At 800 bytes/message: **11.87 GB / 800 bytes ≈ 15.6 million messages maximum queue depth**

**Runway calculations:**

| Scenario | Inbound | Delivery floor | Queue growth rate | Messages to fill Redis | Runway |
|----------|---------|---------------|-------------------|----------------------|--------|
| Derived ceiling (~1,100/sec) | 1,100/sec | 1,200/sec | 0 (net drain) | N/A | Infinite |
| 2× stress (~2,200/sec) | 2,200/sec | 1,200/sec | 1,000/sec | 15.6M | **4.3 hours** |
| 3× stress (~3,300/sec) | 3,300/sec | 1,200/sec | 2,100/sec | 15.6M | **2.1 hours** |
| 5× stress (~5,500/sec) | 5,500/sec | 1,200/sec | 4,300/sec | 15.6M | **1.0 hour** |

**At 3× inbound, the on-call team has approximately 2.1 hours from queue growth onset before Redis fills.** P2 shedding begins at 30 minutes per the response table below, reducing queue growth from 2,100/sec to approximately 1,400/sec and extending runway to ~3.1 hours — sufficient time to scale horizontally.

**Response thresholds:**

| Scenario | Queue growth rate | Alert at | Required action | Time to Redis full from alert |
|----------|-----------------|----------|-----------------|-------------------------------|
| 2× stress | 1,000/sec | 15 minutes | Page on-call; evaluate horizontal scaling | ~4 hours |
| 3× stress | 2,100/sec | 15 minutes | P2 shedding enabled at 30 minutes | ~1.5 hours after shedding begins |
| 5× stress | 4,300/sec | Immediate | Emergency scaling + incident protocol | ~45 minutes |

---

#### P0 Failover Routing — Priority Queue, Not Consistent Hashing

**The problem with consistent hashing for P0:** Consistent hashing on `notification_id % 2` assigns notifications deterministically to APNs connections. A drain-on-failure model must move all traffic from APNs-1 to APNs-2 when APNs-1 fails. These mechanisms are incompatible without rehashing, because:

- In-flight notifications assigned to APNs-1 by hash that are mid-retry will be requeued to APNs-2, creating potential duplicates.
- The idempotency key prevents duplicates only if the key has not expired and if the key correctly distinguishes "attempted and delivered" from "attempted and failed."
- Under connection failure, retry timing is non-deterministic, making idempotency key state unreliable as the sole safeguard.

**Resolution: Priority queue routing.**

Consistent hashing is appropriate for distributing load across stateless workers. It is not appropriate for routing to a stateful resource (a persistent APNs connection) where failover must be clean.

```
P0 Push Architecture:
  APNs-1 (primary):   Worker-1A (active), Worker-1B (hot standby)
  APNs-2 (secondary): Worker-2A (active), Worker-2B (hot standby)

  Routing: Workers consume from a single P0 push queue.
           Workers 1A/1B hold APNs-1; Workers 2A/2B hold APNs-2.
           Each worker fetches from the queue independently.
           Load distributes naturally by fetch rate.

  Failover trigger: APNs-1 write errors exceed 3 in 10 seconds.

  Failover sequence:
    1. Workers 1A/1B stop fetching from the P0 queue.
    2. Workers 2A/2B increase fetch rate to compensate.
    3. In-flight notifications on APNs-1 that have not received
       an APNs receipt are requeued to the P0 queue with their
       original notification_id preserved.
    4. Workers 2A/2B fetch and attempt delivery.
    5. Idempotency key on notification_id prevents duplicate
       delivery if APNs-1 had already delivered before the error.
    6. Pager fires immediately.

  Idempotency key semantics: The key is written in two stages.
    - Stage 1 ("attempted"): Written when a worker fetches and
      begins delivery. Prevents a second worker from attempting
      the same notification concurrently.
    - Stage 2 ("delivered"): Written when APNs receipt confirms
      delivery. Only at this point is the notification considered
      complete.
    If APNs-1 fails after Stage 1 but before Stage 2, the key
    is in "attempted" state. The requeue logic checks for this
    state and allows a retry on APNs-2, writing Stage 2 on
    confirmed delivery. This prevents both duplicate delivery
    and missed delivery.
```

**Failure mode table:**

| Failure | Detection | Response | P0 impact |
|---------|-----------|----------|-----------|
| Worker-1A crashes | Heartbeat miss within 5 seconds | Worker-1B promotes; pager fires | Zero: Worker-1B holds APNs-1 |
| APNs-1 connection drops | Write error on Worker-1A | Worker-1A reconnects (<2 seconds HTTP/2); Worker-1B takes load | <2 seconds degradation |
| APNs-1 endpoint unavailable (>10 seconds) | 3 errors in 10 seconds | Workers drain to APNs-2; requeue in-flight; pager fires | <5 seconds latency spike |
| Both APNs connections fail | All P0 writes fail | Incident protocol; FCM fallback where token exists; SMS fallback for security alerts | Degraded; see Section 5 |

**Cost of a second P0 APNs connection:** Each APNs HTTP/2 connection is a persistent TCP connection. The marginal cost is negligible. The benefit is that connection-level failures — TLS session limits, server-side resets, endpoint unavailability — do not block P0 delivery entirely.

---

#### APNs Rate Limit Validation — Pre-Launch

The 800/sec/connection figure is a conservative operational floor derived from Apple's HTTP/2 connection behavior. Apple does not publish a contractual per-connection rate limit. This figure **must be validated during month 1 load testing**, before launch, not after. If the actual sustained limit is lower than 800/sec, additional connections must be provisioned before launch. Contingency connections (APNs-6, APNs-7) are pre-provisioned in the load testing environment to allow rapid promotion without a configuration change under pressure.

---

#### Worker Pool — Sized to APNs Connections

**The core error to avoid:** Allocating workers independently of the connections they use. One worker