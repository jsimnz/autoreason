# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses concurrency bugs (race condition in two-layer deduplication, shared mutable state in the FCM rate limiter), operational risks (empirical rate limit discovery in production), and underspecified decisions (notification_id source, P0 email escalation criteria, OTP abandoned delivery cleanup, APNs token manager truncation). Two structural concerns are also addressed: head-of-line blocking in the `user_id % 100` grouping scheme, and the ordering gap between P0 queues that undermines the in-app backstop guarantee.

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

E2's defined backup scope covers: restarting failed workers and services; rolling back a deployment using the existing runbook; adjusting SQS visibility timeouts and retry counts via configuration (no code change); escalating Redis or SQS infrastructure issues to AWS support; reading pipeline logs and metrics to diagnose which component is failing.

E2's backup scope explicitly excludes: modifying routing logic or priority classification code; changing deduplication key generation; modifying worker concurrency or batching parameters in code; any schema migration on the notifications database.

If E1 leaves and a situation requires work outside E2's defined scope, the correct response is to freeze the affected component, document the needed change, and address it after the team stabilizes. If E1 leaves during active pipeline development, that work's timeline slips. That is the honest consequence of a 4-person team.

---

## 3. System Architecture

### 3.1 SQS FIFO: Message Group ID Strategy and Head-of-Line Blocking

**The grouping scheme from prior revision:** `group_id = user_id % 100` — 100 groups per queue.

**The head-of-line blocking problem:** With 3M DAU and 100 groups, each group contains approximately 30,000 active users. SQS FIFO guarantees in-order, one-at-a-time processing *within a message group* — the next message in a group is not delivered until the previous message's visibility timeout expires or it is deleted. A single slow message blocks all other messages in that group for the duration of its visibility timeout. At 30,000 users per group, this is a routine occurrence whenever any downstream call is slow.

**Resolution: Validate before committing, then define migration procedure before go-live.**

**Validation (Month 1, E1):** Before the production queue is created, run a load test against a staging SQS FIFO queue at 2× peak throughput (3,500 msg/sec) with 1,000 groups. Measure p50/p99 end-to-end latency per group, visibility timeout expiry rate, and whether AWS throttles at any point. If p99 latency per group exceeds 2 seconds at this load, move to 5,000 groups and retest. The production queue is not created until the group count is validated.

```
group_id = user_id % 1000   # Starting point for validation; confirmed before go-live
visibility_timeout = 15s    # See Section 3.2 for rationale
worker_concurrency = 20     # Per priority tier
```

**Migration procedure (defined before go-live):** If group count must change post-launch:
1. Create a new FIFO queue with the new group count
2. Route all new enqueues to the new queue; old queue continues draining
3. Wait for old queue to reach zero depth (CloudWatch alarm)
4. Decommission the old queue

This adds temporary operational complexity — two queues monitored during transition — but avoids reordering in-flight messages. Changing the group count on an active FIFO queue mid-stream changes which group ID a given user's messages hash to, potentially reordering in-flight messages for users who straddle the transition. This is not a free configuration change.

**Why not per-user group IDs?** Per-user group IDs would eliminate head-of-line blocking between users entirely. The cost is that SQS FIFO per-group sequencing metadata behavior at 3M active groups is not well-documented by AWS, and we have no empirical data for this pattern. 1,000 groups is a middle ground we can validate before launch.

### 3.2 Deduplication: Race Conditions and Worker-Layer Atomicity

#### Router Layer: Atomicity and the SQS-Failure Race Window

**Problem 1 — Race condition at the router layer:** The router checks `dedup:{dedup_key}` in Redis and then, if absent, sets the key and enqueues to SQS. Two concurrent events for the same user/type/entity arriving within milliseconds can both read the key as absent before either write completes. The check-then-set is not atomic.

**Problem 2 — Race window on SQS failure:** When the Redis write succeeds but SQS enqueue fails, deleting the Redis key creates a window during which a concurrent caller can set the key and enqueue. Under SQS timeout conditions, this window spans the full SQS call timeout (up to 5 seconds with a 2s connect / 3s read timeout). Two messages with different `notification_id` values but the same logical notification can both reach workers.

