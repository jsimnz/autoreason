# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Executive Sponsor:** Priya Anand, VP Engineering
**Engineering Lead:** Alex Chen
**Product Lead:** Jordan Rivera

---

## Document Status

This document contains two categories of content that must be kept distinct: **architecture decisions** that are independent of usage profile assumptions, and **sizing calculations** that depend on validated metrics.

Architecture decisions — channel selection, priority schema, delivery logic, infrastructure choices, failure handling — are finalized and ready for implementation planning. They do not change whether DAU/MAU is 15% or 60%.

Sizing calculations — server counts, queue depths, Redis cluster configuration, WebSocket instance counts, SMS cost projections — use a baseline assumption set (§1.1) and must be recalculated before infrastructure is provisioned. §1.1.3 provides the recalculation procedure. The two open decisions in §9 affect sizing only, not architecture.

**What this means in practice:** Engineering can begin implementation work on all sections immediately. Infrastructure provisioning requires §9 resolution. These are different activities with different timelines.

**Two governance items require resolution before specific paths go to production:**

1. **§9 open decisions** (DAU/MAU ratio and geographic distribution): Target resolution 14 days from issue date. No infrastructure should be provisioned until resolved.

2. **Parallel dispatch sign-off (§2.1):** The decision to use parallel multi-channel dispatch for Critical notifications carries real cost and UX consequences — including SMS cost implications not previously captured in cost projections. This decision requires explicit sign-off from Jordan Rivera (Product Lead) with a recorded date before the Critical notification path goes to production. The placeholder in §2.1 must be replaced with a confirmed date and approval record.

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

10M monthly active users. The numbers below are planning assumptions derived from industry averages, not measurements. They must be validated against product analytics before infrastructure is provisioned. §1.1.3 shows how to recalculate all downstream sizing figures once real data is available.

**Two compounding unknowns drive all throughput calculations.** The DAU/MAU ratio and the events-per-DAU-per-day figure are independent variables that multiply together. Both are unknown at this stage. §1.1.1 and §1.1.2 treat them independently; §1.1.3 shows how to combine them.

| Metric | Value | Basis |
|---|---|---|
| Daily active users | ~3M | 30% DAU/MAU — provisional, see §1.1.1 |
| Notification events per DAU per day | ~15 | Industry average — provisional, see §1.1.2 |
| Daily notification volume | ~45M events | 3M × 15 |
| Average sustained throughput | ~520 events/second | 45M / 86,400s |
| Geographic concentration peak | ~1,040 events/second | 2.0× average — see §1.1.4 |
| Burst headroom ceiling | ~1,560 events/second | 3.0× average — infrastructure provisioning target |

**Critical distinction:** The geographic concentration peak (~1,040/sec) is the expected sustained maximum during evening traffic. The burst headroom ceiling (~1,560/sec) is the infrastructure provisioning upper bound — the number used to size queues and autoscaling limits. Do not provision to the geographic peak and assume burst is covered.

#### 1.1.1 DAU/MAU Sensitivity

The DAU/MAU ratio is the first multiplier in every throughput calculation, every server count, and every cost projection. It is borrowed from industry averages and is unknown until instrumented.

| DAU/MAU | DAU | Avg throughput | Geographic peak | Burst ceiling |
|---|---|---|---|---|
| 15% (content-discovery) | 1.5M | ~260/sec | ~520/sec | ~780/sec |
| 30% (baseline) | 3M | ~520/sec | ~1,040/sec | ~1,560/sec |
| 60% (messaging-heavy) | 6M | ~1,040/sec | ~2,080/sec | ~3,120/sec |

These figures assume 15 events/DAU/day. See §1.1.3 for combined sensitivity.

**Action required before infrastructure provisioning:** Product analytics must provide the observed or projected DAU/MAU ratio. If this is a greenfield launch with no historical data, provision for 30% with autoscaling configured to handle 60% without manual intervention.

#### 1.1.2 Events-per-DAU Sensitivity

The events-per-DAU-per-day figure is the second multiplier in all throughput calculations. It varies significantly by product type and is as uncertain as the DAU/MAU ratio.

| App type | Events/DAU/day | Basis |
|---|---|---|
| Content-discovery (likes, follows) | 5–8 | Low social graph density, passive consumption |
| General social (baseline assumption) | 15 | Mixed engagement and messaging |
| Messaging-heavy | 50–100 | Direct message threads, group chats |

This document assumes 15. A messaging-heavy product at 15 events/DAU/day is significantly underestimated. If the product roadmap includes real-time messaging, this assumption must be revisited before Phase 2 infrastructure is provisioned.

