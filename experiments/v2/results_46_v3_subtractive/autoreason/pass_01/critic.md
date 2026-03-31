## Real Problems

### 1. The Priority Queue Scoring Math Is Broken

The score formula `PRIORITY_WEIGHTS[priority] - (time.time() / 1e10)` produces results like `1_000_000 - 0.000000170...` — the timestamp term is astronomically small and has essentially no effect on ordering. Two P1 notifications enqueued hours apart will have nearly identical scores, making the FIFO-within-priority guarantee meaningless. The math doesn't work as described.

### 2. The dequeue_batch Is Not Atomic Despite the Claim

The proposal claims a Lua script makes the operation atomic, but the actual code shown uses a plain pipeline with `zrange` + `zremrangebyrank`. A pipeline is not atomic — it's just batched. Two concurrent workers can both read the same top-N items before either removes them, causing duplicate deliveries. The Lua script is mentioned but never shown.

### 3. SMS Cost Is Wrong by an Order of Magnitude

The proposal states 1M SMS/day at $0.0075/message = $7,500/day, then calls this "expensive." But $0.0075 × 1,000,000 = $7,500/day = **$225,000/month**. This is not a footnote-level concern — it's a budget-destroying number that would almost certainly exceed the entire engineering team's infrastructure budget. The proposal treats it as a known tradeoff and moves on, but never surfaces it as a go/no-go risk.

### 4. In-App Partitioning Strategy Contradicts the Schema

The proposal says partition by `created_at` monthly, but the schema defines `id` as `UUID PRIMARY KEY`. In PostgreSQL, the primary key constraint creates a global unique index across all partitions. You cannot partition on `created_at` while keeping a UUID primary key without including `created_at` in the primary key — this is a hard PostgreSQL limitation. The schema as written won't work with the stated partitioning approach.

### 5. Digest Carry-Forward Logic Creates Silent Data Loss Risk

The `carry_forward_to_next_digest` function is called but never defined or explained. If a user consistently has fewer than 3 grouped events per day (the `MIN_DIGEST_ITEMS` threshold), their notifications are silently deferred indefinitely. There's no stated maximum carry-forward period, no fallback, and no mention of what happens to carried events if a user unsubscribes. Notifications can effectively disappear.

### 6. DAU × Rate Notification Math Is Internally Inconsistent

The traffic model multiplies DAU (3M) × 17 notifications/user/day = 51M, which they round to 50M. But in-app notifications are listed as 20% of 50M = 10M/day. If in-app notifications only go to logged-in users (explicitly stated in the table), and DAU is 3M, then 10M in-app notifications means each active user receives 3.3 in-app notifications/day — not 17. The 17/user/day figure is being applied to DAU for total volume but then distributed across all channels including ones that only reach DAU. The ratios don't add up to a coherent model.

### 7. WebSocket Architecture Has No Stated Horizontal Scaling Plan

The real-time delivery section routes WebSocket connections through Redis Pub/Sub, which works for a single WebSocket server. But with multiple WebSocket servers (necessary for 3M DAU), a message published to Redis must fan out to every server to find the one holding a given user's connection. At 10M in-app notifications/day, every WebSocket server receives every message and must check if it holds a relevant connection. This is a known scaling problem with Redis Pub/Sub that the proposal doesn't acknowledge.

### 8. No Engineer Owns Cross-Channel Concerns

The team allocation assigns E1 to pipeline, E2 to channel integrations, E3 to preferences, and E4 to reliability. Cross-cutting concerns — deduplication across channels, the aggregation/batching logic that spans routing and delivery, the feedback loop from bounces back to preference suppression — fall between these boundaries. The proposal describes these features in detail but assigns no owner.

### 9. APNs JWT Rotation Is Stated Incorrectly

The proposal says "rotate keys every 55 min." APNs JWT tokens (not keys) expire after 1 hour and must be regenerated — but the *signing keys* (`.p8` files) don't rotate on a schedule at all; they're manually revoked. Conflating token refresh with key rotation is an operational mistake that could cause production auth failures if whoever implements this misunderstands what's being rotated.

### 10. The "Revisit at 50M" Exits Are Not Triggered by the Right Signals

The proposal repeatedly defers architectural concerns to "50M MAU" (5× growth). But the Redis Sorted Set contention problem, the WebSocket fan-out problem, and the single-queue bottleneck are all throughput problems, not user-count problems. A viral event could drive 10× normal throughput at 10M MAU. The scaling triggers are defined by the wrong metric.