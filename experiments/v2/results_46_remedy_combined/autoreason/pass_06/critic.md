## Real Problems with This Proposal

### 1. The FIFO Queue Throughput Ceiling Is Not Adequately Addressed

SQS FIFO queues are capped at 3,000 messages/second with batching (300/second without). The proposal puts P1 (DMs, mentions) on a FIFO queue and models P1 peak traffic as a fraction of 9,700/second total. Even if P1 is only 20% of peak traffic, that's ~1,940/second — approaching or exceeding the FIFO ceiling. The proposal mentions "re-evaluate FIFO queue headroom" as a Scaling Trigger A action, but this is a known architectural constraint that exists at launch, not a future scaling concern. The ceiling is deterministic and calculable now. Deferring it to a trigger is not analysis.

### 2. Message Group ID Strategy for FIFO Is Absent

FIFO queue ordering guarantees are per message group ID. If all P1 messages share one group ID, throughput collapses to sequential processing. If each user conversation is a group ID, you get parallelism but must reason carefully about what "ordering" actually means across millions of concurrent group IDs. The proposal justifies FIFO for P1 with "direct messages in a conversation must maintain ordering" but never specifies the message group ID design. This is a critical implementation detail that determines whether the ordering guarantee is real or illusory.

### 3. The Preference Staleness Tradeoff Is Named But Never Defined

The executive summary mentions "a preference system that trades bounded staleness for throughput" as a core architectural bet. This is never explained anywhere in the visible document. There is no section on preference caching, no staleness bound given (seconds? minutes? hours?), no description of what happens when a user opts out of a notification type and continues receiving that type during the staleness window. For a system with legal compliance implications (CAN-SPAM, GDPR consent withdrawal), an unspecified staleness bound on opt-out propagation is a real liability, not a performance footnote.

### 4. The Digest Volume Model Assumes Segmentation Data That Doesn't Exist

The digest model is built on "weekly-active but not daily-active users = ~2M (20% of MAU)." At launch, this segmentation does not exist. The proposal acknowledges that DAU needs to be instrumented from day one but does not apply the same caveat to the weekly-active segment, which is equally unknown. The 40% digest opt-in rate applied to this unknown segment compounds the uncertainty. The model presents a precise figure (526K emails/day) derived from two sequential estimates with no empirical basis.

### 5. The Worker Sizing Argument Contains a Hidden Assumption

The proposal justifies sizing workers for the high scenario (9,700/second) over the base scenario (4,500/second) on the grounds that over-provisioning costs $1,200/month while under-provisioning during growth is worse. This is reasonable. However, the proposal never states what a "worker" is in terms of compute resources, how many workers are needed to sustain 9,700/second, or what the per-worker throughput assumption is. The $1,200/month delta is presented as a conclusion without the calculation. If that number is wrong, the entire sizing argument is unsupported.

### 6. The OTP Rate Limiter Has a Logic Error

In the `should_send_sms_otp` method, the per-user daily limit check using Redis `INCR` runs after the spend-threshold checks. This means the Redis increment happens even when the function returns `False` at the emergency or critical threshold — the counter is incremented for a message that was never sent. Over time this causes users to hit their per-user daily limit due to blocked attempts, locking them out of OTP SMS for the remainder of the day even when the system-level spend returns to normal. This is a silent correctness bug.

### 7. The Worst-Case SMS Scenario Undermines the Alarm Structure

The proposal states the worst case (full breach, all MAU) generates $79,000/day. The emergency alarm threshold is $10,000/day, at which point the fallback protocol activates. But "Blocking Decision Point 1" — which governs what happens to users without email OTP when SMS is rate-limited — is explicitly deferred and not resolved in this document. The alarm structure escalates to a decision that hasn't been made. In an actual emergency, the automated response hits an unresolved dependency.

### 8. The 35% DAU Assumption Is Applied Inconsistently

The proposal uses 35% DAU (3.5M) as the basis for SMS modeling but uses total MAU (10M) as the basis for push opt-in and notification volume modeling. These are different populations being used interchangeably in different sections without acknowledgment. The sensitivity table in Section 1.1 is built on opted-in users derived from MAU; the SMS model is built on DAU. A user who is monthly-active but not daily-active would appear in the push volume model but not the SMS baseline. This inconsistency is not flagged anywhere.

### 9. Four Engineers for Six Months Cannot Own This Scope

The proposal references "E1," "E2," "E4," and team allocation problems, but the visible document never shows the actual allocation. What is visible is the scope: four queue families with DLQs and CloudWatch alarms, a preference system, multi-channel delivery (push, email, SMS, in-app), provider integrations, scaling trigger responses including a structural queue migration, and three blocking decision points requiring cross-functional coordination. The proposal acknowledges "the E2 overload problem" exists and claims to resolve it, but the resolution is not in the visible text. Claiming a staffing problem is resolved without showing the resolution is not the same as resolving it.

### 10. Transactional Email Volume Has No Delivery Latency Requirement

Account verification, password reset, and security alerts are listed as transactional email. These are time-sensitive: a password reset email that arrives 20 minutes late is a support ticket; an OTP via email (used as fallback when SMS is rate-limited) that arrives late breaks authentication flows. The proposal models volume for transactional email but specifies no delivery SLA, no queue priority for transactional versus digest email, and no monitoring for delivery latency. SendGrid is listed as the provider with no discussion of whether transactional and digest traffic share the same sending infrastructure or IP pools — a deliverability concern with real consequences.