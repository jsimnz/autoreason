## Real Problems

### 1. Kafka Justification Is Weak and the Complexity Cost Is Understated

The document justifies Kafka over SQS primarily for replay capability, then acknowledges SQS handles the volume easily. But managed Kafka (Confluent Cloud, MSK) still requires expertise in consumer group management, partition rebalancing, offset management, and schema evolution. A four-person team that hits a consumer group lag incident at 2am is not insulated from Kafka's complexity by paying for a managed service. The "operational surface reduces to configuration and monitoring" claim is false in practice. Consumer group resets, exactly-once semantics failures, and partition skew are not configuration problems. The replay use case cited — a buggy worker incorrectly marking deliveries — could be handled with the DLQ and idempotency mechanisms already described, without Kafka's log retention. The justification doesn't hold up.

### 2. The Idempotency Mechanism Has a Race Condition

The document describes checking a Redis set before delivery, then writing to the set after delivery. If two worker instances consume the same Kafka message simultaneously (possible during rebalance), both can pass the check before either writes to Redis. The document acknowledges the 24-hour TTL gap but doesn't acknowledge this concurrent-read race condition, which can occur in normal operation, not just during replay scenarios.

### 3. Tier 1 SLA Is Internally Inconsistent

The Tier 1 SLA states "best effort within 60 seconds" but the retry schedule runs to 160 minutes (10s + 30s + 1m + 2m + 5m + 10m + 20m + 40m + 80m + 160m). The document doesn't reconcile these. A password reset notification that takes 160 minutes to deliver after 10 retries is not consistent with a 60-second SLA. The 24-hour retry window for the DLQ processor extends this further. No distinction is made between "first attempt within 60 seconds" and "delivered within 60 seconds."

### 4. Direct Message Exclusion From Spike Batching Is Not Enforced Architecturally

The document states DMs are excluded from spike batching "even at Tier 2." But DMs are classified as Tier 2, and the spike batching mechanism triggers on queue depth exceeding a threshold across Tier 2 notifications. The document doesn't describe how the system distinguishes DMs from other Tier 2 notifications during spike batching. If the exclusion is implemented as a flag on the notification type, that's a different architecture than what's described. If it's not implemented, DMs get batched anyway. This is stated as a guarantee but has no supporting mechanism.

### 5. The SMS Cost Estimate Is Not Credible for Its Own Stated Scope

The document estimates $5,000–15,000/year for SMS scoped to security events. But it also states SMS is used for "users in markets where push penetration is low." Low push penetration markets (parts of South Asia, Sub-Saharan Africa, Southeast Asia) can represent a substantial fraction of a 10M MAU base. If even 5% of users are in low-push-penetration markets and receive one SMS per week for social notifications, that's 26M messages/year at $0.01 minimum — $260,000/year. The cost estimate is only valid if "markets where push penetration is low" is operationally defined and enforced as a near-zero population, which the document doesn't do.

### 6. Preference Cache Invalidation for Account Deletion Is Insufficient

The document states account deletion triggers immediate cache invalidation via direct Redis delete. But the notification pipeline reads preferences at dispatch time from Kafka consumers that may already have messages in flight for a deleted user. Messages published to Kafka before the deletion event — but not yet consumed — will be dispatched after the preference cache is cleared. The in-app worker will write to PostgreSQL for a user whose account is being deleted. The document doesn't address in-flight message handling for account deletion, only preference cache state.

### 7. Digest Pre-computation Timing Creates a Data Consistency Window

The digest job runs at 06:00 UTC daily and aggregates the previous 24 hours of unread activity. A user who receives a notification at 05:59 UTC will have it included. A user who reads their notifications at 05:58 UTC and then receives a new notification at 06:01 UTC won't have that notification in the digest until the next day. More concretely: the job reads "unread" state at a point in time, but users are actively reading notifications while the job runs. The document doesn't address what "unread" means relative to job execution time, or how the job handles the read/unread state changing during a run that processes millions of users.

### 8. Circuit Breaker Parameters Are Specified Without Basis

"10 failures in 60 seconds" is given as the circuit breaker threshold with no analysis of what this means at operating load. At 200 notifications/second going to APNs, 10 failures in 60 seconds is a 0.008% error rate — well within normal APNs operation during periods of elevated device offline rates. This threshold will open the circuit during normal operating conditions. Conversely, during a real APNs partial outage, 10 failures in 60 seconds might represent a tiny fraction of total failures. The threshold is specified as if it were calibrated but there's no evidence it is.

### 9. The 30-Day Instrumentation Plan Has No Fallback

The document repeatedly defers decisions to "after 30 days of production data" or "after 60 days." The batching thresholds, spike batching queue depth threshold, and DAU/MAU ratio are all flagged for empirical review. But there's no stated process for who reviews these, what triggers a change, or what happens if the data shows the initial values were significantly wrong. The document acknowledges the values are estimates but treats the review as self-executing. On a four-person team with active feature development, deferred calibration tasks compete directly with roadmap work and frequently don't happen.

### 10. S3 Archival Breaks the In-App Notification Center for Active Users

Notification history rows are exported to S3 and deleted from PostgreSQL after 30 days. The in-app notification center reads from PostgreSQL. A user who opens their notification center and scrolls back more than 30 days gets a hard cutoff. The document presents this as a table-size management solution without acknowledging the user-visible behavior it produces. For a social app where users may reference old DM notifications or account events, this is a product problem, not just an infrastructure tradeoff.