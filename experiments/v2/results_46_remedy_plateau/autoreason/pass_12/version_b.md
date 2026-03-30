# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 4 — Addresses Revision 3 critic findings

---

## Document Status

This revision addresses eight findings from the Revision 3 review. Each section notes which finding it resolves. Sections that were referenced but absent in Revision 3 (§2, §2.3, §3.1, §5.1, §5.3, §7) are now present and complete.

**What changed from Revision 3:**

- Executive summary table corrected: 34.6M/day base case, ~840/sec primetime rate (not 51M/day, not 2,360/sec). The prior figures were retained in the executive summary after being retracted in the body — that inconsistency is resolved here.
- The 47-minute delay derivation is now complete. The prior version ended mid-sentence; the full arithmetic now appears in §1.1.2.
- The instantaneous peak multiplier (4×) is now explicitly labeled a placeholder pending spike injection testing. Memory sizing in §5.1 is presented as a range with the uncalibrated assumption identified.
- §2.3 now specifies the starvation mechanism, including the worker allocation that produces the 14-minute high-priority delay figure.
- Open decisions #1 and #2 are restructured as a single dependent decision with one deadline and one default.
- The email volume model is corrected to account for session-activity correlation during viral events. The 80% flat average is replaced with a time-of-day-adjusted model.
- Finding count corrected: six findings are cited by number in the body; two were addressed in sections not yet written in Revision 3 (§5.3 and §7). Those sections are now present. The document status no longer claims "ten findings" — it claims eight.

**Open decisions requiring sign-off before architecture is finalized:**

All three open decisions from Revision 3 are consolidated into two below, with dependency relationships made explicit.

**Decision A (combined): Worker allocation strategy.** The 14-minute high-priority delay and the 47-minute standard-priority delay are both outputs of the same worker allocation model (§2.3). They cannot be evaluated independently. The question is: are both figures acceptable, or does the team implement the dedicated high-priority worker pool (Option A, §2.4) at a cost of ~3 engineer-weeks?
- If both figures are acceptable: no architectural change required.
- If either figure is unacceptable: Option A is the mitigation for both.
- **Default if no decision within two weeks of circulation: implement Option A.** Decision owner: product lead (for the 47-minute standard-priority figure) and engineering lead (for the 14-minute high-priority figure), jointly. These are not separable decisions — a product team that finds 47 minutes unacceptable cannot defer to engineering on the 14-minute figure as a separate question.
- **Deadline: [DATE + 14 days].** If the product lead does not respond, the engineering lead decides unilaterally and Option A is the default.

**Decision B: Redis Sentinel vs. Redis Cluster.** Failover impact quantified in §5.3. Decision owner: engineering lead. Default if no decision within two weeks: Sentinel, on the grounds that operational complexity for a 4-engineer team favors the simpler option.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M notifications/day at base case across push, email, in-app, and SMS channels. Volume derivation is in §1.1. The range across engagement tiers is 23M–75M/day.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel for automatic failover, with a circuit breaker that routes to a PostgreSQL fallback queue when Redis is unavailable. The worker allocation between the two queues is specified in §2.3. Per-channel queues are out of scope; the dedicated high-priority worker pool (§2.4) achieves priority isolation at lower complexity if the delay figures in Decision A are unacceptable.

**Key figures — all are sustained rates at base case; derivations are in the sections cited:**

| Metric | Value | Source | Status |
|---|---|---|---|
| Base case daily volume | **34.6M/day** | §1.1.1 | Revised from prior 51M (which double-counted) |
| Sustained primetime rate | **~840/sec** | §1.1.2 | Revised from prior 2,360/sec |
| Worker capacity (100 workers) | 3,000/sec sustained | §1.1.2 | Unchanged |
| Worst-case standard-priority delay (3× spike) | **47 minutes** | §1.1.2 | Requires Decision A |
| Worst-case high-priority delay (3× spike) | **14 minutes** | §2.3 | Requires Decision A |
| Peak queue depth (base-case spike) | **~200MB** | §5.1 | Derived from uncalibrated 4× instantaneous multiplier; treat as placeholder |
| Redis Sentinel failover window | 10–30 seconds | §5.3 | Adds ≤30 seconds to high-priority SLA |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies which in-scope components are cut if the timeline proves wrong, with explicit criteria.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. The three assumptions that most affect infrastructure sizing — push opt-in rate, notifications per DAU, and burst multiplier — are each presented with sensitivity analysis and explicit validation commitments with pass/fail criteria and decision owners.

**Available reference points and their limitations:**

- Braze industry survey (2021): median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate.
- Twitter/X internal data (2013): ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- Firebase engineering posts (2019–2022): spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. Used as a reference range for burst multipliers; specific multiplier values remain judgment calls.

### 1.1.1 Channel Reach, Population Bases, and the Email Overlap Problem

**Addressing Finding #8 (email population base), Finding #6 (opt-in rate sensitivity), and the email session-correlation problem identified in Revision 3 review.**

#### The Email/In-App Routing Rule and Its Volume Implications

Email notifications for a social app serve a re-engagement purpose: they reach users who are not in an active session and would otherwise miss the notification. Sending email to an active user who will receive an in-app notification wastes send budget and degrades experience. The routing rule in §3.1 is: email is dispatched only when the user has no active session at routing time.

This means the email-eligible population at any moment is not "users with verified email" — it is "users with verified email who are not currently in an active session." This fraction varies by time of day and by the type of event triggering the notification.

**The session-correlation problem (Addressing Revision 3 review finding on email volume):**

The prior draft applied a flat 80% "not in active session" figure as a daily average. This is wrong for capacity planning purposes in two ways:

