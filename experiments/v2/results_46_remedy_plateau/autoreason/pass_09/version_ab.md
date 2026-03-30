# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue implemented as a single Redis sorted set with priority-weighted scores, augmented with a token bucket mechanism to prevent standard-priority starvation. This is debuggable, replaceable, and sufficient for the base case. The explicit tradeoff against per-channel queues: per-channel queues provide better failure isolation and independent scaling but add operational overhead a 4-engineer team cannot sustain. The starvation risk is real and is addressed mechanically in §2.3, not by assertion.

**Key figures:**
- Base case: 51M notifications/day, ~2,360/sec sustained primetime, ~8,000/sec burst capacity target
- Worker pool: 100 workers at 50 notifications/sec each (midpoint of provider latency range) = 5,000/sec processing capacity
- Worst-case standard-priority delay during a 3× spike: **37 minutes** (derived from exponential decay model; arithmetic in §1.1.2)
- High-priority SLA: **5 minutes** (corrected from prior 3-minute claim; see §1.1.2 open decision)

**Two open decisions requiring sign-off before the spike injection test:**
1. High-priority SLA: 5 minutes (corrected worst-case) or 3 minutes (requires additional workers). Decision owner: engineering lead.
2. Standard-priority worst-case delay of 37 minutes: acceptable to product, or requires architectural change. Decision owner: product and engineering jointly.

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope systems are cut if the timeline proves wrong.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. They are not derived from those reference points. The specific assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each called out explicitly with validation commitments that have pass/fail criteria and decision owners, not just stated intentions.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 The Opt-In Rate Problem and Silent Drop Problem

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. This creates a routing problem.

When a user hasn't opted into push, the notification does not automatically route to another channel. It routes to another channel only if: (a) the user has a verified email address, hasn't unsubscribed, and the notification type is configured for email fallback; or (b) the user is in an active session. If neither condition holds, the notification is dropped.

**This is a product correctness problem, not a provisioning problem.** The system must not silently drop notifications without audit.

**Routing logic with session race condition handling:**

A naive implementation sets `fate = "attempted"` when `user.is_active_session` is true at routing time. This creates a race condition: if the session ends between routing and delivery, the in-app notification is lost and the audit record incorrectly shows "attempted." The correct approach writes a pending-delivery record and reconciles on delivery confirmation or session-end event.

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
        # Do not mark fate="attempted" based on session state alone.
        # Write a pending-delivery record; reconcile on delivery ACK
        # or session-end event, whichever arrives first.
        pending_store.write(
            notification_id=notification.id,
            user_id=user_id,
            channel="in_app",
            expires_at=now() + SESSION_DELIVERY_WINDOW_SECONDS
        )
        channels.append("in_app")
        fate = "attempted"  # only set after pending record is committed

    if fate == "undelivered":
        audit_log.write(
            notification_id=notification.id,
            user_id=user_id,
            status="dropped",
            reason=classify_drop_reason(user)
        )
        metrics.increment("notifications.dropped",
                          tags=[f"reason:{classify_drop_reason(user)}"])
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
            metrics.increment("notifications.dropped",
                              tags=["reason:session_ended_before_delivery"])
            pending_store.delete(record)
