# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This synthesis takes the strongest elements of both versions. Version X contributed more complete arithmetic derivations, the off-hours spike scenario, the routing race condition analysis, the in-app consistency contract, and the PostgreSQL fallback specification. Version Y contributed the three-option decision framework (Option C), the correction to the reversibility claim, the 8× spike scenario planning, the email routing fallback during Redis unavailability, the topology alternatives analysis, the completed volume summary table, and the DAU/MAU remediation procedure with explicit authority and lead time. Where the versions conflicted, the more analytically complete or more conservative treatment is used.

**What this document resolves:**

| Finding | Resolution |
|---|---|
| Delay figures not derived from input distributions | Complete derivations in §2.3 with confidence intervals derived from input uncertainties |
| Burst multiplier above 5× dismissed rather than planned for | 8× scenario analyzed in §1.1.2 and §2.3; failure mode is planned for, not labeled out of scope |
| DAU/MAU sensitivity table showed sustained rates only | Spike-adjusted column added; 8× treated separately as qualitatively different failure mode |
| Decision A/B interaction analysis missed a viable third option | Option C added: weighted fair-share with priority-aware PostgreSQL fallback tables |
| "Option A unrecoverable" claim asserted without analysis | §0.3 analyzes downgrade path; claim partially retracted; concern reframed as process, not technical reversibility |
| Default decision was asymmetric and understated | Default changed to Option C; rationale is the interaction gap it closes, not reversibility alone |
| Routing race condition unanalyzed | §3.2 analyzes race condition and specifies resolution policy |
| Email routing fallback during Redis unavailability unspecified | §3.3 specifies fallback routing behavior when session state is unavailable |
| In-app scoped out without addressing dispatch dependency | §4.3 specifies in-app consistency contract and failure behavior |
| PostgreSQL fallback underspecified | §5.4 specifies schema, throughput, transition, and reconciliation |
| Timeline conditional costs never aggregated | §7.1 aggregates all conditional time costs against the 6-month constraint |
| 35/sec per worker figure inconsistent with latency arithmetic | Corrected to 30/sec; derivation shown in §1.1.2 |
| "More workers not topology" repeated without justification | §2.4 analyzes topology alternatives; "more workers" is not the only answer |
| DAU/MAU validation commitment underspecified | §1.1.1 adds remediation procedure, authority, and lead time |
| Session-distribution fractions not flagged as unvalidated | §1.1.2 flags all five unvalidated assumptions explicitly |
| Volume summary table truncated | Completed in §1.1.1 |

**Figures that remain estimates and why:**

- **34.6M/day base case volume:** Rests on five unvalidated assumptions: DAU/MAU ratio, notifications per DAU, push opt-in rate, session-distribution fractions, and the email routing model. Correct to within a factor of 2. Infrastructure is sized to handle the factor-of-2 upper bound under sustained load.
- **30/sec per worker:** Derived explicitly in §1.1.2. This is a planning midpoint, not a midpoint of the latency range — the distinction matters and is explained. Will be measured at the pre-launch validation gate. The architectural implications of being wrong at either extreme are analyzed in §1.3.
- **Delay figures:** Derived from input distributions in §2.3 with construction method shown. Confidence intervals reflect volume uncertainty propagated through the queue model. They are not SLA commitments.
- **Burst multiplier:** Scenario analysis covers 3×, 5×, and 8×. The 8× scenario is planned for, not merely labeled. Any multiplier above 8× is beyond the range of cited data and any reasonable extrapolation from it; at that point the failure mode is a capacity emergency requiring manual intervention, not a queue management problem.

**Open decisions — sign-off required:**

Three options, not two. Decisions A and B interact. See §0.2 for the full interaction analysis.

---

## 0. Open Decisions

### 0.1 Decision Definitions

**Decision A: Worker allocation strategy.**

- **Option A:** Dedicated high-priority worker pool (separate process group, separate Redis consumer group). Hard isolation between priority tiers during normal operation and partial isolation during failover because high-priority workers can be configured to retry Redis more aggressively before falling back.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together.
- **Option C:** Weighted fair-share during normal operation (identical to Option B), with priority-aware PostgreSQL fallback — separate tables per priority tier (notifications_high_priority, notifications_standard_priority) — activated during Redis unavailability. Workers check the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

Decision owners: product lead and engineering lead jointly — these are not separable questions.

**Default if no sign-off within 14 days: Option C.**
Rationale: Option C addresses the specific interaction gap identified in analysis — no priority isolation during failover under Option B — at lower operational cost than Option A. The upgrade path from C → A is approximately 2 engineer-weeks if validation data shows weighted fair-share or polling-discipline isolation is insufficient. The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override the default to Option A before the window closes.

**Decision B: Redis Sentinel vs. Redis Cluster.**

Decision owner: engineering lead.

**Default if no sign-off within 14 days: Sentinel.**
Rationale: operational complexity favors the simpler option for a 4-engineer team. Failover impact quantified in §5.3. Cluster becomes appropriate at sustained rates above ~15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

### 0.2 Interaction Analysis

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

**Failure mode comparison across options:**

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, 3× spike | Full isolation | Soft isolation | Soft isolation |
| Redis failover, 10–30 sec | Partial isolation (HP workers retry Redis) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades under load; better than B |
| PostgreSQL fallback overloaded | HP workers continue retrying Redis; SP workers queue in PG | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**Combined cost if both defaults fire:** Option C implementation (~1.5 engineer-weeks, slightly more than Option B due to dual-table fallback logic) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks. This is within the slack budget aggregated in §7.1.

### 0.3 Correction to Prior Version's Reversibility Claim

