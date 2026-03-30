# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one for high-priority, one for standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. This replaces the prior single sorted set design. The tradeoff: two sets add modest operational overhead but eliminate the single-point-of-failure problem that the single-set design could not adequately address. Per-channel queues (four or more sets) remain out of scope; the operational overhead is still unjustified for a 4-engineer team at base-case load. The starvation mechanism governing how workers split between the two sets is specified in full in §2.3.

**Key figures — all figures below are sustained rates, not ceilings; §1.1.2 derives the ceiling and explains why it differs:**
- Base case: 51M notifications/day, ~2,360/sec sustained primetime
- Effective worker capacity: 3,500/sec sustained (100 workers × 35/sec, accounting for idle time, retry overhead, and dequeue wait; derivation in §1.1.2)
- Burst absorption: queue absorbs spikes; workers drain at 3,500/sec net of background load; queue does not clear before spike ends
- Worst-case standard-priority delay during a 3× spike: **~47 minutes** (revised upward from 37 minutes; arithmetic completed in §1.1.2)
- High-priority SLA: **8 minutes worst-case** (completed analysis in §1.1.2; prior 3- and 5-minute claims are retracted)

**Three open decisions requiring sign-off before the spike injection test:**
1. Standard-priority worst-case delay of 47 minutes: acceptable to product, or requires architectural change (additional workers or per-channel queues). Decision owner: product and engineering jointly.
2. High-priority worst-case delay of 8 minutes: acceptable, or requires dedicated high-priority worker pool. Decision owner: engineering lead.
3. PostgreSQL fallback queue during Redis outage: acceptable degraded mode (slower processing, no data loss), or requires Redis Cluster for higher availability. Decision owner: engineering lead.

**Pre-launch validation gate:** Spike injection test must measure actual per-worker sustained throughput. If observed throughput is below 30/sec per worker sustained over 10 minutes, the worker count scales linearly: 30/sec → 117 workers; 25/sec → 140 workers; 20/sec → 175 workers. The full response table is in §1.1.2. There is no single threshold below which the system is declared unacceptable; the response is continuous scaling.

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope systems are cut if the timeline proves wrong.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. They are not derived from those reference points. The specific assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each called out explicitly with validation commitments that have pass/fail criteria and decision owners.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 The Opt-In Rate Problem and Silent Drop Problem

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. This creates a routing problem.

When a user hasn't opted into push, the notification routes to another channel only if: (a) the user has a verified email address, hasn't unsubscribed, and the notification type is configured for email fallback; or (b) the user is in an active session. If neither condition holds, the notification is dropped.

**This is a product correctness problem, not a provisioning problem.** The system must not silently drop notifications without audit.

**Channel reach accounting — two distinct uses, kept separate:**

The following table separates throughput-relevant figures (used in §1.1.2 capacity calculations) from list-size figures (used for deliverability planning). Prior drafts conflated these in a single table. They are separated here because they answer different questions: throughput figures answer "how many notifications/sec must the system process?"; list-size figures answer "how large is our email suppression list, and what does deliverability look like at launch?"

**Throughput-relevant figures (all use DAU as base):**

| Channel | Population Base | Assumed Reach % | Reachable Users | Notifs/User/Day | Daily Volume |
|---|---|---|---|---|---|
| Push | 3M DAU | 52% | 1.56M | 17 | 26.5M |
| In-app | Active session users | Session-dependent | Not counted separately | — | Counted in push/email totals |
| Email | 3M DAU | 40% of DAU with verified email and not unsubscribed | 1.2M | 5 (email-eligible types only) | 6M |
| SMS | Auth events only | Not reach-limited | N/A | ~0.5 auth events/user/month | ~50K/day |

**List-size figures (use registered user base; not used in capacity calculations):**

| Channel | Registered Users | Estimated List Size | Purpose |
|---|---|---|---|
| Email | 10M MAU | 5M (50% with verified email) | Deliverability planning, suppression list sizing, IP warming schedule |

