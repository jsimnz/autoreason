# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop checking. Starvation prevention uses an atomic token bucket: P2/P3 queues accumulate credits at guaranteed minimum rates (200/sec for P2, 50/sec for P3), with the bucket check and consumption executed atomically in a single Lua script. P1 is always checked before P2/P3 in any given loop iteration; lower-priority slots are carved out explicitly and do not precede P1.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The Sorted Set replaces a Redis List for O(log N) membership testing, O(log N) recovery scans, and idempotent reclaim under concurrent recovery processes. The recovery lock TTL (90 seconds against a 60-second cycle) closes the gap that allows concurrent recovery instances. Re-enqueue operations are deduplication-safe.

3. **Per-channel, per-priority worker pools** where workers are specialized binaries per channel type. Shifting capacity between channels means scaling instances of the target binary type. Capacity shift timing is specified for automated (2–3 min), rehearsed manual (~8 min), and unrehearsed manual (20–30 min) paths.

4. **Redis primary/replica with bounded failover.** P0 behavior during the 15–30 second failover window is quantified. The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity — the P2/P3 queue accumulation and recovery timeline is specified concretely against that constraint.

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

**Traffic response matrix — pre-specified to avoid reactive decisions under pressure:**

| Measured daily volume | Classification | Response |
|----------------------|----------------|----------|
| < 7.5M/day | Well below plan | Scale down worker instances. No architecture change. |
| 7.5M–45M/day | On plan | No action. Monitor. |
| 45M–80M/day | Moderately above plan | Provision additional worker instances (10–15 min). Increase Redis instance size (same day). No engineering work required. |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering. Timeline slips ~2 weeks. No feature scope cut. |
| > 225M/day | Severely above plan | Defer SMS and email to month 4. One engineer assigned to re-architecture for 3 weeks. Feature scope changes. Team lead makes this call at the month-1 review, not reactively. |

The 80M/day threshold is the point at which infrastructure changes become necessary without code changes. The response is pre-specified because a decision made at 3 AM during a growth spike produces a different architecture than one made deliberately.

**Temporal spike analysis — the 3× model and its actual limits:**

The 3× multiplier models predictable daily rhythm. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** 10–20× baseline over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

**The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity.** Worker capacity (~26,000/sec, derived in Section 3.3) is not the relevant ceiling. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike against the 3× peak figure, FCM demand reaches ~10,500/sec — near or above the FCM ceiling. Worker capacity is irrelevant once the external provider is the bottleneck.

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window. P2 and P3 messages accumulate in queue and drain after the spike subsides. Queue depth during a 10-minute spike at the FCM ceiling, with 3,500/sec excess demand: approximately 2.1M messages queued, draining at ~8,000/sec excess capacity after the spike, cleared in approximately 4 minutes. This is the actual recovery timeline, not a qualitative claim.

### 1.2 Channel Split

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle ~50% of push volume: ~547/sec each at peak.

**Active-user correction applied only where it governs delivery:**

Push serves offline and background users — the 70% channel allocation already represents full DAU-based volume. In-app delivery is gated on WebSocket connection state; the ~63/sec figure reflects 20% concurrency across 3M DAU. Push and in-app are not additive for the same user at the same moment; treating them as additive overstates demand.

**Worker specialization and capacity shifting:**

Workers are specialized binaries per channel type. A push worker contains FCM and APNs dispatch logic and credentials. An email worker contains SMTP client logic and SendGrid credentials. They share no dispatch code at runtime.

This is a deliberate architectural choice. The alternative — a single worker binary parameterized by queue prefix at startup — would require all credentials in every worker's environment and would couple the deployment lifecycle of unrelated channel types. The cost of specialization is that scaling a channel requires deploying instances of the correct binary type, not reconfiguring a shared pool.

**Capacity shift timing under this model:**

- **Automated trigger (queue depth threshold → auto-scaling rule):** 2–3 minutes.
- **Manual, runbook available, on-call engineer present:** ~8 minutes (locate correct worker type, deploy additional instances, verify queue depth decreasing).
- **Manual, 3 AM, runbook not rehearsed:** 20–30 minutes.

**Planning decision:** Implement auto-scaling rules per worker type in month 2. The manual figures apply for the first 60 days of production. The automated figure applies only after the trigger is deployed and tested.

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

- **Transient unavailability (crash, failover, restart):** Workers detect fetch failure, pause dequeue, and retry with exponential backoff. Messages are not lost; delivery is delayed. This is recoverable and bounded. If unavailability exceeds 30 seconds, workers pause dequeue entirely rather than accumulate failed fetch attempts.

- **Connection pool exhaustion:** Under high worker concurrency, the connection pool can saturate independently of database availability. Workers share a pool with a maximum of 100 connections (configurable), with a 5-second acquire timeout. If the pool is exhausted, the worker backs off 100ms and retries rather than spawning additional connections. Pool exhaustion is surfaced via a `pg_pool_wait_time` metric and is a signal to increase pool size or reduce worker concurrency. This is a real operational risk of the ID-based approach that the availability SLA does not address.

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

