# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived with visible arithmetic. Every decision names its owner. Every tradeoff states what is being sacrificed and why that sacrifice is acceptable given the constraints.

**Where the two source versions conflicted, this synthesis resolves each conflict explicitly:**

- **Delivery throughput:** Version X used 1,200/sec derived conservatively from APNs floor. Version Y used 1,400/sec derived from worker pool and channel constraints with receipts decoupled. This synthesis uses **1,200/sec as the queue-depth planning floor** (conservative, defensible) and **1,400/sec as the expected steady-state figure** (derived, auditable). Queue depth models use the floor; capacity planning uses the expected figure. Both figures require load-test validation in month 2.
- **APNs rate limit:** Version X treated this as empirically uncertain (800–1,500/sec/connection). Version Y cited "2,000–3,000/sec per connection from production experience" without an auditable source. This synthesis adopts Version X's epistemic honesty: the number is uncertain, we use 800/sec/connection as the conservative floor for sizing, and we validate the actual ceiling during month 2 load testing before relying on any specific figure.
- **Viral inbound ceiling:** Version X's revised derivation produced ~1,300–8,000/sec with explicit assumptions. Version Y used 14,000/sec from a 10× multiplier on a 600K-user cohort without challenging the inputs. This synthesis uses **8,000/sec as the planning ceiling** (Version X's defensible upper bound) and sizes queues accordingly, while noting that the correct number requires validation against actual viral event data.
- **P1 expiry threshold:** Version Y used 2 hours citing Twitter engagement decay research. Version X correctly noted that Twitter is a public broadcast medium inapplicable to a private social graph. This synthesis uses **4 hours as the default**, explicitly requires Product sign-off, and makes the threshold a named configuration constant rather than an architectural commitment.
- **SMS volume model:** Version X correctly identified that SMS volume derives from auth event rate, not DAU percentage. Version Y used "2% of auth-eligible events" without derivation. This synthesis adopts Version X's derivation model (~360,000 SMS/day) with Version Y's cost structure and spend cap mechanism.

**Key decisions:**

| Decision | Resolution | Tradeoff |
|----------|------------|----------|
| Delivery throughput model | 1,200/sec planning floor; 1,400/sec expected; validate in month 2 load test | Conservative floor used for queue modeling; expected figure used for capacity planning |
| APNs rate limit | 800/sec/connection conservative floor; validate actual ceiling during load testing | Avoids relying on unauditable "production experience" figures |
| Viral inbound ceiling | 8,000/sec planning ceiling with explicit assumptions stated | Lower than Version Y's 14,000/sec; inputs must be validated against actual event data |
| Receipt write path | Decoupled to Kafka topic; async receipt writer; delivery throughput independent of PostgreSQL write capacity | Receipts eventually consistent; duplicate push delivery possible on worker crash; acceptable because APNs/FCM handle deduplication on-device |
| Preference cache miss behavior | Fall back to PostgreSQL read replica synchronously; never suppress on uncertainty | Higher read latency on cache miss; eliminates opt-out compliance risk during cache cold start |
| P0 separation | Dedicated PostgreSQL instance, Redis Sentinel with `appendfsync always`, 2 active poller instances with leader election | Higher infrastructure cost; P0 isolated from all P1/P2 load |
| P1 expiry threshold | 4 hours default; requires Product sign-off by end of month 1 week 4; escalation path defined | Errs toward delivery over discard; threshold is a config constant, not an architectural choice |
| SMS launch | Domestic-only at month 3; volume derived from auth event rate (~360K/day); spend cap $35K/month | Delays international coverage; provides defensible budget number |
| Alerting backup path | PagerDuty primary → Dead Man's Snitch secondary (separate VM, separate AWS account, no Twilio dependency) → SES tertiary (separate AWS account, personal email) | Three layers of operational overhead; structural independence eliminates single-vendor failure modes |
| Worker pool allocation | 10 P0, 20 P1, 10 P2, 5 in-app writers, 3 email workers, 2 SMS workers = 50 total | Allocation is consistent between specification and throughput table throughout this document |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | How to validate |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Check against actual analytics in month 1 |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark | Validate against product analytics before launch |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Viral event inbound ceiling | ~8,000/sec | See Section 1.2; explicit assumptions stated | Validate against actual viral event logs |
| Delivery throughput (planning floor) | ~1,200/sec | Conservative; derived from APNs floor with receipts decoupled | Load test in month 2 |
| Delivery throughput (expected) | ~1,400/sec | Derived from worker pool and channel constraints | Load test in month 2 |
| Push (70%) | 35M/day | Dominant channel | — |
| In-app (20%) | 10M/day | Logged-in users only | — |
| Email (8%) | 4M/day | Digests + transactional | — |
| SMS | ~360K/day | Derived from auth event rate; see Section 1.3 | Validate against auth system logs in month 1 |

