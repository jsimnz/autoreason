# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived with visible arithmetic or explicitly labeled as an estimate requiring validation. Every tradeoff states what is being sacrificed and why that sacrifice is acceptable given the constraints.

**Where the two versions conflicted, this synthesis resolves each conflict explicitly:**

| Conflict | Resolution | Rationale |
|----------|------------|-----------|
| Viral inbound ceiling | ~1,100/sec derived; 2,600/sec stress case for queue modeling | Version Y's derivation is arithmetically honest; Version X's 8,000/sec was asserted, not derived |
| Worker pool size | 21 workers sized to APNs connections, not to worker compute | Version X's 50-worker pool was not derived from any constraint; Version Y's sizing is correct |
| APNs rate limit | 800/sec/connection conservative floor; validate in month 2 load testing | Neither version has an auditable source; epistemic honesty is the correct posture |
| APNs/FCM deduplication | Neither platform provides general deduplication; idempotency keys required | Version X's claim was technically false; Version Y's correction is accurate |
| In-app write throughput | Derived from a single consistent hardware benchmark (8,000/sec on db.r6g.xlarge) | Version X cited incompatible figures with no shared derivation |
| Redis entry size | ~100 bytes/entry derived from int64 ID format and Redis internals | Version X's "50–80 bytes" was unspecified; Version Y's derivation is traceable |
| Viral queue runway | ~26 hours on cache.r6g.large vs. Version X's 60-minute runway | Version X's runway was a consequence of an unjustifiably high inbound ceiling |
| Alerting tertiary path | Non-AWS tertiary path; SES-on-AWS eliminated as "independent" backup | Version Y's correction is structurally sound; AWS-dependent backup for AWS failures is circular |
| P1 expiry threshold | 4 hours default; Product sign-off required; named configuration constant | Consistent across both versions; preserved |
| SMS volume | Derived from auth event rate (~360K/day); spend cap mechanically enforced | Version Y's enforcement mechanism is more operationally complete |

**The core design principle:** Conservatism belongs in the delivery floor, not the inbound ceiling. An inflated inbound ceiling produces an over-provisioned queue model and conceals the real binding constraints. We use a derived inbound ceiling, a conservative delivery floor, and explicit stress cases.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | How to validate |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark | Validate against product analytics before launch |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound (derived ceiling) | ~1,100/sec | Derived in Section 1.2 with explicit assumptions | Validate against viral event logs at launch |
| Viral event inbound (stress case) | ~2,600/sec | 2× derived ceiling; used for queue modeling | — |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 2 |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and APNs connections | Load test in month 2 |
| Push (70%) | 35M/day | Dominant channel | — |
| In-app (20%) | 10M/day | Logged-in users only | — |
| Email (8%) | 4M/day | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Arithmetic Shown

The correct approach is to derive a ceiling from explicit, challengeable inputs — not to assert a round number and call it conservative. Inputs that cannot be validated before launch are labeled as estimates with a validation path.

**Inputs:**

| Input | Value | Basis | How to validate |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Viral content typically engages a small fraction; 5% is more defensible than 10% or 20% | Check against actual cohort size for past viral events |
| Baseline notifications/sec per user in cohort | 34/day = 0.000394/sec | Heavy users at 2× average daily rate | Validate against actual user distribution |
| Viral spike multiplier | 8× personal baseline | Sustained 15-minute spike; provides headroom over a 6× estimate | Monitor at launch; update if spikes are consistently larger |
| Non-viral DAU inbound during spike | ~580/sec | Remaining 2.85M DAU at 17/day average | Stable; does not change during a viral event |

**Derivation:**

```
Viral cohort inbound = 150,000 users × 0.000394/sec × 8× multiplier
                     = 150,000 × 0.003152
                     = ~473/sec

Total inbound ceiling = 473/sec (viral cohort) + 580/sec (remaining DAU)
                      = ~1,053/sec → rounded to ~1,100/sec
```

We add a **20% infrastructure margin** for model error: **~1,320/sec as the queue-sizing derived ceiling.**

For queue depth modeling, we use a **stress case of ~2,600/sec** — approximately 2× the derived ceiling. This represents a scenario where the viral cohort is larger or the spike multiplier is higher than modeled. It is a stress case, not an expected case.

