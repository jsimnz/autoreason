# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. The design is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch.** Validation ownership and the specific process that turns findings into decisions are described at the end of this section.

**Sensitivity to DAU/MAU ratio:** The load model below is built on 2.5M DAU. If the actual ratio is higher — 40% DAU/MAU is not uncommon for a well-retained social app, implying 4M DAU — peak throughput roughly doubles. Infrastructure must be provisioned before this is known. The design response: all queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. This means the system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the DAU/MAU uncertainty.

Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes for standard instance types, but this is not guaranteed under all conditions. Baseline instance counts therefore affect how much burst capacity is available before scaling kicks in — the baseline is not set at the minimum viable count. If actual DAU/MAU exceeds 40% before the 30-day mark, the on-call engineer escalates immediately by manually increasing the auto-scaling ceiling. The 30-day review determines whether the elevated baseline should become the new permanent baseline or whether costs can be reduced.

**Notification volume estimates:**

| Event type | Rate assumption | Daily volume |
|---|---|---|
| Post liked | 15% of DAU trigger one like notification | 375,000 |
| Comment received | 8% of DAU | 200,000 |
| New follower | 5% of DAU | 125,000 |
| Mention | 3% of DAU | 75,000 |
| Direct message | 20% of DAU send at least one | 500,000 |
| System/product | 2% of DAU | 50,000 |
| **Total baseline** | | **~1.3M/day** |

**Peak throughput derivation:**

The previous approach of applying a cross-timezone smoothing factor without derivation has been removed. The derivation below shows its work and states explicitly where estimates are unsupported.

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Evening peak concentration: social app traffic during evening peak (19:00–21:00 local time) runs approximately 3–4× the active-hours average. We use 3× as a conservative estimate and flag it as unsupported by product-specific data. An earlier draft cited Twitter's documented peak/average ratio as a basis for this multiplier; that citation was methodologically flawed — Twitter's published peak ratios describe tweet creation or API request volume, not notification delivery volume. Notification delivery is downstream of user actions, subject to batching, quiet-hour suppression, and asynchronous retry, all of which smooth the delivery curve relative to the action curve. We cannot use action-volume ratios to model delivery-volume ratios without introducing unquantified error. We commit to replacing the 3× figure with measured data within 30 days. Applying 3×: ~63/second at peak.
- Cross-timezone smoothing: for a global user base, peak hours in different regions partially overlap and reduce the instantaneous global peak, but the magnitude of this effect depends on the geographic distribution of users, which is unknown before launch. Rather than substituting one unsupported number for another, we treat the 63/second figure as applying to a single-timezone scenario and note that the actual global peak will be lower by some factor that instrumentation will determine. For provisioning purposes, we use the un-smoothed number. This is conservative: we are provisioning for a higher peak than we expect, which is the correct direction of error.
- Provisioning target with 2× headroom for DAU/MAU uncertainty: **~130 notifications/second**

Brief spikes above the sustained peak are handled by queue buffering, not by provisioning for the instantaneous spike ceiling. These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

**30-day load validation — owner, process, and decision rules:**

Owner: **[Name of backend engineer designated to notifications at project kickoff — to be filled in before project start].** If team composition changes, ownership transfers explicitly in writing; it does not transfer by default to any engineer who happens to be working on notifications.

Required instrumentation, in place before launch:
- Per-second notification creation rate, broken down by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

Review trigger: the 30-day review is not optional. It occurs on day 30 regardless of whether anything appears wrong. It is also triggered immediately — not deferred — if any of the following are observed before day 30:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%

Decision rules at review:
- If actual peak is within 50% of the 130/second estimate: no infrastructure changes required; update the working figure.
- If actual peak is 50–100% above estimate: increase baseline instance counts by the ratio of actual to estimated peak; recalculate cost projections.
- If actual peak is more than 100% above estimate: escalate to team lead and product; infrastructure changes required within one sprint; document what the estimate got wrong and why.

The 30-day review produces a written update to this document's load estimates section. That update is the authoritative figure for all subsequent planning.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which require a fallback channel.

**APNs/FCM rate limits — a permanent architectural constraint:**

APNs and FCM rate limits are platform-level constraints. Apple and Google do not negotiate per-app rate limit increases through developer relations. Treating this as a dependency that could be resolved through outreach mischaracterizes a permanent constraint as a temporary one.

The correct framing: APNs and FCM rate limits are fixed constraints that the system must operate within. The design response is:
- Instrument push throughput per platform from day one, with alerts that fire at 70% of the known rate limit ceiling so the team has lead time before the limit is reached.
- If push volume approaches platform limits, the architectural response is batching and delivery scheduling to spread volume, not negotiation with platform vendors.
- The team lead reviews APNs and FCM public rate limit documentation in month 1 to establish the actual ceiling and configure alert thresholds accordingly. This is an information-gathering action, not a negotiation.
- If push volume is projected to reach platform limits within the 6-month horizon, this is escalated to the team lead and product as a capacity constraint requiring architectural mitigation: more aggressive batching, digest consolidation, or feature-level reduction in notification volume.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status.

The in-app notification center displays a rolling 30-day window. Archival behavior at the 30-day boundary: notifications older than 30 days are moved to cold storage (S3 or equivalent) rather than deleted. The in-app UI does not display archived notifications by default. A "load older notifications" control triggers a cold storage fetch for the requesting user, subject to a rate limit of 5 such fetches per user per day to prevent cold storage read amplification. Notifications are retained in cold storage for 12 months from creation, then permanently deleted. Users are notified of the 12-month deletion policy in the preference UI and in the app's privacy documentation.

