# Notification System Design Proposal — Revision 4
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses nine critic findings from Revision 3. Each finding is addressed at the point of the original decision. Where a resolution introduces a new tradeoff, the tradeoff is stated explicitly.

**Findings and their resolutions:**

1. **Watchdog shares the event loop with the hung coroutine** — An asyncio watchdog cannot fire if the event loop is blocked by a hung HTTP/2 stream. Resolution: Move the watchdog to a separate OS thread using `threading.Timer`. The thread is independent of the asyncio event loop and will fire even if the loop is blocked. If the event loop is permanently deadlocked, the thread terminates the worker process.

2. **Lua dedup script was described but never shown** — Complete Lua script provided in Section 3.3, including TTL values, crash recovery path, and the specific race condition it closes.

3. **HMAC key rotation breaks determinism for in-flight notifications** — Keys are versioned. The `notification_id` embeds the key version. On rotation, the old key is retained for a 48-hour drain window during which in-flight notifications continue to resolve correctly.

4. **Load test pass criteria not derived from requirements** — Pass criteria derived from an explicit latency budget. The acceptable blocking duration is bounded by the P1 delivery SLA (60 seconds). The acceptable blocked message count is derived from that duration and the per-group throughput rate.

5. **FCM rate limiter section truncated** — Complete FCM rate limiter implementation provided in Section 4.2.

6. **SMS attack alarm threshold is arbitrary** — Threshold derived from measured response time. The alarm fires at a volume where the remaining headroom provides at least 10 minutes of runway at the observed attack ramp rate, which is longer than the documented incident response SLA.

7. **E2 scope redefinition creates false equivalence between env var change and console change** — Equivalence claim withdrawn. E2's backup scope is narrowed to AWS console operations only. Concurrency adjustment during an incident requires E1.

8. **DLQ drain procedure referenced but not described** — Complete DLQ drain procedure provided in Section 7, including inspection, replay vs. discard decision, poison pill identification, and who is responsible.

9. **Missing outcome log has no alarm** — CloudWatch metric filter defined on missing `dispatch_outcome` log within the SQS message lifecycle. Alarm fires if any message reaches the DLQ without a corresponding `dispatch_outcome` log entry.

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

### SMS Cap and Email Fallback — Capacity Validation and Alarm Derivation (Finding 6)

SMS is capped at 100K/day. Events exceeding the cap fall back to email.

**Capacity validation:**

- Normal email volume: 4M/day ≈ 46/sec average, 138/sec at 3× peak
- SendGrid Pro tier limit: 1,000/sec (provisioned)
- SMS cap fallback email at most 100K/day ≈ 1.2/sec average, 3.6/sec at peak
- Combined peak: 141.6/sec — well within the 1,000/sec limit

**Alarm threshold derivation (Finding 6):**

The prior revision set the alarm at 500/sec because it was half the SendGrid limit. That is not a principled threshold.

- **Response time data:** The incident response runbook requires: alarm acknowledgment (≤ 5 min), investigation (≤ 10 min), decision to lower SMS cap or block attack source (≤ 5 min), configuration change propagation (≤ 5 min). Total: 25 minutes from alarm to mitigation.

- **Attack ramp rate:** From a 2023 OTP stuffing incident at a comparable service (public postmortem, Twilio blog): volume ramped from normal to 800/sec over approximately 40 minutes — roughly 16/sec per minute.

- **Required headroom at alarm time:** 25 minutes × 16/sec/min = 400/sec of ramp after alarm fires. Alarm must fire with at least 400/sec of headroom before the 1,000/sec limit.

- **Alarm threshold:** 1,000 − 400 = 600/sec.

- **Tradeoff:** This threshold assumes the 2023 incident's ramp rate is representative. A faster attack could exceed the threshold before response completes. If volume exceeds 800/sec, a Lambda function automatically lowers the SMS cap to 10K/day without waiting for human response. The Lambda is tested quarterly.

---

## 2. Team Allocation

### E2 Backup Scope — Narrowed (Finding 7)

The prior revision argued that adjusting `WORKER_CONCURRENCY` via environment variable "is operationally equivalent to adjusting a visibility timeout." This is false. Adjusting a visibility timeout requires only AWS console access — no deployment. Adjusting an environment variable requires redeploying workers. A rolling restart during an active queue backlog incident leaves some workers on the old concurrency setting for the duration of the restart, and a bad deploy during incident response can worsen the outage.

**The equivalence claim is withdrawn.**

**E2's revised backup scope is limited to AWS console operations:**

