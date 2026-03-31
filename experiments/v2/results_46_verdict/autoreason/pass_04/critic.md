## Real Problems with This Proposal

### 1. The Single-Queue Architectural Bet Is Understated as a Risk

The document claims a Redis sorted set "handles 51M items comfortably" but never substantiates this. A sorted set with 51M members has real memory implications. At roughly 100 bytes per entry (score + member), that's ~5GB just for queue entries, before Redis overhead, before the preference cache, before pub/sub, before the APNs JWT store. The document acknowledges Redis serves multiple functions as "the primary infrastructure risk" but the memory budget across all Redis functions is never calculated. The Sentinel cluster configuration (3 nodes) doesn't specify whether these are separate machines or what their memory allocation is.

### 2. The Write Load Table Is Incomplete and the Analysis Promise Is Broken

Section 2.4 is titled "PostgreSQL Write Load Analysis" and sets up a table, then the document ends mid-table. The overflow row is cut off. There is no actual analysis — no connection pool sizing, no disk I/O estimates, no index maintenance overhead, no autovacuum impact from 51M rows/day of inserts into a partitioned delivery log. The table promises an analysis that doesn't exist.

### 3. The In-App Write-Before-Enqueue Creates an Unacknowledged Failure Mode

If the router successfully writes the in-app notification to PostgreSQL and then fails before enqueuing the push notification — crash, network partition, process kill — the in-app notification exists with no corresponding push ever sent. There is no recovery mechanism described. The user has a notification they never received a push for. The document describes what happens when the in-app write fails, but not what happens when the enqueue fails after a successful write. At 175 in-app writes/second, this is not a theoretical edge case.

### 4. The 8-Week Baseline Period for Opt-Out Thresholds Has No Interim Enforcement

The document specifies a 2% absolute threshold during the pre-baseline period, but 2% of 7M push-eligible users is 140,000 opt-outs in a single week. That is an enormous number. The document never explains why 2% is "deliberately conservative" — it's actually quite permissive. A system that drives 140,000 users to disable push notifications before the statistical baseline is established could permanently damage the addressable push audience. The framing of "deliberately conservative" appears to mean conservative in the sense of avoiding false positives, not conservative in the sense of protecting users.

### 5. P0 Isolation Is Described Inconsistently

The document says P0 uses "a dedicated Redis keyspace — a separate sorted set processed by dedicated workers." It then says this is "a narrow exception to the single-queue principle" and that P0 volume is less than 0.1% of total. But SMS is described as auth and security only, which are P0 events. The SLA says P0 delivers within 10 seconds or pages as P1. There is no description of what happens when the dedicated P0 workers are exhausted — whether there's a minimum worker count, whether they autoscale, or whether P0 can be starved by its own queue backing up. Calling it a "dedicated worker pool" without specifying minimum capacity is not isolation.

### 6. The Coverage Verification Schedule Creates Impossible Timelines

E4 must complete solo push on-call in month 1 before push launches in month 2. But push infrastructure (FCM, APNs integrations) is being built by E2 in month 1-2. E4 is simultaneously building email/SMS integrations, monitoring, and DevOps in month 1. E4 carrying solo push on-call for a system that isn't finished yet, in a staging environment that doesn't yet have four months of baselines (those come in month 6), while also being the primary on email and SMS, is not a realistic workload description. The schedule reads as theoretically sound but practically impossible for a single engineer.

### 7. The Preference Cache Invalidation Claim Is Unverified

The document states "write-through invalidation on any preference update." Write-through invalidation means the cache is updated synchronously on every preference write. But preferences are stored in PostgreSQL with Redis as a cache. If the preference update writes to PostgreSQL and then invalidates Redis, there is a window between the two operations where the cache is stale. If the Redis write fails after the PostgreSQL commit, the cache is stale for up to 5 minutes. The document describes this as solved but the mechanism for ensuring atomicity across two separate stores is never specified.

### 8. The 30-Second Polling Fallback Is Presented as Acceptable Without Justification

When WebSocket pub/sub is unavailable, clients fall back to polling every 30 seconds. At 3M DAU polling every 30 seconds, that is 100,000 requests/second against the in-app notification API during a Redis outage — which is precisely when the system is already degraded. The document never analyzes the polling load or whether the API and PostgreSQL can handle it. This is a degraded-mode scenario that could cause a cascading failure.

### 9. The Delivery Log Partition Strategy Is Incomplete

The delivery log is described as "partitioned by month" with S3 archive after 30 days. Monthly partitioning means the current month's partition receives all writes — up to 1,770/sec at peak — with no distribution across partitions. This is a hot partition problem. The document describes the partitioning scheme without acknowledging that monthly range partitioning concentrates writes on a single partition for the entire month.

### 10. The FCM Throughput Analysis Referenced in Month 6 Is Never Shown

Section 1.3 states "FCM throughput analysis shows minimal headroom at 3× during FCM degradation" as justification for using a mocked FCM endpoint in stress testing. This analysis is never presented. FCM has rate limits that vary by project tier and registration token age. Without showing the actual FCM quota, the claim of "minimal headroom" is unverifiable, and the decision to mock FCM rather than test against it obscures whether the real system can meet the 3× design envelope.

### 11. The SMS Allowlist Enforcement Has No Audit Mechanism

The document states the SMS gate is "enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention." There is no description of how this allowlist is managed, who can modify it, whether changes are logged, or how violations are detected. An allowlist enforced only at dispatch time with no audit trail is a cost control mechanism that can be bypassed by anyone who can modify the dispatcher configuration.

### 12. "Revisit at 50M MAU" Is Used as a Deferral Without Trigger Criteria

The document repeatedly defers architectural decisions to "50M MAU" — per-channel queues, the single-queue design, per-channel rate limiting. But 50M MAU is a lagging indicator. By the time MAU reaches 50M, the system has been under stress for months. There are no leading indicators defined — queue depth thresholds, worker saturation percentages, Redis memory utilization — that would trigger architectural review before the system is already failing.