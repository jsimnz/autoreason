## Real Problems

### 1. The Peak Multiplier Math Is Internally Inconsistent

The document claims a 10× multiplier, then provisions for "5,000/sec sustained (8.5× average) and 12,000/sec burst (20× average)." The base average is ~590/sec. 5,000/sec is 8.5×, not 10×. 12,000/sec is 20×. The document never actually provisions for 10× (5,900/sec sustained). The multiplier label is detached from the actual numbers used.

### 2. The Synthetic Load Test Cannot Validate What It Claims To

The document says the month-1 load test at 3,500/sec "validates sizing without requiring production data." But the test is run against staging, which shares no production traffic patterns, no production token distribution, no real APNs/FCM endpoints, and no actual SendGrid/Twilio rate limits. It validates that the queue processes synthetic messages. It does not validate that FCM doesn't throttle at 2,000/sec for a new sender, that APNs certificate handling holds under load, or that SendGrid's IP warming constraints interact badly with burst traffic. The claim of validation is overstated.

### 3. The SMS Cap Lua Script Has a Logic Bug

The script does `SET key 1` on first use, then `INCR` on subsequent calls. If the cap is 3, the sequence is: first call sets to 1 (count = 1, allowed), second call increments to 2 (allowed), third call increments to 3 (allowed), fourth call reads 3, which is not `< cap` (3 < 3 is false), so it's blocked. That means 3 SMS are sent, which matches the cap. But the `INCR` happens *after* the `< cap` check, meaning the script reads the old value, checks it, then increments. On the third allowed call, it reads 2, increments to 3, returns 1. That's correct. However, the script never handles the case where `INCR` is called but the key expired between the `GET` and the `INCR` — a race condition the document explicitly claims this script eliminates. The script uses `GET` then `INCR` as separate commands, which are not atomic together despite being in Lua. Redis Lua scripts *are* atomic, so this is fine — but the explanation "two simultaneous routing decisions serialize on this script" is the actual reason it works, not the logic structure, and the document never explains this correctly.

### 4. The Global SMS Cap Is Dropped Silently With No User Notification

The document states that when the global 200K cap is hit, non-auth SMS is "dropped, not queued." There is no mention of what happens to the user experience — no fallback to push or email, no logging to the delivery event table as a `dropped` state, no alerting to the on-call engineer that the cap was hit mid-day. A notification that enters the router, passes preference checks, passes per-user cap checks, and then is silently dropped at the global cap level will appear in no delivery failure metric. It simply vanishes.

### 5. The Delivery Event Log Is a Write Bottleneck Under Spike Conditions

Every notification writes multiple rows to `delivery_events` — at minimum `created`, `enqueued`, and `delivered` or `failed`. At 12,000/sec burst, that's potentially 36,000+ row inserts per second into a single partitioned PostgreSQL table on an RDS db.r6g.2xlarge. The document never analyzes whether this is sustainable. PostgreSQL on that instance class handles roughly 10,000–30,000 simple inserts/second depending on write amplification, WAL pressure, and index maintenance. The `idx_delivery_events_notification` index on a high-insert table will degrade under this write rate. The document treats this table as free observability infrastructure when it is actually a potential single point of failure during the exact conditions — spike traffic — where you most need observability.

### 6. In-App Notifications Have No Defined Consistency Model for WebSocket Delivery

The document says in-app notifications publish to Redis Pub/Sub after the DB write and that "client polls on reconnect." This means there are two delivery mechanisms (Pub/Sub push and poll) with no defined reconciliation. If a client is connected but the Pub/Sub message is lost (Redis Pub/Sub has no persistence and drops messages if a subscriber is slow or disconnected), the client receives nothing until it polls. The document never defines the polling interval, the poll query structure, or the maximum staleness a client will experience. For a social app where in-app notifications are 20% of volume (~10M/day), "client polls on reconnect" is doing a lot of unexamined work.

### 7. The E4 Overlap Problem Is Acknowledged But Not Actually Resolved

The document flags that email and SMS integrations overlap in weeks 1–6 and says the schedule "staggers these." But the stagger described is: email webhooks are month-1 priority, SMS STOP handling is month-2 work. E4 still owns both simultaneously in months 2–3. The document says "E2 is documented on the email webhook schema by end of month 1" as a mitigation, but E2's primary responsibility is push integrations (APNs + FCM), which is also a month-1–2 deliverable. The cross-training mitigation creates a workload problem for E2 that is not analyzed.

### 8. The Scaling Triggers Table Has Circular Dependencies

The trigger for "Self-operated infrastructure" requires team size >12 engineers AND costs >$30K/month AND "a specific operational limitation is documented." The 12-week lead time means the team needs to make this decision before the limitation becomes critical. But the trigger condition requires the limitation to already be documented — meaning it must already be causing problems. At 12 weeks lead time, by the time the trigger fires and is acted on, the team has been operating under the limitation for 3 months. This is not a forward-looking trigger; it's a lagging indicator dressed up as a proactive one.

### 9. The Base Case DAU Assumption Is Structurally Fragile

The model uses DAU = 30% of MAU = 3M. This is stated as a fixed assumption throughout. But DAU/MAU ratio is one of the most volatile metrics in social apps — it varies from 15% to 65% depending on product stage, notification strategy, and retention. The document acknowledges uncertainty in notification rate per DAU but treats DAU itself as a known constant. If DAU is 50% of MAU (common for engagement-heavy social apps), total daily notifications nearly double to ~85M at the base per-DAU rate, which is close to the "high" scenario. The infrastructure provisioned for "base case" may be the median outcome, not a conservative one.

### 10. The Runbook Requirement Has No Defined Scope or Quality Bar

"Every integration has a documented runbook by end of month 1" appears twice. There is no definition of what a runbook must contain, no review process, and no owner responsible for verifying they exist and are accurate. Runbooks written under month-1 delivery pressure without a template or review gate are likely to be incomplete. The document treats runbook existence as equivalent to operational readiness, which it is not.