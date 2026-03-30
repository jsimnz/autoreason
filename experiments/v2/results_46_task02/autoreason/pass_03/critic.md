## Real Problems with This Proposal

### 1. The "Outbox Eliminates Duplicates" Claim Is False

The proposal explicitly states the outbox "eliminates this class of failure entirely," but the poller code contains a comment acknowledging the opposite: if the `UPDATE` marking rows as relayed fails after Redis writes succeed, rows are reprocessed and duplicate enqueues occur. The proposal then defers this to "idempotency keys (see Section 3.3)" — but Section 3.3 is cut off. The central correctness claim is undermined by the implementation, and the actual deduplication mechanism is absent from the document.

### 2. The Throughput Math Is Internally Inconsistent

The proposal calculates per-instance sustained throughput as "~500 rows/cycle × ~15 cycles/second ≈ 7,500 rows/second," yielding a fleet capacity of ~30,000 rows/second and claims "17× headroom." But earlier it states peak load is 1,750/second and calls that "11× headroom." These numbers cannot both be correct for the same system. The fleet capacity figure appears to be fabricated — 500 rows per 30–50ms cycle is 10,000–16,000 rows/second per instance, not 7,500, and the arithmetic doesn't follow from the stated assumptions.

### 3. The Outbox Poller Has a Correctness Bug Under Transaction Semantics

The poller runs the `SELECT FOR UPDATE SKIP LOCKED` and the `UPDATE SET relayed_at` inside a single transaction, but the Redis pipeline `execute()` call happens between them — outside any ability to roll back if Redis fails. If Redis is unavailable, the transaction will fail to commit (or commit without the Redis writes having succeeded), and the error handling is not shown. The code structure implies Redis writes happen before the DB transaction commits, meaning a partial failure leaves the system in an ambiguous state that the prose claims the outbox prevents.

### 4. The In-App Notification Failure Mode Argument Is Circular

The proposal argues that writing in-app in the same transaction is correct because "if the outbox relay fails permanently, the user has an in-app notification but no push or email — that is the correct failure mode." This is asserted, not justified. For a user who has push enabled and in-app disabled (a valid preference combination), they would receive a notification they cannot see. More broadly, "the user is not completely dark" is a product decision being made silently in an infrastructure document, with no acknowledgment that product stakeholders should validate this behavior.

### 5. The Priority Queue Design Contradicts Its Own Justification

The proposal rejects per-channel queues because they create "priority inversions between channels," then implements per-priority queues (`notification_queue:p0`, `notification_queue:p1`, `notification_queue:p2`) with separate worker pools. The poller code references `queue_key = f"notification_queue:p{row.priority}"` — three separate sorted sets. This is structurally identical to the per-channel queue topology it rejected, just partitioned differently. The operational simplicity argument for a "single priority queue" doesn't apply to what was actually designed.

### 6. SMS Cost Analysis Is Disconnected from the Design

The proposal correctly identifies that international SMS could cost $20,000–$40,000/day, flags this as a serious concern, and says "hard spend caps defined in Section 3.4." Section 3.4 is not present in this document. The most financially dangerous channel has its controls entirely deferred to a missing section.

### 7. The Preference Cache Has an Unacknowledged Failure Mode

The proposal says the preference check is "TTL-bounded" and that routing is "coupled to cache health." The stated mitigation is "the TTL-bounded cache design in Section 3.5" — another missing section. Meanwhile, the failure behavior on cache miss is unspecified. If the cache is unavailable, does routing fail open (sending notifications users opted out of), fail closed (dropping notifications), or fall back to the database synchronously (blowing the latency budget)? This is a correctness and compliance question for a preference system.

### 8. The DAU-to-Notification-Rate Assumption Produces Implausible Numbers

17 notifications/user/day applied to 3M DAU yields 51M notifications — which the proposal rounds to 50M and treats as validated. But 17/day is described as the rate for "engaged" users, applied uniformly to all DAU. DAU by definition includes casual users. If the actual distribution is skewed (e.g., top 10% of users generate 60% of notifications), the peak multiplier of 3× significantly underestimates true burst load for the high-activity cohort. The model treats a per-engaged-user average as a per-DAU average without acknowledging this.

### 9. Cross-Training Is Structurally Unenforceable

The proposal states cross-training is "enforced through paired on-call shifts in month 3." But the timeline has the working system shipping in month 2, meaning engineers are on-call for a live production system before cross-training is complete. If E1 is unavailable during a queue infrastructure incident in month 2, the stated backup (E2) is not yet qualified. The enforcement mechanism arrives after the risk window it is meant to address.

### 10. The Dead-Letter Queue Has No Operational Definition

The architecture diagram references a "Dead-Letter Queue (Redis sorted set + operational runbook)" but the runbook is not present, and no criteria are given for what constitutes dead-lettering versus retry exhaustion versus permanent failure. `relay_attempts < 5` is the retry gate in the poller, but what happens at attempt 5 is not shown in the code or described in prose. For a system handling auth OTPs, silent discard at retry exhaustion is a security issue.