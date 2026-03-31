## Real Problems with This Proposal

### 1. SQS FIFO Throughput Is Actually a Hard Constraint, Not a Soft One

The proposal says "SQS FIFO has a throughput limit of 3,000 messages/sec with batching per queue" and treats this as comfortable headroom over 1,750/sec peak. But this limit applies **per message group ID**, not per queue, when using message groups. If the design uses message group IDs for ordering guarantees (which FIFO queues require for ordering semantics), the effective throughput per group is far lower. The proposal never specifies how message group IDs are assigned. If group ID = user_id, throughput per user is 1 msg/sec. If group ID is a constant, ordering is serialized across all messages. The proposal cannot simultaneously claim FIFO ordering semantics and 3,000/sec throughput without explaining the message group ID strategy, and the two goals are in direct tension.

### 2. The Deduplication Window Creates a Correctness Bug for OTPs

The deduplication key includes a 5-minute window: `(user_id, notification_type, entity_id, 5-minute window)`. For OTPs, `notification_type` would be something like `auth_otp` and `entity_id` would presumably be a session or request ID. If `entity_id` is the same across a retry (user clicks "resend" within 5 minutes), the second OTP is silently deduplicated and never delivered. If `entity_id` is unique per OTP generation, the dedup window provides no protection against duplicates at all for OTPs. The proposal never resolves this tension. For the highest-priority notification type in the system, the deduplication logic is either wrong or vacuous.

### 3. The APNs `apns-expiration` for P0 Is Dangerously Short

P0 notifications include OTPs and security alerts. The proposal sets `apns-expiration: 300s` (5 minutes) for P0. If the user's device is offline for more than 5 minutes — airplane mode, dead battery, poor connectivity — the OTP notification is silently discarded by APNs and never delivered. There is no fallback mechanism described for this case. The proposal elsewhere emphasizes OTP reliability as the justification for switching from Redis to SQS, then sets a delivery window that makes silent OTP loss routine.

### 4. Badge Count Is Served Stale by Design

The APNs payload includes `"badge": 12` as a hardcoded example, but in production the badge count must be computed at dispatch time. The proposal stores in-app notifications in PostgreSQL and caches preferences in Redis with a 60-second TTL. There is no described mechanism for computing an accurate badge count at push dispatch time. If badge counts are read from the same PostgreSQL store, this adds a synchronous DB read per push notification at 35M/day. If they're cached, they're stale. The proposal never addresses this, despite including badge in the payload schema.

### 5. The `carry_forward_to_next_digest` Function Introduces Unbounded State

The digest logic carries events forward if fewer than 3 grouped items exist. There is no described bound on how long an event can be carried forward, what happens to carried-forward events if a user unsubscribes, whether carried-forward events count toward frequency caps, or what happens if the user never accumulates 3 events. This is not a minor gap — it's a data accumulation path with no described termination condition, running against a PostgreSQL table with 90-day retention. Events carried forward indefinitely could outlive the retention window or create compliance issues if a user deletes their account.

### 6. The Team Allocation Has a Single Point of Failure on Critical Path

E2 owns all channel integrations: APNs, FCM, SendGrid, and Twilio. The proposal's own timeline shows these are the most technically complex components with the most external API surface area. If E2 is unavailable (illness, departure), the entire delivery layer stalls. The proposal acknowledges "no dedicated QA" as a risk but does not acknowledge this more severe concentration risk. For a 6-month timeline with a 4-person team, one departure restructures the entire project.

### 7. The 90-Day Hard Delete of Delivery Logs Has Unstated Compliance Implications

The proposal states delivery logs are deleted after 90 days with no discussion of regulatory requirements. Depending on jurisdiction and what counts as "personal data" under GDPR, CCPA, or similar frameworks, delivery logs containing user IDs, message content references, timestamps, and device identifiers may be subject to retention minimums (for legal hold), deletion-on-request obligations, or data residency requirements. The proposal makes a hard architectural decision — deletion at 90 days — without acknowledging that this decision may conflict with legal requirements the team hasn't evaluated.

### 8. Redis Cache TTL Creates a Preference Enforcement Gap That Isn't Acknowledged as a Risk

Preference checks use a Redis cache with a 60-second TTL. The proposal presents this as an operational simplification. The actual consequence: if a user opts out of a notification type, they will continue receiving that notification type for up to 60 seconds. For security alert opt-outs this is probably acceptable. For a user who has just reported harassment and opts out of all notifications from a specific actor, a 60-second window of continued delivery is a safety issue, not a performance tradeoff. The proposal never distinguishes between preference types that tolerate eventual consistency and those that require immediate enforcement.

### 9. The FCM Rate Limit Claim Is Not Verifiable

The proposal states "FCM allows ~600 req/sec per project." FCM does not publish a single documented per-project rate limit in this form — limits depend on the project tier, whether you've requested a quota increase, and the specific API endpoint. Designing a connection pool (50 connections, 500 in-flight requests, targeting 400 req/sec) around an undocumented and potentially incorrect rate figure is a real operational risk. At 35M push notifications/day, hitting an actual rate limit that differs from the assumed one would cause cascading queue backup.

### 10. The APNs `collapse-id` Strategy Will Silently Drop Distinct Notifications

The proposal sets `apns-collapse-id: {notification_type}:{entity_id}`. For a "like" notification, if Alice and Bob both like the same post within a short window, the second notification collapses the first on the device. The proposal describes this as collapsing "stale like/follow notifications," but the collapse happens at the APNs layer before the device processes it — the aggregated payload from the first notification ("Alice liked your photo") is replaced by the second ("Bob liked your photo"), and the user sees only one notification that appears to be from Bob, with no indication Alice also liked it. The proposal's own payload template shows "Alice and 3 others liked your photo" as a server-side aggregation, but the collapse-id strategy means APNs may deliver only the most recent single-actor notification, contradicting the aggregation logic.