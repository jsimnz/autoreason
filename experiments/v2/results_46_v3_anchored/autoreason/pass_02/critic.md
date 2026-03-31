## Real Problems with This Proposal

### 1. The 17 Notifications/User/Day Figure Is Doing Too Much Work

The entire scale calculation depends on "industry avg for engaged social apps" with no citation or range. This single number drives queue sizing, worker counts, infrastructure costs, and team allocation. If the real number is 8 or 35, the architecture may be over- or under-provisioned significantly. The document acknowledges ratios are estimates but then builds hard infrastructure decisions on them without sensitivity analysis.

### 2. DAU × Rate Conflation

The document calculates 50M/day as DAU × 17, but notifications are sent to both active and inactive users (re-engagement emails, digests for users who haven't opened the app). Using DAU as the denominator undercounts total notification volume. The SMS correction section actually demonstrates this problem — it catches one instance but the underlying methodology is flawed for all channels.

### 3. In-App Queue Bypass Is Not Actually Justified

"They're cheap, don't need retry logic, and benefit from immediate consistency" — this is asserted, not argued. If PostgreSQL is slow or under write pressure during a spike, the write path blocks synchronously. The failure isolation argument made so forcefully for other channels is completely abandoned here. A PostgreSQL write failure during a spike drops the in-app notification with no retry path, which contradicts the reliability goals stated elsewhere.

### 4. Write-Through Cache Has a Race Condition

The preference invalidation code deletes the Redis key after the database write. Between the DB write completing and the Redis delete executing, another router process can read the old cached value and re-cache it with the old TTL. The new value then won't be seen for up to 60 seconds despite the "immediate invalidation" claim. The document presents this as solved.

### 5. APNs Token Manager Is Not Thread-Safe

The `APNsTokenManager` has a classic check-then-act race: two threads can simultaneously find `_token is None`, both generate a JWT, and one overwrites the other. More importantly, the `_token_generated_at` and `_token` fields are updated non-atomically. In a multi-threaded push worker, this produces intermittent authentication failures that will be extremely hard to diagnose at 2am.

### 6. Digest Double-Send on Crash Is Not Actually Prevented

The comment says "mark consumed BEFORE sending to prevent double-send on crash" and cites SendGrid idempotency key as the safety net. But no idempotency key is shown being generated or passed to SendGrid in the code. The `DigestEmail` object has no idempotency key field. This is the most critical correctness guarantee in the digest system and it's described but not implemented in the code shown.

### 7. Force-Send Logic Has an Inconsistency

`build_digest_force` is called inside a loop over individual events, meaning it could be called multiple times for the same user in the same digest run if multiple events have hit `MAX_CARRY_FORWARD_CYCLES`. The function is not defined anywhere in the document, so it's unclear whether it deduplicates. This is a real duplicate-email risk.

### 8. No Worker Count or Concurrency Numbers Anywhere

The document specifies FCM connection pool sizes and batch sizes but never states how many worker processes handle each queue. At peak ~1,750 notifications/sec with 70% push, you need to deliver ~1,225 push notifications/sec. Whether the proposed infrastructure actually achieves this is never demonstrated. For a 4-engineer team that will be on-call for this system, this is a significant gap.

### 9. Team Allocation Ignores Cross-Cutting Concerns

E1 owns queue infrastructure, E4 owns reliability and monitoring — but the boundary between these is not defined. Queue dead-letter handling, retry logic, and backpressure are simultaneously infrastructure (E1) and reliability (E4). In practice this will cause ownership ambiguity on the components most likely to fail in production.

### 10. No Dedicated QA Is Understated as a Risk

"Partially mitigated by phased delivery" is not a mitigation — phased delivery is a release strategy, not a quality assurance strategy. For a notification system, the failure modes that matter most (duplicate sends, preference violations, suppression list failures) are behavioral correctness issues that are hard to catch without dedicated testing. The 4-engineer team is already fully allocated; there is no slack to absorb quality work.

### 11. Hash Partitioning Archival Is Operationally Harder Than Claimed

The document correctly rejects range partitioning but then says archival is "handled by a background job that moves rows older than 90 days." With hash partitioning, this background job must do a full table scan with a `WHERE created_at < cutoff` predicate across all partitions, requiring an index on `created_at` in every partition. At 10M rows/day × 90 days = 900M rows, this archival job is a significant operational burden that is entirely hand-waved.

### 12. $205K/Year SMS Cost Presented as "Defensible" Without Approval Context

The document states the SMS cost is "significant, but defensible" without indicating whether this has executive approval or fits within an actual budget. For a 4-engineer team at a company where this document presumably needs sign-off, presenting a $205K/year line item as self-evidently acceptable is a real process problem, not just a documentation gap.

### 13. Month 6 "Hardening" Has No Defined Scope

The timeline mentions "harden in month 6 against defined entry and exit criteria" but those criteria are never stated in the document. This is specifically called out as a deliverable with criteria, then not delivered.