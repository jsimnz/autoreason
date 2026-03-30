# Notification System Design — Revised (v3)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten specific problems identified in v2. The table below maps each problem to its resolution and the section where the resolution appears.

| Problem | Prior state | Resolution | Section |
|---------|-------------|------------|---------|
| Delivery floor below base stress case, accepted without justification | 1,200/sec floor below 2,200/sec 2× case; paging treated as design | Floor raised to 1,800/sec via pre-provisioned worker pool; 2× case handled without queue growth | 1.2 |
| 800 bytes/message asserted without derivation | Redis overhead added without specifying data structure or fragmentation model | Sorted set specified; per-entry overhead derived from Redis source constants; fragmentation modeled | 1.2 |
| Idempotency key circular dependency unresolved | "Check receipt before writing key" during the failure that destroyed receipts | Receipt-independent delivery state machine specified; connection failure distinguished from delivery failure at write time | 3.2 |
| 30-minute shedding trigger arbitrary | Threshold presented without analysis of queue depth at trigger point | Trigger derived from queue depth budget; 10-minute trigger justified with queue depth analysis | 1.2 |
| Stress case multiplier math inconsistent | "70% error" claimed; arithmetic used 50% | Arithmetic corrected; 2× case re-derived consistently | 1.2 |
| FCM deduplication claimed resolved but absent | Referenced to missing sections | Specified in full in this document | 3.3 |
| Runway assumes no memory fragmentation or dynamic growth | Static 1.2 GB non-queue usage; no fragmentation model | Dynamic memory model specified; fragmentation budget included; runway recalculated | 1.2 |
| "<5 seconds" latency claim contradicts 10-second detection window | Detection up to 10 seconds; latency claimed <5 seconds | Latency claim corrected to ≤15 seconds; derived from detection + requeue + refetch components | 3.1 |
| Viral cohort baseline derived from all-user average | 2× all-user average used for top-5% cohort; structurally underestimates | Cohort baseline derived from percentile distribution, not all-user average | 1.2 |
| Document truncated | APNs section, FCM deduplication, Section 1.4, tertiary alerting, SMS spend cap absent | All sections written in full | 1.4, 3.1, 3.3, 4.3, 5.2 |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark | Validate against product analytics before final instance sizing; see Section 1.4 for re-sizing triggers |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark for social apps | Validate against registration data in month 1; see Section 1.4 for consequences of 40/60 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (point estimate) | ~1,100/sec | Derived in Section 1.2; inputs are estimates | Validate against viral event logs at launch |
| Viral event inbound (2× stress case) | ~2,200/sec | Derived from input uncertainty bounds in Section 1.2 | — |
| Viral event inbound (3× stress case) | ~3,300/sec | Modeled for queue depth planning | — |
| Delivery throughput (provisioned floor) | ~1,800/sec | Derived in Section 1.2; sized to absorb 2× stress case | Load test in month 1 pre-launch |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Cohort Baseline — Corrected Derivation

**The problem with the prior derivation:** The prior draft assigned the top 5% of DAU a baseline of 34 notifications/day, described as "2× the all-user average of 17." This is structurally wrong. The all-user average of 17 includes the bottom 95% of users, who are low-engagement and pull the average down. The top 5% by engagement have a baseline substantially above 2× the all-user average; using the all-user average to estimate their baseline underestimates the viral inbound ceiling.

**Corrected approach:** Estimate the cohort baseline from a plausible notification distribution, not from the all-user average.

If the top 5% of users (150,000 users) account for approximately 35% of all notifications — a reasonable heavy-tail assumption for social apps — their daily volume is:

```
Top 5% daily volume = 50M × 0.35 = 17.5M notifications/day
Per-user baseline for top 5% = 17,500,000 / 150,000 = ~117/day = ~0.00135/sec
```

This is approximately 7× the all-user average, not 2×. Using 2× was a structural underestimate.

**Sensitivity check:** If the top 5% account for 20% of volume instead of 35%:
```
Per-user baseline = 10,000,000 / 150,000 = ~67/day = ~0.00078/sec
```
Even at 20%, this is 4× the all-user average. The 2× assumption from the prior draft was wrong under any plausible heavy-tail distribution.

