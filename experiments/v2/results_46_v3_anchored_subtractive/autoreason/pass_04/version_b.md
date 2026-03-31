# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 5 — Addressing Concurrency, Architecture, and Specification Gaps

---

## Executive Summary

Revision 5 addresses eleven problems identified in the Revision 4 review. Three are concurrency correctness issues: the unquantified race window in the Redis-delete-on-SQS-failure path, the underacknowledged tail latency problem in the hung-call scenario, and the missing atomicity guarantee in the worker-layer dedup check. Three are architectural: the ordering gap between the two P0 queues undermining the in-app backstop guarantee, the unvalidated SQS FIFO group count, and the misleading "no code change" claim about group count migration. Two are operational: the undefined boundary of E2's "secondary familiarity," and the DLQ alert threshold misconfigured for normal operating conditions. Two are specification gaps carried forward from Revision 3 despite being listed as fixed: the P0 email escalation criteria and the OTP abandoned delivery cleanup. One is a literal truncation: the APNs token manager implementation ends mid-string in Revision 4.

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

SMS is capped at 100K/day. At 90K/day the system emits a warning alert. At 100K/day the system stops enqueuing new SMS messages, logs the drop with full event context, and routes affected events to email where the user has a verified address. Section 4.3 specifies this behavior in full.

---

## 2. Team Allocation

### 2.1 The Cross-Training Constraint

A 4-person team cannot fully cover all critical paths simultaneously. The goal is to ensure no single departure makes a component *unrecoverable* — not that every component has a full-time backup owner.

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (defined scope below) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM API layer only |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

### 2.2 Defining E2's Backup Scope for the Core Pipeline

Revision 4 said E2 could "maintain the pipeline in a steady state — keeping it running, handling incidents, making small changes" but did not define what "small changes" means. This matters because the boundary between incident response and a change requiring pipeline ownership is exactly what gets crossed during a real incident.

**E2's defined backup scope for the core pipeline covers:**

- Restarting failed workers and services
- Rolling back a deployment to the previous version using the existing runbook
- Adjusting SQS visibility timeouts and retry counts via configuration (no code change)
- Escalating Redis or SQS infrastructure issues to AWS support
- Reading pipeline logs and metrics to diagnose which component is failing
- Executing any runbook step that E4 owns for the monitoring layer

**E2's backup scope explicitly excludes:**

- Modifying routing logic or priority classification code
- Changing deduplication key generation
- Modifying worker concurrency or batching parameters in code
- Any schema migration on the notifications database

If E1 leaves and a situation requires work outside E2's defined scope, the correct response is to freeze the affected component at its current state, document the needed change, and address it after the team stabilizes — either by hiring or by explicitly descoping the change. The plan does not pretend E2 can own pipeline development. If E1 leaves during active pipeline development, the timeline for that work slips. That is the honest consequence of a 4-person team.

---

## 3. System Architecture

### 3.1 SQS FIFO Group Count: Validation Before Commitment

**The problem acknowledged in Revision 4:** The proposal chose 1,000 message groups without empirical data on SQS FIFO per-group throughput behavior at that scale, then described this as "conservative." A reviewer correctly identified that choosing a number without knowing whether it works is not conservatism — it is guessing.

**The additional problem identified in Revision 4 review:** The "revisable decision" framing was misleading. Changing group counts on an active FIFO queue mid-stream changes which group ID a given user's messages hash to, potentially reordering in-flight messages for users who straddle the transition. This is not a free configuration change.

**Resolution: Validate before committing, and define migration procedure before going live.**

**Validation (Month 1, E1):** Before the production queue is created, run a load test against a staging SQS FIFO queue at 2× peak throughput (3,500 msg/sec) with 1,000 groups. Measure: p50/p99 end-to-end latency per group, visibility timeout expiry rate, and whether AWS throttles at any point. If p99 latency per group exceeds 2 seconds at this load, move to 5,000 groups and retest. The production queue is not created until the group count is validated.

**Migration procedure (defined before go-live):** If group count must change post-launch, the procedure is:

1. Create a new FIFO queue with the new group count
2. Route all *new* enqueues to the new queue; old queue continues draining
3. Wait for the old queue to reach zero depth (monitored via CloudWatch alarm)
4. Decommission the old queue

