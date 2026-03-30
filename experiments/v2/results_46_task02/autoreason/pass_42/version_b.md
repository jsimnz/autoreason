# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 14 days of launch**, not 30 — the rationale for the earlier deadline is explained below.

#### 1.1.1 Compounded Assumption Risk

The peak throughput figure used for provisioning is derived by multiplying three independent estimates in sequence:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU from 10M MAU). Range of plausible values: 20–45%.
2. **Notification rate per DAU:** assumed per event type in the table below. These figures are drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Explicitly unsupported by product-specific data.

Compounding three independent assumptions produces a confidence interval that is never fully quantifiable before launch, but the direction of risk is clear: if the DAU/MAU ratio, per-user notification rate, and peak multiplier are all simultaneously higher than estimated — which is possible, since they are not independent; a highly engaged user base tends to produce higher values on all three dimensions — the resulting peak throughput could exceed the provisioning target by a factor of 3 or more, not merely 2×.

The 2× provisioning headroom described below is calibrated to handle any single assumption being wrong by a large margin, or two assumptions being modestly wrong simultaneously. It does not fully cover the scenario where all three are simultaneously wrong in the same direction. That scenario is addressed through the early validation window (14 days, not 30) and the manual escalation trigger described in §1.1.4.

This compounding risk is the primary reason the validation window is 14 days rather than 30. By day 14, enough traffic has been observed to replace the peak multiplier and the per-user notification rate with measured values, even if the DAU/MAU ratio is still stabilizing. Replacing two of the three compounded assumptions substantially reduces the uncertainty in the provisioning target.

#### 1.1.2 Notification Volume Estimates

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
- Evening peak concentration: social app traffic during evening peak (19:00–21:00 local time) runs approximately 3–4× the active-hours average. We use 3× as a conservative estimate and flag it as unsupported by product-specific data. This multiplier applies to the notification *delivery* curve, not the user action curve — batching, quiet-hour suppression, and asynchronous retry all smooth delivery relative to action volume. Using action-volume peak ratios to model delivery-volume ratios would introduce unquantified error in the upward direction. Applying 3×: ~63/second at peak.
- Cross-timezone smoothing: for a global user base, peaks in different regions partially overlap and reduce the instantaneous global peak, but the magnitude depends on geographic distribution of users. We treat the 63/second figure as a single-timezone worst case and use the un-smoothed number for provisioning — the correct direction of error.
- Provisioning target with 2× headroom: **~130 notifications/second**

This headroom is applied to the output of compounded assumptions. Its adequacy depends on how many assumptions are simultaneously wrong. See §1.1.1 for the explicit statement of what this headroom does and does not cover.

#### 1.1.4 Load Validation — Owner, Process, Decision Rules, and Enforcement

**Owner:** Priya Mehta (backend engineer, notifications lead). If team composition differs at project kickoff, the project lead updates this line before the document is distributed.

**Ownership transfer process:** If Priya's role changes or she leaves the team, the project lead designates a replacement owner in writing within 48 hours, notifies the replacement directly, and updates this document. The replacement owner acknowledges the assignment in writing (a reply to the notification email is sufficient). If the project lead fails to make this designation within 48 hours, the team lead assumes temporary ownership and designates a permanent replacement within the following 48 hours. "Temporary team lead ownership" is not a permanent state — it is a defined fallback that triggers a 48-hour clock, not an indefinite default. The gap this process is designed to prevent — undocumented ownership lapse — is detectable: if no named owner appears in this document's header at any point during the project, that is itself an escalation trigger.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate, broken down by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

**Review schedule:**

The 14-day review is mandatory and replaces the 30-day review for the initial validation. It is not optional. It is also triggered immediately — not deferred — if any of the following are observed before day 14:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%

The earlier deadline specifically addresses the compounded assumption risk in §1.1.1: by day 14 there is enough traffic data to replace the per-user notification rate and peak multiplier with measured values. A 30-day window would leave the system running on all three unsupported assumptions for twice as long with no actionable data.

