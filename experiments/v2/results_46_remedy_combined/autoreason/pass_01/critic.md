## Real Problems with This Proposal

### 1. The Math is Internally Contradictory

The proposal multiplies DAU × rate: 3M × 17 = 51M ≈ 50M. But DAU is defined as *daily active users* — users who open the app. Notifications are sent to **all users who have opted in**, including inactive users who haven't opened the app in weeks. Using DAU as the multiplier systematically undercounts total notification volume. The actual number could be 2-5× higher, and the entire infrastructure sizing is built on this flawed baseline.

### 2. Redis as the Sole Queue is a Single Point of Failure with No Stated Durability Guarantee

The proposal stores notification payloads in Redis with `setex` and queue membership in a sorted set. Redis in default configuration is not durable — a crash between `zadd` and the `setex` write, or between dequeue and delivery, loses notifications silently. The proposal never states what Redis persistence mode (RDB, AOF) is required, what the replication topology is, or what happens to the queue during a Redis failover. For a system where "P0 = security alerts and OTPs," silent loss is a serious failure mode, not an operational detail to sort out later.

### 3. The Pipeline Race Condition in Dequeue is Not Actually Fixed

The proposal acknowledges contention on `zrange + zrem` and claims "we use a Lua script to make it atomic." But the code shown does *not* use a Lua script — it uses a pipeline, which batches commands but does not provide atomicity. Two workers running this code simultaneously will dequeue overlapping sets of notifications. This is a correctness bug in the core dequeue path, not a performance concern.

### 4. SMS Cost Estimate is Off by an Order of Magnitude

The proposal states "$7,500/day at 1M messages." Twilio's standard rate is ~$0.0079/message, making 1M messages ~$7,900/day, or **~$2.9M/year**. This is presented as an accepted cost with only a vague "gate it aggressively" mitigation. No budget owner is identified, no cost ceiling is defined, and no fallback is described if SMS spend exceeds projections. For a 4-engineer team, this is a business-threatening line item treated as a footnote.

### 5. In-App Notification Partitioning Strategy Will Break Queries

The proposal partitions the `notifications` table by `created_at` monthly and defines indexes on `(user_id, created_at DESC)`. In PostgreSQL, a query for a user's unread notifications across partition boundaries requires scanning all relevant partitions. A user who hasn't cleared notifications in 2 months triggers a cross-partition scan. The index defined cannot be a global index in PostgreSQL's declarative partitioning — each partition gets its own local index. The proposal treats this as solved when it is not.

### 6. WebSocket Architecture Has No Horizontal Scaling Plan

The real-time delivery path is: client → WebSocket server → Redis Pub/Sub → client. If there are multiple WebSocket servers (required for any real availability), a notification published to Redis must be received by the specific server holding that user's connection. Redis Pub/Sub broadcasts to *all* subscribers, meaning every WebSocket server receives every notification and must filter. At 10M in-app notifications/day with multiple servers, this is significant wasted work. The proposal never addresses how many WebSocket servers are expected or what the fan-out cost is.

### 7. APNs JWT Rotation is Described Incorrectly

The proposal states "rotate keys every 55 min." APNs JWT *tokens* must be regenerated periodically (Apple recommends under 60 minutes), but the *signing key* (the .p8 file) does not rotate on a timer — it's rotated manually when compromised or as a policy decision. Conflating token refresh with key rotation will cause confusion during implementation. More critically, the proposal has no described path for what happens to in-flight APNs connections during token refresh — a dropped connection during a P0 notification send is not handled.

### 8. The Aggregation Window Logic Has an Undefined Cutoff Problem

The digest batching pseudocode has `carry_forward_to_next_digest(events)` when fewer than 3 grouped items exist. This means a user who consistently generates 2 notable events per day never receives a digest — their notifications are silently carried forward indefinitely. The proposal never defines a maximum carry-forward age, a fallback threshold, or what happens to carried-forward events when a user unsubscribes from digests.

### 9. No Engineer Owns Cross-Channel Consistency

The team allocation assigns E1 (pipeline), E2 (channel integrations), E3 (preferences), and E4 (reliability). The scenario where a user receives the same notification via push *and* email because a preference update was in-flight during routing — a fundamental correctness problem in multi-channel systems — has no assigned owner. The proposal describes the preference check as "synchronous at routing time, cached in Redis" but gives no TTL for that cache, meaning a user who disables email notifications could still receive emails for up to [undefined] minutes.

### 10. "No Dedicated QA" is Treated as a Risk When It's a Guarantee of Specific Failures

The proposal says "no dedicated QA — engineers own quality. This is a risk we accept." For a notification system, the failure modes are not random bugs — they are *predictable*: duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors in SMS quiet hours, and unsubscribe links that don't work. These are exactly the class of bugs that require systematic test case enumeration, not incidental coverage by engineers under delivery pressure. Accepting this "risk" means accepting known, enumerable failure modes that will directly harm users.