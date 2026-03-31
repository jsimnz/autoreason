## Real Problems

### 1. The Claim Protocol Has a Race Condition With the Recovery Job

The recovery job re-enqueues events where `state = 'enqueued'`. But events in `state = 'enqueued'` are also actively dequeued by workers. After a Redis crash and AOF recovery, the recovery job will re-enqueue events that are *already in Redis* (restored from AOF). Workers will then race: one claims via the DB UPDATE, but the event_id now has two entries in the Redis sorted set. The claim UPDATE prevents double-delivery in the normal case, but the double-entry in Redis creates unnecessary contention and the proposal doesn't acknowledge this specific scenario.

### 2. The Partition Key Breaks the Primary Key

The PRIMARY KEY is `(event_id, created_at)`. This means `event_id` alone does not uniquely identify a row. The worker claim protocol does `WHERE event_id = %s AND state = 'enqueued'` — this query cannot use the primary key and must scan across partitions. At 430M rows across 30 partitions, this is a correctness and performance problem the proposal explicitly says it solved.

### 3. Idempotency Key Construction Is Underspecified for Recovery

The idempotency key is defined as `event_id + channel + attempt_number`. The `attempt_number` is incremented on retry. But when the recovery job re-enqueues a stuck `claimed` event, it resets state to `enqueued` — there is no mechanism shown for incrementing or tracking `attempt_number` through this path. The recovery path will reuse the same idempotency key as the original attempt, which defeats provider-side deduplication for the exact crash scenario the system is designed to handle.

### 4. The Recovery Job Window Is Arbitrary and Underjustified

The recovery query filters `created_at > NOW() - INTERVAL '2 hours'`. This means any event stuck for more than 2 hours is permanently abandoned — it will never be recovered. There is no alerting, dead-letter queue, or acknowledgment of this as a data loss boundary. The 2-hour figure has no stated basis relative to the 10-minute stuck threshold.

### 5. AOF Rewrite Scheduling Is Operationally Fragile

The proposal says AOF rewrites are "scheduled during off-peak hours." Redis AOF rewrites are triggered automatically by `auto-aof-rewrite-percentage` and `auto-aof-rewrite-min-size`, not by a cron schedule. The config shown uses the automatic triggers. There is no mechanism described to actually schedule rewrites at off-peak times — this is a stated operational property with no implementation.

### 6. Email Batching Reduction Factors Are Fabricated

The batching reduction multipliers (2.5×, 1.8×, 1.2×) are presented in a table with no derivation. They are not calculated from the Poisson λ values shown alongside them. At λ=1.1 events/user/day, most users receive at most one email-triggering event per day, so a 1.2× reduction is plausible. At λ=4.3, a 2.5× reduction implies specific assumptions about batching window size and inter-arrival distribution that are never stated. The numbers are load-bearing for worker sizing decisions.

### 7. The Dequeue Loop Is Cut Off

The proposal ends mid-sentence during the most operationally critical component — the dequeue loop that enforces priority. The behavior under P3 starvation, the polling interval, blocking vs. non-blocking dequeue (`ZPOPMIN` vs. `BZPOPMIN`), and how the loop handles an empty high-priority queue before checking lower priorities are all unspecified. This is not a minor omission; it is where the priority SLA guarantees are actually implemented or violated.

### 8. Token Invalidation Event Flow Has No Backpressure

The `token.invalidated` events are published to a Redis Stream consumed by E3's feedback processor. At scale, APNs 410 responses can arrive in bursts — during provider outages that resolve, for example. There is no stated stream length cap (`MAXLEN`), no consumer group lag alerting, and no description of what happens if the feedback processor falls behind. Unbounded stream growth is a memory exhaustion path on the same Redis instance holding the queues.

### 9. SMS P0 Dedicated Worker Doesn't Solve the Stated Problem

The justification for SMS P0's dedicated worker is that "the general dequeue loop's polling latency is unacceptable." But at negligible SMS volume (1,500/day, ~0.017/sec), the queue will be empty nearly all the time. The latency problem for SMS P0 is not polling interval — it's end-to-end latency from event ingestion through the router, preference check, suppression check, and aggregation window check before the event reaches any worker. The dedicated worker only addresses the last hop.

### 10. No Stated Connection Pool Sizing

The claim protocol requires a PostgreSQL write per notification at 500/sec peak, plus recovery queries, plus delivery log inserts, plus preference cache misses hitting the DB. Workers are described as a pool but pool sizes are not specified anywhere. PostgreSQL connection limits are finite; under the described load with unspecified worker counts, connection exhaustion is a realistic failure mode with no mitigation described.

### 11. The Suppression Cache Has No Stated Invalidation Path for Preference Changes

Preferences are cached in Redis with TTL=5min, write-through. The suppression cache is a Redis Hash with no TTL mentioned. If a user re-enables a channel after being suppressed, there is no described mechanism to remove them from the suppression Hash. The write-through policy covers preference updates but the suppression records are managed by the feedback processor, which is a separate write path with no described coordination with the preference cache.