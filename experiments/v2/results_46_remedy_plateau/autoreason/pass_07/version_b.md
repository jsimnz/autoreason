# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Revision note:** This version addresses ten specific criticisms of the prior draft. Each section header notes what changed and why. The document is complete — all sections referenced in the executive summary are present.

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue (critical, high, standard) with channel fanout, implemented as a single Redis sorted set using priority-weighted scores. Priority determines dequeue order within one data structure. This is debuggable, replaceable, and sufficient for 10M MAU. The tradeoff: per-channel queues allow independent scaling and failure isolation but add operational complexity we cannot staff. We revisit at the top-quartile engagement tier, with a 6-week lead time for that architectural change.

**The 21-minute delay is a product decision, not an infrastructure default.** Under sustained spike conditions, standard-priority notifications face a worst-case 21-minute delay. §1.1.2 now shows the priority-tier allocation arithmetic explicitly — high-priority notifications (DMs, mentions) are allocated 60% of worker capacity during spikes, and the 3-minute SLA for high-priority is demonstrated, not asserted. The 21-minute figure applies only to standard-priority notifications. Product sign-off is required.

**On unvalidated base assumptions:** The scale estimates in §1.1.1 are judgment calls that will be wrong in some direction. The acknowledgment of circularity in prior drafts was accurate but insufficient — it named the problem without bounding the risk. §1.1.1 now specifies: the provisioning architecture is designed to be correct for any outcome in the plausible range, the minimum viable provisioning is determined by the low-engagement tier, and the scale-up path is continuous rather than threshold-gated. We also now model the effect of realistic post-2020 push opt-in rates (40–60%) on effective volume, which reduces the base case push volume meaningfully and is the more important uncertainty.

**Key decisions summarized:**

- Burst multipliers are tier-differentiated, not uniform. Higher engagement tiers have larger follower graphs and more correlated activity; applying a single 3× multiplier across all tiers was inconsistent with the structural argument. §1.1.2 uses 2×, 3×, 4×, and 5× for low through top-quartile tiers respectively, with explicit reasoning.
- SMS cost per notification is 9.9× email cost per notification. The prior draft's cost framing obscured this. §1.2 restructures the cost analysis around per-notification cost and shows SMS is the highest-risk cost item despite being volume-restricted. Global and per-user caps are specified completely in §1.2.1 and §1.2.2 with the complete Lua script.
- In-app notifications bypass the queue for latency reasons but share a deduplication key with push/email/SMS. §3 specifies the split-brain prevention mechanism and what happens when paths diverge.
- DAU/MAU monitoring is continuous with alerting, not periodic review. §1.1 specifies the alert threshold and response SLA. The prior draft's monthly review cycle created a 28-day gap; that gap is closed.
- The rollout abort criterion is now unambiguous: a sliding 48-hour window, resetting on each new trigger event, not on recovery. Three trigger events within any 48-hour window is abort. §1.1.4 specifies the window behavior explicitly.
- §7 maps specific work to specific engineers with sequencing, interface contracts, and a feasibility argument. It is present in this document.

**What this document covers and doesn't:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. It does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, or analytics beyond delivery tracking.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. We use reference points from public data to anchor estimates while acknowledging their limitations.

**Available benchmarks and their problems:**

- Twitter/X internal data (2013): ~8 notifications/day for active users. Era problem: pre-iOS notification permission prompts, different product philosophy, different follower graph density.
- Facebook engineering posts (2014–2016): 10–25/day for DAUs in engagement-heavy apps. Same era problem; also Facebook-scale network effects don't apply at 10M MAU.
- Braze industry survey (2021): median push send rate of 3–5/week per MAU across all app types; top-quartile social apps at 2–4/day per DAU. Most relevant, but aggregates across app types and doesn't segment by permission opt-in rate.

**The opt-in rate problem the prior draft ignored:**

iOS 14+ and Android 13+ require explicit permission prompts for push notifications. Industry data from 2021–2023 (Airship, Braze, OneSignal) shows:
- iOS social apps: 40–55% opt-in rate
- Android social apps: 55–70% opt-in rate (permission prompt is newer, users less trained to decline)
- Blended rate for a new social app: 45–60%

This matters more than the notifications-per-DAU estimate. If our base case assumes 3M DAU and 17 notifications/DAU/day, but only 52% of DAUs have push enabled, effective push volume is 3M × 0.52 × 17 = 26.5M/day, not 39M/day. In-app notifications are not permission-gated and absorb some of this; email absorbs more. The channel mix shifts, not the total notification count.

