# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This version addresses ten specific criticisms of the prior version. The changes are not cosmetic. Several affect architectural conclusions.

**What changed and why:**

| Criticism | Change Made |
|---|---|
| §2.3 derivations claimed but not shown | §2.3 now shows complete derivations inline; CI construction method made explicit |
| 30/sec per worker arithmetic inconsistent | §1.1.2 shows the full derivation; claimed midpoint corrected |
| Email routing fallback during Redis unavailability unspecified | §3.3 added: specifies fallback routing behavior when session state is unavailable |
| Option A "unrecoverable" claim asserted without analysis | §0.3 analyzes downgrade path for Option A; claim partially retracted |
| >5× burst treated as definitionally different without planning | §1.1.2 adds explicit planning for 8× scenario; failure mode is analyzed, not just labeled |
| Decision A/B interaction analysis missed Option B + priority-aware fallback | §0.2 adds this as Option C; interaction analysis revised |
| Volume summary table truncated | §1.1.1 table completed |
| DAU/MAU validation commitment underspecified | §1.1.1 adds remediation procedure, authority, and lead time |
| Session-distribution fractions presented as inputs without flagging as unvalidated | §1.1.2 flags these explicitly alongside DAU/MAU and opt-in rate |
| "More workers not topology" claim repeated without justification | §2.4 added: analyzes topology alternatives and states when each is appropriate |

**Figures that remain estimates and why:**

- **34.6M/day base case volume:** Rests on five unvalidated assumptions: DAU/MAU ratio, notifications per DAU, push opt-in rate, session-distribution fractions, and the email routing model. Correct to within a factor of 2. Infrastructure is sized to handle the factor-of-2 upper bound under sustained load.
- **30/sec per worker:** Now derived explicitly in §1.1.2. The figure is a planning midpoint, not a midpoint of the latency range. The distinction matters and is explained.
- **Delay figures:** Derived from input distributions in §2.3 with the construction method shown. Confidence intervals reflect volume uncertainty propagated through the queue model. They are not SLA commitments.
- **Burst multiplier:** Scenario analysis covers 3×, 5×, and 8×. The 8× scenario is planned for, not merely labeled.

**Open decisions — sign-off required:**

Three options, not two. See §0.2 for the expanded interaction analysis.

---

## 0. Open Decisions

### 0.1 Decision Definitions

**Decision A: Worker allocation strategy.**

- **Option A:** Dedicated high-priority worker pool (separate process group, separate Redis consumer group). Hard isolation between priority tiers.
- **Option B:** Weighted fair-share scheduling across a single worker pool. Soft isolation via queue weight.
- **Option C:** Option B during normal operation, with priority-aware PostgreSQL fallback queues (separate tables per priority tier) activated during Redis unavailability. Soft isolation normally; partial isolation during failover.

Decision owners: product lead and engineering lead jointly.
**Default if no sign-off within 14 days: Option C.**
Rationale: Option C is new to this version and addresses the gap identified in the prior version's interaction analysis. It provides partial priority isolation during failover without the operational overhead of dedicated worker pools. The upgrade path from C → A is approximately 2 engineer-weeks if validation data shows weighted fair-share is insufficient. See §0.2 for the full interaction analysis.

**Decision B: Redis Sentinel vs. Redis Cluster.**

Decision owner: engineering lead.
**Default if no sign-off within 14 days: Sentinel.**
Rationale: operational complexity favors the simpler option for a 4-engineer team. Failover impact quantified in §5.3.

### 0.2 Interaction Analysis — Revised to Include Option C

The prior version presented the interaction as a binary: full priority isolation (Option A) or no priority isolation during failover (Option B + Sentinel). That framing was incomplete. The actual design space has three points.

The key interaction question remains: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

**Option A + Sentinel:** Dedicated high-priority workers retry against Redis more aggressively before falling back. Full priority isolation during normal operation. Partial isolation during failover — high-priority workers can be configured to continue retrying Redis while standard workers fall back to PostgreSQL. Operational cost: two separate worker process groups to deploy, monitor, and scale.