The 5M email list size is relevant for: deciding whether to use a dedicated IP (required above ~2M sends/day on shared IPs per SendGrid guidance), planning the IP warming ramp, and sizing the suppression list store. It is not used in any throughput calculation.

**Routing logic with session race condition handling:**

A naive implementation marks fate as "attempted" when `user.is_active_session` is true at routing time. This creates a race condition: if the session ends between routing and delivery, the in-app notification is lost and the audit record incorrectly shows "attempted."

The correct approach writes a pending-delivery record before appending the in-app channel, and reconciles on delivery confirmation or session-end event, whichever arrives first. The pending store design — including storage estimates, SESSION_DELIVERY_WINDOW_SECONDS definition, and expiry path — is specified in §3.2. The routing code below depends on that design; do not treat the routing logic as complete without reading §3.2.

```python
def route_notification(user_id, notification):
    channels = []
    fate = "undelivered"

    if user.has_push_token and user.push_opted_in:
        channels.append("push")
        fate = "attempted"

    if notification.type in EMAIL_ELIGIBLE_TYPES:
        if user.email_verified and not user.email_unsubscribed:
            channels.append("email")
            fate = "attempted"

    if user.is_active_session:
        # Write the pending record BEFORE appending the channel.
        # If the write fails, do not append in_app — treat as if
        # no active session. This prevents the audit gap where
        # in_app is listed as a delivery channel but no record
        # exists to confirm or deny delivery.
        try:
            pending_store.write(
                notification_id=notification.id,
                user_id=user_id,
                channel="in_app",
                expires_at=now() + SESSION_DELIVERY_WINDOW_SECONDS
                # SESSION_DELIVERY_WINDOW_SECONDS defined in §3.2
            )
            channels.append("in_app")
            fate = "attempted"
        except PendingStoreWriteError:
            metrics.increment("notifications.pending_store.write_failure")
            # Fall through: in_app not added to channels.
            # If no other channel succeeded, fate remains "undelivered".

    if fate == "undelivered":
        audit_log.write(
            notification_id=notification.id,
            user_id=user_id,
            status="dropped",
            reason=classify_drop_reason(user)
        )
        metrics.increment(
            "notifications.dropped",
            tags=[f"reason:{classify_drop_reason(user)}"]
        )
        return

    dispatch(notification, channels)


def on_session_end(user_id):
    pending = pending_store.get_pending(user_id, channel="in_app")
    for record in pending:
        if not delivery_store.is_delivered(record.notification_id):
            audit_log.write(
                notification_id=record.notification_id,
                user_id=user_id,
                status="dropped",
                reason="session_ended_before_delivery"
            )
            metrics.increment(
                "notifications.dropped",
                tags=["reason:session_ended_before_delivery"]
            )
        pending_store.delete(record)
```

**Residual gap:** If the session-end event is lost (client disconnects without a clean close), the pending record expires at SESSION_DELIVERY_WINDOW_SECONDS without reconciliation. The expiry path writes an audit record with reason "pending_record_expired." This is specified in §3.2 and is not considered resolved here.

**Notification fate audit requirement:** A daily report of dropped notifications by reason — no push token, push not opted in, no email, email unsubscribed, session ended before delivery, pending record expired, all channels blocked — is required before launch. Drop rate is a product metric, not an operational metric.

### 1.1.2 Worker Throughput Model, Spike Analysis, and SLA Derivations

#### Worker Throughput: From Ceiling to Sustained Rate

Prior drafts derived 50/sec per worker from the latency budget and used that figure as a sustained rate throughout all arithmetic. This is wrong. 50/sec (or 100/sec at the optimistic end) is the ceiling for a perfectly saturated worker with no idle time, no retry overhead, and no dequeue wait. Sustained throughput is lower for three reasons:

**1. Dequeue wait (idle time between notifications)**

