# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script (Section 3). The token bucket guarantee is only meaningful if workers are split by priority tier — the worker pool structure that makes this real is specified in Section 3.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The processing Sorted Set tracks in-flight messages and is the mechanism for crash recovery. PostgreSQL pool exhaustion risk is quantified with corrected arithmetic in Section 2.1. The worst-case P1 delay under coincident failure is **20–40 minutes under a standard spike, and 50–70 minutes if a DB issue outlasts the spike** — both figures are derived step-by-step. Both require named decision-makers to accept or reject before production.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. The traffic response matrix in Section 1.3 names the specific worker type to provision at each threshold. Capacity shift timing figures are derived from a task breakdown, not asserted.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits. The FCM rate limit used in the spike analysis (10,000/sec) is a planning assumption, not a contractual guarantee. The sensitivity of the spike analysis to that figure is quantified in Section 1.4, with a required pre-production load test to bound the uncertainty.

**Three decisions require named humans before production.** Those decisions are identified in the sections where they arise. The mechanism enforcing this gate is a checklist in the deployment runbook that blocks the production deployment step. Placeholder text is not acceptable and blocks the checklist. If a checkpoint is missed, Section 7 specifies the default conservative action.

**What this document does not claim:**
- FCM rate limits are not knowable in advance with contractual precision. The spike analysis uses a planning assumption and quantifies how wrong that assumption can be before the architecture fails. The required pre-production action is a load test that bounds the uncertainty, not a confirmation that eliminates it.
- The worst-case DM delay figures are derived from arithmetic shown step-by-step, including the dependency on when a spike and slow-query event end relative to each other.
- Deduplication uses an explicit delivered-ID set, not a bloom filter. The false-positive rate for the mechanism used is zero, at the cost of bounded memory. The tradeoff is stated in Section 2.2.

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

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic. The 3× peak multiplier assumes a two-hour evening window. If the app has strong international distribution, the peak-to-average ratio may be lower (rolling timezone distribution) or higher (synchronized global event). This assumption must be revisited with real traffic data at the month-1 review.

**Month-1 checkpoint — missed checkpoint default:** If month-1 traffic data is not reviewed by day 35, the engineering lead defaults to provisioning for the 50% DAU/MAU scenario (100M/day) until the review occurs. This is conservative and costs money; the incentive is to do the review. This default is recorded in the runbook before production launch and applies regardless of who is available.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record (for when the user returns) and queues a push notification (for immediate delivery). The volume model accounts for worst-case write load; suppression of push when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model.

**A viral spike will drive push and in-app saturation simultaneously**, because they are triggered by the same upstream events. The traffic response matrix in Section 1.3 accounts for this correlated failure mode explicitly.

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

Decisions are pre-specified to avoid reactive calls made under pressure. Because workers are specialized by channel type (Section 3), the matrix names the specific worker type to provision at each threshold rather than generic "additional instances."

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook. Both names are filled in before production; placeholder text blocks the deployment checklist. The engineering lead (or named backup if unavailable) reviews month-1 traffic data and makes architectural response decisions for the >80M/day bands.

**Identifying which worker type is saturated:** Each worker type emits a `queue_depth` metric tagged by channel and priority. The runbook instructs on-call engineers to check the per-channel queue depth dashboard before provisioning. The most likely correlated failure is push + in-app saturation simultaneously (same upstream events), not push + email. Push saturation shows rising `queue_depth{channel=push}`; the matrix handles the co-saturation case explicitly.

**On dashboard reliability during incidents:** The per-channel queue depth dashboard may be slow or stale during the same Redis pressure event causing the alert. The runbook specifies a fallback: if the dashboard is unresponsive for more than 2 minutes, the on-call engineer queries Redis directly via CLI. The exact commands are included verbatim in the runbook:

```
LLEN queue:push:p1
LLEN queue:push:p2
LLEN queue:inapp:p1
```

The engineer does not need to reason from first principles at 3 AM. This CLI fallback is a runbook requirement, not a suggestion.

| Measured daily volume | Classification | Response — specific worker types | Confirmation metric | Escalation if unconfirmed |
|----------------------|----------------|----------------------------------|--------------------|-----------------------------|
| < 7.5M/day | Well below plan | Scale down push worker instances (largest pool) | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Check `queue_depth{channel=push}` and `queue_depth{channel=inapp}` first — these will co-saturate. Provision push workers + in-app write capacity. If email queue also rising, add email workers. Increase Redis instance size same day. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + backup make go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**

*Automated trigger (auto-scaling rule, month 2 onward):*
- Metric evaluation + instance boot + worker start: ~2–3 minutes

*Manual, runbook available, dashboard loading normally:*
- Engineer wakes, reads alert, opens runbook: ~2 minutes
- Queries per-channel queue depth (dashboard or CLI fallback): ~1–3 minutes
- Executes runbook scaling command: ~2 minutes
- Instance boot + confirmation: ~3 minutes
- **Total: ~8–10 minutes**

*Manual, runbook available, dashboard degraded (realistic incident scenario):*
- Engineer wakes, reads alert: ~2 minutes
- Dashboard unresponsive; switches to CLI fallback per runbook: ~3 minutes
- Executes scaling command: ~2 minutes
- Instance boot + confirmation via CLI: ~3 minutes
- **Total: ~10–15 minutes**

