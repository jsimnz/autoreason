## Real Problems with This Proposal

### 1. The "Decision Gate" Undermines Month 2 Commitments

The proposal says "do not finalize Redis cluster sizing until two weeks of production data" but also commits to "ship a working system in month 2." These conflict directly. If production launches in month 2, you need infrastructure provisioned before that. Two weeks of production data means mid-month-2 at the earliest, which is after you needed the sizing decision. The proposal never resolves this contradiction.

### 2. The Base Case Multiplier Is Unexplained

The peak calculation uses 3× as a multiplier ("Peak/sec (3×)") with no justification. For a social app, notification spikes are event-driven — a viral post, a celebrity joining, a breaking news moment. These can produce 10–20× sustained load for minutes, not 3× for a few hours. The 3× figure appears to be borrowed from general web traffic patterns, which don't apply to notification systems with correlated triggers.

### 3. SMS Cap Enforcement Has a Race Condition

"This is enforced at the router, not the delivery worker — we never enqueue SMS we won't send." But with distributed router instances, two simultaneous routing decisions for the same user can both read a count of 2, both decide to send, and both enqueue — exceeding the per-user cap of 3. The proposal acknowledges Redis atomic ops elsewhere (Lua scripts for the queue) but doesn't apply that thinking here.

### 4. The In-App Bypass Creates Inconsistent Delivery Guarantees

The proposal explicitly routes in-app notifications around the queue: "if the DB write fails, we retry at the application layer, not through a queue." But this means in-app notifications have different retry semantics, different dead-letter handling, and different observability than every other channel. When debugging a missed notification, engineers must check two completely separate systems. The proposal frames this as a simplification but it adds a second code path that needs its own monitoring, its own failure modes, and its own runbook.

### 5. WebSocket Delivery Has No Fallback

The real-time path is: write to DB → publish to Redis Pub/Sub → WebSocket → client. If the client's WebSocket connection drops between the publish and receipt, the notification is in the DB but the client has no mechanism described for detecting the gap. The proposal doesn't address how clients discover they missed real-time events, whether they poll on reconnect, or what the consistency guarantee is between the DB state and what the client has seen.

### 6. E4 Owns an Unrealistic Scope

E4 owns email integration, SMS integration, reliability engineering, monitoring, and DevOps. Email alone involves webhook processing, bounce handling, suppression list sync, IP warming, deliverability monitoring, and template deployment. SMS involves STOP handling, carrier error codes, and Twilio webhook processing. "Reliability and monitoring" is a full-time role at many companies. Grouping these because they're "webhook-heavy" is an organizational rationalization, not a workload analysis. The backup assignment (E2) has no described capacity to absorb this.

### 7. APNs Token Handling Has an Unaddressed Failure Mode

The proposal says "APNs 410: record Apple's provided timestamp; tokens registered *after* that timestamp remain valid." But the proposal stores tokens with `last_used_at` and `is_valid` columns — there's no `registered_at` column in the schema. The comparison Apple requires (registration timestamp vs. Apple's provided timestamp) cannot be performed with the described schema.

### 8. The Digest Termination Logic Has an Edge Case That Contradicts Its Own Stated Behavior

The proposal says: "a user generating 2 events/day will receive a digest at most once per week." But the code purges events older than 7 days unconditionally (`purge_events_before(user_id, cutoff)`) before checking the threshold. If the user has 13 events accumulated over 6 days (under the threshold), on day 7 the oldest events are purged before the count check. The user may never cross `MIN_DIGEST_ITEMS` in a single window if their event rate is steady but low. The "at most once per week" claim is wrong — it may be never.

### 9. Partition Pre-Creation Is Described but the Failure Mode Is Not

"Monitoring alert fires if the current month's partition does not exist." At 10M rows/day, if the alert fires because the partition wasn't pre-created, the first insert attempt fails. PostgreSQL range partitioning with no default partition rejects inserts that don't match any partition — it doesn't queue them. The alert is reactive to a condition that has already caused data loss. The proposal doesn't address whether there's a default partition, what happens to in-flight notifications during the gap, or what the recovery procedure is.

### 10. The OneSignal/Braze Cost Estimate Is Presented Without a Source

"OneSignal/Braze saves 4–6 weeks of integration work but costs $50–150K/year at our scale." OneSignal has a free tier and a Growth plan at ~$9K/year for 10M MAU. The $50–150K figure appears to be for enterprise contracts or Braze specifically. Using this range to justify building direct integrations — which then requires E2's full time and carries the APNs token management complexity described above — may be based on an inflated cost comparison.

### 11. The Carry-Forward Logic Can Cause Double-Sends

The `build_daily_digest` function calls `carry_forward_to_next_digest(events)` when below the threshold, but there's no described locking or idempotency mechanism. If the daily digest job runs twice for the same user (retry after timeout, duplicate cron trigger), events could be carried forward twice and appear in two separate future digests. The proposal describes idempotency concerns elsewhere but not here.

### 12. "Revisit at 50M MAU" Appears Four Times Without Triggers

The proposal defers four separate architectural decisions to "50M MAU" — per-channel queues, SendGrid vs. SES cost, managed services, and the single-queue design. There's no described mechanism for tracking current MAU, no owner for making the revisit decision, and no lead time estimate for the architectural changes. If growth is faster than expected, these revisits could all become urgent simultaneously.