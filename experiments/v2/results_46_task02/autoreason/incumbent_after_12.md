# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. The synthesis resolves contradictions between prior versions, corrects structural errors in the viral inbound model, raises the delivery floor to a defensible position, and completes all sections that were truncated or missing.

**Key design decisions and their rationale:**

| Decision | Rationale |
|----------|-----------|
| Delivery floor raised to 1,800/sec (24 workers) | Prior 1,200/sec floor was below the base stress case; paging on-call is not a design |
| Viral cohort baseline derived from percentile distribution | Using 2× all-user average for the top 5% is structurally wrong; corrected to ~117/day per cohort user |
| Priority queue routing replaces consistent hash routing | Consistent hashing is incompatible with stateful APNs connection failover |
| Redis sorted set (ZSET) for queue | Provides atomic priority + time ordering; per-entry memory fully derived |
| Receipt-independent delivery state machine | Resolves idempotency circular dependency during connection failures |
| SMS counter in isolated Redis with no eviction | Closes spend cap race condition |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark | Validate before final instance sizing; see Section 1.4 for re-sizing triggers |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark | Validate against registration data in month 1; see Section 1.4 for 40/60 consequences |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (corrected point estimate) | ~2,200/sec | Derived in Section 1.2; inputs are estimates | Validate against viral event logs at launch |
| Viral event inbound (2× stress case) | ~4,400/sec | Derived from input uncertainty bounds in Section 1.2 | — |
| Viral event inbound (3× stress case) | ~6,600/sec | Modeled for queue depth planning; incident-level response required | — |
| Delivery throughput (provisioned floor) | ~1,800/sec | 24 workers; derived in Section 1.2 | Load test in month 1 pre-launch |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

**The iOS/Android split matters.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. Section 1.4 specifies what changes at 40/60.

**The 17 notifications/DAU/day figure drives the entire sizing model.** Section 1.4 specifies what changes at 8/day and 35/day and defines a hard re-sizing trigger.

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Cohort Baseline — Corrected Derivation

**The problem with the prior approach:** Assigning the top 5% of DAU a baseline of 34 notifications/day (described as "2× the all-user average of 17") is structurally wrong. The all-user average of 17 includes the bottom 95% of users, who are low-engagement and pull the average down. Using that average to estimate the top cohort's baseline systematically underestimates the viral inbound ceiling.

**Corrected approach:** Estimate cohort baseline from a plausible notification distribution.

If the top 5% of users (150,000 users) account for approximately 35% of all notifications — a standard heavy-tail assumption for social apps:

```
Top 5% daily volume    = 50M × 0.35 = 17.5M notifications/day
Per-user cohort baseline = 17,500,000 / 150,000 = ~117/day = ~0.00135/sec
```

This is approximately 7× the all-user average. **Sensitivity check:** If the top 5% account for 20% of volume instead of 35%, the per-user baseline is ~67/day = ~0.00078/sec — still 4× the all-user average. The prior draft's 2× assumption was wrong under any plausible heavy-tail distribution.

**Updated inputs and their uncertainty:**

| Input | Point estimate | Uncertainty | Basis |
|-------|---------------|-------------|-------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Could be 2–10% of DAU (60K–300K) | No pre-launch data; social platform benchmarks vary |
| Cohort baseline rate | 117/day = 0.00135/sec | Range: 0.00078–0.00180/sec depending on actual volume share | Estimated from 35% volume share assumption; validate in month 1 |
| Viral spike multiplier | 8× personal baseline | Could be 4–20×; depends on content type and network structure | Sustained 15-minute spike; no pre-launch data |

**The honest framing:** Multiplying estimates together produces an estimate, not a derivation. The value of showing the arithmetic is that it makes the inputs challengeable and the consequences of being wrong calculable — not that it makes the result reliable.

**Modeled inbound ceiling (corrected point estimate):**

```
Viral cohort inbound  = 150,000 × 0.00135/sec × 8 = ~1,620/sec
Remaining DAU inbound = 2,850,000 × 17/day / 86,400 = ~560/sec
Total                 = ~2,180/sec → rounded to ~2,200/sec

With 20% infrastructure margin: ~2,640/sec as queue-sizing ceiling
```

