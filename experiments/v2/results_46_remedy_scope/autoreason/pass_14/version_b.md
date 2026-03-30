# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script (shown in Section 2.2). The token bucket is only meaningful if workers are split by priority tier — the worker pool structure that makes the guarantee real is specified in Section 3.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The processing Sorted Set tracks in-flight messages and is the mechanism for crash recovery. Its structure, worker interaction protocol, and stuck-message handling are specified in Section 2.3. PostgreSQL pool exhaustion risk is quantified with corrected arithmetic in Section 2.1; the worst-case delay is approximately 95 minutes for P1 messages under coincident failure, not 16 minutes as stated in the prior version. That figure requires a named decision-maker to accept or reject before the system goes to production.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. The traffic response matrix specifies *which* worker type to provision at each threshold — generic "additional instances" is not an actionable response given worker specialization. Capacity shift timing figures are derived from a task breakdown in Section 1.3, not asserted.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits. The FCM rate limit used in the spike analysis (10,000/sec) is a planning assumption derived from documented defaults, not a contractual guarantee. The sensitivity of the spike analysis to that figure is quantified in Section 1.4.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated. Where assumptions compound, the sensitivity is quantified. Where a risk acceptance decision has product-facing consequences, it is escalated to a named decision-maker rather than treated as an engineering planning choice.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Average-peak sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

### 1.2 Traffic Response Matrix

The matrix specifies responses at volume thresholds. Decisions are pre-specified to avoid reactive calls made under pressure. Because workers are specialized by channel type, "provision additional instances" is not actionable — the matrix names the specific worker type to provision at each threshold.

**Named decision owner:** The engineering lead (designated before month 1, with a named backup) reviews the month-1 traffic data and makes the architectural response decision for the >80M/day bands. Both names are recorded in the runbook before the system goes to production.

| Measured daily volume | Classification | Response — specific worker types | Confirmation metric | Escalation if unconfirmed |
|----------------------|----------------|----------------------------------|--------------------|-----------------------------|
| < 7.5M/day | Well below plan | Scale down push worker instances (largest pool) | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Provision additional push worker instances (push is 70% of volume; this is the correct first lever). If queue depth alert is push-specific, provision push workers only. If alert is cross-channel, provision push + email workers. Increase Redis instance size same day. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + backup make go/no-go at 3-week checkpoint |

**How to identify which worker type is saturated:** Each worker type emits a `queue_depth` metric tagged by channel and priority. The runbook instructs on-call engineers to check the per-channel queue depth dashboard before provisioning. Push saturation will show a rising `queue_depth{channel=push}` while email and SMS queues remain flat.

### 1.3 Channel Split, Volume Accounting, and Capacity Shift Timing

| Channel | Share of dispatch | Daily dispatch volume | Peak dispatch demand |
|---------|------------------|----------------------|---------------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

**Worker specialization:** Workers are specialized binaries per channel type. A push worker contains FCM and APNs dispatch logic and credentials. An email worker contains SMTP client logic and SendGrid credentials. They share no dispatch code at runtime.

The cost of specialization is that scaling a channel requires deploying instances of the correct binary type. The benefit is that credentials are isolated, deployment lifecycles are decoupled, and a bug in the email dispatch path cannot affect push delivery.

**Capacity shift timing — derived from task breakdown:**

The figures below are derived from the steps required, not asserted. The task breakdown is recorded here so the estimates can be challenged.

*Automated trigger (queue depth threshold → auto-scaling rule):*
- Auto-scaling rule evaluates metric: ~30 seconds
- Instance boot + process start: ~60–90 seconds
- Worker connects to Redis and begins consuming: ~10 seconds
- **Total: 2–3 minutes**

*Manual, runbook available, on-call engineer present:*
- Engineer wakes, reads alert, opens runbook: ~2 minutes
- Reads per-channel queue depth dashboard to identify which worker type: ~1 minute
- Executes runbook command to scale correct worker deployment: ~2 minutes
- Instance boot + worker start: ~2 minutes
- Confirms queue depth is declining: ~1 minute
- **Total: ~8 minutes**

