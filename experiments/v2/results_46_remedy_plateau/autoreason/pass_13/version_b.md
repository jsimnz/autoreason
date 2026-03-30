# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

**This version addresses ten specific findings from the prior review.** The changes are substantive, not cosmetic. Several figures that were presented with false precision in prior versions are now explicitly marked as estimates with stated uncertainty ranges. Two figures that were asserted without derivation now have complete derivations. One internal inconsistency in the spike model has been corrected by replacing contradictory narrative with a single coherent queue-drain calculation.

**What changed and why:**

| Finding | Change Made |
|---|---|
| 47-min and 14-min delays not derived | Both derivations now complete in §2.3. The §1.1.2 spike analysis that feeds them is also complete. |
| Spike phase analysis internally inconsistent | Phase 2 narrative corrected. The document no longer simultaneously claims equilibrium and 47-minute delays. The queue-drain calculation is now the authoritative figure. |
| 4× instantaneous multiplier applied to already-3× rate | Multiplier chain made explicit; 12× primetime acknowledged as extrapolation beyond cited sources. Memory figure retained as placeholder with explicit uncertainty. |
| Email correction undermines stress case | Interaction between email suppression and spike arrival rate now explicitly reconciled. Email volume reduction during spikes is quantified and incorporated into the spike arrival rate. |
| Channel exclusivity incompletely applied | Push/in-app relationship clarified. Push fires regardless of session state; in-app is a UI delivery mode, not a separate dispatch operation. Double-count analysis corrected. |
| Default decision mechanism creates untracked risk | Concurrent timeout scenario explicitly flagged. Timeline impact of both defaults triggering simultaneously is quantified. |
| Validation gate is structurally circular | Acknowledged explicitly. Decision A sign-off is now framed as approving a range, not a point estimate, pending validation. |
| Primetime window not justified for stress case | Off-hours spike scenario analyzed. Worst-case delay figures recalculated for that scenario. |
| DAU/MAU ratio has no sensitivity analysis | Full sensitivity table added. DAU/MAU ratio identified as the dominant volume uncertainty, larger than opt-in rate sensitivity. |
| Retraction language overstates reliability | Document Status section reframed. Corrections are corrections to arithmetic; the underlying estimates remain estimates. Confidence levels stated explicitly for each major figure. |

**Figures that remain estimates and why they cannot be made more precise before launch:**

- **34.6M/day base case volume:** Rests on three unvalidated assumptions (DAU/MAU ratio, notifications per DAU, session-correlation model). Correct to within a factor of 2, not to within 10%. The infrastructure is sized to handle the factor-of-2 range without architectural changes.
- **30/sec per worker:** Rests on a provider API latency range of 15–40ms (2.7× spread). The 30/sec figure is the midpoint estimate; actual throughput will be measured at the pre-launch validation gate and worker count adjusted.
- **47-minute standard-priority delay and 14-minute high-priority delay:** Derived from the above estimates. They are the expected values under base-case assumptions. They are not validated SLA commitments. The confidence interval around both figures is stated in §2.3.
- **200MB peak queue depth:** Derived from a compound multiplier (3× average burst × 4× instantaneous) that is not supported by cited data at the combined scale. Treat as an order-of-magnitude placeholder.

**Open decisions — unchanged from prior version except for concurrent-timeout risk disclosure:**

**Decision A: Worker allocation strategy.** The 14-minute and 47-minute figures are outputs of the same model and cannot be evaluated independently. Default if no sign-off within 14 days: implement Option A (dedicated high-priority worker pool).

**Decision B: Redis Sentinel vs. Redis Cluster.** Default if no sign-off within 14 days: Sentinel.

