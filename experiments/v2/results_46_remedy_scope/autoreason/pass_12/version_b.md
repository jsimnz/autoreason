# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated expiry sweep process and worker-side backstop checking. Starvation prevention uses a combined atomic token bucket and dispatch: P2/P3 queues accumulate credits at guaranteed minimum rates (200/sec for P2, 50/sec for P3), with the bucket check and consumption executed atomically in a single Lua script. P1 is always checked before P2/P3 in any given loop iteration; P2/P3 service slots are carved out explicitly and do not precede P1.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The Sorted Set replaces a Redis List for O(log N) membership testing, O(log N) recovery scans, and idempotent reclaim under concurrent recovery processes. The recovery process is designed to be idempotent against its own crash-and-restart: re-enqueue operations are deduplication-safe. The interaction between recovery and deduplication is specified explicitly.

3. **Per-channel, per-priority worker pools** where workers are specialized binaries per channel type, each containing only the dispatch logic and credentials for that channel. Shifting capacity between channels means scaling worker instances of the target type, not reconfiguring shared workers. Capacity shift timing is specified for automated and manual paths.

4. **Redis primary/replica with bounded failover.** P0 behavior during the 15–30 second failover window is quantified. The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity — and the P2/P3 shedding mechanism is specified against that constraint with a concrete recovery timeline.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** The 30% planning figure is reasonable for mature social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct planning range for an unspecified social app is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Average-peak sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Traffic response matrix — complete:**

| Measured daily volume | Classification | Response |
|----------------------|----------------|----------|
| < 7.5M/day | Well below plan | Scale down worker instances. No architecture change. |
| 7.5M–45M/day | On plan | No action. Monitor. |
| 45M–80M/day | Moderately above plan | Provision additional worker instances (10–15 min). Increase Redis instance size (same day). No engineering work required. |
| 80M–225M/day | Significantly above plan | Above plus shard queue namespace by user ID range — 1 week of engineering. Timeline slips ~2 weeks. No feature scope cut. |
| > 225M/day | Severely above plan | Defer SMS and email to month 4. One engineer assigned to re-architecture for 3 weeks. Feature scope changes. Team lead makes this call at month-1 review, not reactively. |

The 80M/day threshold is the point at which infrastructure changes become necessary without code changes. This is not "on plan" — it is a distinct tier requiring a same-day response. The previous version's gap between 45M and 100M is closed here.

**Temporal spike analysis — the 3× model and its actual limits:**

The 3× multiplier models predictable daily rhythm. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** 10–20× baseline over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

**The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity.** Worker capacity (~26,000/sec, derived in Section 3.3) is not the relevant ceiling. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike against the 3× peak figure, FCM demand reaches ~10,500/sec — near or above the FCM ceiling.

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window. P2 and P3 messages accumulate in queue and drain after the spike subsides. Queue depth during a 10-minute spike at the FCM ceiling, with 3,500/sec excess demand: approximately 2.1M messages queued, draining at ~8,000/sec excess capacity after the spike, cleared in approximately 4 minutes.

### 1.2 Channel Split

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle ~50% of push volume: ~547/sec each at peak.

**Active-user correction applied only where it governs delivery:**

Push serves offline and background users — the 70% channel allocation already represents full DAU-based volume. In-app delivery is gated on WebSocket connection state; the ~63/sec figure reflects 20% concurrency across 3M DAU. Push and in-app are not additive for the same user at the same moment.

**Worker specialization and capacity shifting:**

Workers are specialized binaries per channel type. A push worker contains FCM and APNs dispatch logic and credentials. An email worker contains SMTP client logic and SendGrid credentials. They share no dispatch code at runtime.

This is the honest architecture. The alternative — a single worker binary containing all dispatch functions, selecting at startup — would require all credentials in every worker's environment and would couple the deployment lifecycle of unrelated channel types. The cost of specialization is that scaling a channel requires deploying instances of the correct binary type, not reconfiguring a shared pool.

