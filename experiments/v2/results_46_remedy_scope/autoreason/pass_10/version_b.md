# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via companion expiry sorted sets and worker-side backstop checking. The P1-drains-P2/P3 mechanism is fully specified with starvation prevention.

2. **ID-based queue entries with a processing set (not a processing list) for O(1) membership testing and atomic reclaim.** The previous design used Redis Lists for both the queue and the processing tracker, which created O(N) recovery scans and an unimplementable membership check. This version uses a Redis Sorted Set for processing state and a distributed lock on the recovery process to prevent concurrent reclaim. The failure behavior during PostgreSQL unavailability is specified in terms of actual retry loop behavior, not just reclaim threshold math.

3. **Per-channel, per-priority worker pools with a concrete redeployment path.** Workers are parameterized by queue prefix and dispatch function at startup, not hardcoded. Shifting capacity between channels is a configuration change and rolling restart, not a code change. Every zero cell in the worker matrix is justified. The APNs failure case — new bundle IDs being throttled by Apple — has a specified mitigation.

4. **Redis primary/replica with bounded failover.** P0 behavior during the failover window is quantified. The recovery process is idempotent under concurrent execution.

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

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

**Temporal spike analysis — the 3× model is insufficient for social apps:**

The 3× multiplier models predictable daily rhythm. It does not model viral events. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** A celebrity post or breaking news can generate 10–20× baseline notification volume over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

**Why the system absorbs viral spikes without re-architecture:** At planning volume, worker capacity is ~26,000/sec against a 1,575/sec average peak. A 20× spike against the 3× peak figure yields ~10,500/sec — still 2.5× below worker processing capacity. The real ceiling is external provider rate limits. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike, FCM demand approaches this ceiling.

**Mitigation:** P2 and P3 notifications are shed first under provider throttling. The priority queue structure protects P0/P1 delivery. P2/P3 messages accumulate and drain after the spike. A "like" notification delayed 3 minutes during a viral event is not a product failure.

### 1.2 Channel Split — Derived, Not Asserted

Reference points: consumer social apps (Instagram, TikTok) are push-heavy at 80–90%. Productivity apps (Slack, LinkedIn) show 15–25% email share. New apps without retention data skew toward push because email lists are smaller.

| Channel | Conservative | **Plan** | Push-heavy |
|---------|-------------|----------|-----------|
| Push (FCM + APNs) | 60% | **70%** | 85% |
| In-app | 25% | **20%** | 10% |
| Email | 12% | **8%** | 4% |
| SMS | 3% | **2%** | 1% |

**Daily volumes at plan:**

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec (capacity ceiling, not operating target) |

FCM and APNs each handle ~50% of push volume: **~547/sec each at peak.**

**Channel split robustness — what "robust" actually means:**

The previous version claimed the worker matrix handles push share from 60–85% without re-provisioning, and that in-app workers could be "redeployed" if push exceeded 80%. That claim was wrong as stated. Workers in a per-channel pool call channel-specific APIs and consume channel-specific queues. Redeploying an in-app worker to handle push is not an operational knob — it requires changing what queue the worker reads from and what external API it calls.

This version makes the flexibility concrete. Workers are parameterized at startup:

```python
# Worker startup configuration
worker = NotificationWorker(
    queue_prefix="queue:push:fcm",
    dispatch_fn=fcm_dispatch,
    batch_size=500,
    concurrency=4
)
```

Shifting capacity from in-app to push under high load is a configuration change (update `queue_prefix` and `dispatch_fn` for a subset of in-app worker instances) followed by a rolling restart. This takes approximately 5 minutes for a 5-worker pool. It is not instant and it is not zero-touch, but it does not require a code change or a new deployment artifact. The on-call runbook documents the specific config change and restart procedure.

**The actual robustness boundary:** The worker matrix handles push share from 60–85% without any intervention. If push share exceeds 85%, the in-app → push redeployment procedure is available within 5 minutes. If push share exceeds 90%, additional worker instances must be provisioned — this takes 10–15 minutes on the target infrastructure. These are the real numbers.

### 1.3 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This correction applies differently by channel.

**Push:** Push serves offline and background users. The concurrent-user correction does not apply — the 70% channel allocation already represents full DAU-based volume. Applying a second population filter understates demand.
- Push peak demand = 31.5M/day × 3 / 86,400 = **~1,094/sec**

**In-app:** In-app delivery is gated on WebSocket connection state. A notification to an offline user does not consume in-app delivery resources; it falls back to push or queues for next login.
- In-app peak demand = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand.

**In-app worker sizing against the corrected figure:** 5 in-app workers at ~1,000 rows/sec/worker = 5,000/sec capacity against a 63/sec corrected peak. This is ~79× overcapacity, which is acknowledged. The workers are not sized down for three reasons: (1) in-app workers also handle read-state updates and delivery confirmations, which add load not captured in the delivery rate alone; (2) at 50% concurrency (plausible for a highly engaged app), demand reaches ~157/sec; (3) in-app workers make no external API calls and are the cheapest workers in the fleet. The in-app worker count is driven by ancillary workload and concurrency uncertainty, not delivery throughput.

### 1.4 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

**Honest comparison:**

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Hot-path database dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | Transient DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path |

The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

---

### 1.4.1 Processing State — Sorted Set, Not a List

**The previous design used a Redis List for the processing tracker.** This created three problems that are now fixed:

