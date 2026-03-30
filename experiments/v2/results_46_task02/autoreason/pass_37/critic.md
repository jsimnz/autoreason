## Real Problems with This Proposal

### 1. SQS FIFO Throughput Cap Is Understated

SQS FIFO queues are capped at 300 transactions per second without message grouping, 3,000 with. The proposal routes `notifications-tier1` and `notifications-tier2-dm` through FIFO queues and claims SQS "handles 400 notifications/second with substantial headroom." That headroom claim applies to Standard queues. The FIFO queues for DMs and Tier 1 face real throughput limits that aren't acknowledged. If DM volume spikes, `notifications-tier2-dm` hits a hard ceiling the document doesn't address.

### 2. The Bloom Filter Logic Is Backwards for Its Stated Purpose

The proposal says a negative bloom filter result (user not deleted) proceeds without a database lookup. But bloom filters have false negatives only if implemented incorrectly — a properly constructed bloom filter has zero false negatives. The real risk is false positives (filter says deleted, user is actually live), which the document does handle correctly. The entire explanation of "fast-path negative check" reflects a misunderstanding of bloom filter properties. If the filter says "not deleted," that is guaranteed correct and needs no qualification. The document's framing implies false negatives are possible, which would be a serious bug.

### 3. Concurrent SMS + Push for Tier 1 Creates Uncontrolled SMS Cost Exposure

The document explicitly rejects sequential fallback for Tier 1 in favor of concurrent multi-channel delivery. It then separately claims SMS costs are bounded at $5,000–15,000/year because security events are under 0.1% of DAU. These two claims are in tension. If a security event triggers concurrent SMS to every affected user with no fallback gating, and a bug, misconfiguration, or broad security incident causes Tier 1 volume to spike, the cost control mechanism (security-event-only subtype enforcement) is the only protection. The document calls that enforcement "code, not policy" but provides no description of how that code is tested or what alerts exist if it fails. The cost estimate has no stated upper bound under failure conditions.

### 4. The Digest Job's Snapshot Approach Breaks Its Own Idempotency Guarantee

The document states the digest job uses a snapshot timestamp as an idempotency key. But the snapshot is taken at job start, and the job processes users over multiple hours. Two users processed at different times during the same run share the same snapshot timestamp but may have meaningfully different unread states relative to that timestamp. More critically, if the job restarts, it resumes from the last committed checkpoint — but the snapshot timestamp is fixed at the original job start. A restarted job running hours later uses a stale snapshot that is now much older than it was for users processed before the interruption. The idempotency key prevents duplicate sends but does not protect against a digest that reflects a state 6+ hours stale for some users.

### 5. Cache Invalidation Events Don't Actually Close the Staleness Window They Claim To

The proposal says that for cases where 5-minute TTL staleness is unacceptable, services publish a cache invalidation event to `account-events`. But this event is consumed asynchronously by workers — it doesn't synchronously evict the cache entry at the moment of the preference change. Between the time the invalidation event is published and the time each worker consumes it, those workers continue using the stale cached preference. During a spike or consumer lag, this window could exceed the 5-minute TTL it was meant to replace. The document presents this as solving the immediate-consistency problem; it reduces it but doesn't solve it, and the residual window is unbounded by consumer lag.

### 6. "Re-generated from the Application Event Log" Is Asserted, Not Designed

The document's primary argument against Kafka is that replay is unnecessary because "notifications are re-generated from the application event log, which is the source of truth." This is stated once and never elaborated. There is no description of what this event log is, where it lives, how far back it retains events, what the re-generation process looks like, who runs it, how long it takes, or whether it's been tested. This is the load-bearing justification for a major architectural decision, and it's a single sentence.

### 7. Auto-Scaling Triggers Are Defined Against a Moving Baseline

Auto-scaling is defined as triggering when queue depth exceeds "30 seconds of processing capacity." Processing capacity per instance is not stated anywhere in the document. Without a defined per-instance throughput number, "30 seconds of processing capacity" is not a calculable threshold — it's a tautology. Operators cannot configure this, and the document cannot be evaluated for whether it will scale correctly.

### 8. The 30-Day Validation Requirement Has No Owner or Consequence

The document repeatedly defers empirical validation to "30 days after launch" and "60 days of production data." The DAU/MAU ratio, batching thresholds, spike batching queue depth trigger, and worker instance counts all depend on this validation. But no owner is named for any of these reviews, there is no stated consequence if the review doesn't happen, and there is no description of what "validated" means or what action follows an out-of-range finding. These read as due-diligence language that doesn't constrain behavior.

### 9. Quiet Hours Hold Delivery Creates a Thundering Herd

Notifications held during quiet hours are "delivered at the end of the quiet window." If a meaningful fraction of 2.5M DAU shares a quiet window end time (e.g., 08:00 local time), the system delivers a large batch of held notifications simultaneously. This is a self-inflicted spike that will recur every day at predictable times. The spike batching mechanism in §1.4 operates on queue depth, so it would apply — but that means users who set quiet hours to get undisturbed sleep receive their morning notifications 30 minutes late due to spike batching applied to the spike the quiet-hour release itself caused. The document doesn't acknowledge this interaction.

### 10. The Document Ends Mid-Sentence

Section 1.6 ends with "**PostgreSQL (RDS):** User preferences, notification" — cut off. Whatever followed (likely the in-app notification store design, read replica strategy, or retention policy) is absent. This isn't a minor formatting issue; the infrastructure section is incomplete, and subsequent sections referencing database behavior (§1.9 on the 30-day in-app window, for instance) have no foundation in the document as written.