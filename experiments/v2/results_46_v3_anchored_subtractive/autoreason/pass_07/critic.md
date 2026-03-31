## Real Problems Found

### 1. The `signal` module is used but never imported

In `make_thread_watchdog`, `_force_kill` calls `os.kill(os.getpid(), signal.SIGTERM)`. The `signal` module is not in the import block at the top of the code sample. This will raise a `NameError` at runtime, in the exact failure path where it matters most — when the event loop is permanently deadlocked and graceful cancellation has already failed.

---

### 2. The watchdog's 2-second grace period is ungrounded

The timer gives the event loop 2 seconds to process the cancellation before calling `_force_kill`. This number has no derivation. The proposal is meticulous about deriving every other threshold from a requirement or measurement. This one is not. If the event loop is genuinely deadlocked, 2 seconds is irrelevant. If it is temporarily overloaded, 2 seconds may be insufficient. There is no stated basis for it.

---

### 3. `asyncio.shield` defeats the stated purpose of `asyncio.wait_for`

The code wraps `dispatch_fn(message)` in `asyncio.shield` before passing it to `asyncio.wait_for`. `asyncio.shield` explicitly prevents the inner task from being cancelled when the outer future times out. This means when `wait_for` raises `TimeoutError`, the underlying HTTP/2 call continues running in the background, still holding the event loop's I/O handles. The proposal identifies a hung stream as the primary failure mode. `asyncio.shield` ensures that after a timeout, the hung coroutine is still running. The watchdog is then racing against a task that was supposed to have been cancelled but wasn't.

---

### 4. The SIGTERM handler behavior on process kill is unspecified

When `_force_kill` sends `SIGTERM` to the worker process, the proposal does not state what happens next. If the process is running inside ECS, SIGTERM triggers the container shutdown sequence. If there are other in-flight messages being processed by other coroutines in the same worker, they are dropped without a `dispatch_outcome` log entry. The alarm defined in Finding 9 would fire, but the messages are already lost. The proposal acknowledges this class of problem for the hung-call case but not for the collateral damage to co-resident messages during process termination.

---

### 5. The attack ramp rate is borrowed from a different company's incident

The SMS alarm threshold derivation relies on a ramp rate of 16/sec/minute from a 2023 Twilio postmortem at "a comparable service." The proposal then uses this rate as if it were measured data from this system. The actual ramp rate an attacker achieves against this specific app depends on factors specific to this app: rate limiting at the API layer, CAPTCHA friction, account verification requirements, and the attacker's tooling. A faster ramp invalidates the entire threshold calculation. The proposal acknowledges this in one sentence but does not quantify the risk — it states only that a Lambda fires above 800/sec, without deriving whether 800/sec is a safe secondary threshold either.

---

### 6. The Lambda that auto-lowers the SMS cap is tested quarterly but has no stated correctness criteria

The proposal says the Lambda "automatically lowers the SMS cap to 10K/day" above 800/sec and is "tested quarterly." There is no definition of what a passing test looks like. Does it verify that the cap change propagates within the 25-minute response window? Does it verify idempotency if it fires multiple times? Does it verify that it doesn't trigger during legitimate volume spikes? A test with no pass criteria is not a test.

---

### 7. E2's backup scope creates an unacknowledged gap for APNs and FCM API-layer failures

The table states E2's backup is covered by "E1 on APNs/FCM API layer only." But E1's primary responsibility is "core pipeline: SQS infrastructure, routing logic, delivery workers." The proposal does not describe how deeply E1 knows the APNs/FCM integration layer — token refresh logic, HTTP/2 connection pooling, provider-specific error code handling. Stating coverage in the table does not establish that E1 can actually diagnose and resolve an APNs certificate expiry or an FCM token invalidation wave at 2am. The table asserts coverage; it does not demonstrate it.

---

### 8. The P1 blocking probability calculation ignores group assignment skew

The pass criteria derivation calculates the probability of 3 consecutive slow messages in a group as (0.01)³ and calls it negligible. This assumes slow messages are uniformly distributed across groups. If slow messages are caused by a specific provider failure (e.g., APNs timing out for a subset of device tokens associated with a specific app version), slow messages will cluster in the same groups — because group assignment is presumably based on user or notification type, not random. The independence assumption is violated precisely in the failure modes that matter.

---

### 9. The proposal ends mid-sentence

The document cuts off at "Derive `notification_id` deterministically from the event's stable fields" without completing the resolution for Finding 5. Finding 5 is listed in the executive summary as resolved. It is not resolved in the body. This means the retry deduplication problem — a worker crashes after setting the Redis key but before SQS enqueue succeeds — has no actual specified solution in this revision.