*Tradeoff accepted:* Cold storage fetch adds latency for historical notification access. This is acceptable because users reading notifications more than 30 days old is a low-frequency use case. The alternative — keeping all notifications in the primary store — would increase primary store size by approximately 12× for active users and degrade query performance for the common case.

**Email** is used for digest notifications and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. This scope is deliberate and cost-bounded. The mechanism enforcing this boundary is described in §1.6.

**SMS cost model:**

Security event rate: estimated at 0.05% of DAU per day = 1,250 security events/day.

SMS-triggering security event types are defined at the event level, not the session level. A single login session can trigger both a 2FA SMS and a suspicious login alert, producing two separate SMS messages — one for each event type, because they serve different purposes (authentication vs. alert). The cost model must count both.

- **2FA SMS events:** created when a user with SMS-2FA enabled initiates a login requiring 2FA. Estimated at 30% of security events = 375 events/day.
- **Suspicious login alert events:** created when the fraud detection system flags a login. Estimated at 20% of security events = 250 events/day.
- **Session overlap:** most suspicious logins exhibit unusual patterns (new device, new location) that also trigger 2FA challenges for users with SMS-2FA enabled. Estimated 40% of suspicious login events co-occur with a 2FA event for users with SMS-2FA enabled: 250/day × 40% overlap × 30% SMS-2FA adoption = 30 additional SMS/day.

Total SMS volume: 375 + 250 + 30 = **655 SMS/day**, or approximately 239,000/year.

Domestic SMS rate (US): $0.0075/message. Blended international rate: $0.04/message (UK ~$0.04, India ~$0.009, Brazil ~$0.075, Germany ~$0.09 — weighted by typical social app geographic distribution). Assuming 40% domestic US traffic:

- Domestic: 239,000 × 0.40 × $0.0075 = ~$717/year
- International: 239,000 × 0.60 × $0.04 = ~$5,736/year
- **Total: ~$6,450/year**

Sensitivity: if the user base is skewed toward high-cost markets (Germany, Brazil), the international blended rate rises to ~$0.08/message, bringing total cost to ~$12,500/year. This range must be recalculated before launch in high-cost SMS markets. The SMS worker rejects any notification not tagged with a security event subtype at the routing layer; this is enforced in code, described in §1.6.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. This is a first-attempt target, not a guaranteed end-to-end delivery SLA. Retry behavior after a failed first attempt extends well beyond 60 seconds by design — the goal is eventual delivery, not abandonment after one attempt. These two properties are compatible.
- Channels: push, SMS, and email delivered concurrently — not sequentially. Waiting for push failure confirmation before sending SMS adds unacceptable latency for security events.
- Batching: none — Tier 1 notifications are never batched, never subject to quiet hours, and never suppressed by user preference.
- Volume: estimated <0.1% of total notification volume.

**Tier 1 rate limiting — the security-cost tension, stated explicitly:**

An earlier approach imposed a hard cap of 1,000 Tier 1 events/minute with a manual override requirement as a cost control mechanism. This was wrong. During a genuine large-scale security incident — credential stuffing affecting 50,000 accounts, for example — a 1,000/minute cap means it takes 50 minutes to emit all security notifications, during which affected users are not notified. That is not a cost control tradeoff; it is a security failure.

The tension is real: Tier 1 notifications are expensive (concurrent push + SMS + email), and a runaway process or large security incident can produce unexpected cost at scale. But the response cannot be a hard cap that throttles legitimate security notifications. The two underlying problems require different solutions:

**Problem 1: Runaway process emitting fraudulent Tier 1 events.** This is a correctness problem. The response is authorization controls at the event creation layer: only services with explicit Tier 1 emission authorization (identity service, fraud detection, payment service) can create Tier 1 events. This is enforced by the notification API, which validates the caller's service identity against an allowlist before accepting a Tier 1 event. An unauthorized service receives a rejection, not a queue position. This is described in §1.6.

**Problem 2: A genuine large-scale security incident producing high Tier 1 volume and unexpected cost.** This is a cost-visibility problem, not a throttling problem. The response is real-time cost alerting, not a delivery cap. An alert fires when Tier 1 volume exceeds 1,000 events/minute, paging the on-call engineer with current volume and projected cost. The on-call engineer can investigate and, if the volume is fraudulent, revoke the emitting service's Tier 1 authorization — which stops the fraudulent events without affecting legitimate ones. If the volume is legitimate (a real security incident), the engineer acknowledges the alert and the system continues delivering. No manual override is required to continue delivering legitimate security notifications.

**Tier 2 — Standard (real-time social events)**
- Examples: like, comment, new follower, mention, direct message
- Delivery target: first attempt within 5 minutes
- Channels: push (primary), in-app (always written, regardless of push status)
- Batching: applied when volume to a single user exceeds threshold; direct messages are excluded from batching by a mechanism described in §1.4
- Volume: estimated 85% of total notification volume

**Tier 3 — Digest (low-urgency, aggregated)**
- Examples: weekly summary, "you have 12 unread notifications," re-engagement nudges
- Delivery target: scheduled delivery within a defined window (e.g., 09:00–10:00 user local time)
- Channels: email (primary), in-app (secondary)
- Batching: always batched — individual digest items are never sent as individual notifications
- Volume: estimated 15% of total notification volume, concentrated at scheduled delivery times

---

### 1.4 Batching Logic

Batching serves two purposes: reducing notification fatigue for users who receive high volumes, and reducing load on downstream delivery infrastructure during spikes.

**Notification subtypes:**

Each notification carries two routing fields: `tier` (1, 2, or 3) and `subtype` (a string enum: `like`, `comment`, `follow`, `mention`, `direct_message`, `security`, `digest`, etc.). Batching and spike-exclusion logic operates on `subtype`, not only on `tier`. This is the architectural