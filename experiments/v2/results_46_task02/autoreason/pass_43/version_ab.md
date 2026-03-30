# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 14 days of launch.** The rationale for 14 days rather than 30 is explained in §1.1.1.

#### 1.1.1 Compounded Assumption Risk

The peak throughput figure used for provisioning is derived by multiplying three independent estimates in sequence:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU from 10M MAU). Range of plausible values: 20–45%.
2. **Notification rate per DAU:** assumed per event type in the table below. These figures are drawn from general social app benchmarks, not product-specific data — see §1.1.2 for the explicit limitation this creates.
3. **Evening peak multiplier:** assumed at 3×. Explicitly unsupported by product-specific data.

Compounding three independent assumptions produces a confidence interval that is never fully quantifiable before launch, but the direction of risk is clear: if the DAU/MAU ratio, per-user notification rate, and peak multiplier are all simultaneously higher than estimated — which is possible, since they are not fully independent; a highly engaged user base tends to produce higher values on all three dimensions — the resulting peak throughput could exceed the provisioning target by a factor of 3 or more, not merely 2×.

The 2× provisioning headroom described below is calibrated to handle any single assumption being wrong by a large margin, or two assumptions being modestly wrong simultaneously. It does not fully cover the scenario where all three are simultaneously wrong in the same direction. That scenario is addressed through the 14-day validation window and the manual escalation trigger described in §1.1.4.

This compounding risk is the primary reason the validation window is 14 days rather than 30. By day 14, enough traffic has been observed to replace the peak multiplier and the per-user notification rate with measured values, even if the DAU/MAU ratio is still stabilizing. Replacing two of the three compounded assumptions substantially reduces the uncertainty in the provisioning target. A 30-day window would leave the system running on all three unsupported assumptions for twice as long with no actionable data.

#### 1.1.2 Notification Volume Estimates

The per-event rates below are drawn from general social app benchmarks, not product-specific data. This is a material limitation. Notification rates vary substantially across social product types: a platform with algorithmically amplified content will produce radically higher per-user like notification rates than a close-friends network where content distribution is narrow. A real-time messaging product will produce higher DM notification rates than a passive content feed.

**The rates in this table should be treated as order-of-magnitude placeholders, not calibrated estimates.** Any single rate could be off by 2–5× in either direction depending on product mechanics. The 2× provisioning headroom does not absorb a 5× error on the highest-volume event type (direct messages). The 14-day validation review in §1.1.4 is the mechanism for replacing these placeholders with measured values; until that review completes, the system is running on unvalidated assumptions for its most important input.

| Event type | Rate assumption | Daily volume |
|---|---|---|
| Post liked | 15% of DAU trigger one like notification | 375,000 |
| Comment received | 8% of DAU | 200,000 |
| New follower | 5% of DAU | 125,000 |
| Mention | 3% of DAU | 75,000 |
| Direct message | 20% of DAU send at least one | 500,000 |
| System/product | 2% of DAU | 50,000 |
| **Total baseline** | | **~1.3M/day** |

#### 1.1.3 Peak Throughput Derivation

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- **Evening peak multiplier and geographic distribution — resolved tension:** The document uses a 3× evening peak multiplier applied to the active-hours average and simultaneously acknowledges a global user base. These two assumptions interact: a globally distributed user base reduces the sharpness of any single regional evening peak because peaks in different timezones partially overlap and smooth the global delivery curve. However, the geographic distribution of users is unknown at this stage. Applying a cross-timezone smoothing discount to an unsupported peak multiplier would compound two unsupported assumptions in opposite directions, producing a figure with false precision. The correct approach is to use the single-timezone worst case (no smoothing discount) for provisioning — this is the direction of safe error — and note that if the user base proves to be globally distributed, the actual peak will be lower than provisioned for. Applying 3× to the active-hours average: ~63/second at peak.
- **Spike buffering and the auto-scaling gap:** Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes. During that window, if an unprovisioned spike occurs, new capacity is not yet available. The system handles this gap through queue buffering: all notification jobs are enqueued before processing, so a spike above current processing capacity accumulates in the queue rather than dropping requests or returning errors. At 130/second provisioning target and a hypothetical 3× spike (390/second), the queue accumulates approximately 390 × 150 seconds = 58,500 jobs during a 2.5-minute gap. At approximately 1KB per notification job, this is ~58MB of queue backlog — well within the capacity of standard queue infrastructure. Queue depth alert thresholds are set in §1.1.4; a sustained spike that does not subside within 5 minutes triggers escalation before the queue reaches problematic depth.
- Provisioning target with 2× headroom for compounded assumption uncertainty: **~130 notifications/second**

All queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. The system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the compounded assumption uncertainty. Auto-scaling typically provisions new instances within 2–5 minutes; baseline instance counts therefore affect how much burst capacity is available before scaling kicks in, and the baseline is not set at the minimum viable count.

#### 1.1.4 Load Validation — Owner, Process, Decision Rules, and Enforcement

**Current owner:** Priya Mehta (backend engineer, notifications lead).

**Pre-distribution check:** Before this document is distributed to any stakeholder, the project lead must verify that the named owner above reflects current team composition. This verification is a named step in the project kickoff checklist, not a reminder — if the checklist is not completed, distribution is blocked. The project lead's signature on the checklist is the evidence that the named owner was verified at distribution time.

**Ownership transfer process:** If the named owner's role changes or she leaves the team, the project lead designates a replacement in writing within 48 hours, notifies the replacement directly, and updates this document. The replacement owner acknowledges the assignment in writing. If the project lead fails to make this designation within 48 hours, the team lead assumes temporary ownership and designates a permanent replacement within the following 48 hours. An undocumented ownership lapse is detectable: if no named owner appears in this document's header at any point during the project, that is itself an escalation trigger to the team lead.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate, broken down by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

**Review schedule and enforcement:**

The 14-day review is mandatory. It produces a written update to this section that becomes the authoritative figure for all subsequent planning. The review is not optional and is not deferred because nothing appears wrong.

**Enforcement mechanism:** The review date is entered as a calendar event with the team lead and product lead as required attendees at project kickoff. Missing the review requires explicit sign-off from the team lead, who must document why it was deferred and set a new date within 72 hours. The consequence of missing the review without sign-off is escalation to the product lead; the review does not simply slip. The notifications lead owns scheduling the review; the team lead owns enforcing that it happens.

The review is also triggered immediately — before day 14 — if any of the following are observed:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%

**Decision rules — unified headroom standard:**

All decision rules, whether triggered by upward or downward deviation, target the same headroom standard: **baseline instance counts set to handle 1.5× the measured sustained peak**. This standard applies in all cases without exception.

- If actual peak is within 50% of the 130/second estimate in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts until the new baseline handles 1.5× the measured peak. Compute the new baseline from the measured peak directly — do not apply a mechanical ratio from the old estimate.
- If actual peak is more than 100% above estimate: escalate to team lead and product within 24 hours; implement infrastructure changes within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: reduce baseline instance counts to handle 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure — the safety margin is intentional, but the degree of over-provisioning was calibrated to uncertainty that has now been partially resolved.

The 14-day review produces a written update to this section. That update is the authoritative figure for all subsequent planning.

---

### 1.2 Notification Tiers

Tiers govern delivery priority, channel selection, batching behavior, and failure handling. Every notification is assigned a tier at creation time. The tier assignment is immutable — it cannot be changed by user preference or batching logic, only by the event type definition.

The tier system exists to prevent two failure modes. First, it prevents a backlog of Tier 3 ambient notifications from delaying Tier 1 security events — they run on separate queues with separate workers. Second, it prevents per-user notification volume from being dominated by likes and follows, which are high-volume, low-urgency events that would obscure higher-value interactions if delivered immediately and individually.

