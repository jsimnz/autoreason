# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3 — Addressing Structural and Arithmetic Criticisms

---

## Revision Notes

This revision addresses ten criticisms of Revision 2. Each is either fixed or, where a genuine tradeoff exists, explicitly acknowledged as such with a stated position.

**Summary of changes:**

1. The spike model now uses actual exponential decay arithmetic. The "front-loaded" correction in Revision 2 was cosmetic — it described an exponential shape and computed a uniform rate. The revised model integrates the decay function to produce time-varying enqueue rates, and the queue depth arithmetic reflects that shape. The 34-minute figure is revised to 37 minutes as a result.

2. The 100 notifications/sec per worker figure is now derived from first principles with a latency budget breakdown. It is still an estimate, but it is a reasoned estimate with explicit assumptions and a pre-launch validation requirement.

3. The high-priority SLA analysis is corrected. The prior version used the post-reallocation processing rate for the full 90-second window, including the period before the reallocation trigger fires. The corrected analysis uses pre-reallocation rates for the detection window and post-reallocation rates thereafter. The corrected worst-case is 4.1 minutes, which violates the 3-minute SLA. The SLA is revised to 5 minutes with a product sign-off requirement, or the worker count is increased. Both options are specified; the decision is flagged as open.

4. The dynamic reallocation mechanism is now fully specified. The truncated code in Revision 2 is completed. The second-spike-mid-drain failure mode is analyzed explicitly with queue depth arithmetic.

5. The token bucket starvation prevention mechanism is now fully specified with fill rate, bucket capacity, and minimum throughput guarantee. The interaction with the 70% high-priority reallocation during spike conditions is addressed directly.

6. The in-app session race condition is acknowledged. The routing logic is revised to use a pending-delivery store with a reconciliation path rather than treating session state at routing time as a delivery guarantee.

7. The 3× burst multiplier validation commitment now has a specific pass/fail criterion, a decision owner, and a hard deadline relative to the production rollout date.

8. The email reach contradiction is resolved. The calculation base is now explicitly stated as registered users with a separate DAU-based figure for volume calculations. The two populations are not conflated.

9. The token bucket / worker reallocation interaction is now addressed in a dedicated subsection rather than leaving the two mechanisms to coexist without analysis.

10. No section claims a problem is resolved in the revision notes unless the resolution appears in the body text. Where a problem is partially resolved, the revision note says so.

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue implemented as a single Redis sorted set with priority-weighted scores, augmented with a token bucket mechanism to prevent standard-priority starvation. The token bucket parameters are specified in §2.3. The interaction between the token bucket and spike-time worker reallocation is analyzed in §2.4. These are not described as separate mechanisms that happen to coexist — they are analyzed together because they have to work together.

**Revised worst-case delay for standard-priority notifications: 37 minutes.** The prior 34-minute figure used a front-loaded arrival shape that was described as exponential decay but computed as a uniform rate. The corrected model integrates an actual exponential decay function. The arithmetic is in §1.1.2.

**Revised high-priority SLA: 5 minutes.** The prior 3-minute SLA was based on a calculation error — it applied post-reallocation processing rates to the pre-reallocation window. The corrected worst-case is 4.1 minutes. This either requires a 5-minute SLA (product sign-off required) or additional workers. The tradeoff is in §1.1.2. This is an open decision flagged for resolution before the spike injection test.

**On what this document does not cover:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications are out of scope. §7 is explicit about which in-scope systems are cut if the timeline proves wrong.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. The specific assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each called out explicitly with validation commitments that have pass/fail criteria, not just stated intentions.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU across app types; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS, different network density. Used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

**The opt-in rate problem and the silent drop problem:**

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. This creates a routing problem.

When a user hasn't opted into push, the notification does not automatically route to another channel. It routes to another channel only if: (1) the user has a verified email address and hasn't unsubscribed, and the notification type is configured for email fallback, and the user's preference configuration allows email for this notification type; or (2) the user is in an active session. If none of these conditions are met, the notification is dropped.

**This is a product correctness problem, not a provisioning problem.** The system must not silently drop notifications without audit.

**Revised routing logic with session race condition handling:**

The prior draft set `fate = "attempted"` when `user.is_active_session` was true at routing time. This creates a race condition: if the session ends between routing and delivery, the in-app notification is lost and the audit record incorrectly shows "attempted." The revised approach writes a pending-delivery record and reconciles on delivery confirmation or session-end event.

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
        # Do not mark fate="attempted" here based on session state alone.
        # Write a pending-delivery record; reconcile on delivery ACK or
        # session-end event, whichever arrives first.
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

**What this does not fully solve:** If the session-end event itself is lost (e.g., client disconnects without a clean close), the pending record expires at `SESSION_DELIVERY_WINDOW_SECONDS` without reconciliation. The expiry path must also write an audit record. This is specified in the pending store implementation in §3.2.

**Notification fate audit requirement:** A daily report of dropped notifications by reason (no push token, push not opted in, no email, email unsubscribed, session ended before delivery, pending record expired, all channels blocked) is required before launch. Drop rate is a product metric.

**Revised channel reach accounting:**

