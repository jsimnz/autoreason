# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and What Changed

This revision addresses ten specific problems identified in the prior draft. Each section notes what changed and why. Where a problem cannot be fully resolved within this design's scope, the limitation is stated explicitly along with the action required to resolve it.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch. The process for doing so is described in §1.8.**

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

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications (likes, comments, follows) because the cost of a missed like notification is low. We do not accept it for account security events (password changed, login from new device), which require a fallback channel.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status. The in-app notification center displays a rolling 30-day window of notifications; the behavior at that boundary is addressed in §1.9.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because mandatory push for all users would increase opt-out rates and reduce push effectiveness for users who want it.

**Email** is used for digest notifications (weekly activity summary, content the user missed) and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

*Tradeoff accepted:* Email has the highest deliverability for inactive users but the lowest engagement for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is **not** used for social notifications in low push-penetration markets.

The prior draft stated SMS would serve "users in markets where push penetration is low." That scope was removed because it is not cost-bounded. If 5% of a 10M MAU base receives one social SMS per week, that is approximately 26M messages per year at $0.01 minimum — $260,000/year — before any carrier surcharges. The revised cost estimate for security-only SMS is $5,000–15,000/year, based on security event rates well under 0.1% of DAU. This estimate is only valid if the security-only scope is operationally enforced, which it is: the SMS worker rejects any notification not tagged with a security event type at the routing layer.

If a future product decision requires SMS for non-security events, it requires a separate cost analysis and explicit re-authorization before implementation.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. **This is a first-attempt target, not a guaranteed end-to-end delivery SLA.** Retry behavior after a failed first attempt is described in §1.7. The retry schedule extends beyond 60 seconds by design — the goal is eventual delivery, not abandonment after one attempt. These two properties are compatible and are not in conflict.
- Channels: push (immediate), SMS (immediate, concurrent with push — not a fallback after push fails, because waiting for push failure confirmation would add unacceptable latency for security events), email (concurrent)
- Batching: none — Tier 1 notifications are never batched
- Volume: estimated <0.1% of total notification volume

**Tier 2 — Standard (real-time social events)**
- Examples: like, comment, new follower, mention, direct message
- Delivery target: first attempt within 5 minutes
- Channels: push (primary), in-app (always written, regardless of push status)
- Batching: applied when volume to a single user exceeds threshold (see §1.4); direct messages are excluded from batching by a mechanism described in §1.4
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

The 10-minute window and 5-notification threshold are configurable per subtype in service configuration. These are starting values based on industry convention, not empirical data from this product. Review process is described in §1.8.

**Spike batching (system-level):**

During periods when the Tier 2 queue depth exceeds a defined threshold (initially set at 500,000 queued messages), the system automatically applies a 30-minute hold to Tier 2 notifications before delivery. The hold applies only to notifications where `subtype != direct_message`. Direct messages are routed to a dedicated `notifications.tier2.dm` topic and are not subject to spike batching regardless of overall queue depth.

*Tradeoff accepted:* Spike batching means a user might receive "you have 47 likes" 30 minutes after the likes occurred rather than individual near-real-time notifications. This is acceptable for social content. The DM exclusion is a firm product requirement, not a best-effort behavior, and is enforced at the topic-routing layer, not as a post-hoc filter.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job aggregates each user's unread activity using a **snapshot of read/unread state captured at job start time**. The snapshot timestamp is recorded; notifications received after the snapshot timestamp are not included in the current digest run regardless of when they are read. This means a notification received at 06:01 UTC will appear in the next day's digest, not the current one. This is a known and accepted boundary condition: the alternative — a live read of unread state during a multi-hour batch job — would produce inconsistent results across users and is worse.

The job processes users in deterministic order. If the job is interrupted and restarted, it resumes from the last committed user checkpoint rather than reprocessing from the beginning. Each user's digest is written with the snapshot timestamp as an idempotency key, so a restarted job does not send duplicate digests.

Delivery is scheduled for the user's local morning window using timezone data from the user profile.

*Known limitation:* Timezone data in user profiles is self-reported and may be absent or incorrect. For users with no timezone data, delivery defaults to 09:00 UTC. Improving this requires either requiring timezone at signup (a product decision) or inferring timezone from device locale (requires product work). This is a product team decision; the notification system will consume whatever timezone data is available.

---

### 1.5 User Preference Management

Users can control notification delivery at three levels of granularity:

**Level 1 — Global channel preferences:** On/off per channel (push, email, SMS). Turning off a channel suppresses all notifications on that channel except Tier 1. Tier 1 notifications cannot be suppressed globally; this is a product safety decision, not a configurable option.

**Level 2 — Type preferences:** Per notification subtype, the user can set: all channels on, push only, email only, or off. The "off" setting suppresses the notification entirely except for Tier 1 subtypes, which cannot be set to off.

**Level 3 — Quiet hours:** The user specifies a time window (e.g., 22:00–08:00 in their timezone) during which push and SMS notifications are suppressed. Notifications that arrive during quiet hours are held and delivered at the end of the quiet window. Tier 1 notifications bypass quiet hours.

