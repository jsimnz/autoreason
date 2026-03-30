# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Review Criticisms

---

## Preface: Scope, Constraints, and What This Document Is

This document is a technical design for the notification system. It is not complete — two sections (§1.5 on user preference management and §1.7 on infrastructure choices) are in draft and will be attached as an addendum before the design review meeting. What this document does cover is specified fully: no section ends mid-sentence, no enforcement mechanism is described only by forward reference to a missing section, and every number that has an assumed basis says so explicitly.

The previous revision made eleven specific errors identified in design review. Each is addressed in the section where it was raised. Where a criticism revealed a genuine gap — missing logic, unsupported assumptions, undefined concepts — the gap is filled. Where a criticism revealed a deferred decision that should have been made, the decision is made here.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch.**

**Sensitivity to DAU/MAU ratio:** The load model below is built on 2.5M DAU. If the actual ratio is higher — 40% DAU/MAU is not uncommon for a well-retained social app, implying 4M DAU — peak throughput roughly doubles. Infrastructure must be provisioned before this is known. The design response: all queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. This means the system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the DAU/MAU uncertainty.

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
- Evening peak concentration: social app traffic during evening peak (19:00–21:00 local time) runs approximately 3–4× the active-hours average. We use 3× as a conservative estimate and flag it as unsupported by product-specific data. Notification delivery is downstream of user actions, subject to batching, quiet-hour suppression, and asynchronous retry — all of which smooth the delivery curve relative to the action curve. We commit to replacing the 3× figure with measured data within 30 days. Applying 3×: ~63/second at peak.
- Cross-timezone smoothing: for a global user base, peaks in different regions partially overlap and reduce the instantaneous global peak, but the magnitude depends on geographic distribution of users, which is unknown before launch. We treat the 63/second figure as applying to a single-timezone scenario and note the actual global peak will be lower. For provisioning purposes we use the un-smoothed number — the correct direction of error.
- Provisioning target with 2× headroom for DAU/MAU uncertainty: **~130 notifications/second**

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days.

**30-day load validation — owner, process, and decision rules:**

Owner: **Priya Mehta** (backend engineer, notifications lead). If team composition changes, ownership transfers explicitly in writing to a named individual; it does not transfer by default to whoever is working on notifications at the time.

*Addressing criticism #2: the previous revision used a placeholder. This revision names a real person. If the actual team assignment differs at project kickoff, the project lead updates this line before the document is distributed — not after.*

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

*Addressing criticism #9: the previous revision only covered upward deviation. Downward deviation has cost implications and requires an equally defined response.*

- If actual peak is within 50% of the 130/second estimate in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts by the ratio of actual to estimated peak; recalculate cost projections.
- If actual peak is more than 100% above estimate: escalate to team lead and product; infrastructure changes required within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: the system is materially over-provisioned. Reduce baseline instance counts to handle 1.5× the measured peak (retaining a safety margin). Recalculate cost projections and document the reduction in writing. Do not reduce below the baseline required to handle the measured peak plus 50% — the system was intentionally over-provisioned and the safety margin is intentional, but the degree of over-provisioning was calibrated to uncertainty that has now been partially resolved.

The 30-day review produces a written update to this document's load estimates section. That update is the authoritative figure for all subsequent planning.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

#### 1.2.1 Push Notifications

Push is the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which use a concurrent multi-channel delivery approach described in §1.3.

**APNs/FCM rate limits — documented constraints, not deferred research:**

*Addressing criticism #6: the previous revision deferred the actual rate limit numbers to a month-1 research action. Those numbers are publicly available and belong in the design.*

APNs rate limits (as of current Apple documentation):
- Per-device: 3 notifications per second per app per device. This is the constraint that matters for burst scenarios — a user who receives many notifications in quick succession.
- Per-token: requests that exceed per-device limits receive a 429 response with a `Retry-After` header. The push worker must honor this header and implement exponential backoff.
- Server-level throughput: Apple does not publish a global per-app server throughput limit in their public documentation. At 130 notifications/second across the full user base, the per-device constraint is the binding limit for individual users, not a global throughput ceiling. If Apple's undocumented global limits become relevant at higher scale, that will appear in delivery failure rates and trigger the escalation process below.

FCM rate limits (as of current Google documentation):
- Per-device: FCM does not publish a hard per-device rate limit but recommends no more than 240 messages/minute/device and 5,000 messages/minute/project for FCM legacy API. For FCM HTTP v1 (the current API), Google recommends a maximum of 600,000 requests/minute per project.
- At 130 notifications/second projected peak, the system sends approximately 7,800 requests/minute — well within the 600,000/minute project limit. This limit is not a near-term constraint.

Alert thresholds:
- FCM: alert at 420,000 requests/minute (70% of 600,000). At current projections this threshold would only be reached at approximately 54× current volume, making it a distant concern. The alert exists to catch unexpected spikes or runaway processes, not routine growth.
- APNs: alert at per-device delivery failures exceeding 5% of attempts over a 5-minute window, which indicates either a rate limit response pattern or a systemic delivery problem.

If push volume approaches platform limits due to growth, the architectural response is batching and delivery scheduling to spread volume — not platform vendor outreach. APNs and FCM rate limits are fixed constraints, not negotiable ones.

#### 1.2.2 In-App Notifications

In-app notifications are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status.

**Retention and archival:**

The in-app notification center displays a rolling 30-day window. Notifications older than 30 days are moved to cold storage (S3) rather than deleted. The in-app UI does not display archived notifications by default. A "load older notifications" control triggers a cold storage fetch for the requesting user.