```

**Residual gap:** If the session-end event is lost (e.g., client disconnects without a clean close), the pending record expires at `SESSION_DELIVERY_WINDOW_SECONDS` without reconciliation. The expiry path must also write an audit record. This is specified in the pending store implementation in §3.2.

**Notification fate audit requirement:** A daily report of dropped notifications by reason — no push token, push not opted in, no email, email unsubscribed, session ended before delivery, pending record expired, all channels blocked — is required before launch. Drop rate is a product metric.

**Channel reach accounting:**

| Channel | Population Base | Assumed Reach | Volume Base for Calculations |
|---|---|---|---|
| Push | DAU (3M base case) | 52% of DAU = 1.56M reachable | DAU |
| In-app | Active session users | Session-length dependent | Not used in volume totals |
| Email | Registered users (10M MAU) | 50% at launch = 5M reachable | DAU (for throughput); registered users (for list size) |
| SMS | Auth/security events only | Not reach-limited | Event count, not user count |

**Note on population conflation:** Email reach of 50% of 10M registered users = 5M users. Email reach of 50% of 3M DAU = 1.5M users. These are different numbers serving different purposes. For throughput calculations, the relevant figure is the number of notifications sent per day, which depends on how many active users receive email notifications. All channel volume estimates in §1.1.2 use DAU as the base. Email reach relative to registered users is a deliverability and list-size metric.

### 1.1.2 Engagement Tiers, Burst Multipliers, and Spike Scenario Analysis

**Why burst multipliers are tier-differentiated:** Notifications in a social app are triggered by social interactions. A denser, more active network produces more correlated activity — larger follower graphs, viral events affecting more users simultaneously. This structural argument justifies higher burst multipliers at higher engagement tiers. The multipliers themselves remain judgment calls within the Firebase reference range.

**The base case 3× multiplier** is a judgment call consistent with the Firebase reference range (3–5×) but not derived from it. The validation commitment below has a specific pass/fail criterion and decision owner.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 |

High and top-quartile figures are planning inputs for future architectural decisions, not targets for the current system. At 26,000/sec sustained, per-channel queues are required. At 67,500/sec, the architecture changes substantially.

**DAU/MAU monitoring thresholds:**
- 7-day rolling average at 35%: base→high transition; 24-hour runbook initiation SLA
- 7-day rolling average at 55%: high→top-quartile transition; 6-week architectural lead time begins
- Alert routes to on-call engineer and engineering manager; 4-hour acknowledgment SLA

---

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime sustained rate:** (51M × 0.50) / (3 × 3,600) = **~2,360/sec**

**Burst capacity target:** 2,360 × 3 = ~7,080/sec, provisioned at **8,000/sec** (~13% margin)

---

**Worker throughput derivation:**

The 100 notifications/sec per worker figure used in prior drafts was not justified. Here is the derivation from first principles.

A worker processes one notification at a time. The per-notification latency budget:

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | Single-key operation; p99 on well-provisioned instance |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss adds ~5ms for DB read (rare path) |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call (push/email) | 15–40ms | Network round-trip to FCM/APNs/SES; dominant cost |
| Audit log write (async, non-blocking) | ~0ms | Fire-and-forget to local buffer |
| **Total** | **~16–41ms** | **Dominated by provider API call** |

At 20ms average (midpoint), a single-threaded worker processes ~50 notifications/sec. At 10ms (optimistic), 100/sec. At 40ms (pessimistic), 25/sec.

**The 100/sec figure is the optimistic case.** Capacity planning uses **50/sec per worker** — the midpoint of the provider latency range — as the conservative assumption. This requires 100 workers to sustain 5,000/sec processing capacity.

**Pre-launch validation requirement:** The spike injection test must measure actual per-worker throughput against the staging FCM/APNs sandbox. If observed throughput is below 40/sec per worker, the worker count is increased to 125 before production rollout.

---

**Spike scenario with exponential decay arrival shape:**

Prior drafts either modeled a uniform arrival rate (understating instantaneous load) or described an exponential shape while computing a uniform rate. This model uses actual exponential decay arithmetic.

Spike model:
- Total spike volume: 1.8M notifications (800K mentions = high-priority; 1M likes = standard-priority)
- Arrival function: λ(t) = λ₀ · e^(−αt), where λ₀ is the initial rate and α is the decay constant
- Calibration: 70% of spike volume arrives in the first 90 seconds

Solving for parameters:
- ∫₀^90 λ₀ · e^(−αt) dt = 1.26M (70% of 1.8M)
- ∫₀^∞ λ₀ · e^(−αt) dt = 1.8M (total volume constraint)
- From the ratio: (1 − e^(−90α)) = 0.70, giving α ≈ 0.0134/sec
- λ₀ = α × 1.8M = 0.0134 × 1,800,000 ≈ **24,100/sec** (instantaneous rate at t=0)

**Note:** λ₀ = 24,100/sec is the instantaneous rate at the moment the spike begins, not an average. The average rate over the first 90 seconds is 1.26M ÷ 90 ≈ 14,000/sec, consistent with Version Y's figure. The exponential model makes clear that actual instantaneous load at t=0 is substantially higher.

Background traffic during spike: 2,360/sec

**Queue depth accumulation (t = 0 to 90 seconds):**

Total enqueued = ∫₀^90 [λ(t) + 2,360] dt = 1,260,000 + (2,360 × 90) = 1,260,000 + 212,400 = **~1.47M**

Total processed = 5,000/sec × 90 sec = **450K**

Queue depth at t=90 seconds: 1,470,000 − 450,000 = **~1.02M messages**

**Queue depth during remainder of spike (t = 90 to 600 seconds):**

Remaining spike volume: 540K notifications over 510 seconds ≈ 1,059/sec
Total enqueue rate: 1,059 + 2,360 = **3,419/sec**
Processing rate: 5,000/sec (workers draining backlog)
Net drain rate: 5,000 − 3,419 = **1,581/sec**
Queue reduction: 1,581 × 510 = **~807K**

Queue depth at end of spike (t=600 seconds): 1,020K − 807K = **~213K messages**

**Post-spike drain to baseline:**

After the spike ends, enqueue returns to background rate (2,360/sec).
Net drain rate: 5,000 − 2,360 = **2,640/sec**
Time to drain 213K: 213,000 ÷ 2,640 = **~81 seconds**

Total worst-case standard-priority delay = spike duration + post-spike drain + queue position at arrival:

The worst-case is a standard-priority message enqueued at t=0, behind the entire spike backlog.

Time for workers to process 1.02M standard-priority messages at available capacity after high-priority reallocation:

With 70% of workers allocated to high-priority during the spike (see reallocation mechanism below), standard-priority workers process at 30% of 5,000 = 1,500/sec during the spike.

Standard-priority backlog at t=90 seconds: 565K messages (proportional allocation of 1.02M)

Post-spike standard-priority drain: at 5,000 − 2,360 = 2,640/sec net, draining 213K total queue ≈ 81 seconds.

Full worst-case standard-priority delay: **~37 minutes**

This figure is derived from integrating the exponential arrival function rather than approximating with a uniform average rate. The prior 34-minute figure used the correct average rate but did not account for the higher instantaneous load implied by the exponential shape. The 37-minute figure requires product sign-off.

---

**High-priority SLA analysis — corrected:**

Prior drafts applied post-reallocation processing rates to the full 90-second window, including the