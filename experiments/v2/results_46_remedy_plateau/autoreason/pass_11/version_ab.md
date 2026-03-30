# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This document supersedes all prior drafts. Three decisions require explicit sign-off before the spike injection test:

1. **Standard-priority worst-case delay: 47 minutes during a 3× spike.** This affects likes, comments, and follows — approximately 85% of daily notification volume. This is the common case during any significant viral event, not a tail case. The two architectural responses are costed in §2.4. **Default if no decision is reached within two weeks of circulation: implement the dedicated high-priority worker pool (Option A, §2.4), at a cost of ~3 engineer-weeks.** Decision owner: product and engineering jointly.

2. **High-priority worst-case delay: 14 minutes.** Acceptable for direct messages and mentions, or requires the dedicated worker pool? Decision owner: engineering lead.

3. **Redis Sentinel vs. Redis Cluster.** Sentinel failover takes 10–30 seconds; impact on SLAs and mitigation options are quantified in §5.3. Decision owner: engineering lead.

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels. The base case is 34.6M/day (derivation in §1.1; the prior 51M figure double-counted channel overlap and is retracted).

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. Per-channel queues remain out of scope; the operational overhead is unjustified for a 4-engineer team at base-case load, and a dedicated high-priority worker pool achieves priority isolation at lower complexity (§2.4). The starvation mechanism governing how workers split between the two sets is specified in full in §2.3.

**Key figures — all are sustained rates, not ceilings; §1.1.2 derives both:**

| Metric | Value | Source |
|---|---|---|
| Base case daily volume | 34.6M notifications/day | §1.1.1 — revised downward; prior 51M retracted |
| Sustained primetime rate | ~840/sec | §1.1.2 |
| Worker capacity (100 workers) | 3,000/sec sustained | §1.1.2 — uses 30/sec planning figure |
| Worst-case standard-priority delay (3× spike) | **47 minutes** | §1.1.2 — requires product sign-off |
| Worst-case high-priority delay (3× spike) | **14 minutes** | §2.3 — requires engineering sign-off |
| Redis Sentinel failover window | 10–30 seconds | §5.3 |
| Failover impact on high-priority SLA | Adds ≤30 seconds | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope systems are cut if the timeline proves wrong, with explicit criteria for triggering each cut.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points; they are not derived from those reference points. The three assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each presented with sensitivity analysis and explicit validation commitments with pass/fail criteria and decision owners.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 Channel Reach, Population Bases, and the Email Overlap Problem

**Two distinct uses of reach figures, kept separate:**

Prior drafts conflated throughput-relevant figures with list-size figures in a single table. They answer different questions: throughput figures answer "how many notifications/sec must the system process?"; list-size figures answer "how large is our email suppression list, and what does deliverability look like at launch?" They are separated here.

**The email/in-app overlap problem:**

Email notifications for a social app serve a different purpose than in-app notifications: they are re-engagement or catch-up messages sent to users who are *not* in an active session. Sending an email to a user who is currently active and will receive an in-app notification is wasteful and degrades user experience. The routing logic in §3.1 handles this: email is only dispatched when the user has no active session at routing time.

This means the email reachable population is not "DAU with verified email" — it is "users with verified email who are not in an active session when the notification fires." We model this as a subset of MAU minus current DAU, not a subset of DAU. Applying a DAU-derived per-user rate to this population (as prior drafts did) was the source of the 51M overcount.

**The opt-in rate and silent-drop problem:**

iOS 14+ and Android 13+ require explicit permission prompts. Industry data (Airship, Braze, OneSignal, 2021–2023) shows blended opt-in rates of 45–60% for new social apps. When a user hasn't opted into push, the notification routes to another channel only if: (a) the user has a verified email, hasn't unsubscribed, and the notification type is configured for email fallback; or (b) the user is in an active session. If neither condition holds, the notification is dropped. **This is a product correctness problem, not a provisioning problem.** The system must not silently drop notifications without audit. The routing code and audit requirements are specified in §3.1.

**Push opt-in rate sensitivity:**

