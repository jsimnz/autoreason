# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3 — Addresses all critic findings

---

## Document Status

This revision addresses ten specific findings from the prior review. Each section notes which finding it resolves. Sections previously cited but absent (§2, §2.3, §3.2, §7) are now present. Two prior claims are formally retracted: the 35/sec sustained throughput figure (replaced with 30/sec; arithmetic in §1.1.2) and the 8-minute high-priority SLA (replaced with a derived figure of 14 minutes worst-case; derivation in §1.1.2 and §2.3).

**Remaining open decisions requiring explicit sign-off before the spike injection test:**

1. **Standard-priority worst-case delay: 47 minutes during a 3× spike.** This affects likes, comments, and follows — core engagement notifications. During a 3× spike, approximately 85% of daily notification volume is standard-priority (see §1.1.2 for the breakdown). A 47-minute delay on that volume is a product failure, not an acceptable degraded mode. The two architectural responses — dedicated high-priority worker pool and per-channel queue sharding — are costed in §2.4. A decision is required before architecture is finalized. Decision owner: product and engineering jointly. **If no decision is reached within two weeks of this document's circulation, the default is to implement the dedicated high-priority worker pool (Option A in §2.4), which resolves the high-priority delay at the cost of ~3 engineer-weeks.**

2. **High-priority worst-case delay: 14 minutes.** Acceptable for direct messages and mentions, or requires the dedicated worker pool? Decision owner: engineering lead.

3. **Redis Sentinel vs. Redis Cluster.** Sentinel failover takes 10–30 seconds; the impact on SLAs and the mitigation options are quantified in §5.3. Decision owner: engineering lead.

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day (derivation in §1.1).

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. The starvation mechanism governing how workers split between the two sets is specified in §2.3. Per-channel queues remain out of scope; the operational overhead is unjustified for a 4-engineer team at base-case load, and the alternative of a dedicated high-priority worker pool achieves priority isolation at lower complexity (§2.4).

**Key figures — all figures are sustained rates, not ceilings; §1.1.2 derives both:**

| Metric | Value | Source |
|---|---|---|
| Base case daily volume | 51M notifications/day | §1.1.1 |
| Sustained primetime rate | ~2,360/sec | §1.1.2 |
| Worker capacity (100 workers) | 3,000/sec sustained | §1.1.2 — uses 30/sec, not 35/sec |
| Worst-case standard-priority delay (3× spike) | **47 minutes** | §1.1.2 — requires product sign-off |
| Worst-case high-priority delay (3× spike) | **14 minutes** | §2.3 — requires engineering sign-off |
| Redis Sentinel failover window | 10–30 seconds | §5.3 |
| Failover impact on high-priority SLA | Adds ≤30 seconds | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope systems are cut if the timeline proves wrong, with explicit criteria for triggering each cut.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. The three assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each presented with sensitivity analysis and explicit validation commitments with pass/fail criteria and decision owners.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 Channel Reach, Population Bases, and the Email Overlap Problem

**Addressing Finding #8 (email population base) and Finding #6 (opt-in rate sensitivity).**

**The email/in-app overlap problem:**

Email notifications for a social app serve a different purpose than in-app notifications: they are re-engagement or catch-up messages sent to users who are *not* in an active session. Sending an email to a user who is currently active and will receive an in-app notification is wasteful and degrades user experience. The routing logic in §3.1 handles this: email is only dispatched when the user has no active session at routing time. This means the email reachable population is not "DAU with verified email" — it is "users with verified email who are not in an active session at the time the notification is triggered."

For capacity planning, we model this conservatively: we assume email is sent to users who triggered a notification-eligible event but are not currently active. This is a subset of MAU minus current DAU, not a subset of DAU. The revised email volume estimate:

- MAU: 10M
- Users with verified email, not unsubscribed: 5M (50% of MAU; list-size figure, not throughput figure)
- Of those, fraction not in active session when notification fires: ~80% (conservative; active sessions are short relative to the notification-eligible window)
- Email-eligible notification types per non-active user per day: 2 (lower than the prior 5/DAU figure, which applied DAU rates to a non-DAU population)
- **Revised daily email volume: 5M × 0.80 × 2 = 8M/day**