**Option B + Sentinel:** Weighted fair-share during normal operation. During the 10–30 second failover window, all workers migrate to the PostgreSQL fallback queue together. No priority isolation during failover. Operational cost: lowest.

**Option C + Sentinel (new):** Weighted fair-share during normal operation — identical to Option B. PostgreSQL fallback maintains two separate queue tables (notifications_high_priority, notifications_standard_priority). Workers check the high-priority table first, then standard. Priority isolation during failover is partial — it depends on worker polling discipline, not hard process separation. Operational cost: slightly higher than Option B (two PostgreSQL tables instead of one, worker polling logic is slightly more complex). Upgrade path to Option A: approximately 2 engineer-weeks, same as from Option B.

**Failure mode comparison:**

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, 3× spike | Full isolation | Soft isolation | Soft isolation |
| Redis failover, 10–30 sec | Partial isolation (HP workers retry Redis) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades under load, better than B |
| PostgreSQL fallback overloaded | HP workers retry Redis; SP workers queue in PG | Both tiers queue in PG together | HP queue drains first; SP accumulates |

**Recommendation:** Option C is the correct default because it addresses the specific gap in the prior version's analysis — no priority isolation during failover — at lower operational cost than Option A. The joint sign-off must answer: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If the answer is hard separation, override the default to Option A before the 14-day window closes.

**Combined cost if both defaults fire:** Option C implementation (~1.5 engineer-weeks, slightly more than Option B due to dual-table fallback) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks. This is within the slack budget aggregated in §7.1.

### 0.3 Correction to Prior Version's Reversibility Claim

The prior version stated that Option A "had no defined downgrade path if it proved to be over-engineered." This claim was asserted without analysis. On examination, it is only partially correct.

**What is true:** Collapsing a dedicated worker pool into a shared pool requires redeploying worker process groups and reconfiguring the scheduler — approximately 1 engineer-week. This is less work than building Option A from Option B (~2 engineer-weeks in the other direction). In that sense, Option A is not strictly irreversible.

**What is also true:** Option A by inaction — i.e., accepting Option A as the default without explicit sign-off — would have committed the team to higher operational complexity during the initial build without a clear decision record. The concern was about process, not technical reversibility. The prior version's language overstated the technical irreversibility claim.

**Correction:** The default is Option C (not Option B as in the prior version) for the reasons in §0.2. The reversibility argument is no longer the primary justification. The primary justification is that Option C addresses the identified interaction gap at lower cost than Option A.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range under sustained load. Under spike conditions, the architecture accumulates queue depth and drains post-spike. The delay figures in the table below are the cost of that design choice. §2.4 analyzes when topology changes are preferable to adding workers; "more workers" is not the only answer.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel with automatic failover. A circuit breaker routes to a PostgreSQL fallback queue (§5.4) with separate tables per priority tier when Redis is unavailable. Worker allocation uses weighted fair-share scheduling (Option C default). The architecture handles spikes by accumulating queue depth and draining post-spike, not by processing at spike rate in real time.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1; five unvalidated assumptions |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2 |
| Worker capacity (100 workers) | **2,200–4,400/sec** | Bounded range | §1.1.2; derivation shown |
| Planning figure (100 workers) | **3,000/sec** | Planning midpoint | §1.1.2; measured at validation gate |
| Standard-priority delay, primetime 3× spike | **47 min (CI: 18–95 min)** | Derived; method shown in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | **28 min (CI: 11–57 min)** | Derived; method shown in §2.3 | §2.3 |
| High-priority delay, primetime 3× spike | **14 min (CI: 5–28 min)** | Derived; method shown in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | **~4 hours; queue may not drain** | Scenario analysis | §1.1.2, §2.3 |
| Burst multiplier planning range | **3–5× (cited); 8× (stress scenario)** | Scenario analysis | §1.1.2 |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. **Five assumptions** drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, push opt-in rate, session-distribution fractions, and the email routing model. Each is presented with sensitivity analysis and validation commitments with explicit pass/fail criteria, named decision owners, and — for the DAU/MAU ratio — a specified remediation procedure.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. 8× is extrapolation; it is planned for in §1.1.2 and §2.3 as a stress scenario, not dismissed as out of scope.

