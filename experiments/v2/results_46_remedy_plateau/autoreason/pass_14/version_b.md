# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This is the third revision of this document. It addresses ten structural criticisms of the prior version. Changes are substantive, not cosmetic.

**What this revision changes and why:**

| Criticism | Prior Version's Failure | This Revision's Response |
|---|---|---|
| Model validates itself | Architecture locked before measurements that supposedly validate it | §1.3 explicitly maps which architectural decisions are sensitive to which measurements, and specifies reversibility costs |
| Confidence intervals ungrounded | ±30 min and ±7 min intervals presented without derivation from input uncertainties | §2.3 derives intervals from input distributions; acknowledges they are wider than prior version claimed |
| Burst multiplier unresolved | 12× figure acknowledged as uncalibrated but used as planning input | §1.1.2 replaces 12× with a bounded range and specifies a qualitatively different failure mode analysis |
| DAU/MAU table contradicts sizing claim | Sensitivity table showed sustained rates; spike rates for upper bound exceed worker capacity | §1.1.1 adds spike-adjusted column; sizing claim corrected |
| Routing race condition unanalyzed | Session state treated as clean binary at routing time | §3.2 analyzes race condition and specifies resolution policy |
| Default decisions not analyzed for interaction | Defaults treated as independent with independent costs | §0 (Open Decisions) analyzes interaction; combined cost quantified |
| In-app clarification creates unaddressed dependency | In-app scoped out after clarification; dispatch failure modes affect in-app consistency | §4.3 specifies in-app consistency contract and failure behavior |
| Session-correlation model applied asymmetrically | Used to reduce email volume but not applied to push delivery latency | §1.1.2 applies session-correlation to provider latency assumption |
| PostgreSQL fallback underspecified | Schema, throughput, transition, and reconciliation unspecified | §5.4 specifies fallback queue in full |
| Timeline has no slack accounting | Conditional commitments listed individually but never aggregated | §7.1 aggregates all conditional time costs against the 6-month constraint |

**Figures that remain estimates:**

- **34.6M/day base case volume:** Three unvalidated assumptions. Correct to within a factor of 2. Infrastructure sized to handle the factor-of-2 upper bound.
- **30/sec per worker:** Midpoint of a 2.7× latency range. Will be measured. The architectural implication of being wrong at the extremes is analyzed in §1.3, not deferred to post-measurement.
- **Delay figures:** Derived from input distributions in §2.3. Intervals are wider than prior version claimed. They are not SLA commitments.
- **Burst multiplier:** No longer presented as a single figure. Replaced with a scenario analysis across a range, with qualitative failure mode distinctions.

**Open decisions — sign-off required:**

These decisions interact. They are not independent. See interaction analysis below.

**Decision A: Worker allocation strategy.** Option A (dedicated high-priority worker pool) vs. Option B (weighted fair-share scheduling across a single pool). Decision owners: product lead and engineering lead jointly. **Default if no sign-off within 14 days: Option B (weighted fair-share).** Rationale for changing the default from prior version: Option A requires architectural commitment now; Option B can be upgraded to Option A in approximately 2 engineer-weeks if validation data shows it is insufficient. The prior default was asymmetric — it locked in the more complex option by inaction.

**Decision B: Redis Sentinel vs. Redis Cluster.** Decision owner: engineering lead. **Default if no sign-off within 14 days: Sentinel.** Rationale unchanged: operational complexity favors the simpler option for a 4-engineer team.

**Interaction analysis:** If both decisions time out simultaneously, the interaction is as follows. Option B (weighted fair-share) combined with Sentinel failover means that during the 10–30 second failover window, all workers — high-priority and standard-priority — migrate to the PostgreSQL fallback queue together. There is no priority isolation during failover under Option B. Under Option A, dedicated high-priority workers can be configured to retry against Redis more aggressively before falling back, maintaining partial priority isolation during failover. If the product lead's requirement is that high-priority notifications maintain priority isolation even during infrastructure failures, Option A is the correct choice and the default should be overridden. If priority isolation during failover is acceptable to degrade, Option B with Sentinel is lower complexity and the correct default. **This is the question the joint sign-off must answer.** The combined cost of both defaults firing is not simply additive: it is Option B's implementation cost (~1 engineer-week) plus the cost of later upgrading to Option A if the failover degradation proves unacceptable (~2 engineer-weeks), totaling ~3 engineer-weeks — the same as the prior version's estimate, but now with the upgrade path explicit.

