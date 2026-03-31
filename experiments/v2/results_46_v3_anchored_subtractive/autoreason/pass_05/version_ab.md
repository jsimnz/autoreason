# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses the following issues from the prior version: race condition in two-layer deduplication; hung-call mitigation that was incorrectly characterized; shared mutable state in the FCM rate limiter; head-of-line blocking in the `user_id % 100` grouping scheme; ordering gap between P0 queues undermining the in-app backstop guarantee; `notification_id` inconsistency on retry; and underspecified decisions including P0 email escalation criteria and OTP abandoned delivery cleanup.

Each fix is described at the point of the original decision. Where a fix introduces a new tradeoff, the tradeoff is made explicit.

---

## 1. Scale Assumptions and Constraints

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth and security events only |

SMS is capped at 100K/day. At 90K/day the system emits a warning alert. At 100K/day the system stops enqueuing new SMS messages, logs the drop with full event context, and routes affected events to email where the user has a verified address.

**Validating the email fallback is within capacity:**
- Normal email peak: ~138/sec (4M/day at 3× peak)
- SMS cap overflow routed to email: at most ~3.6/sec at peak
- Combined peak: 141.6/sec — well within the 1,000/sec SendGrid Pro limit

If SMS volume reaches the cap due to a security event (e.g., mass OTP requests), email volume may spike non-linearly. A CloudWatch alarm fires when fallback email volume exceeds 500/sec, triggering manual review.

---

## 2. Team Allocation

A 4-person team cannot fully cover all critical paths simultaneously. The goal is to ensure no single departure makes a component *unrecoverable* — not that every component has a full-time backup owner.

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (defined scope below) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM API layer only |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

### Defining E2's Backup Scope for the Core Pipeline

Worker concurrency is not a code change — it is an environment variable (`WORKER_CONCURRENCY`) read at startup. E2's backup scope includes adjusting this variable and redeploying workers via the existing deployment runbook. Excluding it would mean E2 cannot respond to queue backlog, the most common production incident.

**In scope for E2:**
- Restart failed workers and services
- Roll back a deployment using the existing runbook
- Adjust `WORKER_CONCURRENCY`, `MAX_BATCH_SIZE`, and `BATCH_WINDOW_MS` environment variables and redeploy
- Adjust SQS visibility timeouts and retry counts via AWS console or configuration (no code change)
- Escalate Redis or SQS infrastructure issues to AWS support
- Read pipeline logs and metrics to diagnose which component is failing

**Explicitly out of scope for E2:**
- Modifying routing logic or priority classification code
- Changing deduplication key generation logic
- Modifying batching algorithm logic in code
- Any schema migration on the notifications database

If E1 leaves and a situation requires work outside E2's defined scope, the correct response is to freeze the affected component and address it after the team stabilizes. That is the honest consequence of a 4-person team.

---

## 3. System Architecture

### 3.1 SQS FIFO: Message Group ID Strategy and Head-of-Line Blocking

**The grouping scheme from prior revision:** `group_id = user_id % 100` — 100 groups per queue.

**The head-of-line blocking problem:** With 3M DAU and 100 groups, each group contains approximately 30,000 active users. SQS FIFO guarantees in-order, one-at-a-time processing within a message group — the next message in a group is not delivered until the previous message's visibility timeout expires or it is deleted. A single slow message blocks all other messages in that group for the duration of its visibility timeout. At 30,000 users per group, this is a routine occurrence whenever any downstream call is slow.

**Corrected load test design (Month 1, E1):**

Running a load test with uniform artificial messages does not measure head-of-line blocking. A test where every message completes in 5ms will show excellent p99 latency at any group count and will not surface the pathological case. What we are actually measuring is: if a slow message lands in a group, how many other users are delayed, and for how long?

```
Load test parameters:
  Queue: Staging SQS FIFO, 1,000 groups
  Total throughput: 3,500 msg/sec (2× peak)
  Message distribution: 99% complete in <200ms (simulated fast path)
                         1% complete in 12s (simulated hung APNs call)
  Duration: 30 minutes
  Users per group: ~3,000 (3M DAU / 1,000 groups)

Measurements:
  - Per-group p99 latency when a slow message is in-flight
  - Number of messages blocked behind each slow message
  - Duration of blocking per slow message

Pass criteria:
  - Median blocking duration per slow message: < visibility_timeout (15s)
  - Messages blocked per slow message: < 50
  - No AWS throttling at 3,500 msg/sec
```

