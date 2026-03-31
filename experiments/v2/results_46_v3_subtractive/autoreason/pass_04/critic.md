## Real Problems with This Proposal

### 1. The "2% opt-out" Assumption Is Doing Too Much Work

The traffic model jumps from 51M raw events to 50M after "~2% opt-out filtering." A 2% opt-out rate for a social app is implausibly low — industry figures for notification opt-out rates on mobile are commonly 30–60%. If the real opt-out rate is 40%, the system is designed for roughly double the actual load on push, while email and in-app volumes may be significantly overstated. The entire capacity planning cascades from this number, and it has no cited basis.

### 2. Push Volume Accounting Is Internally Inconsistent

The proposal states 70% of 50M events = 35M push notifications, sent to 8M MAU with push tokens. That implies each of the 8M users receives on average 4.375 push notifications per day. But the 50M events derive from 3M DAU generating 17 events each. Non-DAU users generating events that trigger pushes to 8M recipients is not explained — the events come from DAU activity, but the recipients are MAU. The fanout mechanics (one event → multiple recipient notifications) are never modeled, so the 35M figure is not actually derivable from the stated inputs.

### 3. The Two-Phase Commit for Email Idempotency Doesn't Work

The proposal acknowledges SES has no idempotency keys, then describes recording the attempt before sending. But `record_send_attempt` and `send_email` are not atomic. If the process crashes after recording but before sending, the digest is permanently marked as attempted and never sent. If it crashes after sending but before `mark_send_complete`, the next retry sees no complete record and sends again. The code shown does not actually prevent duplicates — it just moves the race condition around.

### 4. The Carry-Forward Logic Has a Correctness Bug in the Code Shown

The `force_send` condition checks whether the oldest event is `MAX_CARRY_FORWARD_DAYS` old, but `valid_events` has already had expired events removed. Events older than 7 days are in `expired_events` and excluded from `valid_events`. So `oldest_carried` can never be more than 7 days old, meaning `force_send` can never be true for the case it's meant to handle — events that have been accumulating just under the expiry threshold. The fix the proposal claims it's implementing is broken in the code it provides.

### 5. APNs 410 Timestamp Logic Creates a Suppression Gap

The proposal correctly notes that Apple's 410 response includes a timestamp indicating when the token became invalid, and that tokens registered after that timestamp are valid. But the feedback processor is described as consuming from a Redis Stream asynchronously. Between the 410 signal and the feedback processor writing the suppression record, the delivery worker can continue attempting sends to that token. For high-volume users this window could produce dozens of redundant 410s. More seriously, if the Redis Stream consumer group falls behind, this gap grows unboundedly.

### 6. Worker Pool Sizing Has No Derivation

The proposal specifies 20 P0 workers, 40 P1 workers, and 20 P2/P3 workers with no analysis of why these numbers are correct. There is no stated processing time per notification, no queue depth target, no calculation of whether 40 P1 workers can drain the queue during peak (1,750/sec). These numbers appear to be guesses. For a team of 4 operating this in production, undersized worker pools mean silent queue backup; oversized pools mean resource contention on the Redis sorted set.

### 7. The "Single Priority Queue" Framing Obscures a Real Problem

The proposal frames per-channel queues as operationally complex and argues for a single queue. But the single queue still fans out to per-channel dispatchers. If APNs is rate-limited or degraded, P1 push notifications back up in the shared queue and block P1 email notifications from processing. The proposal never addresses head-of-line blocking within a priority tier across channels. The simplicity argument is partially false.

### 8. Email Cost Estimates Are Presented With False Precision

The table shows SendGrid at "$20,000–40,000/month" at "~120M emails/month." SendGrid's published pricing for 120M emails/month is not in that range — their enterprise pricing is negotiated and opaque, but their self-serve tiers don't reach 120M/month. The comparison table is presented as a cost-honest analysis but the numbers are not sourced and vary by 2× within a single cell, which means they cannot support a provider decision.

### 9. Silent Push Probing Has Platform Restrictions That Are Not Acknowledged

The proposal describes weekly silent pushes (`content-available: 1`) to tokens unused in 14 days as having "minimal cost." APNs throttles background pushes aggressively and does not guarantee delivery of silent pushes, especially for apps in a low-power or background-restricted state. FCM similarly does not guarantee delivery of data-only messages. Using non-delivery of a silent probe as a validity signal will produce false positives — valid tokens on battery-optimized devices will be incorrectly suppressed.

### 10. WebSocket Fan-Out Architecture Is Underspecified for Its Failure Mode

The proposal uses Redis Streams with consumer groups for WebSocket fan-out, citing acknowledged delivery as the justification over Pub/Sub. But WebSocket servers are stateful — a given user's WebSocket connection exists on exactly one server. The proposal does not describe how a Redis Stream consumer group routes a message to the specific WebSocket server holding that user's connection. If all WebSocket servers consume all messages and filter locally, that's O(servers × messages) processing. If there's per-user routing, that mechanism is not described. This is a significant architectural gap for a component described as production-ready.

### 11. The 6-Month Timeline Has No Buffer for External Dependencies

The proposal identifies APNs and FCM direct integrations as a deliberate choice over OneSignal/Braze, accepting "upfront engineering cost." APNs app review and provisioning, FCM project configuration, IP warming for email (weeks minimum), and Apple/Google push certificate provisioning all involve external parties with unpredictable timelines. The phased rollout in §7 (not shown) presumably depends on these being resolved on schedule. There is no contingency for a 3-week Apple provisioning delay, which is not hypothetical.