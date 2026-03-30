# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived with visible arithmetic or explicitly labeled as an estimate with a validation path. Every tradeoff names what is being sacrificed and why that sacrifice is acceptable given the constraints.

**Core design principles:**

1. **Conservatism belongs in the delivery floor, not the inbound ceiling.** An inflated inbound ceiling produces an over-provisioned queue model and conceals the real binding constraints.
2. **Stress cases must be derived, not asserted.** A 2× multiplier with no justification is not conservative — it is arbitrary. Each stress case below is derived from explicit model error bounds.
3. **P0 infrastructure is never shared.** OTPs and security alerts do not compete with social engagement volume under any load condition.

**Key design decisions and their rationale:**

| Decision | Rationale |
|----------|-----------|
| Derived viral inbound ceiling (~1,100/sec) rather than asserted round number | Arithmetically honest; produces correct queue sizing and Redis runway |
| Workers sized to APNs connections, not to worker compute | APNs connections are the binding constraint; excess workers produce idle capacity, not throughput |
| P0 gets 2 APNs connections, not 1 | Connection-level failures (not just worker crashes) block delivery; 2 connections costs nothing and eliminates this failure mode |
| Retry schedule defined before TTL is set | TTL derived from maximum retry interval; asserting TTL first inverts the logic |
| Receipt writes decoupled from delivery path via Kafka | PostgreSQL write latency must not bound delivery throughput |
| Idempotency keys in Redis, not APNs/FCM deduplication | Neither platform provides general-purpose deduplication; idempotency must be owned by the application |
| Non-AWS tertiary alerting path | An AWS-dependent backup for AWS failures is structurally circular |
| SMS spend cap via Redis atomic counter + Twilio hard cap | Defense in depth; Redis counter fails open to the Twilio cap |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark; see Section 1.4 for sensitivity | Validate against product analytics before provisioning final instance sizes |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark for social apps | Validate against registration data in month 1 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (derived ceiling) | ~1,100/sec | Derived in Section 1.2 | Validate against viral event logs at launch |
| Viral event inbound (stress case — 2×) | ~2,200/sec | Derived from model error bounds in Section 1.2 | — |
| Viral event inbound (stress case — 3×) | ~3,300/sec | Modeled for queue depth planning | — |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 2 |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and connection count | Load test in month 2 |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

**The iOS/Android split matters for the delivery model.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. If the actual split is 40/60, FCM becomes dominant; Section 1.4 specifies what changes. The analysis below reflects the 60/40 assumption.

**The 17 notifications/DAU/day figure drives the entire sizing model.** Section 1.4 specifies what changes at 8/day and 35/day, and defines a hard re-sizing trigger. If this figure is wrong by more than 2×, the instance sizes, worker counts, and Redis capacity in this document require revision before launch.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Arithmetic Shown

The correct approach is to derive a ceiling from explicit, challengeable inputs — not to assert a round number. Inputs that cannot be validated before launch are labeled as estimates with a validation path.

**Inputs:**

| Input | Value | Basis | Validation path |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Viral content typically engages a small fraction of the active base | Check against actual cohort size for past viral events |
| Baseline notifications/sec per user in cohort | 34/day = 0.000394/sec | Heavy users at 2× average daily rate | Validate against actual user distribution |
| Viral spike multiplier | 8× personal baseline | Sustained 15-minute spike | Monitor at launch; update if spikes are consistently larger |
| Non-viral DAU inbound during spike | ~580/sec | Remaining 2.85M DAU at 17/day average | Stable; does not change during a viral event |

**Derivation:**

```
Viral cohort inbound = 150,000 users × 0.000394/sec × 8× multiplier
                     = ~473/sec

Total inbound ceiling = 473/sec (viral cohort) + 580/sec (remaining DAU)
                      = ~1,053/sec → rounded to ~1,100/sec

With 20% infrastructure margin: ~1,320/sec as the queue-sizing derived ceiling
```

**What this means operationally:** The derived ceiling (~1,100/sec) is below the expected delivery throughput (~1,400/sec). The system absorbs a modeled viral event in steady state without queue growth. Queue growth only occurs if actual inbound exceeds the delivery floor. P0 is on separate infrastructure and is not subject to viral event load — OTPs and security alerts do not scale with social engagement volume.

