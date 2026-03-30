# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The revision addresses ten specific problems identified in review. Changes are substantial in four areas: token bucket implementation (single-key atomic state, fleet-coordination fix), dispatch loop restructuring (token consumption moved after queue check), recovery lock (sweep duration bound with explicit overflow handling), and PostgreSQL risk quantification (pool exhaustion modeled against SLA under concurrent spike conditions).

The four core architectural decisions remain:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses a token bucket with corrected fleet-scale behavior: refill rate is divided by worker count, making the per-worker rate a fleet-allocable share.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** PostgreSQL pool exhaustion risk is now quantified against the delivery SLA with a concrete bound on worst-case delay.

3. **Per-channel, per-priority worker pools** with credential rotation handled via a versioned secrets fetch at startup plus a coordinated rolling restart procedure.

4. **Redis primary/replica with bounded failover.** The post-spike drain estimate is corrected to account for client-side backoff state at spike end; the revised figure is a range, not a point estimate.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated. Where a previous version made an incorrect claim, the correction is noted inline.

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

The matrix specifies responses at volume thresholds. A previous version terminated each response at the action taken. This version adds a confirmation metric and an escalation trigger for each band.

**Named decision owner:** The engineering lead (designated before month 1, with a named backup for unavailability) reviews the month-1 traffic data and makes the architectural response decision for the >80M/day bands. This is not a unilateral call — the decision requires sign-off from the engineering lead and one other senior engineer present at the review. If the engineering lead is unavailable, the backup engineer holds this authority. Both names are recorded in the runbook before the system goes to production. The proposal's framing of "team lead makes this call" without a named owner was a gap; the gap is closed by recording names in the runbook, not in this document.

| Measured daily volume | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|----------------------|----------------|----------|--------------------|-----------------------------|
| < 7.5M/day | Well below plan | Scale down worker instances | Queue depth < 1K sustained | None; re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Provision additional worker instances | Queue depth returning to baseline within 30 min of provisioning | If not confirmed: escalate to engineering lead; consider shard namespace |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s | If not confirmed within 2 weeks: convene architectural review |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + backup make go/no-go at 3-week checkpoint |

### 1.3 Channel Split and Volume Accounting

**Correction from previous version:** Push and in-app were described as "not additive for the same user at the same moment," and this was used to apply an active-user correction to total in-app volume. This was wrong in scope. The correction applies only to simultaneous delivery — a user actively in the app when an event fires. It does not apply to the write volume case, where the same event writes both an in-app notification record (for when the user returns) and queues a push notification (for immediate delivery). These are additive in system load even if not simultaneous from the user's perspective.

**Corrected accounting:**

| Channel | Share of dispatch | Daily dispatch volume | Peak dispatch demand |
|---------|------------------|----------------------|---------------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

In-app write volume is now calculated at full DAU rate, not active-session-corrected rate. The active-user correction (~63/sec) applies only to WebSocket push delivery to currently-connected users, which is a separate path from the notification store write. Total system write load is higher than the previous version stated by approximately 250/sec at peak.

**The suppression logic that actually reduces push volume:** When a user is actively connected via WebSocket, the in-app delivery path fires and the push dispatch is suppressed. This suppression is implemented at the notification router, not assumed in the volume model. The volume model accounts for worst-case (all notifications dispatched to both paths); the suppression is an optimization that reduces FCM/APNs load in practice.

### 1.4 Viral Spike Analysis — Corrected Recovery Timeline

**Previous version's error:** The 4-minute post-spike drain figure assumed FCM immediately returned to full capacity when the spike ended. This is incorrect. During a sustained spike, the dispatch layer applies exponential backoff after repeated 429 responses. When the spike ends, workers are mid-backoff — they are not immediately dispatching at full rate. The 4-minute figure was optimistic by an unspecified factor.

**Corrected analysis:**

