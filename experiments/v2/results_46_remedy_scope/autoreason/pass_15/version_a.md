# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script (Section 2.2). The token bucket is only meaningful if workers are split by priority tier — the worker pool structure that makes the guarantee real is specified in Section 3.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The processing Sorted Set tracks in-flight messages and is the mechanism for crash recovery. PostgreSQL pool exhaustion risk is quantified with corrected arithmetic in Section 2.1; the worst-case P1 delay under coincident failure is approximately 30 minutes, not 16 minutes. That figure requires a named decision-maker to accept or reject before the system goes to production.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. The traffic response matrix specifies *which* worker type to provision at each threshold — "additional instances" is not actionable given worker specialization. Capacity shift timing figures are derived from a task breakdown in Section 1.3, not asserted.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits. The FCM rate limit used in the spike analysis (10,000/sec) is a planning assumption, not a contractual guarantee. The sensitivity of the spike analysis to that figure is quantified in Section 1.4, with a required pre-production action to confirm the actual limit.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated. Where assumptions compound, the sensitivity is quantified. Where a risk acceptance decision has product-facing consequences, it is escalated to a named decision-maker rather than treated as an engineering planning choice.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%. Facebook historically ~65%; newer apps often 15–25%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Average-peak sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic. The 3× peak multiplier assumes a two-hour evening window; if the app has strong international distribution, the peak-to-average ratio may be lower (rolling timezone distribution) or higher (synchronized global event). This assumption should be revisited with real traffic data at month 1.

### 1.2 Traffic Response Matrix

The matrix specifies responses at volume thresholds. Decisions are pre-specified to avoid reactive calls made under pressure at 3 AM. Because workers are specialized by channel type, the matrix names the specific worker type to provision at each threshold rather than generic "additional instances."

**Named decision owner:** The engineering lead (designated before month 1, with a named backup for unavailability) reviews the month-1 traffic data and makes the architectural response decision for the >80M/day bands. Both names are recorded in the runbook before the system goes to production.

| Measured daily volume | Classification | Response — specific worker types | Confirmation metric | Escalation if unconfirmed |
|----------------------|----------------|----------------------------------|--------------------|-----------------------------|
| < 7.5M/day | Well below plan | Scale down push worker instances (largest pool) | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Provision additional push worker instances first (push is 70% of volume). If queue depth alert is push-specific, provision push workers only. If cross-channel, provision push + email workers. Increase Redis instance size same day. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + backup make go/no-go at 3-week checkpoint |

**How to identify which worker type is saturated:** Each worker type emits a `queue_depth` metric tagged by channel and priority. The runbook instructs on-call engineers to check the per-channel queue depth dashboard before provisioning. Push saturation shows a rising `queue_depth{channel=push}` while email and SMS queues remain flat. This check takes approximately one minute and prevents provisioning the wrong worker type.

The 80M/day threshold is the point at which infrastructure changes require code changes. Pre-specifying the response prevents architecture decisions from being made reactively.

### 1.3 Channel Split, Volume Accounting, and Capacity Shift Timing

**Accounting note:** Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record (for when the user returns) and queues a push notification (for immediate delivery). The volume model accounts for worst-case write load; suppression of push when a user is connected via WebSocket is an optimization implemented at the notification router, not an assumption baked into the volume model.

| Channel | Share of dispatch | Daily dispatch volume | Peak dispatch demand |
|---------|------------------|----------------------|---------------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

**Worker specialization:** Workers are specialized binaries per channel type. A push worker contains FCM and APNs dispatch logic and credentials. An email worker contains SMTP client logic and SendGrid credentials. They share no dispatch code at runtime.

The cost of specialization: scaling a channel requires deploying instances of the correct binary type. The benefit: credentials are isolated, deployment lifecycles are decoupled, and a bug in the email dispatch path cannot affect push delivery. A single parameterized binary would require all credentials in every worker's environment and would couple deployment lifecycles across unrelated channel types. Specialization is the correct choice given the team size — the operational clarity outweighs the minor deployment overhead.

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
- Identifies correct worker type from metrics without runbook prompt: ~5 minutes
- Locates deployment configuration, determines correct scaling command: ~8 minutes
- Executes, waits for boot, confirms: ~5 minutes
- **Total: 20–30 minutes**

The 20–30 minute figure is the risk window during the first 60 days before auto-scaling rules are implemented in month 2. Auto-scaling rules eliminate the manual path for the common case. Runbook creation is a month-1 deliverable; the 8-minute manual path applies once the runbook exists.

### 1.4 Viral Spike Analysis

**The FCM rate limit assumption must be stated explicitly:**

"FCM's per-project rate limit is approximately 10,000/sec" is a planning assumption derived from documented FCM defaults for established projects, not a contractual guarantee. FCM's rate limits are not publicly specified at this granularity and vary by project history and account standing.

**Sensitivity of the spike analysis to this assumption:**

| Assumed FCM limit | Binding constraint | Spike behavior |
|---|---|---|
| 500/sec | FCM limit | P1 queue accumulates rapidly; DM delays measured in hours during spike |
| 2,000/sec | FCM limit | P1 queue accumulates; DM delays 15–30 min during sustained spike |
| **10,000/sec (plan)** | FCM limit (at 20× spike) | P1 largely protected; P2/P3 accumulate |
| > 26,000/sec | Worker capacity | Worker capacity becomes binding before FCM |