**Fix:** Use Redis `SET NX` for the dedup write (atomic), carry `dedup_key` in the message body, and add a logical dedup check at the worker layer to catch the router-race case.

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

    notification_id = str(uuid.uuid4())  # Assigned once here, immutable
    message = NotificationMessage(
        notification_id=notification_id,
        event_id=event.event_id,
        logical_dedup_key=compute_dedup_key(event),  # Carried in message body
        # ... other fields
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
        # This creates a brief window where a concurrent caller can also enqueue.
        # The worker-layer logical dedup check (below) catches that case.
        await redis.delete(dedup_key)
        raise
```

#### Worker Layer: Two-Check Dedup and Atomicity

```python
# Check 1: Has this specific message been dispatched?
# Handles SQS redelivery after worker crash.
msg_acquired = await redis.set(
    f"sent:msg:{message.notification_id}", "1", ex=86400, nx=True
)
if not msg_acquired:
    return DispatchResult.ALREADY_DISPATCHED

# Check 2: Has any message for this logical notification been dispatched?
# Handles the router-layer race where two messages with different notification_ids
# represent the same logical notification.
logical_acquired = await redis.set(
    f"sent:logical:{message.logical_dedup_key}",
    message.notification_id,
    ex=86400,
    nx=True,
)
if not logical_acquired:
    return DispatchResult.ALREADY_DISPATCHED

# Both checks passed — proceed to dispatch
```

Both checks use `SET NX` and are atomic at the Redis level. Two concurrent workers racing on the same `notification_id` will have exactly one return `True`; the other receives `False` and discards.

#### The Hung-Call Scenario

A worker sets both Redis keys, begins dispatching to APNs/FCM, the call hangs, and the SQS visibility timeout expires before the worker deletes the message. A second worker picks up the same message, finds both Redis keys set, and discards. If the first worker's call eventually fails, the notification is silently dropped.

This is a known tradeoff, not a bug. The alternative — not setting Redis keys until after confirmed dispatch — means any worker crash between dispatch and SQS delete causes a duplicate send. For most notification types, a duplicate is worse UX than a missed notification. For P0 security alerts, the in-app write queue provides an independent delivery path not subject to this race.

**Mitigation:** Set FCM/APNs HTTP client timeout to 6 seconds total (connect: 2s, read: 4s) and SQS visibility timeout to 15 seconds. This provides a 9-second buffer. With a 6-second total timeout and a 15-second visibility timeout, the hung-call scenario requires the application-layer timeout to silently not fire — a bug in the HTTP client, not a latency tail event. That is a qualitatively different risk category.

```
Normal tail latency:
  t=0:    Worker picks up message, sets Redis keys
  t=6:    Application total timeout fires
  t=6.1:  Worker marks dispatch failed, deletes SQS message
  t=15:   Visibility timeout (never reached)
```

### 3.3 P0 In-App Write: Ordering Gap and the Backstop Guarantee

**The problem with two independent queues:** The prior revision routed P0 alerts to two independent SQS queues — one for push/email dispatch, one for in-app store writes. There is no ordering guarantee between them. A user who receives a push notification and opens the app may find no in-app record — not just for "the same second," but for however long the in-app writer queue is backed up. This directly undermines the stated purpose of the in-app record as a guaranteed backstop.

**The actual requirement:** The in-app record must exist before push delivery is attempted. If push delivery fails and the user opens the app to investigate, the record must already be there.

**Resolution:** The in-app write is performed by the push/email worker *before* any external dispatch call, within the same worker processing step.

```
P0 Security Alert — Worker Processing Order:

1. Worker dequeues message from p0-notifications.fifo
2. Worker writes in-app record to PostgreSQL (synchronous, within worker)
3. Worker dispatches push via APNs/FCM
4. Worker dispatches email via SendGrid
5. Worker deletes SQS message
```

The in-app write moves from the router's hot path (the concern in the prior revision) to the worker. Worker latency is not on the user-facing critical path — the worker runs asynchronously. A slow PostgreSQL write delays push dispatch by the duration of the write, not the user's experience. If the PostgreSQL write fails, the worker does not proceed to push dispatch; the SQS message is redelivered and the write is retried.

**What we give up:** A single worker now has two external dependencies (PostgreSQL and APNs/FCM). A PostgreSQL outage blocks P0 push delivery. This is acceptable: a database outage during a security event is a compound failure, and the DLQ alert (Section 3.4) ensures the on-call engineer is paged regardless.

**The in-app write is idempotent** using `INSERT ... ON CONFLICT DO NOTHING` on `notification_id`. SQS redelivery causing a second write attempt is safe.

### 3.4 Dead Letter Queue Configuration

DLQ depth threshold for P0 queues: alert at depth ≥ 1 (any failed P0 message pages on-call immediately). DLQ depth threshold for standard queues: alert at depth ≥ 50 (filters transient single-message failures from actionable alerts). DLQ retry count before routing to DLQ: 3 attempts. PagerDuty alert SLA: page fires within 60 seconds of DLQ message arrival.

---

## 4. Delivery Channels

### 4.1 Push Notifications

#### APNs Token Manager

```python
class APNsTokenManager:
    """
    JWT token manager shared across all APNs HTTP/2 connections.
    APNs enforces a hard 1-hour token expiry.
    Proactive refresh at 50 minutes (3,000 seconds).

    Thread safety: asyncio.Lock for the refresh critical section.
    Multiple concurrent callers waiting for a refresh all receive
    the same new token — only one refresh executes.
    """

    TOKEN_REFRESH_INTERVAL = 3000  # 50 minutes
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
        claims = {"iss": self._team_id, "iat": now}
        headers = {"alg": self.TOKEN_ALGORITHM, "kid": self._key_id}
        return jwt.encode(
            claims,
            self._private_key_pem,
            algorithm=self.TOKEN_ALGORITHM,
            headers=headers,
        )

    async def get_token(self) -> str:
        # Fast path: token is fresh, no lock needed
        if self._token_is_fresh():
            return self._token

        # Slow path: acquire lock and re-check inside the lock
        async with self._refresh_lock:
            # Re-check: another waiter may have refreshed while we waited
            if self._token_is_fresh():
                return self._token

            self._token = self._generate_token()
            self._token_generated_at = time.monotonic()
            return self._token
```

The double-check inside the lock is required. Without it, all callers queued behind the lock will each generate a new token sequentially after the first caller completes the refresh — producing N token generations when one is needed.

#### FCM Rate Limiter

FCM enforces per-project rate limits. The rate limiter must be shared state