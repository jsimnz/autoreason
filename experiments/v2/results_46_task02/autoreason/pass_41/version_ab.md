# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch.** Validation ownership and the process that turns findings into decisions are described at the end of this section.

**Sensitivity to DAU/MAU ratio:** The load model is built on 2.5M DAU. If the actual ratio is higher — 40% DAU/MAU is not uncommon for a well-retained social app, implying 4M DAU — peak throughput roughly doubles. Infrastructure must be provisioned before this is known. The design response: all queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. This means the system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the DAU/MAU uncertainty.

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

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Evening peak concentration: social app traffic during evening peak (19:00–21:00 local time) runs approximately 3–4× the active-hours average. We use 3× as a conservative estimate and flag it as unsupported by product-specific data. This multiplier is not borrowed from action-volume ratios (tweet creation, API requests) — notification delivery is downstream of user actions, subject to batching, quiet-hour suppression, and asynchronous retry, all of which smooth the delivery curve relative to the action curve. Using action-volume peak ratios to model delivery-volume ratios introduces unquantified error. We commit to replacing the 3× figure with measured data within 30 days. Applying 3×: ~63/second at peak.
- Cross-timezone smoothing: for a global user base, peaks in different regions partially overlap and reduce the instantaneous global peak, but the magnitude depends on geographic distribution of users, which is unknown before launch. We treat the 63/second figure as applying to a single-timezone scenario; the actual global peak will be lower. For provisioning purposes we use the un-smoothed number — the correct direction of error.
- Provisioning target with 2× headroom for DAU/MAU uncertainty: **~130 notifications/second**

Brief spikes above the sustained peak are handled by queue buffering, not by provisioning for the instantaneous spike ceiling. These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days.

**30-day load validation — owner, process, and decision rules:**

Owner: **Priya Mehta** (backend engineer, notifications lead). If team composition differs at project kickoff, the project lead updates this line before the document is distributed. If team composition changes after kickoff, ownership transfers explicitly in writing to a named individual — it does not transfer by default to whoever is working on notifications at the time.

Required instrumentation, in place before launch:
- Per-second notification creation rate, broken down by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

Review trigger: the 30-day review is not optional. It occurs on day 30 regardless of whether anything appears wrong. It is also triggered immediately — not deferred — if any of the following are observed before day 30:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%

**Decision rules at review — including downward deviation:**

- If actual peak is within 50% of the 130/second estimate in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts by the ratio of actual to estimated peak; recalculate cost projections.
- If actual peak is more than 100% above estimate: escalate to team lead and product; infrastructure changes required within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: the system is materially over-provisioned. Reduce baseline instance counts to handle 1.5× the measured peak, retaining a safety margin. Recalculate cost projections and document the reduction in writing. Do not reduce below 1.5× the measured peak — the safety margin is intentional, but the degree of over-provisioning was calibrated to uncertainty that has now been partially resolved.

The 30-day review produces a written update to this document's load estimates section. That update is the authoritative figure for all subsequent planning.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

#### 1.2.1 Push Notifications

Push is the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which use concurrent multi-channel delivery described in §1.3.

**APNs/FCM rate limits — permanent architectural constraints, not negotiating positions:**

APNs and FCM rate limits are platform-level constraints. Apple and Google do not negotiate per-app rate limit increases through developer relations. The correct framing: these are fixed constraints the system must operate within, not temporary blockers resolvable through outreach.

APNs rate limits (current Apple documentation):
- Per-device: 3 notifications per second per app per device. This is the binding constraint for users who receive many notifications in quick succession.
- Requests exceeding per-device limits receive a 429 response with a `Retry-After` header. The push worker must honor this header and implement exponential backoff.
- Apple does not publish a global per-app server throughput limit. At 130 notifications/second across the full user base, the per-device constraint is the binding limit for individual users, not a global throughput ceiling. If Apple's undocumented global limits become relevant at higher scale, that will appear in delivery failure rates and trigger the escalation process below.

FCM rate limits (current Google documentation):
- FCM HTTP v1 (current API): maximum 600,000 requests/minute per project.
- At 130 notifications/second projected peak, the system sends approximately 7,800 requests/minute — well within the 600,000/minute limit. This is not a near-term constraint.

Alert thresholds:
- FCM: alert at 420,000 requests/minute (70% of limit). At current projections this threshold would only be reached at approximately 54× current volume, making it a distant concern for routine growth. The alert exists to catch unexpected spikes or runaway processes.
- APNs: alert at per-device delivery failures exceeding 5% of attempts over a 5-minute window, indicating either a rate limit response pattern or a systemic delivery problem.

If push volume approaches platform limits due to growth, the architectural response is batching and delivery scheduling to spread volume — not platform vendor outreach. The notifications lead reviews both platforms' current public rate limit documentation in month 1 to establish actual ceilings and configure alert thresholds. This is an information-gathering action with a defined owner, not an open dependency.

#### 1.2.2 In-App Notifications

In-app notifications are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status.

**Retention and archival:**

The in-app notification center displays a rolling 30-day window. Notifications older than 30 days are moved to cold storage (S3) rather than deleted. The in-app UI does not display archived notifications by default. A "load older notifications" control triggers a cold storage fetch for the requesting user.

