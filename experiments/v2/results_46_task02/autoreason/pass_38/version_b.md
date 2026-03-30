# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides a complete technical design for the notification system. The design is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

**Note on revision:** This document addresses ten specific problems identified in review. Where a prior version made a claim that doesn't hold, the claim is corrected. Where a prior version deferred a description to a section that was never written, that section is now written. Where a prior version acknowledged a problem and then accepted it without justification, this version either provides the justification or changes the design.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 30 days of launch.** The validation process is described in §1.8.

**Sensitivity to DAU/MAU ratio:** The load model below is built on 2.5M DAU. If the actual ratio is higher — 40% DAU/MAU is not uncommon for a well-retained social app, implying 4M DAU — peak throughput roughly doubles. Infrastructure must be provisioned before this is known. The design response to this uncertainty is stated explicitly: all queue consumers and delivery workers are deployed with auto-scaling configured from day one, with scaling targets set to handle 2× the baseline estimate without manual intervention. The auto-scaling configuration is described in §1.6. The 30-day validation window is not a grace period during which the system might be under-provisioned; it is the window during which we confirm whether auto-scaling headroom is sufficient or whether baseline provisioning needs to increase. If actual DAU/MAU exceeds 40% before the 30-day mark, the on-call engineer escalates immediately rather than waiting for the scheduled review.

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

1.3M notifications/day divided across 24 hours yields an average rate of approximately 15 notifications/second. Social apps exhibit pronounced evening spikes (18:00–22:00 local time). Across a global user base distributed across timezones, the peak hour does not concentrate all users simultaneously — a realistic concentration factor is that roughly 20–25% of DAU are active during the peak hour in their local timezone, spread across a 2–3 hour window in absolute time. Applying an 8× peak factor to the average hourly rate — not to the daily average rate — yields:

- Average hourly rate: ~54,000 notifications/hour (~15/second)
- Peak hour at 8× concentration: ~432,000 notifications/hour
- Sustained peak throughput: **~120 notifications/second**
- Provisioning target with 2× headroom for the DAU/MAU uncertainty above: **~240 notifications/second**

The prior version stated 200–250/second as a derived figure; it was not. The correct derived sustained peak is approximately 120/second. The 240/second provisioning target is the derived figure plus explicit headroom, and is labeled as such. Brief spikes above the sustained peak are handled by queue buffering, not by provisioning for the spike ceiling — attempting to provision for the maximum conceivable instantaneous rate is neither cost-effective nor necessary when queues absorb the burst.

These are estimates, not measurements. The system must be instrumented from day one so actual numbers replace these within the first 30 days of production traffic.

---

### 1.2 Delivery Channels

Four channels are in scope: push, in-app, email, and SMS.

**Push notifications** are the primary real-time channel for mobile users. Delivery goes through APNs (iOS) and FCM (Android). Neither service guarantees delivery or provides reliable delivery receipts — a device that is offline when a notification is sent may receive it later, receive it never, or receive a collapsed version if multiple notifications were queued. The system must not treat push delivery confirmation as proof the user saw the notification.

*Tradeoff accepted:* Push is cheap and fast but unreliable. We accept this unreliability for social notifications (likes, comments, follows) because the cost of a missed like notification is low. We do not accept it for account security events, which require a fallback channel.

**In-app notifications** are rendered in a notification center when the user opens the app. This is the most reliable channel because delivery is synchronous with app usage. In-app notifications are the fallback for failed push and the primary channel for users who have disabled push. Every Tier 2 notification is written to the in-app store regardless of push status. The in-app notification center displays a rolling 30-day window; the archival behavior at that boundary is addressed in §1.9.

*Tradeoff accepted:* In-app notifications require the user to open the app. For time-sensitive content this is a meaningful limitation. We accept it because mandatory push for all users would increase opt-out rates.

**Email** is used for digest notifications (weekly activity summary, content the user missed) and for account and security events. Email is not used for real-time social notifications — the latency is incompatible with the use case, and email for every like would immediately drive unsubscribes.

**SMS** is used only for account security events: two-factor authentication codes and suspicious login alerts. It is not used for social notifications. The cost justification and the specific controls enforcing this scope are described in §1.6.

---

### 1.3 Priority Tiers