#### 1.1.3 Combined Sensitivity and Recalculation Procedure

The two unknowns compound. The table below shows burst ceiling (the infrastructure provisioning target) across the plausible range.

| | 5 events/DAU/day | 15 events/DAU/day | 50 events/DAU/day |
|---|---|---|---|
| 15% DAU/MAU | ~260/sec | ~780/sec | ~2,600/sec |
| 30% DAU/MAU | ~520/sec | ~1,560/sec | ~5,200/sec |
| 60% DAU/MAU | ~1,040/sec | ~3,120/sec | ~10,400/sec |

**Burst ceiling formula:**
```
(MAU × DAU/MAU ratio × events/DAU/day / 86,400) × 3.0 × geographic peak multiplier
```

When validated figures are available, substitute them into this formula and recalculate §7 directly. No other sections require recalculation — architecture decisions are independent of these figures.

**If launching without historical data:** Provision for the (30% DAU/MAU, 15 events/DAU) cell with autoscaling configured to reach the (60% DAU/MAU, 50 events/DAU) cell without manual intervention. The gap between these cells is the risk envelope.

#### 1.1.4 Peak Throughput and Geographic Concentration

| Case | Peak multiplier | Geographic peak |
|---|---|---|
| US-only | 2.0× average | ~1,040/sec (baseline) |
| US + Western Europe | 1.6× average | ~830/sec |
| Global, distributed | 1.3× average | ~675/sec |

Baseline uses 2.0× (US-centric). Infrastructure is provisioned to 3.0× (burst ceiling), not the geographic peak. If the product is genuinely global, infrastructure will be slightly over-provisioned — acceptable. If more concentrated than assumed, the numbers hold.

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

| Metric | Target | Derivation |
|---|---|---|
| Critical notification delivery (p99) | < 5 seconds end-to-end | Measured from event ingestion to channel dispatch |
| Standard notification delivery (p95) | < 2 minutes end-to-end | Measured from event ingestion to channel dispatch |
| Push delivery rate | > 95% of reachable devices | Reachable = valid token, not opted-out |
| Email delivery rate | > 98% (excluding hard bounces) | |
| System availability | 99.5% (< 44 hours downtime/year) | Derived from §6.4 failure mode analysis |
| User preference changes reflected | < 60 seconds | |

**On the availability target:** The 99.5% figure is derived from the failure mode analysis in §6.4, which enumerates failure probability and recovery time for each system component. The derivation appears there; this table reflects its output. If §6.4 is updated, this table is updated in the same commit.

The original draft stated 99.9%. That figure is not supportable given the dependency chain: SQS (99.9% SLA) → ElastiCache (99.9% SLA) → RDS Multi-AZ (99.95% SLA) → FCM/APNs (no formal SLA). A single-region deployment with these dependencies cannot achieve 99.9% end-to-end without redundancy that a 4-person team cannot maintain. 99.5% is honest. If 99.9% is a hard business requirement, the architecture requires multi-region deployment and the team constraint must be revisited before that target is committed to.

---

## 2. Delivery Channels

### 2.1 Channel Overview and Fallback Logic

Four channels are supported. Selection logic differs by priority tier. The key architectural choice — parallel versus sequential dispatch for Critical notifications — is described here in full because it has cost, complexity, and UX consequences that must be understood together before the decision is confirmed.

**For Critical notifications:** All eligible channels are dispatched in parallel simultaneously. Eligibility is determined before dispatch by checking opt-in status and device token validity.

**This is a deliberate product decision, not a default. It requires explicit sign-off from Jordan Rivera (Product Lead) with a recorded date before the Critical notification path goes to production.**

*Pending product sign-off: Jordan Rivera, [DATE — required before production deployment of Critical notification path]*

**Rationale for parallel dispatch:**

1. Security events require acknowledged delivery, not just attempted delivery. Redundancy is correct behavior for "unrecognized device login" — a user who receives the same security alert via push, email, and SMS simultaneously understands something happened.
2. Push-only delivery for security events has a known failure mode: users with notification fatigue or disabled push permissions miss critical alerts entirely.
3. Sequential fallback with async push confirmation requires stateful tracking infrastructure disproportionate to this team size. See §2.1.1 for detail.

**SMS cost implication of parallel dispatch — requires explicit accounting:**

Parallel dispatch means every user registered for SMS receives an SMS for every Critical event, regardless of whether push or email delivered successfully. If 5% of the user base opts into SMS (500,000 users) and the average eligible user receives 2 Critical security events per month, that is 1,000,000 SMS messages per month — $50,000–70,000/month at $0.05–0.07/message — before any growth. This is materially different from a flat per-user estimate.