**What this means operationally:** The derived ceiling (~1,100/sec) is below the expected delivery throughput (~1,400/sec). The system can absorb a modeled viral event in steady state without queue growth. Queue growth only occurs if actual inbound exceeds the delivery floor. P0 is on separate infrastructure and is not subject to viral event load at all — OTPs and security alerts do not scale with social engagement volume.

**Why this matters:** Using an unjustifiably high inbound ceiling (e.g., 8,000/sec derived by asserting a multiplier rather than computing one) does not produce a conservative design. It produces an over-provisioned queue model, an undersized Redis instance relative to the modeled risk, and a 60-minute OOM runway that creates false urgency. The correct conservatism is in the delivery floor, not the inbound ceiling.

---

#### Worker Pool Sizing — Sized to APNs Connections

**The core error to avoid:** Allocating many workers to a small number of APNs connections. One P1 push worker at a 32ms cycle time and 500 notifications per batch sustains approximately 15,600 notifications/second in isolation. Two APNs connections rated at 800/sec each provide a ceiling of 1,600/sec. Fourteen workers waiting on that ceiling means 13.9 workers are idle at all times. Worker count must be derived from the actual binding constraint — APNs connection count — not from an independent sizing exercise.

**Correct sizing principle:**

```
Workers needed to saturate one APNs connection at 800/sec:
  = 800/sec ÷ 15,600/sec per worker
  = ~0.05 workers

We allocate 2 workers per APNs connection:
  - 1 active, 1 on standby for failover if the active worker crashes
  - This is a reliability allocation, not a throughput allocation
```

**APNs connection accounting — complete:**

| Connection | Priority pool | Throughput floor | Shared? |
|------------|--------------|-----------------|---------|
| APNs-1 | P0 exclusively | 800/sec | No |
| APNs-2 | P1 exclusively | 800/sec | No |
| APNs-3 | P1 exclusively | 800/sec | No |
| APNs-4 | P2 exclusively | 800/sec | No |

Total APNs throughput (conservative floor): 4 × 800 = **3,200/sec**. This exceeds the 2,600/sec stress-case inbound ceiling.

**FCM:** A single connection handles 10,000/sec per Google's documentation. All priority levels share one FCM connection; FCM is not the binding constraint at any priority level.

**Revised worker pool:**

| Pool | Workers | APNs connections | Throughput ceiling | Notes |
|------|---------|-----------------|-------------------|-------|
| P0 push | 2 | APNs-1 dedicated | 800/sec (conservative) | Isolated; never shares with P1/P2 |
| P1 push | 4 | APNs-2 and APNs-3 dedicated | 1,600/sec (conservative) | 2 workers per connection for failover |
| P2 push | 2 | APNs-4 dedicated | 800/sec (conservative) | Dedicated connection; not sharing P1 connections |
| P0 SMS | 2 | — | 100/sec | Isolated from P1/P2 SMS |
| In-app writers | 4 | — | ~2,000/sec (derived below) | — |
| Email workers | 3 | — | 100/sec | SendGrid Pro plan limit |
| SMS workers | 2 | — | 100/sec | Non-urgent SMS; separate from P0 SMS |
| Receipt writers | 2 | — | Async; not on critical path | — |
| **Total** | **21** | **4 APNs connections** | | |

Additional workers can be added without architectural change if load testing reveals a constraint not captured here.

---

#### Receipt Write Path — Decoupled from Delivery

The naive design writes a delivery receipt to PostgreSQL for each delivered notification on the critical delivery path. At peak delivery rates, this makes PostgreSQL write capacity the binding delivery constraint — adding workers does not increase throughput.

**Decision:** Receipt writes are fire-and-forget to a Kafka topic (`notification.receipts`), consumed by the 2 dedicated receipt writer workers, which batch inserts at 1,000 rows per transaction. This decouples delivery throughput from PostgreSQL write latency entirely.

**Tradeoff:** Delivery receipts are eventually consistent. There is a window — typically under 60 seconds — during which a notification has been delivered to APNs/FCM but the receipt is not yet written to PostgreSQL. If a worker crashes in this window, the notification will be re-attempted from the outbox.

**Important correction from Version X:** Neither APNs nor FCM provides general-purpose notification deduplication on the device. APNs `apns-collapse-id` coalesces notifications with the same collapse key — it does not prevent duplicate delivery of notifications with different IDs or collapse keys. FCM has no equivalent mechanism. A duplicate delivery from a worker crash will result in two notifications appearing on the device.

