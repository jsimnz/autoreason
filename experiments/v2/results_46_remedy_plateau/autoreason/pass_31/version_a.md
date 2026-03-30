# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Project Coordinator:** Sam Delgado, Program Management Office
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

This is the authoritative version. It supersedes all prior versions. Two open decisions (§9) require joint sign-off within 14 days of issue date. All other sections are final and implementation-ready.

---

## Table of Contents

1. Scale and Constraints
2. Delivery Channels
3. Priority and Batching Logic
4. User Preference Management
5. Infrastructure Choices
6. Failure Handling
7. Capacity Planning
8. Phased Delivery Plan
9. Open Decisions
10. Escalation Procedure

---

## 1. Scale and Constraints

### 1.1 Usage Profile

10M monthly active users. Assuming standard social app engagement patterns:

| Metric | Value | Derivation |
|---|---|---|
| Daily active users | ~3M | 30% DAU/MAU ratio |
| Notification events per DAU per day | ~15 | Likes, comments, follows, messages, system alerts |
| Peak daily notification volume | ~45M events | 3M × 15 |
| Peak hourly volume | ~8M events | 2.5× average during 6–10 PM local time |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Peak throughput | ~2,200 events/second | 8M / 3,600s |

These numbers drive infrastructure sizing in §5 and capacity planning in §7.

### 1.2 Team Constraints

Four backend engineers, six months. This is the binding constraint on every architectural decision in this document. Wherever a tradeoff appears below, the default choice favors operational simplicity over theoretical optimality. A system that two engineers can debug at 2 AM is worth more than a system that performs 15% better on paper.

**Explicit scope exclusions given team size:**
- No custom ML-based send-time optimization (use fixed quiet hours instead)
- No real-time A/B testing framework for notification copy
- No multi-region active-active deployment (single region with warm standby)
- No custom SMS aggregator integration (use a managed provider)
- No three-tier priority schema (two tiers handle all real use cases cleanly — see §3.1)

### 1.3 Success Criteria

| Metric | Target |
|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end |
| Standard notification delivery (p95) | < 2 minutes end-to-end |
| Push delivery rate | > 95% of reachable devices |
| Email delivery rate | > 98% (excluding hard bounces) |
| System availability | 99.9% (< 9 hours downtime/year) |
| User preference changes reflected | < 60 seconds |

---

## 2. Delivery Channels

### 2.1 Channel Overview

Four channels are supported. Selection logic: attempt channels in preference order, stop when delivery is confirmed, unless the event type requires multi-channel delivery (§3.1).

| Channel | Use Case | Latency Target | Cost Per Message |
|---|---|---|---|
| Push (FCM/APNs) | Real-time engagement, mobile-first | < 5s | ~$0.00 (provider free tier covers volume) |
| In-app | Active session users, non-urgent | < 1s | $0.00 (internal) |
| Email | Digests, account events, re-engagement | < 5 min | ~$0.001 |
| SMS | Critical account security only | < 30s | ~$0.05–0.07 |

**SMS cost note:** At 10M MAU, even 1% of users receiving one SMS per month is 100,000 messages — $5,000–7,000/month. SMS is therefore restricted to security events only. This is a deliberate product constraint, not a technical limitation.

### 2.2 Push Notifications (FCM / APNs)

**Provider:** Firebase Cloud Messaging for Android, Apple Push Notification service for iOS. Both are fully managed. A 4-person team should not operate push infrastructure.

**Token management:**
- Device tokens stored in `device_tokens` table (schema in §5.3)
- Tokens refreshed on each app open; stale tokens (no refresh in 90 days) are soft-deleted
- Invalid token responses from FCM/APNs trigger immediate hard-delete and suppress future sends to that token
- One user may have up to 5 active device tokens (multi-device support)

**Delivery confirmation:** FCM and APNs return delivery receipts asynchronously. Receipt processing runs as a separate consumer on the delivery-events queue. Receipts update the `notification_deliveries` table and feed the failure handling logic in §6.

**Tradeoff:** Read receipts are not implemented at the push layer — only at the in-app layer. Push confirms the message reached the device; the in-app layer handles whether the user saw it. This is acceptable and keeps the push integration simple.

### 2.3 In-App Notifications

**Mechanism:** WebSocket connection maintained during active sessions. The notification center pulls from a server-side inbox on load and on reconnect.

**Storage:** Notifications stored in the `notifications` table for 90 days, then archived. Inbox query: unread notifications for this user, ordered by priority then timestamp, limit 50.

**Real-time delivery:** When a user has an active WebSocket session, notifications are pushed over the socket immediately. The socket server subscribes to a Redis pub/sub channel per user (`notifications:{user_id}`). The notification worker publishes to this channel after writing to the database. If no socket is active, the notification sits in the database and appears when the user next opens the app.