**Decision rules — unified headroom standard:**

All decision rules, whether triggered by upward or downward deviation, target the same headroom standard: **baseline instance counts set to handle 1.5× the measured sustained peak**. This is the consistent standard that applies in all cases. The specific actions:

- If actual peak is within 50% of the 130/second estimate in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts until the new baseline handles 1.5× the measured peak. Do not apply a mechanical ratio from the old estimate — compute the new baseline from the measured peak directly.
- If actual peak is more than 100% above estimate: escalate to team lead and product within 24 hours; implement infrastructure changes within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: reduce baseline instance counts to handle 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure — the safety margin is intentional.

The 1.5× standard applies consistently across all cases. There is no scenario in which the decision rules produce a baseline with less than 1.5× headroom over the measured peak.

The 14-day review produces a written update to this section. That update is the authoritative figure for all subsequent planning.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

#### 1.2.1 Push Notifications

Push is the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which use concurrent multi-channel delivery described in §1.3.

**APNs error handling — corrected model:**

APNs uses HTTP/2 persistent connections. The error signaling model is fundamentally different from FCM's and must be implemented correctly; building APNs retry logic on the FCM model will produce a broken implementation.

APNs error responses are returned in the HTTP/2 response to each push request, using the `:status` pseudo-header and a JSON body with a `reason` field. The relevant cases for rate limiting and backpressure:

- **`TooManyRequests` (HTTP 429):** Apple returns this when the push worker is sending too many requests to APNs in a short period. The response does not include a `Retry-After` header — this is the FCM pattern, not the APNs pattern. The correct response is exponential backoff starting at 1 second, doubling up to a maximum of 32 seconds, with jitter. The push worker must implement this directly, not by reading a retry header.
- **`TooManyProviderTokenUpdates` (HTTP 429):** returned when token-based authentication keys are being refreshed too frequently. Distinct from the general rate limit; handled by caching the provider token for its full validity window (up to one hour) rather than regenerating it per request.
- **`BadDeviceToken` (HTTP 410 or 400 with reason `BadDeviceToken`):** the device token is invalid or the app has been uninstalled. The push worker must remove this token from the device registry immediately on receiving this response. Retrying a bad device token wastes quota and produces no delivery.
- **`DeviceTokenNotForTopic` (HTTP 400):** the token does not match the app's bundle ID. Remove from registry; do not retry.
- **HTTP/2 stream errors and connection resets:** APNs may close the HTTP/2 connection under sustained load. The push worker must implement connection pool management with reconnection logic, not just per-request retry.

APNs does not publish a documented per-app global throughput limit. At 130 notifications/second projected peak, this is not an anticipated constraint. If undocumented global limits become relevant at higher scale, they will appear as elevated `TooManyRequests` response rates and trigger the alert threshold below.

Alert threshold: APNs delivery failures (any 4xx or 5xx response) exceeding 5% of attempts over a 5-minute window triggers an alert. The on-call engineer investigates whether the failure pattern matches a known error type (bad tokens, rate limiting, connection issues) and responds accordingly.

**FCM error handling:**

FCM HTTP v1 API returns structured error responses. The relevant cases:

- **HTTP 429 with `Retry-After` header:** FCM does include a `Retry-After` header. Honor it. If no `Retry-After` is present despite a 429, fall back to exponential backoff starting at 1 second.
- **`UNREGISTERED` error:** the FCM registration token is invalid. Remove from registry; do not retry.
- **`INVALID_ARGUMENT`:** malformed request. Log and alert; do not retry without fixing the request.
- **HTTP 500/503:** transient server error. Retry with exponential backoff.

FCM rate limits: maximum 600,000 requests/minute per project. At 130 notifications/second projected peak, the system sends approximately 7,800 requests/minute — well within limits. Alert at 420,000 requests/minute (70% of limit).