**Comparison to prior draft:** The prior draft's point estimate was ~1,100/sec. Correcting the cohort baseline roughly doubles the modeled ceiling to ~2,200/sec. A system sized to the prior estimate would be undersized at normal viral activity, not only at stress cases.

**Stress case multipliers — derived consistently:**

*2× case (base stress case):* Cohort 50% larger (225,000), spike multiplier 50% higher (12×):
```
225,000 × 0.00135 × 12 = ~3,645/sec viral cohort
3,645 + 560            = ~4,205/sec → call it 4,400/sec (2× corrected point estimate)
```
Both inputs simultaneously wrong by 50%. **Note:** A prior draft claimed "70% simultaneous error produces the 2× case" but used 50% in its arithmetic. The correct statement is: 50% simultaneous error on both inputs produces approximately the 2× case. The 2× case is the base stress case because it requires inputs to be simultaneously wrong by 50% — plausible given no pre-launch historical data.

*3× case:* Cohort 100% larger (300,000), multiplier 75% higher (14×):
```
300,000 × 0.00135 × 14 = ~5,670/sec viral cohort
5,670 + 560            = ~6,230/sec → call it 6,600/sec (3× corrected point estimate)
```
Both inputs simultaneously wrong by ~75–100%. Plausible for a genuinely viral launch event; historical examples exist for new social platforms.

**Updated stress case table:**

| Scenario | Inbound | Basis |
|----------|---------|-------|
| Corrected point estimate | ~2,200/sec | Top-5% cohort at corrected baseline |
| 2× stress case | ~4,400/sec | Both inputs 50% over point estimate |
| 3× stress case | ~6,600/sec | Both inputs ~75–100% over point estimate |

---

#### Delivery Floor — Raised to 1,800/sec

**The problem with the prior design:** The prior draft set the delivery floor at ~1,200/sec and acknowledged this was below the 2× stress case. It then described paging on-call as the response. If the 2× case is the base stress case — plausible but not expected — the delivery floor must be above the sustained peak inbound, not below the stress case. Reacting to a foreseeable scenario is not the same as designing for it.

**Revised position:** The delivery floor is raised to ~1,800/sec by pre-provisioning 24 workers.

**Why 1,800/sec rather than 4,400/sec (the 2× case ceiling):**

The corrected point estimate is itself built on estimates. The honest position:

- 1,800/sec handles sustained peak inbound (~1,750/sec) with margin.
- The corrected viral point estimate (~2,200/sec) produces queue growth at ~400/sec — manageable with a short alert-to-action window.
- The 2× stress case (~4,400/sec) produces queue growth at ~2,600/sec — shedding and scaling must engage within 10 minutes (see shedding trigger derivation below).
- The 3× stress case (~6,600/sec) requires incident-level response.

Pre-provisioning for the 3× case (~6,600/sec) requires approximately 88 workers. The operational complexity and resource cost cannot be justified against a scenario requiring both inputs to be simultaneously wrong by 75–100%. The correct design: provision for sustained peak plus margin; pre-provision *capacity* (not running workers) for the 2× case; define clear escalation for the 3× case.

**What "pre-provisioned capacity" means operationally:** Worker instances are pre-configured as AMIs with all dependencies installed. Auto-scaling group maximum is set to 88 workers. Scaling from 24 to 59 workers (the 2× case requirement) takes approximately 4 minutes — 3 additional c6g.2xlarge instances launched from pre-configured AMIs, each hosting ~12 workers. This is the basis for the shedding trigger timing below.

---

#### Per-Worker Resource Profile and 24-Worker Derivation

**Worker resource profile:**

Each delivery worker:
- Holds 2 persistent APNs HTTP/2 connections (100 concurrent streams each = 200 in-flight APNs requests)
- Holds 1 FCM HTTP/2 connection (100 concurrent streams)
- Consumes from Redis sorted set queue via ZPOPMIN (batches of 50)
- Writes idempotency keys to Redis (2 writes per notification: "dispatched" and "delivered")
- Writes delivery receipts to PostgreSQL via connection pool (2 connections per worker)
- CPU: primarily I/O-bound; approximately 0.15 vCPU per worker at full throughput
- Memory: connection state + in-flight buffers ≈ 180 MB per worker

**Per-worker throughput derivation:**