*Manual, unrehearsed, 3 AM (no runbook, engineer must reason from first principles):*
- Engineer wakes, reads alert: ~2 minutes
- Identifies correct worker type from metrics (no runbook prompt): ~5 minutes
- Locates deployment configuration, determines correct scaling command: ~8 minutes
- Executes, waits for boot, confirms: ~5 minutes
- **Total: 20–30 minutes**

The 20–30 minute figure is the risk window during the first 60 days before auto-scaling rules are implemented (month 2). Auto-scaling rules eliminate the manual path for the common case.

### 1.4 Viral Spike Analysis

**The FCM rate limit assumption must be stated explicitly:**

"FCM's per-project rate limit is configurable up to ~10,000/sec" is a planning assumption, not a documented guarantee. FCM's rate limits are not publicly specified at this granularity and vary by project history and account standing. The 10,000/sec figure is derived from documented FCM defaults for established projects and is used here as a planning figure.

**Sensitivity of the spike analysis to this assumption:**

| Assumed FCM limit | Binding constraint | Spike behavior |
|---|---|---|
| 500/sec | FCM limit | P1 queue accumulates rapidly; DM delays measured in hours during spike |
| 2,000/sec | FCM limit | P1 queue accumulates; DM delays 15–30 min during sustained spike |
| **10,000/sec (plan)** | FCM limit (at 20× spike) | P1 largely protected; P2/P3 accumulate |
| > 26,000/sec | Worker capacity | Worker capacity becomes binding before FCM |

**Required action before production:** Confirm the actual FCM rate limit for this project by contacting FCM support or by load testing against a staging project. If the actual limit is below 2,000/sec, the spike analysis and the P1 protection claims in this document are wrong, and the priority queue structure must be re-evaluated.

**Corrected post-spike recovery timeline (assuming 10,000/sec FCM limit):**

During a sustained spike, workers accumulate FCM backoff state. FCM's backoff under sustained 429 responses reaches approximately 32 seconds between retry attempts.

- **0–32 seconds post-spike:** Workers are mid-backoff. Effective dispatch rate: ~20–40% of capacity.
- **32–90 seconds post-spike:** Workers reset backoff. Effective dispatch rate ramps to ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity.

At 2.1M messages queued during a 10-minute spike and a 90-second ramp-up before full drain rate, corrected drain estimate is **5–8 minutes** for P2/P3. P1 messages drain ahead of the P2/P3 backlog via the priority worker pool structure (Section 3).

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path |

**PostgreSQL failure risk — corrected arithmetic:**

There are two distinct failure modes.

**Transient unavailability (crash, failover, restart):** Workers detect fetch failure, pause dequeue, and retry with exponential backoff. Messages are not lost; delivery is delayed. Recoverable and bounded.

**Connection pool exhaustion — corrected worst-case calculation:**

Under normal conditions at 1,575/sec peak with 100 connections and 2–5ms query latency, pool throughput is approximately 20,000–50,000 queries/sec — well above demand.

Pool exhaustion becomes a risk when a viral spike (~10,500/sec demand) coincides with a slow query event (index bloat, autovacuum, lock contention) that increases per-query latency to 50–100ms.

At 100ms per query and 100 connections, pool throughput drops to 1,000 queries/sec.

**Corrected worst-case arithmetic:**

- Accumulation rate: 10,500 demand − 1,000 throughput = **9,500 messages/sec accumulating**
- Over 10 minutes: 9,500 × 600 = **5,700,000 messages queued** (prior version stated 570,000 — off by 10×)
- Drain time after condition resolves at full throughput (~9,500/sec net): approximately **10 minutes**
- Total P1 delay for messages queued mid-event: **up to 20 minutes drain** + up to **10 minutes** of coincident failure duration = **worst case ~30 minutes**