**The SMS cost projections in §7 must use this formula:**
```
SMS cost = (SMS-eligible users) × (expected Critical events per user per month) × (SMS unit cost)
```
Not a flat per-user estimate.

If this cost is unacceptable, the alternative is sequential dispatch with a defined fallback timeout: attempt push, wait a fixed interval (e.g., 10 seconds), then dispatch email and SMS if no delivery receipt is received. This reduces redundant SMS charges but requires stateful per-notification tracking. The tradeoff is implementation complexity versus ongoing cost. This choice must be made explicitly as part of the product sign-off above.

**Duplicate notification UX mitigation:** Notification copy for Critical events uses consistent action-oriented phrasing across all channels ("Action required: new device login detected") so that receiving multiple copies is unambiguous rather than confusing. This copy convention must be enforced in the `event_type_registry` template fields and audited before launch.

**For Standard notifications:** Push is attempted first. Email is batched into digests. In-app is always written. SMS is not used for Standard notifications. If push fails, the notification remains available in-app and in the next email digest. There is no real-time cross-channel fallback for Standard.

#### 2.1.1 Why Stateful Fallback Is Not Used

The "attempt push, fall back to email if not confirmed" model requires: persistent state per in-flight notification, a timeout mechanism, a reconciliation worker, and careful handling of the race between receipt arrival and timeout expiry. Push confirmation from FCM/APNs arrives asynchronously via a separate receipt queue. For Critical notifications, parallel delivery sidesteps this problem entirely. For Standard notifications, the digest model sidesteps it by design. Neither approach requires stateful fallback tracking.

| Channel | Use Case | Latency Target | Cost Per Message |
|---|---|---|---|
| Push (FCM/APNs) | Real-time engagement, mobile-first | < 5s | ~$0.00 (provider free tier) |
| In-app | Active session users, non-urgent | < 1s | $0.00 (internal) |
| Email | Digests, account events, re-engagement | < 5 min | ~$0.001 |
| SMS | Critical account security, explicit opt-in only | < 30s | ~$0.05–0.07 |

### 2.2 Push Notifications (FCM / APNs)

**Provider:** Firebase Cloud Messaging for Android, Apple Push Notification service for iOS. Both are fully managed. A 4-person team should not operate push infrastructure.

**Token management:**

Device tokens are soft-deleted after 90 days without a refresh. This interacts with a second invalidation path: FCM and APNs return an invalid-token error when a push is attempted to an uninstalled app, which triggers immediate hard-delete via the error-handling logic in §6.

The 90-day soft-delete exists for two reasons despite this second path:

1. **Suppressing unnecessary push attempts.** Stale tokens generate API calls that mostly fail. Processing error responses consumes worker capacity. Soft-delete reduces noise before it reaches the provider.
2. **Re-engagement boundary.** After 90 days of inactivity, re-engagement is handled via email, not push. Keeping stale tokens active causes push attempts to compete with email re-engagement sends, creating duplicate outreach with no additional value.

**Token registration: 5-device limit with explicit eviction policy**

A user may have up to 5 active device tokens. When a 6th token is registered, the token with the oldest `last_seen_at` timestamp among active tokens is evicted — not the oldest by registration date. This handles the common case where a user reinstalls the app: the reinstalled device has a recent `last_seen_at` even if first registered long ago, so the genuinely dormant token is evicted rather than the active one.

**Interaction with soft-delete:** Soft-deleted tokens do not count against the 5-device limit. A user who has been inactive for 90 days and reinstalls registers a new token without triggering eviction of any active tokens. The inactive token remains soft-deleted and is not reactivated.

**Concurrent registration edge case:** If two devices attempt to register simultaneously and both would be the 6th token, the database write uses a transaction with a row lock that reads current token count before inserting. One write succeeds; the other re-reads the updated count and applies eviction logic to the post-insert state. This is a low-frequency event but the locking behavior must be explicit in the implementation.

**Token management rules summary:**
- Tokens refreshed on each app open
- Stale tokens (no refresh in 90 days, configurable in `system_config`) soft-deleted and excluded from dispatch
- Invalid token responses from FCM/APNs trigger immediate hard-delete
- Soft-deleted tokens do not count against the 5-device limit
- 6th-device registration evicts the token with the oldest `last_seen_at` among active tokens
- Eviction uses a transactional read-then-write to handle concurrent registration

**The 90-day threshold is configurable** in the `system_config`