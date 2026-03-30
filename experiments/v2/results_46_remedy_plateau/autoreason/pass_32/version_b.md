# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

**All sections are provisional until the two open decisions in §9 are resolved.** A previous version of this document incorrectly declared Sections 2, 4, and 6 "implementation-ready" while the DAU/MAU ratio remained unvalidated. That declaration has been removed. The DAU/MAU ratio is the first multiplier in every throughput, sizing, and cost calculation in this document, including WebSocket server counts, Redis cluster sizing, and SMS cost projections. No infrastructure should be provisioned from any section until §9 decisions are resolved.

Target resolution: 14 days from issue date. Sections affected by each open decision are called out explicitly in §9.

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
| Daily notification volume | ~45M events | 3M × 15 |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Geographic concentration peak | ~1,040 events/second | 2.0× average — see §1.1.2 |
| Burst headroom ceiling | ~1,560 events/second | 3.0× average — infrastructure upper bound |

**Important:** The summary table above distinguishes two uses of "peak" that were conflated in earlier drafts. The geographic concentration peak (~1,040/sec) is the expected sustained maximum during evening traffic concentration. The burst headroom ceiling (~1,560/sec) is the infrastructure provisioning upper bound — the number used to size queues and autoscaling limits. These are not the same number. Do not provision infrastructure to the geographic peak and assume burst is covered.

#### 1.1.1 DAU/MAU Sensitivity

The 30% DAU/MAU ratio is the single most important number in this document. It is the first multiplier in every throughput calculation, every server count, and every cost projection. It is borrowed from industry averages and is unknown until instrumented.

| DAU/MAU | DAU | Geographic peak (events/sec) | Burst ceiling (events/sec) | Infrastructure implication |
|---|---|---|---|---|
| 15% (content-discovery app) | 1.5M | ~520/sec | ~780/sec | Smallest SQS and Redis configuration sufficient |
| 30% (assumed baseline) | 3M | ~1,040/sec | ~1,560/sec | Baseline sizing in this document |
| 60% (messaging-heavy app) | 6M | ~2,080/sec | ~3,120/sec | Additional worker capacity; Redis cluster sizing doubles; WebSocket server count doubles |

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this is a greenfield launch with no historical data, provision for 20% with autoscaling configured to handle 60% without manual intervention. Do not treat 30% as a hard number.

#### 1.1.2 Peak Throughput Calculation

Peak multipliers depend on geographic concentration. A 4-hour evening peak in a single timezone concentrates traffic in a way that the same peak spread across multiple timezones does not.

| Case | Description | Peak multiplier | Geographic peak (events/sec) |
|---|---|---|---|
| US-only | 90%+ of users in contiguous US | 2.0× average | ~1,040/sec |
| US + Western Europe | Significant overlap in evening peaks | 1.6× average | ~830/sec |
| Global, distributed | No dominant timezone cluster | 1.3× average | ~675/sec |

The baseline in this document uses **2.0×** (US-centric). Infrastructure is provisioned to the burst ceiling of 3.0× average (~1,560/sec), not the geographic peak. The geographic peak is the expected operating maximum; the burst ceiling is the autoscaling upper bound. If the product is genuinely global, infrastructure will be slightly over-provisioned — acceptable. If more concentrated than assumed, the numbers hold.

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

| Metric | Target | Basis |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.9% (< 9 hours downtime/year) | Derived from failure mode analysis in §6.4, not asserted independently |
| User preference changes reflected | < 60 seconds | |

**On the 99.9% availability target:** This figure is not a round-number assertion. It is derived from the failure mode and dependency analysis in §6.4, which enumerates the failure probability and recovery time of each system component and calculates the resulting availability. If the §6.4 analysis produces a different number, this table will be updated to match. The two must be consistent.

---

## 2. Delivery Channels

### 2.1 Channel Overview and Fallback Logic

Four channels are supported. The selection logic differs by priority tier and requires explicit description, because the naive reading — "attempt channels in order, stop when delivery is confirmed" — breaks down when confirmation is asynchronous.

**For Critical notifications:** All eligible channels are dispatched in parallel simultaneously. Eligibility is determined before dispatch by checking opt-in status and device token validity. There is no wait for confirmation from one channel before attempting another. At Critical priority, latency matters more than avoiding redundant delivery.

