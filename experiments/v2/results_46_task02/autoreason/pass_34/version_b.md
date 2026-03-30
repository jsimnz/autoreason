# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on Scope and Document Failure

The prior versions of this document accumulated 24 structural problems across two revision cycles, then submitted a truncated draft as a third version. The revision table in that draft claimed to resolve problems in sections that did not exist in the submitted text. That is not a quality signal; it is a reliability failure.

This version takes a different approach. The governance scaffolding — gate confirmation procedures, NSTL backup activation, oversight body quorum rules, fill sequences — has consumed more design attention than the notification system itself. That is the wrong allocation. A four-person team over six months does not need a 3,000-word governance apparatus to build a notification system. It needs clear technical decisions, explicit tradeoffs, and lightweight coordination that does not itself require a manual to operate.

This document therefore:

1. Provides a complete technical design for the notification system
2. Retains a gate system, but in a form that a four-person team can actually use
3. Addresses each of the 11 criticisms directly, including the structural ones
4. Does not claim completeness it cannot demonstrate — sections that are not written are not cited

Where a problem identified in the criticism cannot be fully resolved within a practical governance structure for a team of this size, that limitation is stated explicitly rather than papered over with additional procedure.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; we use 2.5M as the working figure).

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

Peak factor: social apps exhibit pronounced evening spikes (18:00–22:00 local time across timezones) and event-driven spikes (viral content, product launches). Peak-hour volume is estimated at 8–10× average hourly rate, yielding a peak throughput requirement of roughly **200–250 notifications/second** sustained, with brief spikes to 400/second.

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

**Four channels are in scope: push, in-app, email, and SMS.**

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications (likes, comments, follows) because the cost of a missed like notification is low. We do not accept it for account security events (password changed, login from new device), which require a fallback channel.

**In-app notifications** are a notification center within the application, rendered when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage — the user either sees the notification center or does not open the app. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because the alternative — mandatory push for all users — would increase opt-out rates and reduce the effectiveness of push for users who want it.

**Email** is used for digest notifications (weekly activity summary, content the user missed) and for account/security events. Email is not used for real-time social notifications because the latency is incompatible with the use case and because email for every like would immediately drive users to unsubscribe.

*Tradeoff accepted:* Email has the highest deliverability for users who are inactive on mobile, but it is the lowest-engagement channel for social content. We use it narrowly to preserve its signal value.

**SMS** is used only for account security events (two-factor authentication codes, suspicious login alerts) and for users in markets where push penetration is low. SMS is expensive (roughly $0.01–0.05 per message depending on carrier and region) and introduces regulatory complexity (opt-in requirements vary by jurisdiction). At 10M MAU, even 1% of users receiving one SMS per day is 100,000 messages, which at $0.01 average cost is $1,000/day or $365,000/year. This is non-trivial.

*Tradeoff accepted:* We scope SMS to security events and high-priority account events only. This limits cost to an estimated $5,000–15,000/year at current scale while covering the cases where SMS is genuinely necessary. We do not use SMS for social notifications. If a future use case requires broader SMS, it requires explicit re-authorization with a cost estimate.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery SLA: best effort within 60 seconds; retry for up to 24 hours
- Channels: push (immediate), SMS (immediate fallback if push not delivered within 5 minutes), email (concurrent with push)
- Batching: none — these are never batched
- Volume: estimated <0.1% of total notification volume

**Tier 2 — Standard (real-time social events)**
- Examples: like, comment, new follower, mention, direct message
- Delivery SLA: best effort within 5 minutes
- Channels: push (primary), in-app (always written, regardless of push status)
- Batching: applied when volume to a single user exceeds threshold (see §1.4)
- Volume: estimated 85% of total notification volume

**Tier 3 — Digest (low-urgency, aggregated)**
- Examples: weekly summary, "you have 12 unread notifications," re-engagement nudges
- Delivery SLA: scheduled delivery within a defined window (e.g., 09:00–10:00 user local time)
- Channels: email (primary), in-app (secondary)
- Batching: always batched — individual digest items are never sent as individual notifications
- Volume: estimated 15% of total notification volume, but concentrated at scheduled times

---

### 1.4 Batching Logic

