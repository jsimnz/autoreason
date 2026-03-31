# Notification System Design Proposal — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 2. The findings and their resolutions:

1. **Hung-call mitigation mischaracterized** — The 9-second buffer argument was wrong. TCP half-open connections and HTTP/2 stream hangs can defeat application-layer timeouts. Resolution: watchdog task with independent timer, plus mandatory outcome logging before SQS delete.
2. **Two-check dedup race between Check 1 and Check 2** — A worker crashing between the two `SET NX` calls leaves a permanently set `sent:msg` key for a notification that was never dispatched. Resolution: Lua script making both checks atomic, plus a TTL-based recovery path.
3. **P0 in-app write conflates outage with slowness** — PostgreSQL degradation causes visibility timeout expiry before worker completion, exhausting retries without clear signal. Resolution: Separate visibility timeout for P0 workers, plus a slow-write circuit breaker.
4. **Staging load test does not validate the actual problem** — Uniform artificial messages do not surface head-of-line blocking from slow-message distributions. Resolution: Inject synthetic slow messages at a realistic rate to measure blocking duration directly.
5. **`notification_id` inconsistency on retry** — A failed SQS enqueue deletes the Redis dedup key; retry generates a new `uuid4()` and a new `MessageDeduplicationId`, undermining FIFO dedup. Resolution: Derive `notification_id` deterministically from the event's stable fields.
6. **FCM rate limiter section truncated** — The section cut off mid-sentence. Resolution: Complete implementation provided.
7. **E2 backup scope excludes most common incident response** — E2 cannot modify worker concurrency in code, which is the primary response to queue backlog. Resolution: Concurrency is a configuration parameter, not a code change; scope redefined accordingly.
8. **SMS-to-email fallback unvalidated against email capacity** — The fallback assumes email headroom that was never checked. Resolution: Explicit capacity check; fallback bounded and monitored.
9. **Migration zero-depth alarm may never fire** — Poison-pill or DLQ-stuck messages prevent queue depth reaching zero. Resolution: Migration procedure now drains the DLQ explicitly before decommissioning.

Each resolution appears at the point of the original decision. Where a resolution introduces a new tradeoff, the tradeoff is stated.

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

### SMS Cap and Email Fallback — Capacity Validation (Finding 8)

SMS is capped at 100K/day. The fallback routes affected events to email.

**Validation that the fallback is within email capacity:**

- Normal email volume: 4M/day ≈ 46/sec average, 138/sec at 3× peak
- SendGrid Pro tier limit: 1,000/sec (provisioned)
- SMS cap events routed to email: at most 100K/day ≈ 1.2/sec average, 3.6/sec at peak
- Combined peak: 138 + 3.6 = 141.6/sec — well within the 1,000/sec SendGrid limit

The fallback is bounded and validated. However, if SMS volume reaches the cap because of a security event (e.g., mass OTP requests from an attack), email volume may spike non-linearly. A CloudWatch alarm fires when fallback email volume exceeds 500/sec (half the SendGrid limit), triggering a manual review of whether the SMS cap itself should be lowered or the attack surface addressed.

---

## 2. Team Allocation

### E2 Backup Scope — Redefined (Finding 7)

The prior revision excluded "modifying worker concurrency or batching parameters in code" from E2's backup scope. The critic correctly identified that queue backlog — the most common production incident — requires adjusting worker concurrency, and that E2 was therefore unable to respond to the most routine failure mode.

**Resolution:** Worker concurrency is not a code change. It is an environment variable (`WORKER_CONCURRENCY`) read at startup. E2's backup scope now includes adjusting this variable and redeploying workers via the existing deployment runbook. This is operationally equivalent to adjusting a visibility timeout — a configuration operation, not a code modification.

The revised exclusion list removes "worker concurrency" and retains the exclusions that genuinely require code understanding: routing logic, deduplication key generation logic, schema migrations, and batching algorithm changes.

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (revised scope below) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM API layer only |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