**Read state:** Marked read when the user opens the notification center or taps a specific notification. Read events are batched and written every 30 seconds to avoid per-tap database writes.

### 2.4 Email

**Provider:** Amazon SES. Reasons: cheapest at this volume ($0.10/1,000 emails), handles bounce and complaint processing via SNS callbacks, straightforward SDK integration. SendGrid or Postmark are acceptable alternatives if deliverability becomes an issue; switching costs are low because email sending is isolated behind a single service interface.

**Email types:**

| Type | Trigger | Frequency Cap |
|---|---|---|
| Transactional | Account events (password reset, email change) | No cap |
| Activity digest | Aggregated social activity | Max 1/day per user |
| Re-engagement | User inactive > 7 days | Max 1/week per user |
| Product updates | Feature announcements | Max 1/month per user |

**Unsubscribe:** One-click unsubscribe in every email, per CAN-SPAM/GDPR requirements. Unsubscribe events from SES callbacks update user preferences within 60 seconds. Suppression list maintained in SES; users who have unsubscribed from a category are not re-added.

**HTML templates:** Stored in S3, rendered server-side using Handlebars or Jinja2. No inline CSS frameworks — keep templates simple enough that one engineer can maintain them.

### 2.5 SMS

**Provider:** Twilio. More expensive than alternatives (Vonage, AWS SNS for SMS) but has the best deliverability documentation, most mature SDKs, and easiest compliance handling for 10DLC registration in the US. The cost premium is justified for a security-critical channel where a 4-person team cannot afford deliverability debugging.

**Scope:** SMS is sent only for:
1. Password reset (when no push token exists or user explicitly requests SMS)
2. Login from unrecognized device
3. Two-factor authentication codes

**Opt-in:** SMS requires explicit opt-in. Pre-checked consent boxes are not acceptable. Users who have not opted in receive push or email for security events instead, with a prompt to add a phone number.

---

## 3. Priority and Batching Logic

### 3.1 Two-Tier Priority Schema

We use a two-tier schema: **Critical** and **Standard**.

A three-tier schema adds implementation complexity — separate queue configurations, additional routing logic, more conditional branches in the worker — that is not justified at 10M MAU with a 4-person team. The two-tier schema handles all real use cases cleanly. More importantly, a middle "High" tier creates classification disputes at the product level ("is a reply to my comment High or Standard?") that consume engineering and product time without improving user experience. The operationally meaningful distinction is: "wake the user up if necessary" versus "deliver efficiently when convenient." Two tiers map cleanly onto that distinction.

**Critical:**
- Security events (password reset, new device login, 2FA)
- Direct messages from connections
- Mentions in comments or posts
- System alerts (account suspension, content removal)

*Delivery target: < 5 seconds. All appropriate channels attempted in parallel. No batching. Quiet hours ignored.*

**Standard:**
- Likes, reactions, shares
- New followers
- Comment replies (non-mention)
- Digest summaries
- Re-engagement nudges

*Delivery target: < 2 minutes. Push attempted first; email batched into digest if user has email digests enabled. Quiet hours enforced.*

**Runtime override:** Event-type classification is set at registration in the `event_type_registry` table. A privileged internal service account can override classification for a specific event instance, with the override logged to the audit table. Overrides are restricted to a defined allowlist of event types (for example, a viral post crossing a threshold might be upgraded to Critical). Override attempts outside the allowlist are rejected with a 403 and logged. This provides operational flexibility without opening arbitrary runtime reclassification.

### 3.2 Batching Logic

**Standard notifications are batched by recipient, not by event type.** The batcher collects Standard events for a given user over a configurable window (default: 15 minutes) and either:

1. Sends a single push notification summarizing the batch ("You have 5 new likes and 2 new followers"), or
2. Holds for the next email digest if the user has push disabled and email digests enabled.

**Batching is skipped when:**
- The user has an active in-app session (deliver immediately via WebSocket)
- The batch window would push delivery past the user's next estimated active period (simple heuristic based on historical session data — not ML)
- The notification is the first Standard notification in > 4 hours (deliver immediately to maintain engagement signal)

**Quiet hours:** Default 10 PM–8 AM in the user's local timezone. Users can adjust or disable. During quiet hours, Standard notifications are held in the batch queue and released at the boundary. Critical notifications ignore quiet hours.

**Frequency caps (per user, per day):**

| Channel | Cap |
|---|---|
| Push | 20 |
| Email | 1 (digest) |
| SMS | 3 |
| In-app | No cap |

Caps are enforced by a Redis counter with a 24-hour TTL, reset at midnight UTC. Exceeding the cap silently drops the notification to in-app only and logs the suppression event. Surfacing a "you've hit your notification limit" message creates a worse user experience than simply not sending the push.