An earlier version of this document stated that Option A "had no defined downgrade path if it proved to be over-engineered." This claim was asserted without analysis. On examination it is only partially correct.

**What is true:** Collapsing a dedicated worker pool into a shared pool requires redeploying worker process groups and reconfiguring the scheduler — approximately 1 engineer-week. This is less work than building Option A from Option B (~2 engineer-weeks in the other direction). Option A is not technically irreversible.

**What is also true:** Option A by inaction — accepting Option A as the default without explicit sign-off — would have committed the team to higher operational complexity during the initial build without a clear decision record. The concern was about process discipline, not technical reversibility.

**Correction:** The reversibility argument is no longer the primary justification for the default. The primary justification for defaulting to Option C is that it closes the identified interaction gap at lower cost than Option A, with a defined upgrade path if the gap proves to matter in practice.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range under sustained load. Under spike conditions, the architecture accumulates queue depth and drains post-spike. The delay figures below are the cost of that design choice. §2.4 analyzes when topology changes are preferable to adding workers — "more workers" is not the only answer, and the conditions under which it stops being the right answer are specified.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel with automatic failover. A circuit breaker routes to a PostgreSQL fallback queue (§5.4) with separate tables per priority tier when Redis is unavailable. Worker allocation uses Option C by default: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability. The architecture handles spikes by accumulating queue depth and draining post-spike, not by processing at spike rate in real time.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1; five unvalidated assumptions |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2 |
| Worker capacity (100 workers) | **2,200–4,400/sec** | Bounded range | §1.1.2; derivation shown |
| Planning figure (100 workers) | **3,000/sec** | Planning midpoint | §1.1.2; measured at validation gate |
| Standard-priority delay, primetime 3× spike | **47 min (CI: 18–95 min)** | Derived; method shown | §2.3 |
| Standard-priority delay, off-hours 3× spike | **28 min (CI: 11–57 min)** | Derived; method shown | §2.3 |
| High-priority delay, primetime 3× spike | **14 min (CI: 5–28 min)** | Derived; method shown | §2.3 |
| Standard-priority delay, primetime 8× spike | **~4 hours; queue may not drain** | Scenario analysis | §1.1.2, §2.3 |
| Burst multiplier planning range | **3–5× (cited); 8× (stress scenario)** | Scenario analysis | §1.1.2 |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. **Five assumptions** drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, push opt-in rate, session-distribution fractions, and the email routing model. Each is flagged explicitly as unvalidated and presented with sensitivity analysis and validation commitments with pass/fail criteria, named decision owners, and — for the DAU/MAU ratio — a specified remediation procedure with authority and lead time.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. The 8× scenario is extrapolation beyond cited data and is treated as a stress scenario requiring explicit planning, not as a routine operating condition.

### 1.1.1 Volume Model

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call to an external provider. It does not add to the dispatch count.

**Volume implication:** In-app delivery does not add to the dispatch count. The 26.5M push figure counts FCM/APNs dispatch operations only. In-app delivery is a read path, not a write path.

**In-app consistency dependency:** If a push notification is dispatched successfully but the notification feed read fails (Redis unavailable, circuit breaker open), the user receives a push alert but sees nothing in-app on next open. This failure mode is addressed in §4.3.

**Channel exclusivity accounting:** The routing rule (email only when user has no active session at routing time) prevents double-dispatch for the same event. A given notification event dispatches to at most one of {push, email} for any individual user.

#### Volume Summary

| Channel | Population Base | Planning Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel; FCM/APNs dispatch operations only |
| Email | 5M MAU with verified email | 78% weighted daily fraction | 8.0M | Session-adjusted; routing-exclusive with push for same event |
| SMS | Auth events only | Not reach-limited | ~50K | OTP and login alerts only; not session-routed |
| In-app | Active session users | Session-dependent | Not counted | Client-side read of notification feed; no outbound API call; consistency contract in §4.3 |
| **Total dispatch** | | | **~34.55M/day** | Push + Email + SMS; no double-counting |

#### The DAU/MAU Ratio: The Dominant Volume Uncertainty

The DAU/MAU ratio drives push volume directly, and push is 77% of total dispatch volume. A 10-percentage-point swing in DAU/MAU ratio changes total volume by ~25%. A 15-percentage-point swing in opt-in rate changes total volume by ~13%. The DAU/MAU ratio is therefore the primary validation target.

**DAU/MAU sensitivity — spike-adjusted:**

The 5× column uses the upper bound of the Firebase-cited range as the standard stress case. The 8× scenario is addressed separately in §1.1.2 because it produces qualitatively different failure modes — queue may not drain post-spike — not just larger versions of the same failure mode.

| DAU/MAU | DAU | Sustained Rate | 5× Spike Rate | Worker Capacity (3,000/sec) | Outcome |
|---|---|---|---|---|---|
| 20% | 2M | ~630/sec | ~3,150/sec | 3,000/sec | Slight overload; queue accumulates slowly; drains within ~10 min post-spike |
| **30% (base)** | **3M** | **~840/sec** | **~4,200/sec** | **3,000/sec** | Queue accumulates; drains post-spike; delay figures in §2.3 |
| 40% | 4M | ~1,050/sec | ~5,250/sec | 3,000/sec | Significant accumulation; delay ~2× base case; drains post-spike with margin |
| 50% | 5M | ~1,260/sec | ~6,300/sec | 3,000/sec | Queue may not drain post-spike without additional workers |

**Corrected sizing claim:** Worker capacity of 3,000/sec handles sustained load at all DAU/MAU ratios in this table. Under a 5× spike, the architecture is overloaded at every scenario. Spikes are handled by accumulating queue depth and draining