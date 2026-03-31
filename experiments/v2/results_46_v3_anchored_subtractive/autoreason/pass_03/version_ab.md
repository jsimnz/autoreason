# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Core architectural commitments: SQS-backed priority queues, direct channel integrations, PostgreSQL as the system of record. This revision addresses: SQS FIFO throughput and head-of-line blocking, a race condition in two-layer deduplication, an undefined `notification_id` source, a silent failure mode for P0 push delivery, the synchronous in-app write as an availability dependency, stale badge counts, unbounded digest state, a single point of failure in team allocation, compliance implications of log deletion, preference cache TTL safety, FCM rate limit assumptions, and a collapse-id strategy that contradicts server-side aggregation.

---

## 1. Scale Assumptions and Constraints

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth and security events only |

SMS volume is driven by auth and security event rates. We budget 100K SMS/day with a hard system-level cap and alerting at 150K/day.

---

## 2. Team Allocation

A 4-person team cannot fully cover all critical paths simultaneously. The goal is to ensure no single departure makes a component *unrecoverable* — not that every component has a full-time backup owner.

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (secondary familiarity, not ownership) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM API layer only |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

The previous revision assigned E1 as cross-trained backup for push. The failure mode: if E2 leaves and E1 shifts to cover push, the core pipeline loses its primary owner at the moment the team is already under stress. The cross-training solved a channel integration gap while creating a worse gap one layer below it.

The revised scope: E2 provides secondary familiarity with the core pipeline — enough to keep it running and handle incidents in a steady state. E1 covers the APNs and FCM *API integration layer* (HTTP calls, token management, response parsing) if E2 leaves, but does not own the broader push subsystem. If E1 leaves during active core pipeline development, the project timeline slips. That is the honest consequence of a 4-person team.

E4 owns email and SMS alongside reliability work. These integrations are operationally simpler and more stable than push, making them compatible with reliability responsibilities.

---

## 3. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Preference check (Redis cache, tiered TTL)
  - Suppression check
  - Priority assignment
  - Channel selection
  - Aggregation window check
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[SQS Priority Queues]                        [In-App Store]
  - p0-notifications.fifo                    (PostgreSQL,
  - p1-notifications.fifo                     partitioned)
  - p2-notifications.fifo
  - p3-notifications (standard)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2/P3 Worker Pool (10 workers)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log] (PostgreSQL, retention per compliance policy)
          │
          ▼
   [Feedback Processor] (bounces, opens, delivery failures)