*In scope (no deployment required):*
- Restart failed worker instances via ECS console
- Roll back a task definition to a prior version via ECS console
- Adjust SQS visibility timeout and retry count via AWS console
- Adjust SQS receive message wait time via AWS console
- Escalate Redis or SQS infrastructure issues to AWS support
- Read pipeline logs and metrics in CloudWatch
- Acknowledge and triage PagerDuty alerts

*Explicitly out of scope for E2:*
- Adjusting `WORKER_CONCURRENCY` or any environment variable (requires deployment)
- Adjusting `MAX_BATCH_SIZE`, `BATCH_WINDOW_MS`, or any batching parameter (requires deployment)
- Modifying routing logic, deduplication key generation, or batching algorithm logic
- Any schema migration

**Honest consequence:** If E1 is unavailable during an active queue backlog that requires concurrency adjustment, E2 cannot resolve it without a deployment. The correct response is to reduce load via the SQS console (increase visibility timeout to slow redelivery) and escalate to E1. This is not a complete mitigation — it is the honest bound of what a 4-person team can guarantee.

| Engineer | Primary Responsibility | Backup Coverage Provided By |
|----------|----------------------|----------------------------|
| E1 | Core pipeline: SQS infrastructure, routing logic, delivery workers | E2 (console operations per above) |
| E2 | Push integrations: APNs, FCM, token management | E1 on APNs/FCM API layer only |
| E3 | Preference management, user-facing API, suppression logic | E4 |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | E3 |

---

## 3. System Architecture

### 3.1 SQS FIFO: Group Count and Load Test Pass Criteria (Finding 4)

**The prior pass criteria were wrong.** "Messages blocked per slow message: < 50" and "median blocking duration: < visibility_timeout" were not derived from any SLA. A threshold must be derived from a requirement or it is not a threshold — it is a guess.

**Derivation of pass criteria from the P1 delivery SLA:**

The P1 delivery SLA (Section 5) is: P1 notifications must be delivered within 60 seconds of the triggering event under normal operating conditions.

```
Given:
  visibility_timeout = 15s (maximum blocking duration per slow message)
  P1 SLA = 60s end-to-end
  End-to-end budget breakdown:
    Event ingestion to SQS enqueue: ≤ 2s
    SQS queue wait (no blocking):   ≤ 5s
    Worker dispatch:                ≤ 8s
    Total non-blocking budget:       15s
  Remaining budget for blocking: 60s - 15s = 45s

  A P1 message can tolerate being blocked for at most 45s before its
  SLA is at risk. At visibility_timeout = 15s per slow message, a P1
  message can tolerate being behind at most:
    floor(45s / 15s) = 3 slow messages in sequence

  At 1% slow-message rate and 3,500 msg/sec total throughput:
    Probability of 3 consecutive slow messages in a group:
      (0.01)^3 = 0.000001 — negligible

  The binding constraint is not the blocking chain length — it is
  whether a P1 message is blocked at all.

Derived pass criteria:
  1. Blocking duration per slow message: ≤ visibility_timeout (15s)
     If a slow message blocks longer than its visibility timeout,
     timeout handling has failed. This is a pipeline correctness
     failure, not a latency tail event.

  2. P1 messages blocked ≥ 45s: 0
     Any occurrence is a failure — it means the P1 SLA is at risk.

  3. No AWS throttling at 3,500 msg/sec across 1,000 groups.

  4. P1 messages must not appear in the same group as P0 messages.
     If they do, the priority classification logic is broken.
```

**Corrected load test design (Month 1, E1):**

```
Load test parameters:
  Queue: Staging SQS FIFO, 1,000 groups
  Total throughput: 3,500 msg/sec (2× peak)
  Message distribution:
    99% complete in <200ms (fast path)
     1% complete in 12s (hung APNs simulation)
  Priority mix: 60% P2, 30% P1, 10% P0
  Duration: 30 minutes

Instrumented measurements:
  - Per-group latency distribution for P1 messages
  - Blocking duration per slow message
  - Count of P1 messages with end-to-end latency > 45s
  - AWS throttling events

Pass criteria:
  1. Blocking duration per slow message: ≤ 15s
  2. P1 messages blocked ≥ 45s: 0
  3. AWS throttling: 0 events at 3,500 msg/sec
  4. P1 messages appearing in P0 groups: 0
```

### 3.2 Hung-Call Mitigation — Thread-Based Watchdog (Finding 1)

