# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue (critical, high, standard) implemented as a single Redis sorted set with priority-weighted scores — not three separate queues. Priority determines dequeue order within one data structure. This is debuggable, replaceable, and sufficient for 10M MAU. The explicit tradeoff: per-channel queues provide better failure isolation and independent scaling but add operational overhead a 4-engineer team cannot sustain. We revisit this if we reach the top-quartile engagement tier, with a defined 6-week lead time for that architectural change.

**Revised worst-case delay for standard-priority notifications: 34 minutes.** This figure uses a front-loaded spike arrival shape — which is what viral posts actually produce — rather than a uniform distribution. A front-loaded spike generates higher instantaneous enqueue rates that temporarily exceed worker capacity even for high-priority messages during the first 90 seconds. The arithmetic is in §1.1.2. The 28-minute figure from earlier modeling assumed a uniform spike arrival; that assumption understates instantaneous load. Product sign-off is required on 34 minutes.

**The opt-in rate problem creates a silent drop problem.** iOS 14+ and Android 13+ require explicit permission prompts. Blended push opt-in rates of 45–60% mean a meaningful fraction of notifications have no viable delivery channel. The system must not silently discard these — it must log them with a classified reason, and a daily "notification fate" report is required before launch. This is a product correctness requirement, not optional instrumentation. The routing logic is fully specified in §1.1.

**Key decisions summarized:**

- Burst multipliers are tier-differentiated, not uniform. Higher engagement tiers have denser networks and more correlated activity. §1.1.1 uses 2×, 3×, 4×, and 5× for low through top-quartile tiers with explicit structural reasoning.
- The 3× base-case burst multiplier is a judgment call consistent with Firebase engineering data (3–5× range for mid-scale social apps) but not derived from it. A burst injection test validates this before launch; if observed latency exceeds 2.5 minutes during the test, worker count increases before production rollout.
- SMS costs roughly 10× per notification compared to email. SMS is reserved for authentication and security only, enforced at the router level with atomically-enforced per-user and global caps via Lua scripts.
- In-app notifications bypass the queue for latency reasons but share a deduplication key with push/email/SMS. The split-brain prevention mechanism is fully specified in §3.
- DAU/MAU monitoring is continuous with alerting, not periodic review. A 7-day rolling average alert fires at 35% and 55% thresholds with a 4-hour acknowledgment SLA.
- The rollout abort criterion uses a fixed-window counter that does not reset on trigger events. Three trigger events within any fixed 48-hour window is abort. Recovery criteria are specified alongside stop thresholds — stop thresholds without recovery criteria are delegated decisions under pressure, not engineering criteria.
- Validation is two-track: synthetic burst injection (the only way to validate spike behavior before launch) runs concurrently with the 5% production rollout (which validates steady-state behavior, provider error rates, and token validity).
- Redis serves three critical functions — notification queue, SMS cap enforcement, and preference cache — with different failure modes and different failure consequences. These are separated into three logical deployments with specified degraded-mode behavior.
- §7 maps specific work to specific engineers with sequencing, interface contracts, and an honest assessment of what gets cut if the timeline is wrong.

**What this document covers:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. It does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, or analytics beyond delivery tracking.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling and the Silent Drop Problem

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. They are not derived from those reference points. The specific assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each called out explicitly with validation commitments.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU across app types; top-quartile social apps at 2–4/day per DAU. Most relevant benchmark, but aggregates across app types without segmenting by opt-in rate.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Era problem: pre-permission-prompt iOS, different network density. Used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

These benchmarks constrain the plausible range and provide order-of-magnitude sanity checks. The specific numbers in §1.1.1 are not derived from them. If the numbers are wrong, we discover this in the production rollout and revise.

**The opt-in rate problem and the silent drop problem:**

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. This creates a routing problem that must be treated as a product correctness issue, not a provisioning detail.