**Required action before production:** Confirm the actual FCM rate limit for this project by contacting FCM support or by load testing against a staging project. If the actual limit is below 2,000/sec, the spike analysis and P1 protection claims in this document are materially wrong, and the priority queue structure must be re-evaluated before launch.

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window via dedicated worker pools. P2 and P3 messages accumulate in queue and drain after the spike subsides.

**Corrected post-spike recovery timeline (assuming 10,000/sec FCM limit):**

During a sustained spike, workers accumulate FCM backoff state. FCM's documented backoff under sustained 429 responses reaches approximately 32 seconds between retry attempts (5 doublings from a 1-second base). Workers that have reached the backoff ceiling are not immediately dispatching at full rate when the spike ends.

- **0–32 seconds post-spike:** Workers are mid-backoff. Effective dispatch rate: ~20–40% of capacity.
- **32–90 seconds post-spike:** Workers reset backoff. Effective dispatch rate ramps to ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity. Queue drains at net excess rate.

At 2.1M messages queued during a 10-minute spike and a 90-second ramp-up before full drain rate, the corrected drain estimate is **5–8 minutes** for P2/P3. The range reflects uncertainty in how many workers reached maximum backoff depth versus shallower states. P1 messages drain ahead of the P2/P3 backlog via the dedicated worker pool structure specified in Section 3.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload in Redis |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path; Redis memory is the constraint |

**Processing Sorted Set — crash recovery mechanism:**

When a worker dequeues a message from the priority queue (a Redis List or Sorted Set), it immediately writes the notification ID to a `processing:{worker_id}` Sorted Set scored by the dequeue timestamp. On successful dispatch, the worker removes the ID from the processing set. On crash, the processing set retains the ID.

A recovery process scans all `processing:{worker_id}` sets every 60 seconds. Any ID with a score older than `max_dispatch_time + 30 seconds` (typically 90 seconds total) is re-enqueued at its original priority. This ensures at-least-once delivery. The dispatch layer must be idempotent — sending the same notification ID twice should result in deduplication at the recipient device or suppression at the dispatch layer via a delivered-ID bloom filter.

**PostgreSQL failure risk — corrected arithmetic:**

There are two distinct failure modes requiring different responses.

**Transient unavailability (crash, failover, restart):** Workers detect fetch failure, pause dequeue, and retry with exponential backoff. If unavailability exceeds 30 seconds, workers pause dequeue entirely rather than accumulate failed fetch attempts. Messages are not lost; delivery is delayed. Recoverable and bounded.

**Connection pool exhaustion — corrected worst-case calculation:**

Under normal conditions at 1,575/sec peak with 100 connections and 2–5ms query latency, pool throughput is approximately 20,000–50,000 queries/sec — well above demand.

Pool exhaustion becomes a risk when a viral spike (~10,500/sec demand) coincides with a slow query event (index bloat, autovacuum, lock contention) increasing per-query latency to 100ms.

At 100ms per query and 100 connections, pool throughput drops to 1,000 queries/sec.

**Corrected worst-case arithmetic:**

- Accumulation rate: 10,500 demand − 1,000 throughput = **9,500 messages/sec accumulating**
- Over 10 minutes of coincident failure: 9,500 × 600 = **5,700,000 messages queued**
- Drain time after condition resolves at full throughput (~9,500/sec net excess): approximately **10 minutes**
- Total worst-case P1 delay: up to 10 minutes of coincident failure + 10 minutes drain = **~20 minutes**; with a longer slow-query event (30 minutes), worst case approaches **~40 minutes**

A prior version of this analysis stated "16-minute DM delay" — that figure was derived from an arithmetic error (off by 10× on queue accumulation). The corrected range is **20–40 minutes** depending on coincident failure duration.

**This figure requires a named decision-maker.** A 20–40 minute DM delivery delay under coincident failure is a product decision, not an engineering planning choice. The decision to accept this risk for the first 60 days must be made by [Product Lead name] and [Engineering Lead name] and recorded before the system goes to production.

If that delay is unacceptable, **full payload storage in Redis eliminates the DB dependency on the hot path entirely.** The tradeoff: Redis memory cost at 500K queue depth is ~500MB–1GB versus ~100MB for ID-only, and Redis becomes a single point of failure for both queue state and payload. This decision belongs to the product and engineering leads jointly.

**Mitigations, in priority order (for the ID-based approach):**

1. **Read replica for payload fetch** (highest leverage, ~2 days engineering in month 2): Payload fetches are reads; routing to a read replica effectively doubles pool throughput and requires the slow-query event to affect both primary and replica simultaneously — a materially lower-probability condition.

2. **Payload caching in Redis** (5-minute TTL, ~1 day engineering): Hit rate for recently enqueued messages during a spike is estimated at 60–80%, reducing PostgreSQL fetch rate proportionally during spike conditions.

3. **Pool size increase via PgBouncer** (operational, ~2 hours): Increasing the pool to 300 connections provides 3× throughput headroom, triggered by queue depth alert. PostgreSQL supports ~500 simultaneous connections before