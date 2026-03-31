## Real Problems with This Proposal

### 1. The Single Redis Queue Is a Reliability Catastrophe

Redis Sorted Set as the primary queue has no built-in persistence guarantees that match the stated requirements. The proposal says P0 notifications (security alerts, OTPs) must arrive in <5 seconds, but if Redis goes down or restarts, those notifications are gone. The proposal mentions Redis but never addresses AOF/RDB persistence configuration, replication lag, or what happens during a Redis failover. For a system handling OTPs and security alerts, this is not a footnote — it's a core reliability gap. The proposal treats Redis as if it were durable by default.

### 2. The Dequeue Implementation Is Broken

The `dequeue_batch` code uses a pipeline, not a Lua script, despite the text claiming "we use a Lua script to make it atomic." `pipe.execute()` in Redis pipelines is not atomic — it's just batched. Between the `ZRANGE` and `ZREMRANGEBYRANK`, another worker can pop the same items. This means multiple workers will process the same notification, resulting in duplicate sends. This is not a theoretical concern at 40 workers and 1,750/sec peak throughput.

### 3. The $7,500/Day SMS Number Is Wrong and Unexamined

The proposal states SMS costs ~$7,500/day at 1M messages, then restricts SMS to auth, security alerts, and critical use cases — which would be a tiny fraction of 1M/day. The 1M/day figure comes from the 2% channel split of all notifications, but then the channel restrictions make that volume impossible to reach. The cost estimate is built on a volume that contradicts the channel policy. No one caught this internal inconsistency, and the budget implications of the real SMS volume (or the real 1M/day volume) are never resolved.

### 4. Partitioning Strategy Will Break Before Month 6

The proposal calls for monthly partitioning of the notifications table and dropping partitions older than 90 days. At 10M rows/day, a single monthly partition holds ~300M rows. The proposal never addresses how `CREATE INDEX` runs on a 300M-row partition, how partition pruning actually works with the proposed query patterns, or what happens when the partition drop operation runs on a live system. More critically, the index `WHERE is_read = FALSE` on a partial index will become increasingly useless as the read ratio changes — it's only efficient if most notifications are unread, which is the opposite of steady-state behavior.

### 5. WebSocket Architecture Has No Stated Capacity

The proposal describes a WebSocket real-time delivery system for in-app notifications with Redis Pub/Sub, but never states how many concurrent WebSocket connections the system needs to support, how many WebSocket server instances are planned, or how connection state is managed across deployments. With 3M DAU and even a 10% concurrent active rate, that's 300K persistent connections. Redis Pub/Sub fanout at that scale has well-known memory and CPU costs that are never addressed.

### 6. The Aggregation Code Is Truncated at a Critical Point

The proposal cuts off mid-function in section 4.3. The `route_notification` function is incomplete — it shows the aggregation key lookup but not the actual aggregation logic, the non-aggregation path, or how aggregated notifications eventually get enqueued. This is not a minor omission; aggregation is cited as a core feature and the implementation is literally missing. Any engineer trying to build from this spec hits a wall immediately.

### 7. APNs JWT Key Rotation Is Operationally Unspecified

The proposal states "rotate keys every 55 minutes" for APNs JWT authentication, but APNs JWT tokens expire after 1 hour and must be regenerated — this isn't a configurable key rotation, it's a token refresh. If the refresh fails or the clock skews, APNs rejects all pushes silently or with a specific error. The proposal doesn't address how the token refresh is coordinated across 20 pooled connections, what happens during the refresh window, or how failures are detected. This is a known operational hazard for direct APNs integrations.

### 8. No Mention of GDPR/CCPA for Notification Data

The delivery log is stored in PostgreSQL with S3 archive. The proposal describes storing notification content, entity IDs, user IDs, and metadata indefinitely (S3 archive implies long-term). For a 10M MAU social app, there is no discussion of right-to-erasure handling, data retention policy, or what "archive" means for compliance purposes. This is not a nice-to-have — it's a legal requirement in multiple jurisdictions the app almost certainly operates in.

### 9. No On-Call Runbooks or Escalation Path

The proposal states "all engineers rotate on-call" with no dedicated QA, and frames this as a risk they accept. But there are no runbooks, no defined SLOs that trigger escalation, no stated response time expectations, and no discussion of what happens when the on-call engineer can't resolve a queue backup or channel outage. For a system sending OTPs and security alerts, "we accept this risk" is not an operational plan — it's a gap that will surface at 2am.

### 10. FCM Batch Size Claim Is Incorrect

The proposal states "Batch size: 500 tokens per FCM v1 batch request." FCM HTTP v1 API does not support multicast/batch sends in the same way the legacy API did. The v1 API sends one message per request (though you can use HTTP batch requests up to 500, these are HTTP-level batches, not a single FCM operation). The retry and error handling semantics are different per-message in v1. A team building direct FCM integration from this spec will discover this discrepancy when they hit the API, not in the proposal review.