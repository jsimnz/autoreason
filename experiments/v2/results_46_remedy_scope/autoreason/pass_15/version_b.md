# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions, each of which is fully specified in this document rather than referenced forward to absent sections.

**What this document contains:**

- **Section 1:** Scale assumptions, traffic model, viral spike analysis with honest uncertainty bounds, and traffic response matrix
- **Section 2:** Queue architecture — ID-based entries, processing Sorted Set for crash recovery, PostgreSQL failure analysis with corrected arithmetic, and deduplication via a delivered-ID set with explicit false-positive handling
- **Section 3:** Worker pool structure — per-channel, per-priority pools with the specific Lua token bucket implementation that enforces starvation prevention
- **Section 4:** Channel delivery — push (FCM/APNs), email, in-app, SMS — with failure handling per channel
- **Section 5:** User preference management
- **Section 6:** Infrastructure choices and failure handling
- **Section 7:** Delivery timeline and risk register

**Three decisions require named humans before production, not placeholder text.** Those decisions are identified in the sections where they arise, with a specific pre-production gate: the system does not proceed to production until each decision is recorded with a real name and date. The mechanism enforcing this gate is a checklist in the deployment runbook that blocks the production deployment step. If a checkpoint is missed, Section 7 specifies the default conservative action rather than leaving it unresolved.

**What this document does not claim:**

- FCM rate limits are not knowable in advance with contractual precision. The spike analysis uses a planning assumption and quantifies how wrong that assumption can be before the architecture fails. The "required pre-production action" has been reframed: it is a load test that bounds the uncertainty, not a confirmation that eliminates it.
- The 20–40 minute worst-case DM delay under coincident failure is derived from arithmetic that is shown step by step, including the dependency on when the spike and slow-query event end relative to each other.
- The bloom filter deduplication approach has been replaced with an explicit delivered-ID set with a specified false-positive rate of zero for the mechanism used, at the cost of bounded memory. The tradeoff is stated.

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

**Month-1 checkpoint — missed checkpoint default:** If month-1 traffic data is not reviewed by day 35, the engineering lead defaults to provisioning for the 50% DAU/MAU scenario (100M/day) until the review occurs. This is conservative and costs money; the incentive is to do the review. This default is recorded in the runbook before production launch, and it applies regardless of who is available.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record and queues a push notification. The volume model accounts for worst-case write load; suppression of push when a user is connected via WebSocket is an optimization at the notification router.

**A viral spike will drive push and in-app saturation simultaneously**, because they are triggered by the same upstream events. The traffic response matrix in Section 1.3 accounts for this correlated failure mode explicitly.

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

Decisions are pre-specified to avoid reactive calls made under pressure. Because workers are specialized by channel type (Section 3), the matrix names the specific worker type to provision at each threshold.

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook. The >80M/day architectural response is reviewed by the engineering lead. If the engineering lead is unavailable, the backup makes the decision. Both names are filled in before production; placeholder text is not acceptable and blocks the deployment checklist.

**Identifying which worker type is saturated:** Each worker type emits a `queue_depth` metric tagged by channel and priority. Push saturation shows rising `queue_depth{channel=push}`. The most likely correlated failure is push + in-app saturation simultaneously (same upstream events), not push + email. The matrix handles this case:

| Measured daily volume | Classification | Response | Confirmation metric |
|----------------------|----------------|----------|-------------------|
| < 7.5M/day | Well below plan | Scale down push worker instances | Queue depth < 1K sustained |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s |
| 45M–80M/day | Moderately above plan | Check `queue_depth{channel=push}` and `queue_depth{channel=inapp}` first — these will co-saturate. Provision push workers + in-app write capacity. If email queue also rising, add email workers. Increase Redis instance size same day. | Queue depth returning to baseline within 30 min |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Engineering lead + backup make go/no-go at 3-week checkpoint |

**On dashboard reliability during incidents:** The per-channel queue depth dashboard may be slow or stale during the same Redis pressure event causing the alert. The runbook specifies a fallback: if the dashboard is unresponsive for more than 2 minutes, the on-call engineer queries Redis directly via CLI (`LLEN queue:push:p1`, `LLEN queue:inapp:p1`) to determine which queues are saturated. This CLI command is included verbatim in the runbook so the engineer does not need to reason from first principles at 3 AM.

**Manual response timing — honest estimate under degraded conditions:**

The following estimates apply under the conditions stated.

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
- Dashboard unresponsive; switches to CLI fallback per runbook: ~3 minutes (finding the command + executing)
- Executes scaling command: ~2 minutes
- Instance boot + confirmation via CLI: ~3 minutes
- **Total: ~10–15 minutes**

*Manual, no runbook, 3 AM (first 30 days before runbook is finalized):*
- **Total: 20–30 minutes** — this is the risk window before runbook completion, which is a month-1 deliverable.

The runbook is a month-1 deliverable with a specific completion date. If it is not complete by day 30, the engineering lead is notified and the system operates under the 20–30 minute response assumption until it is complete.

### 1.4 Viral Spike Analysis

**The FCM rate limit cannot be confirmed in advance.** FCM does not publish per-project rate limits with contractual precision, and FCM support cannot guarantee a specific rate for a production project under viral conditions. Load testing a staging project produces useful signal but not a production guarantee.

The framing of the prior version — "confirm the actual FCM rate limit before production" — implied a level of certainty that is not achievable. The correct framing is: **bound the uncertainty through load testing, then make an explicit decision about residual risk.**

**Pre-production action (reframed):** Load test push dispatch against a staging project at 2×, 5×, and 10× planned peak. Record the rate at which 429 responses begin. Use the observed rate as the planning assumption. Accept that the production limit may differ, and use the sensitivity table below to understand what that means.

**Sensitivity table:**