Notifications are assigned to one of three priority tiers at creation time. The tier determines queue routing, delivery SLA, and retry behavior.

**Tier 1 — Critical (account and security events)**
- Examples: password reset, login from new device, account suspension, payment failure
- Delivery target: first attempt within 60 seconds of creation. This is a first-attempt target, not a guaranteed end-to-end delivery SLA. Retry behavior after a failed first attempt extends well beyond 60 seconds — the goal is eventual delivery, not abandonment after one attempt.
- Channels: push (immediate), SMS (concurrent with push — not sequential, because waiting for push failure confirmation adds unacceptable latency for security events), email (concurrent). The cost exposure from concurrent multi-channel delivery is real and is addressed directly in §1.6 with specific volume controls.
- Batching: none — Tier 1 notifications are never batched, never subject to quiet hours, and never suppressed by user preference
- Volume: estimated <0.1% of total notification volume. The controls that enforce this bound are described in §1.6.

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
- Batching: always batched
- Volume: estimated 15% of total notification volume

---

### 1.4 Batching Logic

**Notification subtypes:**

Each notification carries two routing fields: `tier` (1, 2, or 3) and `subtype` (a string enum: `like`, `comment`, `follow`, `mention`, `direct_message`, `security`, `digest`, etc.). Batching and spike-exclusion logic operates on `subtype`. The `subtype` field is set at notification creation and is immutable.

**Per-user batching threshold (Tier 2, non-DM subtypes):**

If a user would receive more than 5 notifications of the same subtype within a 10-minute window, subsequent notifications of that subtype are batched. The batch is held for 10 minutes from the first batched notification, then delivered as a single notification: "You have 8 new likes on your post."

The 10-minute window and 5-notification threshold are configurable per subtype. These are starting values based on industry convention, not empirical data from this product. They must be reviewed after 60 days of production data.

**Spike batching (system-level):**

During periods when the Tier 2 standard queue depth exceeds 500,000 queued messages, the system applies a 30-minute hold to Tier 2 standard notifications before delivery. The hold applies only to notifications where `subtype != direct_message`. Direct messages are routed to a dedicated `notifications-tier2-dm` queue and are not subject to spike batching regardless of overall queue depth.

*Tradeoff accepted:* Spike batching means a user might receive "you have 47 likes" 30 minutes after the likes occurred rather than individual near-real-time notifications. This is acceptable for social content. The cost of getting DM latency wrong is qualitatively different — it breaks conversational interaction — so the exclusion is architectural rather than configurable.

**Direct message queue isolation — what it does and does not solve:**

DMs are routed to a dedicated queue and excluded from spike batching. This prevents spike batching from introducing DM delivery delay. It does not, by itself, prevent DM latency degradation caused by resource contention on shared infrastructure — delivery workers, APNs/FCM connections, and the Redis preference cache are shared across Tier 2 traffic including DMs.

To address this: DM delivery workers are a separate worker pool, not merely a separate queue consumed by shared workers. The DM worker pool has dedicated auto-scaling configuration with more aggressive scale-out triggers (described in §1.6) and dedicated Redis connection pool limits so that cache saturation from non-DM traffic does not crowd out DM lookups. APNs/FCM connections are managed per worker pool, so DM workers maintain their own connection pool and are not competing with standard Tier 2 workers for connection slots.

What remains shared: the APNs and FCM services themselves are external and rate-limit by app credential, not by our worker pool. If overall push volume is high enough to approach APNs/FCM rate limits, DMs will be affected along with everything else. Mitigation is to monitor APNs/FCM rate limit responses and alert before the limit is reached, so the team can engage Apple/Google about limit increases before DM delivery degrades. This is an operational dependency, not something the architecture can fully insulate.

**Quiet hours and the thundering herd:**

Users can specify a quiet-hours window during which push and SMS notifications are suppressed. Notifications held during quiet hours are released at the end of that window. If a meaningful fraction of users share the same quiet-hours end time, the release creates a predictable daily spike.

This is addressed by staggering quiet-hours release with a randomized jitter of 0–15 minutes added to the scheduled delivery time. The jitter is deterministic per user (derived from a hash of the user ID) so it is consistent across days.

**What jitter does and does not guarantee:**