**Preference storage:**

User preferences are stored in the primary application database (PostgreSQL) as a JSON column on the user preferences table. At notification dispatch time, the notification service reads the user's preferences from a **Redis cache** (TTL: 5 minutes) before routing to delivery channels. Cache miss falls back to the database.

*Tradeoff accepted:* A 5-minute cache TTL means a user who changes their preferences may continue to receive notifications on the old preference for up to 5 minutes. This is acceptable for routine preference changes.

**Account deletion and in-flight messages:**

Account deletion is handled as an ordered sequence, not a single atomic operation:

1. The account deletion event publishes a `user.deleted` message to a dedicated `account_events` topic.
2. The notification service consumes `user.deleted` and immediately writes a deletion record to a `deleted_users` table in PostgreSQL and removes the user's preference cache entry.
3. All delivery workers check the `deleted_users` table (via a Redis bloom filter for performance — false positives result in dropped notifications for non-deleted users, which is not acceptable, so the bloom filter is used only as a fast-path negative check; a positive result triggers a definitive database lookup) before processing any notification.
4. Notifications already in the queue for a deleted user are dropped at the worker layer when the worker checks deleted status before delivery. The in-app worker does not write to PostgreSQL for deleted users.

This means notifications published to the queue before the deletion event was consumed will be dropped at the worker rather than delivered. There is a window between when the deletion is initiated and when all workers have consumed the `user.deleted` event during which a notification could be delivered to a deleted account. This window is bounded by consumer lag, which is monitored. For account deletion, a small delivery window is acceptable; the alternative — blocking the queue until all in-flight messages are confirmed dropped — is not feasible at this scale.

**Unsubscribe handling:**

Email unsubscribes are processed in real time — the unsubscribe link writes directly to the preference store — so regulatory deadlines (CAN-SPAM: 10 business days; CASL: 10 calendar days) are not practical constraints. The unsubscribe endpoint uses signed tokens in all email footers, verified server-side before processing, to prevent third-party unsubscribe attacks.

---

### 1.6 Infrastructure

**Queue architecture:**

The notification pipeline uses **SQS with SQS FIFO queues** as the primary message bus, not Kafka.

The prior draft chose Kafka primarily for log retention and replay capability. That justification does not hold up on examination. The replay use case — a buggy worker incorrectly marking deliveries — is already addressed by the DLQ and idempotency mechanisms. Kafka's log retention adds replay capability at the cost of consumer group management, partition rebalancing, offset management, and schema evolution expertise that a four-person team will need to exercise at 2am when something goes wrong. "Managed Kafka reduces the operational surface to configuration and monitoring" is not accurate: consumer group resets, exactly-once semantics failures, and partition skew are not configuration problems, and managed services do not eliminate them.

SQS handles 400 notifications/second with headroom to spare, supports dead-letter queues natively, has no consumer group concept to manage, and has operational failure modes that are well-understood and well-documented. The tradeoff is no native replay beyond the DLQ retention window. We accept this: replay scenarios are handled by the DLQ and, for catastrophic failures requiring full replay, by re-generating notifications from the application event log (which is the source of truth, not the notification queue).

If the team later determines that replay capability is worth the operational investment — for example, because the product has matured and the team has grown — migrating to Kafka or Kinesis is a tractable infrastructure project. Starting with Kafka and discovering the team can't operate it is not recoverable in the same way.

**Queue structure:**

| Queue | Type | Retention |
|---|---|---|
| `notifications-tier1` | SQS FIFO | 4 days |
| `notifications-tier2-dm` | SQS FIFO | 3 days |
| `notifications-tier2-standard` | SQS Standard | 3 days |
| `notifications-tier3` | SQS Standard | 7 days |
| `notifications-dlq` | SQS Standard | 14 days |
| `account-events` | SQS FIFO | 7 days |

Tier 1 and DM queues use FIFO to preserve ordering. Standard social notifications use SQS Standard queues because at-least-once delivery with occasional reordering is acceptable for likes and follows.

**Delivery workers:**

Each channel has a dedicated delivery worker pool:
- **Push worker:** calls APNs/FCM APIs, handles token refresh, processes delivery receipts
- **Email worker:** calls email service provider API (SendGrid or AWS SES)
- **SMS worker:** calls SMS provider API (Twilio); enforces security-event-only routing at this layer
- **In-app worker:** writes to the in-app notification store (PostgreSQL + Redis); checks deleted-user status before writing

Workers are stateless and horizontally scalable. Initial deployment: 2 instances per worker type. Auto-scaling adds instances when queue depth exceeds 30 seconds of processing capacity for Tier 1 or 2 minutes for Tier 2.

**Database:**

- **PostgreSQL (RDS):** User preferences, notification history (in-app center), unsubscribe records, deleted-user records
- **Redis (ElastiCache):** Preference cache, push token cache, rate limiting counters, batching state, delivered-notification idempotency set, deleted-user bloom filter
- **S3:** Archived notification logs (see §1.9 for the archival policy and its user-visible implications)

**Third-party dependencies:**

| Dependency | Purpose | Primary failure