| Channel | Population Base | Assumed Reach | Volume Base for Calculations |
|---|---|---|---|
| Push | DAU (3M base case) | 52% of DAU = 1.56M reachable | DAU |
| In-app | Active session users | Unknown; session-length dependent | Not used in volume totals |
| Email | Registered users (10M MAU) | 50% at launch = 5M reachable | Registered users |
| SMS | Auth/security events only | Not reach-limited | Event count, not user count |

**Note on conflation of registered users and DAU:** The prior draft used these populations interchangeably in reach calculations. They are different. Email reach of 50% of 10M registered users = 5M users. Email reach of 50% of 3M DAU = 1.5M users. For volume calculations, the relevant figure is the number of notifications sent per day, which depends on how many active users receive email notifications — approximately 50% of DAU who have verified email and haven't unsubscribed. The volume calculations in §1.1.1 use DAU as the base for all channel volume estimates. Email reach relative to registered users is a deliverability and list-size metric, not a throughput metric.

#### 1.1.1 Engagement Tiers and Burst Multipliers

**Why burst multipliers are tier-differentiated:**

Notifications in a social app are triggered by social interactions. A denser, more active network produces more correlated activity — more users simultaneously active, larger follower graphs, viral events affecting more users simultaneously. This structural argument justifies higher burst multipliers at higher engagement tiers. The multipliers themselves remain judgment calls within the Firebase reference range.

**The base case 3× multiplier:** This is a judgment call consistent with the Firebase reference range (3–5×) but not derived from it. The validation commitment below has a specific pass/fail criterion and decision owner.

**Burst multiplier validation commitment:**

- **Test:** Spike injection test injecting 3× and 4× sustained primetime rate for 10 minutes against the staging environment before production rollout.
- **Pass criterion:** At 3× spike, high-priority queue depth returns to baseline within 8 minutes of spike end; standard-priority queue depth returns to baseline within 45 minutes of spike end. P99 high-priority delivery latency does not exceed the agreed SLA (either 3 or 5 minutes — see §1.1.2 open decision) during the spike.
- **Fail criterion:** Any of the above thresholds are exceeded, or worker processes crash or become unresponsive during the test.
- **On failure:** Capacity plan is revised before production rollout begins. Specific revision: increase worker count by 50% and re-run the test. If the second test fails, per-channel queue architecture is evaluated against the timeline constraint.
- **Decision owner:** Engineering lead for the notification system.
- **Deadline:** Spike injection test must pass at least 3 weeks before the production rollout date to allow time for capacity revision if needed.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 |

High and top-quartile figures are planning inputs for future architectural decisions, not targets for the current system. At 26,000/sec sustained, per-channel queues are required. At 67,500/sec, the architecture changes substantially. Transition monitoring is specified below.

**DAU/MAU monitoring:**

- DAU/MAU ratio computed daily from analytics pipeline.
- 7-day rolling average alert at 35%: base→high transition; 24-hour runbook initiation SLA.
- 7-day rolling average alert at 55%: high→top-quartile transition; 6-week architectural lead time begins.
- Alert routes to on-call engineer and engineering manager; 4-hour acknowledgment SLA.

#### 1.1.2 Peak Provisioning and Spike Scenario Analysis

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** 50% of daily volume in a 3-hour window.

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Burst capacity target:** 2,360 × 3 = ~7,080/sec, provisioned at **8,000/sec** with ~13% margin.

---

**Worker throughput derivation:**

The prior draft used 100 notifications/sec per worker without justification. This figure determines whether the entire spike analysis is valid. Here is the derivation.

A worker processes one notification at a time in a tight loop. The per-notification latency budget:

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | Single-key operation on local Redis; p99 on well-provisioned instance |
| Preference lookup (Redis cache hit) | 0.5ms | User preference cached; cache miss adds ~5ms for DB read (rare path) |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call (push/email) | 15–40ms | Network round-trip to FCM/APNs/SES; dominant cost |
| Audit log write (async, non-blocking) | ~0ms | Fire-and-forget to local buffer; flushed in background |
| **Total per notification** | **~16–41ms** | **Dominated by provider API call** |

At 20ms average per-notification latency (midpoint of provider call range), a single-threaded worker processes ~50 notifications/sec. At 10ms (optimistic), 100/sec. At 40ms (pessimistic), 25/sec.

**The 100/sec figure is the optimistic case.** The base case for capacity planning uses 50/sec per worker, which requires 100 workers to sustain 5,000/sec. Using 50/sec is the conservative assumption; the spike injection test will measure actual per-worker throughput and revise the worker count if needed.

**Revised worker pool sizing:** 100 workers at 50 notifications/sec each = 5,000/sec total capacity. This is unchanged from the prior draft's stated capacity but the justification is now explicit: we are using the midpoint of the provider latency range, not the optimistic case, as the planning assumption.

**Pre-launch validation requirement:** The spike injection test must measure actual per-worker throughput against the staging FCM/APNs sandbox. If observed throughput is below 40/sec per worker, the worker count is increased to 125 before production rollout.

---

**Revised spike scenario with actual exponential decay:**

The prior draft claimed an exponential decay arrival shape but computed a uniform average rate of 14,000/sec over the first 90 seconds. Exponential decay means the instantaneous rate is highest at t=0