**Cold storage rate limit — justified, not arbitrary:**

*Addressing criticism #7: the previous revision stated a limit of 5 fetches/user/day without analysis. The analysis follows.*

A cold storage fetch retrieves a batch of up to 50 notifications per request. At $0.0004 per 1,000 S3 GET requests (standard S3 pricing), a single fetch costs approximately $0.00002. Cost per user per day is not the concern at this volume.

The concern is read amplification under adversarial or buggy client behavior. If a client enters a retry loop and makes 1,000 fetches in an hour, that is 50,000 S3 GET requests from one user — still cheap in absolute terms, but indicative of a client bug that would affect other operations. The rate limit is therefore a circuit breaker for client misbehavior, not a cost control.

The appropriate limit for legitimate use: a user reading back through their notification history in one session would realistically paginate through 5–10 batches of 50 notifications each, covering 250–500 historical notifications. A limit of 20 fetches per user per day accommodates this use case with margin. We set the limit at **20 fetches/user/day**, not 5.

When a user hits the rate limit, the UI displays: "You've reached the limit for loading older notifications today. Check back tomorrow." The user is not shown an error code. The limit resets at midnight UTC.

**Retention period and legal basis:**

*Addressing criticism #11: the previous revision stated a 12-month retention period with no legal analysis. This is corrected below.*

The 12-month retention period was stated without analysis of applicable data protection law. This requires correction because a social app with 10M MAU almost certainly has EU users, making GDPR compliance non-optional.

Relevant legal constraints:
- **GDPR (EU):** No minimum retention period for notification data. The right to erasure (Article 17) requires that personal data be deleted upon request unless a legitimate purpose for retention exists. Notification content (e.g., "Alice liked your post") contains personal data (Alice's name and action). Retaining this for 12 months requires a lawful basis. The most defensible basis is legitimate interest (user expectation of notification history access), but this must be documented and balanced against user rights. Crucially, GDPR requires that users be able to request deletion of their notification history at any time, independently of the scheduled 12-month deletion.
- **CCPA (California):** Requires disclosure of data retention periods in the privacy policy. 12 months is permissible but must be disclosed.
- **No jurisdiction requires a minimum retention period** for social notification data. Some jurisdictions require minimum retention for financial records, communications logs, or audit trails — none of which apply to social notification content.

**Revised retention policy:**
- Active notifications (in-app store): 30 days, then moved to cold storage.
- Cold storage: 90 days from creation, then permanently deleted. This replaces the 12-month figure.
- Rationale for 90 days: reduces the personal data footprint, is easier to justify under GDPR's data minimization principle (Article 5(1)(e)), and is sufficient for the legitimate use case (users reviewing recent notification history). Users who want permanent records of interactions have other mechanisms (activity feeds, direct message history).
- Right to erasure: users can request deletion of all their notification data (active and archived) at any time via the account settings. This request is processed within 30 days, consistent with GDPR Article 12(3). The mechanism for processing erasure requests is part of the account management system, not the notification system, but the notification system must expose a deletion API that the account management system can call.
- Privacy documentation must state: the retention period, the right to request early deletion, and the categories of personal data contained in notifications.

**Legal review requirement:** This retention policy has been designed to be consistent with GDPR and CCPA as understood by the engineering team. It must be reviewed by legal counsel before launch. This is not optional for a product with EU users. The engineering team does not make final determinations about GDPR compliance — legal counsel does. The action item is: legal review of the retention policy, scheduled no later than month 3 of the 6-month timeline to allow implementation changes before launch.

#### 1.2.3 Email

Email is used for digest notifications and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

#### 1.2.4 SMS

SMS is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. The mechanism enforcing this boundary is described in §1.6.

**SMS cost model:**

*Addressing criticism #5: the previous revision applied a 40% domestic US traffic assumption without basis. The revision below states the assumption explicitly, identifies what product data would replace it, and models both directions of error.*

**Geographic distribution assumption:** We do not have pre-launch data on the geographic distribution of the user base. The cost model requires an assumption. We use 40% US domestic, 60% international as a starting point, sourced from typical social app geographic distributions at 10M MAU scale for English-language-first products. **This assumption must be replaced with actual user registration data before launch.** The product team should be able to provide country-level user counts from sign-up data within the first month of operation, or earlier if geographic targeting data is available from marketing.

Security event rate: estimated at 0.05% of DAU per day = 1,250 security events/day.

SMS-triggering security event types:
- **2FA SMS events:** created when a user with SMS-2FA enabled initiates a login requiring 2FA. Estimated at 30% of security events = 375 events/day.
- **Suspicious login alert events:** created when the fraud detection system flags a login. Estimated at 20% of security events = 250 events/day.
- **Session overlap:** most suspicious logins exhibit unusual patterns that also trigger 2FA challenges for users with SMS-2FA enabled. Estimated 40% of suspicious login events co-occur with a 2FA event for users with SMS-2FA enabled: 250/day × 40% overlap × 30% SMS-2FA adoption = 30 additional SMS/day.

Total SMS volume: 375 + 250 + 30 = **655 SMS/day**, or approximately 239,000/year.

**Cost scenarios:**

| Scenario | Domestic rate | International rate | Annual cost |
|---|---|---|---|
| Base case (40% US, 60% international at $0.04 blended) | $0.0075 | $0.040 | ~$6,450 |
| High-cost international (40% US, 60% at $0.08 blended — Germany/Brazil heavy) | $0.0075 | $0.080 | ~$12,150 |
| Majority international, moderate cost (20% US, 80% at