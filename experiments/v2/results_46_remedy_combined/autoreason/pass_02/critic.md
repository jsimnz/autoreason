## Real Problems with This Proposal

### 1. SQS FIFO Queue Throughput Is Incompatible with the Stated Scale

SQS FIFO queues have a hard limit of 3,000 messages/second with batching, or 300/second without. The proposal assigns P0 and P1 to FIFO queues. P1 alone handles direct messages and mentions for a 10M MAU social app — that traffic can easily saturate the FIFO limit during the 3× peak multiplier (4,300/sec total). The proposal never addresses this limit. At peak, P1 notifications would back up silently, which is exactly the failure mode the priority queue is supposed to prevent.

### 2. The 60-Second Preference Cache TTL Creates an Unacknowledged Compliance Risk

The proposal mentions a 60-second TTL on the Redis preference cache but frames this only as an eventual consistency issue. For email and SMS, a user who unsubscribes can legally receive up to 60 seconds of additional messages. Under CAN-SPAM and TCPA, this is not a latency tradeoff — it is a potential violation. The proposal treats this as a consistency engineering problem when it is also a legal exposure that the document's approvers need to explicitly accept.

### 3. The APNs Token Manager Has a Race Condition It Claims to Solve

The `get_token()` method uses `threading.Lock()` to protect token generation. But the "proactive refresh" logic described in prose — where workers check token age before acquiring a connection — happens *outside* the lock. Two workers could simultaneously observe that a token is near expiration, both decide to preemptively refresh, and both call `get_token()` within the lock window. More importantly, the lock only works within a single process. With 15 P0 workers potentially running as separate processes or on separate nodes, the lock provides no cross-process protection. The proposal never addresses this.

### 4. The Partition Strategy Change Is Incomplete and Potentially Wrong

The proposal correctly identifies the problem with time-based partitioning for cross-time queries, then cuts off mid-sentence in the document. More substantively: hash partitioning by `user_id` solves the cross-time query problem but creates a new one — the "show recent notifications across all users" query needed for ops dashboards, debugging, and the feedback processor scanning for delivery failures now requires a full table scan across all partitions. The proposal doesn't acknowledge this tradeoff at all.

### 5. The SMS Cap Exemption for Auth SMS Is Uncosted

The proposal hard-caps SMS at 150K/day but exempts OTPs from the cap while tracking them separately. At $0.0079/message, if OTP volume is significant (password resets, 2FA for 1.5M opted-in users), the exemption could dwarf the capped volume. A social app with 10M MAU could generate hundreds of thousands of OTPs per day during an incident, a credential stuffing attack, or a forced re-authentication event. The proposal presents the $430K/year figure as the SMS cost, but this only covers the capped traffic. The actual ceiling is undefined.

### 6. The Feedback Processor Has No Defined Latency SLA

The feedback processor handles APNs 410 responses and FCM `InvalidRegistration` — meaning it's responsible for stopping sends to invalid tokens. The proposal describes what it does but not when. If the feedback processor is slow or backed up, the system will continue attempting delivery to invalid tokens, generating noise in delivery metrics, potentially triggering provider rate limits, and in the APNs case, risking the sending IP being flagged. There's no queue depth alarm, no processing latency target, and no defined behavior when it falls behind.

### 7. The Test Harness Investment Is Structurally Underspecified for Its Stated Purpose

The proposal commits 15% of engineering time to a test harness covering duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors, and broken unsubscribe links. But the only engineer not assigned to primary and secondary responsibilities is nobody — all four engineers have both. 15% of four engineers is 0.6 engineer-equivalents. The proposal never says who owns the harness, and E4's responsibilities (reliability, monitoring, failure handling, infrastructure) already constitute a full-time workload. This creates a situation where the harness is everyone's responsibility and therefore no one's.

### 8. The Collapse ID Scheme Will Silently Drop Notifications in Legitimate Scenarios

The proposal sets APNs Collapse ID to `{notification_type}:{entity_id}`. This means if two different users both comment on the same post, the second push notification will replace the first on the recipient's device — they will never know about the first comment. For a social app where comment notifications on popular posts are high-value engagement drivers, this is a product decision being made implicitly in an infrastructure document, with no acknowledgment that it's happening.

### 9. IP Warming Schedule Contradicts the Deliverability Risk It's Meant to Address

The proposal says to warm transactional IPs first and not send marketing emails until week 3. But the proposal also states 4M emails/day from day one. Sending 4M emails/day on a cold transactional IP is itself a deliverability risk — ISPs will throttle or block an IP sending millions of messages before it has established reputation. The warming schedule needed for 4M/day transactional volume is weeks to months, not implied as resolved by week 1.

### 10. The Budget Owner Model Creates a Single Point of Approval Failure

E3 owns the SMS rate limiter, and changing the cap requires VP-level approval. But E3 is also on the on-call rotation. During an incident requiring elevated SMS volume (e.g., a security event forcing mass OTP re-authentication), the process to raise the cap is a VP approval — which may not be reachable at 3am. The proposal has no incident exception path, which means either the cap breaks during real emergencies or there's an undocumented informal override process that defeats the control entirely.