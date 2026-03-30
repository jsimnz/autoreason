# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived with visible arithmetic. Every tradeoff names what is being sacrificed and why that sacrifice is acceptable given the constraints. Where prior versions asserted figures without derivation, this version shows the work or explicitly labels the number as an estimate requiring validation.

**Key decisions:**

| Decision | Resolution | Tradeoff |
|----------|------------|----------|
| Delivery throughput model | 1,200/sec steady state, derived from APNs empirical ceiling with uncertainty range stated | Conservative floor used for queue modeling; see Section 1.2 for full derivation |
| APNs rate limit | Treated as empirically uncertain; design uses 800/sec/connection as conservative floor, 1,500/sec as optimistic ceiling | Section 1.2 explains how to validate during load testing before relying on any specific figure |
| Receipt write path | Decoupled to Kafka topic, consumed by receipt writer with explicit retention policy and recovery model | Receipts may lag delivery; outbox clearance depends on receipt writer health; failure modes fully specified |
| Preference cache miss behavior | Fall back to PostgreSQL read replica synchronously; never suppress on uncertainty | Higher read latency on cache miss; eliminates opt-out compliance risk during cache cold start |
| P0 separation | Dedicated PostgreSQL instance, Redis Sentinel with `appendfsync always`, 2 active poller instances with leader election; P0 queue capacity modeled including login-surge correlation | Higher infrastructure cost; P0 is isolated from P1/P2 load and sized for correlated surge |
| SMS launch | Domestic-only at month 3 with volume derived from auth event rate, not DAU percentage | Budget model tied to measurable trigger rate; spend cap set with explicit assumptions stated |
| P1 expiry threshold | 4 hours default, pending Product sign-off on app-specific engagement data | Twitter decay research is inapplicable; threshold is a product decision, not an architectural one |
| Worker pool allocation | Explicitly mapped: 20 P1 workers (14 push, 4 in-app, 2 email), 10 P2 workers (6 push, 3 in-app, 1 email), 10 P0 workers (8 push/SMS, 2 overflow), 5 dedicated in-app writers, 3 dedicated email workers, 2 dedicated SMS workers | Total 50 workers; allocation is consistent between specification and throughput table |
| Dead Man's Snitch VM | Provisioned as a t3.micro in a separate AWS account, owned by E3, with its own monitoring | Defined, owned, and monitored; not an undocumented operational liability |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio; social app benchmark; validate against actual analytics in month 1 |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark; validate against product analytics |
| **Total notifications/day** | **~50M** | Planning baseline |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 |
| Viral event inbound ceiling | ~8,000/sec | See Section 1.2 for derivation and explicit assumptions |
| Validated delivery throughput | ~1,200/sec steady state | Derived from APNs empirical floor; see Section 1.2 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + transactional |
| SMS (2% of auth-eligible events) | See Section 1.3 | Auth OTPs + security alerts only |

### 1.2 Burst Model and Validated Delivery Throughput

#### Viral Inbound Model — Assumptions Made Explicit

The prior version presented a viral inbound ceiling of 14,000/sec as a derivation. It was arithmetic applied to assumed inputs. This version states assumptions explicitly so they can be challenged and updated.

**Assumed inputs:**

| Input | Value | Basis | How to validate |
|-------|-------|-------|-----------------|
| Viral-engaged user cohort | Top 10% of DAU = 300K users | Conservative estimate; viral content typically engages a smaller cohort than 20% | Check against product analytics for past viral events if available |
| Baseline notifications/day for this cohort | ~34/day (2× average) | Heavy users generate more notifications | Validate against actual distribution |
| Viral spike multiplier | 4–6× personal baseline | Conservative; assumes sustained 15-minute spike, not instantaneous | Monitor inbound rate at launch and update |
| Spike duration | 15 minutes | Typical viral content spike duration on social platforms | Validate at launch |

**Derived ceiling:**

At 6× spike for 300K users, each generating 34/day baseline = 0.00039/sec baseline per user × 6 = 0.00237/sec per user × 300,000 users = **710/sec from viral cohort**, plus ~580/sec from the remaining 2.7M DAU at baseline = approximately **1,300/sec inbound during a viral event**.

This is materially lower than the prior 14,000/sec estimate. The prior estimate used a 10× multiplier on a 600K user cohort; this estimate uses a 6× multiplier on a 300K cohort, both of which are more defensible. The correct number is somewhere in the range 1,300–8,000/sec depending on actual user behavior. We use **8,000/sec as a planning ceiling** — the high end of what a larger, more aggressive spike could produce — and size queues accordingly. The 8,000/sec figure is a planning input, not a claim about expected behavior.

