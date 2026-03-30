# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via companion expiry sorted sets and worker-side backstop checking. Starvation prevention uses a token-bucket mechanism: P2/P3 queues accumulate credits at guaranteed minimum rates (200/sec for P2, 50/sec for P3), so lower-priority messages are delayed but never permanently starved under sustained P1 load.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** Full payload storage is the honest alternative; the tradeoff is stated explicitly. The Sorted Set replaces a Redis List for O(log N) membership testing, O(log N) recovery scans, and idempotent reclaim under concurrent recovery processes. The recovery lock TTL is 90 seconds against a 60-second cycle, closing the gap that would allow concurrent recovery instances.

3. **Per-channel, per-priority worker pools** derived from first-principles throughput benchmarks. Workers are parameterized by queue prefix and dispatch function at startup — shifting capacity between channels is a configuration change and rolling restart, not a code change. Realistic timing for that shift is specified for both automated and manual execution paths.

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

**What "re-plan before month 3" actually means:**

If measured traffic diverges from the 15M–100M range by more than 2× in either direction, a re-plan is triggered. For a 4-engineer team on a 6-month timeline, a re-plan triggered at day 30 with a month-3 deadline consumes roughly one-third of total project duration. The trigger and response are therefore pre-specified to avoid re-planning from scratch under pressure.

- **Traffic too low (< 7.5M/day measured):** No re-plan needed. Scale down worker instances. No architecture change.
- **Traffic 2–5× above plan (100M–225M/day):** (a) Provision additional worker instances — 10–15 minutes on target infrastructure; (b) increase Redis instance size — same day; (c) shard queue namespace by user ID range — 1 week of engineering. No feature scope cut. Timeline slips approximately 2 weeks.
- **Traffic > 5× above plan (> 225M/day):** Defer SMS and email to month 4, concentrate engineering on push and in-app. One engineer assigned to re-architecture for 3 weeks. This is the only scenario that changes feature scope. The team lead makes this call at the month-1 review, not reactively.

**Why pre-specifying the response matters:** A re-plan triggered without a pre-specified response at 3 AM during a growth spike produces a different architecture than one made deliberately. The decision tree above is the re-plan. It is made now, when the team is not under pressure.

**Temporal spike analysis — the 3× model and its actual limits:**

The 3× multiplier models predictable daily rhythm. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** A celebrity post or breaking news can generate 10–20× baseline notification volume over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

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

Push serves offline and background users. The concurrent-user correction does not apply — the 70% channel allocation already represents full DAU-based volume. Applying a second population filter understates demand.

In-app delivery is gated on WebSocket connection state. A notification to an offline user falls back to push or queues for next login. The in-app peak demand figure of ~63/sec reflects 20% concurrency across 3M DAU.

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand.

**Capacity shift procedure — realistic timing:**

Workers are parameterized at startup by queue prefix and dispatch function. Shifting capacity from in-app to push under high load is a configuration change followed by a rolling restart. Realistic timing:

- **Scripted, tested, on-call engineer available:** ~5 minutes for a 5-worker pool.
- **3 AM, runbook not previously rehearsed:** 15–25 minutes. Config must be located, change verified, restart monitored.
- **Automated trigger (queue depth threshold alert → auto-scaling rule):** 2–3 minutes.

**Planning decision:** Implement the automated trigger in month 2. Until then, the on-call runbook is rehearsed in staging monthly. The 5-minute figure applies only after the automated trigger is in place. The 15–25 minute figure is the honest planning number for the first 60 days of production.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | Transient DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path |

The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable. If PostgreSQL unavailability exceeds 30 seconds, workers pause dequeue rather than accumulate failed fetch attempts; messages drain normally once the database recovers.

### 2.2 Priority Queue Structure and Starvation Prevention

Four priority levels with defined semantics:

| Priority | Examples | TTL | Guaranteed minimum rate |
|----------|----------|-----|------------------------|
| P0 | Security alerts, account recovery | 1 hour | No cap — always drain first |
| P1 | Direct messages, mentions | 4 hours | No cap — drain before P2/P3 |
| P2 | Comments, reactions | 24 hours | 200 credits/sec |
| P3 | Recommendations, digests | 72 hours | 50 credits/sec |

**The starvation problem:** Under sustained P1 load, a naive priority queue never reaches P2 or P3. A user receiving high-volume notifications will never see lower-priority notifications delivered.

**Starvation prevention — token bucket per lower-priority queue:**

Each P2 and P3 queue has a token bucket maintained in Redis. Workers check the bucket before skipping a lower-priority message.