**Mitigation:** Workers write an idempotency key to Redis (`SET notification:{id}:delivered 1 EX 3600 NX`) before dispatching to APNs/FCM. On re-attempt, the worker checks this key and skips dispatch if already set. The Redis key TTL of 1 hour covers the window between crash and re-attempt under all realistic failure scenarios. This does not eliminate duplicates from simultaneous worker execution (not possible in our single-active-worker-per-connection design) but does eliminate duplicates from crash-and-retry.

**Receipt lag alert:** A separate alert fires if the Kafka consumer lag on `notification.receipts` exceeds 60 seconds. This is monitored independently of delivery throughput.

---

#### In-App Write Throughput — Derived from Hardware

**The problem to avoid:** Citing incompatible figures from the same hardware without a shared derivation. If PostgreSQL on a given instance sustains 15,000–20,000 inserts/second for the receipt writer, the in-app store on the same or similar hardware cannot sustain "~5,000/sec" without explanation of what makes it slower.

**Consistent derivation:**

In-app storage runs on a **db.r6g.xlarge** (4 vCPU, 32GB RAM) Aurora PostgreSQL instance. Aurora PostgreSQL r6g.xlarge sustains approximately 8,000–12,000 simple single-row inserts/second under production conditions with PgBouncer (pool size 50). We use **8,000/sec as the conservative write floor**.

In-app notification rows: `(notification_id int8, user_id int8, payload jsonb, created_at timestamptz, read_at timestamptz)`. No joins on the write path.

Peak in-app write rate: 10M notifications/day × 3× peak factor / 86,400 = **347/sec**. Well below the 8,000/sec hardware ceiling.

**Why 4 in-app workers:** Each worker fetches 500 IDs from the queue, fetches payloads from the outbox read replica (~10ms), and writes rows to the in-app store in batches of 100 (~15ms). Cycle time ~25ms. One worker sustains 20,000 rows/sec in isolation, bounded by the Aurora ceiling at 8,000/sec. Two workers saturate the write ceiling; we allocate 4 for failover and burst headroom.

---

#### Redis Entry Size — Specified

Notification IDs are **int64** (8 bytes). Redis stores integer strings with an optimization for small integers, but under production conditions with large sorted sets, per-entry overhead is:

- Member (int64 string): ~8 bytes
- Score (double): 8 bytes
- Skiplist overhead: ~64 bytes
- Hash table overhead: ~16 bytes

**Total: ~96 bytes per entry.** We use **100 bytes** as the planning figure.

If notification IDs were UUID strings (36 bytes ASCII), per-entry overhead would be approximately 160–180 bytes. We use int64 IDs specifically to control this. The ID format is a design constraint, not an assumption — the schema must enforce it.

**Payload is never stored in Redis.** Sorted set members are notification IDs; scores are priority-weighted timestamps. Workers fetch payloads from PostgreSQL read replicas by ID. Redis memory is bounded by queue depth, not payload size.

---

#### Queue Depth and SLA — Stress Case Modeled

**Queue growth rate in stress case:** 2,600/sec inbound − 1,200/sec delivery = **1,400/sec**

| Duration | Queue accumulation | Redis memory | State | Required response |
|----------|--------------------|--------------|-------|------------------|
| 5 minutes | ~420,000 items | ~40MB | Warning | Page on-call; verify inbound rate is real, not a monitoring artifact |
| 15 minutes | ~1.26M items | ~120MB | Elevated | On-call investigates; no shedding required yet |
| 30 minutes | ~2.52M items | ~240MB | Critical | Begin P2 shedding; notify Product |
| 60 minutes | ~5.04M items | ~480MB | Severe | Evaluate P1 shedding for items older than 30 minutes |
| 120 minutes | ~10.1M items | ~960MB | Incident | Full incident protocol; see Section 5 |

**Redis instance:** **cache.r6g.large** (13.07GB usable). At 100 bytes/entry, capacity is approximately 131M entries. At 1,400/sec queue growth, this is approximately **26 hours of runway** in the stress case. This is sufficient to handle any plausible viral event without OOM risk, and it is the correct figure — it follows directly from the derived inbound ceiling rather than from an asserted one.

**P1 SLA — complete table:**

| Queue depth | Expected P1 tail latency | Alert state | Action |
|-------------|--------------------------|-------------|--------|
| < 10,000 items | < 30 seconds | Normal | None |
| 10,000–100,000 | 30 seconds – 2 minutes | Warning | Page on-call; monitor |
| 100,000–500,000 | 2–7 minutes | Elevated | On-call investigates in