This adds operational complexity — two queues must be monitored during the transition — but it avoids reordering in-flight messages. The complexity is bounded and temporary.

### 3.2 Deduplication: Corrected Race Analysis and Worker-Layer Atomicity

#### Router Layer: The Redis-Delete-on-SQS-Failure Race Window

Revision 4 acknowledged a race window when the Redis key is deleted after SQS failure but described it as "brief." A reviewer correctly noted that under SQS timeout conditions, this window includes the full SQS call timeout (configurable, typically 1–5 seconds) plus the Redis delete round-trip. This is not brief under load.

**The race is real and bounded as follows:**

- Window opens: Redis `SET NX` succeeds for caller A; SQS enqueue begins
- SQS call times out (up to the configured boto3 connect+read timeout, set to 2s connect / 3s read = 5s maximum)
- Redis delete executes (~1ms)
- Window closes: key is gone; a concurrent caller B can now set it and enqueue

**Maximum window duration: approximately 5 seconds.** During this window, a concurrent event with the same dedup key can be enqueued by caller B. The result is two SQS messages for the same logical notification. The worker-layer dedup (described below) catches this: both messages carry different `notification_id` values but the same `dedup_key`. Worker-layer dedup uses `notification_id`, so it does not catch this case directly.

**Fix: Add a second Redis key for in-flight tracking at the router layer.**

```python
async def deduplicate_and_enqueue(
    event: NotificationEvent,
    redis: Redis,
    sqs: SQSClient,
) -> EnqueueResult:
    dedup_key = f"dedup:{compute_dedup_key(event)}"
    inflight_key = f"inflight:{compute_dedup_key(event)}"

    # Step 1: Check and set the dedup key atomically.
    acquired = await redis.set(dedup_key, event.event_id, ex=300, nx=True)
    if not acquired:
        return EnqueueResult.DEDUPLICATED

    # Step 2: Set an in-flight marker before the SQS call.
    # This key exists only during the SQS call window.
    # TTL is set to 10s — longer than any reasonable SQS timeout.
    await redis.set(inflight_key, event.event_id, ex=10)

    notification_id = str(uuid.uuid4())
    message = NotificationMessage(
        notification_id=notification_id,
        event_id=event.event_id,
        dedup_key=compute_dedup_key(event),   # Carried in message body
        # ... other fields
    )

    try:
        await sqs.send_message(
            QueueUrl=priority_queue_url(event.priority),
            MessageBody=message.to_json(),
            MessageGroupId=str(event.user_id % 1000),
            MessageDeduplicationId=notification_id,
        )
        # Success: clear the in-flight marker; dedup key remains for 5 minutes.
        await redis.delete(inflight_key)
        return EnqueueResult.ENQUEUED

    except SQSError:
        # SQS failed. Delete both keys so the event can be retried.
        await redis.delete(dedup_key)
        await redis.delete(inflight_key)
        raise
```

**At the worker layer:** Workers check the `inflight_key` in addition to `sent:{notification_id}`. If `inflight_key` is present, the event is still being processed by the router — the worker discards and lets SQS redeliver after visibility timeout. This does not fully close the race (the inflight_key TTL is 10s, not infinite), but it reduces the effective race window from ~5 seconds to the time between the router's Redis delete and the worker's check — typically under 100ms.

**The residual risk:** Under the described failure mode (SQS timeout, Redis delete, concurrent enqueue), two messages with different `notification_id` values can both reach workers. The worker-layer `sent:{dedup_key}` check (distinct from `sent:{notification_id}`) catches this:

```python
# Worker layer — two checks, in order:

# Check 1: Has this specific message been dispatched? (handles SQS redelivery)
msg_dedup_key = f"sent:msg:{message.notification_id}"
msg_acquired = await redis.set(msg_dedup_key, "1", ex=86400, nx=True)
if not msg_acquired:
    return DispatchResult.ALREADY_DISPATCHED

# Check 2: Has any message for this logical notification been dispatched?
# (handles the router-layer race where two messages with different IDs
# represent the same logical notification)
logical_dedup_key = f"sent:logical:{message.dedup_key}"
logical_acquired = await redis.set(logical_dedup_key, message.notification_id, ex=86400, nx=True)
if not logical_acquired:
    return DispatchResult.ALREADY_DISPATCHED

# Both checks passed — proceed to dispatch
```