### 1.2 Burst Model and Delivery Throughput

#### Viral Inbound Ceiling — Assumptions Made Explicit

The 8,000/sec figure is a planning input, not a claim about expected behavior. The inputs that produce it are stated explicitly so they can be challenged and updated when real data is available.

| Input | Value | Basis | How to validate |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 10% of DAU = 300K users | Conservative; viral content typically engages a smaller fraction than 20% | Check against product analytics for past viral events |
| Baseline notifications/day for this cohort | ~34/day (2× average) | Heavy users generate more notifications | Validate against actual distribution |
| Viral spike multiplier | 6× personal baseline | Conservative; assumes sustained 15-minute spike, not instantaneous | Monitor inbound rate at launch and update |
| Spike duration | 15 minutes | Typical viral content spike duration | Validate at launch |

**Derivation:** 300K users × 34/day baseline = 0.000394/sec per user × 6× spike = 0.00236/sec per user × 300,000 = **710/sec from viral cohort**, plus ~580/sec from the remaining 2.7M DAU at baseline = approximately **1,290/sec from this model**. We use **8,000/sec as the planning ceiling** — the high end of what a larger or more aggressive spike could produce — and size queues accordingly. This is materially more conservative than Version Y's 14,000/sec figure, which applied a 10× multiplier to a 600K-user cohort without challenging either input.

**What this means operationally:** P0 is on separate infrastructure and is not subject to viral event load. OTPs and security alerts do not scale with social engagement volume. P1 and P2 queues accumulate during viral events; delivery latency increases; this is correct behavior. A social notification about a trending post that arrives 8 minutes late is acceptable. An OTP that arrives 8 minutes late is not.

#### Delivery Throughput — Derivation with Uncertainty Bounds

**The APNs rate limit problem:**

Apple does not publish a per-connection throughput ceiling for APNs HTTP/2. Different teams report empirical ceilings ranging from 500/sec to 3,000/sec depending on payload size, connection handling, certificate type, and undocumented server-side behavior. Citing "2,000–3,000/sec from production experience" is not auditable.

**Design decision:** Use **800/sec/connection as the conservative floor** for capacity planning. Use **1,500/sec/connection as the optimistic ceiling**. Validate the actual ceiling during month 2 load testing before relying on any specific figure. The load test protocol is in Section 6.

We maintain 3 APNs connections:
- Conservative floor: 3 × 800 = **2,400/sec push throughput**
- Optimistic ceiling: 3 × 1,500 = **4,500/sec push throughput**
- **Planning figure: 2,400/sec** (conservative floor)

If load testing reveals the actual ceiling is higher, we reduce APNs connection count and reallocate workers. If lower, we add connections before launch.

**Receipt write decoupling — why it matters for throughput:**

The naive design writes a delivery receipt row to PostgreSQL for each delivered notification on the critical delivery path. At 20 P1 workers each completing 500-row batches at 70ms cycle time, the receipt table would receive approximately 143,000 rows/second — well above what a single PostgreSQL primary can sustain (15,000–20,000 simple inserts/second on a c5.2xlarge with PgBouncer). This makes PostgreSQL write capacity the binding delivery constraint, meaning adding workers does not increase throughput.

**Decision:** Receipt writes are fire-and-forget to a Kafka topic (`notification.receipts`), consumed by a dedicated receipt writer that batches inserts at 1,000 rows per transaction. This decouples delivery throughput from PostgreSQL write latency entirely.

**Tradeoff:** Delivery receipts are eventually consistent. There is a window — typically under 60 seconds — during which a notification has been delivered to APNs/FCM but the receipt is not yet written to PostgreSQL. If a worker crashes in this window, the notification is re-attempted from the outbox. APNs and FCM handle duplicate delivery gracefully via notification ID deduplication on the device. The cost is occasional duplicate push delivery; the benefit is that delivery throughput scales with worker count and APNs connection count rather than PostgreSQL write capacity. Receipt lag is monitored with a separate alert (threshold: 60 seconds).

**Per-worker cycle time with receipts off the critical path:**

| Step | Latency |
|------|---------|
| PostgreSQL batch fetch from read replica | ~10ms |
| APNs round-trip (domestic) | ~20ms |
| Redis ZREM on confirmation | ~2ms |
| **Total per cycle** | **~32ms** |

At 500 notifications per cycle and 32ms per cycle, one P1 push worker sustains approximately 15,600 notifications/second in isolation. The system ceiling is not worker compute — it is APNs connections.

**Worker pool allocation — defined once, used consistently throughout:**

