## Real Problems with This Proposal

### 1. The 17/day Figure Is Load-Bearing but Unvalidated, and the Calibration Window Is Too Late

The document acknowledges the 17/day figure is a planning assumption, but month 2 calibration means the system is designed, built, and partially deployed before the core input is verified. The >5× contingency explicitly states this invalidates the 6-month plan. There is no mechanism to get early signal before committing to the architecture—no beta cohort sizing, no instrumentation of existing user behavior, no proxy metric. The honesty about the risk does not reduce the risk.

### 2. The Spike Math Contains a Hidden Assumption That Undermines the Entire Spike Analysis

The viral spike model assumes 20× peak multiplier lasting 90 seconds. But the 20× figure is applied to the *sustained peak* rate (1,750/sec), not to instantaneous burst. The document never justifies why a viral event would be bounded to 90 seconds or why 20× is the right multiplier. A celebrity post or coordinated event can produce a step function, not a smooth spike—meaning the queue absorber assumption (gradual accumulation, gradual drain) may not hold. The drain time math is only valid if the spike is actually shaped the way assumed.

### 3. P0 Worker Throughput Assumption Is Borrowed From Push, But P0 Is Described as Security Alerts

The 350 notifications/sec per worker figure is derived from APNs/FCM HTTP/2 multiplexing. P0 is described as security alerts and account compromise notices. These likely route to SMS and email, not push—channels with fundamentally different throughput characteristics (Twilio SMS is rate-limited by long code vs. short code, SendGrid has its own per-second limits). The worker count derivation for P0 uses the wrong throughput model for the actual P0 traffic mix.

### 4. The Reconciliation Job Is Named But Never Specified

"Every 5 minutes — resolves split-path consistency" appears in the architecture diagram. The document cuts off before explaining what it reconciles, what the consistency model is, or what happens when it finds a discrepancy. For a system with split paths (queue for push/email/SMS, direct write for in-app), this is a critical component. Naming it without specifying it means no one can actually build it, and the consistency guarantees of the system are undefined.

### 5. E4's Scope Arithmetic Is Wrong

The document says E4's residual scope after managed services is "approximately 60% of one engineer's time," with the remaining 40% going to reconciliation job, partition management automation, and month-2 monitoring instrumentation. Reconciliation job development, partition management automation, and production monitoring instrumentation are not 40% tasks—they are each substantial engineering efforts. The document asserts the math works out without showing it.

### 6. The Write-Through Race Condition Is Accepted Without Quantifying Frequency

The preference cache race condition is acknowledged: a user can receive a notification for up to 10 minutes after disabling it. The document calls this "annoying, not dangerous." But at 1,750 notifications/sec with a 5-minute TTL and a write-through pattern, the frequency of this race at scale is not estimated. For a 10M MAU social app where preference changes are common (users muting notifications during meetings, etc.), the aggregate rate of mis-delivered notifications could be significant and a source of user complaints or unsubscribes—not a rare edge case.

### 7. The SMS Budget Enforcement Mechanism Is Described as Concrete But Doesn't Exist Yet

Section 3.4 is referenced multiple times as containing a "concrete technical gate" for SMS budget enforcement. The document is cut off before Section 3.4 appears. The SMS cost range is $240K–$1.38M/month depending on geography. The entire SMS cost risk management depends on a mechanism that is promised but not described anywhere in the visible document.

### 8. Block Suppression Correctness Claim Relies on Organizational Discipline, Not Technical Enforcement

"Block suppression is architecturally separated from preference caching. These are different code paths, not asserted separation." This sentence acknowledges the problem and then restates it. There is no technical mechanism preventing a future engineer from adding a cache layer to the block suppression path—no interface boundary, no enforced abstraction. The safety guarantee is a convention, not an invariant.

### 9. In-App Direct Write Bypass Creates an Unacknowledged Ordering Problem

In-app notifications bypass the queue and write directly to PostgreSQL. Push notifications for the same event go through the queue. A user can receive a push notification for an event before the corresponding in-app notification is readable, or vice versa, depending on timing. The document does not acknowledge this ordering gap or describe what the user experience is when these arrive out of order. For a social app where users tap a push notification to see the in-app content, this is a real UX failure mode.

### 10. The >5× Contingency Kafka Migration Timeline Is Probably Wrong

The document states a Kafka migration is a "3–4 month project." For a team of 4 engineers, mid-flight, while maintaining the existing system, migrating to Kafka, and handling 250M+ notifications/day with a system already described as at the edge of what the team can safely own—3–4 months is optimistic. This number appears without basis. The contingency plan's credibility depends on this estimate being accurate, and it almost certainly is not.