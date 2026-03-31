# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 4 — Addressing Concurrency, Correctness, and Completeness Gaps

---

## Executive Summary

Revision 4 addresses ten problems identified in the Revision 3 review. The problems fall into three categories: concurrency bugs (race condition in two-layer deduplication, shared mutable state in the FCM rate limiter), operational risks presented as sound practice (empirical rate limit discovery in production), and underspecified decisions that defer correctness to implementation time (notification_id source, P0 email escalation criteria, OTP abandoned delivery cleanup, APNs token manager truncation). Two structural concerns are also addressed: head-of-line blocking in the `user_id % 100` grouping scheme, and a cross-training assignment that solves a channel integration gap while creating a worse gap in the foundational layer. The synchronous in-app write for P0 alerts is reconsidered as an availability dependency, not purely a reliability improvement.

Each fix is described at the point of the original decision. Where a fix introduces a new tradeoff, the tradeoff is made explicit.

---

## 1. Scale Assumptions and Constraints

*Unchanged from Revision 3. Reproduced for completeness.*

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

SMS is capped at 100K/day with a hard system-level alert at 150K/day. The 1M/day figure is a budget ceiling, not an expected steady-state.

---

## 2. Team Allocation

### The Cross-Training Problem

Revision 3 assigned E1 as cross-trained backup for push integrations if E2 leaves. A reviewer correctly identified the failure mode: E1's primary responsibility is the core pipeline — the foundational layer that all channel integrations depend on. If E2 leaves and E1 shifts to cover push, the core pipeline simultaneously loses its primary owner at the moment the team is already under stress. The cross-training solves the channel integration gap while creating a more serious gap one layer below it.

**The underlying constraint:** A 4-person team cannot fully cover all critical paths simultaneously. The goal is to ensure no single departure makes a component *unrecoverable* — not that every component has a full-time backup owner.

**Revised allocation:**

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (secondary familiarity, not ownership) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM *API layer only* — E1 does not own pipeline changes |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

The key change: E2 provides *secondary familiarity* with the core pipeline, not ownership of it. If E1 leaves, E2 can maintain the pipeline in a steady state — keeping it running, handling incidents, making small changes — while the team adjusts. E2 cannot simultaneously own push integrations and drive core pipeline development, and the plan does not pretend otherwise. If E1 leaves during active development of the core pipeline, the project timeline slips. That is the honest consequence of a 4-person team, and it is better acknowledged in the plan than discovered during an incident.

E1 covers the APNs and FCM *API integration layer* (the HTTP calls, token management, response parsing) if E2 leaves, but does not own the broader push subsystem. This is a narrower and more realistic scope for cross-training.

---

## 3. System Architecture

### 3.1 SQS FIFO: Message Group ID Strategy and Head-of-Line Blocking

**The grouping scheme from Revision 3:** `group_id = user_id % 100` — 100 groups per queue.

**The head-of-line blocking problem:** With 3M DAU and 100 groups, each group contains approximately 30,000 active users. SQS FIFO guarantees in-order, one-at-a-time processing *within a message group* — the next message in a group is not delivered until the previous message's visibility timeout expires or it is deleted. A single message that takes its full visibility timeout (say, 30 seconds due to a slow APNs connection) blocks all other messages in that group for those 30 seconds. At 30,000 users per group, this is not a theoretical risk. It is a routine occurrence whenever any downstream call is slow.

**The fix:** Increase the number of message groups and shorten the visibility timeout.

```
group_id = user_id % 1000   # 1,000 groups per queue
visibility_timeout = 10s    # Reduced from 30s default
worker_concurrency = 20     # Per priority tier
```

With 1,000 groups, each group contains approximately 3,000 active users at peak. A 10-second visibility timeout means a slow message blocks its group for at most 10 seconds before the message becomes visible again and a different worker can pick it up. The tradeoff: a 10-second visibility timeout means messages can be redelivered to a second worker if the first worker is slow but not dead. The second layer of deduplication (the `sent:{notification_id}` check at the worker layer — see Section 3.2) handles this redelivery correctly.