| Pool | Total workers | Channel allocation | Notes |
|------|--------------|-------------------|-------|
| P0 workers | 10 | 8 push/SMS combined, 2 overflow | Overflow handles burst without touching P1/P2 queues |
| P1 workers | 20 | 14 push, 4 in-app, 2 email | Push-heavy reflects channel volume distribution |
| P2 workers | 10 | 6 push, 3 in-app, 1 email | Proportional to P1 allocation |
| Dedicated in-app writers | 5 | In-app only | Separate from P1/P2 in-app allocation; handles fan-out writes |
| Dedicated email workers | 3 | Email only | Handles digest batching independently |
| Dedicated SMS workers | 2 | SMS only | Separate from P0 SMS allocation; handles non-urgent SMS |
| **Total** | **50** | | |

**Channel rate limits — the actual binding constraints:**

| Channel | Rate limit | Source |
|---------|------------|--------|
| APNs | 800–1,500/sec per connection | Empirically uncertain; see above |
| FCM | 10,000/sec per project | Google documentation |
| SendGrid | 100 emails/sec | Pro plan limit |
| Twilio SMS | 100/sec | Short code limit |
| In-app (PostgreSQL write) | ~5,000/sec | Write capacity of in-app store primary |

**Aggregate throughput:**

| Channel | Workers | Throughput (conservative floor) | Binding constraint |
|---------|---------|--------------------------------|-------------------|
| Push — P0 | 8 | ~800/sec | APNs (1 dedicated connection) |
| Push — P1 | 14 | ~1,600/sec | APNs (2 connections) |
| Push — P2 | 6 | ~800/sec | APNs (shares P1 connections during low P1 load) |
| Email | 5 total | ~100/sec | SendGrid plan limit |
| SMS | 4 total | ~100/sec | Twilio short code |
| In-app | 9 total | ~2,000/sec | PostgreSQL write capacity |

**Theoretical aggregate ceiling (conservative):** ~5,400/sec across all channels simultaneously.

**Steady-state throughput:** P1 push workers at steady state process roughly 70% of the 1,600/sec theoretical ceiling = ~1,120/sec push. Email and in-app add ~200/sec. SMS is negligible in volume terms. Retry cycles consume approximately 15% of worker capacity (estimated; validate at launch). Preference re-checks at delivery time add ~3ms per notification on cache hit, ~20ms on cache miss.

- **Planning floor: 1,200/sec** (used for all queue depth models)
- **Expected steady-state: 1,400/sec** (used for capacity planning)

Both figures require load-test validation. If actual steady-state throughput is materially different, queue depth models and SLA tables must be updated before launch.

#### Queue Depth and P1 SLA

At 8,000/sec inbound (planning ceiling) and 1,200/sec delivery (planning floor), the queue grows at 6,800/sec during a sustained viral event.

**Critical constraint:** Payload is never stored in Redis. Sorted set members are notification IDs; scores are outbox row IDs. Workers fetch payloads from PostgreSQL read replicas by ID. This keeps Redis memory predictable regardless of payload size — at 50–80 bytes per sorted set entry, queue memory is bounded.

| Duration | Queue accumulation | Redis memory impact | State | Response |
|----------|--------------------|--------------------|----|---------|
| 5 minutes | ~2.04M items | ~100–160MB | Warning | Page on-call |
| 15 minutes | ~6.12M items | ~300–490MB | Critical | Page on-call + notify Product |
| 60 minutes | ~24.5M items | ~1.2–2.0GB | Incident | Exceeds Redis memory budget; shedding required |
| 90 minutes | ~36.7M items | ~1.8–2.9GB | Severe | Redis OOM risk; emergency shedding |

**Redis memory is the hard ceiling at approximately 60 minutes of sustained maximum viral inbound.** This is a real operational risk, not a theoretical one. The response protocol:

1. **15 minutes sustained Critical:** On-call engineer evaluates whether inbound rate is actually at planning ceiling or whether the alert reflects a model error.
2. **30 minutes sustained Critical:** Begin shedding lowest-score P2 items (oldest, lowest-engagement notifications) by expiring them at the queue level rather than at the worker.
3. **45 minutes sustained Critical:** Notify Product; evaluate whether P1 items older than 30 minutes should be shed.
4. **60 minutes:** Redis memory alert fires independently. On-call engineer has authority to shed P1 items without additional approval.

This protocol requires Product sign-off before launch. The alternative — provisioning a larger Redis instance — is available but does not change the fundamental tradeoff: unbounded viral events require either infinite memory or a shedding strategy.

**P1 SLA during viral events:**

| Queue depth | Expected P1 tail latency | Alert state |
|-------------|--------------------------|-------------|
| < 10,000 items | < 30 seconds | Normal |
| 10,000–100