**Concurrent timeout risk:** Both defaults firing produces a recoverable outcome, not a trapped architecture, because Option B → Option A is a defined upgrade path. The prior version's default (Option A by inaction) was not recoverable in the same way. This revision corrects the asymmetry.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range without architectural changes under sustained load. Under spike conditions at the upper bound, the architecture requires either additional workers or rate limiting; this is explicit in §1.1.1 and is not obscured by the sensitivity table.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. The fallback queue is fully specified in §5.4. Worker allocation between the two queues is specified in §2.3.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1 |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2 |
| Worker capacity (100 workers) | **2,200–5,300/sec** | Bounded range | §1.1.2 |
| Planning figure (100 workers) | **3,000/sec** | Midpoint estimate | §1.1.2 |
| Standard-priority delay, 3× spike | **47 min (CI: 15–110 min)** | Derived | §2.3 |
| High-priority delay, 3× spike | **14 min (CI: 5–35 min)** | Derived | §2.3 |
| Burst multiplier | **3–8× range; 20×+ qualitatively different failure mode** | Scenario analysis | §1.1.2 |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Three assumptions drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, and the burst multiplier. Each is presented with sensitivity analysis and validation commitments with pass/fail criteria and named decision owners.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the cited basis for the burst multiplier range. The 3× average burst is within that range. Any multiplier above 5× is extrapolation beyond the cited data.

### 1.1.1 Volume Model

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event:

- **Push notification:** Delivered by FCM/APNs to the device OS. Counts as a dispatch operation.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call. It does not add to the dispatch count.

**Volume implication:** In-app delivery does not add to the dispatch count. The 26.5M push figure counts FCM/APNs dispatch operations only.

**In-app consistency dependency:** Because in-app delivery depends on the notification feed read path, the dispatch system's failure modes affect in-app consistency. Specifically: if a push notification is dispatched successfully but the notification feed read fails (Redis unavailable, circuit breaker open), the user receives a push alert but sees nothing in-app on next open. This is addressed in §4.3.

#### Email Routing and Session-Correlation

The routing rule: email is dispatched only when the user has no active session at routing time. The session fraction varies by time of day and is higher during viral events (more users are in-session precisely when the system is most stressed).

**Revised email volume model:**

| Time Window | Fraction of Daily Volume | "Not in Session" Fraction | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |
| **Weighted daily average** | | | **(0.35×0.65)+(0.40×0.80)+(0.25×0.95) = 78%** |
| **Viral event stress case** | | | **~60%** |

**Effect on spike arrival rate:** During a viral spike, email-eligible fraction drops from 78% to ~60%. Email is 23% of total daily volume. The volume reduction: 23% × (1 − 60/78) = ~5% reduction in total spike arrival rate. This is a small embedded conservatism. The delay calculations in §2.3 use the unreduced figure.

**Revised daily email volume:** 5M users with verified email × 78% weighted daily fraction × 2 email-eligible notification types per user per day = **7.8M/day, rounded to 8M/day.**

#### DAU/MAU Sensitivity — Spike-Adjusted

The prior version's sensitivity table showed sustained rates only. The architecture is designed around spike handling. This table adds the spike-adjusted column.

**Assumed spike multiplier for this table: 5× sustained rate.** This is the upper bound of the Firebase-cited range and is used here as the stress case for sizing claims. The implications of higher multipliers are addressed separately in §1.1.2.