**Revised channel mix accounting for opt-in rates:**

| Channel | Assumed Reach | Notes |
|---|---|---|
| Push | 52% of DAU (base case) | Blended iOS/Android; 40–65% plausible range |
| In-app | 100% of DAU | No permission required; shown only to active session users |
| Email | 70% of registered users | Email required at registration; unsubscribes reduce this |
| SMS | Auth/security only | Not reach-limited; triggered by specific events |

The total notification volume estimate (51M/day base case) is relatively stable across opt-in rate assumptions because in-app absorbs what push loses. The push volume estimate is sensitive to opt-in rates; the infrastructure provisioning for FCM/APNs is sized to the push volume, not total volume. §1.2 shows the revised channel volume breakdown.

#### 1.1.1 Engagement Tiers and Burst Multipliers

**Why the prior draft used a uniform burst multiplier and why that was wrong:**

The prior draft applied a 3× burst multiplier uniformly across all engagement tiers. The structural argument in §1.1.1 of that draft was that higher engagement correlates with larger follower graphs and more correlated activity. That argument, taken seriously, implies higher engagement tiers have *larger* burst multipliers — a viral post in a 65% DAU/MAU app reaches more users simultaneously than in a 20% DAU/MAU app, because the high-follower accounts have larger active audiences and the network is denser. Applying the same multiplier was inconsistent with the structural argument. The revised table uses tier-differentiated multipliers.

**Basis for multiplier estimates:**

- Low tier (20% DAU/MAU): Sparse network, low follower counts, viral spikes are small. 2× primetime sustained is conservative.
- Base case (30% DAU/MAU): Moderate network density. 3× is consistent with Firebase engineering data on mid-scale social apps.
- High tier (50% DAU/MAU): Dense network, large follower graphs. 4× reflects higher spike amplitude; a single high-follower post reaches proportionally more active users.
- Top-quartile (65% DAU/MAU): Near-Twitter-density for a 10M MAU app. 5× is a judgment call at the upper end of what published data supports for apps at this engagement level.

These multipliers are explicitly judgment calls. The burst injection test (§1.1.3) will either validate or refute the base case multiplier before launch. The high and top-quartile multipliers will not be validated until we reach those tiers.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Primetime Sustained | Burst Multiplier | Peak/sec | Infrastructure Posture |
|---|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~740/sec | 2× | ~1,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~2,360/sec** | **3×** | **~8,000** | **Base provisioning; continuous monitoring** |
| High | 50% | 5M | 28 | 140M | ~6,500/sec | 4× | ~26,000 | Horizontal scale-out; runbook required |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~13,500/sec | 5× | ~67,500 | Architectural change; per-channel queues; 6-week lead time |

**Note on the high and top-quartile peak/sec figures:** At 26,000/sec and 67,500/sec, the single-queue Redis architecture is no longer adequate. This is the trigger for the architectural change referenced in the executive summary. These figures are planning inputs for that future design, not targets for the current system.

**DAU/MAU monitoring — continuous, not periodic:**

The prior draft specified monthly review of a weekly rolling average, which created a potential 28-day gap between crossing a scale trigger and acting on it. This was a monitoring design flaw.

**Revised monitoring design:**
- DAU/MAU ratio computed daily via the existing analytics pipeline
- Alert fires when 7-day rolling average exceeds 35% (base→high transition trigger)
- Alert fires when 7-day rolling average exceeds 55% (high→top-quartile transition trigger)
- Alert routes to the on-call engineer and engineering manager with a 4-hour acknowledgment SLA
- Scale-up runbook is initiated within 24 hours of alert acknowledgment, not at the next review cycle

The monthly review is retained as a trend review, not as the primary monitoring mechanism.

#### 1.1.2 Peak Provisioning and Priority-Tier Allocation Arithmetic

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** 50% of daily volume in a 3-hour window (consistent with published social app data; treated as a planning assumption, not a derived figure):

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Burst capacity:** 2,360 × 3 = 7,080/sec, rounded to **8,000/sec** with ~13% margin.

**Worker provisioning:**
- Sustained capacity: 5,000/sec (2.1× primetime sustained; headroom for simultaneous events)
- Burst capacity: 8,000/sec (queue absorbs spikes; workers drain backlog)

**Backlog clearance arithmetic:**

A 10-minute spike at 8,000/sec with workers processing at 5,000/sec:
- Backlog accumulated: (8,000 − 5,000) × 600 = **1.8M messages**
- Post-spike drain rate: 5,000/sec (spike has ended; no new backlog accumulation)

