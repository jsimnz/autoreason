# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This synthesis incorporates the strongest elements of two prior versions. Substantive changes are documented below. Figures presented with false precision in prior versions are explicitly marked as estimates with stated uncertainty ranges and confidence levels. All derivations are complete.

**What this document resolves:**

| Finding | Resolution |
|---|---|
| 47-min and 14-min delays not derived | Complete derivations in §2.3, with confidence intervals |
| Spike phase analysis internally inconsistent | Single coherent queue-drain calculation; Phase 2 narrative corrected |
| 4× instantaneous multiplier applied to already-3× rate | Multiplier chain explicit; 12× combined acknowledged as extrapolation beyond cited data |
| Email correction undermines stress case | Email volume reduction during spikes quantified (~5%); incorporated into spike arrival rate as embedded conservatism |
| Channel exclusivity incompletely applied | Push/in-app relationship clarified; in-app is a client-side render, not a separate dispatch operation |
| Default decision mechanism creates untracked risk | Concurrent timeout scenario quantified; ~37% of one engineer's time if both defaults trigger |
| Validation gate structurally circular | Decision A sign-off framed as approving a range pending validation |
| Primetime window not justified for stress case | Off-hours spike scenario analyzed separately |
| DAU/MAU ratio has no sensitivity analysis | Full sensitivity table added; identified as dominant volume uncertainty |
| Retraction language overstates reliability | Corrections to arithmetic noted; underlying estimates remain estimates with explicit confidence levels |

**Figures that remain estimates and why:**

- **34.6M/day base case volume:** Rests on three unvalidated assumptions (DAU/MAU ratio, notifications per DAU, session-correlation model). Correct to within a factor of 2, not within 10%. Infrastructure is sized to handle the factor-of-2 range without architectural changes.
- **30/sec per worker:** Rests on a provider API latency range of 15–40ms (2.7× spread). Midpoint estimate; actual throughput will be measured at the pre-launch validation gate and worker count adjusted.
- **47-minute and 14-minute delay figures:** Expected values under base-case assumptions, not SLA commitments. Confidence intervals stated in §2.3.
- **200MB peak queue depth:** Derived from a compound multiplier (3× average burst × 4× instantaneous) not supported by cited data at this scale. Order-of-magnitude placeholder pending spike injection test.

**Open decisions — sign-off required:**

**Decision A: Worker allocation strategy.** The 14-minute and 47-minute figures are outputs of the same model and cannot be evaluated independently. Decision owners: product lead (47-minute figure) and engineering lead (14-minute figure), jointly — these are not separable questions. **Default if no sign-off within 14 days: implement Option A (dedicated high-priority worker pool), at a cost of ~3 engineer-weeks.**

**Decision B: Redis Sentinel vs. Redis Cluster.** Failover impact quantified in §5.3. **Default if no sign-off within 14 days: Sentinel**, on the grounds that operational complexity favors the simpler option for a 4-engineer team. Decision owner: engineering lead.

**Concurrent timeout risk:** If both decisions time out simultaneously, the combined impact is ~3 engineer-weeks for Option A plus architectural lock-in on Sentinel, consuming approximately 37% of one engineer's time over the 6-month timeline. This is not a conservative default — it is a significant untracked commitment triggered by inaction.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of that range without architectural changes.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. Worker allocation between the two queues is specified in §2.3 with complete derivations. Per-channel queues are out of scope; the dedicated high-priority worker pool (§2.4) achieves priority isolation at lower complexity if the delay figures in Decision A are unacceptable.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | ±50% | §1.1.1; three unvalidated assumptions |
| Sustained primetime rate | **~840/sec** | ±50% | §1.1.2; inherits volume uncertainty |
| Worker capacity (100 workers) | **2,200–5,300/sec** | Bounded range | §1.1.2; 22–53/sec per worker |
| Planning figure (100 workers) | **3,000/sec** | Midpoint estimate | §1.1.2; measured at validation gate |
| Standard-priority delay, primetime 3× spike | **47 minutes** | ±30 min | §2.3; complete derivation |
| Standard-priority delay, off-hours 3× spike | **28 minutes** | ±15 min | §2.3; off-hours scenario |
| High-priority delay, primetime 3× spike | **14 minutes** | ±7 min | §2.3; complete derivation |
| Peak queue depth (base-case spike) | **~200MB** | Order of magnitude | §5.1; uncalibrated compound multiplier |
| Redis Sentinel failover window | **10–30 seconds** | Vendor-documented | §5.3 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. Three assumptions drive the majority of sizing uncertainty: the DAU/MAU ratio, notifications per DAU, and the burst multiplier. Each is presented with explicit sensitivity analysis and validation commitments with pass/fail criteria and named decision owners.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier. The 3× average burst rate is within that range. The 4× instantaneous multiplier applied on top of it is an extrapolation beyond what the cited data supports; the combined 12× peak is explicitly flagged as uncalibrated.

