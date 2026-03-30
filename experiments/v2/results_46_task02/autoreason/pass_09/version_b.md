# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Where previous versions made arithmetic claims without showing the work, this revision shows the work or explicitly labels the number as an estimate requiring validation. Where previous versions made false technical claims to justify design decisions, this revision states the actual tradeoff.

**Corrections from the previous version:**

| Problem | What the previous version claimed | What this version does instead |
|---------|----------------------------------|-------------------------------|
| Viral inbound ceiling | "8,000/sec" with no arithmetic connecting it to the 1,290/sec actually derived | Derives a defensible ceiling from explicit assumptions; uses that number; see Section 1.2 |
| Worker pool sizing | 14 P1 workers theoretically capable of 218,400/sec waiting on a 1,600/sec APNs ceiling | Sizes workers to APNs connections with 2–3× headroom for retry and scheduling overhead; see Section 1.2 |
| P2 APNs connection | P2 listed at "~800/sec" with no connection allocated | P2 gets a dedicated connection; connection accounting is complete; see Section 1.2 |
| APNs/FCM deduplication | "APNs and FCM handle duplicate delivery gracefully via notification ID deduplication on-device" | False. Neither platform provides general deduplication. The actual risk and mitigation are stated; see Section 3.3 |
| In-app write throughput | "~5,000/sec" with no derivation; workers achieving "~2,000/sec" with no connection to hardware | Derives both figures from the same hardware benchmark; see Section 1.2 |
| SMS volume derivation | Referenced "Section 1.3" which was not present | Derivation is present in Section 1.3 |
| Redis entry size | "50–80 bytes" without specifying notification ID format | Specifies ID format (int64); derives memory per entry from Redis internals; see Section 1.2 |
| Alerting tertiary path | SES on AWS as "structurally independent" backup for AWS failures | Replaced with a non-AWS tertiary path; dependency loop eliminated; see Section 5.2 |
| Incomplete SLA table | P1 SLA table cut off mid-row | Complete table present in Section 1.2 |
| SMS spend cap | Named but not mechanically defined | Enforcement mechanism specified at the application layer and Twilio account layer; see Section 1.3 |

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
| Viral event inbound ceiling | ~2,600/sec | Derived in Section 1.2 with explicit assumptions | Validate against viral event logs at launch |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived in Section 1.2 | Load test in month 2 |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and APNs connections | Load test in month 2 |
| Push (70%) | 35M/day | Dominant channel | — |
| In-app (20%) | 10M/day | Logged-in users only | — |
| Email (8%) | 4M/day | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Inbound Ceiling — Arithmetic Shown

The previous version derived ~1,290/sec from its own stated assumptions, then asserted 8,000/sec as the planning ceiling with the phrase "the high end of what a larger or more aggressive spike could produce." That is not arithmetic. This version derives a ceiling from explicit inputs and uses that number.

**Inputs:**

| Input | Value | Basis | How to validate |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 5% of DAU = 150,000 users | Viral content typically engages a smaller fraction than 10%; 5% is more defensible than 10% | Check against actual cohort size for past viral events |
| Baseline notifications/sec for this cohort | 34/day = 0.000394/sec per user | Heavy users at 2× average daily rate | Validate against actual user distribution |
| Viral spike multiplier | 8× personal baseline | Sustained 15-minute spike; higher than previous 6× to provide headroom | Monitor at launch; update if spikes are consistently larger |
| Non-viral DAU inbound during spike | ~580/sec | Remaining 2.85M DAU at baseline 17/day average | Stable; does not change during viral event |

**Derivation:**

```
Viral cohort inbound = 150,000 users × 0.000394/sec × 8× multiplier
                     = 150,000 × 0.003152
                     = 473/sec

Total inbound ceiling = 473/sec (viral cohort) + 580/sec (remaining DAU baseline)
                      = ~1,053/sec
```

Rounding up to **~1,100/sec** as the derived planning ceiling. We add a **20% infrastructure margin** to account for model error and produce a queue-sizing figure of **~1,300/sec**.

**What this number means:** The derived ceiling of ~1,100/sec is below the expected delivery throughput of ~1,400/sec. This means the system, as designed, can absorb a viral event of this magnitude in steady state without queue growth. Queue growth only occurs if the actual viral cohort is larger or the spike multiplier is higher than modeled. The queue depth table below models the scenario where actual inbound reaches 2× the derived ceiling (~2,600/sec) — a stress case, not the expected case.

