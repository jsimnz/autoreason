## Real Problems with This Proposal

### 1. The Sensitivity Matrix Has Identical Rows

In the full sensitivity matrix, the row for "15% DAU, 15 notifications/user" and the row for "25% DAU, 15 notifications/user" produce identical totals (~41M/day, 1,420/sec peak). This is arithmetically wrong — 1.5M DAU × 15 notifications ≠ 2.5M DAU × 15 notifications. The push+in-app column already shows different values (19.5M vs 37.5M), but the totals and peak columns are identical across these two rows. The sizing argument built on this table is therefore based on corrupted numbers, and the claim that "2,500/sec covers the planning basis with 75% headroom" may be incorrect.

### 2. The Version Fencing Logic Doesn't Actually Solve the Stated Race Condition

The proposal claims the `<` (strict less than) comparison fixes the race condition where a reader re-caches stale data after invalidation. It doesn't. The Lua script only fires on writes — it controls whether the *existing* cache entry gets deleted. It does nothing to prevent the scenario the proposal itself describes: Thread B reads stale data, Thread A deletes the key, Thread B then re-caches the stale data with a fresh TTL. Thread B's re-caching happens *after* the Lua script has already run and deleted the key. The version fence has no mechanism to intercept or reject that re-population. The residual staleness acknowledged at the end is not just a 60-second TTL issue — it's a structural gap in the solution.

### 3. The `get_user_preferences` Cache Population Has No Version Check

When the cache is cold and `get_user_preferences` reads from the database and populates Redis, there is no version check or atomic guard. During a write, the sequence can be: write completes, Lua script deletes cache key, concurrent reader queries DB replica with replication lag, reader gets old version, reader populates cache with stale data and a fresh 60-second TTL. The version fencing mechanism the proposal spent considerable space justifying is entirely bypassed at the most vulnerable moment — cache population from a potentially lagged replica.

### 4. The SMS Budget Sign-Off Creates a Real Delivery Risk

The proposal states SMS-specific elements are "explicitly gated" on budget approval, but E2 is assigned to channel integrations including Twilio as a primary Month 1–2 responsibility. If the SMS budget decision is delayed — which is likely given it requires external sign-off — E2's work plan is blocked or must proceed speculatively. The proposal doesn't address this dependency on the timeline or team allocation sections, creating a coordination failure the document itself could cause.

### 5. The 3× Peak Multiplier Is Applied to All Channels Identically

SMS is event-triggered (auth events, OTPs) and does not follow the same social-traffic peak pattern as push and in-app notifications. Applying a 3× multiplier to 75K SMS/day implies 225K SMS at peak, which would be ~$3,375 in Twilio costs in a single peak period. More importantly, OTP volume is driven by login events, not time-of-day social patterns. The multiplier is borrowed from the wrong domain and the proposal doesn't acknowledge this.

### 6. The Escalation Path for Architecture Review Is Underspecified

The Month 2 checkpoint table says ">60% above plan" triggers an "architectural review" owned by "all engineers" with a decision in 48 hours. But the proposal has already made architectural commitments (per-channel queues, Redis sorted sets, PostgreSQL for in-app) that cannot be revisited in 48 hours without scrapping significant work. "Architectural review" at Month 2 is not a real option — it's a placeholder that creates false confidence the system can adapt to that scenario.

### 7. The Preference UI Guidance Contradicts the Cache Behavior Description

The proposal says the preference UI "should reflect" that changes take effect within 1 minute. But the residual staleness section acknowledges the stale-cache-after-write race condition can extend staleness beyond the TTL. A user who changes preferences, triggers the race condition, and receives notifications for longer than 60 seconds will have been given incorrect information by the UI. The proposal treats "up to 60 seconds" as the worst case when it is actually the average case and the race condition is the unquantified tail.

### 8. Dead-Letter Queue Ownership Has a Gap

The ownership table assigns DLQ handlers to E4, with E1 as reviewer. But E2 owns channel integrations, and DLQ entries for push, email, and SMS will require channel-specific knowledge to triage (e.g., distinguishing an APNs invalid token from a transient FCM 503). E4 owning DLQ handling without channel expertise — and E2 not appearing in the DLQ ownership row at all — means the person who will actually debug 2am DLQ alerts lacks documented authority and context.