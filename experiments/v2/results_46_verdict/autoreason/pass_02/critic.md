## Real Problems with This Proposal

### 1. The Single Queue Is Understated as a Risk

The document calls the single priority queue the "core architectural bet" and says it's "revisited at 50M MAU." But it doesn't address what happens when the queue backs up under P0 load. A Redis sorted set with 51M items across all priority levels means P0 processing competes for the same Redis instance as P2 bulk operations. Under a backlog event — viral content spike, a bad deploy — P0 latency degrades before any circuit breaker can fire. The document never specifies what P0 latency SLAs are, so there's no way to know when this becomes a problem.

### 2. Redis Is Both the Queue and the Preference Cache

Redis is used for the priority queue (sorted sets), preference caching, WebSocket pub/sub, APNs JWT management, and worker coordination locks. This is a single point of failure for the entire system. The document acknowledges bus factor as the "primary organizational risk" but never names Redis as the primary infrastructure risk. A Redis outage or memory exhaustion event takes down everything simultaneously: queue processing stops, preference checks fail, APNs JWT rotation fails, and in-app delivery via WebSocket fails. There is no fallback described for any of these.

### 3. APNs JWT Lock Has a Race Condition

The `_rotate()` method uses `SET NX` with a 10-second expiry to prevent thundering herd during rotation. But the fallback path (`_get_with_fallback`) returns the previous token if the current token is absent — which is exactly the condition during initial startup or after a Redis flush. If the previous token is also absent, it calls `_rotate()` recursively, which may immediately fail to acquire the lock (another worker holds it) and recurse again. There's no depth limit on this recursion. Under a cold-start or Redis flush scenario, this can stack overflow or spin indefinitely.

### 4. FCM Throughput Math Is Internally Inconsistent

The document calculates peak FCM throughput as ~2,550 req/sec at 3× peak across 20 P1 workers (~128 req/sec per worker). It then states 50 persistent connections with ~100 concurrent streams = 5,000 concurrent in-flight requests as the capacity. But 5,000 concurrent in-flight is not the same as 5,000 req/sec — throughput depends on latency. If FCM p99 latency is 200ms, 5,000 concurrent streams yields ~25,000 req/sec. If p99 is 2 seconds, it yields ~2,500 req/sec. The document never states assumed FCM latency, so the throughput claim is unverifiable.

### 5. Digest Batching Code Is Truncated

Section 3.2 ends mid-sentence: `MAX_CARRY_FORWARD_EVENTS = 20` followed by a horizontal rule and nothing else. The carry-forward bounds logic that was explicitly promised ("we bound accumulation explicitly") is never shown. This is the section that was called out as a "common implementation error" — and then the implementation is missing entirely.

### 6. No Backpressure Mechanism Is Defined

The ingestion API accepts events and routes them to the queue, but there's no description of what happens when the queue is full, growing faster than workers can drain it, or when downstream providers (FCM, SendGrid) are rate-limiting. There's no circuit breaker, no load shedding policy, no mention of what the ingestion API returns to callers under overload. For a system processing 51M events/day, this is a gap that will be encountered in production.

### 7. Cross-Training Timeline Creates a Coverage Gap

The cross-training rotation is scheduled for month 3. But push goes live in month 2. If E2 (push owner) is unavailable during month 2 — illness, departure, on-call emergency — E4 (cross-trained on push) hasn't done their rotation yet. The document explicitly acknowledges bus factor as the primary risk and then schedules the mitigation one month after the highest-volume channel goes live.

### 8. Preference Check Consistency Is Understated

The document says preference changes "may not take effect immediately" during the routing-to-delivery window and calls this "acceptable for a social app." But there's no TTL specified for the Redis preference cache in this section (it says "explicit TTLs" and defers to Section 5). For a notification that sits in a backlog queue for several hours — which can happen during a processing backup — a user who opted out after routing but before delivery will still receive the notification. The document treats this as a minor caveat; for opt-out compliance in certain jurisdictions (GDPR, CAN-SPAM), it may not be.

### 9. Delivery Log Write Amplification Is Unexamined

Every notification writes to a PostgreSQL delivery log, which at 51M/day is ~590 writes/second average and ~1,770/second at peak. The document mentions PostgreSQL is also used for in-app notification storage (partitioned) and the suppression list sync. There's no discussion of whether this is one PostgreSQL instance, what the write capacity is, or how delivery log writes interact with in-app storage reads (which are described as "read-heavy"). PostgreSQL at 1,770 writes/second is achievable but not free — it requires explicit configuration and hardware sizing that's absent here.

### 10. S3 Archive Strategy Has No Defined Policy

The delivery log is described as "PostgreSQL + S3 archive" with no archival policy: no retention period, no trigger for archival (age? table size?), no description of what "archive" means operationally (is it still queryable? for how long?). For a system generating 51M log entries/day, this is approximately 350M rows/week. Without a defined archival policy, PostgreSQL table growth will become a problem on a known timeline that the document never calculates.

### 11. Month 6 "Hardening" Is Not a Real Phase

The final month is described as "chaos testing, runbook review, load testing to 2× peak." But chaos testing requires a known steady state to test against — you can't chaos test a system that was just built in month 5. Running chaos experiments on a system without established baseline behavior produces noise, not signal. More fundamentally, hardening deferred to month 6 means five months of production traffic on a system that hasn't been load tested. The load testing target of "2× peak" also contradicts the earlier claim that month 6 load tests to "2× peak" — the system was already designed for 3× peak throughput, so 2× is below the design target.