The prior version's "16-minute DM delay" figure was derived from an arithmetic error. The corrected figure is approximately **30 minutes** under the specific coincident failure scenario (viral spike + slow query event, both sustained for 10 minutes).

**This figure requires a named decision-maker.** A 30-minute DM delivery delay under coincident failure is a product decision, not an engineering planning choice. The decision to accept this risk for the first 60 days must be made by [Product Lead name] and [Engineering Lead name] and recorded before the system goes to production. If that delay is unacceptable, full payload storage in Redis eliminates the DB dependency on the hot path entirely — the tradeoff is real and the decision belongs to the product and engineering leads jointly, not to the infrastructure team unilaterally.

**Mitigations, in priority order:**

1. **Read replica for payload fetch** (highest leverage): Payload fetches are reads; routing them to a read replica removes them from the primary write path and effectively doubles pool throughput. Engineering cost: approximately 2 days in month 2.

2. **Payload caching in Redis** (5-minute TTL): Hit rate for recently enqueued messages during a spike is high — estimated 60–80% reduction in PostgreSQL fetch rate during spike conditions. Engineering cost: approximately 1 day.

3. **Pool size increase via PgBouncer**: Increasing the pool to 300 under viral spike conditions provides 3× throughput headroom. Triggered by queue depth alert.

**Planning decision:** Implement read replica routing and payload caching in month 2. With both mitigations in place, the coincident failure scenario requires a slow query event to affect both primary and replica simultaneously — a lower-probability condition.

### 2.2 Priority Queue Structure, TTL Enforcement, and Starvation Prevention

Four priority levels with defined semantics:

| Priority | Examples | TTL | Minimum dispatch rate |
|----------|----------|-----|----------------------|
| P0 | Security alerts, account recovery | 1 hour | No cap — always drain first |
| P1 | Direct messages, mentions | 4 hours | No cap — drain before P2/P3 |
| P2 | Comments, reactions | 24 hours | 200 tokens/sec fleet-wide |
| P3 | Recommendations, digests | 72 hours | 50 tokens/sec fleet-wide |

**The starvation prevention mechanism — how it actually works:**

The token bucket guarantees a minimum dispatch rate for P2 and P3. This guarantee is only meaningful if some workers are dedicated to P2/P3 regardless of P0/P1 queue depth. A priority-ordered single worker pool — drain P0 before P1 before P2 — cannot simultaneously drain P1 at full rate and guarantee P2 minimums. The token bucket is a rate control mechanism, not a scheduling mechanism.

**The scheduling mechanism that makes the guarantee real is the worker pool split, specified in Section 3.** A fraction of push workers are permanently assigned to P2/P3 queues only. These workers do not check P0/P1 queues. The token bucket then limits their dispatch rate to 200/sec (P2) and 50/sec (P3) to prevent P2/P3 from consuming capacity needed for P0/P1 during load spikes.

The combined guarantee: P2 receives at least 200/sec and at most its dedicated worker pool capacity. P1 receives the remainder of worker capacity after P2/P3 dedicated pools are allocated.

**Token bucket Lua script — atomic check and consumption:**

The check and consumption must execute atomically. A non-atomic implementation (read token count, check, decrement as separate commands) allows two workers to both read a count of 1, both decide to proceed, and both decrement — resulting in a negative token count and a burst above the rate limit. The Lua script below executes as a single atomic operation in Redis.

```lua
-- token_bucket_consume.lua
-- KEYS[1]: token bucket key (e.g., "token_bucket:p2")
-- ARGV[1]: max_tokens (bucket capacity)
-- ARGV[2]: refill_rate (tokens per second, as a fleet-allocable share)
-- ARGV[3]: current_time_seconds (Unix timestamp, passed from caller)
-- ARGV[4]: tokens_requested (typically 1)
--
-- Returns: 1 if tokens were consumed (proceed), 0 if insufficient tokens (backoff)
--
-- Correctness properties:
-- 1.