**Tier 1 — Security and account events.** Examples: password reset, email address change, login from new device, account recovery. Delivery is concurrent across all available channels (push, email, SMS, in-app). No batching. No quiet-hour suppression. Failure on any single channel does not suppress delivery on others. Delivery is attempted on every channel regardless of user preferences, because the user's ability to act on a security event must not depend on which channels they have opted into. *Legal caveat:* if this interpretation conflicts with applicable regulations in a specific jurisdiction (some privacy frameworks require opt-in for all commercial communications regardless of category), legal review is required before launch in that jurisdiction. This is an open item requiring legal sign-off before launch.

**Tier 2 — Direct social interactions.** Examples: direct messages, mentions, comments on the user's own content. Delivered promptly (target: within 60 seconds of the triggering event for an online device). Subject to quiet-hour suppression. Not batched. Every Tier 2 notification is written to the in-app store before push is attempted — see §1.4.2 for the implementation guarantee.

**Tier 3 — Ambient social activity.** Examples: likes on posts, new followers, reposts. Batched into digests delivered at most once per hour per user. Subject to quiet-hour suppression. Written to the in-app store when the digest is assembled, not when the triggering event occurs. Users who prefer immediate delivery of likes and follows can upgrade these to Tier 2 cadence via preference settings (§1.5), but the notification still goes through the Tier 3 delivery worker; the preference controls delivery timing, not the worker assignment.

---

### 1.3 Tier 1 Delivery Path

Tier 1 notifications require a delivery approach distinct from Tier 2 and Tier 3 because the cost of non-delivery is high and the user cannot be expected to have any particular channel preference configured. A user who has never set up push notifications still needs to receive a password reset email.

**Delivery behavior:** All available channels are attempted concurrently at the moment the Tier 1 event is created. "Available" means the channel infrastructure is operational, not that the user has opted into it — user channel preferences do not suppress Tier 1 delivery.

**Per-channel behavior under Tier 1:**

- **Push:** Sent immediately via APNs/FCM with the highest-priority flag (`apns-priority: 10` for APNs, `priority: high` for FCM). Not collapsed with other notifications.
- **Email:** Sent immediately via the transactional email provider. Not batched. Uses a dedicated sending domain separate from marketing or digest email to protect deliverability — a security email arriving in spam because the sending domain was flagged for digest volume is a Tier 1 delivery failure.
- **SMS:** Sent immediately via SMS provider. Tier 1 is the only tier that uses SMS proactively — for Tier 2 and Tier 3, SMS is used only as a fallback when the user has no other reachable channel.
- **In-app:** Written to the in-app store immediately, with distinct visual treatment (persistent red badge until acknowledged) that distinguishes it from social notifications.

**Failure handling under Tier 1:** Each channel retries independently. A failure on push does not delay the email attempt. Each channel exhausts its retry budget (3 attempts with exponential backoff, maximum 5-minute total retry window) independently. After retry exhaustion on all channels, the event is written to a dead-letter queue and an alert fires to the on-call engineer. The 5-minute retry window is intentionally short for security events — a password reset that takes 20 minutes to arrive is functionally useless if the user is trying to recover access in real time.

**Delivery confirmation logging:** Each channel attempt is logged with timestamp, channel, outcome (delivered/failed/retried), and error code if failed. This log is retained for 90 days and is the source of truth for incident investigation. Push delivery acknowledgment from APNs/FCM is not treated as proof the user saw the notification — in-app acknowledgment (the user tapping the notification) is the only confirmed-read signal.

---

### 1.4 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

#### 1.4.1 Push Notifications

Push is the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which use concurrent multi-channel delivery as described in §1.3.

**APNs and FCM push workers are separate code paths with separate error handling logic.** They share queue infrastructure and monitoring but must not share retry or error-handling code — the signaling models are incompatible. Conflating the two is a common implementation error that produces broken retry behavior on one or both platforms.

**APNs error handling:**

APNs uses HTTP/2 persistent connections. Error responses are returned in the HTTP/2 response to each push request via the `:status` pseudo-header and a JSON body with a `reason` field.

- **`TooManyRequests` (HTTP 429):** APNs does not include a `Retry-After` header — this is the FCM pattern, not the APNs pattern. The correct response is exponential backoff starting at 1 second, doubling up to a maximum of 32 seconds, with jitter. The push