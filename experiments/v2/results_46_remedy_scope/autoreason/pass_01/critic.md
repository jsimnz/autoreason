## Real Problems with This Proposal

### 1. The Single Queue Is a Liability, Not a Simplification

The proposal frames a single Redis sorted set as an operational simplicity win, but it creates a severe coupling problem. A burst of P2 social notifications (likes, follows) at 1,750/sec peak competes directly with P0 security alerts for the same zrange/zrem lock, even with Lua scripting. The "P0 always beats P1" guarantee depends on workers continuously draining the queue — if the queue backs up (provider outage, deployment, traffic spike), P0 latency degrades. There is no isolation. The proposal acknowledges this with "we'd revisit at 50M MAU" but the failure mode is a security alert arriving 45 seconds late, not a scale problem.

### 2. The Pipeline Stage Counts Are Not Coherent

At peak: 1,750 notifications/sec enter the queue. The proposal allocates 40 workers total (10+20+10). No throughput per worker is ever specified. We don't know if 40 workers can drain 1,750/sec or if the queue will grow unboundedly under sustained peak load. The peak multiplier of 3× assumes a 1-2 hour spike, which means queue depth could reach millions of items before draining. This is not analyzed anywhere.

### 3. The Dequeue Logic Has a Race Condition

The `dequeue_batch` pseudocode does `zrange` then `zremrangebyrank` in a pipeline. A pipeline is not atomic — it's a batched send, not a transaction. Multiple workers will pull the same items. The proposal says "we use a Lua script to make it atomic" but then shows non-atomic Python code. The actual Lua script is never shown. This is a core correctness guarantee being hand-waved.

### 4. The Priority Scoring Math Breaks Down

The score formula is `PRIORITY_WEIGHTS[priority] - (time.time() / 1e10)`. `time.time()` returns Unix timestamp in seconds, currently ~1.7×10⁹. Dividing by 1×10¹⁰ gives ~0.17. The P1 weight is 1,000,000. This means a P1 notification's score is ~999,999.83. The timestamp component contributes less than 1 unit of variation across all of time, effectively destroying FIFO ordering within priority bands. Within P2, all notifications have nearly identical scores and ordering becomes arbitrary.

### 5. The In-App Partitioning Strategy Is Underspecified in a Way That Will Cause Incidents

The proposal says "partition by `created_at` monthly" and "drop partitions older than 90 days." Monthly partitions means dropping a partition covers 30 days at a time — so at day 91 you drop the oldest month, which may contain notifications from day 61-90 that are still within the retention window. The boundary math is never reconciled. Additionally, PostgreSQL declarative partitioning requires the partition key in all unique constraints. The `PRIMARY KEY` on `id` alone will not work on a partitioned table — this schema will fail at creation.

### 6. SMS Cost Estimate Is Wrong by an Order of Magnitude

The proposal states "~$0.0075/message at Twilio volume pricing = $7,500/day at 1M." That math is correct. But 1M SMS/day is 30M/month. Twilio's volume pricing at 30M messages/month is not $0.0075 — that's closer to their list price for low volumes. At 30M/month you'd negotiate carrier surcharges, A2P 10DLC fees, and country-specific rates. More importantly, 1M SMS/day × 365 = $2.7M/year on SMS alone, for a feature serving 2% of notifications. This should be a budget-breaking number that drives the architecture, but the proposal treats it as an accepted constraint and moves on.

### 7. The WebSocket Architecture Has No Capacity Planning

"WebSocket for users who are actively using the app" — with 3M DAU, even 10% concurrent means 300,000 persistent WebSocket connections. The proposal offers no server count, no connection limits per server, no reconnection strategy under server failure, and no analysis of what happens to Redis Pub/Sub fan-out when a WebSocket server restarts and all 300K clients reconnect simultaneously. Redis Pub/Sub has no persistence, so messages published during reconnect are lost — the proposal says "the client polls on reconnect" but the polling endpoint and its load under a thundering herd scenario are unaddressed.

### 8. E4's Scope Is Unrealistic for One Engineer

E4 owns "Reliability, monitoring, failure handling, DevOps" for a system processing 50M events/day across four external providers, a partitioned PostgreSQL database, Redis clusters, and WebSocket infrastructure. This is not a single-engineer scope. The proposal acknowledges no dedicated QA as a risk but does not acknowledge that DevOps + reliability + monitoring for this system is itself a full-time job before failure handling is added.

### 9. The Digest Carry-Forward Logic Creates Unbounded State

The `carry_forward_to_next_digest` function is called when a digest has fewer than 3 items. There is no bound on how long events can be carried forward. A user who receives 1-2 events/day indefinitely never gets a digest and accumulates unbounded state. The proposal never specifies a maximum carry-forward age, a fallback flush trigger, or what happens to carried-forward events if a user unsubscribes from email.

### 10. APNs JWT Key Rotation Is Specified Incorrectly

"Rotate keys every 55 min" — APNs JWT tokens expire after 1 hour from the `iat` claim, but the key itself (the `.p8` file) does not rotate on a timer. The token (JWT) must be regenerated before expiration, but the proposal conflates token refresh with key rotation. With 20 persistent APNs connections and a 55-minute rotation, there is no specification of how in-flight requests are handled during rotation, whether connections are drained or killed, or how multiple worker processes coordinate so they don't each independently rotate simultaneously.

### 11. The Aggregation Window Design Loses Notifications Silently

The aggregation code sets a Redis key with a TTL and "adds to existing aggregation." When the aggregation TTL expires, something must flush the aggregated notification to the queue. This flush mechanism is never described. If the flush job fails or doesn't exist, aggregated notifications are silently dropped. The proposal shows the aggregation write path but not the read/flush path, which is where the correctness guarantee lives.

### 12. Month 6 "Hardening" Is Not a Phase, It's an Admission

Dedicating the final month entirely to hardening a system that has been in production since month 2 means the system runs in a non-hardened state for four months at 50M notifications/day. The proposal never defines what "hardening" means — load testing, chaos engineering, security audit, SLA definition — nor does it specify what quality bar is acceptable for months 2-5. For a team with no dedicated QA, this is not a risk acknowledgment; it's a plan to run a production system in a known-incomplete state.