## Real Problems Found

### 1. Document ends mid-sentence again
The executive summary explicitly claims "Section 2.8 is completed" as a resolved finding. Section 2.5 cuts off in the middle of deriving the threshold — the same class of failure that was supposedly fixed. This is the third revision with this problem.

### 2. The "required input" dependency is unresolved but called launch-blocking without a process
Section 2.5 says the time-of-day threshold requires product team input and is "launch-blocking." No deadline, owner, or escalation path is specified. A launch-blocking dependency with no owner is not a resolved finding — it is an unresolved dependency with a warning label attached.

### 3. `_get_current_cap` instantiates a DynamoDB resource on every call
`_get_current_cap` creates a new `boto3.resource('dynamodb')` and `Table` object inside the function body. This runs every 60 seconds, per publisher instance, for the lifetime of the service. The connection overhead is unnecessary and the pattern will cause problems under load or if DynamoDB is slow, but more critically it means the publisher's DynamoDB dependency is invisible from the task definition — it has no IAM role reference, no timeout, and no error handling specific to DynamoDB failures.

### 4. AUTH sub-cap alarm thresholds are inconsistent with stated headroom
Section 2.2 states AUTH volume is 3–5K/day and 20K provides 4–6× headroom. Section 2.4 sets the first AUTH alarm at 80% (16K consumed). At normal volume of 5K/day, this alarm never fires under any realistic organic scenario. The alarm threshold is calibrated for a cap that is already nearly exhausted, not for detecting anomalous growth early enough to act.

### 5. `REDIS_CONNECTION_FAILURE` uses a metric that may not exist
The alarm definition lists `AWS/ElastiCache / CacheClusterStatus` and then immediately pivots to "or application-level metric." `CacheClusterStatus` is not a CloudWatch metric — it is a console status field. The alarm as written references a metric that cannot be configured in CloudWatch. The application-level alternative is defined only in prose, not implemented anywhere in the shown code.

### 6. The failure mode table has a logical error
The table shows "Redis fully failed" causes `PublisherHeartbeat` to go absent "after timeout." But the publisher code catches all exceptions and sleeps — it does not crash. If Redis fails but the publisher process is still running, the heartbeat continues to be emitted. `SMS_METRIC_PUBLISHER_DEAD` does not fire. The table contradicts the code.

### 7. The 3-minute publisher dead window claim is only valid with one worker task
The heartbeat alarm is defined as `Sum < 1` over 60 seconds. If there are multiple worker tasks, each running a publisher sidecar, the sum will remain above 1 even when most publishers are dead. The alarm as defined cannot detect partial publisher failure in a multi-task deployment, and the document makes no claim about task count while asserting a bounded 3-minute detection window.

### 8. Section 2.8 is referenced as completed in the executive summary but does not appear in the document
The executive summary lists Finding 2 as resolved and states "the 200-account attack calculation is carried through to a detection window estimate." Section 2.8 does not appear in the document at all. It was not truncated — it was never included.

### 9. The enforcement check in Finding 7's resolution has no specified behavior for the Lambda automated path
Section 2.1 and 2.9 state that any write causing AUTH + SOCIAL > 100K is rejected at the DynamoDB write layer. The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB. If AUTH has been manually increased close to 100K, the Lambda's automated write will be rejected. No behavior is specified for this case — the circuit breaker silently fails to act during an active attack.

### 10. `socket_connect_timeout=2` and `socket_timeout=2` are inconsistent with the latency alarm threshold
The publisher will time out Redis operations at 2000ms. `REDIS_LATENCY_HIGH` fires at p99 > 50ms. The document claims this means on-call is paged "well before the publisher begins timing out." That is true for the gap between 50ms and 2000ms, but the publisher emits metrics using whatever values it last successfully read — it does not emit zero on a slow read, it blocks until timeout or success. The claim that stale-zero values appear during slow Redis is incorrect given the code as written; the publisher will block for up to 2 seconds and then either succeed or throw, not silently emit zero.