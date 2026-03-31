## Real Problems with This Proposal

### 1. The Recovery Job Has a Race Condition That Causes Duplicate Delivery

The recovery mechanism relies on querying PostgreSQL for events in state `enqueued` with no delivery log entry, then re-enqueuing them. But the delivery worker writes the delivery log entry *after* processing, not before. During the window between a worker dequeuing a notification and writing the delivery log, the recovery job can find that event, classify it as undelivered, and re-enqueue it. The proposal calls this "idempotent" but it is not — the original worker is still processing and will deliver it; the re-enqueued copy will deliver it again. This race is not addressed anywhere.

### 2. The Suppression Check Has a TOCTOU Race Despite Claiming to Fix It

The proposal explicitly rejects per-worker caches because "two different workers... both check their local cache, find nothing, and both send." It then replaces this with a shared Redis Hash. But the same race exists: two workers processing notifications for the same invalid token both call `HSET` only *after* sending. Between the check (`HGET`) and the send, neither has written to the shared hash yet. The shared hash narrows nothing relative to the per-worker cache for concurrent workers processing the same token simultaneously. The proposal claims this fixes the problem it identified; it does not.

### 3. The WebSocket "Connecting" State Deferred Check Is Untracked

Case B re-enqueues a deferred check after 5 seconds using unspecified infrastructure. There is no description of what executes this deferred check — no queue, no scheduler, no cron. If the component handling the deferred check crashes between the 5-second and 10-second window, the notification is silently lost. It never reaches the PostgreSQL inbox (that write is deferred) and never reaches the stream. This is a real data loss path with no named recovery mechanism.

### 4. The Email Batching Reduction Factor Is Invented

The proposal states "estimated average batching reduction: 2.5×" with no derivation. This single number determines whether email volume is 520K/day or 1.3M/day — a 2.5× difference in worker load, SES throughput requirements, and IP warming trajectory. The 2.5× figure is presented as an estimate but there is no basis given: no assumption about user posting frequency, no distribution of likes-per-post, no analysis of how many distinct users send likes to the same recipient within a 15-minute window. If the actual batching ratio is 1.5×, the email channel is substantially under-provisioned.

### 5. Worker Pool Sizing Ignores Retry Load

The worker math (e.g., 17 push workers needed, provision 30) accounts for peak volume but not retry volume. At 9.4M push/day, even a 1% transient failure rate generates 94,000 retries/day — roughly 3 additional retries/second at baseline, spiking higher during APNs degradation events. During an APNs degradation event, retries and new work compete in the same queue with the same workers. The proposal acknowledges APNs degradation as a failure mode but does not account for the retry amplification effect on worker capacity during that exact scenario.

### 6. The APNs JWT Token Approach Has a Shared Key Write Contention Problem

A single background job writes the JWT to a shared Redis key every 45 minutes. Workers read from local in-process cache with a 30-second TTL. This means up to 30 seconds after the background job writes a new token, some workers are still using the old token. APNs tokens are valid for 60 minutes, so 45-minute regeneration with 30-second worker lag is fine in normal operation. But if the background job fails silently — no alert is described for this failure — workers continue using an expired token. There is no described monitoring or alerting for JWT generation failures, and no fallback if the background job misses its window.

### 7. The Proposal Does Not Describe How the PostgreSQL Event Log Is Partitioned

The event log receives all events before Redis enqueue — up to 14.4M writes/day, plus delivery log writes, plus recovery reads. At 6 months, this table will have hundreds of millions of rows. The proposal mentions the in-app store is "partitioned" but says nothing about partitioning strategy, retention policy, or archival for the event log or delivery log. PostgreSQL query performance for the recovery job ("events in state enqueued with no delivery log entry") degrades significantly without the right indexes and partition pruning, and the recovery job runs at exactly the worst time — after a crash, when load is high.

### 8. The "No Cross-Channel Priority" Admission Is Understated

The proposal accepts that "a P0 email cannot preempt a P1 push in the push worker pool" and calls this acceptable because P0 events go to SMS or email. But the SMS worker pool is provisioned at 3 workers for negligible volume. If a P0 security event triggers SMS delivery and the SMS workers are processing the rare P1 SMS notifications, there is no preemption mechanism. The same logic the proposal uses to dismiss cross-channel priority for push applies here — except SMS is explicitly called out as the channel for P0 events. The proposal contradicts itself.

### 9. The "Connecting" State Can Persist Indefinitely If the Client Abandons the Handshake

The registry TTL is 90 seconds, refreshed by heartbeat. But the state transition from `connecting` to `connected` happens only on successful handshake completion, and the state is deleted only on clean disconnect or TTL expiry. If a client initiates a handshake and then drops (network failure before completion), the entry stays in `connecting` state for up to 90 seconds. Any notifications arriving during this window hit Case B, triggering deferred checks that themselves have the untracked execution problem noted above. This is not an edge case — mobile clients on flaky connections do this constantly.

### 10. IP Warming Is Mentioned as a Risk But Has No Quantitative Impact on the Plan

The proposal flags email IP warming as involving external parties and references §6 for contingencies. IP warming for 520K emails/day takes 4–6 weeks minimum, starting at hundreds of emails/day and ramping. During warming, the email channel cannot handle its designed load. The proposal does not describe what happens to email notifications that cannot be sent during warming — whether they queue, are dropped, or fall back to another channel. For a system where email is 9% of volume, this is a multi-week period where a significant channel is operationally unavailable, and the architecture has no described degraded-mode behavior for it.