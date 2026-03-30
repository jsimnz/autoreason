## Real Problems with This Proposal

### 1. The "Silent, Unrecoverable Loss" Claim Is Wrong

The document justifies full payload storage by arguing that storing only IDs creates an "unrecoverable" crash window. This is false. Standard practice is to use a dead-letter queue or visibility timeout (as in SQS): the message is not acknowledged until processing completes. If the payload fetch fails, the message returns to the queue. The document presents a solved problem as unsolvable to justify a more expensive architectural choice, without acknowledging that the alternative exists.

### 2. Peak Accumulation Math Is Internally Inconsistent

Section 1.3 states workers process ~26,000/sec but input is ~1,575/sec, then claims 7.6M entries accumulate during the 2-hour spike. If worker capacity exceeds input rate by 16×, the queue cannot accumulate 7.6M entries — it drains continuously. The document never explains what causes accumulation when drain rate vastly exceeds input rate. The memory sizing exercise is built on a number that contradicts the capacity figures stated two paragraphs earlier.

### 3. P1 Workers Draining P2/P3 Queues Is Unexplained

The justification for zero P2/P3 FCM/APNs workers is that "P1 push workers drain P2/P3 queues via priority-aware consumers during off-peak." This is asserted without any mechanism specified. How does a P1 worker know to consume from a lower-priority queue? What prevents P2/P3 starvation during sustained P1 load? This is a real architectural question with real failure modes, not a detail.

### 4. The OTP Fallback Logic Has a Budget Control Gap

The router code explicitly enqueues to P0_SMS_QUEUE when the user has no verified email, with only a log statement for budget review. This means a user without a verified email bypasses the SMS budget cap entirely on the security-critical path. The "two independent budgets with enforced controls" claim in the executive summary is not true for this population.

### 5. APNs Conservative Floor Is Undefended

The document states 300 req/sec/worker as the conservative floor for APNs planning, citing "production reports." No source is given. The range cited (300–2,000) is wide enough that the floor could be wrong by an order of magnitude. If actual throughput is 100 req/sec/worker — which is plausible for a new bundle ID with no established relationship with Apple — the 4-worker APNs pool handles only 400/sec against a 547/sec peak demand, meaning the system ships with a known capacity deficit on the iOS push path.

### 6. The Expiry Sorted Set Pruning Process Is Unspecified

Section headers reference a "background pruning process" for expiry sorted sets, and the executive summary mentions it. The document never specifies who runs it, how frequently, what happens if it falls behind, or how it interacts with worker failures. The executive summary calls out that expiry sets "grow without bound under worker outage" as a known problem, then defers the solution entirely.

### 7. Redis Single-Node Description Is Contradictory

The document describes ElastiCache r7g.4xlarge as "a single-node logical view with Multi-AZ replication — not a cluster." ElastiCache Multi-AZ replication for a single node is a primary/replica setup. Failover involves a replica promotion with a brief unavailability window. For P0 queues (OTP, security alerts), this unavailability window is not acknowledged or bounded. The document explicitly states "no single point of failure on the security-critical path" for workers but accepts a potential single point of failure in the queue store itself.

### 8. WebSocket Sequence Numbers Are Claimed but Not Shown

The executive summary states "WebSocket sequence numbers are designed, not deferred — reconnect catch-up logic is specified in Section 5." Section 5 does not exist in this document. This is either a reference to content that was cut or a false claim in the executive summary.

### 9. The Deduplication Key Count Is Inconsistently Applied

The document calculates ~156K simultaneous deduplication keys and calls the memory "immaterial." But the same 5-minute TTL window means that any retry storm or worker backup that causes messages to be re-enqueued within the TTL window will suppress legitimate redelivery. The document treats deduplication as purely a memory question and never addresses the false-positive suppression risk under the exact failure conditions (worker outage, queue backup) that the TTL is meant to handle.

### 10. Channel Split Percentages Are Asserted Without Basis

The 70/20/8/2 channel split is presented as a planning input with no derivation. For a system being designed before launch, this split determines worker counts, Redis memory, and budget allocations. If the actual split is 85% push (common for consumer social apps), the in-app and email worker counts are wrong and the push capacity utilization figures understate demand. The document applies rigorous sensitivity analysis to DAU/MAU but treats the channel split as a known quantity.

### 11. The "Honest Assessment" Understates the Staffing Risk

The document acknowledges utilization figures are low but attributes this to redundancy requirements and APNs uncertainty. A more direct problem: 21 workers across 5 channels and 4 priorities, managed by 4 engineers who are also building the application, represents significant operational surface area. The document does not address who is on-call for the notification system, what the escalation path is for the APNs re-planning gate, or how the team handles the month-2 load test milestone alongside other development work.