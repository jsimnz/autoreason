## Real Problems with This Proposal

### 1. The Single Queue Is a Liability Disguised as a Simplification

The proposal claims a single priority queue is simpler to operate than per-channel queues, but this is backwards. A single queue means a SendGrid outage or rate limit now blocks push notifications sitting behind it. Channel-specific backpressure (FCM throttling, Twilio quota exhaustion) has no isolation boundary. The "4 queues to monitor" argument is weak — monitoring four queues is not meaningfully harder than one, and the blast radius of failure is far larger with a single queue. The proposal acknowledges this tradeoff but dismisses it without quantifying what a correlated failure looks like.

### 2. The Dequeue Operation Is Not Actually Atomic

The proposal claims the `zrange` + `zremrangebyrank` pipeline is made atomic via a Lua script, but the code shown does *not* use a Lua script — it uses a pipeline, which is not atomic. Multiple workers running this code simultaneously will dequeue the same batch. This is a correctness bug that will cause duplicate notifications in production from day one.

### 3. SMS Cost Math Is Wrong and the Channel Strategy Is Incoherent

$7,500/day for SMS is $2.7M/year. This is presented as an accepted constraint, but the proposal simultaneously says SMS is gated aggressively and limited to auth/security use cases. At 1M SMS/day with strict gating, the volume assumption is inconsistent with the use case restrictions. If SMS is truly limited to OTP and security alerts for 10M MAU, 1M/day implies every user receives an SMS daily — that contradicts "premium channel" positioning. The volume estimate is almost certainly wrong, but the proposal never reconciles this.

### 4. The Digest Carry-Forward Logic Creates Silent Data Loss Risk

The `carry_forward_to_next_digest` function is described but never defined. Events that don't meet the `MIN_DIGEST_ITEMS = 3` threshold are carried forward indefinitely. There is no stated cap on how long events carry forward, no TTL, no handling for users who never accumulate 3 events, and no specification of what "carry forward" means in storage terms. This is a real gap — not a minor one — because it affects whether users ever receive notifications about low-activity periods.

### 5. Partitioning Strategy Will Break Queries

The proposal recommends monthly partitioning on `created_at`, but the primary access pattern is `WHERE user_id = X ORDER BY created_at DESC`. PostgreSQL cannot partition-prune on `user_id` when partitioned by `created_at`, meaning every query for a user's notifications scans all active partitions. At 900M rows/quarter across monthly partitions, this is a serious query performance problem. The indexes defined are on the parent table and may not propagate correctly depending on PostgreSQL version and partition setup.

### 6. WebSocket Architecture Has No Stated Capacity Plan

The proposal describes a WebSocket + Redis Pub/Sub architecture for real-time delivery but gives no numbers: How many concurrent WebSocket connections? How many WebSocket server instances? What happens when a WebSocket server dies — do subscribers reconnect and re-subscribe? Redis Pub/Sub has no persistence and no fan-out guarantees across clustered Redis nodes without specific configuration. For 3M DAU, even a fraction of simultaneous active users could mean hundreds of thousands of concurrent connections, which is an infrastructure problem that receives zero treatment.

### 7. APNs JWT Rotation Is Specified Incorrectly

The proposal states JWT keys rotate "every 55 minutes." APNs tokens expire after 60 minutes, but the token is a *signed JWT*, not a key. The signing key (`.p8` file) does not rotate on a timer — it's rotated manually when revoked. What rotates is the JWT itself. The proposal conflates the two, which suggests the author hasn't implemented APNs HTTP/2 authentication directly. This will likely result in implementation confusion during E2's channel integration work.

### 8. No Stated Handling for Preference Cache Invalidation

The proposal says user preferences are cached in Redis and checked synchronously at routing time. There is no description of how the cache is invalidated when a user changes their preferences. A user who opts out of a notification type could continue receiving that type for the duration of the cache TTL — which is never stated. For a system explicitly designed around user preference control, this is a significant correctness gap.

### 9. Month 6 "Hardening" Is Not Defined

The timeline reserves an entire month for hardening, but the proposal never defines what hardening means, what criteria must be met before hardening begins, or what exit criteria mark it complete. For a 4-engineer team on a 6-month timeline, an undefined phase consuming 17% of the schedule is a project management risk, not a safety buffer.

### 10. No Failure Mode Analysis for the Feedback Processor

The feedback processor handles bounces, opens, and failures from all channels. If it falls behind or fails, suppression lists become stale — meaning the system will continue sending to invalid addresses and bounced emails, damaging sender reputation. The proposal shows the feedback processor in the architecture diagram but provides no discussion of its reliability requirements, processing latency targets, or what happens during an outage. Given that email deliverability is explicitly called out as a concern (bounce rate <2%), this is a critical omission.