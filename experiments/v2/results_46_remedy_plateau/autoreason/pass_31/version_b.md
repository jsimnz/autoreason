# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

**Draft — Pending Resolution of Open Decisions**

This document is not implementation-ready. Two open decisions in §9 must be resolved before §3 (batching) and §5 (infrastructure sizing) are finalized. Sections that do not depend on those decisions (§2, §4, §6) may proceed to implementation review in parallel. The distinction between what is final and what is blocked is called out explicitly in each section.

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

10M monthly active users. The numbers below are planning assumptions, not measurements. They must be validated against actual product analytics before infrastructure is provisioned. The sensitivity of downstream sizing to the DAU/MAU ratio is analyzed explicitly in §1.1.1.

| Metric | Value | Basis |
|---|---|---|
| Daily active users | ~3M | 30% DAU/MAU — see §1.1.1 |
| Notification events per DAU per day | ~15 | Likes, comments, follows, messages, system alerts |
| Peak daily notification volume | ~45M events | 3M × 15 |
| Peak hourly volume | ~5.6M events | See §1.1.2 |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Peak throughput | ~1,560 events/second | See §1.1.2 |

#### 1.1.1 DAU/MAU Sensitivity

The 30% DAU/MAU ratio is borrowed from industry averages for social apps. The actual ratio for this product is unknown until we have instrumented data. The ratio matters because it is the first multiplier in every throughput calculation.

| DAU/MAU | DAU | Peak events/sec | Infrastructure implication |
|---|---|---|---|
| 15% (content-discovery app) | 1.5M | ~780/sec | Smallest SQS configuration sufficient |
| 30% (assumed baseline) | 3M | ~1,560/sec | Baseline sizing in this document |
| 60% (messaging-heavy app) | 6M | ~3,120/sec | Requires additional worker capacity; Redis cluster sizing doubles |

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this product has no historical data (greenfield launch), use 20% for initial provisioning with autoscaling configured to handle 60% without manual intervention. Do not use 30% as a hard number.

#### 1.1.2 Peak Throughput Calculation

The earlier draft used "2.5× average during 6–10 PM local time" to derive peak hourly volume. This is wrong for a global user base. A 4-hour evening peak in a single timezone concentrates traffic; the same peak smeared across multiple timezones does not.

**Geographic concentration assumption:** This calculation must be revisited based on the actual user geography. Three cases:

| Case | Description | Peak multiplier | Peak events/sec |
|---|---|---|---|
| US-only | 90%+ of users in contiguous US (3 timezone spread) | 2.0× average | ~1,040/sec |
| US + Western Europe | Significant overlap in morning/evening peaks | 1.6× average | ~830/sec |
| Global, distributed | No dominant timezone cluster | 1.3× average | ~675/sec |

The baseline sizing in this document uses **2.0×** (US-centric case), producing ~1,040 events/second sustained peak and ~1,560 events/second for burst headroom at 3× average. This is the conservative assumption. If the product is genuinely global, infrastructure is slightly over-provisioned, which is acceptable. If the product is more concentrated than assumed, the numbers hold.

**Action required:** Engineering must obtain geographic distribution of users from the product team before finalizing §7 capacity planning.

### 1.2 Team Constraints

Four backend engineers, six months. This is the binding constraint on every architectural decision in this document. Wherever a tradeoff appears, the default choice favors operational simplicity over theoretical optimality.

**Explicit scope exclusions given team size:**
- No custom ML-based send-time optimization (use fixed quiet hours instead)
- No real-time A/B testing framework for notification copy
- No multi-region active-active deployment (single region with warm standby — RTO and RPO defined in §6.4)
- No custom SMS aggregator integration (use Twilio managed service)
- No three-tier priority schema (rationale in §3.1)

### 1.3 Success Criteria

| Metric | Target | Notes |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.9% | Analysis in §6.4 |
| User preference changes reflected | < 60 seconds | |

---

## 2. Delivery Channels

### 2.1 Channel Overview and Fallback Logic

Four channels are supported. The selection logic differs by notification priority and requires explicit description because the naive reading ("stop when delivery is confirmed") breaks down when confirmation is asynchronous.

**For Critical notifications:** All eligible channels are attempted in parallel simultaneously. "Eligible" is determined before dispatch by checking user opt-in status and device token validity. There is no wait for confirmation from one channel before attempting another — at Critical priority, latency matters more than avoiding redundant delivery. Users may receive the same critical notification via both push and email; this is acceptable and expected.

**For Standard notifications:** Push is attempted first. Email is batched into digests on a configurable window. In-app is always written. SMS is not used for Standard notifications. There is no cross-channel fallback for Standard — if push fails, the notification remains available in-app and in the next email digest. The system does not attempt to detect push failure and trigger email in real time for Standard events; the complexity of asynchronous confirmation tracking is not justified for non-critical content.

**Why this distinction matters:** The earlier design described "stop when delivery is confirmed" as if confirmation were synchronous. Push confirmation from FCM/APNs is asynchronous and arrives via a separate receipt queue. Building a stateful fallback system that waits for async push confirmation before deciding to send email would require: persistent state per in-flight notification, a timeout mechanism, a reconciliation worker, and careful handling of the race between receipt arrival and timeout expiry. This is a non-trivial distributed systems problem. For Critical notifications, parallel delivery sidesteps it entirely. For Standard notifications, the digest model sidesteps it by design.

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