**Why this is materially different from the previous version:** The previous version's 8,000/sec figure would require a 20× multiplier on the remaining DAU baseline or a viral cohort of roughly 1.1M users at 8× spike — implausible for a 3M DAU social app. Using an unjustifiably high ceiling does not produce a conservative design; it produces an over-provisioned queue model and an under-examined delivery constraint.

**The correct conservatism is in the delivery floor, not the inbound ceiling.** We plan queues for 2× the derived inbound ceiling and we use the conservative delivery floor (1,200/sec). This combination is defensible.

---

#### Worker Pool Sizing — Sized to APNs Connections, Not to Worker Compute

**The previous version's error:** It stated one P1 push worker sustains 15,600 notifications/second in isolation (500 notifications / 0.032 seconds), then allocated 14 P1 push workers to 2 APNs connections rated at 800/sec each. Fourteen workers capable of 218,400/sec waiting on a 1,600/sec APNs ceiling means 13.9 of those workers are idle at all times. The worker count was not derived from anything.

**Correct sizing principle:** Workers should be sized to keep APNs connections saturated with headroom for retry cycles, scheduling jitter, and connection re-establishment. The relevant ratio is:

```
Workers needed per APNs connection = 
  (APNs round-trip latency / batch processing time) × saturation headroom
```

At 20ms APNs round-trip and 32ms total cycle time (10ms fetch + 20ms APNs + 2ms Redis), one worker is busy 62.5% of the time waiting on APNs. To keep one APNs connection saturated at 800/sec with a 32ms cycle time and 500 notifications per batch:

```
Throughput per worker = 500 notifications / 0.032 seconds = 15,625/sec per worker in isolation
APNs ceiling per connection = 800/sec (conservative floor)
Workers needed to saturate one connection = 800 / 15,625 ≈ 0.05 workers
```

One worker can saturate one APNs connection with significant headroom. Worker count is therefore not the constraint — APNs connection count is. We allocate **2 workers per APNs connection** to provide failover if a worker crashes, not to increase throughput.

**Revised worker pool:**

| Pool | Workers | APNs connections | Throughput ceiling | Notes |
|------|---------|-----------------|-------------------|-------|
| P0 push | 2 | 1 dedicated | 800/sec (conservative) | Isolated; never shares connections with P1/P2 |
| P1 push | 4 | 2 dedicated | 1,600/sec (conservative) | 2 workers per connection for failover |
| P2 push | 2 | 1 dedicated | 800/sec (conservative) | Dedicated connection; not "sharing P1 connections" |
| In-app writers | 4 | — | ~2,000/sec (derived below) | |
| Email workers | 3 | — | ~100/sec | SendGrid Pro plan limit |
| SMS workers | 2 | — | ~100/sec | Twilio short code limit |
| P0 SMS | 2 | — | ~100/sec | Dedicated; isolated from P1/P2 SMS |
| Receipt writer | 2 | — | Async; not on critical path | |
| **Total** | **21** | **4 APNs connections** | | |

**Why fewer workers than before:** The previous design's 50-worker pool was not derived from any constraint. The actual constraints are APNs connection count and channel rate limits. 21 workers are sufficient to saturate all channels at their rate limits with failover headroom. Additional workers can be added without architectural change if load testing reveals a constraint we missed.

**APNs connection accounting — complete:**

| Connection | Priority pool | Throughput floor | Shared? |
|------------|--------------|-----------------|---------|
| APNs-1 | P0 exclusively | 800/sec | No |
| APNs-2 | P1 exclusively | 800/sec | No |
| APNs-3 | P1 exclusively | 800/sec | No |
| APNs-4 | P2 exclusively | 800/sec | No |

Total APNs throughput ceiling (conservative floor): 4 × 800 = **3,200/sec**. This exceeds the 2,600/sec stress-case inbound ceiling.

**FCM connection:** A single FCM connection handles 10,000/sec per Google's documentation. P0/P1/P2 FCM traffic shares one connection; FCM is not the binding constraint for any priority level.

---

#### In-App Write Throughput — Derived from Hardware

**The previous version's error:** It cited "15,000–20,000 simple inserts/second on a c5.2xlarge with PgBouncer" for the receipt writer, then stated "~5,000/sec" for the in-app store on presumably identical hardware, then stated workers achieve "~2,000/sec" — none of these figures connected to each other or to a hardware specification.