### 1.1.1 Volume Model

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call to an external provider. It does not add to the dispatch count.

**Volume implication:** In-app delivery does not add to the dispatch count. The 26.5M push figure counts FCM/APNs dispatch operations only. In-app delivery is a read path, not a write path.

**In-app consistency dependency:** If a push notification is dispatched successfully but the notification feed read fails (Redis unavailable, circuit breaker open), the user receives a push alert but sees nothing in-app on next open. This failure mode is addressed in §4.3.

**Channel exclusivity accounting:** The routing rule (email only when user has no active session at routing time) prevents double-dispatch for the same event. A given notification event dispatches to at most one of {push, email} for any individual user.

#### Volume Summary (Complete)

| Channel | Population Base | Planning Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel; FCM/APNs dispatch operations only |
| Email | 5M MAU with verified email | 78% weighted daily fraction | 8.0M | Session-adjusted; routing-exclusive with push for same event |
| SMS | Auth events only | Not reach-limited | ~50K | OTP and login alerts only; not session-routed |
| In-app | Active session users | Session-dependent | Not counted as dispatch | Client-side read of notification feed; no outbound API call; consistency contract in §4.3 |
| **Total dispatch** | | | **~34.55M/day** | Push + Email + SMS; no double-counting |

#### The DAU/MAU Ratio: The Dominant Volume Uncertainty

The DAU/MAU ratio drives push volume directly, and push is 77% of total dispatch volume.

**DAU/MAU sensitivity — spike-adjusted:**

The spike multiplier used in this table is 5× sustained rate — the upper bound of the Firebase-cited range — as the standard stress case. The 8× scenario is addressed separately in §1.1.2 because it produces qualitatively different failure modes (queue may not drain post-spike), not just larger versions of the same failure mode.

| DAU/MAU | DAU | Sustained Rate | 5× Spike Rate | Worker Capacity (3,000/sec) | Outcome |
|---|---|---|---|---|---|
| 20% | 2M | ~630/sec | ~3,150/sec | 3,000/sec | Slight overload; queue accumulates slowly; drains within ~10 min post-spike |
| **30% (base)** | **3M** | **~840/sec** | **~4,200/sec** | **3,000/sec** | Queue accumulates; drains post-spike; delay figures in §2.3 |
| 40% | 4M | ~1,050/sec | ~5,250/sec | 3,000/sec | Significant accumulation; delay ~2× base case; drains post-spike with margin |
| 50% | 5M | ~1,260/sec | ~6,300/sec | 3,000/sec | Queue may not drain post-spike without additional workers |

**Validation commitment — with remediation procedure:**

Measure actual DAU/MAU ratio at 500K MAU.

- **Pass criterion:** Ratio within 20–40% range. No action required; proceed on current sizing.
- **Fail criterion:** Ratio above 45%. This places the system in the "queue may not drain" scenario under a 5× spike.
- **Remediation procedure:** If ratio exceeds 45% at 500K MAU, the engineering lead has authority to delay scale-up to 2M MAU pending worker count re-evaluation. Lead time for provisioning additional workers on the chosen infrastructure (see §5) is approximately 2–3 days for cloud-provisioned instances. The re-evaluation produces a revised worker count estimate within 1 week of the trigger measurement. Scale-up to 2M MAU does not proceed until the revised worker count is deployed and validated under load test.
- **Decision owner:** Engineering lead. The product lead is notified but does not have veto authority over the scale-up delay.

#### Push Opt-In Rate Sensitivity

| Push Opt-In Rate | Reachable Push Users