When a user hasn't opted into push, that notification does not automatically route to another channel. It routes to another channel only if: (1) the user has a verified email address and hasn't unsubscribed, **and** (2) the notification type is configured for email fallback, **and** (3) the user's preference configuration explicitly allows email for this notification type. If none of these conditions are met and the user is not in an active session, the notification is silently lost.

The system must not allow silent drops. The routing logic:

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
        channels.append("in_app")  # always show if active
        fate = "attempted"

    if fate == "undelivered":
        audit_log.write(
            notification_id, user_id, "dropped",
            reason=classify_drop_reason(user)
        )
        metrics.increment("notifications.dropped",
                          tags=[f"reason:{classify_drop_reason(user)}"])
        return

    dispatch(notification, channels)
```

**Notification fate audit requirement:** A daily report of dropped notifications by reason (no push token, push not opted in, no email, email unsubscribed, no active session, all channels blocked) is required before launch. The drop rate is a product metric. A system that silently fails 20% of notifications is not delivering on its contract to users, regardless of whether the infrastructure is healthy.

**Revised channel reach accounting:**

| Channel | Assumed Reach | Honest Uncertainty | Notes |
|---|---|---|---|
| Push | 52% of DAU | 40–65% plausible range | Blended iOS/Android; validated post-launch |
| In-app | Active session users only | Depends on session length | Not a reliable fallback for time-sensitive notifications |
| Email | 50% at launch, 70% steady-state | New senders face deliverability problems | §1.3 treats this as launch-critical risk |
| SMS | Auth/security only | Not reach-limited | Event-triggered; not a fallback channel |

**Note on email reach:** The 70% steady-state figure assumes an established sender reputation. A new sender will not achieve this at launch. §1.3 addresses email deliverability as a launch-critical risk with a specific mitigation plan.

---

#### 1.1.1 Engagement Tiers, Burst Multipliers, and Why They Are Tier-Differentiated

Notifications in a social app are triggered by social interactions. A user base with 65% DAU/MAU is posting more content, interacting more frequently, and generating more cross-user events per day than a 20% DAU/MAU user base. More events mean more notification triggers. A denser, more active network also produces more correlated activity — more users simultaneously active, larger follower graphs, viral events affecting more users at once. This structural argument justifies both higher per-DAU notification rates and higher burst multipliers at higher engagement tiers. The specific multiplier values remain judgment calls.

**Why burst multipliers must be tier-differentiated:**

Applying a uniform 3× burst multiplier across all tiers is inconsistent with the structural argument above. Revised multipliers:

- **Low tier (20% DAU/MAU):** Sparse network, low follower counts, viral spikes are small. 2× is conservative.
- **Base case (30% DAU/MAU):** Moderate network density. 3× is consistent with the Firebase reference range but not derived from it.
- **High tier (50% DAU/MAU):** Dense network, large follower graphs. 4× reflects higher spike amplitude.
- **Top-quartile (65% DAU/MAU):** Near-Twitter-density for a 10M MAU app. 5× is a judgment call at the upper end of published data.

The base-case 3× multiplier is validated by the burst injection test (§1.1.3). If the test produces queue behavior materially different from the model, the multiplier and capacity plan are revised before the production rollout begins. High and top-quartile multipliers will not be validated until we reach those tiers.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec | Infrastructure Posture |
|---|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** | **Base provisioning; continuous monitoring** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 | Horizontal scale-out; runbook initiated within 24h of alert |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 | Architectural change; per-channel queues; 6-week lead time |

High and top-quartile figures are planning inputs for future architectural decisions, not targets for the current system. At 26,000/sec, per-channel queues are required. At 67,500/sec, the architecture changes substantially. These transitions are monitored continuously.

**DAU/MAU monitoring — continuous, not periodic:**

A monthly review cycle creates a potential 28-day gap between crossing a scale threshold and acting on it. This is a monitoring design flaw, not a scheduling preference.

Revised monitoring:
- DAU/MAU ratio computed daily via the existing analytics pipeline
- 7-day rolling average alert at **35%**: base→high transition; 24-hour runbook initiation SLA
- 7-day rolling average alert at **55%**: high→top-quartile transition; 6-week architectural lead time begins
- Alert routes to on-call engineer and engineering manager; 4-hour acknowledgment SLA
- Monthly trend review retained as a supplement, not as the primary monitoring mechanism

---

#### 1.1.2 Peak Provisioning and Spike Scenario Analysis

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** Industry data consistently shows 40–60% of daily social notification volume in a 3–4 hour primetime window. Using 50% in a 3-hour window:

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Burst capacity target:** 2,360 × 3 = ~7,080/sec, provisioned at **8,000/sec** with ~13% margin.

**Worker provisioning:**
- Sustained capacity: 5,000/sec (~2.1× primetime sustained; headroom for simultaneous events)
- Burst capacity: 8,000/sec (queue absorbs spikes; workers drain backlog)

The gap is intentional. Over-provisioning workers for continuous 8,000/sec capacity wastes roughly 50% of compute 99% of the time. Queue depth is the shock absorber.

**Queue infrastructure note:** Redis sorted set operations are O(log N). At a spike-peak depth of ~1.8M elements, O(log 1,800,000) ≈ O(21). A single ElastiCache r6g.xlarge handles ~40–60K sorted set ops/sec under load. Our peak enqueue rate of 8,000/sec is well within this; we do not need to shard the queue at base-case load.

**Worker capacity allocation:**

| Priority Tier | Worker Allocation | Processing Rate | Notification Types |
|---|---|---|---|
| Critical | 10% of workers (dedicated pool) | 500/sec | Auth SMS, security alerts |
| High | 60% of workers | 3,000/sec | DMs, mentions, replies |
| Standard | 30% of workers | 1,500/sec | Likes, follows, digests |

Critical uses a physically dedicated pool to provide hard isolation. High and standard use a weighted dequeue policy within the shared worker pool. Workers are not permanently assigned to tiers — the dynamic reallocation mechanism (below) adjusts allocation based on observed queue depth.

**Revised spike scenario — front-loaded arrival shape:**

Earlier modeling used a uniform 8,000/sec arrival rate across the full spike window. Real viral posts front-load heavily: the post arrives in feeds, generates a burst of interactions in the first 60–90 seconds, then decays. A uniform arrival shape understates instantaneous load and produces an optimistic queue depth estimate.

Revised spike model:
- Total spike volume: 1.8M notifications (800K mention notifications, high-priority; 1M like notifications, standard-priority)
- Arrival shape: exponential decay from t=0
  - First 90 seconds: 70% of spike volume = 1.26M notifications at ~14,000/sec average instantaneous rate
  - Remaining 8.5 minutes: 30% of spike volume = 540K notifications at ~1,059/sec
- Background traffic during spike: 2,360/sec sustained

**Peak instantaneous enqueue rate (first 90 seconds):** 14,000 + 2,360 = **~16,360/sec**

This exceeds our 8,000/sec burst capacity. The queue absorbs the excess; workers process at maximum capacity.

**Queue depth accumulation during first 90 seconds:**

- Total enqueued: 16,360 × 90 = ~1.47M
- Total processed: 5,000 × 90 = 450K
- Queue depth at t=90 seconds: **~1.02M messages**

**Queue depth during remaining 8.5 minutes:**

- Enqueue rate: 1,059 + 2,360 = ~3,419/sec
- Processing rate: 5,000/sec
- Net drain: 5,000 − 3,419 = 1,581/sec
- Queue reduction: 1,581 × 510 = ~806K
- Queue depth at end of spike (t=10 min): 1,020K − 806K = **~214K messages**

**Priority composition during the first 90 seconds:**

High-priority enqueue: 14,000 × (800/1800) ≈ 6,222/sec
Standard-priority enqueue: 14,000 × (1000/1800) ≈ 7,778/sec

At nominal worker allocation (high: 3,000/sec, standard: 1,500/sec):
- High-priority: 6,222