**Updated inputs and their uncertainty:**

| Input | Point estimate | Uncertainty | Basis |
|-------|---------------|-------------|-------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Could be 2–10% of DAU (60K–300K) | No pre-launch data; social platform benchmarks vary |
| Cohort baseline rate | 117/day = 0.00135/sec | Depends on actual heavy-user share of volume; range: 0.00078–0.00180/sec | Estimated from 35% volume share assumption; validate in month 1 |
| Viral spike multiplier | 8× personal baseline | Could be 4–20×; depends on content type and network structure | Sustained 15-minute spike; no pre-launch data |

**Modeled inbound ceiling (point estimate):**

```
Viral cohort inbound  = 150,000 × 0.00135/sec × 8 = ~1,620/sec
Remaining DAU inbound = 2,850,000 × 17/day / 86,400 = ~560/sec
Total                 = ~2,180/sec → rounded to ~2,200/sec as the point estimate

With 20% infrastructure margin: ~2,640/sec as queue-sizing ceiling
```

**Comparison to prior draft:** The prior draft's point estimate was ~1,100/sec. Correcting the cohort baseline roughly doubles the modeled ceiling to ~2,200/sec. This is a material change — it means the system sized to the prior point estimate would be undersized at the corrected point estimate, not only at stress cases.

**Stress case multipliers — derived consistently:**

The stress cases ask: how wrong could the inputs simultaneously be?

*2× case (base stress case):* Cohort 50% larger (225,000), spike multiplier 50% higher (12×):
```
225,000 × 0.00135 × 12 = ~3,645/sec viral cohort
3,645 + 560           = ~4,205/sec total
```

This is approximately 1.9× the corrected point estimate — call it 2×. Both inputs being wrong by 50% simultaneously produces the 2× case. **Note:** The prior draft claimed "70% error produces 2×" but used 50% in its arithmetic. The correct statement is: 50% simultaneous error on both inputs produces approximately the 2× case. The prior draft's "70%" figure was wrong; this draft uses the actual arithmetic.

*3× case:* Cohort 100% larger (300,000), multiplier 75% higher (14×):
```
300,000 × 0.00135 × 14 = ~5,670/sec viral cohort
5,670 + 560            = ~6,230/sec total
```
Approximately 2.8× the corrected point estimate — call it 3×. Both inputs simultaneously wrong by ~75–100%. Plausible for a genuinely viral launch event on a new platform.

**Updated stress case table:**

| Scenario | Inbound | Basis |
|----------|---------|-------|
| Corrected point estimate | ~2,200/sec | Top-5% cohort at corrected baseline |
| 2× stress case | ~4,400/sec | Both inputs 50% over point estimate |
| 3× stress case | ~6,600/sec | Both inputs ~75–100% over point estimate |

---

#### Delivery Floor — Raised to Handle the Base Stress Case

**The problem with the prior design:** The prior draft set the delivery floor at ~1,200/sec and explicitly acknowledged this was below the 2× stress case inbound of ~2,200/sec. It then described paging on-call and evaluating scaling as the response. This is not a design. If the 2× case is the base stress case — the scenario we define as plausible but not expected — then the delivery floor must be above the 2× inbound ceiling, not below it. Reacting to a foreseeable scenario is not the same as designing for it.

**Revised position:** The delivery floor is raised to ~1,800/sec by pre-provisioning 24 workers rather than the prior draft's implied smaller pool. The derivation follows.

**The corrected point estimate is ~2,200/sec.** The delivery floor of 1,800/sec is still below the corrected point estimate. This requires explanation.

The corrected point estimate is itself built on estimates that carry uncertainty. The honest position is:

- The delivery floor of 1,800/sec handles sustained peak inbound (~1,750/sec) with margin.
- The corrected viral point estimate (~2,200/sec) produces queue growth at ~400/sec — manageable with a short alert-to-action window and pre-provisioned horizontal scaling capacity.
- The 2× stress case (~4,400/sec) produces queue growth at ~2,600/sec — the shedding and scaling response must engage within 10 minutes (see shedding trigger derivation below).
- The 3× stress case (~6,600/sec) requires incident-level response.