**Problem 1 — O(1) membership test was unimplementable.** The previous design stated "the worker acknowledgment path checks whether the message is still in the processing list." Checking membership in a Redis List requires a full `LRANGE` scan — O(N). There is no O(1) membership test for Redis Lists. At 1,380 in-flight messages during an outage, this scan is not catastrophic, but it is not the O(1) operation implied.

**Problem 2 — `LREM` during recovery is O(N) per message, O(N²) aggregate.** The recovery process called `LREM` for each stale message, scanning the entire processing list each time. During a sustained outage with hundreds of messages accumulated, this becomes quadratic.

**Problem 3 — Concurrent recovery processes double-reclaim.** Two recovery process instances running concurrently (during a rolling restart, or if the 30-second interval overlaps) could both call `LREM` for the same message ID, both succeed (since `LREM` removes the first occurrence), both call `RPUSH`, and the message ends up enqueued twice. The previous design acknowledged duplicate delivery from the slow-worker race but not from the recovery process itself.

**Fix: Use a Redis Sorted Set for processing state.**

```
# Dequeue: atomically move to processing set
MULTI
  RPOPLPUSH queue:<priority>:<channel> scratch_list  # temporary
  ZADD processing:<channel> <unix_timestamp> <message_id>
  LREM scratch_list 1 <message_id>
EXEC
```

Actually, the cleanest pattern avoids the scratch list entirely. The queue itself is a Sorted Set scored by enqueue time, and dequeue is an atomic range-pop:

```
# Queue is a Sorted Set scored by enqueue timestamp
# (lower score = higher priority within same priority level)

# Enqueue:
ZADD queue:<priority>:<channel> <enqueue_unix_ts> <message_id>

# Dequeue (atomic, Lua script):
local msg = redis.call('ZPOPMIN', KEYS[1])  -- queue:<priority>:<channel>
if msg[1] then
    redis.call('ZADD', KEYS[2], ARGV[1], msg[1])  -- processing:<channel>, now, id
end
return msg[1]
```

Keys:
- `KEYS[1]` = `queue:<priority>:<channel>`
- `KEYS[2]` = `processing:<channel>`
- `ARGV[1]` = current Unix timestamp

**This gives us:**
- O(log N) dequeue (ZPOPMIN on a sorted set)
- O(log N) membership test: `ZSCORE processing:<channel> <message_id>` returns nil if not present
- O(log N) removal on acknowledgment: `ZREM processing:<channel> <message_id>`
- O(log N + K) recovery scan: `ZRANGEBYSCORE processing:<channel> 0 <now-60>` returns K stale entries directly

**Heartbeat update** (worker coroutine, every 10 seconds):
```
ZADD processing:<channel> <current_unix_timestamp> <message_id>
```
This updates the score in-place. O(log N).

**Worker acknowledgment** (after successful delivery):
```
ZSCORE processing:<channel> <message_id>
# If nil: message was reclaimed; discard result silently
# If non-nil: ZREM processing:<channel> <message_id>
```
O(log N). Implementable. No list scan.

---

### 1.4.2 Recovery Process — Idempotent Under Concurrent Execution

**The previous recovery process was not idempotent.** Two concurrent instances could both identify the same stale entry and both re-enqueue it.

**Fix: Distributed lock on the recovery process.**

The recovery process acquires a Redis lock before scanning:

```python
def run_recovery(channel: str):
    lock_key = f"recovery_lock:{channel}"
    lock_token = str(uuid.uuid4())
    
    # Acquire lock with 45-second TTL (longer than one recovery cycle)
    acquired = redis.set(lock_key, lock_token, nx=True, ex=45)
    if not acquired:
        return  # Another instance is running recovery; skip this cycle
    
    try:
        now = time.time()
        stale_threshold = now - 60
        
        # Get stale entries
        stale = redis.zrangebyscore(f"processing:{channel}", 0, stale_threshold)
        
        for msg_id in stale:
            # Atomic reclaim: only re-enqueue if still in processing set
            # (worker may have ack'd between scan and reclaim)
            reclaim_script = """
                local score = redis.call('ZSCORE', KEYS[1], ARGV[1])
                if score and tonumber(score) <= tonumber(ARGV[2]) then
                    redis.call('ZREM', KEYS[1], ARGV[1])
                    redis.call('ZADD', KEYS[2], ARGV[3], ARGV[1])
                    return 1
                end
                return 0
            """
            reclaimed = redis.eval(
                reclaim_script,
                2,
                f"processing:{channel}",      # KEYS[1]
                f"queue:retry:{channel}",      # KEYS[2]
                msg_id,                        # ARGV[1]
                stale_threshold,               # ARGV[2] — re-check threshold atomically
                now,                           # ARGV[3] — new enqueue score
            )
    finally:
        # Release lock only if we still own it
        release_script = """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                return redis.call('DEL', KEYS[1])
            end
            return 0
        """
        redis.eval(release_script, 1, lock_key, lock_token)
```

**Why the Lua script makes reclaim idempotent:** The script atomically checks that the message is still in the processing set with a score at or below the stale threshold before removing and re-enqueueing. If a second recovery instance somehow acquires the lock (impossible with the SET NX guard, but defended against anyway), or if a worker acks the message between the scan and the reclaim, the Lua script's conditional check prevents double-reclaim. The operation is a no-op if the message is already gone.

**Recovery cycle:** Runs every 30 seconds per channel. Lock TTL is 45 seconds, preventing overlap.

---

### 1.4.3 Deduplication — Set at Enqueue Time, Not Delivery Time

**The previous design set the dedup key at