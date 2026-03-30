# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural Criticisms

---

## Revision Notes

This revision addresses ten substantive criticisms of the prior draft. Each section that changed notes what changed and why. Sections that are substantially new are marked **[NEW]**. The prior draft's executive summary claimed several things were "fully specified" in sections that either didn't exist in the visible text or were underspecified. This revision either specifies them or explicitly downgrades the claim.

**Summary of changes:**

1. Dynamic reallocation mechanism is now fully specified with a concrete implementation and failure mode analysis — including what happens when a second spike arrives mid-drain.
2. The spike scenario is replaced with a front-loaded arrival shape. The 28-minute figure no longer holds; the revised worst-case is 34 minutes, derived from the corrected model.
3. Standard-priority starvation prevention is now specified as a token bucket mechanism with a concrete minimum throughput guarantee.
4. The opt-in rate / silent drop problem is acknowledged as a product correctness issue, not a provisioning detail, with explicit routing logic and a "notification fate" audit requirement.
5. The 3× base case burst multiplier is no longer attributed to an uncited source. It is presented as an assumption with a specific validation commitment.
6. The abort criterion is redesigned. The sliding-window-reset-on-trigger logic is replaced with a fixed-window counter that does not reset on trigger events.
7. Three Redis deployments are replaced with one cluster with logical separation and explicit failure mode tradeoffs.
8. The in-app deduplication mechanism is now specified in full, including the split-brain scenario.
9. §7 now exists and contains an actual feasibility argument with named engineers, sequencing, and an honest assessment of what gets cut if the timeline is wrong.
10. Email deliverability for a new sender is treated as a launch-critical risk with a specific mitigation plan.

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue implemented as a single Redis sorted set with priority-weighted scores, augmented with a token bucket mechanism to prevent standard-priority starvation. This is debuggable, replaceable, and sufficient for the base case. The tradeoff against per-channel queues is explicit: per-channel queues provide better failure isolation and independent scaling but add operational overhead a 4-engineer team cannot sustain. The starvation risk is real and is now addressed mechanically, not by assertion.

**What has changed from the prior draft and why:**

The prior draft contained several claims that were stated as solved but not demonstrated. The most significant: the dynamic worker reallocation mechanism was described in one sentence with no specification; the spike scenario was constructed with a convenient arrival shape that understated instantaneous load; standard-priority starvation had no prevention mechanism; and three Redis deployments were presented as architecturally clean without accounting for their operational cost. These are not editorial gaps — they are design gaps that would produce failures in production. This revision closes them.

**Revised worst-case delay for standard-priority notifications: 34 minutes.** The prior 28-minute figure assumed a uniform spike arrival rate. A front-loaded spike shape — which is what viral posts actually produce — generates a higher instantaneous enqueue rate that temporarily exceeds worker capacity even for high-priority messages during the first 90 seconds. The corrected figure is 34 minutes. The arithmetic is in §1.1.2. Product sign-off is required.

**On what this document does not cover:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications are out of scope. §7 is explicit about which of the in-scope systems get cut if the timeline proves wrong.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. They are not derived from those reference points. The specific assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each called out as assumptions with explicit validation commitments.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU across app types; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Era problem: pre-permission-prompt iOS, different network density. Used as a lower bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values are still judgment calls.

**The opt-in rate problem and the silent drop problem:**

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. This creates a routing problem that the prior draft mischaracterized.

The prior draft stated: "the channel mix shifts, not the total notification count." This is wrong in a specific way that matters for product correctness. When a user hasn't opted into push, that notification does not automatically route to another channel. It routes to another channel only if:

1. The user has a verified email address and hasn't unsubscribed, **and**
2. The notification type is configured for email fallback, **and**
3. The user's preference configuration explicitly allows email for this notification type.

If none of these conditions are met, the notification is dropped. For a user who is not in an active session, in-app delivery also fails. The notification is silently lost.