### 3.3 Deduplication

Duplicate events — same user, same event type, same source entity within 60 seconds — are deduplicated before queuing. Deduplication key: `SHA256(user_id + event_type + source_entity_id)`, checked against a Redis set with 60-second TTL. This prevents double-sends from upstream event producers that may emit the same event more than once during retry storms.

---

## 4. User Preference Management

### 4.1 Preference Model

Each user has a preference record with the following structure:

```
user_notification_preferences:
  user_id                 (FK to users)
  channel_push            (enabled | disabled)
  channel_email           (enabled | disabled)
  channel_sms             (enabled | disabled | not_configured)
  email_digest_frequency  (immediate | daily | weekly | never)
  quiet_hours_enabled     (boolean)
  quiet_hours_start       (HH:MM, user local time)
  quiet_hours_end         (HH:MM, user local time)
  timezone                (IANA timezone string)
  per_type_overrides      (JSONB: event_type → {push, email, sms} booleans)
  updated_at
```

`per_type_overrides` allows granular control without a separate row per event type. The JSONB field is queried at delivery time; the full preference record is cached in Redis with a 60-second TTL.

**Why JSONB for overrides rather than a normalized table?** A normalized `user_event_type_preferences` table would have up to 10M × N rows where N is the number of event types. Most users never customize per-type preferences. JSONB on the main preference row keeps the common case (no overrides) fast and the uncommon case (some overrides) still queryable. The tradeoff is that JSONB is harder to query in aggregate ("how many users have disabled push for likes?") — but that's an analytics query, not a hot path, and it can be handled with a GIN index or a periodic export to the data warehouse.

### 4.2 Preference Propagation

Preference changes must be reflected in delivery within 60 seconds (§1.3). The flow:

1. User changes preference via API
2. API writes to `user_notification_preferences` table
3. API publishes `preference_changed` event to the preference-updates queue
4. Preference consumer invalidates the Redis cache key for that user
5. Next notification delivery reads fresh preference from database (cache miss) and repopulates cache

Cache invalidation, not cache update, is used here. Invalidation avoids stale-write races when multiple preference changes arrive in quick succession. The 60-second TTL provides a natural fallback if the queue consumer is down: the old preference expires within the TTL window regardless.

### 4.3 Global Unsubscribe

A global unsubscribe (user opts out of all non-transactional notifications) is stored as a boolean flag on the user record, not in the preference table. This ensures it is checked at the earliest possible point in the delivery pipeline, before preference lookup, and cannot be accidentally bypassed by a bug in preference parsing. Security events are never suppressed by global unsubscribe.

### 4.4 Preference UI Principles

Not a backend concern, but stated here to prevent misalignment with the product team:

- Preferences reachable in ≤ 3 taps from any notification
- "Unsubscribe from all" is a single action, not a multi-step flow
- Preference changes feel instant via optimistic UI update with background sync

---

## 5. Infrastructure Choices

### 5.1 Architecture Overview

```
[Event Producers]
       │
       ▼
  [Event Bus / SNS]
       │
       ▼
[Notification Worker]──────────[Preference Cache (Redis)]
       │
       ▼
 [Priority Router]
    │         │
    ▼         ▼
[Critical   [Standard
  Queue]      Queue]
    │         │
    ▼         ▼
[Channel Routers: Push │ Email │ SMS │ In-App]
       │
       ▼
[Delivery Receipts Queue]
       │
       ▼
 [Failure Handler]
       │
       ▼
  [DLQ + Alerts]
```

All components run on AWS. The choice of AWS reflects assumed team familiarity; substitute equivalent GCP services throughout if the team is GCP-fluent.

### 5.2 Message Queue: Amazon SQS + SNS

**Choice:** SQS for delivery queues, SNS for fan-out from the event bus to queue subscribers.

**Why not Kafka?** Kafka is correct if you need replay, complex stream processing, or multi-consumer fan-out at very high throughput. At 2,200 events/second peak, SQS handles this comfortably with zero operational overhead. Kafka on MSK adds ~$500–800/month and requires at least one engineer who knows how to operate it. At 4 engineers and 6 months, that cost is not justified. If the system grows to 100M MAU and requires replay or complex event processing, migrate to Kafka then. The SQS interface is simple enough that migration is not architecturally painful.

**Queue structure:**

| Queue | Purpose | Visibility Timeout | DLQ Threshold |
|---|---|---|---|
| `notifications-critical` | Critical delivery, no batching | 1 minute | Any message → alarm |
| `notifications-standard` | Standard delivery, batching enabled | 15 minutes | > 100 messages → alarm |
| `notifications-dlq-critical` | Failed critical notifications | — |