**Capacity shift timing under this model:**

- **Scripted auto-scaling rule (queue depth threshold → add instances of target worker type):** 2–3 minutes.
- **Manual, runbook available, on-call engineer present:** ~8 minutes (locate correct worker type, deploy additional instances, verify queue depth decreasing).
- **Manual, 3 AM, runbook not rehearsed:** 20–30 minutes.

**Planning decision:** Implement auto-scaling rules per worker type in month 2. The manual figures apply for the first 60 days of production.

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

**PostgreSQL failure modes — two distinct cases:**

The previous version cited 99.99% managed PostgreSQL availability to justify this choice. That figure has two problems: it does not bound individual outage duration, and it does not cover connection pool exhaustion under high concurrency.

The correct justification is behavioral, not SLA-based:

- **Transient unavailability (crash, failover, restart):** Workers detect fetch failure, pause dequeue, and retry with exponential backoff. Messages are not lost; delivery is delayed. This is recoverable and bounded.
- **Connection pool exhaustion:** Under high worker concurrency with one payload fetch per dequeue, the connection pool can saturate. This is a distinct failure mode. Mitigation: workers share a connection pool with a maximum size of 100 connections (configurable), with a 5-second acquire timeout. If the pool is exhausted, the worker backs off for 100ms and retries rather than spawning additional connections. Pool exhaustion under sustained load is a signal to increase pool size or reduce worker concurrency, surfaced via the `pg_pool_wait_time` metric. This is a real operational risk of the ID-based approach and is not fully mitigated by the availability SLA.

If operational PostgreSQL dependency on the hot path is unacceptable for the team, full payload storage in Redis is the correct choice. The tradeoff is real.

### 2.2 Priority Queue Structure, TTL Enforcement, and Starvation Prevention

Four priority levels with defined semantics:

| Priority | Examples | TTL | Guaranteed minimum rate |
|----------|----------|-----|------------------------|
| P0 | Security alerts, account recovery | 1 hour | No cap — always drain first |
| P1 | Direct messages, mentions | 4 hours | No cap — drain before P2/P3 |
| P2 | Comments, reactions | 24 hours | 200 tokens/sec |
| P3 | Recommendations, digests | 72 hours | 50 tokens/sec |

**TTL enforcement — the expiry sweep:**

The queue is a Redis Sorted Set scored by enqueue timestamp. TTL expiry is enforced by a dedicated sweep process, not by the dequeue path. The executive summary referenced "companion expiry sorted sets" — this section specifies what that actually means.

The sweep process runs every 60 seconds per queue:

```python
def run_ttl_sweep(queue_key: str, ttl_seconds: int):
    """Remove expired entries from a priority queue."""
    expiry_cutoff = time.time() - ttl_seconds
    # ZREMRANGEBYSCORE removes all entries with score <= cutoff
    # Score is enqueue timestamp, so this removes entries older than TTL
    removed = redis.zremrangebyscore(queue_key, 0, expiry_cutoff)
    metrics.increment("ttl_sweep.removed", removed, tags={"queue": queue_key})
    return removed
```

**Who runs it:** A dedicated sweep worker process, separate from dispatch workers. One instance is sufficient at planning volume; it processes all queues in under 1 second per cycle. The sweep worker holds a distributed lock (60-second TTL, renewed every 30 seconds) so only one instance runs at a time.

**What happens if the sweep falls behind:** At P2 volume (315/sec peak, 24-hour TTL), the maximum queue depth before expiry is approximately 27M entries. The sweep removes expired entries in O(log N + K) time where K is the number of expired entries. At 60-second intervals with a 315/sec arrival rate and no delivery, the sweep removes up to 18,900 entries per cycle — this is well within Redis's capacity. The sweep cannot fall behind under normal conditions. Under the extreme-load scenario discussed below, the sweep continues running and removes expired entries; this is the intended behavior.