*Manual, no runbook, 3 AM (first 30 days before runbook is finalized):*
- **Total: 20–30 minutes** — this is the risk window before runbook completion. The runbook is a month-1 deliverable with a specific completion date. If it is not complete by day 30, the engineering lead is notified and the system operates under the 20–30 minute response assumption until complete.

### 1.4 Viral Spike Analysis

**The FCM rate limit cannot be confirmed in advance.** FCM does not publish per-project rate limits with contractual precision, and FCM support cannot guarantee a specific rate for a production project under viral conditions. Load testing a staging project produces useful signal but not a production guarantee.

The correct framing is: **bound the uncertainty through load testing, then make an explicit decision about residual risk.**

**Pre-production action:** Load test push dispatch against a staging project at 2×, 5×, and 10× planned peak. Record the rate at which 429 responses begin. Use the observed rate as the planning assumption. Accept that the production limit may differ, and use the sensitivity table below to understand what that means. If load testing produces an observed limit below 2,000/sec, the P1 protection claims in this document are materially wrong and the priority queue structure must be re-evaluated before launch. This is a pre-production gate, not a suggestion.

**Sensitivity table:**

| Assumed FCM limit | Binding constraint at 20× spike | P1 DM behavior |
|---|---|---|
| 500/sec | FCM limit | P1 delays measured in hours |
| 2,000/sec | FCM limit | P1 delays 15–30 min during sustained spike |
| **10,000/sec (plan)** | FCM limit | P1 largely protected; P2/P3 accumulate |
| > 26,000/sec | Worker capacity | Worker capacity becomes binding before FCM |

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window via dedicated worker pools. P2 and P3 messages accumulate in queue and drain after the spike subsides.

**Post-spike recovery — arithmetic shown explicitly:**

Assumptions: 10-minute sustained spike, FCM limit 10,000/sec, 20× demand spike producing ~21,000/sec push demand, workers accumulating exponential backoff to a ceiling of ~32 seconds.

Accumulation during spike:
- FCM can dispatch: 10,000/sec
- Demand: ~21,000/sec
- Net accumulation: ~11,000/sec
- Over 10 minutes: 11,000 × 600 = **6,600,000 messages queued**

During a sustained spike, workers accumulate FCM backoff state. FCM's documented backoff under sustained 429 responses reaches approximately 32 seconds between retry attempts (5 doublings from a 1-second base). Workers that have reached the backoff ceiling are not immediately dispatching at full rate when the spike ends.

- **0–32 seconds post-spike:** Workers are mid-backoff. Effective dispatch rate: ~20–40% of capacity.
- **32–90 seconds post-spike:** Workers reset backoff. Effective dispatch rate ramps to ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity.

At 6.6M messages queued and a 90-second ramp-up before full drain rate, drain time at net ~10,000/sec is approximately **11 minutes**. The drain timeline depends critically on when the spike ends relative to any coincident DB slow-query event:

| Scenario | Spike duration | DB issue duration | Messages queued at drain start | Net drain rate | Drain time | Total P1 delay |
|---|---|---|---|---|---|---|
| Spike only, no DB issue | 10 min | 0 | 6.6M | ~10,000/sec after backoff ramp | ~11 min | **~21 min** |
| Spike + DB issue, DB recovers first | 10 min | 8 min | 6.6M | Full rate after backoff ramp | ~11 min | **~21 min** |
| Spike + DB issue, co-terminus | 10 min | 10 min | 6.6M | Full rate after backoff ramp | ~11 min | **~21 min** |
| Spike ends, DB issue persists 20 min more | 10 min | 30 min total | 6.6M + continued accumulation | Partial until DB recovers | Extended | **50–70 min** |

The worst case is not the spike — it is a DB slow-query event that outlasts the spike and continues to constrain drain rate. The 50–70 minute figure for this scenario requires a real product decision before production. If that delay is unacceptable, the mitigation is full payload storage in Redis (eliminating the DB dependency on the hot path), at the cost of ~500MB–1GB additional Redis memory at 500K queue depth and increased Redis failure impact. This decision belongs to the product lead and engineering lead jointly, recorded with names and date before production launch.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload in Redis |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | DB unavailability delays delivery; messages not lost | Redis memory exhaustion; no DB dependency on hot path |
| Compounded failure risk | Spike + DB issue: 50–70 min worst case | Spike alone: Redis memory as binding constraint |

The decision to use ID-based storage must be made with the worst-case figure on the table. If the product lead and engineering lead accept the 50–70 minute worst case, ID-based is correct. If they do not, full payload in Redis is the alternative, and that decision changes infrastructure sizing.

**Processing Sorted Set — crash recovery mechanism:**

When a worker dequeues a notification ID from the priority queue, it immediately writes the ID to a `processing:{worker_id}` Sorted Set scored by the dequeue timestamp. On successful dispatch, the worker removes the ID from the processing set. On crash, the ID remains.

A recovery process — a single goroutine in a designated worker instance, not a separate service — scans all `processing:{worker_id}` sets every 60 seconds. Any ID with a score older than `max_dispatch_time + 30 seconds` (90 seconds default) is re-enqueued at its original priority. This produces at-least-once delivery semantics. Deduplication is handled in Section 2.2.

**PostgreSQL connection pool — corrected arithmetic:**

Under normal conditions at 1,575/sec peak with 100 connections and 2–5ms query latency, pool throughput