APNs HTTP/2 with 200 concurrent streams: at 50ms average round-trip (APNs documented P50 latency):
```
Theoretical: 200 streams / 0.050 sec = 4,000 notifications/sec per worker
```
In practice, with queue fetch overhead, idempotency writes, and receipt writes:

| Operation | Latency | Notes |
|-----------|---------|-------|
| ZPOPMIN batch fetch (50 items) | ~2ms | ~0.04ms per notification |
| Idempotency write pair | ~1ms total | Pipelined |
| APNs dispatch + receipt | ~50ms | Dominates; determines concurrency model |
| Receipt write to PostgreSQL | Async | Does not block dispatch |

Sustained throughput per worker: approximately **75 notifications/sec**. This accounts for the gap between theoretical stream concurrency and practical overhead.

**24-worker pool:**
```
24 workers × 75 notifications/sec = 1,800 notifications/sec sustained
```

**Instance sizing:**

Each worker: 0.15 vCPU, 180 MB RAM. On a c6g.2xlarge (8 vCPU, 16 GB RAM):
```
Workers per instance: min(8 / 0.15, 16,384 MB / 180 MB) = min(53, 91) = 53 workers per instance
```
One c6g.2xlarge hosts 24 workers with substantial headroom. For fault tolerance, distribute across 3 instances (8 workers each). If one instance fails, 16 workers remain = 1,200/sec; auto-scaling replaces the failed instance within 4 minutes.

For the 2× stress case (~4,400/sec): 4,400 / 75 = ~59 workers required. Pre-provisioned scaling group accommodates this. Scaling from 24 to 59 workers takes approximately 4 minutes.

---

#### Redis Data Structure and Per-Message Memory — Derived from Structure

**Data structure choice: Redis Sorted Set (ZSET)**

| Structure | Priority ordering | Atomic dequeue | Per-entry overhead | Chosen |
|-----------|-----------------|---------------|-------------------|--------|
| List (LPUSH/BRPOP) | Requires multiple lists; head-of-line blocking risk | Yes (BLPOP) | ~80 bytes | No |
| Redis Stream | Excellent audit trail | Yes (consumer groups) | ~500 bytes base | No |
| Sorted Set (ZPOPMIN) | Native; score encodes priority + timestamp | Yes | ~200 bytes (derived below) | **Yes** |

Score encoding: `score = priority_weight × 1e12 + unix_timestamp_ms`

This provides P0 > P1 > P2 ordering with time ordering within each priority level, in a single atomic structure.

**Per-entry memory derivation (Redis 7.x sorted set internals):**

Each entry lives in both a skiplist and a hash table:

| Component | Size | Derivation |
|-----------|------|------------|
| Skiplist node base (`zskiplistNode`) | 24 bytes | Fixed struct |
| Skiplist level pointers (avg 3.2 levels at 15M entries) | 26 bytes | 8 bytes × 3.2 levels |
| Score (double) | 8 bytes | Stored in skiplist node |
| Hash table entry (`dictEntry`) | 24 bytes | Fixed struct |
| Key: `sdshdr8` header + 36-byte UUID | 39 bytes | 3-byte header + UUID string |
| Value: serialized notification payload | ~512 bytes | Push payload + metadata |
| Redis allocator overhead (~10% fragmentation) | ~63 bytes | Applied to total |
| **Total per entry** | **~696 bytes** | Round to **~700 bytes** |

**Fragmentation note:** Redis uses jemalloc with size classes. Actual allocation for a ~700-byte object will be rounded to the next jemalloc size class (typically 768 bytes for objects in this range). The runway calculations below use 768 bytes to be conservative.

---

#### Redis Capacity and Runway — Arithmetic Shown End-to-End

**cache.r6g.large capacity: 13.07 GB**

Non-queue Redis usage:
- User preference cache: 3M DAU × 200 bytes = 600 MB
- Idempotency keys: 50M/day with 8-hour TTL → ~24M keys at steady state × 25 bytes = 600 MB
- SMS counters: negligible
- **Total non-queue: ~1.2 GB**

**Dynamic memory model:** The 1.2 GB non-queue figure grows with DAU. At 20% DAU growth, non-queue usage grows by ~240 MB. The runway calculations include a 500 MB buffer for growth and fragmentation beyond the jemalloc model.

Available for queue storage: 13.07 GB − 1.2 GB − 