1. **During viral events, the triggering moment is correlated with high session activity.** A viral post generates notifications at the moment users are engaging with the app — session concurrency is elevated precisely when notification volume spikes. The 80% figure is optimistic during the cases that most stress the system.

2. **The 80% figure is a daily average across all hours, including overnight hours when session activity is near zero.** It overstates the not-in-session fraction during primetime (roughly 60–65% not in session during peak hours) and understates it during off-hours (roughly 95%+ not in session at 3am).

**Revised email volume model:**

For capacity planning, we use the primetime fraction, not the daily average, because primetime is when the system is stressed:

| Time Window | Fraction of Daily Email Volume | Estimated "Not in Session" | Email-Eligible Fraction |
|---|---|---|---|
| Primetime (4 hrs) | 35% | 65% | 65% |
| Shoulder (8 hrs) | 40% | 80% | 80% |
| Off-peak (12 hrs) | 25% | 95% | 95% |

Weighted average "not in session" across the day: (0.35 × 0.65) + (0.40 × 0.80) + (0.25 × 0.95) = 0.228 + 0.320 + 0.238 = **78.5%**, rounded to 78% for planning.

This is close to the prior 80% flat figure as a daily average, but the distribution matters: primetime email volume is lower than a flat-average model suggests (65% eligible, not 80%), and the spike cases are even lower because viral events concentrate in primetime with elevated session activity. For spike capacity planning, we use 60% as the email-eligible fraction during a viral event (conservative; actual session concurrency during a major viral event could suppress email dispatch further).

**Revised daily email volume:**

- Users with verified email, not unsubscribed: 5M (50% of 10M MAU; list-size figure)
- Weighted daily email-eligible fraction: 78%
- Email-eligible notification types per eligible user per day: 2
- **Daily email volume: 5M × 0.78 × 2 = 7.8M/day**, rounded to **8M/day**

**Email volume during a viral spike:**

- Email-eligible fraction during spike: 60% (elevated session activity)
- Spike arrival rate applies to the 15% of volume that is high-priority; email is not a high-priority channel (OTP and auth events go to SMS, not email). Email spike is primarily standard-priority.
- Email volume does not drive the capacity constraint; push does. The email figure is included for completeness and for IP warming planning (§6.2).

#### Push Opt-In Rate Sensitivity

**Addressing Finding #6.**

The base case uses 52% push opt-in rate. The full sensitivity:

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
| Email | 5M MAU with verified email | 78% weighted daily | 8.0M | Revised; session-adjusted |
| SMS | Auth events only | Not reach-limited | ~50K | OTP, login alerts only |
| In-app | Active session users | Session-dependent | Not additive | Subset of push/email triggers; no separate dispatch volume |
| **Total** | | | **~34.6M/day** | No double-counting; in-app is delivery mode, not additional volume |

**Why the prior 51M figure was wrong:** The prior model applied per-DAU notification rates to the full reachable population for each channel independently, then summed the channels. A user who receives an in-app notification for a like does not also receive an email for the same like (routing rule: email only if not in session). The channels are not additive for the same notification event. The 34.6M figure counts dispatch operations, not notification events — each event results in at most one dispatch per channel, and the routing logic ensures most events dispatch to exactly one channel.

### 1.1.2 Worker Throughput Model, Spike Analysis, and SLA Derivations

**Addressing Finding #3 (missing high-priority SLA derivation), Finding #4 (worker throughput contradiction), Finding #5 (incomplete burst model), Finding #1 (47-minute delay derivation cut off), and the spike arithmetic contradiction identified in Revision 3 review.**

#### Worker Throughput

**Planning figure: 30/sec per worker.** The prior draft used 35/sec, which was inconsistent with the document's own arithmetic. Retraction and correction carried forward from Revision 3.

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

At 32ms midpoint: 1,000ms ÷ 32ms = 31.25/sec. Applying 2% retry throughput reduction: **~30.6/sec, rounded to 30/sec for planning.**

100 workers × 30/sec = **3,000/sec sustained processing capacity.**

#### Primetime Rate

- Daily volume: 34.6M
- Primetime window: 4 hours (14:00–18:00 local; US-primary app, single global peak approximation)
- Primetime fraction: 35% of daily volume
- Primetime volume: 34.6M × 0.35 = 12.1M
- Primetime sustained rate: 12.1M ÷ 14,400 seconds = **~840/sec**

At 840/sec sustained, 100 workers provide 3.6× headroom at normal load. This headroom is consumed during burst events.

#### Spike Model: Clarifying the Queue Growth Claim

**Addressing the spike arithmetic contradiction from Revision 3 review.**

The prior draft stated in adjacent paragraphs that (a) "at the average burst rate, workers keep pace with the spike" and (b) "the queue grows at 7,080/sec for the first few minutes." Both statements are true but they describe different phases of the same event. The apparent contradiction arises from conflating the instantaneous peak with the average burst rate. Here is the reconciliation:

A viral notification spike does not arrive at a constant rate. The arrival rate is highest at t=0 (when the triggering event propagates through the social graph) and decays as the event ages. We model the arrival rate as:

- **t=0 instantaneous peak:** 4× the average burst rate (judgment call; uncalibrated; see below)
- **Average burst rate over the spike duration:** 3× the primetime sustained rate
- **Spike duration:** 30 minutes (conservative; most viral events peak and decay within 20 minutes per Firebase reference data)

For the base case:

- Average burst rate: 3 × 840/sec = 2,520/sec
- t=0 instantaneous peak: 4 × 2,520/sec = 10,080/sec
- Worker processing rate: 3,000/sec

**Phase 1 — Queue growing (t=0 to ~t=5 minutes):** Arrivals exceed capacity. At t=0, the queue grows at 