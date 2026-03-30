## Real Problems with This Proposal

### 1. The Document Is Incomplete
Section 3.1 cuts off mid-sentence: "Rotated manually, only when comprom—". Everything after APNs JWT token management is missing. The proposal covers Sections 1–3.1 partially. Sections 3.2 through 7+ (email, SMS delivery, cross-channel consistency, DLQ strategies, monitoring, test harness) are entirely absent. The executive summary, team allocation table, and scope claims reference content that doesn't exist in this document.

### 2. The Opt-In Rate Assumption Is Load-Bearing and Undefended
The entire scale model pivots on 60% push opt-in rate, stated once in the conservative scenario column with no justification. Industry push opt-in rates vary from 40–70% depending on platform, app category, and prompt timing. A 40% rate changes the conservative scenario materially. This figure is never revisited in the base or high scenarios — the table simply omits it for those columns with a dash, which means those rows are computed from an unstated assumption.

### 3. The P1 Sharding Scheme Has a Correctness Problem
The proposal claims ordering is preserved per recipient within each shard. But ordering in SQS FIFO is preserved per MessageGroupId *within a single queue*. When the proposal later says "Expand to 8 shards if Scaling Trigger A fires," it doesn't address what happens to in-flight messages in the 4-shard configuration. A recipient whose user ID hashed to shard 2 under modulo-4 will hash to a different shard under modulo-8. Messages already enqueued in the old shard and messages newly enqueued in the new shard will be processed by different workers with no ordering guarantee between them during the transition window. The proposal presents shard expansion as a configuration increment with no architectural consequence. That's wrong.

### 4. The Redis Idempotency Key Has a Race Condition the Proposal Doesn't Acknowledge
The code clears the idempotency key when max retries are exceeded so "DLQ processor can retry cleanly." But if a slow worker is still processing the original message when the DLQ processor retries, both will acquire the key (the original clears it, the DLQ processor sets it, the original's in-flight send completes anyway). The proposal acknowledges the Redis-unavailability duplicate risk but not this one, which is more likely in the failure scenarios the DLQ processor is specifically designed to handle.

### 5. The FIFO Deduplication Window Is Unaddressed
SQS FIFO native deduplication uses a 5-minute deduplication window. The proposal states FIFO queues "handle deduplication natively for P0 and P1" and uses this to argue the Redis idempotency dependency only applies to P2/P3. But if a P1 message is retried after the 5-minute window — which is entirely plausible given the visibility timeout and retry logic described — FIFO deduplication will not catch it. The proposal treats FIFO deduplication as a complete solution when it is only a partial one.

### 6. The Email Volume Is Suspiciously Flat
Email is capped at 4M/day across all three scenarios with the parenthetical "digest model caps this." But the digest model is never defined in the visible portions of the document. If email includes transactional notifications (account alerts, password resets) in addition to digests, the cap doesn't hold. If it's purely digest, the proposal needs to state what happens to transactional email volume, which scales with DAU and is not digest-bounded.

### 7. The Hour Allocation Has an Unacknowledged Dependency Problem
E2 owns push, email, and SMS — 600 hours of channel work. Cross-channel consistency is co-owned by E1 and E2 with 200 hours allocated. E2 is therefore accountable for 800 hours of the 3,072 total, which is 26% of all available engineering time for one person. The proposal treats the 20% overhead deduction as uniform, but E2's coordination surface (three channels plus cross-channel work with E1) is substantially higher than E3 or E4's. The allocation doesn't reflect this and provides no mitigation.

### 8. The OTP Fallback Authorization Framing Obscures a Security Decision Already Made
The proposal says the emergency email OTP fallback "must be authorized" by Security and that "engineering implements whatever is authorized." But the code is already written with email fallback as the default, and the rationale ("blocking authentication at scale during a security incident creates a second incident") is already argued. The decision has been made and documented. Framing it as a pending authorization is misleading about where the default actually sits.

### 9. Scaling Trigger B Is Described as Requiring an Architecture Review Without Allocating Time for It
Trigger B — sustained peak above 10,000/sec — calls for migrating P1 from FIFO to standard queues plus application-level ordering. This is described as a "structural change" requiring an architecture review. No time is allocated for this in the 6-month budget, no owner is named, and no estimate of the work is given. If this trigger fires in month 3, the team has no runway to execute it within the existing allocation.

### 10. The Test Harness Scope Is Stated as Fixed but Untethered from the Missing Sections
The proposal asserts the test harness is 200 hours covering six named failure classes. Four of the six failure classes — incorrect aggregation counts, timezone errors, broken unsubscribe links, and token invalidation races — depend on components (aggregation logic, digest scheduling, unsubscribe flow, token refresh) that are either in missing sections or not yet designed. Allocating fixed hours to test harness coverage for undesigned components is not a scope commitment; it's a placeholder that will be renegotiated when those sections are written.