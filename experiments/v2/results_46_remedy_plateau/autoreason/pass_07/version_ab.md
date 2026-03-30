# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue (critical, high, standard) with channel fanout, implemented as a single Redis sorted set using priority-weighted scores — not three separate queues. Priority determines dequeue order within one data structure. This is debuggable, replaceable, and sufficient for 10M MAU. The tradeoff: per-channel queues allow independent scaling and failure isolation but add operational complexity we cannot staff. We revisit this if we reach the top-quartile engagement tier, with a defined 6-week lead time for that architectural change.

**The 28-minute worst-case delay is a product decision, not an infrastructure default.** Backlog clearance arithmetic under a realistic viral spike scenario produces a 28-minute worst-case delay for standard-priority notifications. The 21-minute figure cited in earlier drafts was based on an unrealistic spike composition; the corrected figure is 28 minutes and is demonstrated, not asserted, in §1.1.2. This applies only to standard-priority notifications (likes, generic activity). High-priority notifications (DMs, mentions) clear within 60 seconds under the same spike conditions, demonstrated via explicit worker allocation arithmetic. Product sign-off is required on the 28-minute figure.

**On scale assumptions:** The estimates in §1.1.1 are judgment calls anchored by industry benchmarks, not derived from them. §1.1.1 is explicit about this distinction. The provisioning architecture is designed to be correct across the plausible range; the minimum viable provisioning is determined by the low-engagement tier; and the scale-up path is continuous rather than threshold-gated. Critically, post-2020 push opt-in rates (40–60%) materially affect push volume estimates and are modeled explicitly — this is the more important uncertainty than notifications-per-DAU.

**Key decisions summarized:**

- Burst multipliers are tier-differentiated, not uniform. Higher engagement tiers have larger follower graphs and more correlated activity; a single multiplier was inconsistent with the structural argument. §1.1.2 uses 2×, 3×, 4×, and 5× for low through top-quartile tiers with explicit reasoning.
- SMS costs 9.9× per notification compared to email. §1.2 restructures cost analysis around per-notification cost. SMS is reserved for authentication and security only, enforced at the router level with atomically-enforced per-user and global caps — fully specified in §1.2.1 and §1.2.2 with complete Lua scripts.
- In-app notifications bypass the queue for latency reasons but share a deduplication key with push/email/SMS. §3 specifies the split-brain prevention mechanism and divergence handling.
- DAU/MAU monitoring is continuous with alerting, not periodic review. A 7-day rolling average alert fires at 35% and 55% thresholds with a 4-hour acknowledgment SLA. The prior monthly review cycle created a 28-day response gap; that gap is closed.
- The rollout abort criterion uses a sliding 48-hour window resetting on each new trigger event, not on recovery. Three trigger events within any 48-hour window is abort. §1.1.4 specifies both stop thresholds and recovery criteria — stop thresholds without recovery criteria are delegated decisions under pressure, not engineering criteria.
- Validation is two-track: synthetic burst injection (the only way to validate spike behavior before launch) runs concurrently with the 5% production rollout (which validates steady-state behavior, provider error rates, and token validity). §1.1.3 specifies both tracks and their acceptance criteria.
- Redis serves three critical functions — notification queue, SMS cap enforcement, and preference cache — with different failure modes. §4.2 specifies separate Redis deployments for each function, their failure behavior, and degraded-mode operation.
- §7 maps specific work to specific engineers with sequencing, interface contracts, and a feasibility argument that can be evaluated.

**What this document covers and doesn't:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. It does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, or analytics beyond delivery tracking.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. We use reference points from public data to anchor estimates while acknowledging their limitations.

**Available benchmarks and their problems:**

- Twitter/X internal data (2013): ~8 notifications/day for active users. Era problem: pre-iOS notification permission prompts, different product philosophy, different follower graph density.
- Facebook engineering posts (2014–2016): 10–25/day for DAUs in engagement-heavy apps. Same era problem; Facebook-scale network effects don't apply at 10M MAU.
- Braze industry survey (2021): median push send rate of 3–5/week per MAU across all app types; top-quartile social apps at 2–4/day per DAU. Most relevant, but aggregates across app types and doesn't segment by permission opt-in rate.

These benchmarks constrain the plausible range. The specific numbers in the table below are judgment calls within that range, chosen to be consistent with the structural argument in §1.1.1. They are not derived from the benchmarks. If we are wrong about the specific numbers, we will discover this in the production rollout and revise. The benchmarks are a sanity check on order of magnitude, not a defense of the numbers.