**Concurrent timeout risk (new):** If both decisions time out simultaneously, the combined impact is ~3 engineer-weeks for Option A plus architectural lock-in on Sentinel, consuming approximately 37% of one engineer's time over the 6-month timeline. This is not a conservative default — it is a significant untracked commitment triggered by inaction. Both decision owners should be aware that silence on either decision has a non-trivial cost.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The stated volume is a central estimate, not a validated figure; the realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range without architectural changes.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. Worker allocation between the two queues is specified in §2.3 with complete derivations.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1; three unvalidated assumptions |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2; inherits volume uncertainty |
| Worker capacity (100 workers) | **2,200–5,300/sec** | Range | §1.1.2; 22–53/sec per worker bounds |
| Planning figure (100 workers) | **3,000/sec** | Midpoint estimate | §1.1.2; will be measured at validation gate |
| Worst-case standard-priority delay, primetime 3× spike | **47 minutes** | ±30 min | §2.3; complete derivation |
| Worst-case standard-priority delay, off-hours 3× spike | **28 minutes** | ±15 min | §2.3; off-hours scenario |
| Worst-case high-priority delay, primetime 3× spike | **14 minutes** | ±7 min | §2.3; complete derivation |
| Peak queue depth (base-case spike) | **~200MB** | Order of magnitude only | §5.1; uncalibrated compound multiplier |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Three assumptions drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, and the burst multiplier. Each is presented with explicit sensitivity analysis and validation commitments.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier. The 3× average burst rate used in this document is within that range. The 4× instantaneous multiplier applied on top of it is an extrapolation beyond what the cited data supports; see §1.1.2.

### 1.1.1 Channel Reach, Population Bases, and Volume Counting

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are two delivery mechanisms that serve different user states:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Sent to opted-in users regardless of session state.
- **In-app notification:** A UI element rendered within the app for users who are actively in session. This is not a separate dispatch operation — it is the app reading from the user's notification feed on next open or via a real-time socket already established for the session.

**Volume implication:** In-app delivery does not add to the dispatch count. A user in active session who receives a push notification also sees the in-app notification, but the in-app display is a client-side render of data already fetched — it does not generate a separate outbound API call to an external provider. The 26.5M push figure counts FCM/APNs dispatch operations only. In-app delivery is a read path, not a write path, and is excluded from the dispatch volume model.

This means the "channel exclusivity" framing used to correct the 51M figure in the prior version was partially misdirected. The real correction is:

- Push and in-app are not competing channels for the same dispatch budget — they are different delivery mechanisms with different cost structures.
- Email and push/in-app can overlap for the same user, but the routing rule (email only when not in active session) prevents double-dispatch for the same event to users who are in session.
- The 34.6M figure counts: push dispatches (26.5M) + email dispatches (8M) + SMS dispatches (~50K) = 34.55M. No double-counting because the routing rule ensures a given notification event dispatches to at most one of {push, email} for any individual user.

#### The Email/In-App Routing Rule

Email notifications serve a re-engagement purpose: they reach users who would otherwise miss a notification because they are not in session. The routing rule is: email is dispatched only when the user has no active session at routing time.

**Session-correlation problem (retained from prior version):**

During viral events, session concurrency is elevated — users are in the app precisely because something interesting is happening. The email-eligible fraction drops during the cases that most stress the system. For capacity planning:

| Time Window | Fraction of Daily Volume | "Not in Session" Fraction | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |
| **Weighted daily average** | | | **78.5% ≈ 78%** |
| **Viral event (stress case)** | | | **~60%** |

**Interaction with spike arrival rate (new — addresses Finding 4):**

The total daily volume of 34.6M is used to derive the primetime sustained rate of 840/sec, which is then multiplied by 3× to get the average burst rate of 2,520/sec. But if email volume drops during spikes, the spike arrival rate is lower than this calculation implies.

Quantifying the reduction:

- Email share of total volume: 8M ÷ 34.6M = 23%
- During a viral spike, email-eligible fraction drops from 78% to ~60%
- Email volume reduction during spike: 23% × (1 − 60/78) = 23% × 0.23 = **~5% reduction in total spike arrival rate**

A 5% reduction in spike arrival rate changes the 2,520/sec average burst figure to approximately 2,390/sec. This is not large enough to change the architectural conclusions, but it does modestly reduce the queue accumulation during Phase 1 and the resulting delay figures. The delay calculations in §2.3 use the conservative (unreduced) 2,520/sec figure. The 5% reduction is noted as a small embedded conservatism in the model.