**Why not per-user group IDs?** Per-user group IDs (`group_id = user_id`) would eliminate head-of-line blocking between users entirely. The cost is that SQS FIFO throughput is bounded by the number of *active* groups — with 3M DAU and messages spread across 3M group IDs, the aggregate throughput is the sum of individual group rates, which SQS handles, but the operational overhead of managing 3M active groups (and the SQS FIFO per-group sequencing metadata) creates unpredictable behavior at scale. The AWS documentation does not specify per-group throughput limits clearly, and we have no empirical data for this usage pattern. 1,000 groups is a conservative middle ground we can validate before launch.

**This is a revisable decision.** The group count is a configuration parameter. If head-of-line blocking remains a problem in production despite 1,000 groups and 10-second visibility timeouts, we increase to 5,000 groups. This does not require a code change.

### 3.2 Deduplication: Fixing the Race Condition and Defining notification_id

**Two problems from Revision 3:**

**Problem 1 — Race condition at the router layer:** The router checks `dedup:{dedup_key}` in Redis and then, if absent, sets the key and enqueues to SQS. Two concurrent events for the same user/type/entity arriving within milliseconds can both read the key as absent before either write completes, resulting in two messages enqueued. The check-then-set is not atomic.

**Fix:** Use Redis `SET NX` (set if not exists) as the deduplication operation, not a separate GET followed by SET. `SET NX` is atomic at the Redis level.

```python
async def deduplicate_and_enqueue(
    router: NotificationRouter,
    event: NotificationEvent,
) -> EnqueueResult:
    dedup_key = compute_dedup_key(event)
    redis_key = f"dedup:{dedup_key}"

    # Atomic: SET key value EX 300 NX
    # Returns True if key was set (first occurrence), False if already existed
    acquired = await redis.set(
        redis_key,
        event.event_id,      # Store event_id for debugging, not used for logic
        ex=300,              # 5-minute dedup window
        nx=True,             # Only set if key does not exist
    )

    if not acquired:
        return EnqueueResult.DEDUPLICATED

    # Key was set — we are the first to process this event
    # Enqueue to SQS
    try:
        await sqs.send_message(
            QueueUrl=priority_queue_url(event.priority),
            MessageBody=event.to_json(),
            MessageGroupId=str(event.user_id % 1000),
            MessageDeduplicationId=event.event_id,  # SQS-level dedup as backstop
        )
        return EnqueueResult.ENQUEUED
    except SQSError:
        # Enqueue failed after Redis key was set.
        # Delete the Redis key so the event can be retried by the caller.
        await redis.delete(redis_key)
        raise
```

The `except SQSError` block is important: if the Redis write succeeds but the SQS enqueue fails, we must delete the Redis key, otherwise the event is permanently deduplicated without ever being delivered. This creates a brief window where a concurrent event could also set the key and enqueue — we accept this. The alternative (leaving the key set on SQS failure) causes silent message loss, which is worse.

**Problem 2 — notification_id is never defined:** The worker-layer dedup check uses `sent:{notification_id}` to prevent duplicate dispatch on SQS redelivery. The previous revision never specified where `notification_id` comes from or whether it is stable across redeliveries. If a worker generates a new ID at dequeue time, the check is useless.

**Fix:** `notification_id` is set by the router at enqueue time, embedded in the SQS message body, and is stable across all redeliveries of the same SQS message.

```python
@dataclass
class NotificationMessage:
    notification_id: str   # UUID4, assigned by router, immutable
    event_id: str          # Source event ID, used for router-layer dedup
    user_id: int
    notification_type: str
    entity_id: str
    priority: int
    channels: list[str]
    payload: dict
    created_at: float

# At the router, before enqueue:
message = NotificationMessage(
    notification_id=str(uuid.uuid4()),  # Assigned once, here, never regenerated
    event_id=event.event_id,
    # ... rest of fields
)

# At the worker, before dispatch:
dedup_key = f"sent:{message.notification_id}"
already_sent = await redis.set(dedup_key, "1", ex=86400, nx=True)
if not already_sent:
    # This notification_id was already dispatched by a previous worker
    # (SQS redelivery after worker crash mid-dispatch)
    return DispatchResult.ALREADY_DISPATCHED
```

Because `notification_id` is embedded in the SQS message body, every redelivery of the same SQS message carries the same `notification_id`. A worker that crashes after setting `sent:{notification_id}` but before deleting the SQS message will cause SQS to redeliver the message; the next worker reads the same `notification_id`, finds the Redis key set, and discards.

