# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. The design is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it, who owns that action, and what happens if it is not resolved.

**Document status:** This revision addresses eight design gaps identified in review: FIFO throughput capacity, Tier 1 cross-channel deduplication, bloom filter sizing, quiet-hours surge, preference cache invalidation boundaries, digest job staleness, invalid token handling, and application event log design. The infrastructure section, previously truncated, is complete in this revision.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch. The validation process, owner, and consequences of deviation are described in §1.8.**

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

Peak factor: social apps exhibit pronounced evening spikes (18:00–22:00 local time across timezones) and event-driven spikes from viral content. Peak-hour volume is estimated at 8–10× average hourly rate, yielding a sustained peak throughput requirement of roughly **200–250 notifications/second**, with brief spikes to 400/second.

An additional scheduled surge occurs at the end of quiet hours across major timezones. This surge is modeled separately in §1.4 because it is predictable and requires proactive scaling rather than reactive auto-scaling.

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications (likes, comments, follows) because the cost of a missed like notification is low. We do not accept it for account security events, which receive concurrent multi-channel delivery with cross-channel deduplication as described in §1.3.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status. Invalid push token handling and its relationship to in-app state are described in §1.7. The in-app notification center displays a rolling 30-day window; archival behavior at that boundary is described in §1.9.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because mandatory push for all users would increase opt-out rates and reduce push effectiveness for users who want it.

**Email** is used for digest notifications (weekly activity summary, content the user missed) and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications in low push-penetration markets. Cost basis and enforcement mechanism are described in §1.2.1 below.

**§1.2.1 SMS scope enforcement and cost basis**

If 5% of a 10M MAU base received one social SMS per week, that would be approximately 26M messages per year — at $0.01 minimum, $260,000/year before carrier surcharges. The cost estimate for security-only SMS is $5,000–15,000/year, based on security event rates well under 0.1% of DAU.

This estimate is only valid if the security-only scope is operationally enforced. The SMS delivery worker rejects any notification where `subtype` is not in the set `{two_factor_auth, suspicious_login, account_suspension, payment_failure}`. This check is in code, not policy documentation. Any expansion of the SMS subtype allowlist requires a code change, a cost analysis, and explicit sign-off from the engineering lead and product owner. This requirement is documented in the codebase as a comment adjacent to the allowlist definition, not only in this document.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. This is a first-attempt target, not a guaranteed end-to-end delivery SLA. Retry behavior after a failed first attempt is described in §1.7.
- Channels: push, SMS, and email fire concurrently — not sequentially — because waiting for push failure confirmation before initiating SMS adds unacceptable latency for security events. Cross-channel deduplication is handled as described in §1.3.1 below.
- Batching: none. Tier 1 notifications are never batched, never subject to quiet hours, and never suppressed by user preference.
- Volume: estimated <0.1% of total notification volume.

**§1.3.1 Tier 1 cross-channel deduplication**

When push, SMS, and email fire concurrently for a Tier 1 event, the user will receive all three if all three succeed. For security events, this is a deliberate product decision with a specific rationale: a user who receives a "login from new device" alert on three channels simultaneously is more likely to take action than one who receives it on one channel. The redundancy is a feature, not a defect. This decision must be documented in product requirements, not assumed from the technical design.

However, the notification text must be written to make concurrent multi-channel delivery non-alarming. The push notification reads: "Security alert: new login detected. Check your email for details." The SMS reads: "Security alert from [App]. Check your email or app." The email contains the full detail. This framing prevents three identical simultaneous alerts from reading as three separate incidents.

For the subset of Tier 1 events where receiving three alerts is genuinely problematic — for example, a two-factor authentication code, where SMS is the intended channel and push/email would be redundant — the notification subtype carries a `preferred_channel` field. When `preferred_channel` is set, the other channels are suppressed unless the preferred channel fails after two retry attempts. The retry window for preferred-channel failure before fallback activation is 90 seconds, configurable per subtype. Two-factor auth codes set `preferred_channel: sms`.

This design avoids a synchronization problem: if channels checked each other's delivery status before sending, the coordination overhead and failure modes of that check would undermine the latency goal. Instead, the design separates the cases: most Tier 1 events send on all channels by design; the small subset where channel preference matters uses the `preferred_channel` mechanism with a defined fallback window.

**Tier 2 — Standard (real-time social events)**
- Examples: like, comment, new follower, mention, direct message
- Delivery target: first attempt within 5 minutes
- Channels: push (primary), in-app (always written, regardless of push status)
- Batching: applied when volume to a single user exceeds threshold; direct messages are excluded from batching as described in §1.4
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

Each notification carries two routing fields: `tier` (1, 2, or 3) and `subtype` (a string enum: `like`, `comment`, `follow`, `mention`, `direct_message`, `security`, `digest`, etc.). Batching and exclusion logic operates on `subtype`, not only on `tier`. This is the architectural mechanism that allows direct messages to be excluded from spike batching while remaining Tier 2: the spike batching rule checks `subtype != direct_message` before applying the hold. The `subtype` field is set at notification creation and is immutable.

**Per-user batching threshold (Tier 2, non-DM subtypes):**

If a user would receive more than 5 notifications of the same subtype within a 10-minute window, subsequent notifications of that subtype are batched. The batch is held for 10 minutes from the first batched notification, then delivered as a single notification: "You have 8 new likes on your post."

