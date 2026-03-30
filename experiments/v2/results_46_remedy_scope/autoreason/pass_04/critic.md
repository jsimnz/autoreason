## Real Problems

### 1. Deduplication Race Condition Is Unsolved

The document says deduplication must happen at enqueue time and uses a Redis key check before enqueue. But "check BEFORE enqueue" is not atomic. Two concurrent events for the same notification ID can both pass the check before either sets the deduplication key. The document never shows the atomic check-and-set operation (e.g., SET NX). The prose claims the problem is solved; the implementation doesn't solve it.

### 2. Full Payload Storage Assumption Breaks Down at Scale

The document argues for full payload in queue entries to avoid a crash window. But at 50M notifications/day with peak bursts, storing full payloads in Redis Lists means Redis memory consumption is entirely payload-driven. A social notification payload with user content, media URLs, and metadata can easily be 1–5KB. At 8.4M queued excess items during a 2-hour peak, that's 8–42GB of Redis memory for queue contents alone — on top of expiry sorted sets, deduplication keys, preference cache, aggregation state, and pub/sub. The document never calculates Redis memory requirements. This is a critical omission for a managed ElastiCache sizing decision.

### 3. The Expiry Sorted Set Creates a Memory Leak

The companion expiry sorted set is only cleaned up at dequeue time when a worker checks and discards expired entries. But if a queue backs up severely (Redis slowdown, worker outage), expired entries accumulate in both the list and the sorted set. The sorted set is never explicitly pruned by a background process — the document describes no such process. Under sustained failure, the expiry sets grow without bound. This is the exact problem the TTL mechanism was supposed to solve, reintroduced in a different data structure.

### 4. APNs Throughput Figure Is Fabricated and Acknowledged as Such

The document explicitly states the 1,000 req/sec/worker figure "must be confirmed — it cannot be assumed," then uses it throughout all capacity planning tables, headroom calculations, and worker counts. The entire APNs column of the capacity table is built on an unvalidated number. If the real limit is 300 req/sec, the worker count is wrong. If it's 2,000, over-provisioned. The document identifies this as a problem but does not treat it as one — it proceeds as if the number is reliable.

### 5. Worker Count Arithmetic Is Internally Inconsistent

The team allocation table shows 25 total workers. The demand vs. capacity table shows worker counts per channel per priority (2+3+2+0=7 FCM, 2+2+1+0=5 APNs, 0+1+1+2=4 Email, 2+1+0+0=3 SMS, 0+2+2+2=6 In-app = 25). But the high-level architecture diagram lists P0=6, P1=9, P2=6, P3=4 = 25 total. These two decompositions are inconsistent: by channel gives 25, by priority gives 25, but the per-cell values don't reconcile. For example, P0 should have 2 FCM + 2 APNs + 0 Email + 2 SMS + 0 In-app = 6, which matches. P1 should have 3+2+1+1+2=9, which matches. P2 should have 2+1+1+0+2=6, which matches. P3 should have 0+0+2+0+2=4, which matches. Actually this specific check passes — but the document never shows this reconciliation, making it unverifiable at a glance and fragile to any single change.

### 6. OTP Spike Cost Model Is Inconsistent With the Architecture

The document models a security incident spike at 5–10× for 1–3 days, reaching 750K–1.5M OTP SMS/day. The SMS workers are sized at 3 total with ~200/sec combined capacity. 1.5M SMS/day requires sustained ~17/sec, well within capacity. But the document also states OTP SMS is "uncapped." During a spike to 1.5M/day, Twilio costs jump to ~$18,000/day. There is no approval workflow, spending alert, or circuit breaker described for this scenario. "Separately budgeted" is not the same as "controlled."

### 7. WebSocket Sequence Number Design Is Mentioned But Not Specified

The architecture diagram references "sequence-numbered events" for WebSocket fanout with "PostgreSQL catch-up on reconnect." Sequence numbers require a monotonic, gap-free counter per user — a non-trivial distributed systems problem. The document never specifies where these sequence numbers are generated, how gaps are detected on the client, what the catch-up query looks like, or how the sequence interacts with the in-app notification store. E3 is assigned this in months 3–4 with no design basis. This is a significant hidden complexity treated as an implementation detail.

### 8. The Feedback Processor Has No Design

The architecture diagram shows a Feedback Processor consuming bounces, opens, token invalidity, and delivery receipts. Token invalidity handling is operationally critical — sending to invalid FCM/APNs tokens wastes throughput and can result in FCM rate limiting. The document contains zero design for this component: no data model, no latency requirements, no description of how invalid tokens are removed from the preference store. It appears in a diagram and nowhere else.

### 9. Email Is Excluded From P0 But the Contingency Depends On It

The document states "Email is absent from P0 by design: OTPs must not be delivered via a channel with 5–30 minute delivery latency." The month 2 contingency is "email-only for non-critical notifications and SMS for OTP." This contingency is internally consistent. But if SMS integration is also delayed, the month 2 launch has no OTP delivery path. The contingency has a single point of failure that isn't acknowledged.

### 10. DAU/MAU Ratio Applied Inconsistently to Notification Rate

The document multiplies 3M DAU × 17 notifications/user/day = 51M ≈ 50M total. But 17 notifications/user/day is described as an "industry average for engaged social apps." DAU by definition includes only active users on that day, who are more engaged than average. Applying an average-engagement rate to an active-user count double-counts engagement. The 50M/day figure is likely an overestimate, but the document never addresses this. Given that the entire capacity plan flows from this number, the uncertainty should be quantified.