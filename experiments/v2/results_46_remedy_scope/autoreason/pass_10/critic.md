## Real Problems with This Proposal

### 1. The Visibility Timeout Implementation Is Broken Under Concurrent Workers

The recovery process uses `LREM` to remove a specific ID from the processing list, then `RPUSH` to re-enqueue it. But with multiple workers consuming from the same channel, the processing list for a channel is shared. `LREM` removes the first matching occurrence, which is correct in isolation, but the recovery process iterates a batch of stale IDs in a non-atomic loop. Two recovery process instances running concurrently (e.g., during a rolling restart or if the 30-second interval overlaps) can double-reclaim the same message — `LREM` succeeds for both, `RPUSH` executes twice, and the message is now enqueued twice. The document acknowledges duplicate delivery but attributes it only to the slow-worker race, not to the recovery process itself being a source of duplication.

### 2. The Dedup Key Design Doesn't Actually Protect Against the Described Duplicate

The slow-worker race condition produces a duplicate because the original worker completes after the message was reclaimed and re-enqueued. The document says the dedup layer handles this. But the dedup key is set at delivery time, not at enqueue time. If the re-enqueued message is picked up and delivered by a second worker before the original worker finishes, the second worker sets the dedup key, then the original worker checks it and finds it already set — but the original worker's check happens after it has already fetched the payload and may have already made the external API call. The dedup key prevents the acknowledgment, not the delivery attempt.

### 3. The LREM Operation Is O(N) on the Processing List

`LREM queue:<priority>:<channel>` scans the entire list linearly. The document discusses queue depths of potentially hundreds of thousands during outages. During a PostgreSQL outage where 1,380 messages accumulate in the processing list, the recovery process calling `LREM` for each of those entries becomes O(N²) in aggregate. This is not acknowledged. Under exactly the conditions where recovery matters most — a sustained outage — the recovery process becomes the bottleneck.

### 4. The Pruning Process Has an Unacknowledged Race Against Dequeue

The TTL pruning loop does `LREM` on the queue list followed by `ZREM` on the expiry set. A worker can dequeue a message (via `RPOPLPUSH`) between the `LREM` and `ZREM` calls. The message is now in the processing list, the worker fetches it, sees it's expired, discards it — fine. But the `ZREM` then fails silently because the message ID is gone from the queue but the expiry record still gets cleaned up correctly. This path is actually okay. The reverse race is not: the pruning process checks the expiry set, finds an expired ID, but before it calls `LREM`, a worker dequeues the message and begins processing it. The pruning `LREM` then removes the ID from the processing list (not the queue list — it's already moved), and the recovery process later finds the message gone from the processing list but still in `processing_timestamps`, creating a phantom entry that accumulates until manual cleanup.

### 5. The APNs Throughput Range Is Presented as a Floor Defense but the Failure Case Is Cut Off

The document explicitly says "The failure case that must be named" and then the text ends mid-sentence. The APNs section is incomplete. This is the one case the executive summary specifically calls out as having "a real mitigation, not just a load test date," and that mitigation is missing from the document.

### 6. The 60-Second Reclaim Threshold Interacts Badly with the 5-Minute Dedup TTL in One Specific Path

The document correctly notes that if a P0 notification sits in queue longer than 5 minutes, the dedup key expires and a retry delivers normally. But the scenario where this matters — a provider outage — is also the scenario where the retry itself may be delayed past 5 minutes. When the outage clears, multiple re-enqueued copies of the same notification (from successive reclaim cycles across the outage duration) may all have valid dedup keys expired, and all attempt delivery. The document treats "dedup key expires, retry delivers normally" as the correct behavior but doesn't address that a 10-minute outage could produce 10 reclaim cycles for the same P0 message, all of which attempt delivery after recovery.

### 7. The Worker Acknowledgment Check Is Described but Not Implementable as Described

The document states: "The worker acknowledgment path checks whether the message is still in the processing list before marking delivery complete." Checking membership in a Redis List requires `LRANGE` and a linear scan — there is no O(1) membership test for Redis Lists. At scale, this check is either prohibitively expensive or requires maintaining a separate set mirroring the processing list, which is not mentioned and introduces its own consistency hazard.

### 8. The Heartbeat Alert Threshold Is Miscalibrated

The alert fires if a worker's heartbeat rate drops below 1/30sec for more than two consecutive intervals. The heartbeat runs every 10 seconds. Two consecutive missed intervals means the alert fires after 20 seconds of missed heartbeats. But the reclaim threshold is 60 seconds. The alert fires 40 seconds before any message is actually at risk. This generates alerts for transient network hiccups, momentary GC pauses, and deployment restarts — all of which resolve before the reclaim threshold. The alert threshold is not tied to the actual risk boundary.

### 9. The PostgreSQL Failure Delay Estimate Is Underspecified for the Claimed Scenario

The document states P0 delay during PostgreSQL failover is "approximately 60–120 seconds" based on reclaim threshold plus re-queue time. But the exponential backoff is 1s → 2s → 4s → max 30s. A worker hitting a failed PostgreSQL connection will burn through backoff cycles before the reclaim threshold expires. During those cycles, the worker holds the message in the processing list and retries — meaning the message is not re-enqueued at 60 seconds; it's re-enqueued at 60 seconds only if the worker itself fails to retry successfully. If the worker is alive and retrying, the message stays in the processing list for the full outage duration plus however long the worker's backoff cycle is at the time of recovery. The 60–120 second estimate assumes worker death, not worker retry loops.

### 10. The Channel Split Robustness Claim Is Not Supported

The document claims the worker matrix is robust to push share ranging from 60–85% without re-provisioning, and that in-app workers have excess capacity that can be redeployed if push exceeds 80%. But workers are described as per-channel, per-priority pools. "Redeploying" in-app workers to handle push is not a configuration change — it requires changing what queue those workers consume from and what external API they call. This is a code/deployment change, not an operational knob. The robustness claim implies operational flexibility that the architecture doesn't actually provide.