Jitter reduces instantaneous peak rate by spreading a concentrated release across a 15-minute window instead of a single moment. For a population of users whose quiet hours end at 08:00, jitter reduces the instantaneous peak by approximately 15× — users are distributed roughly uniformly across 15 one-minute buckets rather than all firing at once.

What jitter does not do: it does not reduce the total notification volume delivered during that window. If the 15-minute post-jitter window still produces a queue depth exceeding 500,000 messages — the spike batching threshold — spike batching will trigger. Whether it triggers depends on the number of users with 08:00 quiet-hour end times and their per-user notification volume. For a 10M MAU base, if 10% of users set quiet hours ending at 08:00 (1M users), and each has an average of 3 held notifications, that is 3M messages to be delivered over 15 minutes — roughly 3,300/second sustained, well above the spike batching threshold.

The design's honest position: jitter is a meaningful mitigation that handles the common case where quiet-hour concentration is moderate. It does not prevent spike batching from triggering during the morning release window if quiet-hour adoption is high and concentrated. The spike batching mechanism is explicitly the backstop for this case, and users who configure quiet hours should expect that their morning release may be subject to a 30-minute additional delay during high-traffic periods. This behavior should be documented in the user-facing preference UI. The alternative — guaranteeing exact quiet-hour end delivery regardless of system load — would require dedicated per-user scheduled jobs, which is not feasible at this scale with this team.

**Digest batching (Tier 3):**

Digest notifications are pre-computed by a scheduled job that runs at 06:00 UTC daily. The job aggregates each user's unread activity. The correctness of this job depends on how the snapshot timestamp is managed across restarts.

**Snapshot timestamp persistence and restart correctness:**

The snapshot timestamp is the read-consistent point at which unread state is evaluated. The idempotency key for each user's digest record is `(user_id, snapshot_timestamp)`. For this key to protect against duplicate digests on restart, the snapshot timestamp must be the same in both the original run and any restart.

The snapshot timestamp is persisted to a dedicated row in the PostgreSQL `digest_job_runs` table at the moment the job starts, before processing any users. The row contains: `run_date` (the calendar date), `snapshot_timestamp` (the fixed evaluation point), `status` (running/complete/failed), and `last_committed_user_id` (updated after each batch of users is processed and committed). On restart, the job reads the `digest_job_runs` row for today's `run_date`. If a row exists with `status = running`, the job uses the persisted `snapshot_timestamp` and resumes from `last_committed_user_id`. If no row exists, the job creates one with a fresh snapshot timestamp.

This means a restart caused by a crash, a code deployment, or a scheduler misconfiguration will always recover the original snapshot timestamp from the database, not generate a new one. A restart that generates a new snapshot timestamp — which would change the idempotency key and enable duplicate delivery — requires either a missing or corrupted `digest_job_runs` row, which is a database integrity failure and is caught by the job's startup validation step.

The one remaining gap: if an operator manually deletes the `digest_job_runs` row and restarts the job, a new snapshot timestamp will be generated and users processed in both runs will receive duplicate digests. This is prevented by: (a) restricting delete access to the `digest_job_runs` table to a named DBA role, not the application service account, and (b) documenting that manual deletion of a running job's row is a destructive operation requiring explicit sign-off.

A notification received at 06:01 UTC will not appear in the current digest for any user. This is a known and accepted boundary condition. A user who receives a late-night notification not captured in the morning digest will see it in the following day's digest. This is a known product behavior and should be reflected in user-facing documentation.

*Known limitation:* Timezone data in user profiles is self-reported and may be absent or incorrect. For users with no timezone data, delivery defaults to 09:00 UTC. Improving this requires either requiring timezone at signup or inferring it from device locale — both are product decisions outside the scope of this document.

---

### 1.5 User Preference Management

Users can control notification delivery at three levels of granularity:

**Level 1 — Global channel preferences:** On/off per channel (push, email, SMS). Turning off a channel suppresses all notifications on that channel except Tier 1. Tier 1 notifications cannot be suppressed globally.

**Level 2 — Subtype preferences:** Per notification subtype, the user can set: all channels on, push only, email only, or off. The "off" setting suppresses the notification entirely except for Tier 1 subtypes.

**Level 3 — Quiet hours:** The user specifies a time window during which push and SMS notifications are suppressed. Tier 1 notifications