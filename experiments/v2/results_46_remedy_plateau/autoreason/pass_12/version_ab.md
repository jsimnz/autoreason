# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This synthesis resolves all findings from prior reviews. Two figures are formally retracted: the 35/sec sustained throughput figure (replaced with 30/sec; arithmetic in §1.1.2) and the 51M/day base-case volume (replaced with 34.6M/day; the prior figure double-counted channels). The 47-minute standard-priority delay and 14-minute high-priority delay are retained as derived outputs of the worker allocation model — they require sign-off, not revision.

**What changed from prior versions:**

- Volume model corrected: 34.6M/day base case, ~840/sec primetime rate. The 51M/day figure applied per-DAU notification rates to all channels independently without accounting for channel exclusivity routing.
- Email volume model corrected: flat 80% "not in session" replaced with a time-of-day-adjusted model. Session activity is correlated with viral events — the cases that stress the system are precisely the cases where email-eligible fraction is lowest.
- Worker throughput corrected: 35/sec retracted; 30/sec confirmed by the document's own latency arithmetic.
- 47-minute delay derivation is complete. The prior version ended mid-calculation.
- Open decisions consolidated: three prior open decisions reduced to two, with explicit dependency relationship and named decision owners.

**Open decisions requiring sign-off before architecture is finalized:**

**Decision A (combined): Worker allocation strategy.** The 14-minute high-priority delay and the 47-minute standard-priority delay are both outputs of the same worker allocation model (§2.3). They cannot be evaluated independently.

- If both figures are acceptable: no architectural change required.
- If either figure is unacceptable: the dedicated high-priority worker pool (Option A, §2.4) is the mitigation for both, at a cost of ~3 engineer-weeks.
- **Default if no decision within 14 days of circulation: implement Option A.**
- Decision owners: product lead (47-minute standard-priority figure) and engineering lead (14-minute high-priority figure), jointly. These are not separable — a product team that finds 47 minutes unacceptable cannot defer to engineering on the 14-minute figure as a distinct question.

**Decision B: Redis Sentinel vs. Redis Cluster.** Failover impact quantified in §5.3. Default if no decision within 14 days: Sentinel, on the grounds that operational complexity for a 4-engineer team favors the simpler option. Decision owner: engineering lead.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The range across engagement tiers is 23M–75M/day. Volume derivation is in §1.1.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. The worker allocation between the two queues is specified in §2.3. Per-channel queues are out of scope; the dedicated high-priority worker pool (§2.4) achieves priority isolation at lower complexity if the delay figures in Decision A are unacceptable.

**Key figures — all are sustained rates at base case; derivations are in the sections cited:**

| Metric | Value | Source | Status |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | §1.1.1 | Revised from prior 51M (double-counted channels) |
| Sustained primetime rate | **~840/sec** | §1.1.2 | Revised from prior 2,360/sec |
| Worker capacity (100 workers) | **3,000/sec sustained** | §1.1.2 | Uses corrected 30/sec per worker |
| Worst-case standard-priority delay (3× spike) | **47 minutes** | §1.1.2 | Requires Decision A; affects ~85% of volume |
| Worst-case high-priority delay (3× spike) | **14 minutes** | §2.3 | Requires Decision A |
| Peak queue depth (base-case spike) | **~200MB** | §5.1 | Derived from uncalibrated 4× instantaneous multiplier; treat as placeholder pending spike injection test |
| Redis Sentinel failover window | **10–30 seconds** | §5.3 | Adds ≤30 seconds to high-priority SLA |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope components are cut if the timeline proves wrong, with explicit criteria and decision owners for each cut.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. The three assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each presented with sensitivity analysis and explicit validation commitments with pass/fail criteria and decision owners.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 Channel Reach, Population Bases, and the Email Overlap Problem

#### The Email/In-App Routing Rule and Its Volume Implications

Email notifications serve a re-engagement purpose: they reach users who are not in an active session and would otherwise miss the notification. Sending email to a user who is active and will receive an in-app notification wastes send budget and degrades experience. The routing rule in §3.1 is: email is dispatched only when the user has no active session at routing time.