The 10-minute window and 5-notification threshold are configurable per subtype in service configuration. These are starting values based on industry convention, not empirical data from this product. They must be reviewed by [**Owner: backend lead**] after 60 days of production data using the process described in §1.8.

**Spike batching (system-level):**

During periods when the Tier 2 standard queue depth exceeds 500,000 queued messages, the system automatically applies a 30-minute hold to Tier 2 standard notifications before delivery. The hold applies only to notifications where `subtype != direct_message`. Direct messages are routed to a dedicated `notifications-tier2-dm` queue and are not subject to spike batching regardless of overall queue depth.

The 500,000-message threshold is an initial value, not a validated operating point. It must be reviewed by [**Owner: backend lead**] after 30 days of production data.

**Quiet-hours release surge:**

Quiet hours create a predictable, scheduled surge that is qualitatively different from organic or viral spikes. When a user's quiet window ends, all held notifications are released at once. Across a large user base, users in the same timezone with the same quiet-hours setting (the default 22:00–08:00 is explicitly suggested in the UI) will release simultaneously.

Estimating the surge: if 20% of DAU (500,000 users) have quiet hours enabled, and 60% of those share a timezone cluster (e.g., US Eastern), that is 300,000 users releasing held notifications at approximately 08:00 Eastern. If each user held an average of 3 notifications, the surge is 900,000 messages delivered within a short window — roughly 2–3× the average hourly rate, potentially coinciding with the morning organic spike.

The system handles this through two mechanisms:

1. **Pre-warming:** A scheduled Lambda function runs 10 minutes before each major quiet-hours release window (identified by timezone cluster size — initially US Eastern, US Pacific, UK, and Central European time) and scales the push worker pool to 2× its current capacity. The scale-up completes before the surge arrives. This is proactive rather than reactive.

2. **Staggered release:** Rather than releasing all held notifications for a timezone cluster at the exact quiet-hours boundary, the notification scheduler adds a uniformly distributed random jitter of 0–15 minutes per user. A user whose quiet hours end at 08:00 receives their held notifications at a random time between 08:00 and 08:15. This reduces the instantaneous peak by approximately 75% while keeping delivery within a window users will not notice.

The jitter is applied at release scheduling time, not at delivery time, so it is deterministic per user per quiet-hours cycle and does not affect retry logic.

*Tradeoff accepted:* Staggered release means some users receive held notifications up to 15 minutes after their quiet window ends. This is acceptable; the alternative is a predictable infrastructure failure on a daily schedule.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job takes a snapshot of read/unread state at start time and records the snapshot timestamp. Notifications received after the snapshot timestamp are not included in the current digest run; they appear in the next day's digest.

**Digest job staleness by processing order:**

The digest job processes users sequentially. At 10M MAU, even with aggressive optimization, the job runs for several hours. A user processed in hour four of the job receives a digest reflecting state from approximately 10:00 UTC, but the snapshot was taken at 06:00 UTC — a four-hour staleness gap. This gap is not uniform across users; it grows proportionally with processing order.

This is a structural property of the design, not an edge case. It is accepted on the following basis: digest notifications are explicitly low-urgency content. A user who receives a digest at 14:00 local time showing activity through 06:00 UTC is receiving a summary, not a real-time feed. The four-hour potential staleness is within the expected tolerance for a digest channel.

However, the design mitigates the worst cases through two mechanisms:

1. **Processing order is randomized per run**, not deterministic. Users are not always processed last. Over multiple days, each user experiences a distribution of processing positions rather than always being at the end of the queue. This does not eliminate staleness but prevents any user from systematically receiving the stalest digests.

2. **The digest email includes an explicit timestamp:** "Activity through [time] UTC." Users are not misled into believing the digest is current. This is a product requirement enforced at the template layer.

*Known limitation:* Timezone data in user profiles is self-reported and may be absent or incorrect. For users with no timezone data, delivery defaults to 09:00 UTC. Improving this requires either requiring timezone at signup or inferring it from device locale — both are product decisions outside this document's scope. The notification system will consume whatever timezone data is provided. [**Owner: product team to decide and communicate to backend lead within 60 days of launch.**]

---

### 1.5 User Preference Management

Users can control notification delivery at three levels of granularity:

**Level 1 — Global channel preferences:** On/off per channel (push, email, SMS). Turning off a channel suppresses all notifications on that channel except Tier 1. Tier 1 notifications cannot be suppressed globally.

**Level 2 — Subtype preferences:** Per notification subtype, the user can set: all channels on, push only, email only, or off. The "off" setting suppresses the notification entirely except for Tier 1 subtypes, which cannot be set to off.

**Level 3 — Quiet hours:** The user specifies a time window during which push and SMS notifications are suppressed. Notifications that arrive during quiet hours are held and delivered at the end of the quiet window with jitter applied as described in §1.4. Tier 1 notifications bypass quiet hours.

**Preference storage:**

User preferences are stored in PostgreSQL as a JSON column on the user preferences table. At notification dispatch time, the notification service reads preferences from a Redis cache (TTL: 5 minutes) before routing to delivery channels. Cache miss falls back to the database.

**Preference cache invalidation boundaries:**

The 5-minute TTL is appropriate for most preference changes. The following specific changes trigger an immediate cache invalidation event published to the `account-events` queue, bypassing the TTL:

- Global push disabled (user explicitly turning off all push)
- Global SMS disabled