| DAU/MAU | DAU | Sustained Rate | 5× Spike Rate | Worker Capacity (100 workers, 30/sec) | Outcome |
|---|---|---|---|---|---|
| 20% | 2M | ~630/sec | ~3,150/sec | 3,000/sec | **Slight overload; queue accumulates** |
| **30% (base)** | **3M** | **~840/sec** | **~4,200/sec** | **3,000/sec** | **Queue accumulates; drains post-spike** |
| 40% | 4M | ~1,050/sec | ~5,250/sec | 3,000/sec | **Significant accumulation; delay ~2× base case** |
| 50% | 5M | ~1,260/sec | ~6,300/sec | 3,000/sec | **Queue may not drain post-spike; requires additional workers** |

**Corrected sizing claim:** Worker capacity of 3,000/sec (100 workers at 30/sec) does not handle all cases without architectural changes. It handles sustained load at all DAU/MAU ratios in the table. Under a 5× spike, it is overloaded at every scenario. The architecture handles spikes by accumulating queue depth and draining post-spike — not by processing at spike rate in real time. The 47-minute and 14-minute delay figures are the cost of this design choice. If those delays are unacceptable, the answer is more workers, not a different queue topology.

**Validation commitment:** Measure actual DAU/MAU ratio at 500K MAU. If ratio exceeds 45%, re-evaluate worker count before scaling to 2M MAU. Decision owner: engineering lead. Pass/fail criterion: ratio within 20–40% range confirms the base model; above 45% triggers a re-plan.

#### Volume Summary

| Channel | Population Base | Planning Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel |
| Email | 5M MAU with verified email | 78% weighted daily | 8.0M | Session-adjusted; routing-exclusive with push for same event |
| SMS | Auth events only | Not reach-limited | ~50K | OTP and login alerts only |
| In-app | Active session users | Session-dependent | Not counted | Client-side read; not a dispatch operation |
| **Total** | | | **~34.6M/day** | Dispatch operations only |

### 1.1.2 Worker Throughput Model and Burst Analysis

#### Worker Throughput

**Planning figure: 30/sec per worker.** This is the midpoint of a 15–40ms provider API latency range. The 2.7× spread in the latency range produces a 1.5–2.7× spread in per-worker throughput (22–53/sec). The planning figure of 30/sec sits at the lower third of this range, which is intentionally conservative for a capacity plan.

**Latency budget:**

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | p99 on well-provisioned instance |
| Dequeue wait (idle time) | 1ms | Near zero during spike |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss ~5ms; miss rate <5% once warmed |
| Channel routing logic | 0.1ms | In-process |
| Provider API call | 15–40ms | **Dominant cost** |
| Retry overhead (amortized) | 0.6ms | 0.3% retry rate × 27.5ms midpoint × 2 retries |
| Synchronization/bookkeeping | 1.5ms | Audit flush, metrics, signal check |
| **Total** | **~19–45ms** | Midpoint: ~32ms → ~30/sec |

**Session-correlation effect on provider latency:** During viral events, more users are in-session simultaneously, meaning more apps are making concurrent FCM/APNs calls. Provider API latency is likely to increase during these events — the same events that generate the spikes this system is designed to handle. The 15–40ms range was derived from baseline conditions. Under viral spike conditions, the upper bound may be 60–80ms, reducing per-worker throughput to 12–17/sec. This is the adverse scenario for the delay calculations in §2.3. The prior version applied session-correlation only to reduce email volume; this revision applies it symmetrically to push delivery latency.

#### Burst Multiplier: Scenario Analysis Replacing Single Figure

The prior version used a 12× combined peak multiplier (3× average burst × 4× instantaneous), acknowledged it as uncalibrated, and then used it as a planning input. This is not a valid approach. An acknowledged uncalibrated figure should not anchor capacity calculations.

This revision replaces the single multiplier with a scenario analysis. The scenarios differ not only in queue depth but in qualitative failure mode:

**Scenario 1: 3–5× spike (within cited Firebase range)**
- Arrival rate: 2,520–4,200/sec against 3,000/sec worker capacity
- Queue accumulates during spike; drains post-spike
- Standard-priority delay: 15–110 minutes (see §2.3)
- High-priority delay: 5–35 minutes
- **Failure mode: delayed delivery. Queue drains. System recovers.**

**Scenario 2: 8