**E2's revised backup scope for the core pipeline:**

*In scope:*
- Restart failed workers and services
- Roll back a deployment using the existing runbook
- Adjust `WORKER_CONCURRENCY` environment variable and redeploy workers
- Adjust SQS visibility timeouts and retry counts via AWS console or configuration (no code change)
- Adjust `MAX_BATCH_SIZE` and `BATCH_WINDOW_MS` environment variables and redeploy
- Escalate Redis or SQS infrastructure issues to AWS support
- Read pipeline logs and metrics to diagnose which component is failing

*Explicitly out of scope:*
- Modifying routing logic or priority classification code
- Changing deduplication key generation logic
- Modifying batching algorithm logic in code (adjusting parameters via env vars is in scope)
- Any schema migration on the notifications database

If E1 leaves and a situation requires work outside E2's defined scope, the correct response is to freeze the affected component and address it after the team stabilizes. This is the honest consequence of a 4-person team.

---

## 3. System Architecture

### 3.1 SQS FIFO: Group Count Validation — Corrected Load Test (Finding 4)

**The prior validation approach was wrong.** Running a load test with uniform artificial messages at 1,000 groups measures aggregate throughput and AWS throttling behavior. It does not measure head-of-line blocking, which is caused by the distribution of slow messages within groups, not by total message volume. A test where every message completes in 5ms will show excellent p99 latency at any group count and will not surface the pathological case.

**What we are actually trying to measure:** If a slow message (say, a 12-second APNs call) lands in a group, how many other users in that group are delayed, and for how long?

**Corrected load test design (Month 1, E1):**

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
  - Whether AWS delivers subsequent messages in the group before
    the slow message's visibility timeout expires (it should not)
```

**Pass criteria:**
- Median blocking duration per slow message: < visibility_timeout (15s)
- Messages blocked per slow message: < 50 (approximately 1.7% of a group's daily volume)
- No AWS throttling at 3,500 msg/sec

**If the test reveals unacceptable blocking:** The correct fix is not to increase group count further (which reduces blocking duration but not frequency). It is to set a shorter visibility timeout and ensure the application-layer timeout is reliably shorter than the visibility timeout. This is addressed in Section 3.2.

**Why not per-user group IDs?** Per-user group IDs eliminate inter-user blocking entirely. The cost is that SQS FIFO behavior with millions of distinct message group IDs is not documented by AWS, and we have no empirical data for this pattern. We do not use it until we have that data.

### 3.2 Hung-Call Mitigation — Corrected Analysis (Finding 1)

**The prior analysis was wrong.** The claim that the 9-second buffer (15s visibility timeout minus 6s HTTP timeout) makes the hung-call scenario require "a bug in the HTTP client" is incorrect. TCP half-open connections after network partitions, HTTP/2 stream-level hangs where the connection is alive but the stream produces no data, and proxy-level timeouts that terminate the connection without notifying the application layer can all cause the application-layer timeout to silently not fire. These are production failure modes, not hypothetical bugs.

**The actual risk:** A worker sets both Redis dedup keys, begins an APNs/FCM call, the call hangs indefinitely, the visibility timeout expires, a second worker picks up the message, finds both dedup keys set, and discards. The notification is dropped silently. The first worker eventually completes or is killed, but the notification was never delivered and no alert fires.

**Resolution: Watchdog task with independent timer**

```python
async def dispatch_with_watchdog(
    message: NotificationMessage,
    dispatch_fn: Callable,
    visibility_timeout: int = 15,
    dispatch_budget: int = 8,  # Must be < visibility_timeout
) -> DispatchResult:
    """
    Runs dispatch_fn with two independent timeout mechanisms:
    1. asyncio timeout on the dispatch call itself
    2. Watchdog task that fires independently of the dispatch coroutine

    If the asyncio timeout fires normally, the watchdog is cancelled.
    If the asyncio timeout silently fails (e.g., hung HTTP/2 stream),
    the watchdog fires at dispatch_budget + 1 seconds and logs a
    WATCHDOG_FIRED event, which pages on-call.

    The watchdog does not retry — it only logs and raises so the
    caller can handle cleanup. Retry is handled by SQS redelivery.
    """
    watchdog_fired = asyncio.Event()

    async def watchdog():
        await asyncio.sleep(dispatch_budget + 1)
        watchdog_fired.set()
        # This log line triggers a CloudWatch alarm → PagerDuty
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
        # Normal timeout path — asyncio timeout fired correctly
        logger.warning(
            "dispatch_timeout: asyncio timeout fired within budget",
            extra={"notification_id": message.notification_id}
        )
        raise DispatchTimeoutError(message.notification_id)
    except WatchdogFiredError:
        # Watchdog fired — asyncio timeout did not fire correctly.
        # This is an infrastructure-level problem, not a latency tail event.
        raise

