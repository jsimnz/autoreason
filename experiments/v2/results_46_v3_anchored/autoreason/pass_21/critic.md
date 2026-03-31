## Real Problems with This Proposal

### 1. The Sign-Off Table Is Structurally Broken

The sign-off table lists "E1 provides volume model input" as the engineer role for SMS budget decisions, but E1 is also responsible for opt-out compliance architecture, SendGrid technical requirements, broadcast rate limiting implementation, and upstream API behavior definition. No workload analysis is provided for E1 specifically, despite the document acknowledging the overall budget is not comfortable. The table creates the appearance of accountability structure without actually distributing load.

### 2. Tier 1 Queue Has No Bound But No Analysis of What Happens When It Grows

The document explicitly states Tier 1 has no bound and producers are blocked. During a Type 4 spike at 12,030/sec, if Tier 1 represents even 5% of traffic, that is ~600/sec of OTP and safety messages arriving while workers are saturated. The document does not analyze how long the block persists, what the producer timeout behavior is, or whether blocking Tier 1 producers cascades into application server thread exhaustion. "Never drop; block producers" is a policy statement, not a design. The downstream consequences of blocking are unexamined.

### 3. The Degradation Math Is Internally Inconsistent

Default A activates at 2,650–3,800/sec. Default B activates above 3,800/sec sustained for 5 minutes. But the Type 1 spike calculation shows 5,414/sec — well above the Default B threshold — for the *most common* spike type. This means Default B, described as appropriate for Type 2 events, fires routinely during ordinary viral content. The document treats Default B as an exceptional response but the math shows it is a normal operating condition for any meaningful viral event.

### 4. The 60-Second Worker Sleep Creates a Thundering Herd

When Default B clears, all Tier 3 workers resume on their next loop cycle "within 60 seconds of recovery." If there are dozens of workers, they all resume approximately simultaneously after the same 60-second sleep cycle. The suppressed Tier 3 queue has been accumulating during the spike. All workers wake, find a large queue, and begin processing simultaneously. This is a textbook thundering herd scenario against Redis. The document does not acknowledge this.

### 5. The Metrics Process Failure Mode Is Backwards

The document states that if the detection process fails, workers default to normal operation, justified as preferring false negatives over false positives. But the failure mode being protected against is a spike occurring *while* the detection process is down — which means Tier 3 workers continue consuming at full rate during a spike that would otherwise trigger Default B, potentially starving Tier 1 and Tier 2 processing. The justification inverts the actual risk: an undetected spike is worse than an unnecessary suspension.

### 6. Queue Bound Arithmetic Is Wrong

The document calculates Tier 2 queue memory as "2M × ~200 bytes ≈ 400MB in Redis." This ignores Redis overhead per key/list entry, which for a list with 2M entries adds pointer overhead, encoding overhead, and the list structure itself. Redis list entries at this scale carry meaningful overhead beyond raw payload size. The 400MB figure understates actual memory consumption and is used to justify the bound as "manageable" without real capacity analysis.

### 7. The Compliance Architecture Risk Is Understated in the Wrong Direction

The document frames the compliance risk as "1–2 engineer-weeks of rework during the highest-velocity period." But it also states the synchronous and cached architectures "have different data access patterns across all four channel dispatch paths." If the dispatch paths are built with synchronous opt-out checks embedded in the query logic, switching to cached architecture is not a refactor — it changes the correctness model. A synchronous check guarantees opt-out state at dispatch time. A cached check does not. These are not equivalent architectures with different performance characteristics; they have different correctness guarantees, and the legal review needs to evaluate correctness, not latency.

### 8. "Drop Oldest" Policy for Tier 2 Is Not Analyzed for Regulatory Risk

Direct messages are Tier 2. The document proposes dropping the oldest Tier 2 messages when the queue hits 2M. Dropping a direct message notification is not equivalent to dropping a like notification. Depending on jurisdiction and app category, undelivered message notifications may have user expectation or even regulatory implications. The document does not acknowledge this distinction — it groups DMs with mentions and applies the same drop policy.

### 9. The Per-DAU Rate Has No Sensitivity Analysis Despite Acknowledged Uncertainty

The document provides detailed sensitivity analysis for concentration assumptions but none for the 11/DAU/day figure itself. The raw event range is 7.5–23/DAU/day before batching — a 3× spread. The document acknowledges the 11 figure is a midpoint estimate, not derived, but then uses it as the sole input to all downstream calculations. A sensitivity table showing what 8/DAU and 16/DAU produce in peak rates would be the same type of analysis already applied to concentration — its absence is inconsistent with the document's own methodology.

### 10. The International User Base Problem Is Acknowledged Then Ignored

The document notes that the 90%/4-hour concentration assumption breaks down with substantial international users, then proceeds to use it as the planning basis anyway. The "correct response" listed is to instrument peak window detection post-launch. But the worker ceiling, queue bounds, Redis memory sizing, and Default B thresholds are all calculated from the 90%/4-hour assumption. If the actual concentration is flatter due to international users, the peak rate is lower — but the system is sized for a spike profile that may not occur while being potentially undersized for sustained moderate load across time zones. The document does not analyze the sustained moderate load case at all.

### 11. HTTP 429 Backpressure Requires Retry Logic From All Producers But This Is Underdefined

The document states producers must implement retry logic and calls this "a contract between the notification service and its callers, documented before Month 2 implementation begins." But the proposal does not specify who owns those producers, how many there are, or whether they are internal services or third-party integrations. If any producer does not implement retry correctly, the 429 response results in dropped notifications with no queue entry — invisible data loss. The contract is mentioned but not enforced by the design.