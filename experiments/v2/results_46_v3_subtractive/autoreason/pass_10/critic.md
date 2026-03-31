## Real Problems with This Proposal

### 1. The Recovery Job Is Underspecified Where It Matters Most

The proposal repeatedly defers to "the recovery job" as the designed closure for the crash window between `zpopmin` and claim, but never specifies the recovery job's own failure modes. What happens if the recovery job crashes mid-run? What is the recovery job's scheduling mechanism and what happens if it falls behind during sustained high load? The staleness threshold is mentioned but never defined. "Targeted below 0.01%" is not a design — it is an aspiration with no mechanism attached.

### 2. The Routing Table Is a New Single Point of Failure That Isn't Acknowledged

The proposal presents the `event_partition_routing` table as a correctness improvement, which it is. But it creates a new failure mode that is not analyzed: if the ingestion API writes to `notification_events` but the routing table write fails (or the transaction is rolled back), the event is unroutable. The claim function returns `None` with a logged error and the event is silently undeliverable. This is not a crash-recovery scenario — it is a data integrity failure with no recovery path described.

### 3. The Preference Cache Invalidation Race Is Not Addressed

Preferences are cached in Redis with a 5-minute TTL. A user who disables push notifications can still receive push notifications for up to 5 minutes. For opt-out of SMS (TCPA), the proposal says suppression checks are always enforced, but the suppression cache is populated by the feedback processor consuming a Redis Stream. The latency between a user disabling SMS and the suppression cache reflecting that is not characterized. If it goes through the same preference cache, the TCPA compliance claim is not substantiated.

### 4. The Fanout Multiplier Is Inconsistently Applied

The proposal derives 18M recipient-notification events per day using a 1.2 fanout, then applies opt-out rates to get routed events. But the channel distribution percentages (65% push, 25% in-app, etc.) are applied to routed events as if users have exactly one channel each. A user with both push and email enabled generates events on both channels. The math treats channel distribution as mutually exclusive when it is not, which means the routed event totals are likely undercounts and the worker sizing derived from them is suspect.

### 5. The Idempotency Key Design Defeats Its Own Purpose for the Main Failure Mode

The proposal correctly notes that idempotency keys deduplicate network-level retries within a single attempt. But the primary failure mode requiring deduplication — worker crashes after delivery, before state update — results in a new `attempt_number` and therefore a new idempotency key on recovery. This means the provider-side deduplication provides zero protection against the crash-recovery duplicate delivery scenario. The proposal acknowledges this but presents it as intentional design. The consequence is that the 0.01% duplicate target has no provider-side enforcement mechanism; it relies entirely on the staleness threshold bounding re-enqueues, which is itself underspecified (see problem 1).

### 6. P0 SMS Fast-Path Bypasses Aggregation But Suppression Cache Latency Still Applies

The proposal emphasizes that suppression checks are retained for P0 SMS. But if the suppression cache has not yet been updated (e.g., a user just opted out, the feedback processor hasn't written to cache yet), the suppression check passes on stale data. The fast path makes this worse, not better, because it reduces the time available for cache propagation. This is specifically a compliance risk for TCPA, not just a product quality issue.

### 7. The WebSocket Delivery Path Is Not Designed

In-app delivery to online clients is routed through Redis Streams to WebSocket servers, but this path receives almost no design attention. There is no specification of consumer group configuration, what happens when a WebSocket server crashes with unacknowledged stream entries, how the "client sync on reconnect" interacts with the in-app PostgreSQL store, or how the system determines a client is online versus offline at routing time. For 3.6M events/day (25% of total volume), this is a significant gap.

### 8. The Team Allocation Creates an Unacknowledged Coordination Bottleneck

E1 owns the recovery job threshold calibration per the cross-cutting column, but E4 also owns "recovery job (threshold calibration, runbook)." This is a direct ownership conflict on a critical component. More broadly, the feedback processor (E3) depends on the token invalidity stream (E2), which depends on the Redis Stream consumer group configuration that appears to be owned by E4. A three-engineer dependency chain for a latency-sensitive compliance path is not flagged as a risk.

### 9. The Partition Pre-Creation Job Failure Is Not Analyzed

The proposal notes that indexes are created on child partitions at creation time and that E4 owns the partition pre-creation job. But if this job fails to run, inserts to `notification_events` will fail when the next day's partition doesn't exist. At 14.4M events/day, this is a total outage scenario. There is no fallback, no alerting threshold, and no description of how far ahead partitions are created beyond "7 days ahead" — which means the failure window for the job is 7 days but the consequence of a silent failure is not discussed.

### 10. S3 Archival Consistency Is Not Addressed

Partitions older than 30 days are archived to S3 and dropped. If the archival job fails silently after dropping the partition but before completing the S3 write, that data is gone. If it fails after the S3 write but before dropping the partition, the next run may attempt to archive again. Neither case is addressed. For a delivery log that is described as the authoritative recovery source, silent data loss in archival is a serious problem.

### 11. The Batching Window Is Described as Both Derived and Configurable

The proposal derives the reduction factor mathematically from a 30-minute window, presents a table of results, and then says "the batching window is a configurable product parameter, not a derived one." This is a contradiction. If it is configurable, the worker sizing and queue depth monitoring thresholds derived from the 30-minute assumption are wrong whenever product changes the parameter. There is no described mechanism for keeping these in sync.