| Assumed FCM limit | Binding constraint at 20× spike | P1 DM behavior |
|---|---|---|
| 500/sec | FCM limit | P1 delays measured in hours |
| 2,000/sec | FCM limit | P1 delays 15–30 min during sustained spike |
| **10,000/sec (plan)** | FCM limit | P1 largely protected; P2/P3 accumulate |
| > 26,000/sec | Worker capacity | Worker capacity becomes binding before FCM |

If load testing produces an observed limit below 2,000/sec, the P1 protection claims in this document are materially wrong, and the priority queue structure must be re-evaluated before launch. This is a pre-production gate, not a suggestion.

**Post-spike recovery — arithmetic shown explicitly:**

Assumptions: 10-minute sustained spike, FCM limit 10,000/sec, 20× demand spike producing ~21,000/sec push demand, workers accumulating exponential backoff to a ceiling of ~32 seconds.

Accumulation during spike:
- FCM can dispatch: 10,000/sec
- Demand: ~21,000/sec
- Net accumulation: ~11,000/sec
- Over 10 minutes: 11,000 × 600 = **6,600,000 messages queued**

The drain timeline depends on when the spike ends relative to when the slow-query event (if any) ends. These are independent events. Three scenarios:

| Scenario | Spike duration | Slow-query duration | Messages queued at drain start | Net drain rate | Drain time | Total delay |
|---|---|---|---|---|---|---|
| Spike only, no DB issue | 10 min | 0 | 6.6M | ~10,000/sec after backoff ramp | ~11 min | ~21 min |
| Spike + DB issue, DB recovers first | 10 min | 8 min | 6.6M | Full rate after backoff ramp | ~11 min | ~21 min |
| Spike + DB issue, co-terminus | 10 min | 10 min | 6.6M | Full rate after backoff ramp | ~11 min | ~21 min |
| Spike ends, DB issue persists 20 min more | 10 min | 30 min | 6.6M + continued accumulation | Partial until DB recovers | **40–60 min** | **50–70 min** |

The worst case is not the spike — it is a DB slow-query event that outlasts the spike and continues to constrain drain rate. The 20–40 minute figure from the prior version understated this scenario. The corrected worst case, where a DB issue persists 20 minutes after the spike ends, is **50–70 minutes of P1 DM delay**.

**This figure requires a real decision before production.** A 50–70 minute worst-case DM delivery delay under a compounded failure is a product decision. The decision to accept this risk must be made by the product lead and engineering lead, recorded with names and date, before production launch. If that delay is unacceptable, the mitigation is full payload storage in Redis (eliminating the DB dependency on the hot path), at the cost of ~500MB–1GB additional Redis memory at 500K queue depth and increased Redis failure impact.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload in Redis |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes | No |
| Memory at 500K depth | ~100MB | ~500MB–1GB |
| Primary failure mode | DB unavailability delays delivery | Redis memory is the constraint |
| Compounded failure risk | Spike + DB issue: 50–70 min worst case | Spike alone: Redis memory exhaustion |

The decision to use ID-based storage must be made with the worst-case figure above on the table. If the product lead and engineering lead accept the 50–70 minute worst case, ID-based is correct. If they do not, full payload in Redis is the alternative and that decision changes the infrastructure sizing.

**Processing Sorted Set — crash recovery:**

When a worker dequeues a notification ID from the priority queue, it immediately writes the ID to a `processing:{worker_id}` Sorted Set scored by the dequeue timestamp. On successful dispatch, the worker removes the ID. On crash, the ID remains.

A recovery process (a single goroutine in a designated worker instance, not a separate service) scans all `processing:{worker_id}` sets every 60 seconds. Any ID with a score older than `max_dispatch_time + 30 seconds` (90 seconds default) is re-enqueued at its original priority.

This produces at-least-once delivery semantics. Deduplication is handled in Section 2.2.

**PostgreSQL connection pool — corrected arithmetic:**

Under normal conditions at 1,575/sec peak with 100 connections and 2–5ms query latency, pool throughput is approximately 20,000–50,000 queries/sec — well above demand.

Pool exhaustion risk: a viral spike (~21,000/sec demand) coincides with a slow-query event increasing per-query latency to 100ms.

At 100ms per query and 100 connections, pool throughput drops to 1,000 queries/sec. Net accumulation: 21,000 − 1,000 = 20,000 messages/sec. Over 10 minutes: 12,000,000 messages queued.

This is materially worse than the accumulation from FCM throttling alone, because the DB constraint affects all channels, not just push. This is the scenario that produces the 50–70 minute worst case in Section 1.4.

**Mitigations, in priority order:**

1. **Read replica for payload fetch** (~2 days engineering, month 2): Routes payload fetches to a replica, requiring the slow-query event to affect both primary and replica simultaneously — a materially lower-probability condition. This is the highest-leverage mitigation and should be implemented before month 2 traffic review.

2. **Payload caching in Redis** (5-minute TTL, ~1 day engineering): Estimated 60–80% hit rate for recently enqueued messages during a spike. Reduces PostgreSQL fetch rate proportionally.

3. **Pool size increase via PgBouncer** (operational, ~2 hours): Increasing the pool to 300 connections provides 3× throughput headroom. Triggered by queue depth alert. PostgreSQL supports approximately 500 simultaneous connections before connection overhead degrades throughput; 300 is a safe ceiling.

4. **Full payload in Redis** (architectural, ~1 week engineering): Eliminates the DB dependency entirely. Accept only if the 50–70 minute worst case is rejected by the product lead.

### 2.2 Deduplication — Delivered-ID Set, Not Bloom Filter

The prior version specified a "delivered-ID bloom filter" for deduplication. Bloom filters have false positive rates: they will occasionally report that a message has been delivered when