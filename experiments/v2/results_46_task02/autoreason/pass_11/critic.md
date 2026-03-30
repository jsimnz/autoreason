## Real Problems

### 1. The "Derived" Viral Model Is Not Actually Derived

The document claims stress multipliers are "derived from model error bounds," but the inputs themselves are asserted. The "top 5% of DAU" cohort size, the "8× personal baseline" spike multiplier, and the "34/day for heavy users" figure are all estimates with no historical basis. Multiplying three asserted numbers together and calling the result "derived" is arithmetic, not derivation. The stress case analysis inherits all the uncertainty of the inputs and does not reduce it.

### 2. The Retry Schedule TTL Section Is Truncated and Incomplete

The TTL derivation section ends mid-sentence: "TTL = 2 hours (7,200 seconds) is". This is a critical section — idempotency key expiry determines whether duplicate delivery occurs — and it is literally unfinished. The document cannot be implemented from this specification.

### 3. The 3× Stress Case Queue Arithmetic Is Wrong

The document states the 3× scenario produces ~2,100/sec queue growth rate. The derivation: 3,300/sec inbound minus 1,200/sec delivery floor equals 2,100/sec. But the delivery floor cited is 1,200/sec while the expected throughput is 1,400/sec. Using the floor is appropriate, but the Redis runway calculation of "~17 hours" for cache.r6g.large is never shown. The capacity of a cache.r6g.large in notification-sized messages is not stated anywhere, making the runway figure unverifiable.

### 4. P0 Failover Routing Is Contradictory

The routing rule states "consistent hash on notification_id % 2" assigns notifications to APNs connections, but the failover rule states "Workers 1A/1B drain to APNs-2" if APNs-1 is unhealthy. Consistent hashing and a drain-on-failure model are incompatible without rehashing. Notifications in-flight to APNs-1 that are mid-retry will either be requeued (adding latency) or duplicated (violating idempotency). The interaction between the hash routing and the failover drain is not specified.

### 5. FCM Per-Device Rate Limit Mitigation Is Unimplemented

The document correctly identifies that FCM enforces approximately 240 notifications/hour per registration token and states "the P2 shedding logic must deduplicate by user_id." However, this deduplication is never specified anywhere in the worker pool design, the shedding logic, or the Kafka routing. A requirement stated in a caveat with no implementation detail is not a design — it is a known gap.

### 6. The 26-Worker Fit Claim Is Unsupported

The document states all 26 workers fit on 2 × c6g.xlarge instances "with headroom" but provides no memory or CPU accounting. Workers maintaining persistent APNs HTTP/2 connections, Redis connections, and Kafka consumer group membership have non-trivial per-worker overhead. At 26 workers across 2 instances, that is 13 workers per instance on 4 vCPUs and 8GB RAM. No per-worker resource profile is given, making "with headroom" an assertion.

### 7. The Non-AWS Tertiary Alerting Path Is Named But Not Specified

The document states "Non-AWS tertiary alerting path" as a key design decision and explains the structural reason (circular dependency). But no tertiary path is described anywhere in the document. What system, what trigger condition, what failure mode it covers — none of this appears. It is listed as a solved problem but is not designed.

### 8. SMS Spend Cap Has a Race Condition

The design uses a Redis atomic counter plus a Twilio hard cap as defense in depth. However, under the 2× or 3× stress scenarios where Redis is under memory pressure and queue growth is occurring, the Redis counter could be evicted or become unavailable. The document acknowledges "Redis counter fails open to the Twilio cap" but does not specify the eviction policy for the SMS counter key, whether it is in a separate Redis instance, or whether it has a TTL. Failing open to Twilio means spend exposure during the exact scenarios where the system is already degraded.

### 9. The iOS/Android Split Sensitivity Analysis References a Section That Does Not Exist

The document states "if the actual split is 40/60, FCM becomes dominant; Section 1.4 specifies what changes." Section 1.4 is referenced multiple times for sensitivity analysis and re-sizing triggers, but it does not appear in the document. This is a forward reference to content that was never written.

### 10. APNs 800/sec/Connection Figure Is Unvalidated and Structurally Critical

The document correctly notes Apple does not publish a contractual per-connection rate limit and labels the 800/sec figure as a "conservative operational floor." However, the entire throughput model — including the claim that the 3× stress case is survivable — depends on this number. If the actual limit is, for example, 400/sec, the system is under-provisioned for the base derived ceiling, not just stress cases. The document says to validate in month 2 load testing, which is after launch.

### 11. Receipt Write Decoupling Introduces Consistency Risk That Is Not Acknowledged

The document states receipt writes are decoupled from the delivery path via Kafka to avoid PostgreSQL write latency bounding delivery throughput. This is operationally correct, but it means delivery confirmation and actual receipt recording are asynchronous with no specified lag bound. If a receipt worker falls behind or fails, the system has delivered notifications with no recorded receipts for an unbounded period. The document does not specify a lag SLO, a maximum acceptable receipt delay, or what happens to analytics and debugging during a receipt worker outage.