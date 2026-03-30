# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. The design is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch. The validation process and ownership are described in §1.8.**

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

Peak factor: social apps exhibit pronounced evening spikes (18:00–22:00 local time across timezones) and event-driven spikes from viral content. Peak-hour volume is estimated at 8–10× average hourly rate, yielding a sustained peak throughput requirement of roughly **200–250 notifications/second**, with brief spikes to 400/second across all queues combined.

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications (likes, comments, follows) because the cost of a missed like notification is low. We do not accept it for account security events (password changed, login from new device), which require a fallback channel.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status. The in-app notification center displays a rolling 30-day window; the archival behavior at that boundary is addressed in §1.9.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because mandatory push for all users would increase opt-out rates and reduce push effectiveness for users who want it.

**Email** is used for digest notifications (weekly activity summary, content the user missed) and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. This scope is deliberate and cost-bounded. If 5% of a 10M MAU base received one social SMS per week, that would be approximately 26M messages per year — at $0.01 minimum, $260,000/year before carrier surcharges. The cost estimate for security-only SMS is $5,000–15,000/year, based on security event rates well under 0.1% of DAU.

This estimate is only valid if the security-only scope is operationally enforced. The SMS worker rejects any notification not tagged with a security event subtype at the routing layer, enforced in code rather than policy. The specific controls protecting this boundary — including how they are tested and what alerts fire if they are violated — are described in §1.6 alongside the SMS worker implementation.

If a future product decision requires SMS for non-security events, it requires a separate cost analysis and explicit re-authorization before implementation.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. This is a first-attempt target, not a guaranteed end-to-end delivery SLA. Retry behavior after a failed first attempt is described in §1.7 and extends well beyond 60 seconds by design — the goal is eventual delivery, not abandonment after one attempt. These two properties are compatible.
- Channels: push (immediate), SMS (concurrent with push — not a sequential fallback, because waiting for push failure confirmation adds unacceptable latency for security events), email (concurrent). The cost exposure from concurrent multi-channel delivery is real: a spike in Tier 1 volume would trigger SMS to all affected users simultaneously. The controls preventing that exposure are described in §1.6.
- Batching: none — Tier 1 notifications are never batched, never subject to quiet hours, and never suppressed by user preference
- Volume: estimated <0.1% of total notification volume

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

If a user would receive more than **5 notifications of the same subtype within a 10-minute window**, subsequent notifications of that subtype are batched. The batch is held for **10 minutes from the first batched notification**, then delivered as a single notification: "You have 8 new likes on your post."

The 10-minute window and 5-notification threshold are configurable per subtype in service configuration. These are starting values based on industry convention, not empirical data from this product. They must be reviewed after 60 days of production data; the review process is described in §1.8.

**Spike batching (system-level):**

During periods when the Tier 2 standard queue depth exceeds a defined threshold (initially 500,000 queued messages, reviewed after 30 days per §1.8), the system automatically applies a 30-minute hold to Tier 2 standard notifications before delivery. The hold applies only to notifications where `subtype != direct_message`. Direct messages are routed to a dedicated `notifications-tier2-dm` queue and are not subject to spike batching regardless of overall queue depth. This is a firm product requirement enforced at the topic-routing layer, not a post-hoc filter.

*Tradeoff accepted:* Spike batching means a user might receive "you have 47 likes" 30 minutes after the likes occurred rather than individual near-real-time notifications. This is acceptable for social content. The cost of getting DM latency wrong is qualitatively different — it breaks conversational interaction — so the exclusion is architectural rather than configurable.

**Quiet hours and the thundering herd interaction:**

Users can specify a quiet-hours window during which push and SMS notifications are suppressed (see §1.5). Notifications held during quiet hours are released at the end of that window. If a meaningful fraction of users share the same quiet-hours end time — 08:00 local time is the obvious concentration point — the release creates a predictable daily spike that will itself trigger the spike batching mechanism, meaning users who configured quiet hours to receive undisturbed sleep will find their morning notifications delayed an additional 30 minutes by the spike their own quiet-hour release caused.

This interaction is addressed by staggering quiet-hours release rather than releasing all held notifications at the precise end-of-window moment. When a user's quiet window ends, their held notifications are placed into a release queue with a randomized jitter of 0–15 minutes added to the scheduled delivery time. The jitter is deterministic per user (derived from a hash of the user ID) so it is consistent across days — a given user always receives their morning notifications at, say, 08:07, not at a random time each day.

This does not eliminate the interaction entirely — a sufficiently large concentration of users with identical quiet windows will still produce a detectable spike — but it reduces the peak by roughly an order of magnitude and makes the spike gradual enough that auto-scaling can absorb it. The spike batching mechanism remains active as a backstop; the goal of jitter is to prevent it from triggering routinely.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job aggregates each user's unread activity using a **snapshot of read/unread state captured at job start time**. The snapshot timestamp is recorded and fixed for the entire run. All users in that run are evaluated against the same snapshot timestamp.

