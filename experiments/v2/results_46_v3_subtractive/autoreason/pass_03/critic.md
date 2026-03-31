## Real Problems with This Proposal

### 1. The DAU×Rate Math Is Internally Inconsistent

The proposal derives 50M notifications/day from 3M DAU × 17/day. But push volume is 35M/day attributed to 8M MAU. If push recipients are MAU-based, not DAU-based, then the top-level DAU×rate formula doesn't actually produce the channel breakdown. The two models are incompatible and the total figure is unreliable.

### 2. FCM Batch Size Is Wrong

FCM v1 API does not support batch requests of 500 tokens. FCM v1 is a single-device API. The legacy FCM HTTP API supported multicast up to 1,000 tokens but is deprecated. The proposal specifies a non-existent batching mechanism for the API it claims to use.

### 3. The Preference Check Cache Invalidation Problem Is Unaddressed

Preferences are checked at routing time against a Redis cache. The proposal never specifies the TTL, invalidation strategy, or what happens when a user turns off a notification type. A user who disables push notifications could continue receiving them for the duration of whatever staleness window exists in the cache. For a social app this is a trust and compliance issue, not just a minor bug. The proposal acknowledges the cache exists but treats invalidation as solved.

### 4. Redis Pub/Sub Is Not Reliable for WebSocket Fan-out

The in-app notification path uses Redis Pub/Sub to fan-out to WebSocket servers. Redis Pub/Sub is fire-and-forget — if a WebSocket server is momentarily disconnected or a subscriber is slow, messages are dropped silently. The proposal claims in-app notifications don't need retry logic, but a user who misses a real-time notification and whose client doesn't poll frequently enough will simply never see it until the next poll. The "persistent record" value proposition of in-app notifications is undermined by the delivery mechanism.

### 5. The Digest Idempotency Key Is Not Actually Idempotent Against the Email Provider

`digest_id` is described as an idempotency key, but idempotency keys only work if the email provider supports them and if the same key is reused on retry. Postmark supports idempotency keys; SES does not. The digest engine uses SES for digests. A retry after a network timeout will produce a duplicate email. The proposal claims to have closed the data loss window but opens a duplicate-send window with no discussion.

### 6. Partition Pruning Claim Is Questionable for the Read Path

The proposal justifies the composite primary key `(id, created_at)` by saying a global unique index defeats partition pruning. But the mark-as-read endpoint, the only identified single-notification lookup, must include `created_at` in the request payload. This means the client must store and transmit `created_at` for every notification. The proposal states this as an accepted tradeoff but never addresses what happens when a client omits it, passes a wrong value, or when the notification is near a partition boundary. The lookup behavior in these cases is undefined.

### 7. The `token.invalidated` Redis Stream Has No Consumer Group or Failure Handling

E2 publishes to a Redis stream; E3 consumes it. The proposal defines ownership but never specifies consumer groups, acknowledgment semantics, or what happens if E3's feedback processor falls behind or crashes. Redis Streams without explicit consumer group management will either re-deliver to no one or accumulate indefinitely. A backlog here means invalid tokens continue receiving push attempts until the stream is drained, generating APNs 410 and FCM error responses at scale.

### 8. The 90-Day Token Purge Is Insufficient for the Stated Goal

The proposal batch-purges tokens unused for 90 days to "cover uninstalls without explicit logout." But APNs and FCM both return explicit invalidity signals (410, `InvalidRegistration`) when a token is invalid. Waiting 90 days means actively sending to dead tokens for up to 90 days before purging them. At 35M push/day with any meaningful churn rate, this is a significant source of wasted API calls and inflated error rates that will affect deliverability scoring with FCM.

### 9. MIN_DIGEST_ITEMS Threshold Creates Unbounded Carry-Forward for Low-Activity Users

The carry-forward logic accumulates events until there are at least 3 items before sending. The 7-day expiry is meant to bound this. But the expiry silently discards notifications rather than sending them. A user who generates 2 events per week will never receive a digest — events accumulate to day 7 and are then expired, repeatedly. This is not a degraded experience; it is complete notification failure for a defined user segment, with no alerting.

### 10. Worker Pool Sizing Has No Stated Basis

P0: 10 workers, P1: 20 workers, P2/P3: 10 workers. At peak throughput of ~1,750/sec and assuming any non-trivial latency per external API call (APNs, FCM), these numbers may be severely undersized or arbitrarily oversized. No latency assumptions, no Little's Law calculation, no basis is given. For the component the proposal identifies as the core architectural bet, the sizing is undefended.

### 11. The Proposal Is Cut Off

Section 3.3 ends mid-sentence: "A nightly job (owned by E4)". Partition maintenance, the retention strategy, and the remainder of the document including §4 through §7 (phased rollout, runbooks) are missing. The proposal references these sections repeatedly as risk mitigations but they do not exist in the document.