# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

This document has two statuses by section. **Sections 2, 4, and 6** are final and implementation-ready. **Sections 3, 5, and 7** depend on two open decisions in §9 (DAU/MAU ratio confirmation, geographic distribution of users) and must not be used for infrastructure provisioning until those decisions are resolved. The dependency is called out explicitly in each affected section. Target resolution: 14 days from issue date.

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

10M monthly active users. The numbers below are planning assumptions derived from industry averages, not measurements. They must be validated against product analytics before infrastructure is provisioned. §1.1.1 shows explicitly how sensitive downstream sizing is to the two key assumptions.

| Metric | Value | Basis |
|---|---|---|
| Daily active users | ~3M | 30% DAU/MAU — see §1.1.1 |
| Notification events per DAU per day | ~15 | Likes, comments, follows, messages, system alerts |
| Peak daily notification volume | ~45M events | 3M × 15 |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Peak throughput | ~1,560 events/second | See §1.1.2 |

#### 1.1.1 DAU/MAU Sensitivity

The 30% DAU/MAU ratio is borrowed from industry averages. The actual ratio is unknown until instrumented. It is the first multiplier in every throughput calculation and therefore the most important number to validate.

| DAU/MAU | DAU | Peak events/sec | Infrastructure implication |
|---|---|---|---|
| 15% (content-discovery app) | 1.5M | ~780/sec | Smallest SQS configuration sufficient |
| 30% (assumed baseline) | 3M | ~1,560/sec | Baseline sizing in this document |
| 60% (messaging-heavy app) | 6M | ~3,120/sec | Additional worker capacity; Redis cluster sizing doubles |

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this is a greenfield launch with no historical data, provision for 20% with autoscaling configured to handle 60% without manual intervention. Do not treat 30% as a hard number.

#### 1.1.2 Peak Throughput Calculation

Peak multipliers depend heavily on geographic concentration. A 4-hour evening peak in a single timezone concentrates traffic in a way that the same peak smeared across multiple timezones does not.

| Case | Description | Peak multiplier | Peak events/sec |
|---|---|---|---|
| US-only | 90%+ of users in contiguous US | 2.0× average | ~1,040/sec |
| US + Western Europe | Significant overlap in evening peaks | 1.6× average | ~830/sec |
| Global, distributed | No dominant timezone cluster | 1.3× average | ~675/sec |

The baseline in this document uses **2.0×** (US-centric), producing ~1,040 events/second sustained peak and ~1,560 events/second for burst headroom at 3× average. If the product is genuinely global, infrastructure will be slightly over-provisioned — acceptable. If more concentrated than assumed, the numbers hold.

**Action required:** Engineering must obtain geographic user distribution from the product team before finalizing §7.

### 1.2 Team Constraints

Four backend engineers, six months. This is the binding constraint on every architectural decision in this document. Wherever a tradeoff appears, the default choice favors operational simplicity over theoretical optimality. A system two engineers can debug at 2 AM is worth more than one that performs 15% better on paper.

**Explicit scope exclusions:**
- No custom ML-based send-time optimization (fixed quiet hours instead)
- No real-time A/B testing framework for notification copy
- No multi-region active-active deployment (single region with warm standby — RTO and RPO defined in §6.4)
- No custom SMS aggregator integration (Twilio managed service)
- No three-tier priority schema (rationale in §3.1)

### 1.3 Success Criteria

| Metric | Target | Notes |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.9% (< 9 hours downtime/year) | Analysis in §6.4 |
| User preference changes reflected | < 60 seconds | |

---

## 2. Delivery Channels

### 2.1 Channel Overview and Fallback Logic

Four channels are supported. The selection logic differs by priority tier and requires explicit description, because the naive reading — "attempt channels in order, stop when delivery is confirmed" — breaks down when confirmation is asynchronous.

**For Critical notifications:** All eligible channels are dispatched in parallel simultaneously. Eligibility is determined before dispatch by checking opt-in status and device token validity. There is no wait for confirmation from one channel before attempting another. At Critical priority, latency matters more than avoiding redundant delivery. Users may receive the same critical notification via both push and email; this is acceptable and expected.

**For Standard notifications:** Push is attempted first. Email is batched into digests. In-app is always written. SMS is not used for Standard notifications. There is no real-time cross-channel fallback for Standard — if push fails, the notification remains available in-app and in the next email digest.