The snapshot timestamp is used as part of the idempotency key for each user's digest record: the key is `(user_id, snapshot_timestamp)`. If the job is interrupted and restarted, it resumes from the last committed user checkpoint and uses the original snapshot timestamp, ensuring no user receives a duplicate digest.

A notification received at 06:01 UTC will not appear in the current digest for any user, regardless of when during the run their digest is computed. This is a known and accepted boundary condition: the alternative — a live read of unread state during a multi-hour batch job — would produce inconsistent results across users and is operationally harder to reason about. A user who receives a late-night notification not captured in the morning digest will see it in the following day's digest. This is a known product behavior, not a system error, and should be reflected in user-facing documentation.

*Known limitation:* Timezone data in user profiles is self-reported and may be absent or incorrect. For users with no timezone data, delivery defaults to 09:00 UTC, which will be wrong for a large fraction of users. Improving this requires either requiring timezone at signup or inferring it from device locale — both are product decisions outside the scope of this document. The notification system will consume whatever timezone data is provided.

---

### 1.5 User Preference Management

Users can control notification delivery at three levels of granularity:

**Level 1 — Global channel preferences:** On/off per channel (push, email, SMS). Turning off a channel suppresses all notifications on that channel except Tier 1. Tier 1 notifications cannot be suppressed globally; this is a product safety decision, not a configurable option.

**Level 2 — Subtype preferences:** Per notification subtype, the user can set: all channels on, push only, email only, or off. The "off" setting suppresses the notification entirely except for Tier 1 subtypes, which cannot be set to off.

**Level 3 — Quiet hours:** The user specifies a time window (e.g., 22:00–08:00 in their timezone) during which push and SMS notifications are suppressed. Notifications that arrive during quiet hours are held and delivered at the end of the quiet window, subject to the jitter mechanism described in §1.4. Tier 1 notifications bypass quiet hours.

**Preference storage:**

User preferences are stored in the primary application database (PostgreSQL) as a JSON column on the user preferences table. At notification dispatch time, the notification service reads the user's preferences from a **Redis cache** (TTL: 5 minutes) before routing to delivery channels. Cache miss falls back to the database.

*Tradeoff accepted:* A 5-minute cache TTL means a user who changes their preferences may receive notifications on the old preference for up to 5 minutes. This is acceptable for routine preference changes.

**Cache invalidation: what it solves and what it doesn't:**

Two mechanisms reduce preference cache staleness below the 5-minute TTL for cases where staleness is not acceptable:

1. **Direct cache write on critical state changes:** When an account is suspended or deleted, the handling service writes the updated state directly to Redis synchronously, before returning. This closes the staleness window for those specific events: the cache entry reflects the new state as soon as the operation completes, not after a consumer processes an event. The tradeoff is that the writing service must have a direct Redis dependency, which is acceptable for the account management service but not appropriate as a general pattern.

2. **Cache invalidation events via `account-events` queue:** For preference changes that are not suspension or deletion, the preference service publishes an invalidation event to the `account-events` FIFO queue. Workers consume this event and evict the affected cache key. This reduces staleness for users who change preferences and then immediately trigger a notification — a common pattern when a user turns off notifications for a specific subtype because they are receiving too many. However, this mechanism is asynchronous: between the time the event is published and the time each worker processes it, those workers continue serving the stale cached preference. During consumer lag, this window could exceed the 5-minute TTL it was intended to improve.

The design accepts this residual window for non-critical preference changes. The practical consequence is that a user who turns off like notifications may receive one or two additional likes before the change propagates. This is a product experience issue, not a safety issue, and it is preferable to the operational complexity of synchronous cache invalidation across all workers for every preference change.

**Account deletion and in-flight messages:**

Account deletion is handled as an ordered sequence:

1. The account deletion event causes the account management service to write a deletion record to a `deleted_users` table in PostgreSQL and simultaneously write the deleted status directly to Redis (synchronous, not event-driven, as described above).
2. A `user.deleted` message is published to the `account-events` FIFO queue to ensure all workers eventually refresh their local state.
3. All delivery workers check deleted status before processing any notification, using a **Redis bloom filter as a fast-path negative check only**: a negative result (user not deleted) proceeds without a database lookup; a positive result triggers a definitive database lookup before dropping the notification. False positives in the bloom filter result in an extra database read, not in dropped notifications for live users. Because deletion writes directly to Redis synchronously in step 1, workers that have the old preference cached will find the deletion flag on their next Redis read for that user.
4. Notifications already in the queue for a deleted user are dropped at the worker layer when the worker checks deleted status before delivery.

There is still a window between when deletion is initiated and when the direct Redis write completes — a matter of milliseconds under normal conditions, potentially longer under Redis degradation. For account deletion, this window is acceptable. Blocking the queue until all in-flight messages are confirmed dropped is not feasible at this scale.

**Unsubscribe handling:**

Email unsubscribes are processed in real time — the unsubscribe link writes directly to the preference store — so regulatory deadlines (CAN-SPAM: 10 business days