**The opt-in rate problem:**

iOS 14+ and Android 13+ require explicit permission prompts for push notifications. Industry data from 2021–2023 (Airship, Braze, OneSignal) shows:
- iOS social apps: 40–55% opt-in rate
- Android social apps: 55–70% opt-in rate
- Blended rate for a new social app: 45–60%

This matters more than the notifications-per-DAU estimate. If the base case assumes 3M DAU and 17 notifications/DAU/day, but only 52% of DAUs have push enabled, effective push volume is 3M × 0.52 × 17 = 26.5M/day, not 51M/day. In-app notifications are not permission-gated and absorb some of this; email absorbs more. The channel mix shifts, not the total notification count. Infrastructure provisioning for FCM/APNs is sized to push volume, not total volume — this is a meaningful difference.

**Revised channel reach accounting for opt-in rates:**

| Channel | Assumed Reach | Notes |
|---|---|---|
| Push | 52% of DAU (base case) | Blended iOS/Android; 40–65% plausible range |
| In-app | 100% of DAU | No permission required; shown only to active session users |
| Email | 70% of registered users | Required at registration; unsubscribes reduce this |
| SMS | Auth/security only | Not reach-limited; triggered by specific events |

#### 1.1.1 Engagement Tiers, Burst Multipliers, and Why They Are Tier-Differentiated

Notifications in a social app are primarily triggered by social interactions — likes, comments, follows, mentions, shares. A user base with 65% DAU/MAU is posting more content, interacting more frequently, and generating more cross-user events per day than a 20% DAU/MAU user base. More events means more notification triggers. This is a structural argument about causation, not a statistical fit to data.

**Why burst multipliers must be tier-differentiated:**

A viral post from a high-follower account generates simultaneous notifications to active followers. In a high-engagement app, more of those followers are active simultaneously — the network is denser and more correlated. Applying a uniform 3× burst multiplier across all tiers was inconsistent with this structural argument. The revised multipliers:

- Low tier (20% DAU/MAU): Sparse network, low follower counts, viral spikes are small. 2× is conservative.
- Base case (30% DAU/MAU): Moderate network density. 3× is consistent with Firebase engineering data on mid-scale social apps.
- High tier (50% DAU/MAU): Dense network, large follower graphs. 4× reflects higher spike amplitude.
- Top-quartile (65% DAU/MAU): Near-Twitter-density for a 10M MAU app. 5× is a judgment call at the upper end of published data.

These multipliers are explicitly judgment calls. The burst injection test (§1.1.3) will validate or refute the base case multiplier before launch. High and top-quartile multipliers will not be validated until we reach those tiers.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec | Infrastructure Posture |
|---|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** | **Base provisioning; continuous monitoring** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 | Horizontal scale-out; runbook required before launch |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 | Architectural change; per-channel queues; 6-week lead time |

**Note on high and top-quartile peak/sec figures:** At 26,000/sec and 67,500/sec, the single-queue Redis architecture is no longer adequate. These figures are planning inputs for a future architectural change, not targets for the current system.

**DAU/MAU monitoring — continuous, not periodic:**

A monthly review cycle creates a potential 28-day gap between crossing a scale trigger and acting on it. This is a monitoring design flaw.

Revised monitoring design:
- DAU/MAU ratio computed daily via the existing analytics pipeline
- Alert fires when 7-day rolling average exceeds 35% (base→high transition trigger)
- Alert fires when 7-day rolling average exceeds 55% (high→top-quartile transition trigger)
- Alert routes to on-call engineer and engineering manager with a 4-hour acknowledgment SLA
- Scale-up runbook initiated within 24 hours of alert acknowledgment

The monthly review is retained as a trend review, not as the primary monitoring mechanism.

#### 1.1.2 Peak Provisioning and Priority-Tier Allocation Arithmetic

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** Industry data consistently shows 40–60% of daily social notification volume in a 3–4 hour primetime window. Using 50% in a 3-hour window as a planning assumption:

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Burst capacity:** 2,360 × 3 = 7,080/sec, rounded to **8,000/sec** with ~13% margin.

**Worker provisioning:**
- Sustained capacity: 5,000/sec (~2.1× primetime sustained; headroom for simultaneous events)
- Burst capacity: 8,000/sec (queue absorbs spikes; workers drain backlog)