### 1.1.1 Channel Reach, Population Bases, and Volume Counting

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are two delivery mechanisms serving different user states:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Sent to opted-in users regardless of session state.
- **In-app notification:** A UI element rendered within the app for users who are actively in session. This is not a separate dispatch operation — it is the app reading from the user's notification feed on next open or via a real-time socket already established for the session.

**Volume implication:** In-app delivery does not add to the dispatch count. A user in active session who receives a push notification also sees it in-app, but the in-app display is a client-side render of data already fetched — it does not generate a separate outbound API call to an external provider. The 26.5M push figure counts FCM/APNs dispatch operations only. In-app delivery is a read path, not a write path, and is excluded from the dispatch volume model.

The "channel exclusivity" framing used in prior versions was partially misdirected. The real accounting is:

- Push and in-app are not competing channels for the same dispatch budget — they are different delivery mechanisms with different cost structures.
- Email and push can overlap for the same user, but the routing rule (email only when not in active session) prevents double-dispatch for the same event.
- The 34.6M figure counts: push dispatches (26.5M) + email dispatches (8M) + SMS dispatches (~50K) = 34.55M. No double-counting because routing ensures a given notification event dispatches to at most one of {push, email} for any individual user.

#### The Email/In-App Routing Rule and Session-Correlation Problem

Email notifications serve a re-engagement purpose: they reach users not in active session who would otherwise miss a notification. The routing rule is: email is dispatched only when the user has no active session at routing time.

**Why a flat "not in session" fraction is wrong for capacity planning:**

During viral events, session concurrency is elevated — users are in the app precisely because something interesting is happening. The email-eligible fraction drops during the cases that most stress the system. The prior draft's flat 80% figure was wrong in two ways: it overstated the not-in-session fraction during primetime (~65%) and understated it during off-hours (~95%+).

**Revised email volume model:**

| Time Window | Fraction of Daily Volume | "Not in Session" Fraction | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |
| **Weighted daily average** | | | **(0.35×0.65)+(0.40×0.80)+(0.25×0.95) = 78.5% ≈ 78%** |
| **Viral event stress case** | | | **~60%** |

**Interaction with spike arrival rate:** During a viral spike, email-eligible fraction drops from 78% to ~60%. Email is 23% of total daily volume (8M ÷ 34.6M). The volume reduction during spikes: 23% × (1 − 60/78) = 23% × 0.23 ≈ **5% reduction in total spike arrival rate.** This changes the 2,520/sec average burst figure to approximately 2,390/sec — not large enough to change architectural conclusions. The delay calculations in §2.3 use the conservative unreduced 2,520/sec figure; the 5% reduction is a small embedded conservatism.

**Revised daily email volume:**
- Users with verified email, not unsubscribed: 5M (50% of 10M MAU)
- Weighted daily email-eligible fraction: 78%
- Email-eligible notification types per eligible user per day: 2
- **Daily email volume: 5M × 0.78 × 2 = 7.8M/day, rounded to 8M/day**

