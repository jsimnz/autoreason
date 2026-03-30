## Real Problems with This Proposal

### 1. The TTL Logic Is Broken for Queue Entries

The code stores the full payload in both a `setex` key (with TTL) and an `lpush` (no TTL). Redis Lists have no per-element TTL. Once pushed, a P0 notification sits in the list forever until a worker pops it. The 5-minute "stale OTPs are worse than no OTPs" guarantee is entirely fictional — a P0 OTP queued during a Redis slowdown will be delivered hours later. The `ntf:{id}` key will expire, but the queue entry won't. The design justification for separate queues partially rests on TTL semantics that the implementation doesn't actually enforce.

### 2. The Lua Script Provides No Atomicity Benefit

The document claims the Lua script batches multiple `RPOP` calls into a single round-trip. That's true for latency, but the script provides zero atomicity across the batch. Each `RPOP` is individually atomic; the script is not a transaction. If the Redis connection drops mid-script, some items are already popped and gone. The document simultaneously argues against the ID-only approach because of crash windows, then uses a Lua script that has its own crash window across a batch of 50. The full-payload approach narrows but does not eliminate loss.

### 3. Worker-to-Queue Mapping Arithmetic Doesn't Add Up

The document states 14 workers total, then 28 with 2× headroom. The priority queue table shows P0=2, P1=8, P2=4, P3=4 = 18 workers, not 14. The channel capacity table (FCM=4, APNs=3, Email=2, SMS=1, In-app=4) sums to 14 but maps to different organizational units than the priority table. These are never reconciled. It's unclear whether "28 workers" means 28 per channel, 28 per priority tier, or 28 total, and the two tables are inconsistent with each other.

### 4. P0 Is Critically Under-Resourced

P0 gets exactly 2 workers — 1 FCM and 1 APNs. There is no redundancy. A single worker crash means P0 OTPs and security alerts queue with no processing until the worker restarts. For the tier the document calls "non-negotiable for security," a single-worker-per-channel design with no failover is a serious operational gap. The document acknowledges Redis failover as a P0 delivery risk but ignores worker-level single points of failure entirely.

### 5. APNs Throughput Calculation Is Wrong

The document states "20 persistent connections with ~40ms RTT per request, the pool delivers approximately 500 requests/second." 20 connections ÷ 0.040 seconds = 500/sec only if each connection handles exactly one in-flight request at a time. HTTP/2 supports multiplexing — APNs specifically supports multiple concurrent streams per connection. The calculation treats HTTP/2 like HTTP/1.1. The stated 1.4× headroom figure is therefore unreliable, and the alert threshold derived from it is also unreliable.

### 6. The In-App Peak Demand Correction Is Inconsistently Applied

The document correctly notes that in-app demand should be adjusted for active users (~350/sec, not 1,040/sec). This correction is never applied to the queue drain analysis, which uses "combined worker capacity of ~8,000+ notifications/sec" against total volume including the overcounted channels. More importantly, the same active-user logic should arguably apply to push notifications too — a push to an offline user is different from one to an active user — but the document doesn't examine this.

### 7. The Deduplication Key and Queue Entry Are Not Kept Consistent

The `ntf:{id}` key is described as being "retained for deduplication checks." But the dequeue code never checks it. There is no code shown that consults this key before processing. If a notification is enqueued twice (e.g., due to a retry on a failed `pipeline.execute()`), both full payloads sit in the queue and both will be processed. The deduplication mechanism is described but not implemented in the shown code path.

### 8. Month 2 Ship Date Has No Buffer for Integration Failures

The timeline ships a working system in month 2 with E2 owning both FCM and APNs simultaneously. APNs certificate management, provisioning profiles, and sandbox/production environment differences are non-trivial. FCM token registration and the migration from legacy FCM to HTTP v1 API are also non-trivial. Doing both in parallel in the same 8-week window, while E1 is simultaneously building the core pipeline those integrations depend on, leaves no room for the commonplace delays in third-party API onboarding. There's no stated contingency if push isn't ready by month 2.

### 9. The SMS Budget Analysis Uses the Wrong Baseline

The document calculates SMS cost against 1M/day and then caps at 100K/day. But OTP volume is not bounded by the cap — it's driven by login and registration events. At 10M MAU with normal authentication patterns, OTP volume alone could approach or exceed 100K/day during growth phases or after a forced re-authentication event (security incident, session expiry policy change). The cap and the "always permitted" carve-out for OTPs are in potential conflict, and the document doesn't model OTP volume independently.

### 10. WebSocket Fanout Architecture Is Unspecified but Load-Bearing

The in-app path terminates in "Redis Pub/Sub → clients" with no design. Redis Pub/Sub has no persistence — a message published while a client is momentarily disconnected is lost. For a system that separately stores in-app notifications in PostgreSQL, the relationship between the pub/sub fanout and the stored record is never defined. Does the client re-fetch on reconnect? Is there a sequence number? This is a significant surface area handed to E3 with no design guidance and no timeline allocation visible in the team table.