The entire push volume estimate scales linearly with the opt-in rate assumption. The full sensitivity:

| Push Opt-In Rate | Reachable Push Users | Daily Push Volume | Change from Base |
|---|---|---|---|
| 45% (pessimistic) | 1.35M | 23.0M | −13% |
| **52% (base case)** | **1.56M** | **26.5M** | **—** |
| 60% (optimistic) | 1.80M | 30.6M | +15% |

At the pessimistic end, total daily volume drops to ~31M; at the optimistic end, ~38M. Worker capacity of 3,000/sec handles all three cases without architectural changes. The opt-in rate affects absolute volume but does not change the capacity architecture at this scale.

**Validation commitment:** Measure actual opt-in rate at 100K users (first post-launch cohort) and update the model. If opt-in exceeds 70% — outside the industry reference range, suggesting an unusually engaged early cohort — re-evaluate worker count before scaling to 1M MAU. Decision owner: engineering lead.

**Throughput-relevant figures (used in §1.1.2 capacity calculations):**

| Channel | Population Base | Assumed Reach % | Reachable Users | Notifs/User/Day | Daily Volume |
|---|---|---|---|---|---|
| Push | 3M DAU | 52% opted in | 1.56M | 17 | 26.5M |
| Email | 5M MAU with verified email | 80% not in active session when notification fires | 4.0M | 2 (email-eligible types only) | 8M |
| SMS | Auth events only | Not reach-limited | N/A | ~0.5 auth events/user/month | ~50K/day |
| In-app | Active session users | Session-dependent | Not counted separately | — | Subset of push/email triggers; no additive volume |
| **Total** | | | | | **~34.6M/day** |

The email population base is MAU-derived (not DAU-derived) because email targets non-active users. The per-user rate (2/day) is lower than the prior 5/day figure, which incorrectly applied DAU activity rates to a non-DAU population. The net effect is a higher absolute email volume than prior drafts (8M vs. 6M), but a lower total because in-app is correctly excluded from additive volume.

**List-size figures (not used in capacity calculations):**

| Channel | Registered Users | Estimated List Size | Purpose |
|---|---|---|---|
| Email | 10M MAU | 5M (50% with verified email) | IP warming schedule; dedicated IP decision threshold (~2M sends/day per SendGrid guidance); suppression list sizing |

### 1.1.2 Worker Throughput Model, Spike Analysis, and SLA Derivations

#### Corrected Worker Throughput Figure

**Retraction:** Prior drafts used 35/sec per worker as the sustained planning figure, described it as "slightly above the midpoint," then derived a midpoint of ~31/sec with a 2% retry reduction yielding ~30/sec. 35/sec is 17% above the figure the document's own arithmetic produced. This is not conservative; it is optimistic in the wrong direction for a capacity plan. **The planning figure is corrected to 30/sec per worker.** The 35/sec figure does not appear elsewhere in this document.

**Why the ceiling differs from the sustained rate:**

50/sec per worker (the ceiling from the raw latency budget) assumes a perfectly saturated worker with no idle time, no retry overhead, and no synchronization cost. Sustained throughput is lower for three reasons:

1. **Dequeue wait:** Workers use blocking ZPOPMIN with a timeout. During normal operation, workers spend some fraction of time waiting. During a spike the queue is saturated and this term approaches zero; we add 1ms conservatively to the latency budget.
2. **Retry overhead:** FCM's documented error rate on well-formed requests is ~0.1–0.5%. At 0.3% retry rate, expected added latency per notification ≈ 0.08ms, but retries tie up a worker for a full additional provider round-trip. We model this as a 2% throughput reduction.
3. **Synchronization overhead:** Workers periodically flush audit log buffers, check shutdown signals, and update metrics. Estimated at 1–2ms per notification cycle in aggregate.

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
| **Total** | **~19–45ms** | Midpoint: ~32ms |

At 32ms midpoint: 1,000ms ÷ 32ms = 31.25/sec. Applying the 2% retry throughput reduction: **~30.6/sec, rounded to 30/sec for planning.**

100 workers × 30/sec = **3,000/sec sustained processing capacity.**

