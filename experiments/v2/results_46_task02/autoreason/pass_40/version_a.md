# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. The design is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch.** The validation process is described in §1.8.

**Sensitivity to DAU/MAU ratio:** The load model below is built on 2.5M DAU. If the actual ratio is higher — 40% DAU/MAU is not uncommon for a well-retained social app, implying 4M DAU — peak throughput roughly doubles. Infrastructure must be provisioned before this is known. The design response to this uncertainty is explicit: all queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. This means the system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the DAU/MAU uncertainty.

Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes for standard instance types, but this is not guaranteed under all conditions. Baseline instance counts therefore affect how much burst capacity is available before scaling kicks in — the baseline is not set at the minimum viable count. If actual DAU/MAU exceeds 40% before the 30-day mark, the on-call engineer escalates immediately by manually increasing the auto-scaling ceiling, which takes minutes, not days. The 30-day review determines whether the elevated baseline should become the new permanent baseline or whether costs can be reduced.

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

The peak factor is derived explicitly rather than stated as a fixed multiplier:

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Peak hour concentration: social app traffic during evening peak (19:00–21:00 local time) runs approximately 3–4× the daytime average, based on published traffic patterns from comparable consumer apps (Twitter's documented peak/average ratio of approximately 3:1 for notification volume). Applying a 3.5× multiplier: ~74/second at peak
- Cross-timezone smoothing: for a global user base, peak hours in different regions partially overlap, reducing the instantaneous global peak. The smoothing factor is estimated at 0.6× — meaning the global peak is approximately 60% of what it would be if all users were in one timezone. Adjusted sustained peak: ~120/second

The 8× ratio of peak to 24-hour average (120/15 ≈ 8) is an output of this derivation, not an independent input. It is stated here so it can be challenged if the assumptions are wrong.

- Provisioning target with 2× headroom for DAU/MAU uncertainty: **~240 notifications/second**

Brief spikes above the sustained peak are handled by queue buffering, not by provisioning for the instantaneous spike ceiling. These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications because the cost of a missed like notification is low. We do not accept it for account security events, which require a fallback channel.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status. The in-app notification center displays a rolling 30-day window; archival behavior at that boundary is addressed in §1.9.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because mandatory push for all users would increase opt-out rates and reduce push effectiveness for users who want it.

**Email** is used for digest notifications and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. This scope is deliberate and cost-bounded.

**SMS cost model:**

Security event rate: estimated at 0.05% of DAU per day (0.05% of 2.5M DAU = 1,250 security events/day). Not all security events require SMS — 2FA codes require SMS only when the user has SMS-2FA enabled, estimated at 30% of users who trigger a security event. Suspicious login alerts go to all users triggering that event type, estimated at 20% of security events. Combined SMS-triggering security events: approximately 625/day, or ~228,000/year.

Domestic SMS rate (US): $0.0075/message (Twilio standard, 2024). International rates vary widely: UK ~$0.04, India ~$0.009, Brazil ~$0.075, Germany ~$0.09. For a global social app, assuming 40% domestic US traffic and 60% international at a blended international rate of $0.04/message:

- Domestic: 228,000 × 0.40 × $0.0075 = ~$684/year
- International: 228,000 × 0.60 × $0.04 = ~$5,472/year
- **Total: ~$6,200/year**

Sensitivity: if international traffic is skewed toward high-cost markets (Germany, Brazil), the total reaches $12,000–18,000/year. If the product expands to high-cost SMS markets as the primary user base, this range must be recalculated before launch in those markets.

This estimate is only valid if the security-only scope is operationally enforced. The SMS worker rejects any notification not tagged with a security event subtype at the routing layer, enforced in code rather than policy. The specific controls protecting this boundary are described in §1.6.

If a future product decision requires SMS for non-security events, it requires a separate cost analysis and explicit re-authorization before implementation.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. This is a first-attempt target, not a guaranteed end-to-end delivery SLA. Retry behavior after a failed first attempt extends well beyond 60 seconds by design — the goal is eventual delivery, not abandonment after one attempt. These two properties are compatible.
- Channels: push, SMS, and email delivered concurrently — not sequentially. Waiting for push failure confirmation before sending SMS adds unacceptable latency for security events.
- Batching: none — Tier 1 notifications are never batched, never subject to quiet hours, and never suppressed by user preference
- Volume: estimated <0.1% of total notification volume

The cost exposure from concurrent multi-channel delivery is real. If a security incident caused 100,000 users to simultaneously receive Tier 1 events, the SMS cost alone would be ~$750 domestic / ~$4,000 internationally in a single incident. The controls bounding this exposure: (a) rate limiting on Tier 1 event creation at the API layer — no single service can emit more than 1,000 Tier 1 events per minute without triggering an alert and requiring manual override, and (b) the Tier 1 queue has a configurable maximum-depth alarm at 50,000 messages, which pages the on-call engineer before the queue reaches a volume that would produce material unexpected cost. These controls are described in full in §1.6.

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

Each notification carries two routing fields: `tier` (1, 2, or 3) and `subtype` (a string enum: `like`, `comment`, `follow`, `mention`, `direct_message`, `security`, `digest`, etc.). Batching and spike-exclusion logic operates on `subtype`, not only on `tier`. This is the architectural mechanism that allows direct messages to be excluded from spike batching while remaining Tier 2: the spike batching rule checks `subtype != direct_message` before applying the hold. The `subtype` field is set at notification creation and is immutable.

**Per-user batching threshold (Tier 2, non-DM subtypes):**

If a user would receive more than 5 notifications of the same subtype within a 10-minute window, subsequent notifications of that subtype are batched. The batch is held for 10 minutes from the first batched notification, then delivered as a single notification: "You have 8 new likes on your post."

The 5-notification threshold and 10-minute window are configurable per subtype in service configuration. These are starting values — they are not derived from empirical data for this product, and that is an acknowledged gap. The owner of the 60-day review of these values is the backend engineer designated to the notifications team at project kickoff; if the team rotates, the designation transfers explicitly. The review is not optional if product metrics show notification opt-out rates increasing in the first 60 days — in that case it is escalated immediately rather than deferred to the scheduled review. The review process is described in §1.8.

**Spike batching (system-level):**

During periods when the Tier 2 standard queue depth exceeds 500,000 queued messages, the system automatically applies a 30-minute hold to Tier 2 standard notifications before delivery. The hold applies only to notifications where `subtype != direct_message`.

*Tradeoff accepted:* Spike batching means a user might receive "you have 47 likes" 30 minutes after the likes occurred rather than individual near-real-time notifications. This is acceptable for social content. The cost of getting DM latency wrong is qualitatively different — it breaks conversational interaction — so the exclusion is architectural rather than configurable.

**Direct message queue isolation — what it does and does not solve:**

DMs are routed to a dedicated `notifications-tier2-dm` queue and excluded from spike batching. This prevents spike batching from introducing DM delivery delay. It does not, by itself, prevent DM latency degradation caused by resource contention on shared infrastructure.

To address this: DM delivery workers are a separate worker pool, not merely a separate queue consumed by shared workers. The DM worker pool has dedicated auto-scaling configuration with more aggressive scale-out triggers (described in §1.6) and dedicated Redis connection pool limits so that cache saturation from non-DM traffic does not crowd out DM lookups. APNs/FCM connections are managed per worker pool, so DM workers maintain their own connection pool and are not competing with standard Tier 2 workers for connection slots.

What remains shared: APNs and FCM rate-limit by app credential, not by our worker pool. If overall push volume approaches APNs/FCM rate limits, DMs will be affected along with everything else. The design's response to this is not to treat monitoring as sufficient mitigation: the team lead contacts APNs and FCM developer relations in month 1 to document current limits and request information on the increase process. This is a named pre-launch dependency, not a reactive one. Monitoring alerts fire before rate limits are reached so that the team has lead time to act; the specific alert thresholds are defined in §1.6.

**Quiet hours and the thundering herd:**

Users can specify a quiet-hours window during which push and SMS notifications are suppressed. Notifications held during quiet hours are released at the end of that window. If a meaningful fraction of users share the same quiet-hours end time — 08:00 local time is the obvious concentration point — the release creates a predictable daily spike.

This is addressed by staggering quiet-hours release with a randomized jitter of 0–15 minutes added to the scheduled delivery time. The jitter is deterministic per user (derived from a hash of the user ID) so it is consistent across days — a given user always receives their morning notifications at, say, 08:07, not at a random time each day. Hash-based jitter does not guarantee perfectly uniform distribution, but for user ID spaces of millions the distribution is close enough to uniform that the peak reduction is approximately 10–14× rather than the theoretical 15×. This is meaningful.

**What jitter does and does not guarantee:**

Jitter reduces instantaneous peak rate by spreading a concentrated release across a 15-minute window. It does not reduce total notification volume delivered during that window. The document's own numbers show that jitter alone does not prevent spike batching from triggering during the morning release window: for a 10M MAU base, if 10% of users set quiet hours ending at 08:00 (1M users) with an average of 3 held notifications each, that is 3M messages over 15 minutes — roughly 3,300/second sustained, well above the spike batching threshold of 500,000 queued messages.

The design's honest position: jitter eliminates the instantaneous burst that would occur without it and handles the common case where quiet-hour concentration is moderate. It does not prevent spike batching from triggering during the morning release window if quiet-hour adoption is high and concentrated. The spike batching mechanism is explicitly the backstop for this case.

Users who configure quiet hours should expect that their morning release may be subject to an additional 30-minute delay during high-traffic periods. This behavior is documented in the user-facing preference UI — not buried in internal documentation — so users who configure quiet hours understand the tradeoff they are accepting. The alternative — guaranteeing exact quiet-hour end delivery regardless of system load — would require dedicated per-user scheduled jobs, which is not feasible at this scale with this team.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job aggregates each user's unread activity using a snapshot of read/unread state captured at job start time. A notification received at 