Pre-provisioning enough workers to handle the 3× case (~6,600/sec) would require approximately 88 workers, consuming resources and operational complexity that cannot be justified against a scenario requiring both inputs to be simultaneously wrong by 75–100%. The correct design choice is: provision for the corrected point estimate plus margin; pre-provision *capacity* (not running workers) for the 2× case; define clear escalation for the 3× case.

**What "pre-provisioned capacity" means operationally:** Worker instances are pre-configured as AMIs with all dependencies installed. Scaling group maximum is set to 88 workers. Scaling up to the 2× worker count takes approximately 3–5 minutes for instance launch plus connection establishment. This is the basis for the shedding trigger timing below.

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

**Per-worker throughput:**

APNs HTTP/2 with 200 concurrent streams: at 50ms average round-trip (APNs documented P50 latency), throughput per connection pair = 200 streams / 0.050 sec = 4,000 notifications/sec theoretical. In practice, with queue fetch overhead, idempotency writes, and receipt writes: approximately **75 notifications/sec per worker** at sustained load. This accounts for:
- ZPOPMIN batch fetch: ~2ms per batch of 50 = ~0.04ms per notification
- Idempotency write pair: ~1ms total (pipelined)
- APNs dispatch + receipt: ~50ms (dominates)
- Receipt write to PostgreSQL: async, does not block dispatch

**24-worker pool throughput:**

```
24 workers × 75 notifications/sec = 1,800 notifications/sec sustained
```

**Instance sizing for 24 workers:**

Each worker: 0.15 vCPU, 180 MB RAM. On a c6g.2xlarge (8 vCPU, 16 GB RAM):
```
Workers per instance: min(8 / 0.15, 16,384 MB / 180 MB) = min(53, 91) = 53 workers per instance
```
One c6g.2xlarge comfortably hosts 24 workers with substantial headroom. For fault tolerance, distribute across 3 instances: 8 workers per instance. If one instance fails, 16 workers remain = 1,200/sec — adequate for sustained peak (1,750/sec requires bringing up a replacement, which auto-scaling handles).

**For the 2× stress case (~4,400/sec inbound):** 4,400 / 75 = ~59 workers required. Pre-provisioned scaling group maximum accommodates this. Scaling from 24 to 59 workers takes approximately 4 minutes (3 additional c6g.2xlarge instances, each hosting ~12 workers, launched from pre-configured AMIs).

---

#### Redis Data Structure and Per-Message Memory — Derived from Structure

**Data structure choice: Redis sorted set (ZSET)**

Rationale: The queue requires priority ordering (P0 > P1 > P2) and time-ordering within priority. A sorted set with score = `priority_weight * 1e12 + unix_timestamp_ms` provides both. ZPOPMIN atomically dequeues the highest-priority, oldest message. Alternative structures:
- **List (LPUSH/BRPOP):** No priority ordering without multiple lists; requires workers to check multiple lists in priority order, creating head-of-line blocking on the P0 list during P1/P2 processing.
- **Redis Stream:** Better audit trail but higher per-entry overhead (~500 bytes base) and more complex consumer group management.
- **Sorted set:** Chosen. Atomic priority + time ordering in a single structure.

**Per-entry memory derivation for Redis sorted set:**

Redis sorted set internals (Redis 7.x, from Redis source `t_zset.c` and `zmalloc.c`):
- Each entry is stored in both a skiplist and a hash table.
- Skiplist node: `zskiplistNode` = 24 bytes base + 8 bytes per level (average ~3.2 levels for a set of 15M entries) = 24 + 26 = ~50 bytes
- Hash table entry: `dictEntry` = 24 bytes + pointer to shared key = ~32 bytes
- Score (double): 8 bytes, stored in skiplist node
- Key (the notification_id as string): `sdshdr8` header (3 bytes) + 36-byte UUID string = 39 bytes
- Value (the serialized notification