```python
def get_available_tokens(priority: str, refill_rate: float, capacity: float) -> float:
    """Atomic token bucket check via Lua."""
    script = """
        local tokens = tonumber(redis.call('GET', KEYS[1])) or ARGV[3]
        local last = tonumber(redis.call('GET', KEYS[2])) or ARGV[1]
        local now = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local cap = tonumber(ARGV[3])
        
        local elapsed = now - last
        local new_tokens = math.min(cap, tokens + elapsed * rate)
        redis.call('SET', KEYS[1], new_tokens)
        redis.call('SET', KEYS[2], now)
        return new_tokens
    """
    return redis.eval(script, 2,
        f"{priority}_tokens", f"{priority}_last_refill",
        time.time(), refill_rate, capacity)

def worker_dispatch_loop(channel: str):
    while True:
        # Always drain P0 first, unconditionally
        msg = dequeue(f"queue:p0:{channel}")
        if msg:
            dispatch(msg); continue
            
        # Check whether P2 or P3 have accumulated enough credits to service
        p2_tokens = get_available_tokens("p2", 200, 2000)
        p3_tokens = get_available_tokens("p3", 50, 500)
        
        if p2_tokens >= 200:
            msg = dequeue(f"queue:p2:{channel}")
            if msg:
                consume_tokens("p2", 1)
                dispatch(msg); continue
        
        if p3_tokens >= 50:
            msg = dequeue(f"queue:p3:{channel}")
            if msg:
                consume_tokens("p3", 1)
                dispatch(msg); continue
        
        # Default: drain P1
        msg = dequeue(f"queue:p1:{channel}")
        if msg:
            dispatch(msg); continue
            
        time.sleep(0.01)  # Empty queue backoff
```

**What this guarantees:** Under sustained P1 load, P2 receives at minimum 200 dispatch slots/sec across the worker fleet, and P3 receives at minimum 50 dispatch slots/sec. At planning volume, P2 peak demand is approximately 315/sec. The guaranteed minimum covers 63% of P2 peak demand even under full P1 saturation.

**What this does not guarantee:** Under extreme P1 load, P2 and P3 will be delayed but not starved. The delay is bounded by queue depth divided by the guaranteed minimum rate. In the extreme case where P2 queue depth reaches the TTL ceiling (24 hours × 315/sec ≈ 27M messages), drain time at 200/sec minimum is approximately 37 hours — which exceeds the 24-hour TTL. In this scenario, P2 messages expire before delivery. This is the correct behavior: a "like" notification from 25 hours ago has no value. The TTL is the ultimate starvation backstop.

### 2.3 Processing State — Sorted Set, Not a List

**Why not a Redis List:** Three concrete problems make Redis Lists unsuitable for the processing tracker.

**Problem 1 — No O(1) membership test.** Checking membership in a Redis List requires a full `LRANGE` scan — O(N). The worker acknowledgment path needs to verify message ownership before marking delivery complete. Not implementable in O(1) with a List.

**Problem 2 — `LREM` during recovery is O(N) per message, O(N²) aggregate.** Under a sustained outage with hundreds of accumulated messages, recovery becomes quadratic.

**Problem 3 — Concurrent recovery processes cause double-enqueue.** Two recovery instances running concurrently can both `LREM` the same message ID, both succeed, both `RPUSH`, and the message ends up enqueued twice.

**Fix: The queue is a Sorted Set scored by enqueue timestamp. The processing tracker is a separate Sorted Set scored by dequeue timestamp.**

```lua
-- Dequeue (atomic Lua script):
-- KEYS[1] = queue:<priority>:<channel>
-- KEYS[2] = processing:<channel>
-- ARGV[1] = current Unix timestamp

local msg = redis.call('ZPOPMIN', KEYS[1])
if msg[1] then
    redis.call('ZADD', KEYS[2], ARGV[1], msg[1])
end
return msg[1]
```

This gives:
- O(log N) dequeue via `ZPOPMIN`
- O(log N) membership test: `ZSCORE processing:<channel> <message_id>` returns nil if not present
- O(log N) removal on acknowledgment: `ZREM processing:<channel> <message_id>`
- O(log N + K) recovery scan: `ZRANGEBYSCORE processing:<channel> 0 <now-60>` returns K stale entries directly

**Heartbeat update** (worker coroutine, every 10 seconds):
```
ZADD processing:<channel> <current_unix_timestamp> <message_id>
```
Updates the score in-place. Prevents false reclaim of slow-but-alive workers.

**Worker acknowledgment** (after successful delivery):
```
ZSCORE processing:<channel> <message_id>
# If nil: message was reclaimed by recovery; discard result silently
# If non-nil: ZREM processing:<channel> <message_id>
```

**The slow-worker race condition — acknowledged and bounded:**

A worker that is alive but blocked will miss heartbeat updates. If the block exceeds 60 seconds, the recovery process reclaims the message and re-enqueues it. The original worker may then complete processing and attempt to acknowledge a message it no longer owns — the `ZSCORE` check causes it to discard its result silently.

This creates a duplicate delivery window, not a loss window. The deduplication layer (Section 2.5) handles the duplicate.

The 60-second reclaim threshold is deliberately conservative. A 10-second heartbeat with a 60-second threshold provides a 5-missed-heartbeat buffer. The realistic cause of a >60-second block is not a GC pause (typically <1 second) but a database connection hung on failure. Worker database connections have a 15-second connect timeout and a 30-second query timeout, so a hung call resolves with an error before the reclaim threshold is reached.

**Residual risk:** If both the heartbeat coroutine and the database timeout are misconfigured simultaneously, a worker could hold a message past