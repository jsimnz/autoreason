## Real Problems with This Proposal

### 1. The Priority Queue Math Is Broken

The score formula `PRIORITY_WEIGHTS[priority] - (time.time() / 1e10)` doesn't work correctly. `time.time()` returns something like `1700000000.0`, divided by `1e10` gives `0.17`. So P1's score range is `[999999.83, 1000000.0]` and P0's range is `[-0.17, 0.0]`. P0 always beats P1, fine — but within P0, newer notifications get *higher* (worse) priority scores than older ones because you're subtracting a small positive number. The FIFO-within-priority claim is backwards. Older P0 items have scores closer to 0, newer items have more negative scores and will be dequeued first. This is LIFO, not FIFO.

### 2. The Dequeue Operation Is Not Atomic Despite the Claim

The proposal claims a Lua script makes it atomic, then shows code that doesn't use a Lua script — it uses a pipeline. Redis pipelines are not atomic. `zrange` followed by `zremrangebyrank` in a pipeline can allow two workers to read the same items between the two commands. This is exactly the race condition the proposal claims to have solved.

### 3. In-App Notification Volume Makes the Schema Unworkable

10M rows/day × 90 days = 900M rows per partition before archival. The proposal acknowledges this requires monthly partitioning, but the indexes defined are on the base table, not on partitions. PostgreSQL won't automatically create those indexes on new partitions — each new partition needs indexes created manually or via a partition management tool. There's no mention of this operational requirement, and with 4 engineers and no dedicated DBA, this will be missed.

### 4. SMS Cost Estimate Is Wrong by an Order of Magnitude

The proposal says 1M SMS/day at $0.0075 = $7,500/day. That's $225,000/month in SMS costs alone, for a social app. This is not treated as a crisis — the proposal just calls it "expensive" and moves on. At 10M MAU with 2% SMS penetration, this is an existential cost that would consume most or all of a typical Series A/B startup's infrastructure budget. The gating logic described (3 SMS/user/day cap) would do almost nothing to address this because the 1M/day estimate already assumes SMS is gated to auth and critical alerts.

### 5. The DAU × 17 Notifications Math Is Internally Inconsistent

The proposal estimates 17 notifications/user/day for DAU (3M users), yielding 50M/day. But then it says 20% are in-app = 10M/day. If in-app notifications only go to logged-in users, and DAU is 3M, that's 3.3 in-app notifications per active user per day — plausible. But push notifications (70% = 35M/day) are sent to 3M DAU, implying ~11.7 push notifications per active user per day. This seems extremely high and would result in mass opt-outs, but more importantly, the proposal never reconciles push delivery against MAU vs. DAU. Push goes to installed-app users regardless of daily activity, so the denominator for push should be closer to MAU (10M), not DAU.

### 6. The Digest Carry-Forward Logic Creates Silent Data Loss Risk

```python
if len(grouped) < MIN_DIGEST_ITEMS:
    carry_forward_to_next_digest(events)
    return None
```

`carry_forward_to_next_digest` is never defined or described. If a user consistently generates 1-2 digest-eligible events per day and never hits the threshold of 3, their notifications are carried forward indefinitely. There's no cap on how long events accumulate, no maximum age after which they're discarded, and no fallback delivery path. A user could have notifications silently held for weeks.

### 7. Redis Pub/Sub for WebSocket Delivery Is Unreliable by Design, But the Fallback Is Underspecified

The proposal acknowledges WebSocket messages can be missed and says "the client polls on reconnect." But there's no polling endpoint defined in the API spec, no description of what "reconnect" means (network blip? app backgrounded for 2 hours?), and no maximum staleness guarantee. The API shows `GET /v1/notifications` with cursor pagination, but there's no specification of how the client knows it missed messages or how it determines where to resume. This is described as acceptable but the failure mode — a user missing notifications with no indication — is not quantified.

### 8. APNs JWT Key Rotation Is Operationally Fragile

"Rotate keys every 55 minutes" for APNs JWT authentication is mentioned as a configuration detail with no implementation. APNs JWTs expire after 1 hour, so rotating at 55 minutes is correct, but this requires generating new JWTs, distributing them to a pool of 20 persistent connections, and handling in-flight requests that are using the old JWT. If this rotation fails or is delayed — due to a Redis hiccup, a deployment, or a worker crash — all APNs delivery stops silently. This is a single point of failure with no monitoring or fallback described.

### 9. The Team Allocation Has a Single-Point-of-Failure Problem

E2 owns all four channel integrations: APNs, FCM, SendGrid, and Twilio. These are the four revenue-critical delivery paths. If E2 leaves, is sick, or is on vacation during an incident, no other engineer has ownership of the most operationally complex part of the system. The proposal acknowledges "no dedicated QA" as a risk but doesn't acknowledge the bus factor on channel integrations, which is higher-risk.

### 10. The Suppression and Preference Cache Has No Invalidation Strategy

"User preferences are cached in Redis" is stated as a design decision, but there's no TTL mentioned, no invalidation on preference update, and no description of the data structure. If a user turns off push notifications, how long until that change is reflected? If the cache TTL is long (e.g., 1 hour), users who opt out of a channel will continue receiving notifications for up to an hour — a TCPA/GDPR compliance risk for SMS and email respectively. This is especially serious given the proposal's emphasis on SMS consent compliance.

### 11. The FCM Batch Size Claim Is Wrong

The proposal states "Batch size: 500 tokens per FCM v1 batch request." FCM HTTP v1 API does not support batch sending to multiple tokens in a single request — that was a feature of the legacy FCM API which was deprecated. The v1 API requires one request per device token. This is a fundamental misunderstanding of the API being used, and at 35M push notifications/day, the throughput math built around 500-token batches is entirely wrong.