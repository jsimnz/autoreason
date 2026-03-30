## Real Problems with This Proposal

### 1. The 8× Peak Factor Is Unexplained and Possibly Wrong

The document derives a peak throughput of ~120/second by applying an "8× peak factor" to the average hourly rate. No justification is given for why 8× is the right multiplier rather than 4× or 15×. The document earlier notes that 20–25% of DAU are active during their local peak hour spread across a 2–3 hour window — that reasoning, if followed through, does not obviously produce an 8× figure. The number appears to be asserted rather than derived. Since all provisioning targets flow from this figure, an unsupported multiplier undermines the entire load model.

### 2. The SMS Cost Estimate Has No Stated Basis

The document claims security-only SMS will cost $5,000–15,000/year based on "security event rates well under 0.1% of DAU," but 0.1% of 2.5M DAU is 2,500 events/day, which is ~912,500 messages/year. At $0.01/message that is ~$9,000/year — plausible, but the document never shows this arithmetic. More importantly, it doesn't account for international SMS rates, which can be 5–20× domestic rates. For a global social app, the stated range could be badly wrong in the upward direction.

### 3. Concurrent Multi-Channel Tier 1 Delivery Is Not Actually Cost-Controlled

The document acknowledges that concurrent push + SMS + email for all Tier 1 events creates cost exposure during spikes, and says "the controls preventing that exposure are described in §1.6." Section 1.6 is never provided in this document. This pattern appears multiple times — critical operational controls are repeatedly deferred to a missing section. This is not a minor gap: it means the cost protection, the SMS boundary enforcement, the volume enforcement for the <0.1% Tier 1 claim, and the auto-scaling configuration are all described as existing but are not actually present in the document.

### 4. The Document Is Incomplete and Presents Itself as Complete

The preface states "this document provides a complete technical design." The document is visibly truncated mid-sentence in the digest batching section. Section 1.6 (auto-scaling, SMS boundary controls, Tier 1 volume controls) is referenced repeatedly but never appears. Section 1.8 (validation process, 60-day batching review) and 1.9 (archival behavior) are also referenced but absent. A design document that calls itself complete while missing multiple sections it depends on is misleading to anyone who reads the preface and acts on that claim.

### 5. The 30-Day Validation Window Creates Real Under-Provisioning Risk It Claims Not To

The document states explicitly: "The 30-day validation window is not a grace period during which the system might be under-provisioned." Then it describes a scenario where actual DAU/MAU exceeds 40% *before* the 30-day mark and says the on-call engineer escalates "immediately." But escalation is not provisioning. There is no pre-staged capacity, no pre-negotiated auto-scaling ceiling, and no stated time budget between "engineer escalates" and "capacity is available." Cloud auto-scaling does not provision instantly under all conditions, especially if baseline instance counts are low. The reassurance contradicts the actual mechanism.

### 6. Jitter Is Presented as More Effective Than It Is

The document claims jitter reduces instantaneous peak by "approximately 15×" by spreading users across 15 one-minute buckets. This assumes users are uniformly distributed across the 15-minute window, which the hash-based deterministic jitter does not guarantee — hash outputs can cluster. More importantly, the document then immediately concedes that even with jitter, the morning release for a 10M MAU base with 10% quiet-hour adoption produces ~3,300/second, which triggers spike batching anyway. The jitter analysis is presented as a meaningful mitigation but the document's own numbers show it doesn't prevent the problem it's meant to address.

### 7. The Batching Threshold Values Have No Empirical Basis and No Interim Owner

The 5-notification threshold and 10-minute window are described as "starting values based on industry convention, not empirical data from this product," with a review scheduled at 60 days. There is no owner named for this review, no stated consequence if the review doesn't happen, and no description of what "industry convention" means here or which products it comes from. Given that these thresholds directly affect user experience for the highest-volume notification type (likes, at 375K/day), shipping them without a named owner for the review is a gap.

### 8. APNs/FCM Rate Limit Mitigation Is Purely Reactive

The document acknowledges that APNs and FCM rate-limit by app credential and that DM isolation cannot protect against this. The mitigation is "monitor rate limit responses and alert before the limit is reached, so the team can engage Apple/Google about limit increases." Engaging Apple and Google about rate limit increases is not a fast process — it can take weeks and is not guaranteed. There is no stated current rate limit, no stated headroom, and no fallback if the limit is reached before the engagement resolves. For a system where DM delivery is explicitly called out as qualitatively important, this is a thin mitigation.

### 9. The In-App 30-Day Rolling Window Has No Stated Behavior at the Boundary

The document notes the in-app notification center shows a 30-day rolling window and says "archival behavior at that boundary is addressed in §1.9" — which is missing. For users, silent deletion of notifications at day 30 is a different experience than archiving, which is different from pagination. This is a product-facing behavior that is simply unspecified.

### 10. Digest Snapshot Correctness Argument Has a Logical Gap

The document argues that a restart generating a new snapshot timestamp requires "either a missing or corrupted `digest_job_runs` row." But it does not address the case where the job crashes *before* the `digest_job_runs` row is committed — i.e., the row doesn't exist yet because the crash happened between job start and the first database write. In that case, a restart would create a new row with a new snapshot timestamp, and users processed in any partial first run before the crash would receive duplicate digests. The document's own correctness argument does not cover this window.