**Why this distinction matters:** The "stop when confirmed" model implies that confirmation is synchronous. It is not. Push confirmation from FCM/APNs arrives asynchronously via a separate receipt queue. Building a stateful fallback system that waits for async push confirmation before deciding to trigger email would require: persistent state per in-flight notification, a timeout mechanism, a reconciliation worker, and careful handling of the race between receipt arrival and timeout expiry. For Critical notifications, parallel delivery sidesteps this problem entirely. For Standard notifications, the digest model sidesteps it by design. Neither approach requires stateful fallback tracking.

| Channel | Use Case | Latency Target | Cost Per Message |
|---|---|---|---|
| Push (FCM/APNs) | Real-time engagement, mobile-first | < 5s | ~$0.00 (provider free tier) |
| In-app | Active session users, non-urgent | < 1s | $0.00 (internal) |
| Email | Digests, account events, re-engagement | < 5 min | ~$0.001 |
| SMS | Critical account security, explicit opt-in only | < 30s | ~$0.05–0.07 |

**SMS cost note:** At 10M MAU, even 1% of users receiving one SMS per month is 100,000 messages — $5,000–7,000/month. SMS is restricted to security events for opted-in users. This is a deliberate product constraint, not a technical limitation.

### 2.2 Push Notifications (FCM / APNs)

**Provider:** Firebase Cloud Messaging for Android, Apple Push Notification service for iOS. Both are fully managed. A 4-person team should not operate push infrastructure.

**Token management:**
- Device tokens stored in `device_tokens` table (schema in §5.3)
- Tokens refreshed on each app open; stale tokens (no refresh in 90 days) are soft-deleted
- Invalid token responses from FCM/APNs trigger immediate hard-delete and suppress future sends to that token
- One user may have up to 5 active device tokens (multi-device support)

**Delivery confirmation:** FCM and APNs return delivery receipts asynchronously. Receipt processing runs as a separate consumer on the delivery-events queue. Receipts update the `notification_deliveries` table and feed the failure handling logic in §6. Receipts are **not** used to gate fallback channel dispatch — see §2.1 for the rationale.

**Tradeoff accepted:** Read receipts are not implemented at the push layer, only at the in-app layer. Push confirms the message reached the device; in-app handles whether the user saw it. This keeps the push integration simple and avoids instrumenting a signal (push open rate) that is unreliable on iOS due to system-level notification coalescing.

### 2.3 In-App Notifications

**Mechanism:** WebSocket connection maintained during active sessions. The notification center pulls from a server-side inbox on load and on reconnect.

**Storage:** Notifications stored in the `notifications` table for 90 days, then archived. Inbox query: unread notifications for this user, ordered by priority then timestamp, limit 50.

**Real-time delivery:** When a user has an active WebSocket session, notifications are pushed over the socket immediately. The socket server subscribes to a Redis pub/sub channel per user (`notifications:{user_id}`). The notification worker publishes to this channel after writing to the database. If no socket is active, the notification sits in the database and appears when the user next opens the app.

**WebSocket scaling:** At 3M DAU with an average session length of 20 minutes distributed across a 16-hour active window, concurrent WebSocket connections peak at approximately 3M × (20/960) ≈ 62,500 concurrent connections.

Key design decisions for this connection count:
- WebSocket servers are stateless; any server can handle any user connection
- Each WebSocket server subscribes to active user channels on the shared Redis pub/sub cluster
- Redis pub/sub is not persistent: a message published when no subscriber is connected is lost at the pub/sub layer. This is acceptable because the notification is written to the database before publication. On reconnect, the client sends its last-seen notification ID and the server returns all unread notifications with a higher ID — a simple range query, not a complex sync protocol. There is no message loss, only a delivery mode change from real-time to on-reconnect.

**WebSocket server sizing:** At 62,500 concurrent connections, a t3.medium instance handles ~10,000–15,000 connections comfortably. Plan for 6–8 instances behind a load balancer with sticky sessions disabled (connection state is in Redis, not local). Autoscale on connection count at 70% capacity per instance.

**Read state:** Marked read when the user opens the notification center or taps a specific notification. Read events are batched and written every 30 seconds to avoid per-tap database writes.

### 2.4 Email

**Provider:** Amazon SES.

**Why SES:** Cost — $0.10/1,000 emails versus $0.80–1.00/1,000 for SendGrid or Postmark. At digest volumes for 3M DAU, this difference is material. SES handles bounce and complaint processing via SNS callbacks and has straightforward SDK integration.

**The deliverability tradeoff is real and must be managed actively.** This is not a set-and-forget choice:
- SPF, DKIM, and DMARC records must be configured and monitored at launch. These are not optional.
- AWS will pause sending if bounce rate exceeds 5% or complaint rate exceeds 0.1%. This requires continuous monitoring, not periodic checks.
- A dedicated sending IP must be provisioned from day one. Shared IP reputation is unpredictable at 10M MAU volumes.