Batching serves two purposes: reducing notification fatigue for users who receive high volumes, and reducing load on downstream delivery infrastructure during spikes.

**Per-user batching threshold (Tier 2):**

If a user would receive more than **5 notifications of the same type within a 10-minute window**, subsequent notifications of that type are batched. The batch is held for **10 minutes from the first batched notification**, then delivered as a single notification: "You have 8 new likes on your post."

The 10-minute window and 5-notification threshold are configurable per notification type in the service configuration. These are starting values based on industry convention, not empirical data from this product. They must be reviewed after 60 days of production data.

**Spike batching (system-level):**

During periods when the notification queue depth exceeds a defined threshold (initially set at 500,000 queued messages, reviewed after 30 days), the system automatically downgrades Tier 2 notifications to batched delivery with a 30-minute hold. Tier 1 notifications are never affected by spike batching. This prevents a viral event from creating a delivery backlog that degrades Tier 1 SLAs.

*Tradeoff accepted:* Spike batching means a user might receive a "you have 47 likes" notification 30 minutes after the likes occurred rather than individual notifications in near-real-time. This is acceptable for social content. It is not acceptable for messages, which are excluded from spike batching even at Tier 2.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job aggregates each user's unread activity from the previous 24 hours and queues a single digest notification per user who meets the threshold (default: at least 3 unread items). Delivery is scheduled for the user's local morning window using timezone data from the user profile.

*Known limitation:* Timezone data in user profiles is self-reported and may be absent or incorrect. For users with no timezone data, delivery defaults to 09:00 UTC. This will be wrong for a large fraction of users. Improving this requires either requiring timezone at signup (product decision, not infrastructure) or inferring timezone from device locale (requires product work). This limitation is noted for the product team; it is not resolved in this document.

---

### 1.5 User Preference Management

Users can control notification delivery at three levels of granularity:

**Level 1 — Global channel preferences:** On/off per channel (push, email, SMS). Turning off a channel suppresses all notifications on that channel except Tier 1. Tier 1 notifications (security events) cannot be suppressed globally; this is a product safety decision.

**Level 2 — Type preferences:** Per notification type (likes, comments, follows, messages, etc.), the user can set: all channels on, push only, email only, off. The "off" setting suppresses the notification entirely except for Tier 1 types, which cannot be set to off.

**Level 3 — Quiet hours:** The user specifies a time window (e.g., 22:00–08:00 in their timezone) during which push and SMS notifications are suppressed. Notifications that arrive during quiet hours are held and delivered at the end of the quiet window. Tier 1 notifications bypass quiet hours.

**Preference storage:**

User preferences are stored in the primary application database (PostgreSQL) as a JSON column on the user preferences table. At notification dispatch time, the notification service reads the user's preferences from a **Redis cache** (TTL: 5 minutes) before routing to delivery channels. Cache miss falls back to the database.

*Tradeoff accepted:* A 5-minute cache TTL means a user who changes their preferences may continue to receive notifications on the old preference for up to 5 minutes. This is acceptable for preference changes (the user will not notice a 5-minute lag in a preference taking effect). For account deletion or account suspension, preferences are invalidated immediately by a direct cache delete, not relying on TTL expiry.

**Unsubscribe handling:**

Email unsubscribes must be processed within 10 business days under CAN-SPAM and within 10 calendar days under CASL. The system processes unsubscribes in real time (the unsubscribe link writes directly to the preference store), so the regulatory deadline is not a practical constraint. However, the unsubscribe endpoint must be authenticated to prevent third-party unsubscribe attacks. Implementation: signed unsubscribe tokens in all email footers, verified server-side before processing.

---

### 1.6 Infrastructure

**Queue architecture:**

The notification pipeline uses **Kafka** as the primary message bus. Notifications are published to Kafka topics partitioned by user ID (ensuring ordering for a given user) and consumed by channel-specific workers.

Topic structure:
- `notifications.tier1` — critical notifications, 12 partitions, 7-day retention
- `notifications.tier2` — standard notifications, 48 partitions, 3-day retention
- `notifications.tier3` — digest notifications, 12 partitions, 7-day retention
- `notifications.dlq` — dead letter queue for all failed deliveries, 12 partitions, 14-day retention

