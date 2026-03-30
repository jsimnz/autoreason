# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via companion expiry sorted sets and worker-side backstop checking. Starvation prevention uses a token-bucket mechanism: P2/P3 queues each accumulate credits at a guaranteed minimum rate (200 credits/sec for P2, 50 credits/sec for P3), and workers must spend a credit to skip a lower-priority message. Under sustained P1 load, P2 and P3 are delayed but not starved.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The deduplication layer is a Redis hash with a 24-hour TTL, keyed by `notification_id:channel`, checked atomically on dispatch. Its failure modes and performance cost are specified. The recovery lock TTL is 90 seconds against a 60-second cycle — the gap between the previous 45/30 design is acknowledged and closed.

3. **Per-channel, per-priority worker pools** derived from first-principles throughput benchmarks, not asserted. The worker matrix is fully specified with per-worker throughput justification. The APNs new-bundle-ID throttling mitigation is a pre-warm procedure with a defined runbook. The in-app worker count is justified by quantified ancillary load, not circular reasoning.

4. **Redis primary/replica with bounded failover.** P0 behavior during the failover window is quantified: a 15–30 second window during which P0 notifications queue but do not deliver, with a defined recovery sequence. The viral spike analysis correctly identifies FCM rate limits as the binding constraint, not worker capacity, and the P2/P3 shedding mechanism is specified against that constraint.

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

If measured traffic diverges from the 15M–100M range by more than 2× in either direction, a re-plan is triggered. For a 4-engineer team on a 6-month timeline, this is a real cost: a re-plan triggered at day 30 with a month-3 deadline consumes roughly one-third of total project duration. The trigger and response are therefore pre-specified to avoid re-planning from scratch under pressure.

**Traffic too low (< 7.5M/day measured):** No re-plan needed. The system runs underutilized. Worker instances are scaled down. No architecture change.

**Traffic 2–5× above plan (100M–225M/day):** Pre-specified response: (a) provision additional worker instances — 10–15 minutes on target infrastructure; (b) increase Redis instance size — same day; (c) shard the queue namespace by user ID range — 1 week of engineering. No feature scope is cut. Timeline slips by approximately 2 weeks.

**Traffic > 5× above plan (> 225M/day):** This exceeds the architecture's designed range. Pre-specified response: defer SMS and email channels to month 4, concentrate engineering on push and in-app. One engineer is assigned to re-architecture for 3 weeks. This is the only scenario that changes feature scope. The team lead makes this call at the month-1 review, not reactively.

**Why pre-specifying the response matters:** A re-plan triggered without a pre-specified response at 3 AM during a growth spike produces a different architecture than one made deliberately. The decision tree above is the re-plan. It is made now, when the team is not under pressure.

**Temporal spike analysis — the 3× model and its actual limits:**

The 3× multiplier models predictable daily rhythm. It does not model viral events. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** A celebrity post or breaking news can generate 10–20× baseline notification volume over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

**The binding constraint during viral spikes is FCM/APNs rate limits, not worker capacity.** Worker capacity (~26,000/sec derived in Section 3.3) is not the relevant ceiling. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike against the 3× peak figure, FCM demand approaches ~10,500/sec — near or above the FCM ceiling. Worker capacity is irrelevant once the external provider is the bottleneck.

**What actually protects delivery during a viral spike:** The priority queue structure. Under FCM throttling, the dispatch layer receives 429 responses and applies exponential backoff. P0 and P1 messages are retried immediately within the backoff window. P2 and P3 messages are deprioritized: they accumulate in queue and drain after the spike subsides. A "like" notification delayed 3 minutes during a viral event is not a product failure. The queue depth during a 10-minute spike at 10,500/sec FCM ceiling with 3,500/sec excess: approximately 2.1M messages queued, draining at ~8,000/sec excess capacity after the spike, cleared in approximately 4 minutes. This is the actual recovery timeline, not a qualitative claim.

### 1.2 Channel Split

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

**Active-user correction applied only where it governs delivery:**

Push serves offline and background users. The concurrent-user correction does not apply to push. In-app delivery is gated on WebSocket connection state; a notification to an offline user falls back to push or queues for next login. The in-app peak demand figure of ~63/sec reflects the 20% concurrency fraction of 3M DAU.

**Capacity shift procedure — realistic timing:**

Workers are parameterized at startup by queue prefix and dispatch function. Shifting capacity from in-app to push under high load is a configuration change followed by a rolling restart. The realistic timing, not the best-case timing:

- **Scripted, tested, on-call engineer available:** ~5 minutes for a 5-worker pool.
- **3 AM, runbook not previously rehearsed:** 15–25 minutes. Config must be located, change must be verified, restart must be monitored.
- **Automated trigger (queue depth threshold alert → auto-scaling rule):** 2–3 minutes.

**Planning decision:** Implement the automated trigger in month 2. Until then, the on-call runbook is rehearsed in a staging environment monthly. The 5-minute figure applies only after the automated trigger is in place. The 15–25 minute figure is the honest planning number for the first 60 days of production.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path DB dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | Transient DB unavailability delays delivery | Eliminates DB dependency on hot path |

The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

### 2.2 Priority Queue Structure and Starvation Prevention

Four priority levels with defined semantics:

| Priority | Examples | TTL | Guaranteed minimum rate |
|----------|----------|-----|------------------------|
| P0 | Security alerts, account recovery | 1 hour | No cap — always drain first |
| P1 | Direct messages, mentions | 4 hours | No cap — drain before P2/P3 |
| P2 | Comments, reactions | 24 hours | 200 credits/sec |
| P3 | Recommendations, digests | 72 hours | 50 credits/sec |

**The starvation problem:** Under sustained P1 load, a naive priority queue never reaches P2 or P3. A user who receives a high-volume notification type will never see lower-priority notifications delivered.

**Starvation prevention — token bucket per lower-priority queue:**

Each P2 and P3 queue has a token bucket maintained in Redis. Workers are required to check the bucket before skipping a lower-priority message.

```python
# Token bucket state in Redis:
# p2_tokens: float (current token count)
# p2_last_refill: unix timestamp

# Refill rate: 200 tokens/sec for P2, 50 tokens/sec for P3
# Bucket capacity: 10× refill rate (2000 for P2, 500 for P3)

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
            
        # Drain P1 unless P2 or P3 have accumulated tokens above threshold
        p2_tokens = get_available_tokens("p2", 200, 2000)
        p3_tokens = get_available_tokens("p3", 50, 500)
        
        # If P2 has more than 1 second of backlog credits, service it
        if p2_tokens >= 200:
            msg = dequeue(f"queue:p2:{channel}")
            if msg:
                consume_tokens("p2", 1)
                dispatch(msg); continue
        
        # If P3 has more than 1 second of backlog credits, service it
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

**What this guarantees:** Under sustained P1 load, P2 receives at minimum 200 dispatch slots/sec across the worker fleet, and P3 receives at minimum 50 dispatch slots/sec. At the planning volume, P2 peak demand is ~315/sec (70% of push peak × 30% P2 share, approximate). The guaranteed minimum covers 63% of P2 peak demand even under full P1 saturation. P3 at ~79/sec peak demand is covered at 63% minimum as well.

**What this does not guarantee:** Under extreme P1 load (e.g., a viral DM storm), P2 and P3 will be delayed but not starved. The delay is bounded by queue depth divided by the guaranteed minimum rate. At maximum P2 queue depth (TTL-bounded at 24 hours × 315/sec = ~27M messages), drain time at 200/sec minimum is approximately 37 hours — which exceeds the 24-hour TTL. In this extreme scenario, P2 messages expire before delivery. This is the correct behavior: a "like" notification from 25 hours ago has no value. The TTL is the ultimate starvation backstop.

### 2.3 Processing State — Sorted Set, Not a List

**Why not a Redis List:** Three concrete problems.

**Problem 1 — No O(1) membership test.** Checking membership in a Redis List requires a full `LRANGE` scan — O(N). The worker acknowledgment path needs this check. Not implementable with a List.

**Problem 2 — `LREM` during recovery is O(N) per message, O(N²) aggregate.** Under a sustained outage with hundreds of accumulated messages, recovery becomes quadratic.

**Problem 3 — Concurrent recovery processes cause double-enqueue.** Two recovery instances running concurrently can both `LREM` the same message ID, both succeed, both `RPUSH`, and the message ends up enqueued twice.

**Fix: Sorted Set scored by enqueue timestamp for the queue; separate Sorted Set scored by dequeue timestamp for the processing tracker.**

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
- O(log N) membership test: `ZSCORE processing:<channel> <message_id>`
- O(log N) removal on acknowledgment: `ZREM processing:<channel> <message_id>`
- O(log N + K) recovery scan: `ZRANGEBYSCORE processing:<channel> 0 <now-60>`

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

### 2.4 Recovery Process — Idempotent Under Concurrent Execution

**The lock TTL gap — acknowledged and closed:**

The previous design used a 45-second lock TTL with a 30-second recovery cycle. If a recovery process ran for 45 seconds (possible under Redis latency with a large stale set), the lock expired and a second instance could begin before the first finished. The Lua script