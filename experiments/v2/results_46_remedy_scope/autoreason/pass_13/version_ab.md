# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket with correct fleet-scale behavior: the refill rate represents a fleet-allocable share, and the bucket check and consumption execute atomically in a single Lua script.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** PostgreSQL pool exhaustion risk is quantified against the delivery SLA with concrete bounds on worst-case delay, not treated as a qualitative footnote.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. Capacity shift timing is specified for automated, rehearsed manual, and unrehearsed manual paths.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity. Post-spike drain timelines account for client-side backoff state at spike end and are expressed as ranges, not point estimates.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated. Where assumptions compound, the sensitivity is quantified.

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

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

### 1.2 Traffic Response Matrix

The matrix specifies responses at volume thresholds. Decisions are pre-specified to avoid reactive calls made under pressure at 3 AM.

**Named decision owner:** The engineering lead (designated before month 1, with a named backup for unavailability) reviews the month-1 traffic data and makes the architectural response decision for the >80M/day bands. This requires sign-off from the engineering lead and one other senior engineer. Both names are recorded in the runbook before the system goes to production.

| Measured daily volume | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|----------------------|----------------|----------|--------------------|-----------------------------|
| < 7.5M/day | Well below plan | Scale down worker instances | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Provision additional worker instances; increase Redis instance size same day | Queue depth returning to baseline within 30 min | Escalate to engineering lead; consider shard namespace |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + backup make go/no-go at 3-week checkpoint |

The 80M/day threshold is the point at which infrastructure changes become necessary without code changes. Pre-specifying the response prevents architecture decisions from being made reactively.

### 1.3 Channel Split and Volume Accounting

**Accounting correction:** Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record (for when the user returns) and queues a push notification (for immediate delivery). The volume model accounts for worst-case; the suppression logic that reduces push volume when a user is actively connected via WebSocket is an optimization implemented at the notification router, not an assumption baked into the volume model.

| Channel | Share of dispatch | Daily dispatch volume | Peak dispatch demand |
|---------|------------------|----------------------|---------------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

In-app write volume is calculated at full DAU rate. The active-user correction (~63/sec) applies only to WebSocket push delivery to currently-connected users, which is a separate path from the notification store write. FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

**Worker specialization and capacity shifting:**

Workers are specialized binaries per channel type. A push worker contains FCM and APNs dispatch logic and credentials. An email worker contains SMTP client logic and SendGrid credentials. They share no dispatch code at runtime.

The alternative — a single worker binary parameterized by queue prefix at startup — would require all credentials in every worker's environment and would couple the deployment lifecycle of unrelated channel types. The cost of specialization is that scaling a channel requires deploying instances of the correct binary type.

**Capacity shift timing under this model:**

- **Automated trigger (queue depth threshold → auto-scaling rule):** 2–3 minutes
- **Manual, runbook available, on-call engineer present:** ~8 minutes
- **Manual, unrehearsed, 3 AM:** 20–30 minutes

Auto-scaling rules per worker type are implemented in month 2. The manual figures apply for the first 60 days of production.

### 1.4 Viral Spike Analysis — Corrected Recovery Timeline

**The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity.** Worker capacity (~26,000/sec, derived in Section 3) is not the relevant ceiling. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike against the 3× peak figure, FCM demand reaches ~10,500/sec — near or above the FCM ceiling.

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window. P2 and P3 messages accumulate in queue and drain after the spike subsides.

**Corrected post-spike recovery timeline:**

During a sustained spike, workers accumulate backoff state. FCM's documented backoff behavior under sustained 429 responses reaches a ceiling of approximately 32 seconds between retry attempts (5 doublings from a 1-second base). Workers that have reached the backoff ceiling are not immediately dispatching at full rate when the spike ends.

- **0–32 seconds post-spike:** Workers begin receiving 200 responses but are mid-backoff. Effective dispatch rate: ~20–40% of capacity.
- **32–90 seconds post-spike:** Workers reset backoff. Effective dispatch rate ramps to ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity. Queue drains at net excess rate.

At 2.1M messages queued during a 10-minute spike and a 90-second ramp-up before full drain rate, the corrected drain estimate is **5–8 minutes**, not 4 minutes. The range reflects uncertainty in how many workers reached maximum backoff depth versus shallower states.

**Operational implication:** The 5–8 minute figure applies to P2/P3 only. P1 messages (DMs, mentions) drain ahead of the P2/P3 backlog because the P1 retry path is not subject to P2/P3 deferral.

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

There are two distinct failure modes, and they require different responses.

**Transient unavailability (crash, failover, restart):** Workers detect fetch failure, pause dequeue, and retry with exponential backoff. Messages are not lost; delivery is delayed. If unavailability exceeds 30 seconds, workers pause dequeue entirely rather than accumulate failed fetch attempts. This is recoverable and bounded.