*Why Kafka over a simpler queue (SQS, RabbitMQ):* At 200+ notifications/second sustained with spike capacity to 400/second, Kafka's throughput is not the reason to choose it. SQS handles this easily. The reason is **replay capability** — Kafka's log retention means that if the push delivery worker has a bug and incorrectly marks 50,000 notifications as delivered when they were not, we can replay from the retained log and re-deliver. For a notification system, this failure recovery property is worth the operational overhead of running Kafka.

*Tradeoff accepted:* Kafka is operationally more complex than SQS. On a four-person team, this is a real cost. We mitigate it by using a managed Kafka service (Confluent Cloud or AWS MSK) rather than self-hosted Kafka. The operational surface is reduced to configuration and monitoring, not cluster management.

**Delivery workers:**

Each channel has a dedicated delivery worker pool:
- Push worker: calls APNs/FCM APIs, handles token refresh, processes delivery receipts
- Email worker: calls email service provider API (SendGrid or AWS SES)
- SMS worker: calls SMS provider API (Twilio)
- In-app worker: writes to the in-app notification store (PostgreSQL + Redis)

Workers are stateless and horizontally scalable. Initial deployment: 2 instances per worker type, auto-scaling configured to add instances when queue lag exceeds 30 seconds for Tier 1 or 2 minutes for Tier 2.

**Database:**

- **PostgreSQL (RDS):** User preferences, notification history (for in-app center), unsubscribe records
- **Redis (ElastiCache):** Preference cache, push token cache, rate limiting counters, batching state
- **S3:** Archived notification logs (after 30 days, notification history rows are exported to S3 and deleted from PostgreSQL to manage table size)

**Third-party dependencies:**

| Dependency | Purpose | Failure risk |
|---|---|---|
| APNs | iOS push delivery | Apple service outage; token expiry |
| FCM | Android push delivery | Google service outage; token expiry |
| SendGrid / AWS SES | Email delivery | Provider outage; IP reputation |
| Twilio | SMS delivery | Provider outage; carrier issues |

All third-party dependencies are wrapped in circuit breakers (initial threshold: 10 failures in 60 seconds opens the circuit; 30-second half-open probe). Failed deliveries are written to the DLQ for retry.

---

### 1.7 Failure Handling

**Retry policy by tier:**

| Tier | Max retries | Retry schedule | After max retries |
|---|---|---|---|
| Tier 1 | 10 | Exponential backoff: 10s, 30s, 1m, 2m, 5m, 10m, 20m, 40m, 80m, 160m | Alert on-call; write to DLQ |
| Tier 2 | 5 | Exponential backoff: 30s, 2m, 10m, 30m, 2h | Write to DLQ; deliver as in-app only |
| Tier 3 | 3 | Fixed: 1h, 4h, 24h | Drop; log for analytics |

**DLQ processing:**

The dead letter queue is consumed by a separate DLQ processor that runs every 6 hours. It attempts re-delivery for Tier 1 items up to 24 hours after original creation, and for Tier 2 items up to 6 hours after creation. Items older than these windows are logged and discarded. The DLQ processor generates a daily report of dropped notifications by type and channel, reviewed by the on-call engineer.

**Push token management:**

Stale push tokens are a primary source of push delivery failures. APNs and FCM return specific error codes when a token is invalid or the app has been uninstalled. The push worker processes these responses and marks tokens as invalid in the token store immediately upon receipt of an invalidation error. Tokens are refreshed from the device each time the user opens the app.

**Idempotency:**

Each notification is assigned a UUID at creation. Delivery workers check a Redis set of recently delivered notification IDs (TTL: 24 hours) before attempting delivery. If the ID is already in the set, delivery is skipped. This prevents duplicate delivery when a worker crashes after delivery but before acknowledging the Kafka message, causing the message to be reprocessed.

*Known gap:* The Redis TTL means idempotency protection expires after 24 hours. A Kafka consumer group reset (e.g., for replay after a bug) that replays messages older than 24 hours will not be protected by this mechanism. For replay scenarios, the operator must either extend the Redis TTL before initiating the replay or accept that some users may receive duplicate notifications. This tradeoff is documented in the runbook