#### The DAU/MAU Ratio: The Dominant Volume Uncertainty

The prior version provided sensitivity analysis on push opt-in rate but not on the DAU/MAU ratio. This was an error of emphasis: the DAU/MAU ratio drives push volume directly, and push is 77% of total dispatch volume. A swing in DAU/MAU ratio has a larger impact on total volume than the opt-in rate sensitivity already analyzed.

**DAU/MAU ratio sensitivity:**

| DAU/MAU Ratio | DAU | Daily Push Volume | Total Daily Volume | Primetime Rate | Change from Base |
|---|---|---|---|---|---|
| 20% (low engagement) | 2M | 17.7M | ~26M | ~630/sec | −25% |
| **30% (base case)** | **3M** | **26.5M** | **~35M** | **~840/sec** | **—** |
| 40% (high engagement) | 4M | 35.4M | ~44M | ~1,050/sec | +25% |
| 50% (top-quartile) | 5M | 44.2M | ~52M | ~1,260/sec | +50% |

Worker capacity of 3,000/sec handles all scenarios up to and including the 40% DAU/MAU case without architectural changes. The 50% case requires either additional workers or rate limiting; see §2.4.

**Comparison with opt-in rate sensitivity:** A 15-percentage-point swing in opt-in rate (45% to 60%) changes total volume by ±13%. A 10-percentage-point swing in DAU/MAU ratio (30% to 40%) changes total volume by +25%. The DAU/MAU ratio is the larger uncertainty and should be the primary validation target post-launch.

**Validation commitment:** Measure actual DAU/MAU ratio at 500K MAU. If ratio exceeds 45%, re-evaluate worker count before scaling to 2M MAU. Decision owner: engineering lead. Pass/fail criterion: ratio within 20–40% range confirms the base model; above 45% triggers a re-plan.

#### Push Opt-In Rate Sensitivity

| Push Opt-In Rate | Reachable Push Users (of 3M DAU) | Daily Push Volume | Total Daily Volume | Change from Base |
|---|---|---|---|---|
| 45% (pessimistic) | 1.35M | 23.0M | ~31M | −11% |
| **52% (base case)** | **1.56M** | **26.5M** | **~35M** | **—** |
| 60% (optimistic) | 1.80M | 30.6M | ~39M | +11% |

This is a secondary uncertainty relative to the DAU/MAU ratio. Worker capacity handles all three cases without architectural changes.

**Validation commitment:** Measure actual opt-in rate at 100K users (first post-launch cohort). If opt-in exceeds 70%, re-evaluate worker count before scaling to 1M MAU. Decision owner: engineering lead. Pass/fail criterion: opt-in rate within 45–65% confirms the model; outside that range triggers a re-plan.

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

**Retraction:** A prior draft used 35/sec per worker as the sustained planning figure, described as "slightly above the midpoint," while the document's own latency arithmetic produced a midpoint of 31/sec with a 2% retry reduction yielding ~30/sec. 35/sec is 17% above what the arithmetic supports and is optimistic in the wrong direction for a capacity plan. **The planning figure is corrected to 30/sec per worker.**

**Latency budget:**

| Operation | Estimated Latency | Notes |
|---|---|---|
| Redis ZPOPMIN (dequeue) | 0.5ms | p99 on well-provisioned instance |
| Dequeue wait (idle time) | 1ms | Near zero during spike; conservative for off-peak |
| Preference lookup (Redis cache hit) | 0.5ms | Cache miss ~5ms; miss rate <5% once warmed |
| Channel routing logic | 0.1ms | In-process; no I/O |
| Provider API call | 15–40ms | **Dominant cost; FCM/APNs/SES** |
| Retry overhead (amortized) | 0.6ms | 0.3% retry rate × 27.5ms midpoint × 2 retries |
| Synchronization/bookkeeping | 1.5ms | Audit flush, metrics, signal check |
| **Total** | **~19–45ms** | Midpoint: 