## Real Problems

### 1. The Hung-Call "Mitigation" Is Inadequate

The proposal claims the hung-call scenario requires "a bug in the HTTP client, not a latency tail event" — but this is wrong. HTTP/2 stream-level hangs, half-open TCP connections after network partitions, and proxy timeouts can all cause application-layer timeouts to silently not fire in production environments. The proposal dismisses a real production failure mode by mischaracterizing it as a qualitatively different risk category. The 9-second buffer provides no actual protection if the timeout mechanism itself is what fails.

### 2. The Logical Dedup Check Has a Race Between Check 1 and Check 2

The two worker-layer Redis `SET NX` calls are individually atomic but not jointly atomic. Two concurrent workers processing different `notification_id` values for the same logical notification can both pass Check 1 (different keys), then race on Check 2. One wins Check 2 and dispatches. But between Check 1 and Check 2, if the losing worker crashes after passing Check 1, its `sent:msg:{notification_id}` key is set permanently, consuming a dedup slot for a notification that was never dispatched. This is a silent correctness hole the proposal does not acknowledge.

### 3. P0 In-App Write Creates a New Silent Failure Mode

The proposal states that if the PostgreSQL write fails, "the SQS message is redelivered and the write is retried." But after 3 DLQ attempts, the message routes to the DLQ and pages on-call. During a PostgreSQL degradation event — not a full outage — slow writes can cause the visibility timeout to expire before the worker completes, causing repeated redelivery that exhausts retries without a clear failure signal. The proposal conflates "PostgreSQL outage" with "PostgreSQL slow" and the 3-retry DLQ threshold is calibrated for fast failures, not slow ones.

### 4. The Staging Validation Does Not Validate the Actual Problem

The head-of-line blocking fix involves running a load test at 1,000 groups. But the original problem was identified at 100 groups with 30,000 users per group causing routine blocking. The load test measures p99 latency and throttling — it does not measure the actual head-of-line blocking characteristic, which depends on the distribution of slow messages within groups, not aggregate throughput. A load test with uniform artificial messages will not surface the real-world pathological case.

### 5. The `notification_id` Source Is Still Underspecified for Retry Scenarios

The proposal assigns `notification_id = str(uuid.uuid4())` at the router layer, and uses it as `MessageDeduplicationId`. But when SQS enqueue fails and the Redis key is deleted, a retry of the same event generates a new `uuid4()` — a different `notification_id` and a different `MessageDeduplicationId`. SQS FIFO deduplication is based on `MessageDeduplicationId`, so the retry is treated as a new message. The proposal does not acknowledge this: the retry path produces a notification_id that is inconsistent with the original attempt's dedup key, undermining the deduplication guarantee the system is built around.

### 6. The FCM Rate Limiter Section Is Truncated

The proposal cuts off mid-sentence: "The rate limiter must be shared state" — and then nothing. This is not a minor editorial issue. The FCM rate limiter was explicitly identified in the Executive Summary as containing a concurrency bug involving shared mutable state. The section that was supposed to address this bug is missing. The Executive Summary claims this is resolved; the body does not contain the resolution.

### 7. E2's Backup Scope Excludes the Most Likely Failure Scenarios

E2 cannot modify worker concurrency or batching parameters in code. But queue depth spikes — the most common production pipeline incident — frequently require exactly that. The defined scope allows E2 to adjust SQS visibility timeouts via configuration but not to change how fast workers consume from the queue. This means the most routine operational response to a backlog event is outside the defined backup scope, and the proposal's answer ("freeze the component") is not operationally viable during an active incident.

### 8. The SMS Cap Fallback to Email Is Not Validated Against Email Capacity

At 100K SMS/day the system routes affected events to email. The proposal does not check whether this is within email capacity. The email channel is estimated at 4M/day (~46/sec average). If SMS events spike to cap simultaneously with normal email load, the incremental email volume and its effect on SendGrid throughput or rate limits is unexamined. The fallback assumes email has headroom that is never verified.

### 9. The Migration Procedure Depends on a Zero-Depth Alarm That May Never Fire

The queue migration procedure waits for "old queue to reach zero depth (CloudWatch alarm)." SQS FIFO queues with poison-pill messages or messages in DLQ state do not reach zero depth automatically. If any message in the old queue is stuck — including in the DLQ — the migration procedure stalls indefinitely. The proposal does not address this case.