async def worker_process_message(message: NotificationMessage, sqs, redis):
    # Acquire dedup locks (Section 3.3)
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
        # Outcome is logged before SQS delete, always.
        # A missing outcome log means the worker was killed between dispatch and finally —
        # a signal that the message may need manual inspection in the DLQ.
        if outcome is not None:
            logger.info(
                "dispatch_outcome",
                extra={"notification_id": message.notification_id, "outcome": outcome}
            )
        # SQS delete only happens if we have a definitive outcome.
        # If outcome is None (worker killed in finally block), SQS redelivers.
        if outcome == DispatchOutcome.SUCCESS:
            await sqs.delete_message(message.receipt_handle)
        # On failure, do not delete — let SQS redeliver up to retry_count,
        # then route to DLQ.
```

**What the watchdog provides:** If the asyncio timeout fires normally, the watchdog is a no-op. If the asyncio timeout silently fails, the watchdog fires one second later, logs `WATCHDOG_FIRED`, and raises. The CloudWatch alarm on `WATCHDOG_FIRED` pages on-call. The on-call engineer investigates the hung connection and the notification is retried via SQS redelivery.

**What the watchdog does not provide:** The watchdog does not prevent the hung-call silent drop scenario. If the watchdog fires after the visibility timeout has already expired and a second worker has already discarded the message, the notification is still dropped. The watchdog's value is that the drop is no longer silent — it is logged and paged. That is the honest bound of what we can guarantee at the application layer without distributed transaction semantics.

**Visibility timeout and budget:**

```
visibility_timeout = 15s   (SQS)
dispatch_budget    = 8s    (asyncio.wait_for)
watchdog_fires_at  = 9s    (dispatch_budget + 1)
buffer             = 6s    (15s - 9s)
```

This provides 6 seconds between watchdog fire and visibility timeout expiry — enough for the watchdog to log, raise, and the worker to clean up before SQS redelivers.

### 3.3 Deduplication: Atomic Two-Check and Crash Recovery (Findings 2 and 5)

#### Finding 5: Deterministic `notification_id` on Retry

**The problem:** When SQS enqueue fails and the Redis dedup key is deleted, a retry generates a new `uuid4()`. This produces a new `MessageDeduplicationId`, which SQS FIFO treats as a distinct message — the deduplication guarantee is broken for the retry path.

**Resolution:** Derive `notification_id` deterministically from the event's stable fields using a keyed hash. The same event always produces the same `notification_id`, regardless of how many times it is retried.

```python
import hashlib
import hmac

NOTIFICATION_ID_KEY = b"<secret-key-from-secrets-manager>"  # 32 bytes, rotated annually

def derive_notification_id(event: NotificationEvent) -> str:
    """
    Deterministic notification_id derived from stable event fields.
    Same event → same notification_id → same MessageDeduplicationId.

    Uses HMAC-SHA256 to prevent notification_id prediction from event fields.
    The key is loaded from AWS Secrets Manager at startup.

    Fields included: event_id, user_id, event_type, entity_id, channel.
    Fields excluded: timestamp (not stable across retries