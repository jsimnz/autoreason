## Real Problems with This Proposal

### 1. The "Race Condition Fixed" Section Is Incomplete

Section 3.1 ends mid-sentence: "JWT rotation failure means all APNs delivery stops — this is a single point of failure requiring explicit" — then nothing. The document claims in its preamble to have fixed a recursive race condition in APNs JWT rotation, but the actual fix is never shown. This is the most critical gap: the document explicitly promises a solution to a named problem and then doesn't deliver it.

### 2. The Compliance Mitigation Is Legally Unsound

The proposal states that a "reasonable technical delay" of up to 5 minutes (potentially longer during backlogs) is acceptable and will be documented in the privacy policy. This is not how GDPR works. Under Article 7(3), withdrawal of consent must be "as easy as" giving it, and processing must stop — there is no "reasonable technical delay" carve-out for systems capable of checking preferences in real time. Calling it a documented risk doesn't make it compliant. The proposal also says users who complain get "immediate suppression and a manual review," which implies the system can suppress immediately when motivated — undermining the stated justification for the delay.

### 3. PostgreSQL Overflow Table Is Underdefined

The fallback for Redis unavailability is a "PostgreSQL overflow table" that workers drain on recovery. The proposal never specifies: schema, indexing, drain ordering (does it preserve priority?), drain rate relative to normal queue throughput, or what happens if PostgreSQL is also degraded. Given that PostgreSQL is simultaneously handling in-app notification storage, delivery logs, and now queue overflow, the interaction between these workloads under a Redis failure scenario is entirely unexamined.

### 4. Write Amplification Problem Is Claimed Fixed but Never Addressed

The preamble lists "unexamined PostgreSQL write amplification" as a gap that was fixed. The document never actually addresses PostgreSQL write amplification anywhere. The delivery log writes, in-app storage, overflow table, and preference storage are all described independently with no analysis of combined write load, WAL pressure, or partitioning strategy for the delivery log table at 51M rows/day.

### 5. S3 Archival Policy Is Still Undefined

The preamble claims an "undefined S3 archival policy" was fixed. The phrase "PostgreSQL write replica + S3 archive" appears in the architecture diagram, but there is no policy anywhere in the document — no retention period, no archival trigger, no data format, no cost estimate. Claiming a gap was fixed and then not fixing it is worse than leaving the original gap open.

### 6. The Bus Factor Mitigation Doesn't Actually Reduce Bus Factor

The cross-training schedule requires each engineer to complete "at least one production deployment in staging" before a channel goes live. A single staging deployment does not constitute meaningful coverage ability. If E4 is hit by a bus, E2's cross-training on push consists of watching E4 work during months 1–2. The document identifies bus factor as "the primary organizational risk" and then addresses it with a checkbox that doesn't survive scrutiny.

### 7. 4× Load Test Target Is Internally Inconsistent

The proposal states the system is designed for 3× peak throughput, then says "2× is below design target and not a useful test," then sets the load test target at 4×. But if the system is designed for 3×, testing at 4× is testing beyond the design envelope — which is fine, but the document frames this as routine validation rather than stress-beyond-design. More importantly, the FCM throughput analysis shows almost no headroom at 3× peak during FCM degradation. A 4× load test would require either FCM cooperation or a mock — neither is discussed.

### 8. The 0.5% Opt-Out Threshold Has No Statistical Basis

The proposal treats a week-over-week opt-out rate increase above 0.5% as a P1 incident. With 7M push-eligible users, 0.5% is 35,000 users. There is no discussion of baseline opt-out rate variance, seasonal effects, or whether this threshold would produce constant false positives or miss real problems. A threshold without a baseline is not a meaningful SLA.

### 9. Re-engagement Campaigns in Month 5 Contradict the SMS Constraint

The proposal introduces "re-engagement campaigns" in month 5 with no channel specification. Re-engagement is a common SMS use case. The document establishes hard gates for SMS restricted to auth and security, but then schedules a campaign feature without clarifying it will never touch SMS — or if it will, how that interacts with the stated restriction and the cost analysis that made SMS restriction necessary.

### 10. The In-App Bypass Creates an Unacknowledged Consistency Problem

In-app notifications bypass the queue and write directly to PostgreSQL. Push notifications for the same event go through the queue. The proposal never addresses what happens when a user receives a push notification, taps it, and the corresponding in-app notification hasn't been written yet — or was written but the WebSocket pub/sub was degraded. The two code paths are described as having "genuinely different operational profiles" but the user-visible consistency requirement between them is never examined.

### 11. Preference Cache Invalidation Is Asserted, Not Designed

The proposal states preferences are cached with "write-through invalidation on any preference update" but never specifies the mechanism. Write-through from where? If the preference API updates PostgreSQL, something must invalidate the Redis key. Whether that's synchronous in the API request, via a database trigger, or via a change-data-capture pipeline has significant reliability implications — especially given that Redis unavailability is already identified as the primary infrastructure risk. This is load-bearing architecture described in one clause.