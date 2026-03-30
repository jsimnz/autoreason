## Real Problems with This Proposal

### 1. The Single Queue Is a Correctness Problem, Not Just a Scale Problem

The proposal frames the single Redis sorted set as a scale tradeoff to revisit at 50M MAU. But it's actually a correctness problem at current scale. P2 volume (likes, follows) is ~35M items/day. A burst of P2 traffic can fill the queue and create head-of-line blocking for P0 items even with priority scoring, because workers dequeue in batches of 50. A batch of 50 P2 items gets locked in a worker pipeline before any P0 item can be processed. The "P0 always beats P1" claim in section 4.2 is only true at the queue level, not at the worker level.

### 2. The Atomic Dequeue Doesn't Work as Written

The pseudocode in section 4.2 uses a pipeline, not a Lua script, despite the text claiming it uses a Lua script. A Redis pipeline is not atomic — it batches commands but doesn't prevent interleaving. Two workers executing this simultaneously will dequeue overlapping sets of items. The proposal acknowledges contention but then doesn't actually solve it in the code shown.

### 3. SMS Cost Estimate Is Wrong by an Order of Magnitude

The proposal calculates SMS cost as ~$7,500/day (1M messages × $0.0075). But Twilio's $0.0075 rate is for US outbound. International SMS is $0.05–$0.09 per message for major markets. A social app with 10M MAU almost certainly has significant international users. At even 30% international traffic, actual costs are closer to $15,000–$20,000/day. The proposal then uses this understated number to justify aggressive SMS gating, but the gating logic may be insufficient if the real cost is 2–3× higher.

### 4. The Digest Carry-Forward Logic Creates Silent Data Loss

Section 3.2 includes this logic: if a digest has fewer than 3 grouped items, carry events forward to the next digest. There is no described mechanism for what happens to carried-forward events when a user unsubscribes, deletes their account, or when the system restarts. Events in this liminal state — written to the DB but not yet sent — could be silently dropped or, worse, sent to a user who has since unsubscribed. There's no table, queue, or store described for holding these carried-forward events.

### 5. WebSocket Architecture Has No Described Horizontal Scaling Path

The proposal describes Redis Pub/Sub for WebSocket fan-out. Redis Pub/Sub requires every WebSocket server to subscribe to every channel. At 3M DAU with even modest concurrent connections, you have potentially millions of Redis Pub/Sub subscriptions across WebSocket servers. The proposal doesn't describe how many WebSocket servers are expected, connection limits per server, or how channel subscriptions are managed at scale. "We use Redis Pub/Sub" is not an architecture — it's a component choice without a deployment model.

### 6. Monthly Partitioning at 10M Rows/Day Is Under-Specified

The proposal says to partition `notifications` by `created_at` monthly and drop partitions older than 90 days. At 10M/day, a single monthly partition is ~300M rows. The proposal doesn't address how Postgres will handle partition pruning for the unread index query (`WHERE is_read = FALSE`), which spans all partitions for users with old unread notifications. Partial indexes on partitioned tables in Postgres have known limitations. This is not a theoretical concern — it will affect query performance for any user who hasn't cleared notifications in 30+ days.

### 7. APNs JWT Key Rotation Is Specified Incorrectly

The proposal says to rotate JWT keys every 55 minutes. APNs JWT tokens (not keys) expire after 1 hour and should be refreshed, but the underlying APNs authentication key (the .p8 file) is a long-lived credential that should not be rotated on a 55-minute schedule. Rotating the .p8 key requires revoking and re-uploading in Apple Developer Portal and redeploying. If the proposal means token refresh, it's using wrong terminology in a way that will confuse E2 during implementation. If it actually means key rotation, it describes an operationally dangerous and unnecessary procedure.

### 8. No Description of What Happens When Redis Goes Down

Redis is the single point of failure for the entire notification pipeline: the priority queue, the preference cache, the aggregation windows, the WebSocket pub/sub, the SMS rate limiting counters, and the unread count cache all depend on it. The proposal mentions "proven infrastructure" and "reliability" as priorities but has no described Redis HA configuration, no failover behavior, and no degradation path. The section on E4's responsibilities mentions "failure handling" but there's no actual content about what failure handling means for the most critical dependency.

### 9. The Preference Check Cache Invalidation Is Unaddressed

Section 2 states: "User preferences are cached in Redis. Checking at routing keeps workers dumb and fast." There is no described TTL, invalidation strategy, or consistency model for this cache. If a user turns off push notifications, how long until the cache reflects that? If the TTL is long (say, 1 hour), users will continue receiving notifications they've disabled. If the TTL is short, you're adding significant Redis read pressure at 1,750 req/sec peak. Neither path is discussed.

### 10. Four Engineers Cannot Own This Operational Surface in Six Months

The proposal assigns E4 to "Reliability, monitoring, failure handling, DevOps" as a single person's primary responsibility. The actual operational surface includes: Redis cluster management, Postgres partition maintenance and vacuuming, SendGrid webhook processing, Twilio webhook processing (STOP/HELP compliance), APNs feedback service, FCM token purge jobs, WebSocket server fleet, delivery worker fleet, dead-letter queue processing, TCPA timezone enforcement jobs, suppression list sync jobs, and the ingestion API. This is not one engineer's primary responsibility — it's a platform team. The proposal acknowledges "no dedicated QA" as a risk but doesn't acknowledge that E4's scope is undeliverable.