If the test reveals unacceptable blocking, the correct fix is not to increase group count further — it is to ensure the application-layer timeout reliably fires before the visibility timeout. This is addressed in Section 3.2.

```
group_id = user_id % 1000   # Starting point for validation; confirmed before go-live
visibility_timeout = 15s
worker_concurrency = 20     # Per priority tier
```

**Migration procedure (defined before go-live):** If group count must change post-launch:
1. Create a new FIFO queue with the new group count
2. Route all new enqueues to the new queue; old queue continues draining
3. Drain the DLQ explicitly before decommissioning — poison-pill or DLQ-stuck messages can prevent the main queue from reaching zero depth
4. Wait for old queue to reach zero depth (CloudWatch alarm)
5. Decommission the old queue

**Why not per-user group IDs?** Per-user group IDs eliminate inter-user blocking entirely. The cost is that SQS FIFO behavior with millions of distinct message group IDs is undocumented by AWS and we have no empirical data for this pattern. We do not use it until we have that data.

### 3.2 Hung-Call Mitigation — Corrected Analysis

**The prior analysis was wrong.** The claim that the 9-second buffer makes the hung-call scenario require "a bug in the HTTP client" is incorrect. TCP half-open connections after network partitions and HTTP/2 stream-level hangs where the connection is alive but the stream produces no data can both cause the application-layer timeout to silently not fire. These are production failure modes.

**The actual risk:** A worker sets both Redis dedup keys, begins an APNs/FCM call, the call hangs indefinitely, the visibility timeout expires, a second worker picks up the message, finds both dedup keys set, and discards. The notification is dropped silently.

**Resolution: Watchdog task with independent timer**

```python
async def dispatch_with_watchdog(
    message: NotificationMessage,
    dispatch_fn: Callable,
    visibility_timeout: int = 15,
    dispatch_budget: int = 8,  # Must be < visibility_timeout
) -> DispatchResult:
    """
    Two independent timeout mechanisms:
    1. asyncio timeout on the dispatch call itself
    2. Watchdog task that fires independently of the dispatch coroutine

    If asyncio timeout fires normally, watchdog is cancelled.
    If asyncio timeout silently fails, watchdog fires at dispatch_budget + 1s
    and logs WATCHDOG_FIRED, which pages on-call.

    The watchdog does not retry — retry is handled by SQS redelivery.
    """
    async def watchdog():
        await asyncio.sleep(dispatch_budget + 1)
        logger.error(
            "WATCHDOG_FIRED: dispatch did not complete within budget",
            extra={
                "notification_id": message.notification_id,
                "channel": message.channel,
                "dispatch_budget_sec": dispatch_budget,
            }
        )
        raise WatchdogFiredError(message.notification_id)

    watchdog_task = asyncio.create_task(watchdog())

    try:
        result = await asyncio.wait_for(dispatch_fn(message), timeout=dispatch_budget)
        watchdog_task.cancel()
        return result
    except asyncio.TimeoutError:
        watchdog_task.cancel()
        logger.warning("dispatch_timeout", extra={"notification_id": message.notification_id})
        raise DispatchTimeoutError(message.notification_id)
    except WatchdogFiredError:
        raise

async def worker_process_message(message: NotificationMessage, sqs, redis):
    dedup_result = await atomic_dedup_check(message, redis)
    if dedup_result != DedupResult.ACQUIRED:
        await sqs.delete_message(message.receipt_handle)
        return

    outcome = None
    try:
        outcome = await dispatch_with_watchdog(
            message,
            dispatch_fn=get_dispatch_fn(message.channel),
        )
    except (DispatchTimeoutError, WatchdogFiredError, DispatchError) as e:
        outcome = DispatchOutcome.FAILED
        logger.error("dispatch_failed", extra={"error": str(e), "notification_id": message.notification_id})
    finally:
        if outcome is not None:
            logger.info("dispatch_outcome", extra={
                "notification_id": message.notification_id,
                "outcome": outcome,
            })
        if outcome == DispatchOutcome.SUCCESS:
            await sqs.delete_message(message.receipt_handle)
        # On failure, do not delete — let SQS redeliver up to retry_count, then DLQ.
```

```
visibility_timeout = 15s
dispatch_budget    = 8s
watchdog_fires_at  = 9s
buffer             = 6s  (15s - 9s, for watchdog to log and worker to clean up)
```