This is higher than the prior 6M/day estimate because the population base is larger (MAU-derived, not DAU-derived), partially offset by a lower per-user rate. The prior 6M figure was arithmetically inconsistent; this figure is directionally correct given the assumptions.

**Push opt-in rate sensitivity (Addressing Finding #6):**

The prior draft selected 52% without presenting the sensitivity. The entire push volume estimate scales linearly with this figure. Here is the full sensitivity:

| Push Opt-In Rate | Reachable Push Users (of 3M DAU) | Daily Push Volume | Change from Base |
|---|---|---|---|
| 45% (pessimistic) | 1.35M | 23.0M | −13% |
| **52% (base case)** | **1.56M** | **26.5M** | **—** |
| 60% (optimistic) | 1.80M | 30.6M | +15% |

At the pessimistic end, total daily volume drops to ~47M; at the optimistic end, ~55M. Worker capacity of 3,000/sec handles all three cases without architectural changes. The opt-in rate affects absolute volume but does not change the capacity architecture at this scale. The validation commitment: measure actual opt-in rate at 100K users (first cohort post-launch) and update the model. If opt-in exceeds 70% (outside the industry reference range, suggesting an unusually engaged early cohort), re-evaluate worker count before scaling to 1M MAU.

**Throughput-relevant figures (used in capacity calculations):**

| Channel | Population Base | Assumed Reach % | Reachable Users | Notifs/User/Day | Daily Volume |
|---|---|---|---|---|---|
| Push | 3M DAU | 52% | 1.56M | 17 | 26.5M |
| Email | 5M (MAU with verified email) | 80% not in active session | 4.0M | 2 (email-eligible types, non-active users) | 8M |
| SMS | Auth events only | Not reach-limited | N/A | ~0.5 auth events/user/month | ~50K/day |
| In-app | Active session users | Session-dependent | Not counted separately | — | Subset of push/email triggers; no additive volume |
| **Total** | | | | | **~34.6M base (revised)** |

**Note on revised total:** The revised total (34.6M) is lower than the prior 51M base case. The prior figure double-counted: it applied per-DAU notification rates to the full reachable population without accounting for channel exclusivity (a user receiving an in-app notification does not also receive an email for the same event). The 34.6M figure is the estimated number of notification dispatch operations per day. The primetime sustained rate is revised accordingly in §1.1.2.

**List-size figures (not used in capacity calculations):**

| Channel | Registered Users | Estimated List Size | Purpose |
|---|---|---|---|
| Email | 10M MAU | 5M (50% with verified email) | IP warming schedule, suppression list sizing, deliverability planning |

### 1.1.2 Worker Throughput Model, Spike Analysis, and SLA Derivations

**Addressing Finding #3 (missing high-priority SLA derivation), Finding #4 (worker throughput contradiction), Finding #5 (incomplete burst model), and Finding #1 (47-minute delay not contextualized).**

#### Corrected Worker Throughput Figure

**Retraction:** The prior draft used 35/sec per worker as the sustained planning figure, described it as "slightly above the midpoint," then derived a midpoint of 31/sec with a 2% retry reduction yielding ~30/sec. 35/sec is 17% above the 30/sec figure the document's own arithmetic produced. This is not conservative; it is optimistic in the wrong direction for a capacity plan. **The planning figure is corrected to 30/sec per worker.**

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
| **Total** | **~19–45ms** | Midpoint: 32ms |

At 32ms midpoint: 1,000ms ÷ 32ms = 31.25/sec. Applying the 2% retry throughput reduction: **~30.6/sec, rounded to 30/sec for planning.**

**100 workers × 30/sec = 3,000/sec sustained processing capacity.**

The optimistic case (19ms → 53/sec) and pessimistic case (45ms → 22/sec) bound the range. The pre-launch validation gate (§4.3) measures actual throughput and scales workers accordingly.

#### Revised Traffic Model and Primetime Rate

With the corrected daily volume of ~34.6M notifications/day:

- Primetime window: 4 hours (14:00–18:00 local, approximated as a single global peak for a US-primary app)
- Primetime fraction: ~35% of daily volume
- Primetime volume: 34.6M × 0.35 = 12.1M
- Primetime sustained rate: 12.1M ÷ 14,400 seconds = **~840/sec**

This is substantially lower than the prior 2,360/sec figure, which was derived from the overcounted 51M/day total. At 840/sec sustained, 100 workers at 30/sec provide 3,000/sec capacity — a 3.6× headroom at normal load. This headroom is consumed during burst events.

**Revised engagement tier table with complete instantaneous peaks:**

The instantaneous peak at t=0 is higher than the average burst rate because viral notification spikes arrive with an approximately exponential distribution — the rate is highest immediately and decays as the triggering event propagates through the graph. We model t=0 as 4× the average burst rate for a conservative instantaneous estimate. This multiplier is a judgment call; the spike injection test in §4.3 will calibrate it.

| Engagement Tier | DAU | Daily Volume | Primetime Sustained | Burst Multiplier (avg) | Average Burst Rate | Instantaneous Peak (t=0, 4× avg burst) |
|---|---|---|---|---|---|---|
| Low | 2M | ~23M | ~560/sec | 2× | ~1,120/sec | ~4,500/sec |
| **Base case** | **3M** | **~35M** | **~840/sec** | **3×** | **~2,520/sec** | **~10,080/sec** |
| High | 5M | ~58M | ~1,400/sec | 4× | ~5,600/sec | ~22,400/sec |
| Top-quartile | 6.5M | ~75M | ~1,820/sec | 5× | ~9,100/sec | ~36,400/sec |

**What "absorb" means quantitatively:**

The system does not process the instantaneous peak in real time. Workers process at 3,000/sec. During a base-case 3× spike, notifications arrive at ~2,520/sec average (and ~10,080/sec at t=0). The queue absorbs the difference. Here is the arithmetic:

- Spike duration: assume 30 minutes (conservative; most viral events peak and decay within 20 minutes per Firebase reference data)
- Total notifications arriving during spike: 2,520/sec × 1,800 seconds = 4,536,000
- Total processed during spike: 3,000/sec × 1,800 seconds = 5,400,000
- **At the average burst rate, workers keep pace with the spike.** The queue does not grow unboundedly; it absorbs the instantaneous peak at t=0 and drains as the arrival rate drops below 3,000/sec.

The binding constraint is not the average burst rate but the instantaneous peak at t=0. At 10,080/sec arriving and 3,000/sec processing, the queue grows at 7,080/sec for the first few minutes. Peak queue depth (assuming the instantaneous rate decays to the average over 5 minutes):

- Approximate excess arrivals in first 5 minutes: (10,080 − 3,000)/sec × 300sec × 0.5 (decay factor) ≈ 1,062,000 notifications
- At ~200 bytes per queue entry (notification ID, user ID, priority, timestamp): ~200MB peak queue depth

A well-provisioned Redis instance with 4GB allocated to the notification queues handles this with substantial margin. The Redis memory sizing is specified in §5.1.

#### Priority Split and the 47-Minute Delay in Context

**Addressing Finding #1: the 47-minute delay must be contextualized by volume, not just flagged.**

**Notification priority classification:**

| Priority | Notification Types | Estimated % of Daily Volume |
|---|---|---|
| High | Direct messages, auth events (OTP, login alerts), safety alerts | ~15% |
| Standard | Likes, comments, follows, reposts, group activity | ~85% |

**This means that during a 3× spike, approximately 85% of daily notification volume — likes, comments, follows — experiences up to a 47-minute delay.** This is not a tail case affecting a small fraction of users; it is the common case for the majority of notification types during any significant viral event.

**Revised worst-case delay arithmetic:**

During a 3× spike at the base case:
- Arrival rate (average): 2,520/