**Tradeoff:** Read receipts are not implemented at the push layer, only at the in-app layer. Push confirms the message reached the device; in-app handles whether the user saw it. This is acceptable and keeps the push integration simple.

### 2.3 In-App Notifications

**Mechanism:** WebSocket connection maintained during active sessions. The notification center pulls from a server-side inbox on load and on reconnect.

**Storage:** Notifications stored in the `notifications` table for 90 days, then archived. Inbox query: unread notifications for this user, ordered by priority then timestamp, limit 50.

**Real-time delivery:** When a user has an active WebSocket session, notifications are pushed over the socket immediately. The socket server subscribes to a Redis pub/sub channel per user (`notifications:{user_id}`). The notification worker publishes to this channel after writing to the database. If no socket is active, the notification sits in the database and appears when the user next opens the app.

**WebSocket scaling:** At 3M DAU with an average session length of 20 minutes and sessions distributed across a 16-hour active window, concurrent WebSocket connections peak at approximately 3M × (20/960) ≈ 62,500 concurrent connections. Each connection requires a pub/sub subscription on the Redis cluster.

Redis pub/sub at this channel count is manageable on a standard ElastiCache cluster, but requires explicit design decisions:

- WebSocket servers are stateless; any server can handle any user connection
- Each WebSocket server instance maintains its own set of active user subscriptions on the shared Redis pub/sub cluster
- When a notification is published to `notifications:{user_id}`, it is received by whichever server instance holds that user's connection
- Redis pub/sub is not persistent: if no subscriber is connected when a message is published, the message is lost at the pub/sub layer. This is acceptable because the notification has already been written to the database before publication. When the user reconnects, the WebSocket server fetches unread notifications from the database. There is no message loss, only a delivery mode change (real-time → on-reconnect)
- Reconciliation on reconnect: the client sends its last-seen notification ID; the server returns all unread notifications with ID greater than that value. This is a simple range query, not a complex sync protocol

**WebSocket server sizing:** At 62,500 concurrent connections, a single t3.medium instance handles ~10,000–15,000 WebSocket connections comfortably. Plan for 6–8 instances behind a load balancer with sticky sessions disabled (connection state is in Redis, not local). Auto-scaling on connection count with a target of 70% capacity per instance.

**Read state:** Marked read when the user opens the notification center or taps a specific notification. Read events are batched and written every 30 seconds to avoid per-tap database writes.

### 2.4 Email

**Provider:** Amazon SES.

**Deliverability commitment:** Choosing SES is a cost decision ($0.10/1,000 vs. $0.80–1.00/1,000 for SendGrid or Postmark). The deliverability tradeoff is real and must be managed actively:

- SES requires the team to configure and monitor SPF, DKIM, and DMARC records at launch. These are not optional.
- SES bounce and complaint rates must be monitored continuously. AWS will pause sending if the bounce rate exceeds 5% or complaint rate exceeds 0.1%. This is an operational responsibility, not a set-and-forget configuration.
- A dedicated sending IP should be provisioned from day one. Shared IP reputation is unpredictable at 10M MAU volumes.

**Switching providers is not low-cost.** If SES deliverability becomes a problem, migrating to SendGrid or Postmark requires: exporting and importing suppression lists (SES suppression list format is not directly compatible with other providers), re-configuring SPF/DKIM/DMARC DNS records, rebuilding bounce and complaint webhook integrations, and warming up a new sending IP — typically a 4–6 week process during which deliverability is degraded. The team should treat SES deliverability as a first-class operational concern rather than assuming migration is a simple fallback.

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

**Scope:** SMS is sent only for security events, and only to users who have explicitly opted in with a verified phone number:
1. Password reset (when no push token exists or user explicitly requests SMS)
2. Login from unrecognized device
3. Two-factor authentication codes

**Opt-in and routing interaction:** SMS requires explicit opt-in with a verified phone number. This creates a routing precondition that must be resolved before channel dispatch, not inside it. The channel eligibility check — performed before any dispatch begins — excludes SMS from the eligible channel set for users who have not opted in. Users without SMS opt-in receive push and/or email for security events, with an in-app prompt to add and verify a phone number.

This means the parallel dispatch for Critical notifications (§2.1) operates on the user's eligible channel set, which may or may not include SMS. The eligibility check reads from the preference cache (§4.2) and is the same check used to determine push token validity. No conditional logic exists inside the channel routers themselves — eligibility is resolved upstream.

---

## 3. Priority and Batching Logic

### 3.1 Two-Tier Priority Schema

We use a two-tier schema: **Critical** and **Standard**.

A three-tier schema adds implementation complexity — separate queue configurations, additional routing logic, more conditional branches in the worker — that is not justified at 10M MAU with a 4-person team. The operationally meaningful distinction is: "wake the user up if necessary" versus "deliver efficiently when convenient." Two tiers map cleanly onto that distinction. A middle "High" tier creates classification disputes at the product level that consume engineering and product time without improving user experience.

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

*Delivery target: < 2 minutes. Push attempted; email batched into digest; in-app always written. Quiet hours enforced.*

**Runtime override:** Event-type classification is set at registration in the `event_type_registry` table. A privileged internal service account can override classification for a specific event instance, with the override logged to the audit table. Overrides are restricted to a defined allowlist of event types. Override attempts outside the allowlist are rejected with a 403 and logged.

### 3.2 Batching Logic

**Standard notifications are batched