The optimistic case (19ms → 53/sec) and pessimistic case (45ms → 22/sec) bound the range. The pre-launch spike injection test measures actual throughput and scales workers accordingly.

**Pre-launch validation gate — continuous scaling table, not a single pass/fail threshold:**

| Observed Throughput/Worker | Workers Required for 3,000/sec | Action |
|---|---|---|
| ≥ 30/sec | 100 | No change |
| 25–29/sec | 104–120 | Scale to required count before rollout |
| 20–24/sec | 125–150 | Scale to required count; flag for architecture review |
| < 20/sec | > 150 | Stop rollout; convene architecture review before proceeding |

If observed throughput is below 20/sec, the bottleneck is likely provider API latency under staging sandbox rate limits, not worker count. The architecture review must identify the root cause before scaling further.

#### Revised Traffic Model and Primetime Rate

With the corrected daily volume of ~34.6M notifications/day:

- Primetime window: 4 hours (14:00–18:00 local, approximated as a single global peak for a US-primary app at launch)
- Primetime fraction: ~35% of daily volume
- Primetime volume: 34.6M × 0.35 = 12.1M
- **Primetime sustained rate: 12.1M ÷ 14,400 seconds = ~840/sec**

At 840/sec sustained, 100 workers at 30/sec provide 3.6× headroom at normal load. This headroom is consumed during burst events.

**Engagement tiers with instantaneous peak modeling:**

The instantaneous peak at t=0 is higher than the average burst rate because viral notification spikes arrive with an approximately exponential distribution — the rate is highest immediately and decays as the triggering event propagates through the social graph. We model t=0 as 4× the average burst rate as a conservative instantaneous estimate. This multiplier is a judgment call; the spike injection test will calibrate it.

| Engagement Tier | DAU | Daily Volume | Primetime Sustained | Burst Multiplier (avg) | Average Burst Rate | Instantaneous Peak (t=0) |
|---|---|---|---|---|---|---|
| Low | 2M | ~23M | ~560/sec | 2× | ~1,120/sec | ~4,500/sec |
| **Base case** | **3M** | **~35M** | **~840/sec** | **3×** | **~2,520/sec** | **~10,080/sec** |
| High | 5M | ~58M | ~1,400/sec | 4× | ~5,600/sec | ~22,400/sec |
| Top-quartile | 6.5M | ~75M | ~1,820/sec | 5× | ~9,100/sec | ~36,400/sec |

**Why burst multipliers are tier-differentiated:** Notifications in a social app are triggered by social interactions. A denser, more active network produces more correlated activity — larger follower graphs, viral events affecting more users simultaneously. This structural argument justifies higher burst multipliers at higher engagement tiers. The specific multipliers are judgment calls within the Firebase reference range (3–5×).

**What "absorb" means quantitatively:**

The system does not process the instantaneous peak in real time. During a base-case 3× spike:

- Notifications arrive at ~2,520/sec average, ~10,080/sec at t=0
- Workers process at 3,000/sec
- At the average burst rate, workers keep pace; the queue does not grow unboundedly
- The binding constraint is the instantaneous peak at t=0: 10,080/sec arriving, 3,000/sec processing → queue grows at ~7,080/sec for the first few minutes

Peak queue depth estimate (assuming instantaneous rate decays to average over 5 minutes):

- Approximate excess arrivals in first 5 minutes: (10,080 − 3,000)/sec × 300sec × 0.5 (decay factor) ≈ 1,062,000 notifications
- At ~200 bytes per queue entry: **~200MB peak queue depth**

A well-provisioned Redis instance with 4GB allocated to the notification queues handles this with substantial margin. Redis memory sizing is specified in §5.1.

#### Priority Split and the 47-Minute Delay in Context

**Notification priority classification:**

| Priority | Notification Types | Estimated % of Daily Volume |
|---|---|---|
| High | Direct messages, auth events (OTP, login alerts), safety alerts | ~15% |
| Standard | Likes, comments, follows, reposts, group activity | ~85% |

**During a 3× spike, approximately 85% of daily notification volume — likes, comments, follows — experiences up to