## Real Problems Found

### 1. Health File Race Condition on Publisher Restart

The healthcheck detects staleness after `MAX_STALENESS_SECONDS = 180`, but the publisher loop interval is not specified in the visible portion of the document. If the publish interval is 60 seconds and the health file is written only on *successful* CloudWatch publish, a single transient CloudWatch failure will cause the health file to age past 180 seconds (3 missed writes) and trigger an ECS restart. This means a brief CloudWatch hiccup causes a publisher restart rather than a retry, potentially creating a restart loop during exactly the conditions (elevated traffic, AWS service stress) when the publisher most needs to be stable.

### 2. The Failure Detection Table Has a Silent Undetected Failure

The table row "DynamoDB read fails (caught in `_get_current_cap`)" explicitly states the health file does *not* go stale and ECS does *not* restart. This means if the cap value cannot be read from DynamoDB, the publisher continues emitting metrics — but what value does it emit? The document doesn't say. If it emits a stale cached value, CloudWatch alarms are fed incorrect data silently. If it emits zero, alarms may fire incorrectly. The document acknowledges this failure mode is undetected but does not state what the published value actually is in this case.

### 3. `essential: true` Creates a New Availability Problem

The document argues `essential: true` is safe because "there is no worker process on the same task to disrupt." But the publisher is now a *single task* for the entire cluster. With `essential: true` and ECS's restart behavior, a crashing publisher that fails its health check repeatedly will be stopped and restarted in a loop. During this loop, CloudWatch gets no metrics. The document acknowledges graphs go dark but treats this as acceptable. However, the INSUFFICIENT_DATA alarm state is the *only* signal to on-call that the publisher is down — and INSUFFICIENT_DATA is a passive state, not an active alert. The document does not specify that an alarm is configured to page on INSUFFICIENT_DATA transitions for SMS consumption alarms.

### 4. The 48-Hour TTL Argument Is Cut Off Mid-Sentence

The document ends abruptly: "After 48 hours, the key is" — the sentence is incomplete. Finding 7 in the executive summary states "The document has been read from start to finish, including the last sentence of every section, before submission." This is directly falsified by the document's own content. This is the same defect as Revision 10 Finding 1 and Revision 10 Finding 7, now in its third consecutive revision.

### 5. INCR Plus EXPIRE Is Not Atomic

The `_increment_consumed` function calls `redis_client.incr(key)` and then conditionally calls `redis_client.expire(key, 172800)` in a separate round trip. Between these two calls, a Redis failover, network partition, or process crash can leave the key without a TTL permanently. The document describes this as a "hygiene problem" when the TTL is missing, but the fix it implements does not actually guarantee the TTL is set — it only attempts to set it when `new_value == 1`. If that second call fails, the key has no TTL and the hygiene problem the fix was designed to solve remains.

### 6. The Quarterly AUTH Cap Review Schedule Is Internally Inconsistent

Section 2.2 states the review is scheduled at "end of months 1, 3, and 6 post-launch" — that is three reviews in six months, not quarterly. Quarterly would be months 3 and 6 (or 1, 4, and 7 if starting from month 1). This inconsistency is minor but the review schedule is load-bearing: it is the stated mechanism for catching AUTH volume growth before the sub-cap is exhausted. If the review cadence is ambiguous, it may not happen on schedule.

### 7. The Conditional Write Failure Path Pages On-Call But Provides No Time Bound

Section 2.1 states that if the DynamoDB conditional write fails because the total constraint would be violated, "the Lambda pages on-call immediately." There is no specification of Lambda timeout, retry behavior, or what happens to the SMS message that triggered the failed write. Does the message get dropped? Requeued? The dispatch worker presumably receives a failure response, but what it does with that is not specified. During an active attack this is the critical path.

### 8. The Publisher Healthcheck Has a Startup False-Positive Window

`startPeriod: 10` seconds is specified in the ECS health check definition. The healthcheck looks for `/tmp/publisher_last_success` and exits 1 if the file is not found. If the publisher takes longer than 10 seconds to complete its first cycle and write the health file — plausible if Redis or CloudWatch connections are slow at startup — the health check will fail during the grace period and ECS may count those failures toward the `retries: 3` limit. The document does not address whether the 10-second start period is sufficient for the publisher's actual initialization time.