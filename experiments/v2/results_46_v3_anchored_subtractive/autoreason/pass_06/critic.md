## Real Problems

### 1. The Watchdog Does Not Actually Solve the Stated Problem

The document correctly admits "the watchdog does not prevent the hung-call silent drop scenario" but then claims its value is that "the drop is no longer silent." However, the watchdog fires at 9 seconds and the visibility timeout is 15 seconds. If the asyncio timeout silently failed (the exact failure mode motivating the watchdog), the worker is still hung. The watchdog raises `WatchdogFiredError` inside the hung coroutine context, but a genuinely hung HTTP/2 stream may not yield control back to the event loop for the watchdog's exception to propagate. An asyncio watchdog task and the hung coroutine share the same event loop — if the event loop is blocked, the watchdog cannot fire either. The fix does not escape the failure mode it was designed to address.

### 2. The Lua Atomicity Fix Is Described But Never Shown

Finding 2 claims the resolution is a "Lua script making both checks atomic, plus a TTL-based recovery path." The document shows `atomic_dedup_check(message, redis)` called in the worker but never defines it. The Lua script — the entire substance of the fix — is absent. A reader cannot evaluate whether the race condition is actually closed, whether the TTL values are correct, or whether the recovery path handles the crash scenario described. This is the most technically complex fix in the document and it is entirely missing.

### 3. The HMAC Key Rotation Claim Is Unexamined

The document states the `NOTIFICATION_ID_KEY` is "rotated annually." Rotating the key changes the output of `derive_notification_id` for every event. Any in-flight notification at rotation time will produce a different `notification_id` on retry than it had before rotation, breaking the determinism guarantee the fix was designed to provide. The rotation procedure needed to be worked out and stated. Asserting annual rotation without addressing this is not a resolved finding — it is a deferred problem presented as solved.

### 4. The Load Test Pass Criteria Are Not Derived From Requirements

The corrected load test specifies "messages blocked per slow message: < 50" and "median blocking duration per slow message: < visibility_timeout (15s)." Neither threshold is connected to a user-facing requirement. Fifty blocked messages per slow message at 1% slow-message rate means roughly 35,000 delayed messages per day at stated push volume. Whether that is acceptable is never established. The pass criteria appear to be chosen to be passable, not because they protect a stated SLA.

### 5. The FCM Rate Limiter Fix Is Still Missing

Finding 6 in the executive summary states "complete implementation provided" for the truncated FCM rate limiter section. The document cuts off mid-sentence at the end of Section 3.3 before any FCM rate limiter content appears. The same truncation error from Revision 2 is present in Revision 3, and the executive summary falsely claims it was resolved.

### 6. The SMS Attack Scenario Alarm Threshold Is Arbitrary

The document sets a CloudWatch alarm at 500/sec fallback email volume (half the SendGrid limit) and calls this the trigger for manual review. There is no analysis of how quickly volume can rise from the alarm threshold to the SendGrid limit during an active attack, how long manual review and response takes, or whether 500/sec provides enough headroom for the response to complete before the limit is hit. The number 500 appears to have been chosen because it is round and below 1,000, not because it reflects response time data.

### 7. The E2 Scope Redefinition Creates a False Equivalence

The document argues that adjusting `WORKER_CONCURRENCY` "is operationally equivalent to adjusting a visibility timeout — a configuration operation, not a code modification." These are not equivalent. Adjusting a visibility timeout via the AWS console requires no deployment. Adjusting an environment variable requires a redeployment of workers. A redeployment during an active queue backlog incident has its own failure modes: rolling restart leaves some workers on the old concurrency setting, a bad deploy during incident response can worsen the outage. The equivalence claim papers over real operational risk introduced by making E2 responsible for deployments.

### 8. The DLQ Drain Procedure Is Referenced but Not Described

Finding 9 states the migration procedure "now drains the DLQ explicitly before decommissioning." No updated migration procedure appears in the document. There is no description of how DLQ messages are inspected, whether they are replayed or discarded, who makes that decision, or how poison pills are identified and handled separately from legitimately retryable messages. The resolution is stated in the executive summary and then absent from the body.

### 9. The `outcome = None` Handling Has a Silent Failure Mode

The worker code states: "If outcome is None (worker killed in finally block), SQS redelivers." But the condition for SQS delete is `if outcome == DispatchOutcome.SUCCESS` — failure and None both result in no delete. The comment says this is intentional. However, if a worker is killed repeatedly in the finally block (e.g., OOM kill during logging), the message will redeliver, hit the same OOM condition, exhaust retries, and route to the DLQ with no `dispatch_outcome` log and no `WATCHDOG_FIRED` log. The document claims the absence of an outcome log is "a signal that the message may need manual inspection," but there is no alarm defined on missing outcome logs. The signal exists only if someone is already looking.