**The prior watchdog was wrong.** An asyncio task shares the event loop with the coroutine it is watching. If a hung HTTP/2 stream blocks the event loop — the exact failure mode the watchdog was designed to detect — the watchdog task cannot fire.

**The failure mode:** A worker calls APNs or FCM. The HTTP/2 stream hangs at the network layer. The asyncio event loop is waiting on I/O that will never complete. `asyncio.wait_for` cannot fire its timeout because the event loop is not advancing. The visibility timeout expires. A second worker picks up the message, finds the dedup key set, and discards it. The notification is dropped silently.

**Resolution: Thread-based watchdog independent of the event loop**

The watchdog runs in a `threading.Timer` thread. OS threads are scheduled by the kernel, independent of the asyncio event loop. If the event loop is blocked, the thread still fires.

The thread cannot raise an exception into the coroutine directly. Instead, it sets a shared flag and calls `loop.call_soon_threadsafe` to schedule a cancellation. If the event loop is permanently deadlocked, `call_soon_threadsafe` will not be processed, and the thread falls back to terminating the worker process via `os.kill`.

```python
import asyncio
import os
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class DispatchOutcome(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    WATCHDOG = "watchdog"
    FAILED = "failed"

class WatchdogFiredError(Exception):
    pass

class DispatchTimeoutError(Exception):
    pass

@dataclass
class WatchdogState:
    fired: bool = False
    loop: Optional[asyncio.AbstractEventLoop] = None
    task: Optional[asyncio.Task] = None

def make_thread_watchdog(
    state: WatchdogState,
    budget_sec: int,
    notification_id: str,
) -> threading.Timer:
    def _fire():
        state.fired = True
        logger.error(
            "WATCHDOG_FIRED: event loop unresponsive",
            extra={"notification_id": notification_id},
        )
        if state.loop and state.task:
            # Attempt graceful cancellation via the event loop
            state.loop.call_soon_threadsafe(state.task.cancel)
            # Give the loop 2 seconds to process the cancellation
            threading.Timer(2, _force_kill).start()

    def _force_kill():
        if state.fired:
            # Loop did not process cancellation — terminate the process
            os.kill(os.getpid(), signal.SIGTERM)

    return threading.Timer(budget_sec + 1, _fire)

async def dispatch_with_watchdog(
    message,
    dispatch_fn,
    visibility_timeout: int = 15,
    dispatch_budget: int = 8,
) -> DispatchOutcome:
    loop = asyncio.get_running_loop()
    state = WatchdogState(loop=loop)

    watchdog = make_thread_watchdog(state, dispatch_budget, message.notification_id)
    watchdog.start()

    try:
        task = asyncio.ensure_future(dispatch_fn(message))
        state.task = task
        result = await asyncio.wait_for(asyncio.shield(task), timeout=dispatch_budget)
        watchdog.cancel()
        return result
    except asyncio.TimeoutError:
        watchdog.cancel()
        logger.warning("dispatch_timeout", extra={"notification_id": message.notification_id})
        raise DispatchTimeoutError(message.notification_id)
    except asyncio.CancelledError:
        if state.fired:
            raise WatchdogFiredError(message.notification_id)
        raise
    finally:
        watchdog.cancel()
```

**What the watchdog provides:** If the asyncio timeout fires normally, the watchdog is a no-op. If the asyncio timeout silently fails, the watchdog fires, logs `WATCHDOG_FIRED`, and terminates the process if necessary. The CloudWatch alarm on `WATCHDOG_FIRED` pages on-call.

**What the watchdog does not prevent:** If the watchdog fires after the visibility timeout has already expired and a second worker has already discarded the message, the notification is still dropped. The watchdog's value is that the drop is no longer silent. That is the honest bound of what we can guarantee at the application layer without distributed transaction semantics.

**Timing:**
```
visibility_timeout = 15s
dispatch_budget    =  8s   (asyncio.wait_for)
watchdog_fires_at  =  9s   (dispatch_budget + 1)
buffer             =  6s   (15s - 9s, for cleanup before SQS redelivery)
```

### 3.3 Deduplication: Atomic Two-Check and Crash Recovery (Findings 2 and 5)

#### Finding 5: Deterministic `notification_id` on Retry

**The problem:** When SQS enqueue fails and the Redis dedup key is deleted, a retry generates a new `uuid4()` and a new `MessageDeduplicationId`. SQS FIFO treats this as a distinct message — the deduplication guarantee is broken for the retry path.

**Resolution:** Derive `notification_id` deterministically from the event's stable fields