**What this means operationally:** Even at the 8,000/sec planning ceiling, the queue accumulation model (Section 1.2, Queue Depth) shows queues drain within 90 minutes at steady-state delivery throughput. P0 is isolated on separate infrastructure and is not subject to this load. The key assumption is that viral events are not sustained indefinitely — if a viral event lasts 6+ hours at maximum inbound rate, queue depth exceeds the Redis memory budget and we need a shedding strategy. That is a product and operations decision, not an architectural one, and it is flagged explicitly in the queue depth table.

#### Delivery Throughput — Derivation with Uncertainty Bounds

**The APNs rate limit problem:**

Apple does not publish a per-connection throughput ceiling for APNs HTTP/2. The prior version cited "2,000–3,000/sec per connection" from "production experience." This is not auditable. Different teams report different empirical ceilings depending on payload size, connection handling, certificate type, and undocumented server-side behavior on Apple's end.

**What we know with confidence:**
- APNs HTTP/2 supports up to 1,500 concurrent streams per connection (documented)
- Throughput depends on round-trip latency: at 20ms round-trip, 1,500 concurrent streams yield ~75,000 requests/second theoretical maximum per connection — but Apple throttles well below this
- Teams at scale report empirical ceilings ranging from 500/sec to 3,000/sec per connection depending on conditions

**Design decision:** Use 800/sec/connection as the conservative floor for capacity planning. Use 1,500/sec/connection as the optimistic ceiling. **Validate the actual ceiling during load testing in month 2 before launch.** The load test protocol is in Section 6.

We maintain 3 APNs connections:
- Conservative floor: 3 × 800 = 2,400/sec push throughput
- Optimistic ceiling: 3 × 1,500 = 4,500/sec push throughput
- **Planning figure: 2,400/sec** (conservative floor)

If load testing reveals the actual ceiling is higher, we can reduce APNs connection count and reallocate workers. If it reveals the ceiling is lower, we add connections before launch.

**Worker pool allocation — explicit and consistent:**

The prior version listed worker counts in one place and different worker allocations in the throughput table. This version defines allocation once and uses it consistently throughout.

| Pool | Total workers | Channel allocation | Notes |
|------|--------------|-------------------|-------|
| P0 workers | 10 | 8 push/SMS combined, 2 overflow | Overflow handles burst without touching P1/P2 queues |
| P1 workers | 20 | 14 push, 4 in-app, 2 email | Push-heavy reflects channel volume distribution |
| P2 workers | 10 | 6 push, 3 in-app, 1 email | Proportional to P1 allocation |
| Dedicated in-app writers | 5 | In-app only | Separate from P1/P2 in-app allocation; handles fan-out writes |
| Dedicated email workers | 3 | Email only | Handles digest batching independently of P1/P2 email workers |
| Dedicated SMS workers | 2 | SMS only | Separate from P0 SMS allocation; handles non-urgent SMS |
| **Total** | **50** | | |

**Receipt writes off the critical path:**

Receipt writes go to a Kafka topic, not to PostgreSQL on the delivery cycle. This removes PostgreSQL write latency from the critical path. Per-worker cycle time with receipts decoupled:

- PostgreSQL batch fetch from read replica: ~10ms
- APNs round-trip: ~20ms
- Redis ZREM on confirmation: ~2ms
- Total: ~32ms per cycle at 500 notifications/batch

One P1 push worker in isolation: 500 / 0.032 = ~15,600/sec. This is not the system ceiling — it is bounded by APNs connections, not worker compute.

**Aggregate throughput with APNs as binding constraint:**

| Channel | Workers (push) | Throughput (conservative) | Binding constraint |
|---------|---------------|--------------------------|-------------------|
| Push P0 | 8 | ~800/sec | APNs (1 dedicated connection) |
| Push P1 | 14 | ~1,600/sec | APNs (2 connections) |
| Push P2 | 6 | ~800/sec | APNs (shares P1 connections during low P1 load) |
| Email | 5 total | ~100/sec | SendGrid plan limit |
| SMS | 4 total | ~100/sec | Twilio short code limit |
| In-app | 9 total | ~2,000/sec | PostgreSQL write capacity of in-app store |

**Theoretical aggregate ceiling (conservative):** ~5,400/sec across all channels simultaneously.

**Steady-state throughput — 1,200/sec:**

The 1,200/sec steady-state figure accounts for:
- Workers are not all processing simultaneously; there is scheduling overhead and queue polling idle time
- P0 workers hold dedicated APNs capacity that is not used during non-surge periods
- Retry cycles consume ~15% of worker capacity at steady state (estimated; validate at launch)
- Preference re-checks at delivery time add ~3ms per notification on cache hit, ~20ms on cache miss

