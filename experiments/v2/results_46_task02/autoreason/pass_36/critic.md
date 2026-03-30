## Real Problems with This Proposal

### 1. The SQS FIFO Throughput Problem Is Unaddressed

SQS FIFO queues are capped at 300 transactions per second without message grouping, or 3,000 with message group IDs. The document places `notifications-tier1` and `notifications-tier2-dm` on FIFO queues and claims SQS "handles 400 notifications/second with substantial headroom" — but that statement appears to apply to Standard queues. The document never demonstrates that the FIFO queues can handle peak load, never mentions message group ID strategy, and the blanket throughput claim is simply wrong as applied to FIFO. This is a capacity design error on the queues explicitly chosen for the most sensitive notification types.

### 2. Concurrent Multi-Channel Tier 1 Delivery Creates Duplicate Notification Problem

The document states that for Tier 1, push, SMS, and email fire concurrently rather than sequentially. It gives a reason (latency). It never addresses what happens when all three succeed and the user receives the same security alert three times simultaneously. There is no described mechanism for cross-channel deduplication or suppression after successful delivery on one channel. For security events like "login from new device," receiving three simultaneous alerts may itself cause user panic or support escalation. The document treats this as solved by the concurrency decision but it is not.

### 3. The Bloom Filter False Positive Rate Is Never Specified

The deleted-user bloom filter is described as a "fast-path negative check," with false positives causing extra database reads. The document does not specify the target false positive rate, the expected size of the deleted-users set, or how the filter is sized. At 10M MAU with meaningful churn, the deleted-users set could be very large. An undersized bloom filter with a high false positive rate would cause a substantial fraction of all notification deliveries to incur a database lookup, potentially collapsing the performance advantage the bloom filter was introduced to provide. This is presented as a solved design when the critical parameters are absent.

### 4. Quiet Hours Delivery Surge Is Unmodeled

Notifications held during quiet hours for all users in a timezone are released simultaneously at the end of the quiet window. The document models evening spikes and viral spikes but never models the quiet-hours release spike. If a significant fraction of users share a timezone and set similar quiet hours (22:00–08:00 is the example given), the 08:00 release represents a scheduled, predictable, large surge that could exceed the spike estimates the infrastructure was sized for. The auto-scaling trigger is queue depth, not time-based anticipation, so the system would be reacting to this surge rather than preparing for it.

### 5. The 5-Minute Preference Cache TTL Is Inconsistently Applied

The document says that for cases where 5-minute staleness is unacceptable, a cache invalidation event is published to `account-events`. But the examples given are account suspension and preference changes "that require immediate effect." The document never defines which preference changes qualify. A user turning off push notifications entirely — arguably a high-intent action — would wait up to 5 minutes under the standard TTL unless someone has decided it triggers an invalidation event. That decision is not documented. The boundary between "routine preference change" (TTL acceptable) and "requires immediate effect" (invalidation event) is unspecified and left to implementer judgment.

### 6. The Digest Job Snapshot and Per-User Ordering Interact Badly at Scale

The digest job takes a snapshot at 06:00 UTC and processes users in "deterministic order." For a 10M MAU base, even if only a fraction receive digests, this job runs for hours. Users processed late in the job have a snapshot that is many hours stale relative to their actual delivery time. A user processed at hour four of the job has a digest reflecting state from four hours ago, but it is delivered as if current. The document acknowledges the snapshot boundary at 06:01 UTC but does not acknowledge that the effective staleness window grows proportionally with job duration and varies per user based on processing order. This is not a minor edge case — it is structural to the design.

### 7. Invalid Push Token Handling Has No Described Impact on In-App State

The push worker "marks invalid tokens immediately." The document does not describe what happens next. If a token is invalid, the user likely has push disabled or has uninstalled and reinstalled the app. The in-app notification is still written (it always is for Tier 2), but the push that would prompt the user to open the app and see it has failed silently. There is no described mechanism for escalating to another channel on token invalidity, no distinction between a temporarily invalid token and a permanently invalid one, and no process for token refresh that is actually specified beyond "handles token refresh" as a parenthetical. The failure mode is described in one clause; the response is not described at all.

### 8. The Document Is Incomplete and Published Anyway

The infrastructure section cuts off mid-sentence: "**PostgreSQL (RDS):** User preferences, notification" — and then the document ends. This is not a minor formatting issue. The database design, the in-app notification store, the Redis architecture, the deployment model, and presumably several other sections are simply absent. The preface claims the document provides "a complete technical design." It does not. Engineers implementing from this document would be making up significant portions of the system with no design authority, and reviewers approving it would be approving an incomplete specification while believing it complete.

### 9. Re-Generation from Application Event Log Is Asserted, Not Designed

The rejection of Kafka hinges partly on the claim that "for catastrophic failures requiring full replay, notifications are re-generated from the application event log, which is the source of truth." This event log is never described anywhere in the document. Its schema, retention policy, queryability, and the process for re-generating notifications from it are entirely absent. The argument against Kafka's replay capability relies on this alternative existing and working, but it is a forward reference to a system that has not been designed within this document.

### 10. The 30-Day Validation Deadline Has No Owner or Consequence

The document repeatedly defers to 30-day and 60-day reviews: validate the DAU/MAU ratio, review batching thresholds, review spike queue depth thresholds. None of these reviews name an owner, define what "review" means operationally, or specify what happens if the review concludes the initial parameters were wrong. The document acknowledges that its estimates are not measurements, which is appropriate, but the mechanism for replacing estimates with measurements is described as a process without any accountable party or defined outcome.