Workers use blocking ZPOPMIN with a timeout. When the queue is not fully loaded, a worker may wait up to the timeout before receiving a notification. During the spike, the queue is saturated and this term is near zero. During normal operation, workers spend some fraction of time idle. For capacity planning during a spike (the binding constraint), dequeue wait contributes approximately 0.5–1ms additional latency per notification cycle. We add 1ms to the latency budget as a conservative estimate.

**2. Retry overhead**

Provider API calls fail at some rate. FCM's documented error rate on well-formed requests is approximately 0.1–0.5%. Each retry adds one full provider API round-trip (15–40ms). At 0.3% retry rate, expected added latency per notification = 0.003 × 27.5ms (midpoint) ≈ 0.08ms. This is negligible individually but adds up across workers. More importantly, retries tie up a worker for a full additional round-trip. We model this as a 2% throughput reduction.

**3. Synchronization overhead and non-notification work**

Workers periodically flush their local audit log buffer, check for shutdown signals, and update metrics. We estimate this adds 1–2ms per notification cycle in aggregate.

**Revised latency budget:**

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | Single-key operation; p99 on well-provisioned instance |
| Dequeue wait (idle time) | 1ms | Conservative; near zero during spike |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss ~5ms, rare path |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call | 15–40ms | Dominant cost; FCM/APNs/SES |
| Retry overhead (amortized) | 0.6ms | 0.3% retry rate × 27.5ms midpoint × 2 retries |
| Synchronization/bookkeeping | 1.5ms | Audit flush, metrics, signal check |
| **Total** | **~19–45ms** | |

At the midpoint of 32ms, sustained throughput per worker = 1,000ms ÷ 32ms = **~31/sec**. Applying the 2% retry throughput reduction: **~30/sec per worker**.

At the optimistic end (19ms): ~53/sec. At the pessimistic end (45ms): ~22/sec.

**Sustained capacity planning uses 35/sec per worker** — slightly above the midpoint, rounded for arithmetic convenience, and validated against the spike injection test before production rollout. This is not a ceiling; it is the expected sustained rate under load.

**100 workers × 35/sec = 3,500/sec sustained processing capacity.**

**Pre-launch validation gate (revised):**

The spike injection test measures actual per-worker sustained throughput over a 10-minute window against the staging FCM/APNs sandbox. The response to observed throughput is a continuous scaling table, not a single pass/fail threshold:

| Observed Throughput/Worker | Workers Required for 3,500/sec | Action |
|---|---|---|
| ≥ 35/sec | 100 | No change |
| 30–34/sec | 103–117 | Scale to required count before rollout |
| 25–29/sec | 121–140 | Scale to required count; flag for architecture review |
| 20–24/sec | 146–175 | Scale to required count; schedule per-channel queue evaluation within 30 days |
| < 20/sec | > 175 | Stop rollout; convene architecture review before proceeding |

If observed throughput is below 20/sec, the bottleneck is likely not worker count but provider API latency (e.g., staging sandbox rate limits not representative of production). The architecture review must identify the bottleneck before scaling workers further.

---

#### Engagement Tiers and Burst Multipliers

**Why burst multipliers are tier-differentiated:** Notifications in a social app are triggered by social interactions. A denser, more active network produces more correlated activity — larger follower graphs, viral events affecting more users simultaneously. This structural argument justifies higher burst multipliers at higher engagement tiers. The multipliers themselves remain judgment calls within the Firebase reference range (3–5×).

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Instantaneous Peak |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500/sec |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~24,100/sec at t=0** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | — |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | — |

**Important:** The "burst multiplier" column describes the ratio of average spike rate to sustained rate. The instantaneous peak at t=0 is substantially higher due to the exponential arrival shape (see below). The 8,000/sec provisioning figure in prior drafts was derived from the average burst rate and does not represent meaningful burst protection against the instantaneous peak. This is addressed in §2 (queue design): the system is not designed to process the instantaneous peak in real time. It is designed to absorb the