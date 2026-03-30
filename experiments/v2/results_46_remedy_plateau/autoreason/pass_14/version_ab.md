# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This synthesis takes the strongest elements of two prior versions. Version X contributed more complete arithmetic derivations, clearer channel accounting, and the off-hours spike scenario. Version Y contributed the corrected default decision asymmetry, the spike-adjusted DAU/MAU sensitivity table, the burst multiplier scenario analysis replacing the uncalibrated 12× figure, the routing race condition analysis, the in-app consistency contract, the PostgreSQL fallback specification, and the timeline slack aggregation. Where the versions conflicted, the more conservative or more analytically complete treatment is used.

**What this document resolves:**

| Finding | Resolution |
|---|---|
| Delay figures not derived from input distributions | Complete derivations in §2.3 with confidence intervals derived from input uncertainties |
| Burst multiplier acknowledged as uncalibrated but used as planning input | Replaced with scenario analysis across a range; qualitatively different failure modes distinguished |
| DAU/MAU sensitivity table showed sustained rates only | Spike-adjusted column added; sizing claim corrected — worker capacity does not handle all spike scenarios without additional workers |
| Default decisions not analyzed for interaction | Interaction analyzed; combined cost and upgrade path explicit |
| Default for Decision A was asymmetric | Default changed from Option A to Option B; rationale: Option B → Option A is a defined upgrade path; Option A by inaction was not recoverable in the same way |
| Routing race condition unanalyzed | §3.2 analyzes race condition and specifies resolution policy |
| In-app scoped out without addressing dispatch dependency | §4.3 specifies in-app consistency contract and failure behavior |
| Session-correlation applied to reduce email volume but not to push delivery latency | Applied symmetrically in §1.1.2; adverse scenario for delay calculations identified |
| PostgreSQL fallback underspecified | §5.4 specifies schema, throughput, transition, and reconciliation |
| Timeline conditional costs never aggregated | §7.1 aggregates all conditional time costs against the 6-month constraint |
| 35/sec per worker figure inconsistent with latency arithmetic | Corrected to 30/sec; derivation shown |

**Figures that remain estimates and why:**

- **34.6M/day base case volume:** Rests on three unvalidated assumptions (DAU/MAU ratio, notifications per DAU, session-correlation model). Correct to within a factor of 2, not within 10%. Infrastructure is sized to handle the factor-of-2 upper bound under sustained load.
- **30/sec per worker:** Midpoint of a 2.7× latency range (15–40ms). Will be measured at the pre-launch validation gate. The architectural implications of being wrong at either extreme are analyzed in §1.3, not deferred to post-measurement.
- **Delay figures:** Derived from input distributions in §2.3. Confidence intervals are wider than prior versions claimed. They are not SLA commitments.
- **Burst multiplier:** No longer presented as a single figure. Replaced with a scenario analysis. Any multiplier above 5× is extrapolation beyond cited data and is treated as a qualitatively different failure mode.

**Open decisions — sign-off required:**

These decisions interact. They are not independent.

**Decision A: Worker allocation strategy.** Option A (dedicated high-priority worker pool) vs. Option B (weighted fair-share scheduling across a single pool). Decision owners: product lead and engineering lead jointly — these are not separable questions. **Default if no sign-off within 14 days: Option B (weighted fair-share).** Rationale: Option B can be upgraded to Option A in approximately 2 engineer-weeks if validation data shows it is insufficient. Option A by inaction, as specified in the prior version, locked in the more complex option without an explicit upgrade path. The default is corrected to the reversible choice.

**Decision B: Redis Sentinel vs. Redis Cluster.** Decision owner: engineering lead. **Default if no sign-off within 14 days: Sentinel.** Rationale: operational complexity favors the simpler option for a 4-engineer team. Failover impact quantified in §5.3.

**Interaction analysis:** The two decisions interact on a specific question that the joint sign-off must answer explicitly: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

Under Option B + Sentinel: during the 10–30 second failover window, all workers migrate to the PostgreSQL fallback queue together. There is no priority isolation during failover.