The queue is a Redis Sorted Set scored by enqueue timestamp. TTL expiry is enforced by a dedicated sweep process, not by the dequeue path.

The sweep process runs every 60 seconds per queue:

```python
def run_ttl_sweep(queue_key: str, ttl_seconds: int):
    """Remove expired entries from a priority queue."""
    expiry_cutoff = time.time() - ttl_seconds
    removed = redis.zremrangebyscore(queue_key, 0, expiry_cutoff)
    metrics.increment("ttl_sweep.removed", removed, tags={"queue": queue_key})
    return removed
```

The sweep worker holds a distributed lock (90-second TTL, renewed every 30 seconds) so only one instance runs at a time. The 90-second lock TTL against a 60-second cycle closes the gap that would allow a second instance to acquire the lock before the first finishes and renews.

**Worker-side backstop:** Before dispatching a dequeued message, the worker checks whether the message's enqueue timestamp exceeds the TTL. If expired, the worker discards without dispatch and emits a `ttl_miss` metric. This catches messages that entered the processing Sorted Set before the sweep ran.

**The starvation problem and its honest limits:**

Under sustained P1 load, a naive priority queue never reaches P2 or P3. The token bucket below provides a guaranteed minimum service rate. However, there is a scenario where this guarantee fails: if P1 load is so sustained that the P2 queue grows faster than the 200/sec minimum drain rate, P2 messages will expire before delivery.

At planning volume, P1 peak demand is approximately 218/sec (DMs and mentions at ~20% of push volume). Worker capacity for push is ~4,000/sec. P1 saturation would require 18× the planning P1 volume — either a viral event (transient, handled by the spike analysis in Section 1.1) or a fundamental misclassification of notification types.

**If P1 saturation is a sustained normal condition — meaning the app has heavy DM volume as a core use case — the priority classification is wrong.** DMs should not compete with comments for the same worker pool. The correct fix is a dedicated worker pool for DMs, not token bucket tuning. This is a product decision to be made before month 1.

In the extreme case where P2 queue depth reaches the TTL ceiling (24 hours × 315/sec ≈ 27M messages), drain time at 200/sec minimum is approximately 37 hours — which exceeds the 24-hour TTL. In this scenario, P2 messages expire before delivery. This is the correct behavior: a "like" notification from 25 hours ago has no value. The TTL is the ultimate starvation backstop.

**Starvation prevention — atomic token bucket:**

The token bucket check and consumption execute atomically in a single Lua script. The threshold for servicing P2 is 1 token (not the bucket capacity). The refill rate is 200 tokens/sec, meaning P2 receives at minimum 200 dispatch slots/sec across the worker fleet.

```lua
-- atomic_token_consume.lua
-- KEYS[1] = token bucket key (e.g., "tokens:p2")
-- KEYS[2] = last refill timestamp key
-- ARGV[1] = current Unix timestamp (float)
-- ARGV[2] = refill rate (tokens/sec)
-- ARGV[3] = bucket capacity
-- ARGV[4] = tokens to consume (1)
-- Returns: 1 if token consumed (dispatch this priority), 0 if insufficient

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
    redis.call('SET', KEYS[1], refilled)
    redis.call('SET', KEYS[2], now)
    return 0
end
```

**Dispatch loop — P1 priority enforced before P2/P3:**

The loop checks P1 before any lower-priority slot is serviced. P2 and P3 slots are carved out explicitly in sequence — a P3 slot is only attempted if no P2 slot is available this cycle.

```python
def worker_dispatch_loop(channel: str):
    while True:
        # P0: always drain first, unconditionally
        msg = try_dequeue(f"queue:p0:{channel}")
        if msg:
            dispatch(msg)
            continue

        # Determine whether a lower-priority slot is earned this cycle
        # P2 is checked before P3; only one lower-priority slot per cycle
        p2_slot = try_consume_token("p2", refill_rate=200, capacity=2000)
        p3_slot = (not p2_slot) and try_consume_token("p3", refill_rate=50, capacity=500)

        # Service one lower-priority message if a slot was earned
        if p2_slot:
            msg = try_dequeue(f"queue:p2:{channel}")
            if msg:
                dispatch(msg)
                continue

        if p3_slot:
            msg = try_dequeue(f"queue:p3:{channel}")
            if msg:
                dispatch(msg)
                continue

        # Default: drain P1
        msg = try_dequeue(f"queue:p1:{channel}")
        if msg:
            dispatch(msg)
            continue

        time.sleep(0.01)  # Empty queue backoff
```

This structure ensures P1 is never bypassed to service P2 or P3. Lower-priority slots are additive to P1 capacity, not competitive with it.

### 2.3 Processing State — Sorted Set, Not a List

**Why not a Redis List:** Three concrete problems make Redis Lists unsuitable for the processing tracker.

- **No O(1) membership test.** Checking membership requires a full `LRANGE` scan — O(N). The acknowledgment path needs to verify message ownership before marking delivery complete.