Both checks use `SET NX` and are therefore atomic. The two-check structure means: even if the router race produces two messages with different `notification_id` values, the second worker to process either message finds `sent:logical:{dedup_key}` already set and discards.

#### Worker Layer: The Visibility-Timeout Race

A reviewer identified that two workers can both read `sent:{notification_id}` as absent if the SQS visibility timeout expires at the exact moment a second consumer picks up the message. Revision 4 applied `SET NX` to the router layer but described the worker check conceptually without explicitly guaranteeing atomicity.

The worker code above uses `SET NX` for both checks. This is explicit. The atomicity guarantee is the same as the router layer: `SET NX` is a single Redis command and is atomic at the Redis level. Two concurrent workers racing on the same `notification_id` will have exactly one return `True` from `SET NX`; the other receives `False` (already set) and discards.

#### The Hung-Call Scenario: Revised Assessment

Revision 4 described the scenario where a worker sets `sent:{notification_id}`, begins dispatching to APNs/FCM, the call hangs, and the visibility timeout expires before the worker deletes the SQS message. Revision 4 claimed this was rare because FCM/APNs timeouts (5 seconds) were well under the visibility timeout (10 seconds). A reviewer correctly noted that cumulative latency — connection establishment, TLS handshake, DNS resolution, HTTP/2 connection pool queuing — can push total call time beyond 10 seconds without the application-layer timeout triggering.

**Revised assessment:** This scenario is not rare. It is a normal tail latency event. The question is not how to prevent it but what the consequence is and whether the consequence is acceptable.

**Consequence:** Worker A sets `sent:msg:{notification_id}` and `sent:logical:{dedup_key}`, begins the APNs call. The visibility timeout expires. Worker B picks up the same message, finds both Redis keys set, and discards. Worker A's APNs call eventually completes — either successfully (the notification was delivered) or with a failure (the notification was not delivered). If it completes successfully, the outcome is correct. If it fails, the notification is silently dropped: the SQS message has been discarded by Worker B, and the Redis keys prevent any future worker from retrying.

**This is a known tradeoff, not a bug.** The alternative — not setting the Redis keys until after confirmed dispatch — means any worker crash between dispatch and SQS delete causes a duplicate send. For most notification types (likes, comments, follows), a duplicate is worse UX than a missed notification. For security alerts (P0), the in-app write queue provides an independent delivery path that is not subject to this race.

**Mitigation:** Set the FCM/APNs HTTP client timeout to 6 seconds total (connect: 2s, read: 4s) and the SQS visibility timeout to 15 seconds. This provides a 9-second buffer between the application-layer timeout and the SQS redelivery trigger. The buffer covers TLS handshake (~100–300ms), DNS (~50ms), and HTTP/2 connection pool queuing under load (~500ms at p99 based on FCM latency data). It does not cover pathological conditions (network partition, FCM regional outage), which are handled by the circuit breaker described in Section 4.1.

```
Timeline under normal tail latency:
  t=0:     Worker A picks up message, sets Redis keys
  t=0.5:   Connection established, TLS complete
  t=1:     HTTP/2 request sent
  t=5:     Application read timeout fires (no response)
  t=5.001: Worker A marks dispatch as failed, deletes SQS message, records failure
  t=15:    Visibility timeout would have triggered (never reached)

Timeline under pathological condition (FCM regional outage):
  t=0:     Worker A picks up message, sets Redis keys
  t=6:     Application total timeout fires
  t=6.001: Worker A marks dispatch as failed, deletes SQS message, records failure
  t=15:    Visibility timeout would have triggered (never reached)
```

With a 6-second total timeout and a 15-second visibility timeout, the hung-call scenario requires the total timeout to silently not fire — a bug in the HTTP client, not a latency distribution tail event. This is a qualitatively different risk category.

### 3.3 P0 In-App Write: Ordering Gap and the Backstop Guarantee

**The problem from Revision 4 review:** The two-queue P0 routing (push/email queue and in-app queue as independent SQS queues) has no ordering guarantee between them. A user who receives a push notification and immediately opens the app may find no in-app record — not just for "the same second" as Revision 4 claimed, but for however long the in-app writer queue is backed up. This directly undermines the stated purpose of the in-app record as a guaranteed backstop.

**Restating the actual requirement:** The in-app record is