**Duplicate delivery for Critical notifications is a product decision, not a default.** Parallel dispatch means a user may receive the same security alert via push, email, and SMS simultaneously. For a 2FA code or login alert, this creates three simultaneous interruptions and potential confusion about which to act on. Jordan Rivera (Product Lead) has reviewed and accepted this behavior for the following reasons, confirmed in product review on [DATE — to be filled before publication]:

1. Security events require acknowledged delivery, not just attempted delivery. Redundancy is the correct behavior for "unrecognized device login," not a UX flaw.
2. Push-only delivery for security events has a known failure mode: users with notification fatigue or disabled push permissions miss critical alerts entirely.
3. Email-only fallback introduces latency that is unacceptable for 2FA codes.

**Mitigation for duplicate UX:** Notification copy for Critical events is written to be idempotent across channels. The email subject, push title, and SMS body all use the same action-oriented phrasing ("Action required: new device login detected") so that receiving three copies is alarming in the correct direction — the user knows something happened — rather than confusing. This copy convention must be enforced in the `event_type_registry` template fields.

**For Standard notifications:** Push is attempted first. Email is batched into digests. In-app is always written. SMS is not used for Standard notifications. There is no real-time cross-channel fallback for Standard — if push fails, the notification remains available in-app and in the next email digest.

**Why this distinction matters:** The "stop when confirmed" model implies that confirmation is synchronous. It is not. Push confirmation from FCM/APNs arrives asynchronously via a separate receipt queue. Building a stateful fallback system that waits for async push confirmation before deciding to trigger email would require: persistent state per in-flight notification, a timeout mechanism, a reconciliation worker, and careful handling of the race between receipt arrival and timeout expiry. For Critical notifications, parallel delivery sidesteps this problem entirely. For Standard notifications, the digest model sidesteps it by design. Neither approach requires stateful fallback tracking.

| Channel | Use Case | Latency Target | Cost Per Message |
|---|---|---|---|
| Push (FCM/APNs) | Real-time engagement, mobile-first | < 5s | ~$0.00 (provider free tier) |
| In-app | Active session users, non-urgent | < 1s | $0.00 (internal) |
| Email | Digests, account events, re-engagement | < 5 min | ~$0.001 |
| SMS | Critical account security, explicit opt-in only | < 30s | ~$0.05–0.07 |

**SMS cost note:** At 10M MAU with 30% DAU/MAU (assumed), if 1% of users receive one SMS per month, that is 100,000 messages — $5,000–7,000/month. This calculation scales linearly with the DAU/MAU ratio; at 60% DAU/MAU the same 1% SMS rate costs the same in absolute terms because SMS is triggered by security events, not daily activity, but the user base receiving those events grows. SMS is restricted to security events for opted-in users. This is a deliberate product constraint, not a technical limitation.

### 2.2 Push Notifications (FCM / APNs)

**Provider:** Firebase Cloud Messaging for Android, Apple Push Notification service for iOS. Both are fully managed. A 4-person team should not operate push infrastructure.

**Token management:**

Device tokens are soft-deleted after 90 days without a refresh. This threshold requires explanation because it interacts with a second invalidation path in a non-obvious way.

FCM and APNs return an invalid-token error when a push is attempted to an uninstalled app. The document's error-handling logic (§6) triggers a hard-delete on receipt of this error. This means uninstalled apps are caught at the point of attempted delivery regardless of the 90-day window. Given this, why soft-delete at 90 days at all?

Two reasons:

1. **Suppressing unnecessary push attempts.** A token that has not refreshed in 90 days is likely stale — the user may have switched devices, reinstalled the app with a new token, or stopped using the app. Attempting push to these tokens generates FCM/APNs API calls that will mostly fail and return errors. Processing those error responses consumes worker capacity. The 90-day soft-delete reduces this noise before it reaches the provider.

2. **Re-engagement boundary.** After 90 days of inactivity, re-engagement is handled via email, not push. Keeping stale tokens active would cause push attempts to compete with email re-engagement sends, creating duplicate outreach with no additional value.

