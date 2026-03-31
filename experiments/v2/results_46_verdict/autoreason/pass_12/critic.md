## Real Problems

### 1. The "Separate Queues Prevent Borrowing" Argument Is Incomplete

The document claims separate queues make channel isolation a "structural property." But the shared priority classifier is still a single point of contention. Under FCM backpressure, messages pile up in the push queue. The classifier continues routing new messages into that backed-up queue. The isolation problem hasn't been eliminated—it's been moved upstream into classifier throughput and downstream into queue depth management. The document never analyzes classifier capacity under this scenario.

### 2. Peak Window Assumption Is Load-Bearing and Unvalidated

The 4-hour window / 60% concentration figure is explicitly called an assumption, but the entire ceiling calculation depends on it. The document says "we will validate in month 2"—but the infrastructure is being provisioned before month 2. If the actual concentration is 2 hours / 60%, the sustained peak doubles to ~4,250/sec and the burst ceiling jumps proportionally. The provisioning decisions made in months 1–2 are based on a number the team acknowledges they don't know yet.

### 3. The 3× Burst Multiplier Is Poorly Grounded

The document cites "published incident reports from comparable-scale systems" without naming them. A 10M MAU social app is not Twitter or Facebook. The claim that 3× covers viral spike scenarios at this scale is asserted, not demonstrated. More importantly, the multiplier and the traffic model uncertainty are treated as independent when they aren't—a higher-than-expected DAU/MAU ratio combined with a viral event produces compounded load, not additive.

### 4. Month 2 Traffic Review Is Structurally Underpowered

The review is described as producing deliverables, but there's no stated owner, no meeting format, no quorum requirement, and no consequence if the deliverables are incomplete beyond the document's own warning that an incomplete review "is not a review—it is a reassurance." That sentence is not an enforcement mechanism. With 4 engineers under delivery pressure, this review will slip or produce shallow output.

### 5. Bus Factor Mitigation Is Aspirational

The document acknowledges that "cross-training in the sense of watching someone else work does not constitute coverage ability" and claims the mitigation is "demonstrated capability." But no mechanism for demonstrating capability is defined. There are no coverage drills, no shadowing requirements with defined completion criteria, no runbook testing cadence. The coverage chain table lists partners but provides no evidence those partners can actually operate the systems they're listed as covering.

### 6. SMS Escalation Path Has a Critical Gap

The tiered escalation structure pages on-call engineering at $15,000 and leadership at $25,000. But the document also states these notifications are never automatically suppressed without human decision. If the on-call engineer is paged at 3am and doesn't respond within the escalation window, or approves continued spend without investigating, there is no backstop. The $47,250/month scenario can be reached without any of the escalation steps actually resolving the underlying cause.

### 7. P0 Classification Is a Circular Dependency

The taxonomy is described as a prerequisite for P0/P1/P2 classification, which is a prerequisite for SMS gate enforcement, which is a prerequisite for the channel dispatcher. But the SMS budget analysis in §1.1c already assumes specific P0 volume percentages (1%, 2%, 5%) before the taxonomy exists. The budget scenarios are built on a classification that hasn't been done yet. If the day-1 session determines that P0 is narrower or broader than assumed, the entire budget analysis needs to be rerun before infrastructure decisions are finalized.

### 8. The Auth/Security SMS Allowlist Has No Defined Initial Contents

The allowlist is described as a versioned configuration file requiring two-engineer PR review to modify, with an emergency path for urgent additions. But the document never states what is on the allowlist at launch. "Auth and security" is described in prose but never enumerated. This means the allowlist contents are implicitly determined by whoever writes the initial configuration, without the governance process the document prescribes for modifications.

### 9. WebSocket Connection Pool Scaling Is Underspecified

The sensitivity table mentions expanding the WebSocket connection pool at 40–50% DAU/MAU, but the document never establishes what the baseline connection pool size is, what server-side resource constraints govern it, or how connection state is managed when the pool expands. Horizontal scaling of WebSocket servers requires session affinity or shared state management—neither is addressed.

### 10. The Document Ends Mid-Sentence

Section 2.2 ends with "E1 serves as tertiary backup for all channels when both primary and coverage partner are simultaneously" and nothing follows. Whatever was being specified here—likely the most complex coverage scenario—is missing entirely.

### 11. Retry Exhaustion Definition Is Inconsistent With Stated Fallback Trigger

The SMS fallback gate specifies "3 attempts with exponential backoff over 90 seconds." But the document never establishes what constitutes retry exhaustion for auth/security notifications, which bypass the fallback gate entirely. If an APNs token is stale and the push fails, auth/security SMS is sent immediately without any retry logic—or it's sent after some undefined retry sequence. The bypass behavior is unspecified.

### 12. No Latency Requirements Anywhere

The document is entirely throughput-focused. There are no stated latency SLOs for any channel or notification priority. A P0 security alert that arrives 45 minutes late has been "delivered" by the throughput model but has failed its actual purpose. Without latency requirements, the queue depth and consumer scaling decisions have no correctness criterion beyond "don't fall over."