**What this does not protect against:** If a worker sets `sent:{notification_id}` and then dispatches to APNs/FCM, but the dispatch call hangs and the visibility timeout expires before the worker deletes the SQS message, a second worker picks up the same message, finds the Redis key already set, and discards it — even though the first dispatch may have failed (the hang may resolve as a failure after the timeout). This means a notification that appeared to be in-flight is silently dropped. We accept this tradeoff: the alternative is not setting the Redis key until after confirmed dispatch, which reintroduces the duplicate dispatch problem for all crash scenarios. Hung external calls are handled by the FCM/APNs client timeouts (set to 5 seconds, well under the 10-second visibility timeout), making this scenario rare in practice.

### 3.3 P0 In-App Write: Synchronous vs. Asynchronous

**The problem from Revision 3:** The proposal described the in-app store write for P0 security alerts as "synchronous, before anything else," presenting this as a reliability improvement. A reviewer correctly identified that a synchronous PostgreSQL write in the router's hot path couples router latency directly to database latency. A slow write or lock contention delays all P0 routing.

**The actual tradeoff:** The in-app write is a *durability* guarantee, not a delivery guarantee. The purpose is to ensure the security alert is visible to the user even if all push and email delivery fails. The question is whether this durability guarantee needs to be synchronous in the router, or whether it can be asynchronous with a different durability mechanism.

**Resolution:** The in-app write is asynchronous but uses a separate durable queue, not a fire-and-forget call.

```
P0 Security Alert Routing:

Router
  │
  ├── 1. Enqueue to p0-notifications.fifo (SQS) — push/email dispatch
  │
  └── 2. Enqueue to p0-inapp.fifo (SQS) — in-app store write
           │
           └── In-App Writer Worker
                   │
                   └── PostgreSQL write (in-app store)
```

Both enqueues happen before the router returns. Neither is a direct database write. The router's latency is now coupled to two SQS enqueue operations (both fast, typically <5ms), not to a PostgreSQL write.

**What we give up:** The in-app record is not written at the exact moment of routing. There is a brief window (typically seconds, bounded by SQS delivery latency and worker processing time) during which a user who opens the app immediately after a security event might not yet see the in-app alert. For security alerts, this is acceptable — the user is unlikely to open the app in the same second as the triggering event, and the push notification (which arrives via a different path) serves as the immediate signal.

**What we retain:** If the push delivery worker crashes, if APNs is down, if email delivery fails — the in-app write is independently queued and will complete. The in-app store remains the guaranteed backstop.

**P0 dead letter queue:** Both SQS queues have a dead letter queue configured at depth 3 (3 failed processing attempts). DLQ messages trigger a PagerDuty alert within 60 seconds. This is the failure handling path — not silent discard.

---

## 4. Delivery Channels

### 4.1 Push Notifications

#### APNs Token Manager — Complete Implementation

The Revision 3 APNs token manager was truncated. The complete implementation is below. The critical correctness requirement is double-checked locking: the slow path must re-check token freshness *inside* the lock to prevent multiple concurrent callers from all generating new tokens simultaneously.

```python
class APNsTokenManager:
    """
    JWT token manager shared across all APNs HTTP/2 connections.
    APNs enforces a hard 1-hour token expiry.
    We refresh proactively at 50 minutes (3,000 seconds).

    Thread safety: uses asyncio.Lock for the refresh critical section.
    Multiple concurrent callers waiting for a refresh will all receive
    the same new token — only one refresh actually executes.
    """

    TOKEN_REFRESH_INTERVAL = 3000   # 50 minutes in seconds
    TOKEN_ALGORITHM = "ES256"

    def __init__(self, key_id: str, team_id: str, private_key_pem: bytes):
        self._key_id = key_id
        self._team_id = team_id
        self._private_key_pem = private_key_pem
        self._token: str | None = None
        self._token_generated_at: float = 0.0
        self._refresh_lock = asyncio.Lock()

    def _token_is_fresh(self) -> bool:
        return (
            self._token is not None
            and (time.monotonic() - self._token_generated_at) < self.TOKEN_REFRESH_INTERVAL
        )

    def _generate_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self._team_id,
            "