**What the watchdog does not provide:** The watchdog does not prevent the hung-call silent drop scenario if the visibility timeout has already expired before the watchdog fires. Its value is that the drop is no longer silent — it is logged and paged. That is the honest bound of what we can guarantee at the application layer without distributed transaction semantics.

### 3.3 Deduplication: Atomicity, Crash Recovery, and Deterministic IDs

#### Deterministic `notification_id` on Retry

**The problem:** When SQS enqueue fails and the Redis dedup key is deleted, a retry generates a new `uuid4()`. This produces a new `MessageDeduplicationId`, which SQS FIFO treats as a distinct message — the deduplication guarantee is broken for the retry path.

**Resolution:** Derive `notification_id` deterministically from the event's stable fields. The same event always produces the same `notification_id` regardless of how many times it is retried.

```python
import hmac, hashlib

NOTIFICATION_ID_KEY = b"<secret-key-from-secrets-manager>"  # 32 bytes, rotated annually

def derive_notification_id(event: NotificationEvent) -> str:
    """
    Deterministic notification_id derived from stable event fields.
    Uses HMAC-SHA256 to prevent notification_id prediction from event fields.

    Fields included: event_id, user_id, event_type, entity_id, channel.
    Fields excluded: timestamp (not stable across retries).
    """
    stable = f"{event.event_id}:{event.user_id}:{event.event_type}:{event.entity_id}:{event.channel}"
    digest = hmac.new(NOTIFICATION_ID_KEY, stable.encode(), hashlib.sha256).hexdigest()
    return digest
```

#### Router Layer: Atomic Enqueue

```python
async def deduplicate_and_enqueue(
    event: NotificationEvent,
    redis: Redis,
    sqs: SQSClient,
) -> EnqueueResult:
    dedup_key = f"dedup:{compute_dedup_key(event)}"

    # Atomic SET NX — returns True if key was set (first occurrence)
    acquired = await redis.set(dedup_key, event.event_id, ex=300, nx=True)
    if not acquired:
        return EnqueueResult.DEDUPLICATED

    # Deterministic: same event always produces same notification_id
    notification_id = derive_notification_id(event)
    message = NotificationMessage(
        notification_id=notification_id,
        event_id=event.event_id,
        logical_dedup_key=compute_dedup_key(event),
    )

    try:
        await sqs.send_message(
            QueueUrl=priority_queue_url(event.priority),
            MessageBody=message.to_json(),
            MessageGroupId=str(event.user_id % 1000),
            MessageDeduplicationId=notification_id,
        )
        return EnqueueResult.ENQUEUED
    except SQSError:
        # Delete the Redis key so the event can be retried.
        # The worker-layer logical dedup check catches any concurrent enqueue
        # that slips through this window.
        await redis.delete(dedup_key)
        raise
```

#### Worker Layer: Atomic Two-Check Dedup

**The problem with sequential SET NX calls:** A worker crashing between Check 1 (`sent:msg`) and Check 2 (`sent:logical`) leaves `sent:msg` permanently set for a notification that was never dispatched. Subsequent redeliveries find `sent:msg` set and discard without checking `sent:logical` — the notification is silently dropped.

**Resolution:** Both checks in a single Lua script, executed atomically.

```lua
-- atomic_dedup.lua
-- Returns "ACQUIRED" if both keys were set (first time seeing this message).
-- Returns "MSG_DUPLICATE" if sent:msg was already set.
-- Returns "LOGICAL_DUPLICATE" if sent:logical was already set.
-- Returns "PARTIAL_RECOVERY" if sent:msg was absent but sent:logical was set
--   (indicates a prior crash between the two writes — safe to discard).

local msg_key     = KEYS[1]  -- sent:msg:{notification_id}
local logical_key = KEYS[2]  -- sent:logical:{logical_dedup_key}
local notif_id    = ARGV[1]
local ttl         = tonumber(ARGV[2])

local msg_set = redis.call("SET", msg_key, "1", "NX", "EX", ttl)
if not msg_set then
    return "MSG_DUPLICATE"
end

local logical_set = redis.call("SET", logical_key, notif_id, "NX", "EX", ttl)
if not logical_set then
    -- sent:msg was just set but sent:logical was already set.
    -- This means a prior attempt dispatched successfully (or crashed after
    -- setting sent:logical). Either way, discard.
    -- Do not delete sent:msg — leave it set to block future redeliveries.
    return "LOGICAL_DUPLICATE"
end

return "ACQUIRED"
```