```

### 3.1 SQS FIFO: Message Group ID Strategy

We do not need cross-user ordering guarantees. The requirement is that P0 notifications are not delayed behind P2 backlogs — solved by separate queues per priority tier, not by ordering within a queue. Within a priority tier, there is no correctness requirement that user A's notification be delivered before user B's.

**The head-of-line blocking problem:** With 3M DAU and 100 groups (as in the previous revision), each group contains approximately 30,000 active users. SQS FIFO processes messages within a group one at a time — a single message that takes its full visibility timeout blocks all other messages in that group for that duration. At 30,000 users per group, this is routine whenever any downstream call is slow.

**Fix:** Increase group count and shorten visibility timeout.

```
group_id = user_id % 1000   # 1,000 groups per queue
visibility_timeout = 10s    # Reduced from 30s default
```

With 1,000 groups, each group contains approximately 3,000 active users at peak. A 10-second timeout means a slow message blocks its group for at most 10 seconds before becoming visible again. The tradeoff: messages can be redelivered to a second worker if the first is slow but not dead. The worker-layer deduplication (Section 3.2) handles this correctly.

**Why not per-user group IDs?** Per-user group IDs eliminate head-of-line blocking between users entirely. The cost is unpredictable behavior at scale — AWS documentation does not specify per-group throughput limits clearly, and we have no empirical data for 3M active group IDs. 1,000 groups is a conservative middle ground we can validate before launch. The group count is a configuration parameter; increasing it does not require a code change.

**Throughput:** With high-throughput mode enabled, SQS FIFO supports up to 3,000 messages/sec aggregate per queue. Our peak is ~1,750/sec across all queues. If we approach the limit during a viral event, we add a second P1 FIFO queue and route by `user_id % 2`. This is a runbook item, not a code change.

### 3.2 Deduplication: Race Condition Fix and notification_id Definition

**Two problems from the previous revision:**

**Problem 1 — Race condition at the router layer:** The router checked `dedup:{dedup_key}` in Redis and then, if absent, set the key and enqueued to SQS. Two concurrent events for the same user/type/entity arriving within milliseconds could both read the key as absent before either write completed, resulting in two messages enqueued. The check-then-set was not atomic.

**Fix:** Use Redis `SET NX` as the deduplication operation.

```python
async def deduplicate_and_enqueue(
    event: NotificationEvent,
) -> EnqueueResult:
    dedup_key = f"dedup:{compute_dedup_key(event)}"

    # Atomic: SET key value EX 300 NX
    # Returns True if key was set (first occurrence), False if already existed
    acquired = await redis.set(
        dedup_key,
        event.event_id,   # Stored for debugging; not used for logic
        ex=300,           # 5-minute dedup window
        nx=True,
    )
    if not acquired:
        return EnqueueResult.DEDUPLICATED

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
        # Delete the key so the event can be retried — otherwise it is
        # permanently deduplicated without ever being delivered.
        await redis.delete(dedup_key)
        raise
```

The `except SQSError` delete creates a brief window where a concurrent event could also set the key and enqueue. We accept this. The alternative — leaving the key set on SQS failure — causes silent message loss, which is worse.

**Problem 2 — notification_id was never defined:** The worker-layer dedup check used `sent:{notification_id}`, but the previous revision never specified where `notification_id` comes from or whether it is stable across SQS redeliveries. If a worker generates a new ID at dequeue time, the check is useless.

**Fix:** `notification_id` is assigned by the router at enqueue time, embedded in the SQS message body, and is stable across all redeliveries.

```python
@dataclass
class NotificationMessage:
    notification_id: str   # UUID4, assigned by router, never regenerated
    event_id: str          # Source event ID, used for router-layer dedup
    user_id: int
    notification_type: str
    entity_id: str
    priority: int
    channels: list[str]
    payload: dict
    created_at: float

# At the worker, before dispatch:
dedup_key = f"sent:{message.notification_id}"
acquired = await redis.set(dedup_key, "1", ex=86400, nx=True)
if not acquired:
    return DispatchResult.ALREADY_DISPATCHED
```

Because `notification_id` is in the SQS message body, every redelivery of the same SQS message carries the same ID. A worker that crashes after setting `sent:{notification_id}` but before deleting the SQS message causes SQS to redeliver; the next worker finds the key set and discards.

**Known gap:** If a worker sets `sent:{notification_id}`, dispatches to APNs/FCM, but the call hangs past the visibility timeout, a second worker discards the message as already sent — even if the first dispatch ultimately failed. We accept this: APNs/FCM client timeouts are set to 5 seconds, well under the 10-second visibility timeout, making this scenario rare. The alternative (setting the Redis key only after confirmed dispatch) reintroduces duplicate dispatch for all crash scenarios.

### 3.3 OTP Routing: Separate from the General Pipeline

OTPs have requirements incompatible with the general notification system: exactly-once delivery per generation event, expiry managed by the auth service, and deduplication semantics that mean "don't redeliver the same OTP" — not "suppress a second OTP when the user requests one." A window-based dedup key cannot express these semantics correctly.

OTPs are routed through a dedicated path:

```
Auth Service
    │
    ├── Generates OTP, stores in Redis with TTL matching OTP validity
    │
    └── Calls OTP Delivery Service directly (not the notification pipeline)
            │
            ├── delivery_id = uuid4()
            ├── SET otp_delivery:{delivery_id} "pending" EX 300
            ├── Sends via Twilio (SMS) or APNs/FCM (push)
            └── On success: SET otp_delivery:{delivery_id} "delivered"
                On failure: retry with same delivery_id (provider idempotency key)