**Implementation note:** APNs and FCM push workers are separate code paths with separate error handling logic. They share queue infrastructure and monitoring but must not share retry or error-handling code — the signaling models are incompatible.

#### 1.2.2 In-App Notifications

In-app notifications are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push.

**The in-app write guarantee — implementation specification:**

The document states that every Tier 2 notification is written to the in-app store regardless of push status. This guarantee requires a concrete implementation; a statement of intent without implementation backing is not a guarantee.

Implementation: the notification worker performs a **synchronous dual-write** — it writes to the in-app store first, then attempts push delivery. The in-app write is the prerequisite for the push attempt, not a parallel operation. If the in-app write fails, the entire notification job is retried from the queue; push is not attempted. If the in-app write succeeds and push fails, the notification is already in the in-app store — the guarantee is satisfied without any reconciliation step.

*Tradeoff accepted:* Synchronous dual-write adds latency to push delivery (the in-app write must complete before push is attempted) and couples the two operations. The alternative — parallel writes with a reconciliation process — would reduce latency but requires implementing and operating a reconciliation job, which adds complexity this team cannot afford to maintain reliably. The latency cost of sequential writes is acceptable: in-app store writes are expected to complete in under 10ms at p99 for the notification sizes involved. Push delivery latency is dominated by APNs/FCM round-trip time (typically 100–500ms), making the 10ms in-app write overhead negligible from the user's perspective.

The in-app write guarantee applies to Tier 2 notifications. Tier 1 (security) notifications use a different delivery path described in §1.3. Tier 3 (batched digest) notifications are written to the in-app store when the digest is assembled, not when the triggering event occurs.

**Retention and archival:**

The in-app notification center displays a rolling 30-day window. Notifications older than 30 days are moved to cold storage (S3) rather than deleted. The in-app UI does not display archived notifications by default. A "load older notifications" control triggers a cold storage fetch for the requesting user.

*Tradeoff accepted:* Cold storage fetch adds latency for historical notification access. This is acceptable because users reading notifications more than 30 days old is a low-frequency use case. The alternative — keeping all notifications in the primary store — would increase primary store size by approximately 12× for active users and degrade query performance for the common case.

**The cold storage UI and infrastructure — resolving the internal contradiction:**

The previous draft justified cold storage on the grounds that reading notifications older than 30 days is rare, then specified a dedicated UI control, a rate-limiting system, a circuit breaker, and a user-facing error message for that rare use case. These are in tension: either the use case is rare enough that minimal infrastructure is warranted, or it is common enough that the cold storage tradeoff deserves reconsideration.

The resolution: the "load older notifications" UI control and cold storage access are retained, but the infrastructure protecting against abuse is simplified to match the stated frequency. A **20 fetches/user/day** rate limit is enforced at the API gateway level using an existing rate-limiting mechanism (not a bespoke circuit breaker). When the limit is reached, the API returns HTTP 429 and the client displays: "You've reached the limit for loading older notifications today." The rate limit exists to catch client bugs (a client in a retry loop), not to manage cost or expected user behavior. No dedicated rate-limiting service is built for this; the API gateway's standard per-user rate limiting is sufficient.

If usage data after launch shows that cold storage access is in fact common — more than 5% of DAU triggering at least one cold storage fetch per week — the cold storage tradeoff should be revisited: either extend the primary store retention window or accept that the cold storage infrastructure is load-bearing rather than incidental. This review is owned by the notifications lead and is part of the 90-day post-launch review.

**Retention period and legal basis:**

The in-app store retains notifications for 30 days. Cold storage retains notifications for **90 days from creation**, then permanently deletes them.

*Why 90 days:* A social app with 10M MAU almost certainly has EU users, making GDPR compliance non-optional. Notification content (e.g., "Alice liked your post") contains personal data. The 90-day figure reduces the personal data footprint