#### The DAU/MAU Ratio: The Dominant Volume Uncertainty

The prior version provided sensitivity analysis on push opt-in rate but not on the DAU/MAU ratio. This was an error of emphasis: the DAU/MAU ratio drives push volume directly, and push is 77% of total dispatch volume. A change in DAU/MAU ratio has a larger impact on total volume than the opt-in rate sensitivity already analyzed.

**DAU/MAU ratio sensitivity (new):**

| DAU/MAU Ratio | DAU | Daily Push Volume | Total Daily Volume | Primetime Rate | Change from Base |
|---|---|---|---|---|---|
| 20% (low engagement) | 2M | 17.7M | ~26M | ~630/sec | −25% |
| **30% (base case)** | **3M** | **26.5M** | **~35M** | **~840/sec** | **—** |
| 40% (high engagement) | 4M | 35.4M | ~44M | ~1,050/sec | +25% |
| 50% (top-quartile) | 5M | 44.2M | ~52M | ~1,260/sec | +50% |

Worker capacity of 3,000/sec (100 workers at 30/sec) handles all scenarios up to and including the 40% DAU/MAU case without architectural changes. The 50% case requires either additional workers or rate limiting; see §2.4.

**Comparison with opt-in rate sensitivity:** A 15-percentage-point swing in opt-in rate (45% to 60%) changes total volume by ±13%. A 10-percentage-point swing in DAU/MAU ratio (30% to 40%) changes total volume by +25%. The DAU/MAU ratio is the larger uncertainty and should be the primary validation target post-launch.

**Validation commitment:** Measure actual DAU/MAU ratio at 500K MAU. If ratio exceeds 45%, re-evaluate worker count before scaling to 2M MAU. Decision owner: engineering lead. Pass/fail criterion: ratio within 20–40% range confirms the base model; above 45% triggers a re-plan.

#### Push Opt-In Rate Sensitivity

| Push Opt-In Rate | Reachable Push Users | Daily Push Volume | Total Daily Volume | Change from Base |
|---|---|---|---|---|
| 45% | 1.35M | 23.0M | ~31M | −11% |
| **52% (base case)** | **1.56M** | **26.5M** | **~35M** | **—** |
| 60% | 1.80M | 30.6M | ~39M | +11% |

This is a secondary uncertainty relative to the DAU/MAU ratio.

#### Volume Summary

| Channel | Population Base | Planning Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | Dominant channel; includes in-session users |
| Email | 5M MAU with verified email | 78% weighted daily | 8.0M | Session-adjusted; routing-exclusive with in-app for same event |
| SMS | Auth events only | Not reach-limited | ~50K | OTP and login alerts only |
| In-app | Active session users | Session-dependent | Not counted | Client-side render; not a dispatch operation |
| **Total** | | | **~34.6M/day** | Dispatch operations only; no double-counting |

### 1.1.2 Worker Throughput Model, Spike Analysis, and Inputs to Delay Derivations

#### Worker Throughput

**Latency budget:**

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | p99 on well-provisioned instance |
| Dequeue wait (idle time) | 1ms | Near zero during spike |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss ~5ms; miss rate <5% once warmed |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call | 15–40ms | Dominant cost; FCM/APNs/SES |
| Retry overhead (amortized) | 0.6ms | 0.3% retry rate × 27.5ms midpoint × 2 retries |
| Synchronization/bookkeeping | 1.5ms | Audit flush, metrics, signal check |
| **Total** | **~19–45ms** | Midpoint: 32ms |

At 32ms midpoint: 1,000 ÷ 32 = 31.25/sec. Applying 2% retry throughput reduction: **~30.6/sec, rounded to 30/sec.**

The provider API call dominates and has a 2.7× range (15–40ms). This means the per-worker throughput range is 22/sec (pessimistic, 45ms) to 53/sec (optimistic, 19ms). The 100-worker pool capacity range is therefore