```

A new OTP generation creates a new `delivery_id` and is treated as a distinct send. Abandoned pending deliveries (device offline, no callback received) are cleaned up by a TTL-based sweep: any `otp_delivery:{id}` key still in "pending" state after 5 minutes is logged as undelivered and the auth service is notified to invalidate the OTP.

### 3.4 P0 Security Alert Delivery Policy

**APNs expiration:** Security alerts are not time-bounded the way OTPs are. The previous revision's 300-second APNs expiration was borrowed from OTP logic and is wrong — a user with a dead battery for 6 minutes would never receive a "new device login" alert. Security alerts use:

```
apns-expiration: NOW + 24 hours
FCM TTL: 86400 seconds
```

**In-app write — synchronous vs. asynchronous:** The previous revision described the in-app store write as "synchronous, before anything else," presenting this as a reliability improvement. A synchronous PostgreSQL write in the router's hot path couples router latency to database latency. A slow write or lock contention delays all P0 routing.

The in-app write is a *durability* guarantee, not a delivery guarantee. It does not need to be synchronous in the router.

**Resolution:** Both the push/email dispatch and the in-app store write are enqueued to separate SQS queues before the router returns. Neither is a direct database write in the router path.

```
P0 Security Alert Routing:

Router
  │
  ├── 1. Enqueue to p0-notifications.fifo (push/email dispatch)
  └── 2. Enqueue to p0-inapp.fifo (in-app store write)
                   │
                   └── In-App Writer Worker → PostgreSQL
```

Both enqueues happen before the router returns. Router latency is coupled to two SQS enqueue operations (~5ms each), not to a PostgreSQL write.

**What we give up:** A user who opens the app in the seconds between routing and the in-app writer completing its write may not yet see the alert. This is acceptable — the push notification serves as the immediate signal, and the latency window is measured in seconds.

**Delivery policy:**
1. Enqueue in-app write (durable, guaranteed backstop)
2. Enqueue push (APNs expiration: 24h, FCM TTL: 86400)
3. Enqueue email (for account takeover class alerts only)
4. If push fails with UNREGISTERED/invalid token: in-app is the delivery
5. Both queues have DLQ at depth 3; DLQ messages trigger PagerDuty within 60 seconds

**P0 email escalation criteria:** Email is added for notifications classified as account takeover indicators: new device login from unrecognized location, password changed without recent user session, multiple failed authentication attempts followed by success. These are defined as a closed enum in the routing configuration — not inferred at runtime.

---

## 4. Push Channel Implementation

### 4.1 FCM Rate Limits

FCM does not publish per-project rate limits. The actual quota depends on Firebase project tier and whether a quota increase has been requested. Building a connection pool around an assumed number is an operational risk at 35M push/day.

**Resolution:** Design for graceful degradation when limits are hit, not around an assumed limit.

```python
class FCMDispatcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(200)  # Conservative starting concurrency
        self._rate_limiter = TokenBucketRateLimiter(
            initial_rate=300,   # req/sec — conservative starting point
            max_rate=1000,      # upper bound, increased empirically
            min_rate=50,        # floor during backoff
        )

    async def send(self, token: str, payload: dict) -> FCMResult:
        await self._rate_limiter.acquire()
        async with self._semaphore:
            try:
                result = await self._do_send(token, payload)
                return result
            except FCMRateLimitError as e:
                retry_after = e.retry_after or 30
                await self._rate_limiter.reduce_rate(factor=0.5)
                await asyncio.sleep(retry_after)
                raise
```

**Empirical rate limit discovery:** In the first week of production, we ramp concurrency from 50 to 500 in-flight requests in steps of 50, with a 15-minute hold at each step, monitoring for