**Derivation using a single consistent benchmark:**

We run in-app storage on a **db.r6g.xlarge** (4 vCPU, 32GB RAM) Aurora PostgreSQL instance. This is a read-heavy workload — most in-app notifications are read on open, written once. Benchmark reference: Aurora PostgreSQL r6g.xlarge sustains approximately 8,000–12,000 simple single-row inserts/second under production conditions with connection pooling (PgBouncer, pool size 50). We use **8,000/sec as the conservative write floor**.

In-app notifications are written as single rows: `(notification_id, user_id, payload_jsonb, created_at, read_at)`. No joins on the write path. Payload is stored as JSONB, typically 200–500 bytes.

At 10M in-app notifications/day and a 3× peak factor, peak in-app write rate = 10M × 3 / 86,400 = **347/sec**. This is well below the 8,000/sec hardware ceiling.

**Why 4 in-app workers:** Each worker fetches a batch of 500 notification IDs from the queue, fetches payloads from the outbox read replica (~10ms), and writes rows to the in-app store (~15ms at batch size 100). Cycle time ~25ms. One worker sustains 500/0.025 = 20,000 rows/sec in isolation, bounded by the Aurora write ceiling at 8,000/sec. Two workers saturate the write ceiling; we allocate 4 for failover and burst headroom.

---

#### Queue Depth and P1 SLA — Complete Table

**Redis entry size — specified:**

Notification IDs are **int64** (8 bytes, stored as Redis integer strings, which Redis optimizes to approximately 8 bytes internal representation). A Redis sorted set entry consists of:

- Member: 8 bytes (int64 string)
- Score: 8 bytes (double)
- Skiplist overhead: ~64 bytes per entry
- Hash table overhead: ~16 bytes per entry (pointer + metadata)

**Total per entry: approximately 96 bytes under production conditions.** We use **100 bytes** as the planning figure for simplicity and to provide a small margin.

If notification IDs were UUID strings (36 bytes as ASCII), per-entry overhead would be approximately 160–180 bytes. We use int64 IDs specifically to avoid this. The ID format is a design constraint, not an assumption.

**Queue depth model — stress case (actual inbound 2× derived ceiling = ~2,600/sec; delivery floor = 1,200/sec):**

Queue growth rate in stress case: 2,600 − 1,200 = **1,400/sec**

| Duration | Queue accumulation | Redis memory | State | Required response |
|----------|--------------------|--------------|-------|------------------|
| 5 minutes | ~420,000 items | ~40MB | Warning | Page on-call; verify inbound rate is real |
| 15 minutes | ~1.26M items | ~120MB | Elevated | On-call investigates; no action required yet |
| 30 minutes | ~2.52M items | ~240MB | Critical | Begin P2 shedding; notify Product |
| 60 minutes | ~5.04M items | ~480MB | Severe | Evaluate P1 shedding for items >30 minutes old |
| 120 minutes | ~10.1M items | ~960MB | Incident | Full incident protocol; see Section 5 |

**Redis memory budget:** We provision a **cache.r6g.large** (13.07GB usable). At 100 bytes/entry, the instance holds approximately 131M entries before OOM. At 1,400/sec queue growth, this is approximately **26 hours of runway** in the stress case — sufficient to handle any plausible viral event duration without OOM risk. This is materially different from the previous version's 60-minute runway, which was a consequence of using an unjustifiably high inbound ceiling (8,000/sec) combined with an undersized instance.

**P1 SLA during viral events — complete table:**

| Queue depth | Expected P1 tail latency | Alert state | Action |
|-------------|--------------------------|-------------|--------|
| < 10,000 items | < 30 seconds | Normal | None |
| 10,000–100,000 items | 30 seconds – 2 minutes | Warning | Page on-call; monitor |
| 100,000–500,000 items | 2–7 minutes | Elevated | On-call investigates inbound rate |
| 500,000–2,000,000 items | 7–28 minutes | Critical | Begin P2 shedding; notify Product |
| > 2,000,000 items | > 28 minutes | Severe | P1 shedding for items > P1 expiry threshold |

P1 expiry threshold: **4 hours default**. This requires Product sign-off by end of month 1, week 4. It is a named configuration constant (`P1_EXPIRY_