**This is a product correctness problem, not a provisioning problem.** The system must not silently drop notifications. The revised routing logic:

```
function route_notification(user_id, notification):
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
        channels.append("in_app")  # always show if in session
        fate = "attempted"
    
    if fate == "undelivered":
        # Notification will be lost. Log with reason.
        audit_log.write(notification_id, user_id, "dropped", reason=classify_drop_reason(user))
        metrics.increment("notifications.dropped", tags=["reason:no_channel"])
        return
    
    dispatch(notification, channels)
```

**Notification fate audit requirement:** A daily report of dropped notifications by reason (no push token, push not opted in, no email, email unsubscribed, no active session, all channels blocked) is required before launch. This is not optional instrumentation — it is the only way to know whether the system is silently failing a meaningful fraction of users. The drop rate is a product metric, not just an engineering metric.

**Revised channel reach accounting:**

| Channel | Assumed Reach | Honest Uncertainty | Notes |
|---|---|---|---|
| Push | 52% of DAU | 40–65% plausible range | Blended iOS/Android; validated post-launch |
| In-app | Active session users only | Unknown; depends on session length | Not a reliable fallback for time-sensitive notifications |
| Email | 50% of registered users at launch | Grows as reputation builds | 70% is steady-state; new senders face deliverability problems (§1.3) |
| SMS | Auth/security only | Not reach-limited | Event-triggered; not a fallback channel |

**Note on email reach:** The prior draft assumed 70% email reach, reduced only by unsubscribes. This is wrong for a new sender. §1.3 addresses email deliverability as a launch-critical risk.

#### 1.1.1 Engagement Tiers and Burst Multipliers

**Why burst multipliers are tier-differentiated:**

Notifications in a social app are triggered by social interactions. A denser, more active network produces more correlated activity — more users simultaneously active, larger follower graphs, viral events that affect more users at once. This structural argument justifies higher burst multipliers at higher engagement tiers. The multipliers themselves remain judgment calls.

**The base case 3× multiplier:** The prior draft attributed this to "Firebase engineering data on mid-scale social apps" — a source that was not cited and does not appear in the benchmarks table. This was an error. The 3× figure is a judgment call consistent with the Firebase reference range (3–5×) but not derived from it. **Validation commitment:** The burst injection test in §1.1.3 will test 3× and 4× spike scenarios before launch. If the 3× scenario produces queue behavior materially different from the model, the multiplier and capacity plan are revised before the production rollout begins. This is the only multiplier that can be validated pre-launch.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 |

High and top-quartile figures are planning inputs for future architectural decisions, not targets for the current system. At 26,000/sec, per-channel queues are required. At 67,500/sec, the architecture changes substantially. These transitions are monitored continuously (§1.1.1 monitoring) and have defined lead times.

**DAU/MAU monitoring:**

- DAU/MAU ratio computed daily
- 7-day rolling average alert at 35%: base→high transition; 24-hour runbook initiation SLA
- 7-day rolling average alert at 55%: high→top-quartile transition; 6-week architectural lead time begins
- Alert routes to on-call engineer and engineering manager; 4-hour acknowledgment SLA

#### 1.1.2 Peak Provisioning and Spike Scenario Analysis

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** 50% of daily volume in a 3-hour window (industry reference range: 40–60%).

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Burst capacity target:** 2,360 × 3 = ~7,080/sec, provisioned at **8,000/sec** with ~13% margin.

**[NEW] Revised spike scenario with front-loaded arrival shape:**

The prior draft modeled a viral spike as 1.8M notifications arriving uniformly over 10 minutes at a steady 8,000/sec. This was identified as a convenient shape that understated instantaneous load. Real viral posts front-load heavily — the post is shared, arrives in feeds, and generates a burst of interactions in the first 60–90 seconds before the rate decays.

Revised spike model:

- Total spike volume: 1.8M notifications (same as prior draft)
- Arrival shape: exponential decay starting at t=0
  - First 90 seconds: 70% of spike volume = 1.26M notifications at ~14,000/sec average instantaneous rate
  - Remaining 8.5 minutes: 30% of spike volume = 540K notifications at ~1,059/sec
- Background traffic during spike: 2,360/sec sustained

Peak instantaneous enqueue rate (first 90 seconds): 14,000 + 2,360 = **~16,360/sec**

This exceeds our 8,000/sec burst capacity. The queue absorbs the excess; workers process at maximum capacity. The question is queue depth at the end of the spike.

**Queue depth accumulation during the first 90 seconds:**

- Total enqueued: 16,360/sec × 90 sec = ~1.47M
- Total processed: 5,000/sec × 90 sec = 450K (workers at maximum capacity)
- Queue depth at t=90 seconds: ~1.02M messages

**Queue depth during the remaining 8.5 minutes:**

- Enqueue rate: 1,059 + 2,360 = ~3,419/sec
- Processing rate: 5,000/sec (workers draining the backlog)
- Net drain: 5,000 − 3,419 = 1,581/sec
- Queue reduction in 8.5 minutes: 1,581 × 510 = ~806K
- Queue depth at end of spike (t=10 min): 1,020K − 806K = **~214K messages**

**Priority composition during the spike:**

The 1.8M spike breaks down as: 800K mention notifications (high-priority) and 1M like notifications (standard-priority). The front-loaded arrival applies to both proportionally.

High-priority enqueue during first 90 seconds: 14,000 × (800/1800) ≈ 6,222/sec
Standard-priority enqueue during first 90 seconds: 14,000 × (1000/1800) ≈ 7,778/sec

High-priority processing allocation: 60% of 5,000 = 3,000/sec
Standard-priority processing allocation: 30% of 5,000 = 1,500/sec

During the first 90 seconds:
- High-priority: 6,222/sec enqueue vs. 3,000/sec processing → backlog accumulates at 3,222/sec
- Standard-priority: 7,778/sec enqueue vs. 1,500/sec processing → backlog accumulates at 6,278/sec

High-priority backlog at t=90 seconds: 3,222 × 90 = **~290K messages**
Standard-priority backlog at t=90 seconds: 6,278 × 90 = **~565K messages**

**High-priority SLA check during front-loaded spike:**

High-priority messages are not processed as fast as they arrive during the first 90 seconds. A high-priority message enqueued at t=0 waits behind the ~290K high-priority backlog that accumulates. At 3,000/sec processing rate, clearing 290K takes ~97 seconds. A high-priority message enqueued at t=0 experiences approximately 90 + 97 = **~3 minutes of queue delay** at worst. This is at the edge of the 3-minute SLA, not comfortably within it.

**Revised high-priority worker allocation:** Increase high-priority worker allocation to 70% during detected spike conditions (queue depth > 50K for high-priority tier). This reduces high-priority backlog accumulation:

- High-priority processing: 70% of 5,000 = 3,500/sec
- High-priority backlog at t=90 seconds: (6,222 − 3,500) × 90 = ~245K
- Drain time for high-priority backlog: 245K ÷ (3,500 − background high-priority enqueue) ≈ 245K ÷ 2,800 = ~87 seconds
- Worst-case high-priority delay: 90 + 87 = ~177 seconds = **~3 minutes**

This is within the 3-minute SLA but with minimal margin. The spike injection test must validate this; if observed latency exceeds 2.5 minutes during the test, the worker count is increased before launch.

**[NEW] Dynamic reallocation mechanism — full specification:**

The prior draft described this in one sentence. This section specifies it completely.

The worker pool consists of 50 worker processes (sufficient for 5,000/sec at 100 notifications/sec per worker). Workers are not statically assigned to priority tiers. Instead, each worker executes the following dispatch loop:

```python
REALLOCATION_CHECK_INTERVAL_MS = 500
HIGH_PRIORITY_