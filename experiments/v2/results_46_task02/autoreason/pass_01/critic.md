## Real Problems

### 1. The Pipeline Is Not Atomic — Data Loss Is Guaranteed

The routing step writes to the Redis queue and the PostgreSQL in-app store as separate operations with no transaction boundary. If the process crashes between these two writes, or if Redis accepts the enqueue but Postgres write fails (or vice versa), you have a notification that exists in one place but not the other. At 50M/day, even a 0.01% failure rate is 5,000 lost or duplicated notifications per day. The proposal never addresses this, and "proven infrastructure over custom-built components" doesn't solve it.

### 2. The Dequeue Operation Is Not Actually Atomic

The proposal acknowledges contention on zrange+zrem and says "we use a Lua script to make it atomic." But the Lua script shown in the proposal is not the actual dequeue — the code shown uses a pipeline (which is not atomic, it just batches round trips). Then it does individual `redis.get()` calls for each notification ID outside the pipeline. If a worker crashes after removing items from the sorted set but before processing them, those notifications are silently dropped. There is no dead-letter mechanism described for this path.

### 3. Redis as Primary Queue Has No Persistence Guarantee by Default

Redis AOF/RDB persistence is not mentioned anywhere. If the Redis instance restarts with default configuration, the entire queue is gone. At 50M notifications/day, the queue at any given moment contains millions of in-flight items. The proposal treats Redis as durable infrastructure without specifying the durability configuration required to make it so.

### 4. The Priority Scoring Math Breaks Down

The score formula is `PRIORITY_WEIGHT - (timestamp / 1e10)`. At Unix timestamp ~1.7 billion, dividing by 1e10 gives ~0.17. So the timestamp contribution to the score is less than 0.2, while priority weights are spaced at 1,000,000 apart. This means FIFO ordering within a priority level is effectively meaningless — the timestamp component is so small relative to the weight gaps that floating point precision will cause ordering anomalies. More critically, a P2 notification from 24 hours ago has a score of approximately 2,000,000 - 0.17 = 1,999,999.83, nearly identical to a brand-new P2 notification. FIFO within priority doesn't work.

### 5. SMS Cost Is Wrong and the Channel Is Under-Gated

The proposal states SMS costs ~$7,500/day at 1M messages. Twilio's standard rate is $0.0079/message outbound in the US, but that's domestic only. International SMS runs $0.05–$0.15/message. For a 10M MAU social app, a substantial fraction of users are international. The actual SMS cost could be 3–10× higher than modeled. More critically, the proposal allows users to configure "critical alerts" like mentions as SMS. Mentions at any meaningful engagement rate on a 10M MAU social app will blow through both the rate limit and the budget. A 3 SMS/user/day cap on 10M users is 30M SMS/day maximum exposure — $237,000/day — and the proposal has no circuit breaker for total spend.

### 6. In-App Notification Table Will Not Scale as Designed

The proposal stores 10M in-app notifications per day, partitioned monthly by `created_at`, and drops partitions after 90 days. That's ~900M rows per quarter, ~300M rows per month per partition. The two indexes (`user_id, created_at DESC` with and without the partial filter) on a 300M-row partition will produce indexes that are themselves hundreds of gigabytes. The `read-all` endpoint (`POST /v1/notifications/read-all`) executes an UPDATE on potentially thousands of rows per user with no described batching. Under concurrent load from millions of users this will cause severe lock contention and table bloat. The proposal doesn't mention connection pooling, and a single PostgreSQL instance is implied.

### 7. WebSocket Architecture Has a Race Condition

The real-time flow is: write to DB → publish to Redis Pub/Sub → WebSocket server pushes to client. The proposal notes "if the WebSocket message is missed, the client polls on reconnect." But there's no described polling mechanism — the API spec shows only cursor-based pagination, not a "give me everything since timestamp X" endpoint. If a user receives 50 notifications while disconnected and reconnects, they get whatever the first page of the cursor-based API returns, with no guarantee they receive all missed notifications without manual pagination. The proposal doesn't describe how the client knows it missed anything.

### 8. The Digest Carry-Forward Logic Creates Unbounded State

```python
if len(grouped) < MIN_DIGEST_ITEMS:
    carry_forward_to_next_digest(events)
    return None
```

If a user consistently generates fewer than 3 digest-worthy events per day, their events carry forward indefinitely. The proposal doesn't describe where this carry-forward state lives, how long it's retained, or what happens when it accumulates for weeks. For low-activity users (a significant population on any social app), this creates unbounded growth in deferred state and means some users may never receive a digest email at all — which breaks re-engagement use cases.

### 9. No Described Backpressure Mechanism

The ingestion API has no described rate limiting or backpressure. If an upstream service fires a burst of events — a viral post getting 500K likes in an hour, a marketing team triggering a campaign, a bug causing a notification loop — the queue grows unboundedly. The proposal describes worker pool sizes (10/20/10 workers) but no mechanism to shed load, reject ingestion, or alert when queue depth exceeds safe thresholds. A viral event at 10M MAU scale is not an edge case.

### 10. APNs JWT Rotation Is Described Incorrectly

The proposal specifies rotating APNs JWT keys "every 55 minutes." APNs JWTs have a maximum validity of 60 minutes, but the token is a *signed JWT* — you don't rotate the signing *key* every 55 minutes, you issue a new *token* signed with the same long-lived key. Rotating the actual key requires uploading a new `.p8` file in App Store Connect, revoking the old one, and redeploying credentials. If the proposal intends key rotation (not token refresh), this would cause APNs authentication failures during the rotation window and requires coordination outside the system. If it intends token refresh, the terminology is wrong in a way that will confuse the engineers implementing it.