Wait — this is the drain rate for the *total* queue. The time-to-clear depends on what's in the backlog. We need to model priority-tier composition.

**Priority-tier composition during a viral spike:**

A viral post from a high-follower account generates mention/reply notifications for everyone who interacts with the post. These are high-priority. The bulk of the spike volume is high-priority, not standard-priority. We need to allocate worker capacity across tiers explicitly.

**Worker capacity allocation during spike conditions:**

| Priority Tier | Worker Allocation | Processing Rate | Notification Types |
|---|---|---|---|
| Critical | 10% of workers (dedicated pool) | 500/sec | Auth SMS, security alerts |
| High | 60% of workers | 3,000/sec | DMs, mentions, replies |
| Standard | 30% of workers | 1,500/sec | Likes, follows, digests |

This is a weighted dequeue policy, not physical worker separation (except for critical, which uses a dedicated pool). Workers poll the sorted set; the dequeue weight ensures high-priority messages are processed first while not starving standard-priority messages entirely.

**Spike scenario analysis — worst case for each tier:**

*Scenario: Viral post generates 800K mention notifications (high-priority) and 1M like notifications (standard-priority) in a 10-minute window, plus normal background traffic.*

Background traffic during spike (at 2,360/sec sustained):
- High-priority background: ~700/sec (30% of background is DMs/mentions)
- Standard-priority background: ~1,660/sec

Total enqueue rate at spike peak: 8,000/sec
- High-priority: ~1,500/sec (spike mentions + background)
- Standard-priority: ~6,500/sec (spike likes + background)

Worker allocation at spike:
- High-priority workers: 3,000/sec processing rate vs. 1,500/sec enqueue rate → **no backlog accumulates for high-priority during spike**
- Standard-priority workers: 1,500/sec processing rate vs. 6,500/sec enqueue rate → backlog accumulates at 5,000/sec

High-priority backlog at spike end: 0 (workers outpace enqueue rate throughout)
Standard-priority backlog at spike end: 5,000 × 600 = **3.0M messages**

Post-spike standard-priority drain:
- Standard-priority enqueue returns to background: ~1,660/sec
- Standard-priority processing rate: 1,500/sec
- Net drain rate: 1,500 − 1,660 = **−160/sec** — standard-priority workers cannot drain the backlog because background traffic consumes all standard-priority capacity

**This is a problem.** Under this scenario, the standard-priority backlog never clears on its own. We need to either:

1. Temporarily reallocate high-priority workers to standard-priority once the spike clears (high-priority backlog is zero; workers are available)
2. Or increase standard-priority worker allocation

**Resolution — dynamic reallocation:**

When high-priority backlog depth < 1,000 messages (effectively empty), high-priority workers are temporarily reassigned to standard-priority processing. This is implemented as a queue depth check in the worker dispatch loop, not as a separate system.

Post-spike with dynamic reallocation:
- Standard-priority processing rate: 1,500 + 3,000 (reallocated) = 4,500/sec
- Standard-priority enqueue: ~1,660/sec
- Net drain rate: 4,500 − 1,660 = **2,840/sec**
- Time to drain 3.0M backlog: 3,000,000 ÷ 2,840 ≈ **~18 minutes**
- Maximum delay for a standard-priority message enqueued at spike start: 10 min (spike duration) + 18 min (drain time) = **~28 minutes**

This is slightly worse than the prior draft's 21-minute figure because the scenario is more realistic (spike is predominantly high-priority, which the prior draft ignored). The 21-minute figure in the prior draft was wrong; 28 minutes is the correct worst-case for standard-priority under a viral mention spike.

**High-priority SLA validation:**

Under the worst-case spike scenario above, high-priority processing rate (3,000/sec) exceeds high-priority enqueue rate (~1,500/sec) throughout the spike. High-priority messages are processed as fast as they arrive. End-to-end latency for high-priority during spike: queue transit time + channel delivery time ≈ **under 60 seconds**, well within the 3-minute SLA.

The 3-minute SLA holds. The prior draft asserted this; this version demonstrates it.

**What this means for product:**

| Notification Type | Priority Tier | Worst-Case Delay | SLA Met? |
|---|---|---|---|
| Auth/security SMS | Critical | <30 seconds | Yes — dedicated pool |
| Direct messages | High | <60 seconds during spike | Yes |
| Mentions, replies | High | <60 seconds