Under Option A + Sentinel: dedicated high-priority workers can be configured to retry against Redis more aggressively before falling back, maintaining partial priority isolation during failover.

If the answer is that priority isolation must be maintained even during infrastructure failures, Option A is the correct choice and the default must be overridden before the 14-day window closes.

**Combined cost if both defaults fire:** Option B implementation (~1 engineer-week) plus the cost of later upgrading to Option A if failover degradation proves unacceptable (~2 engineer-weeks) = ~3 engineer-weeks total. This is the same magnitude as the prior version's estimate, but the upgrade path is now explicit and the outcome is recoverable. The prior version's default (Option A by inaction) had no defined downgrade path if Option A proved to be over-engineered.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range under sustained load. Under spike conditions at the upper bound, the architecture requires either additional workers or rate limiting — this is explicit in §1.1.1 and is not obscured by the sensitivity tables.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a fully specified PostgreSQL fallback queue (§5.4) when Redis is unavailable. Worker allocation between the two queues is specified in §2.3 with complete derivations. The architecture handles spikes by accumulating queue depth and draining post-spike, not by processing at spike rate in real time. The delay figures below are the cost of this design choice. If those delays are unacceptable, the answer is more workers — not a different queue topology.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1; three unvalidated assumptions |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2; inherits volume uncertainty |
| Worker capacity (100 workers) | **2,200–5,300/sec** | Bounded range | §1.1.2; 22–53/sec per worker |
| Planning figure (100 workers) | **3,000/sec** | Midpoint estimate | §1.1.2; measured at validation gate |
| Standard-priority delay, primetime 3× spike | **47 min (CI: 15–110 min)** | Derived from input distributions | §2.3 |
| Standard-priority delay, off-hours 3× spike | **28 min (CI: 10–65 min)** | Derived from input distributions | §2.3 |
| High-priority delay, primetime 3× spike | **14 min (CI: 5–35 min)** | Derived from input distributions | §2.3 |
| Burst multiplier | **3–5× cited range; 8×+ qualitatively different failure mode** | Scenario analysis | §1.1.2 |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Three assumptions drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, and the burst multiplier. Each is presented with sensitivity analysis and validation commitments with explicit pass/fail criteria and named decision owners.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier. Any multiplier above 5× is extrapolation beyond what the cited data supports.

### 1.1.1 Volume Model

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call to an external provider. It does not add to the dispatch count.

**Volume implication:** In-app delivery does not add to the dispatch count. The 26.5M push figure counts FCM/APNs dispatch operations only. In-app delivery is a read path, not a write path.

**In-app consistency dependency:** Because in-app delivery depends on the notification feed read path, the dispatch system's failure modes affect in-app consistency. Specifically: if a push notification is dispatched successfully but the notification feed read fails (Redis unavailable, circuit breaker open), the user receives a push alert but sees nothing in-app on next open. This failure mode is addressed in §4.3.

**Channel exclusivity accounting:** Push and email can overlap for the same user, but the routing rule (email only when user has no active session at routing time) prevents double-dispatch for the same event. The 34.6M figure counts push dispatches (26.5M) + email dispatches (8M) + SMS dispatches (~50K) = 34.55M. No double-counting because routing ensures a given notification event dispatches to at most one of {push, email} for any individual user.

#### Email Routing, Session-Correlation, and the Spike Interaction

The routing rule is: email is dispatched only when the user has no active session at routing time. The not-in-session fraction is not flat across the day — it is highest during off-hours and lowest during primetime and viral events. This matters for capacity planning because the cases that most stress the system (viral spikes) are precisely the cases where email volume is suppressed.

**Revised email volume model:**

| Time Window | Fraction of Daily Volume | "Not in Session" Fraction | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |
| **Weighted daily average** | | | **(0.35×0.65)+(0.40×0.80)+(0.25×0.95) = 78%** |
| **Viral event stress case** | | | **~60%** |