**Connection pool exhaustion — the scenario that threatens the SLA:**

At 1,575/sec peak throughput with 100 connections and 2–5ms query latency, the pool can sustain approximately 20,000–50,000 queries/sec — well above peak demand under normal conditions. Pool exhaustion becomes a risk when a viral spike (10–20× baseline, ~10,500–21,000/sec demand) coincides with a slow query event (index bloat, autovacuum, lock contention) that increases per-query latency to 50–100ms.

At 100ms per query and 100 connections, pool throughput drops to 1,000 queries/sec. At 10,500/sec demand, workers queue for pool connections with a 5-second acquire timeout. The effective dispatch rate for all priorities drops to approximately 1,000/sec until the condition resolves.

**Quantified worst case:**
- **P0 impact:** At 1,000/sec effective throughput with 500 P0 messages queued, worst-case dispatch delay is 0.5 seconds. P0 TTL is 1 hour; pool exhaustion does not threaten P0 delivery unless the slow query condition persists for the full TTL window.
- **P1 impact:** More significant. At 10,500/sec demand against 1,000/sec throughput, if the condition persists for 10 minutes, P1 queue depth reaches approximately 570,000 messages. Drain time after condition resolves: approximately 6 minutes at full throughput. Total P1 delay for messages queued mid-event: up to 16 minutes. A 16-minute DM delivery delay is a visible user experience failure, though no messages are lost.

**Mitigations, in priority order:**

1. **Read replica for payload fetch** (highest leverage): Payload fetches are reads; routing them to a read replica removes them from the primary write path and effectively doubles pool throughput. Engineering cost: approximately 2 days in month 2.

2. **Payload caching in Redis** (5-minute TTL): Hit rate for recently enqueued messages during a spike is high — estimated 60–80% reduction in PostgreSQL fetch rate during spike conditions. Engineering cost: approximately 1 day.

3. **Pool size increase under load**: PostgreSQL supports up to ~500 simultaneous connections on a standard instance before connection overhead degrades throughput. Increasing the pool to 300 under viral spike conditions via PgBouncer provides 3× throughput headroom. Triggered by queue depth alert.

**Planning decision:** Implement read replica routing and payload caching in month 2. Accept the unmitigated risk for the first 60 days. If a viral spike occurs in month 1, the worst case is a 16-minute DM delay, not message loss.

**If 16-minute DM delay under worst-case coincident failure is unacceptable, full payload storage in Redis is the correct architectural choice.** The tradeoff is real and the decision belongs to the team.

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

The sweep process runs every 60 seconds per queue and holds a distributed lock so only one instance runs at a time. The sweep measures its own execution time and handles overflow explicitly:

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
            lock.extend(120)  # Extend lock if slow but not overflowing

        if elapsed > 90:
            metrics.increment("sweep.overflow", tags={"queue": queue_key})
            # Terminate and release; next cycle begins immediately
            return

    except Exception as e:
        metrics.increment("sweep.error", tags={"queue": queue_key, "error": str(e)})
        raise
    finally:
        lock.release()
```

The lock TTL (120 seconds, extended on slow sweeps) closes the gap that would allow a second instance to acquire the lock before the first finishes. If a sweep exceeds 120 seconds and a second instance acquires the lock, the resulting concurrent `ZREMRANGEBYSCORE` calls on the same range are idempotent — removing already-removed members is a no-op in Redis. Concurrent sweep execution wastes CPU but does not corrupt queue state. Two consecutive `sweep.overflow` events trigger a manual review per the operations runbook.

**Worker-side backstop:** Before dispatching a dequeued message, the worker checks the message's enqueue timestamp against the TTL. If expired, the worker discards without dispatch and emits a `ttl_miss` metric. This catches messages that entered the processing Sorted Set before the sweep ran.

**The starvation problem and its honest limits:**

The token bucket below provides a guaranteed minimum service rate for P2 and P3. This guarantee has a failure mode: if P1 load is so sustained that the P2 queue grows faster than the 200/sec minimum drain rate, P2 messages will expire before delivery.

At planning volume, P1 peak demand is approximately 218/sec. Worker capacity for push is ~4,000/sec. P1 saturation would require 18× the planning P1 volume — either a viral event (transient, handled by the spike analysis) or a fundamental misclassification of notification types.

**If P1 saturation is a sustained normal condition — meaning the app has heavy DM volume as a core use case — the priority classification is wrong.** DMs should not compete with comments for the same worker pool. The correct fix is a dedicated worker pool for DMs, not token bucket tuning. This is a product decision to be made before month 1.

In the extreme case where P2 queue depth reaches the TTL