**Switching providers is not low-cost.** If SES deliverability becomes a problem, migrating to SendGrid or Postmark requires: exporting suppression lists (SES format is not directly compatible), reconfiguring SPF/DKIM/DMARC DNS records, rebuilding bounce and complaint webhook integrations, and warming up a new sending IP — typically a 4–6 week process during which deliverability is degraded. Treat SES deliverability as a first-class operational concern from day one, not as a problem to solve if it arises.

**Email types:**

| Type | Trigger | Frequency Cap |
|---|---|---|
| Transactional | Account events (password reset, email change) | No cap |
| Activity digest | Aggregated social activity | Max 1/day per user |
| Re-engagement | User inactive > 7 days | Max 1/week per user |
| Product updates | Feature announcements | Max 1/month per user |

**Unsubscribe:** One-click unsubscribe in every email, per CAN-SPAM/GDPR requirements. Unsubscribe events from SES callbacks update user preferences within 60 seconds. Suppression list maintained in SES; users who have unsubscribed from a category are not re-added to it.

**HTML templates:** Stored in S3, rendered server-side using Handlebars or Jinja2. No inline CSS frameworks — keep templates simple enough that one engineer can maintain them.

### 2.5 SMS

**Provider:** Twilio. More expensive than alternatives (Vonage, AWS SNS for SMS) but has the best deliverability documentation, most mature SDKs, and easiest compliance handling for 10DLC registration in the US. The cost premium is justified for a security-critical channel where a 4-person team cannot afford deliverability debugging.

**Scope:** SMS is sent only for security events, and only to users who have explicitly opted in with a verified phone number:
1. Password reset (when no push token exists or user explicitly requests SMS)
2. Login from unrecognized device
3. Two-factor authentication codes

**Opt-in and routing interaction:** SMS requires explicit opt-in with a verified phone number. Pre-checked consent boxes are not acceptable. The channel eligibility check — performed before any dispatch begins — excludes SMS from the eligible channel set for users who have not opted in. Users without SMS opt-in receive push and/or email for security events, with an in-app prompt to add and verify a phone number. No conditional logic exists inside the channel routers themselves; eligibility is resolved upstream, before dispatch.

---

## 3. Priority and Batching Logic

*This section is final except for the batch window default in §3.2, which depends on the DAU/MAU ratio confirmation in §9.*

### 3.1 Two-Tier Priority Schema

We use a two-tier schema: **Critical** and **Standard**.

A three-tier schema adds implementation complexity — separate queue configurations, additional routing logic, more conditional branches in the worker — that is not justified at 10M MAU with a 4-person team. More importantly, a middle "High" tier creates classification disputes at the product level ("is a reply to my comment High or Standard?") that consume engineering and product time without improving user experience. The operationally meaningful distinction is: "wake the user up if necessary" versus "deliver efficiently when convenient." Two tiers map cleanly onto that distinction.

**Critical:**
- Security events (password reset, new device login, 2FA)
- Direct messages from connections
- Mentions in comments or posts
- System alerts (account suspension, content removal)

*Delivery target: < 5 seconds. All eligible channels dispatched in parallel. No batching. Quiet hours ignored.*

**Standard:**
- Likes, reactions, shares
- New followers
- Comment replies (non-mention)
- Digest summaries
- Re-engagement nudges

*Delivery target: < 2 minutes. Push attempted first; email batched into digest; in-app always written. Quiet hours enforced.*

**Runtime override:** Event-type classification is set at registration in the `event_type_registry` table. A privileged internal service account can override classification for a specific event instance, with the override logged to the audit table. Overrides are restricted to a defined allowlist of event types — for example, a viral post crossing a threshold might be upgraded to Critical. Override attempts outside the allowlist are rejected with a 403 and logged. This provides operational flexibility without opening arbitrary runtime reclassification.

### 3.2 Batching Logic

**Standard notifications are batched by recipient, not by event type.** The batcher collects Standard events for a given user over a configurable window (default: 15 minutes — *pending §9 DAU/MAU confirmation*) and either:

1. Sends a single push notification summarizing the batch ("You have 5 new likes and 2 new followers"), or
2. Holds for the next email digest if the user has push disabled and email digests enabled.

**Batching is skipped when:**
- The user has an active in-app session (deliver immediately via WebSocket)
- The batch window would push delivery past the user's