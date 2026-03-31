Here are the real problems with this proposal:

## Scale and Math Problems

**The 27.2M "corrected" total is wrong in a different way.** In-app is counted at 14.4M (100% of non-opted-out users), but those users are already included in the push (65%) and email (20%) counts. The total isn't 9.4M + 14.4M + 2.9M + 1,500 — that double-counts every in-app user who also has push or email enabled. The proposal congratulates itself for fixing the prior version's multi-channel error while making a different accounting error in the same section.

**The Poisson batching math is being applied to the wrong population.** The calculation uses 4.8 events/user/day across all 600K email-opted-in DAU, but DAU is already a daily active subset. The events-per-user rate should be derived from the full opted-in user base, not just the daily active slice, or the document needs to explain why it's appropriate to use DAU here. Using DAU understates the denominator and inflates the per-user rate.

**The 1.05× reduction factor conclusion is presented as validating the batching window, but it actually undermines the architectural choice.** A 5% volume reduction means the system is doing all the complexity of aggregation windows, sorted sets, and configurable batching parameters for essentially no throughput benefit. The document acknowledges this ("primary value is latency control, not volume reduction") but doesn't address whether the complexity is justified for latency control alone, especially when P0 bypasses the window entirely.

## Operational and Failure Mode Problems

**The catch-all partition "safety net" creates a silent correctness problem.** When the pre-creation job fails and traffic falls into the catch-all partition, the system continues operating normally from the application's perspective. Nothing forces remediation. The runbook for migrating rows from the catch-all into daily partitions is mentioned but not specified — at 14.4M+ events/day, even a few hours of catch-all traffic means millions of rows requiring migration, with unclear impact on query performance, archival jobs, and the recovery job's partition-scoped queries during the migration window.

**The recovery job's own failure modes are promised in the executive summary but the document is cut off before delivering them.** The section heading says "Fully Specified" and the executive summary lists this as a resolved weakness, but the actual specification is incomplete. This is the most prominent claim in the document and it isn't substantiated.

**The synchronous suppression cache write on opt-out is a hidden availability dependency.** If the suppression cache (Redis) is unavailable when a user opts out via the preference API, the document doesn't say what happens. Does the opt-out fail? Does it succeed with a degraded guarantee? The TCPA compliance mechanism depends entirely on this write succeeding, but Redis AOF with fsync=everysec means the cache itself can lose up to 1 second of state. An opt-out written to Redis but not yet fsynced, followed by a crash, followed by an SMS send in the recovery window, is a TCPA violation. The document treats the 30-second TTL cache as the compliance boundary but doesn't account for the cache's own durability gap.

**The 0.01% duplicate target is described as "an operational target, not a guarantee" but no measurement mechanism is specified.** If it's an operational target, there must be a way to know whether it's being met. The document doesn't describe how duplicates are detected or counted post-delivery, making the target unverifiable.

## Design Coherence Problems

**The WebSocket delivery path is listed as "designed" in the executive summary but doesn't appear in the visible portion of the document.** Section 2.2's data flow diagram references Redis Streams and consumer groups for WebSocket delivery, but the promised specification of consumer group configuration, crash handling, and online/offline determination is not present in the sections shown.

**The routing table transaction atomicity argument has a gap.** The document claims "the failure mode 'event written, routing entry missing' cannot occur" because both writes are in the same transaction. This is true for the happy path, but the document doesn't address what happens if the transaction succeeds at the database level but the application crashes before enqueuing the event_id to Redis. The event exists in PostgreSQL in state 'enqueued' but is not in the Redis sorted set. The recovery job is supposed to handle this, but the recovery job specification is cut off.

**The configuration-change recalculation job is described as producing "recommendations that require human review" but the trigger is described as automatic.** A configuration-change event automatically triggers a job that outputs recommendations. This means worker sizing can silently drift from recommendations if humans don't act on them, with no specified alert or enforcement mechanism. The document presents this as solving the invisible dependency problem, but it only makes the dependency visible — it doesn't prevent the system from running under the wrong sizing.

**Priority is enforced via sorted set score, but the document doesn't explain how different priorities coexist in the same sorted set.** If score is Unix timestamp in milliseconds, a P3 bulk notification sent now has a lower (earlier) score than a P0 critical notification sent one millisecond later, meaning the P3 is dequeued first. The document mentions "per-channel worker pools" but doesn't describe whether there are per-priority queues or a single queue with priority-aware dequeuing, making the priority enforcement mechanism unverifiable.

## Organizational Problems

**The ownership resolution for E3 creates a single point of failure on the TCPA compliance path.** E3 owns preference API, suppression cache writes, feedback processor, and the opt-out synchronous cache write. Every component in the compliance chain belongs to one engineer. The document resolves the three-engineer dependency chain concern but creates a bus-factor-one compliance risk.

**The "new event types require a pull request" policy is stated as a design decision but has no enforcement mechanism.** The router rejects unclassified events with a 422, which is correct, but the classification table itself is not described — where it lives, who can modify it, and whether the PR requirement is enforced by process or tooling. At 4 engineers, process-only enforcement is fragile.