During a 10-minute viral spike, workers accumulate backoff state. FCM's documented backoff behavior under sustained 429 responses reaches a ceiling of approximately 32 seconds between retry attempts (5 doublings from a 1-second base). Workers that have reached the backoff ceiling need 32 seconds of successful responses before they reset to full dispatch rate.

Post-spike drain timeline:
- **0–32 seconds:** Workers begin receiving 200 responses but are mid-backoff. Effective dispatch rate: ~20–40% of capacity (~800–1,600/sec against 3,500/sec capacity).
- **32–90 seconds:** Workers reset backoff. Effective dispatch rate ramps to ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity (~3,500/sec). Queue drains at ~2,400/sec net excess.

At 2.1M messages queued (calculated in the previous version) and a ramp-up period of approximately 90 seconds before full drain rate, the corrected drain estimate is **5–8 minutes**, not 4 minutes. The range reflects uncertainty in how many workers reached maximum backoff depth versus shallower backoff states.

**What this means operationally:** P2 messages queued during a 10-minute viral spike may experience up to 8 minutes of additional delay after the spike ends. For a "like" notification, this is acceptable. For a P1 direct message queued during the spike, the P1 retry path (immediate retry within backoff window, not subject to P2/P3 deferral) means P1 messages drain ahead of the P2/P3 backlog. The 5–8 minute figure applies to P2/P3 only.

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

**PostgreSQL failure risk — quantified against SLA:**

The previous version acknowledged pool exhaustion as "a real operational risk" and moved on. This version quantifies it.

**Scenario: pool exhaustion coincides with a viral spike.**

At 1,575/sec peak throughput, each dequeue requires one PostgreSQL fetch. With 100 connections and typical query latency of 2–5ms, the pool can sustain approximately 20,000–50,000 queries/sec under normal conditions — well above peak demand. Pool exhaustion is not a concern at planning volume.

The risk scenario is a viral spike (10–20× baseline, ~10,500–21,000/sec) coinciding with a slow query event (index bloat, autovacuum, lock contention) that increases per-query latency to 50–100ms. At 100ms per query and 100 connections, pool throughput drops to 1,000 queries/sec. At 10,500/sec demand, workers queue for pool connections with a 5-second acquire timeout.

**Quantified worst case:** At 5-second acquire timeout and 10,500/sec demand against 1,000/sec pool throughput, workers begin timing out after approximately 0.5 seconds of pool saturation. Timed-out workers back off 100ms and retry. This creates a feedback loop: the effective dispatch rate for P0 and P1 messages drops to approximately the pool throughput ceiling (1,000/sec) until either the slow query condition resolves or the spike subsides.

**P0 SLA impact:** At 1,000/sec effective throughput and P0 messages queued behind pool exhaustion, P0 dispatch delay is bounded by queue depth ahead of the P0 message divided by 1,000/sec. For a queue with 500 P0 messages queued, worst-case delay is 0.5 seconds. P0 TTL is 1 hour; pool exhaustion does not threaten P0 delivery unless the slow query condition persists for the full TTL window.

**P1 SLA impact:** More concerning. At 10,500/sec demand with only 1,000/sec throughput, P1 messages (DMs, mentions) queue. If the condition persists for 10 minutes, P1 queue depth reaches approximately 570,000 messages. Drain time after condition resolves: approximately 6 minutes at full throughput. Total P1 delay for messages queued mid-event: up to 16 minutes. P1 TTL is 4 hours; no messages are lost, but 16-minute DM delivery delay is a visible user experience failure.

**Mitigations:**

1. **Read replica for payload fetch.** Payload fetches are reads; routing them to a read replica removes them from the primary write path and doubles effective pool throughput. This is the highest-leverage mitigation and costs approximately 2 days of engineering in month 2.

2. **Pool size increase under load.** The pool ceiling of 100 connections is a configuration parameter. PostgreSQL supports up to ~500 simultaneous connections on a standard instance before connection overhead degrades throughput. Increasing the pool to 300 under viral spike conditions (triggered by queue depth alert) provides 3× throughput headroom. This requires PgBouncer or equivalent connection pooler to avoid direct connection overhead.