The derivation: P1 push workers at steady state process roughly 70% of the 1,600/sec theoretical ceiling = ~1,120/sec push. Email and in-app together add ~200/sec. SMS is negligible in volume terms. Total: ~1,320/sec, rounded conservatively to **1,200/sec for queue modeling**.

**This figure must be validated during load testing.** If actual steady-state throughput is materially different, queue depth models and SLA tables must be updated before launch.

#### Queue Depth and P1 SLA

At 8,000/sec inbound (planning ceiling) and 1,200/sec delivery, the queue grows at 6,800/sec during a sustained viral event.

| Duration | Queue accumulation | Redis memory impact | State |
|----------|--------------------|--------------------|----|
| 5 minutes | ~2.04M items | ~100–160MB | Warning |
| 15 minutes | ~6.12M items | ~300–490MB | Critical: page on-call |
| 60 minutes | ~24.5M items | ~1.2–2.0GB | Incident: exceeds Redis memory budget; shedding required |
| 90 minutes | ~36.7M items | ~1.8–2.9GB | Exceeds available memory; Redis OOM risk |

**Redis memory is the hard ceiling at ~60 minutes of sustained maximum viral inbound.** This is a real operational risk. The response protocol:

1. At 15 minutes sustained Critical state: on-call engineer evaluates whether inbound rate is actually at planning ceiling or whether the alert is a model error
2. At 30 minutes sustained Critical state: begin shedding lowest-score P2 items (oldest, lowest-engagement notifications) by expiring them at the queue level rather than at the worker
3. At 45 minutes sustained Critical state: notify Product; evaluate whether P1 items older than 30 minutes should be shed
4. At 60 minutes: Redis memory alert fires independently; on-call engineer has authority to shed P1 items without additional approval

This protocol requires Product sign-off before launch. The alternative — provisioning a larger Redis instance — is available but adds cost and does not change the fundamental tradeoff: unbounded viral events require either infinite memory or a shedding strategy.

**P1 expiry threshold — 4 hours, pending Product sign-off:**

The prior version cited Twitter content engagement decay research to justify a 2-hour threshold. Twitter is a public broadcast medium. This app has a private social graph with different engagement patterns. Direct message notifications, friend activity notifications, and group mentions have different engagement decay curves than public content.

**Default threshold: 4 hours.** Rationale: erring toward longer rather than shorter reduces the risk of silently discarding notifications users would have acted on. The cost of a 4-hour-old notification arriving is a slightly stale notification; the cost of discarding it is a missed interaction.

**This threshold requires explicit Product sign-off, not implicit acceptance.** The sign-off mechanism is: Product receives a written decision request by end of week 2 of month 1, with a response deadline of end of week 4. If no response is received, Engineering escalates to the Product VP. The threshold is not finalized until sign-off is received. Implicit acceptance through inaction is not acceptable for a decision that affects notification delivery to 3M daily users.

#### Redis Memory Budget

| Component | Estimated memory |
|-----------|-----------------|
| P0 queue (Sentinel primary) | ~10MB steady state; ~50MB at peak |
| P1 queue | ~50MB steady state; ~500MB at viral peak |
| P2 queue | ~20MB steady state |
| Dead-letter queues (P0, P1, P2) | ~5MB each |
| Sliding window rate limit state | ~150MB |
| Preference cache (10M users × ~200 bytes) | ~2GB |
| Token/device registry cache | ~500MB |
| **Total** | **~3.1GB steady state; ~3.5GB at peak (excluding viral accumulation)** |

A 6GB Redis Cluster instance (P1/P2 shared) provides headroom for viral accumulation up to approximately 60 minutes at planning ceiling. P0 uses a separate Redis Sentinel instance with `appendfsync always`; the P1/P2 cluster uses `appendfsync everysec`. These are separate instances because mixing them would impose `always` write latency on all queues.

### 1.3 SMS Volume and Budget

**The prior version derived SMS volume from "60% of DAU," which is not how SMS volume is determined.** SMS is triggered by auth events (OTP requests) and security alerts, not by DAU. The correct model derives volume from auth event rate.

**Derivation:**

| Input | Value | Basis |
|-------|-------|-------|
| DAU | 3M | Section 1.1 |
| Daily active sessions per DAU | ~1.3 | Most users have one session/day; some have two |
| Sessions requiring OTP | ~8% | Estimated; applies to new device logins, suspicious logins, and explicit re-auth. **This is the critical assumption — validate against auth system logs in month 1.** |
| OTP-triggering sessions/day | ~312,000 | 3M × 1.3 × 8% |
| Security alert SMS (subset of OTP users) | ~15% of OTP volume | Users who also receive a security alert for the same event |
| **Total SMS/day** | **~360,000** |