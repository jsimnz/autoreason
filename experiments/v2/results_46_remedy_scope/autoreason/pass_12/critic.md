## Real Problems

### 1. Token Bucket Logic Is Broken

The dispatch loop checks `p2_tokens >= 200` before consuming, but the bucket capacity is 2000 and refill rate is 200/sec. This means P2 only gets serviced when the bucket has accumulated 200 tokens — which takes 1 second of P1 load before P2 gets *any* slots. Then `consume_tokens("p2", 1)` consumes 1 token per dispatch, not 200. The threshold and consumption amount are inconsistent. The "200 credits/sec guaranteed minimum" claim is not what the code actually implements.

### 2. Token Bucket Has a Race Condition

`get_available_tokens` and `consume_tokens` are two separate Redis operations. Between them, another worker can consume tokens. The bucket check and consumption are not atomic. Under concurrent workers, multiple workers can each see sufficient tokens and all dispatch, collectively consuming far more than the guaranteed minimum — or conversely, the guarantee can be violated. The Lua script only atomicizes the read-and-update of the token count, not the check-then-consume sequence.

### 3. The Sorted Set Dequeue Script Removes TTL Enforcement

The original queue entries are in a Sorted Set scored by enqueue timestamp, which enables TTL expiry via `ZRANGEBYSCORE`. But `ZPOPMIN` removes the lowest score (earliest enqueue), which is correct for FIFO — but the TTL enforcement described in Section 2.2 requires a separate sweep to expire old messages. The dequeue script shown has no TTL check. There is no code shown for the TTL expiry sweep, no discussion of who runs it, how often, or what happens if it falls behind. The "companion expiry sorted sets" mentioned in the executive summary never appear in the actual design.

### 4. P1 Is Never Explicitly Serviced Under Load

The dispatch loop checks P2 and P3 token buckets, and if either has enough tokens it services that queue — then falls through to P1 as a default. But if P2 has 200+ tokens and P3 has 50+ tokens simultaneously, both lower-priority queues get serviced in sequence before P1 in that loop iteration. Under sustained high P2/P3 queue depth, P1 can be delayed by two dequeue attempts per loop cycle. P1 has "no cap — drain before P2/P3" in the table, but the code does not enforce this.

### 5. The 37-Hour Drain Time Is Presented as Acceptable

The design explicitly calculates that under extreme P1 load, P2 messages expire before delivery — and calls this "correct behavior." But this conclusion assumes the extreme scenario is transient. If sustained P1 load is a normal operating condition (e.g., a large user base with heavy messaging), P2 notifications — comments, reactions — are systematically never delivered. The design acknowledges this but frames it as a feature rather than quantifying how often it would occur at planning volume.

### 6. Recovery Lock TTL Argument Is Circular

The design states the recovery lock TTL is 90 seconds against a 60-second cycle, "closing the gap that would allow concurrent recovery instances." But this only prevents a second recovery instance from starting a new cycle while the first holds the lock. It does not address what happens when the recovery process itself crashes mid-run after reclaiming some messages but before completing. The lock expires after 90 seconds, a new instance starts, and messages already re-enqueued by the crashed instance get re-enqueued again. The deduplication layer is invoked as the solution, but the interaction between recovery and deduplication is never specified.

### 7. Heartbeat Coroutine Failure Mode Is Understated

The design argues the realistic cause of a >60-second block is a hung database call, and that timeouts resolve this before the reclaim threshold. But the heartbeat is a coroutine — in a single-threaded async runtime, a blocking database call in the main coroutine prevents the heartbeat coroutine from running regardless of timeout settings. The timeout resolves the block, but the heartbeat has already missed multiple cycles before that happens. The design's own 5-missed-heartbeat buffer may not be sufficient if the block duration equals the query timeout (30 seconds = 3 missed heartbeats), and the analysis assumes the heartbeat runs independently when it may not.

### 8. PostgreSQL Availability SLA Is Used Incorrectly

The design cites 99.99% availability for managed PostgreSQL to justify the ID-based approach. 99.99% annual availability is approximately 52 minutes of downtime per year, but it does not bound individual outage duration — a single incident could account for all of that budget. More critically, "managed PostgreSQL 99.99%" typically refers to the control plane SLA, not query latency or connection availability under load. Under high worker concurrency with payload fetches on every dequeue, connection pool exhaustion is a distinct failure mode not covered by the availability SLA. This failure mode causes the same symptom (workers pause) but is not transient in the same way.

### 9. The Re-Plan Decision Tree Has an Unexamined Gap

The traffic response matrix covers < 7.5M/day, 100M–225M/day, and > 225M/day. The range 7.5M–100M is the "on plan" range with no response specified. But the upper end of that range (say, 80M/day sustained) is nearly 2× the planning figure and would require meaningful infrastructure changes. The document implies no action is needed anywhere in this range, which is incorrect.

### 10. Worker Parameterization Claim Obscures Actual Coupling

The design claims shifting capacity between channels is "a configuration change and rolling restart, not a code change." But workers dispatch to channel-specific external APIs (FCM vs. APNs vs. SMTP vs. SMS gateway). A worker parameterized for push cannot dispatch email without the email dispatch function. The claim is technically true only if all dispatch functions are compiled into every worker binary and selected at startup — which is not stated and represents significant binary bloat and credential management complexity. If workers are instead specialized binaries, the claim is false.