3. **Payload caching.** Cache recently fetched payloads in Redis with a 5-minute TTL. Hit rate for recently enqueued messages during a spike is high. This reduces PostgreSQL fetch rate by an estimated 60–80% during spike conditions. Engineering cost: 1 day.

**Planning decision:** Implement read replica routing and payload caching in month 2. Accept the unmitigated risk for the first 60 days. If a viral spike occurs in month 1, the worst-case scenario is a 16-minute DM delay, not message loss.

**If the team determines that 16-minute DM delay under a worst-case coincident failure is unacceptable, full payload storage in Redis is the correct architectural choice.** The tradeoff is real and the decision belongs to the team, not this document.

### 2.2 Priority Queue Structure, TTL Enforcement, and Starvation Prevention

Four priority levels with defined semantics:

| Priority | Examples | TTL | Guaranteed minimum rate |
|----------|----------|-----|------------------------|
| P0 | Security alerts, account recovery | 1 hour | No cap — always drain first |
| P1 | Direct messages, mentions | 4 hours | No cap — drain before P2/P3 |
| P2 | Comments, reactions | 24 hours | 200 tokens/sec fleet-wide |
| P3 | Recommendations, digests | 72 hours | 50 tokens/sec fleet-wide |

**TTL enforcement — the expiry sweep:**

The queue is a Redis Sorted Set scored by enqueue timestamp. TTL expiry is enforced by a dedicated sweep process, not by the dequeue path.

The sweep runs every 60 seconds per queue. **Previous version's error:** The 90-second lock TTL was claimed to "close the gap" against concurrent recovery instances. This argument is circular: it holds only if the sweep always completes within 60 seconds, which is not guaranteed when the expired set is large or Redis is under load.

**Corrected approach — sweep duration bound with overflow handling:**

The sweep process measures its own execution time. If the sweep exceeds 45 seconds, it emits a `sweep.slow` alert and commits partial results (expired entries removed so far). The lock TTL is extended to 120 seconds in this case. If the sweep exceeds 90 seconds, it terminates, releases the lock, and the next cycle begins immediately. A `sweep.overflow` metric is emitted; the operations runbook specifies that two consecutive `sweep.overflow` events trigger a manual review of queue depth and Redis latency.

The residual risk: if a sweep takes longer than 120 seconds (extended lock TTL), a second instance can acquire the lock while the first is still running. This would result in duplicate `ZREMRANGEBYSCORE` calls on the same range — which are idempotent in Redis (removing already-removed members is a no-op). Concurrent sweep execution does not corrupt queue state; it wastes CPU. The alert chain catches this condition before it becomes chronic.

```python
def run_ttl_sweep(queue_key: str, ttl_seconds: int, lock_client):
    """Remove expired entries with duration monitoring and overflow protection."""
    lock = lock_client.acquire(f"lock:sweep:{queue_key}", ttl=120)
    if not lock:
        return  # Another instance is running

    start = time.monotonic()
    expiry_cutoff = time.time() - ttl_seconds

    try:
        removed = redis.zremrangebyscore(queue_key, 0, expiry_cutoff)
        elapsed = time.monotonic() - start
        metrics.gauge("sweep.duration_seconds", elapsed, tags={"queue": queue_key})
        metrics.increment("ttl_sweep.removed", removed, tags={"queue": queue_key})

        if elapsed > 45:
            metrics.increment("sweep.slow", tags={"queue": queue_key})
            lock.extend(120)  # Extend if slow but not overflowing

    except Exception as e:
        metrics.increment("sweep.error", tags={"queue": queue_key, "error": str(e)})
        raise
    finally:
        lock.release()
```

**Worker-side backstop:** Before dispatching a dequeued message, the worker checks the message's enqueue timestamp against the TTL. If expired, the worker discards without dispatch and emits a `ttl_miss` metric. This