**Effect on spike arrival rate:** During a viral spike, email-eligible fraction drops from 78% to ~60%. Email is 23% of total daily volume (8M ÷ 34.6M). The volume reduction during spikes: 23% × (1 − 60/78) = 23% × 0.23 ≈ **5% reduction in total spike arrival rate.** This is a small embedded conservatism. The delay calculations in §2.3 use the conservative unreduced figure.

**Revised daily email volume:** 5M users with verified email × 78% weighted daily fraction × 2 email-eligible notification types per user per day = **7.8M/day, rounded to 8M/day.**

#### The DAU/MAU Ratio: The Dominant Volume Uncertainty

The DAU/MAU ratio drives push volume directly, and push is 77% of total dispatch volume. A swing in DAU/MAU ratio has a larger impact on total volume than the opt-in rate sensitivity. It is therefore the primary validation target.

**DAU/MAU sensitivity — spike-adjusted:**

The prior version's sensitivity table showed sustained rates only. Because the architecture is designed around spike handling, the relevant question is what happens to spike rates, not sustained rates. The assumed spike multiplier for this table is 5× sustained rate — the upper bound of the Firebase-cited range, used as the stress case for sizing claims.

| DAU/MAU | DAU | Sustained Rate | 5× Spike Rate | Worker Capacity (3,000/sec) | Outcome |
|---|---|---|---|---|---|
| 20% | 2M | ~630/sec | ~3,150/sec | 3,000/sec | **Slight overload; queue accumulates slowly** |
| **30% (base)** | **3M** | **~840/sec** | **~4,200/sec** | **3,000/sec** | **Queue accumulates; drains post-spike (see §2.3)** |
| 40% | 4M | ~1,050/sec | ~5,250/sec | 3,000/sec | **Significant accumulation; delay ~2× base case** |
| 50% | 5M | ~1,260/sec | ~6,300/sec | 3,000/sec | **Queue may not drain post-spike; requires additional workers** |

**Corrected sizing claim:** Worker capacity of 3,000/sec handles sustained load at all DAU/MAU ratios in this table. Under a 5× spike, it is overloaded at every scenario. The architecture handles spikes by accumulating queue depth and draining post-spike. The 47-minute and 14-minute delay figures are the cost of this design choice, not a defect in the queue topology. If those delays are unacceptable, the answer is more workers.

**Comparison with opt-in rate sensitivity:** A 15-percentage-point swing in opt-in rate (45% to 60%) changes total volume by ±13%. A 10-percentage-point swing in DAU/MAU ratio (30% to 40%) changes total volume by +25%. The DAU/MAU ratio is the larger uncertainty and should be the primary validation target post-launch.

**Validation commitment:** Measure actual DAU/MAU ratio at 500K MAU. If ratio exceeds 45%, re-evaluate worker count before scaling to 2M MAU. Decision owner: engineering lead. Pass/fail criterion: ratio within 20–40% range confirms the base model; above 45% triggers a re-plan.

#### Push Opt-In Rate Sensitivity

| Push Opt-In Rate | Reachable Push Users (of 3M DAU) | Daily Push Volume | Total Daily Volume | Change from Base |
|---|---|---|---|---|
| 45% (pessimistic) | 1.35M | 23.0M | ~31M | −11% |
| **52% (base case)** | **1.56M** | **26.5M** | **~35M** | **—** |
| 60% (optimistic) | 1.80M | 30.6M | ~39M | +11% |

This is a secondary uncertainty relative to the DAU/MAU ratio. Worker capacity handles all three cases under sustained load.

**Validation commitment:** Measure actual opt-in rate at 100K users (first post-launch cohort). If opt-in exceeds 70%, re-evaluate worker count before scaling to 1M MAU. Decision owner: engineering lead. Pass/fail criterion: opt-in rate within 45–65% confirms the model; outside that range triggers a re-plan.

#### Volume Summary

| Channel | Population Base | Planning Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel; includes in-session users |
| Email | 5M MAU with verified email | 78% weighted daily | 8.0M | Session-adjusted; routing-exclusive with push for same event |
| SMS | Auth events only | Not reach-limited | ~50K | OTP and login alerts only |
| In-app | Active session users | Session-dependent | Not counted | Client-side read; not a