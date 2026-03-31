## Real Problems with This Proposal

### 1. Worker Pool Sizing Is Circular and Underspecified

Section 1.5.3 derives the fanout rate limit from P3 worker pool capacity (8 workers), but Section 2.1 is cut off before explaining how 8 workers was determined. The "derivation" of 2,000 events/second depends on an unshown derivation. The document claims the fanout rate limit is "derived, not asserted" in the executive summary, but the actual worker pool count is asserted without basis. The circularity is hidden by the truncation.

### 2. The 5% P3 Weight Appears Without Origin

Section 1.5.3 uses "8 workers × 500 events/sec × 5% weight" to calculate P3 throughput during fanout, but the priority-aware worker pool model was introduced specifically to eliminate probability weights. The document explicitly states weighted fair queuing is replaced. Then it uses a weight (5%) in a throughput calculation for the new model. This is either a remnant of the discarded model or an unexplained hybrid, and it contradicts the architectural change the executive summary highlights as a primary improvement.

### 3. The Email Batching Analysis Conflates Two Different Claims

The document argues the batching window has only 1.02× throughput impact, then retains batching for digest grouping (a product requirement). These are separate justifications, but the throughput analysis is presented as the basis for the configuration management decision. If the real reason for retention is digest grouping, the throughput analysis is irrelevant to the keep/discard decision. More concretely: the 5-minute minimum threshold in Section 1.3.2 is justified by interaction with "email worker processing latency," but no email worker processing latency figure appears anywhere in the document. The threshold is asserted.

### 4. The Opt-Out Rate Is Applied Inconsistently

Section 1.1 applies a 20% global opt-out, leaving 80% of users. Section 1.2 then calculates email opt-in as "10M × 0.80 × 0.20 = 1.6M users" — correctly applying the opt-out. But the channel opt-in rates in Section 1.2 are described as rates "among the 80% of users who have not globally opted out," which is consistent. However, the in-app channel is listed at 100% opt-in and described as not disableable at the channel level. This means 8M users receive in-app notifications. But the routed notification events figure (14.4M) already has the 20% opt-out applied, so in-app delivery should be 14.4M events, not derived from 8M users. The per-channel delivery table shows 14.4M in-app events, which is consistent with the routed total, but the 1.6M email user denominator calculation treats opt-out and channel opt-in as independent when the document's own framing says channel opt-in is conditional on not having globally opted out. Whether these compound correctly depends on whether global opt-out and channel-level opt-in are stored and evaluated independently, which is never specified.

### 5. The Fail-Closed SMS Recommendation Has an Unexamined Failure Mode

Section 1.6.1 recommends halting SMS sending during suppression cache failures as the engineering-preferred option because it "converts a compliance risk into a delivery degradation." This is only true if the suppression cache failure is detectable before sending occurs. If the failure mode is silent (stale cache, partial failure, split-brain between cache nodes), SMS messages could be sent to opted-out numbers before the failure is detected. The document does not specify how suppression cache failures are detected, what the detection latency is, or whether the cache is the authoritative source or a replica of a durable store. The fail-closed recommendation is presented as solving the TCPA risk when it may only solve the case where the cache is detectably unavailable.

### 6. The 42-Minute P3 Clearance Time Is Accepted Without Examining What Happens During That Window

Section 1.5.3 acknowledges that for a 500,000-follower user, P3 queue clearance takes approximately 42 minutes. The document says "if the product launches follower notifications with users at this scale, the P3 worker pool must be resized." But follower notification is explicitly a post-launch feature with a launch gate. The launch gate checklist in Section 1.5.4 requires validating "delivery latency SLA confirmed acceptable for tail cases" — but no P3 delivery latency SLA exists anywhere in the document. Product lead is asked to sign off on something that has no specified value.

### 7. The Token Invalidity Architecture Has an Unowned Gap

Section 1.6.2 specifies that E2 "publishes structured events to `token.invalidated` stream" and "does not own downstream consumers," while E3 owns the "feedback processor (consumes `token.invalidated` stream)." E4 owns "`token.invalidated` stream infrastructure." What happens to push notifications in the window between token invalidity detection and the feedback processor consuming and acting on the event is unspecified. More specifically: if E2 detects a token as invalid during a delivery attempt, does it retry, drop, or dead-letter the in-flight notification? The ownership boundary is drawn at the stream, but the in-flight notification is neither E2's responsibility (E2 doesn't own downstream consumers) nor E3's (E3 consumes from the stream, not from the delivery attempt). This is a gap in ownership, not a clean handoff.

### 8. The DAU/MAU Sensitivity Analysis Sizing Claim Is Internally Inconsistent

The document states infrastructure is sized for the pessimistic scenario (20% DAU/MAU, 9.6M routed events/day) and claims the optimistic scenario (50%, 24M events/day) requires "worker pool counts increase approximately 2.5× the pessimistic baseline but no architectural changes." 2.5× the pessimistic baseline is exactly the ratio of optimistic to pessimistic routed events (24M / 9.6M = 2.5). This implies the system scales linearly with zero overhead, which contradicts the queue depth and fanout headroom constraints described elsewhere. The 50% headroom reservation in the fanout rate limit (Section 1.5.3) means the system at pessimistic sizing is not running at capacity — but the worker pool recount at optimistic volume is described as proportional scaling, ignoring that the headroom assumption changes when volume doubles.

### 9. Section 2.1 Is Truncated

The document cuts off mid-sentence at the end of Section 2.1. The priority-aware worker pool model — the primary architectural change highlighted in the executive summary — is never fully specified in the document body. The executive summary describes it, the introduction to Section 2.1 begins to describe it, and then the document ends. Any review of whether the revised model actually solves the problems identified with weighted fair queuing cannot be completed from this document.