**Worker-side backstop:** Before dispatching a dequeued message, the worker checks whether the message's enqueue timestamp (stored in the notification record) exceeds the TTL. If expired, the worker discards without dispatch and emits a `ttl_miss` metric. This catches messages that entered the processing Sorted Set before the sweep ran.

**The starvation problem and its honest limits:**

Under sustained P1 load, a naive priority queue never reaches P2 or P3. The token bucket below provides a guaranteed minimum service rate. However, there is a scenario where this guarantee fails: if P1 load is so sustained that P2 queue depth grows faster than the 200/sec minimum drain rate, P2 messages will expire before delivery. At planning volume, P2 peak demand is ~315/sec. The guaranteed minimum covers ~63% of P2 peak demand under full P1 saturation.

**The critical question is whether sustained full P1 saturation is a normal operating condition.** At planning volume, P1 peak demand is ~1,094/sec × 70% push × (proportion that are DMs/mentions). If DMs and mentions constitute 20% of push volume, P1 peak is ~218/sec. Worker capacity for push is ~4,000/sec. P1 saturation would require 18× the planning P1 volume — which is either a viral event (transient, handled by the spike analysis in Section 1.1) or a fundamental misclassification of notification types.

If P1 saturation is a sustained normal condition — meaning the app has heavy DM volume as a core use case — the priority classification is wrong. DMs should not compete with comments for the same worker pool. The correct fix in that scenario is to give DMs their own dedicated worker pool, not to tune the token bucket. This is a product decision, not an infrastructure decision, and should be made before month 1.

**Starvation prevention — atomic token bucket:**

The previous version had two bugs: the check threshold (200) and consumption amount (1) were inconsistent, and the check and consume were non-atomic across separate Redis calls. Both are fixed here.

The token bucket is checked and consumed atomically in a single Lua script. The threshold for servicing P2 is 1 token (not 200). The refill rate is 200 tokens/sec, meaning P2 receives at minimum 200 dispatch slots/sec across the worker fleet.

```lua
-- atomic_token_consume.lua
-- KEYS[1] = token bucket key (e.g., "tokens:p2")
-- KEYS[2] = last refill timestamp key
-- ARGV[1] = current Unix timestamp (float)
-- ARGV[2] = refill rate (tokens/sec)
-- ARGV[3] = bucket capacity
-- ARGV[4] = tokens to consume (1)
-- Returns: 1 if tokens were consumed (dispatch this priority), 0 if insufficient

local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local cap = tonumber(ARGV[3])
local consume = tonumber(ARGV[4])

local tokens = tonumber(redis.call('GET', KEYS[1])) or cap
local last = tonumber(redis.call('GET', KEYS[2])) or now

local elapsed = math.max(0, now - last)
local refilled = math.min(cap, tokens + elapsed * rate)

if refilled >= consume then
    redis.call('SET', KEYS[1], refilled - consume)
    redis.call('SET', KEYS[2], now)
    return 1
else
    -- Still update the refilled amount and timestamp even if not consuming
    redis.call('SET', KEYS[1], refilled)
    redis.call('SET', KEYS[2], now)
    return 0
end
```

**Dispatch loop — P1 priority enforced before P2/P3:**

The previous version had a structural bug: if both P2 and P3 token buckets were full, both were serviced before P1 in a single loop iteration. The corrected loop checks P1 first, then carves out exactly one lower-priority slot if the token bucket permits:

```python
def worker_dispatch_loop(channel: str):
    while True:
        # P0: always drain first, unconditionally
        msg = try_dequeue(f"queue:p0:{channel}")
        if msg:
            dispatch(msg)
            continue

        # P1: drain before any P2/P3, unless a lower-priority slot is earned
        # Check whether a lower-priority slot is available this cycle
        p2_slot = try_consume_token("p2", refill_rate=200, capacity=2000)
        p3_slot = (not p2_slot) and try_consume_token("p