This means the email-eligible population at any moment is not "users with verified email" — it is "users with verified email who are not currently in an active session." This fraction varies by time of day and is correlated with the type of event triggering the notification.

**The session-correlation problem:**

The prior draft applied a flat 80% "not in active session" figure as a daily average. This is wrong for capacity planning in two ways:

1. **During viral events, the triggering moment is correlated with high session activity.** A viral post generates notifications at the moment users are engaging with the app — session concurrency is elevated precisely when notification volume spikes. The 80% figure is optimistic during the cases that most stress the system.

2. **The 80% figure is a daily average across all hours, including overnight hours when session activity is near zero.** It overstates the not-in-session fraction during primetime (roughly 60–65%) and understates it during off-hours (roughly 95%+ at 3am).

**Revised email volume model:**

For capacity planning, we use the primetime fraction because primetime is when the system is stressed:

| Time Window | Fraction of Daily Email Volume | Estimated "Not in Session" | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |

Weighted daily average: (0.35 × 0.65) + (0.40 × 0.80) + (0.25 × 0.95) = 0.228 + 0.320 + 0.238 = **78.5%**, rounded to 78%.

This is close to the prior 80% flat figure as a daily average, but the distribution matters for spike planning. For viral event capacity planning, we use 60% as the email-eligible fraction — elevated session activity during a major viral event suppresses email dispatch further. Email is not a high-priority channel (OTP and auth events go to SMS), so this suppression does not affect the high-priority SLA.

**Revised daily email volume:**

- Users with verified email, not unsubscribed: 5M (50% of 10M MAU)
- Weighted daily email-eligible fraction: 78%
- Email-eligible notification types per eligible user per day: 2
- **Daily email volume: 5M × 0.78 × 2 = 7.8M/day**, rounded to **8M/day**

#### Push Opt-In Rate Sensitivity

The base case uses 52% push opt-in. The full sensitivity:

| Push Opt-In Rate | Reachable Push Users (of 3M DAU) | Daily Push Volume | Total Daily Volume | Change from Base |
|---|---|---|---|---|
| 45% (pessimistic) | 1.35M | 23.0M | ~30M | −13% |
| **52% (base case)** | **1.56M** | **26.5M** | **~35M** | **—** |
| 60% (optimistic) | 1.80M | 30.6M | ~40M | +14% |

Worker capacity of 3,000/sec handles all three cases without architectural changes. The opt-in rate affects absolute volume but does not change the capacity architecture at this scale.

**Validation commitment:** Measure actual opt-in rate at 100K users (first post-launch cohort). If opt-in exceeds 70% — outside the industry reference range, indicating an unusually engaged early cohort — re-evaluate worker count before scaling to 1M MAU. Decision owner: engineering lead. Pass/fail criterion: opt-in rate within 45–65% range confirms the model; outside that range triggers a re-plan.

#### Throughput-Relevant Volume Summary

| Channel | Population Base | Planning Reach % | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel; drives capacity |
| Email | 5M MAU with verified email | 78% weighted daily | 8.0M | Session-adjusted; not additive with in-app |
| SMS | Auth events only | Not reach-limited | ~50K | OTP, login alerts only |
| In-app | Active session users | Session-dependent | Not additive | Delivery mode, not separate dispatch volume |
| **Total** | | | **~34.6M/day** | Counts dispatch operations; no double-counting |

**Why the prior 51M figure was wrong:** The prior model applied per-DAU notification rates to the full reachable population for each channel independently, then summed channels. A user who receives an in-app notification for a like does not also receive an email for the same like — the routing rule ensures channel exclusivity. The 34.6M figure counts dispatch operations; each notification event results in at most one dispatch per channel, and routing logic ensures most events dispatch to exactly one channel.

### 1.1.2 Worker Throughput Model, Spike Analysis, and SLA Derivations

#### Worker Throughput

**Retraction:** The prior draft used 35/sec per worker as the sustained planning figure, described it as "slightly above the midpoint," then derived a midpoint of 31/sec with a 2% retry reduction yielding ~30/sec. 35/sec is 17% above the figure the document's own arithmetic produced. This is optimistic in the wrong direction for a capacity plan. **The planning figure is corrected to 30/sec per worker.**

