## Real Problems

### 1. The Lock Fallback Is a Hard Failure Path, Not a Graceful Degradation

When the distributed lock is held by another process and `self._local_token` is `None`, the code waits "briefly and retry" — but the code shown has no retry loop, no sleep, and no actual implementation. It falls off a cliff. On cold start of all 43 workers simultaneously (deploy, crash recovery), every process has `_local_token = None`, they all race for the lock, 42 lose, and 42 processes have no token and no code path to get one. The comment "wait briefly and retry" is not code.

### 2. The Race Condition Acknowledgment Understates the Actual Risk

The document says a preference change "can take up to 10 minutes to propagate in the worst case" and calls it "annoying, not dangerous." But the suppression logic for blocks also relies on the same write-through cache path being described. The document then says blocking is "always Postgres-authoritative, never cache-only" — but this is asserted, not enforced architecturally. Nothing in the design prevents the router from reading a cached preference that hasn't been invalidated yet for a block event if the invalidation step fails silently. There's no compensating check described for the failure mode where step 2 (cache invalidation) fails after step 1 (Postgres write) succeeds.

### 3. In-App Bypass Creates an Unacknowledged Consistency Problem

In-app notifications bypass the queue entirely and go directly to Postgres. But the delivery log also goes to Postgres. If a user's action generates both a push notification (through the queue, with retry logic, with delivery logging) and an in-app notification (direct write), these two records are written through entirely different paths with no transaction boundary between them. The document never addresses what happens when one succeeds and the other fails, or how the system reconciles the delivery state of a single logical notification event that spans both paths.

### 4. The Viral Spike Math Assumes Uniform Distribution, Which Is Wrong

The document calculates that a 20× spike for 90 seconds produces ~1,053,000 additional queue items at ~500MB. This assumes the spike is evenly distributed across P0/P1/P2 queues in the same 70/20/8/2 channel ratio as steady state. A viral spike (someone famous posts something) generates predominantly P1 social notifications, not the steady-state mix. The P1 queue receives a disproportionate share of the spike. The 15 P1 workers are sized for steady-state P1 volume, not a 20× spike concentrated on one queue. P1 drain time during an actual viral event is not calculated anywhere.

### 5. The Month 2 Recalibration Has No Decision Owner or Authority

The document says "recalibrate against production data at month 2" and lists actions required at different volume thresholds. But for the ">5× estimate requires architecture review; queue infrastructure may need replacement with Kafka" scenario: who makes that call? What is the decision timeline? The system has been in production for 2 months with real users. A "Kafka replacement" is a multi-month project. The document presents this as a tidy branch in a table but doesn't acknowledge that discovering at month 2 that you need Kafka means the entire 6-month plan is invalid, and there's no contingency for that.

### 6. E4 Scope Resolution Is Circular

The document acknowledges E4's scope is too large, then resolves it by switching from self-managed to managed services (ElastiCache, RDS). But the remaining E4 scope — ElastiCache configuration and capacity planning, RDS query performance and schema operations, Datadog configuration, on-call participation — is still described as "a full-time job." A full-time job is the problem that was just acknowledged. The resolution doesn't reduce scope; it relabels it. E4 still owns infrastructure operations, database performance, observability, and on-call for a 50M notifications/day system, just on managed services instead of self-managed ones.

### 7. The SMS Budget Cap Mechanism Is Described But Not Designed

The document correctly identifies that SMS costs could reach $1.38M/month and says the solution is "a hard monthly budget cap." But the cap is never specified as a technical mechanism. How is the cap enforced? Is it a counter in Redis? What happens when the cap is hit — are SMS notifications dropped, queued, downgraded to push? Who gets alerted? What's the behavior for P0 SMS notifications (auth codes, security alerts) when the cap is hit? The document identifies the risk precisely and then defers the entire solution to an unspecified implementation.

### 8. The APNs Token TTL in Redis Is Set to 3600 Seconds, Not 2700

The token is refreshed every 2700 seconds (45 minutes) but stored in Redis with `ex=3600` (60 minutes). This means a token can sit in Redis for up to 60 minutes. Apple's spec says tokens expire after 1 hour. If a token is generated, sits in Redis for 58 minutes without being locally cached by any process, then gets read and used, it may expire mid-use within 2 minutes. The local cache uses the 2700-second threshold correctly, but the Redis TTL creates a window where a process can read a token from Redis that is valid per the Redis TTL but will expire before the next refresh cycle.

### 9. Worker Count Derivations Are Disconnected From Each Other

P0 workers are sized at 8 based on a 100,000-item/60-second security incident scenario. P1 workers are sized at 15 and P2 at 20, but no equivalent derivation is shown for P1 or P2. The document shows the P0 math (1,667/sec ÷ 200 req/sec per worker ≈ 8 workers) but P1 and P2 numbers appear without derivation. At steady-state peak of 1,750/sec total, with 70% push going through P1/P2, the channel dispatcher is handling ~1,225 push notifications/sec from P1+P2 combined. Whether 35 workers (15+20) can sustain that throughput against real APNs/FCM HTTP/2 connection limits, with actual network latency, is not demonstrated.