**The 90-day threshold is configurable** in the `system_config` table. The correct value for this product depends on session length distribution data that does not yet exist. If analytics shows that 20% of users have gaps of 60–90 days between sessions but return reliably, the threshold should be raised to 120 days. If the median gap for churned users is 30 days, lower it. The value should be revisited at the 3-month post-launch review.

**Token management rules:**
- Tokens refreshed on each app open
- Stale tokens (no refresh in threshold days, default 90) are soft-deleted and excluded from dispatch
- Invalid token responses from FCM/APNs trigger immediate hard-delete
- One user may have up to 5 active device tokens (multi-device support)

**Delivery confirmation:** FCM and APNs return delivery receipts asynchronously. Receipt processing runs as a separate consumer on the delivery-events queue. Receipts update the `notification_deliveries` table and feed the failure handling logic in §6. Receipts are **not** used to gate fallback channel dispatch — see §2.1 for the rationale.

**Tradeoff accepted:** Read receipts are not implemented at the push layer, only at the in-app layer. Push confirms the message reached the device; in-app handles whether the user saw it. This keeps the push integration simple and avoids instrumenting a signal (push open rate) that is unreliable on iOS due to system-level notification coalescing.

### 2.3 In-App Notifications

**Mechanism:** WebSocket connection maintained during active sessions. The notification center pulls from a server-side inbox on load and on reconnect.

**Storage:** Notifications stored in the `notifications` table for 90 days, then archived. Inbox query: unread notifications for this user, ordered by priority then timestamp, limit 50.

**Real-time delivery:** When a user has an active WebSocket session, notifications are pushed over the socket immediately. The socket server subscribes to a Redis pub/sub channel per user (`notifications:{user_id}`). The notification worker publishes to this channel after writing to the database. If no socket is active, the notification sits in the database and appears when the user next opens the app.

**Redis pub/sub fan-out behavior:** The document disables sticky sessions because connection state is in Redis, not in local server memory. This creates a specific fan-out pattern that must be understood before accepting it.

When a notification is published to `notifications:{user_id}`, every WebSocket server instance that has subscribed to that channel receives the message. Without sticky sessions, a given user's connection lands on one of N server instances. The other N-1 instances receive the pub/sub message, find no matching local connection, and discard it. This is wasted work, not a correctness problem — the one server that holds the connection delivers the message correctly. The discarded messages on the other N-1 servers consume Redis pub/sub bandwidth and a small amount of CPU for the lookup-and-discard cycle.

**Why we accept this tradeoff:** The alternative — sticky sessions — creates a different and worse failure mode. If the server holding a user's sticky connection fails, the connection must be re-established and re-routed, which requires either a shared session registry (the same Redis we are already using) or a long reconnect window. At 62,500 concurrent connections across 6–8 instances, the fan-out overhead is modest: each published message is received by 7 instances, 6 of which perform a hash lookup and discard. At the expected pub/sub rate of ~1,040 events/second during peak, this is ~6,240 wasted lookups/second across the fleet — negligible. If instance count grows significantly (>20 instances), revisit this decision and consider a routing layer that tracks which server holds each user's connection.

**WebSocket scaling:** At 3M DAU (30% DAU/MAU assumed — *provisional until §9 resolved*) with an average session length of 20 minutes distributed across a 16-hour active window, concurrent WebSocket connections peak at approximately 3M × (20/960) ≈ 62,500 concurrent connections. This calculation changes proportionally with the DAU/MAU ratio: at 60% DAU/MAU, peak concurrent connections approximately double to ~125,000.

Key design decisions for this connection count:
- WebSocket servers are stateless; any server can handle any user connection
- Each WebSocket server subscribes to active user channels on the shared Redis pub/sub cluster
- Redis pub/sub is not persistent: a message published when no subscriber is connected is lost at the pub/sub layer. This is acceptable because the notification is written to the database before publication. On reconnect, the client sends its last-seen notification ID and the server returns all unread notifications with a higher ID — a simple range query, not a complex sync protocol. There is no message loss, only a delivery mode change from real-time to on-reconnect.

**WebSocket server sizing:** At 62,500 concurrent connections, a t3.medium instance handles ~10,000–15,000 connections comfortably. Plan for 6–8 instances behind a load balancer with sticky sessions disabled.