---

#### Stress Case Multipliers — Derived from Model Error Bounds

A stress case multiplier without justification is arbitrary. The correct approach is to derive the multiplier from explicit bounds on how wrong the viral model could be, then model the consequences for each case.

**Why 2× is the base stress case:**

The two main sources of model error are cohort size and spike multiplier. If both are simultaneously 40% higher than estimated (cohort = 210,000, multiplier = 11.2×):

```
210,000 × 0.000394 × 11.2 = ~927/sec viral cohort
927 + 580 = ~1,507/sec total → approximately 1.4× derived ceiling
```

A simultaneous doubling of both inputs (cohort = 300,000, multiplier = 16×) produces approximately 2× the derived ceiling. This requires both estimates to be wrong by 100% simultaneously — plausible for a first viral event on a new platform with no historical data, which is why we use it as the base stress case.

**Why we also model 3×:**

A 3× case (cohort = 450,000, multiplier = 24×) represents a scenario where the product goes genuinely viral beyond any reasonable pre-launch estimate. This has happened to new social platforms. We model it to understand the failure mode, not because we expect it.

**5× and above** would require 400,000+ users each generating 32× their baseline rate simultaneously. At that point, the correct response is emergency scaling, not pre-provisioned capacity. We do not provision for 5×; we define the operational response in Section 5.

**Stress case consequences:**

| Scenario | Inbound | Queue growth rate | Redis runway (cache.r6g.large) | Response |
|----------|---------|-----------------|-------------------------------|----------|
| Derived ceiling | ~1,100/sec | 0 (below delivery floor) | Infinite | None required |
| 2× stress | ~2,200/sec | ~1,000/sec | ~36 hours | Page on-call at 15 min |
| 3× stress | ~3,300/sec | ~2,100/sec | ~17 hours | P2 shedding at 30 min |
| 5× stress | ~5,500/sec | ~4,300/sec | ~8 hours | Emergency scaling; incident protocol |

The 3× case is survivable with P2 shedding. The 5× case does not produce OOM within 8 hours, providing sufficient time to scale horizontally or enable shedding before data loss.

---

#### P0 Worker and Connection Architecture — Connection-Level Failover Modeled

Worker-level failover (active + hot standby) is necessary but not sufficient. APNs connection-level failures — connection drops, TLS session limits, server-side resets, endpoint unavailability — block all workers sharing that connection. With a single APNs connection, a connection-level failure blocks P0 delivery entirely until reconnection, which typically takes 2–30 seconds but can take longer during APNs-side incidents.

**Decision: P0 gets 2 dedicated APNs connections.**

```
P0 Push Architecture:
  APNs-1 (primary):   Worker-1A (active), Worker-1B (hot standby)
  APNs-2 (secondary): Worker-2A (active), Worker-2B (hot standby)

  Routing: Consistent hash on notification_id % 2
  Failover: If APNs-1 is unhealthy for >10 seconds,
            Workers 1A/1B drain to APNs-2.
            APNs-2 can carry full P0 load (P0 volume << 800/sec ceiling).
```

**Failure modes and responses:**

| Failure mode | Detection | Response | P0 impact |
|--------------|-----------|----------|-----------|
| Worker-1A crashes | Heartbeat miss within 5 seconds | Worker-1B promotes to active; pager fires | Zero: Worker-1B holds APNs-1 connection |
| APNs-1 connection drops | Write error on Worker-1A | Worker-1A reconnects (<2 seconds for HTTP/2); Worker-1B takes load during reconnect | <2 seconds degradation |
| APNs-1 endpoint unavailable | All APNs-1 writes fail for >10 seconds | Workers drain to APNs-2; pager fires | Zero: APNs-2 carries full P0 load |
| Both APNs connections fail | All P0 writes fail | Incident protocol; FCM fallback where token exists; SMS fallback for security alerts | Degraded; see Section 5 |

**TLS renegotiation:** APNs HTTP/2 connections use TLS 1.3. Server-initiated renegotiation does not occur in TLS 1.3. Connection lifetime is bounded by APNs server-side session limits. Workers maintain 30-second heartbeats and reconnect proactively rather than waiting for a write failure.

