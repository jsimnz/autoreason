## Real Problems with This Proposal

### 1. The Bloom Filter Logic Is Backwards

The document claims a bloom filter negative result means "user not deleted" and proceeds without a database lookup, while a positive triggers a database lookup. Bloom filters guarantee no false negatives — if something is in the set, it will be found. But a newly deleted user may not yet be in the bloom filter if the filter hasn't been updated. The design's stated goal is to catch deleted users fast; the bloom filter only reliably catches users who were deleted *before* the filter was last rebuilt. The document never addresses how or when the bloom filter is updated, its false positive rate, or its size. This is the core mechanism for protecting deleted users from receiving notifications, and it's underspecified in a way that obscures a real correctness gap.

### 2. Concurrent Multi-Channel Tier 1 Delivery Creates Unquantified Cost Exposure

The document acknowledges that Tier 1 sends push, SMS, and email concurrently — not sequentially — and notes this creates cost exposure if Tier 1 volume spikes. It promises controls are described in §1.6, but §1.6 is never included in this document. The SMS cost justification depends entirely on Tier 1 volume staying under 0.1% of DAU, but no mechanism is described that actually enforces or monitors this. The promise to describe it later is not a control.

### 3. The Snapshot-Based Digest Has a Silent Correctness Problem

The idempotency key is `(user_id, snapshot_timestamp)`. If the job is restarted with a *different* snapshot timestamp — due to an operator mistake, a code deployment, or a scheduler misconfiguration — the key changes and every user processed in both runs gets a duplicate digest. The document assumes restarts always reuse the original timestamp, but never describes how that timestamp is persisted and recovered. If it lives only in memory or in an ephemeral job context, a crash-and-restart cycle loses it.

### 4. The Quiet Hours Jitter Is Presented as a Solution When It's Only a Mitigation

The document says jitter "reduces the peak by roughly an order of magnitude." This figure is asserted without derivation. If 30% of users set quiet hours ending at 08:00 — a plausible concentration for a social app — a 0–15 minute jitter spreads those users across 15 minutes instead of 1, reducing instantaneous peak by roughly 15×, but the sustained load over that window is identical. Whether the spike batching mechanism triggers depends on queue depth, not instantaneous rate. The document doesn't model whether the sustained load during the jitter window still exceeds the 500,000-message queue depth threshold. It might routinely trigger the very batching it claims to prevent.

### 5. The Cache Invalidation Event Can Exceed the TTL It's Meant to Improve

The document explicitly acknowledges this: "During consumer lag, this window could exceed the 5-minute TTL it was intended to improve." This means the invalidation event mechanism provides no guarantee of improvement over simply waiting for TTL expiry. Under load — exactly when consumer lag is most likely — the mechanism is least effective. The document frames this as acceptable, but it means the invalidation event system adds architectural complexity (a FIFO queue dependency, consumer workers, eviction logic) that may provide zero benefit in the cases that matter most.

### 6. The Document Ends Mid-Sentence

The proposal cuts off in the middle of the unsubscribe handling paragraph: "so regulatory deadlines (CAN-SPAM: 10 business days" — and stops. CAN-SPAM compliance is a legal obligation, not an optional design consideration. The document cannot be treated as complete when the section covering regulatory requirements is literally unfinished.

### 7. The 200–250 Notifications/Second Peak Estimate Is Derived From Flawed Arithmetic

The document estimates ~1.3M notifications/day. Divided across 24 hours, the average rate is ~15/second. An 8–10× peak factor yields 120–150/second at peak hour, not 200–250. The document then adds "brief spikes to 400/second" without derivation. The stated peak throughput requirement of 200–250/second doesn't follow from the stated inputs. Infrastructure is sized against this number, so if it's wrong, the sizing is wrong.

### 8. FIFO Queue Semantics Are Assumed but Never Validated Against the Use Case

The document routes account events through a FIFO queue, which is appropriate for ordered processing. But FIFO queues in systems like SQS have per-message-group ordering, not global ordering. If multiple events for the same user (preference change, then account deletion) are in different message groups, ordering is not guaranteed. The document never specifies what the message group key is. If it's not user ID, the ordering guarantee that makes the deletion sequence safe doesn't exist.

### 9. The DAU/MAU Validation Dependency Is Unresolved at Design Time

The entire load model is built on a 20–30% DAU/MAU ratio that the document says must be validated within 30 days of launch. But infrastructure must be provisioned before launch. If actual DAU/MAU is 40% — not uncommon for a healthy social app — peak throughput roughly doubles, potentially exceeding the designed capacity before the validation window closes. The design has no stated behavior for this scenario.

### 10. Direct Message Queue Isolation Is Incomplete

DMs are excluded from spike batching via a dedicated queue (`notifications-tier2-dm`). But the document only addresses spike batching as a source of DM delay. DMs still share delivery workers, APNs/FCM connections, and the Redis preference cache with all other Tier 2 traffic. During a spike that saturates those shared resources, DM delivery latency will degrade even though DMs never enter the spike-batched queue. The architectural isolation is partial, but the document presents it as solving the DM latency problem entirely.