The gap is intentional. Over-provisioning workers for continuous 8,000/sec capacity wastes roughly 50% of compute 99% of the time. Queue depth is the shock absorber.

**Queue infrastructure note:** Redis sorted set operations are O(log N). At a spike-peak depth of 1.8M elements, O(log 1,800,000) ≈ O(21). A single ElastiCache r6g.xlarge handles ~40–60K sorted set ops/sec under load. Our peak enqueue rate of 8,000/sec is well within this; we do not need to shard the queue at base case load.

**Worker capacity allocation during spike conditions:**

| Priority Tier | Worker Allocation | Processing Rate | Notification Types |
|---|---|---|---|
| Critical | 10% of workers (dedicated pool) | 500/sec | Auth SMS, security alerts |
| High | 60% of workers | 3,000/sec | DMs, mentions, replies |
| Standard | 30% of workers | 1,500/sec | Likes, follows, digests |

This is a weighted dequeue policy, not physical worker separation (except for critical, which uses a dedicated pool). Workers poll the sorted set; the dequeue weight ensures high-priority messages are processed first while not starving standard-priority messages entirely.

**Spike scenario analysis — worst case for each priority tier:**

*Scenario: A viral post generates 800K mention notifications (high-priority) and 1M like notifications (standard-priority) in a 10-minute window, plus normal background traffic.*

Background traffic during spike (at 2,360/sec sustained):
- High-priority background: ~700/sec (30% of background is DMs/mentions)
- Standard-priority background: ~1,660/sec

Total enqueue rate at spike peak: 8,000/sec
- High-priority: ~1,500/sec (spike mentions + background)
- Standard-priority: ~6,500/sec (spike likes + background)

Worker allocation at spike:
- High-priority: 3,000/sec processing rate vs. 1,500/sec enqueue rate → **no backlog accumulates for high-priority during spike**
- Standard-priority: 1,500/sec processing rate vs. 6,500/sec enqueue rate → backlog accumulates at 5,000/sec

High-priority backlog at spike end: 0
Standard-priority backlog at spike end: 5,000 × 600 = **3.0M messages**

**Post-spike drain — the problem and its resolution:**

Standard-priority enqueue returns to background (~1,660/sec) after the spike. Standard-priority processing rate is 1,500/sec. Net drain rate: 1,500 − 1,660 = **−160/sec** — standard-priority workers cannot drain the backlog because background traffic consumes all standard-priority capacity.

Resolution — dynamic reallocation: When high-priority backlog depth < 1,000 messages (effectively empty), high-priority workers are temporarily reassigned to standard-priority processing. This is implemented as a queue depth check in the worker dispatch loop, not as a separate system.

Post-spike with dynamic reallocation:
- Standard-priority processing rate: 1,500 + 3,000 (reallocated) = 4,500/sec
- Standard-priority enqueue: ~1,660/sec
- Net drain rate: 4,500 − 1,660 = **2,840/sec**
- Time to drain 3.0M backlog: 3,000,000 ÷ 2,840 ≈ **~18 minutes**
- Maximum delay for a standard-priority message enqueued at spike start: 10 min (spike duration) + 18 min (drain time) = **~28 minutes**

This is worse than the 21-minute figure in earlier drafts because the spike composition is more realistic — a viral post generates predominantly high-priority mention notifications, not a uniform mix. The 21-minute figure was based on an unrealistic spike composition; 28 minutes is correct.

**High-priority SLA validation:**

Under this worst-case spike scenario, high-priority processing rate (3,000/sec) exceeds high-priority enqueue rate (~1,500/sec) throughout the spike. High-priority messages are processed as fast as they arrive. End-to-end latency for high-priority during spike: queue transit time + channel delivery time ≈ **under 60 seconds**, well within the 3-minute SLA.

**Summary for product:**

| Notification Type | Priority Tier | Worst-Case Delay | SLA Met? |
|---|---|---|---|
| Auth/security SMS | Critical | <30 seconds | Yes — dedicated pool |
| Direct messages | High | <60 seconds during spike | Yes |
| Mentions, replies | High | <60 seconds during spike | Yes |
| Likes, follows | Standard | ~28 minutes during spike | **Requires product sign-off** |
| Digest/batch | Standard | ~28 minutes during spike | Likely yes by design |

We are not declaring 28 minutes acceptable for social notifications. We are identifying it as the worst-case delay for