*Tradeoff accepted:* Cold storage fetch adds latency for historical notification access. This is acceptable because users reading notifications more than 30 days old is a low-frequency use case. The alternative — keeping all notifications in the primary store — would increase primary store size by approximately 12× for active users and degrade query performance for the common case.

**Cold storage rate limit — justified, not arbitrary:**

A cold storage fetch retrieves a batch of up to 50 notifications per request. At $0.0004 per 1,000 S3 GET requests, a single fetch costs approximately $0.00002. Cost per user per day is not the concern at this volume.

The concern is read amplification under adversarial or buggy client behavior. A client in a retry loop making 1,000 fetches per hour generates 50,000 S3 GET requests — still cheap in absolute terms, but indicative of a client bug that would affect other operations. The rate limit is a circuit breaker for client misbehavior, not a cost control.

A user reading back through notification history in one session would realistically paginate through 5–10 batches of 50 notifications, covering 250–500 historical notifications. A limit of **20 fetches/user/day** accommodates this use case with margin. When a user hits the limit, the UI displays: "You've reached the limit for loading older notifications today. Check back tomorrow." No error code is shown. The limit resets at midnight UTC.

**Retention period and legal basis:**

The in-app store retains notifications for 30 days. Cold storage retains notifications for **90 days from creation**, then permanently deletes them.

*Why 90 days, not 12 months:* A social app with 10M MAU almost certainly has EU users, making GDPR compliance non-optional. Notification content (e.g., "Alice liked your post") contains personal data. The 90-day figure reduces the personal data footprint and is easier to justify under GDPR's data minimization principle (Article 5(1)(e)) than 12 months. It is sufficient for the legitimate use case — users reviewing recent notification history — while users who want permanent records of interactions have other mechanisms (activity feeds, direct message history).

Relevant legal constraints:
- **GDPR (EU):** No minimum retention period for notification data. The right to erasure (Article 17) requires personal data be deleted upon request unless a legitimate purpose for retention exists. The most defensible basis for retaining notification data is legitimate interest (user expectation of notification history access), but this must be documented and balanced against user rights. Users must be able to request deletion of their notification history at any time, independently of the scheduled 90-day deletion.
- **CCPA (California):** Requires disclosure of data retention periods in the privacy policy. 90 days is permissible but must be disclosed.

Right to erasure: users can request deletion of all their notification data (active and archived) at any time via account settings. This request is processed within 30 days, consistent with GDPR Article 12(3). The notification system must expose a deletion API that the account management system can call; the deletion workflow itself lives in account management.

Privacy documentation must state: the retention period, the right to request early deletion, and the categories of personal data contained in notifications.

**Legal review requirement:** This retention policy has been designed to be consistent with GDPR and CCPA as understood by the engineering team. It must be reviewed by legal counsel before launch — this is not optional for a product with EU users. The engineering team does not make final determinations about GDPR compliance. Action item: legal review of the retention policy scheduled no later than month 3 of the 6-month timeline, to allow implementation changes before launch.

#### 1.2.3 Email

Email is used for digest notifications and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

#### 1.2.4 SMS

SMS is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. This scope is deliberate and cost-bounded. The mechanism enforcing this boundary is described in §1.6.

**SMS cost model:**

*Geographic distribution assumption:* We do not have pre-launch data on user geographic distribution. The cost model requires an assumption. We use 40% US domestic, 60% international, sourced from typical social app geographic distributions at 10M MAU scale for English-language-first products. **This assumption must be replaced with actual user registration data before launch** — the product team should be able to provide country-level user counts from sign-up data within the first month of operation.

Security event rate: estimated at 0.05% of DAU per day = 1,250 security events/day.

SMS-triggering security event types are defined at the event level, not the session level. A single login session can trigger both a 2FA SMS and a suspicious login alert, producing two separate SMS messages — one for each event type, because they serve different purposes (authentication vs. alert). The cost model counts both.

- **2FA SMS events:** created when a user with SMS-2FA enabled initiates a login requiring 2FA. Estimated at 30% of security events = 375 events/day.
- **Suspicious login alert events:** created when the fraud detection system flags a login. Estimated at 20% of security events = 250 events/day.
- **Session overlap:** most suspicious logins also trigger 2FA challenges for users with SMS-2FA enabled. Estimated 40% of suspicious login events co-occur with a 2FA event for users with SMS-2FA enabled: 250/day × 40% overlap × 30% SMS-2FA adoption = 30 additional SMS/day.

Total SMS volume: 375 + 250 + 30 = **655 SMS/day**, approximately 239,000/year.

**Cost scenarios:**

| Scenario | Domestic rate | International blended rate | Annual cost |
|---|---|---|---|
| Base case (40% US, 60% international) | $0.0075 | $0.040 | ~$6,450 |
| High-cost international (Germany/Brazil heavy) | $0.0075 | $0.080 | ~$12,150 |
| Majority international, moderate cost (20% US, 80% at $0.04) | $0.0075 | $0.040 | ~$8,010 |

The base case blended international rate of $0.04 reflects UK (~$0.04), India (~$0.009), Brazil (~$0.075), Germany (~$0.09) weighted by typical social app geographic distribution. If the user base is skewed toward high-cost markets, the international