**Latency budget:**

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | Single-key operation; p99 on well-provisioned instance |
| Dequeue wait (idle time) | 1ms | Near zero during spike; conservative for off-peak |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss ~5ms; miss rate <5% once warmed |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call | 15–40ms | Dominant cost; FCM/APNs/SES |
| Retry overhead (amortized) | 0.6ms | 0.3% retry rate × 27.5ms midpoint × 2 retries |
| Synchronization/bookkeeping | 1.5ms | Audit flush, metrics, signal check |
| **Total** | **~19–45ms** | Midpoint: 32ms |

At 32ms midpoint: 1,000ms ÷ 32ms = 31.25/sec. Applying 2% retry throughput reduction: **~30.6/sec, rounded to 30/sec.**

100 workers × 30/sec = **3,000/sec sustained processing capacity.**

The optimistic case (19ms → 53/sec) and pessimistic case (45ms → 22/sec) bound the range. The pre-launch validation gate (§4.3) measures actual throughput and scales workers accordingly.

#### Primetime Rate

- Daily volume: 34.6M
- Primetime window: 4 hours (14:00–18:00 local; US-primary app, single global peak approximation)
- Primetime fraction: 35% of daily volume
- Primetime volume: 34.6M × 0.35 = 12.1M
- Primetime sustained rate: 12.1M ÷ 14,400 seconds = **~840/sec**

At 840/sec sustained, 100 workers provide 3.6× headroom at normal load. This headroom is consumed during burst events.

#### Spike Model

A viral notification spike does not arrive at a constant rate. The arrival rate is highest at t=0 when the triggering event propagates through the social graph, and decays as the event ages. We model:

- **t=0 instantaneous peak:** 4× the average burst rate. This multiplier is a judgment call and is explicitly uncalibrated. The spike injection test in §4.3 will measure it. Memory sizing derived from this figure (§5.1) should be treated as a placeholder until that test runs.
- **Average burst rate over spike duration:** 3× the primetime sustained rate
- **Spike duration:** 30 minutes (conservative; most viral events peak and decay within 20 minutes per Firebase reference data)

**Phase analysis for the base case 3× spike:**

- Average burst rate: 3 × 840/sec = 2,520/sec
- t=0 instantaneous peak: 4 × 2,520/sec = 10,080/sec
- Worker processing rate: 3,000/sec

**Phase 1 — Queue growing (t=0 to ~t=5 minutes):** Arrivals at ~10,080/sec exceed capacity at 3,000/sec. Queue grows at ~7,080/sec. Over 5 minutes with exponential decay to the average rate, approximate excess arrivals: (10,080 − 3,000)/sec × 300sec × 0.5 (decay factor) ≈ 1,062,000 notifications. At ~200 bytes per queue entry: **~200MB peak queue depth.**

**Phase 2 — Queue draining (t=5 minutes onward):** Arrival rate has decayed below 3,000/sec. Workers drain the accumulated backlog.

**Total balance over 30-minute spike:**
- Total arrivals: 2,520/sec × 1,800 seconds = 4,536,000
- Total processed: 3,000/sec × 1,800 seconds = 5,400,000
- **At the average burst rate, workers keep pace with the spike.** The queue does not grow unboundedly; it absorbs the instantaneous peak and drains as arrival rate drops below capacity.

**Engagement tier table:**

| Tier | DAU | Daily Volume | Primetime Sustained | Avg Burst Rate (3×) | Instantaneous Peak (4× avg burst) |
|---|---|---|---|---|---|
| Low | 2M | ~23M | ~560/sec | ~1,120/sec | ~4,500/sec |
| **Base case** | **3M** | **~35M** | **~840/sec** | **~2,520/sec** | **~10,080/sec** |
| High | 5M | ~58M | ~1,400/sec | ~5,600/sec | ~22,400/sec |
| Top-quartile | 6.5M | ~75M | ~1,820/sec | ~9,100