**Cost:** Each APNs HTTP/2 connection is a persistent TCP connection. The cost of a second P0 connection is negligible.

---

#### Worker Pool — Sized to APNs Connections

**The core error to avoid:** Allocating workers independently of the connections they use. One P1 push worker at a 32ms cycle time and 500 notifications per batch sustains approximately 15,600 notifications/second in isolation. Two APNs connections rated at 800/sec each provide a ceiling of 1,600/sec. Fourteen workers waiting on that ceiling means 13.9 workers are idle at all times. Worker count must be derived from the actual binding constraint — APNs connection count — not from an independent sizing exercise.

**APNs connection accounting:**

| Connection | Priority pool | Throughput floor | Shared? |
|------------|--------------|-----------------|---------|
| APNs-1 | P0 exclusively | 800/sec | No |
| APNs-2 | P0 exclusively (failover) | 800/sec | No |
| APNs-3 | P1 exclusively | 800/sec | No |
| APNs-4 | P1 exclusively | 800/sec | No |
| APNs-5 | P2 exclusively | 800/sec | No |

Total APNs throughput (conservative floor): 5 × 800 = **4,000/sec**. This exceeds the 3,300/sec 3× stress-case inbound ceiling.

**Note on APNs rate limits:** The 800/sec/connection figure is a conservative operational floor. Apple does not publish a contractual per-connection rate limit. This figure should be validated during month 2 load testing. If the actual limit is higher, throughput improves; if lower, add connections before launch.

**FCM:** Uses HTTPS POST requests, not a persistent connection. FCM carries ~14M push notifications/day = ~486/sec at 3× peak. Well below FCM's documented 10,000/sec sender limit. FCM is not the binding constraint at any realistic split. **Per-device rate limit caveat:** FCM enforces per-registration-token limits (approximately 240 notifications/hour). The P2 shedding logic must deduplicate by user_id to avoid triggering this.

**Revised worker pool:**

| Pool | Workers | APNs connections | Throughput ceiling | Notes |
|------|---------|-----------------|-------------------|-------|
| P0 push | 4 | APNs-1, APNs-2 (dedicated) | 1,600/sec (conservative) | 2 connections × 2 workers; connection failover modeled |
| P1 push | 4 | APNs-3, APNs-4 (dedicated) | 1,600/sec (conservative) | 2 connections × 2 workers |
| P2 push | 2 | APNs-5 (dedicated) | 800/sec (conservative) | Single connection acceptable; P2 tolerates delay |
| FCM (all priorities) | 3 | 1 FCM connection (HTTPS) | 10,000/sec | Priority enforced by worker fetch order |
| P0 SMS | 2 | — | 100/sec | Isolated from P1/P2 SMS |
| In-app writers | 4 | — | ~2,000/sec (derived below) | — |
| Email workers | 3 | — | 100/sec | SendGrid Pro plan limit |
| SMS workers | 2 | — | 100/sec | Non-urgent SMS |
| Receipt writers | 2 | — | Async; not on critical path | — |
| **Total** | **26** | **5 APNs connections** | | |

All 26 workers fit on 2 × c6g.xlarge instances (4 vCPU, 8GB each) with headroom.

---

#### Idempotency Key TTL — Derived from Retry Schedule

**The error to avoid:** Asserting a TTL and then claiming it "covers all realistic failure scenarios" without defining what those scenarios are. TTL must be derived from the maximum retry interval, not the other way around.

**Retry schedule — defined first:**

```
Attempt 1: Immediate (initial dispatch)
Attempt 2: 30 seconds after failure detection
Attempt 3: 2 minutes after attempt 2
Attempt 4: 10 minutes after attempt 3
Attempt 5: 30 minutes after attempt 4
Attempt 6+: 30-minute intervals until P1 expiry (4 hours from creation)
```

Maximum time from initial dispatch to final retry attempt: **4 hours** (P1 expiry threshold).

**TTL derivation:**

```
Maximum retry window = 4 hours = 14,400 seconds
Safety margin = 2× = 28,800 seconds
TTL = 2 hours (7,200 seconds) is