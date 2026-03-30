# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status

This document synthesizes two versions. The primary contributions of each:

**From Version X:** Complete arithmetic derivations with confidence intervals, off-hours spike scenario analysis, routing race condition analysis (§3.2), in-app consistency contract (§4.3), PostgreSQL fallback schema specification (§5.4), timeline cost aggregation (§7.1), and the correction to the reversibility claim (§0.3).

**From Version Y:** The five unvalidated assumptions presented with explicit validation commitments, pass/fail criteria, named owners, and remediation procedures (§1.1); the email volume construction with all intermediate steps shown rather than collapsed; the acknowledgment-required sign-off procedure for open decisions; the corrected worker capacity range derivation (1,300–3,500/sec); and the SMS SLA commitment.

**Where the versions conflicted, the more analytically complete or more conservative treatment is used.** One material conflict is resolved explicitly: Version X's executive summary stated the worker capacity range as 2,200–4,400/sec; Version Y's derivation produces 1,300–3,500/sec. Version Y's derivation is shown in full in §1.2 and is used throughout. The planning figure of 3,000/sec is retained from both versions but its position within the corrected range is explained.

**Figures that remain estimates:**

- **34.6M/day base case volume** rests on five unvalidated assumptions. Correct to within a factor of 2. Infrastructure is sized to handle the factor-of-2 upper bound under sustained load.
- **30/sec per worker** is a planning figure, not a midpoint of the latency range. Derivation is in §1.2. Will be measured at the pre-launch validation gate.
- **Delay figures** are derived from input distributions in §2.3 with construction method shown. They are not SLA commitments.
- **Burst multiplier** scenarios cover 3×, 5×, and 8×. The 8× scenario is planned for, not labeled out of scope. Any multiplier above 8× is a capacity emergency requiring manual intervention.

**Open decisions requiring sign-off:** Three decisions, not two. Decisions A and B interact. See §0.

---

## 0. Open Decisions

### 0.1 Decision A — Worker Allocation Strategy

**Decision owners: product lead and engineering lead jointly.**

**Sign-off procedure:** Both owners must confirm in writing that they have read this section and accept Option C, or nominate an alternative. Silence does not constitute sign-off. If no response is received within 14 days, the engineering lead will escalate to both parties directly before the window closes.

**Default if no explicit sign-off within 14 days: Option C.**

Three options:

- **Option A — Dedicated high-priority worker pool:** Separate process group, separate Redis consumer group. Hard isolation between priority tiers during normal operation; partial isolation during Redis failover because high-priority workers can be configured to retry Redis more aggressively before falling back. Higher operational complexity; appropriate if hard process separation is required.

- **Option B — Weighted fair-share:** Single worker pool with queue weights. Soft isolation during normal operation. No priority isolation during Redis failover — all workers migrate to the PostgreSQL fallback queue together. Lowest complexity; closes no isolation gap during failover.

- **Option C (default) — Weighted fair-share with priority-aware fallback:** Weighted fair-share during normal operation (identical to Option B), with priority-aware PostgreSQL fallback — separate tables per priority tier (`notifications_high_priority`, `notifications_standard_priority`) — activated during Redis unavailability. Workers poll the high-priority table first, then standard. Soft isolation normally; partial isolation during failover via polling discipline rather than hard process separation.

**Rationale for Option C as default:** It closes the specific interaction gap identified in §0.3 — no priority isolation during failover under Option B — at lower operational cost than Option A. The upgrade path from C → A requires approximately 2 engineer-weeks if validation data shows polling-discipline isolation is insufficient. The joint sign-off must answer one explicit question: *Is polling-discipline-based priority isolation during failover sufficient, or is hard process separation required?* If hard separation is required, override the default to Option A before the window closes.

### 0.2 Decision B — Redis Sentinel vs. Redis Cluster

**Decision owner: engineering lead.** Same acknowledgment requirement as Decision A.

**Default if no explicit sign-off within 14 days: Sentinel.**

Rationale: operational complexity favors the simpler option for a 4-engineer team. Sentinel failover takes 10–30 seconds; Cluster failover takes 1–5 seconds. The failover window is handled by the PostgreSQL circuit-breaker fallback (§5.3–5.4), so the practical difference is a 10–25 second delta in fallback exposure, not a hard SLA difference. Cluster becomes appropriate at sustained rates above approximately 15,000/sec or when the failover window becomes a hard SLA constraint — neither condition applies at launch.

### 0.3 Interaction Analysis

The key interaction question: *Is priority isolation required during infrastructure failover, or is degradation acceptable?*

| Scenario | Option A | Option B | Option C |
|---|---|---|---|
| Normal operation, 3× spike | Full isolation | Soft isolation | Soft isolation |
| Redis failover, 10–30 sec | Partial isolation (HP workers retry Redis) | No isolation | Partial isolation (HP workers poll HP table first) |
| Redis failover + 3× spike simultaneously | Partial isolation degrades under load | Severe degradation for all tiers | Partial isolation degrades; better than B |
| PostgreSQL fallback overloaded | HP workers continue retrying Redis; SP workers queue in PG | Both tiers queue in PG together | HP queue drains first; SP accumulates |
| 8× spike, normal operation | Full isolation maintained | Soft isolation; SP severely delayed | Soft isolation; SP severely delayed |

**Combined contingency cost if defaults fire and later require upgrade:** Option C implementation (~1.5 engineer-weeks) plus upgrade to Option A if failover behavior proves insufficient (~2 engineer-weeks) = ~3.5 engineer-weeks total. Whether this fits within the timeline is shown in §7.1.

### 0.4 Correction to Prior Reversibility Claim

An earlier draft stated that Option A "had no defined downgrade path if it proved over-engineered." This claim was asserted without analysis and is only partially correct.

**What is true:** Collapsing a dedicated worker pool into a shared pool requires redeploying worker process groups and reconfiguring the scheduler — approximately 1 engineer-week. Option A is not technically irreversible.

**What is also true:** Option A by inaction — accepting it as default without explicit sign-off — would have committed the team to higher operational complexity during the initial build without a clear decision record. The original concern was about process discipline, not technical reversibility.

**Correction:** The reversibility argument is no longer the primary justification for the default. The primary justification for defaulting to Option C is that it closes the identified interaction gap at lower cost than Option A, with a defined upgrade path if the gap proves to matter in practice.

---

## Executive Summary

This document designs a notification system handling approximately 34.6M dispatch operations per day at the base case across push, email, and SMS channels. The realistic range given model uncertainty is 20M–55M/day. Infrastructure is sized to handle the upper end of the validated range under sustained load.

**Core architectural decision:** A tiered priority queue implemented as two Redis sorted sets — one high-priority, one standard-priority — backed by Redis Sentinel with automatic failover. A circuit breaker routes to a PostgreSQL fallback queue with separate tables per priority tier when Redis is unavailable. Worker allocation defaults to Option C: weighted fair-share during normal operation, priority-aware fallback during Redis unavailability. The architecture handles spikes by accumulating queue depth and draining post-spike — the delay figures below are the cost of that design choice.

**Key figures:**

| Metric | Value | Confidence | Source |
|---|---|---|---|
| Base case daily volume | 34.6M/day | ±50% | §1.1 |
| Sustained primetime rate | ~840/sec | ±50% | §1.2 |
| Worker capacity (100 workers) | 1,300–3,500/sec | Bounded range; derivation in §1.2 | §1.2 |
| Planning figure (100 workers) | 3,000/sec | Conservative bound; measured at validation gate | §1.2 |
| Standard-priority delay, primetime 3× spike | 47 min (CI: 18–95 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, off-hours 3× spike | 28 min (CI: 11–57 min) | Queue model; method in §2.3 | §2.3 |
| High-priority delay, primetime 3× spike | 14 min (CI: 5–28 min) | Queue model; method in §2.3 | §2.3 |
| Standard-priority delay, primetime 8× spike | ~4 hours; queue may not drain | Scenario analysis; §2.4 | §2.4 |
| Redis Sentinel failover window | 10–30 seconds | Vendor-documented | §5.3 |
| SMS p99 delivery target | <60 seconds | SLA commitment | §3.4 |

**Out of scope:** Notification content generation, A/B testing of notification copy, analytics beyond delivery tracking, and the upstream event pipeline that triggers notifications. §7 specifies cut criteria and decision owners if the timeline proves insufficient.

---

## 1. Scale Assumptions and Constraints

### 1.1 Volume Model

We do not know our notification rate before launch. The estimates below are judgment calls anchored by industry reference points. **Five assumptions** drive the majority of sizing uncertainty. Each is flagged as unvalidated and presented with a validation commitment, pass/fail criteria, a named owner, and a remediation procedure.

**Available reference points and their limitations:**

- **Braze industry survey (2021):** Median push send rate 3–5/week per MAU; top-quartile social apps at 2–4/day per DAU. Most relevant but aggregates across app types without segmenting by opt-in rate or geography.
- **Twitter/X internal data (2013):** ~8 notifications/day for active users. Pre-permission-prompt iOS era; used as a lower-bound sanity check only.
- **Firebase engineering posts (2019–2022):** Spike-to-sustained ratios of 3–5× for mid-scale social apps during viral events. This is the entire cited basis for the burst multiplier range. The 8× scenario is extrapolation beyond cited data and is treated as a stress scenario requiring explicit planning, not a routine operating condition.

#### The Five Unvalidated Assumptions

**Assumption 1: DAU/MAU ratio = 30%**
Gives 3M DAU from 10M MAU. Reference range from cited sources: 20–50% for social apps. This is the dominant volume uncertainty — push is 77% of total dispatch volume, and push volume scales directly with DAU. A 10-percentage-point swing changes total volume by approximately 25%.

*Validation commitment:* Measure from beta cohort data at 8 weeks before launch. Owner: data engineering lead. Pass criterion: ratio falls within 25–40%. Fail criterion: ratio falls outside 20–50%.

*Remediation if ratio falls outside 20–50%:* Engineering lead has authority to adjust worker count without further sign-off. Lead time required: 2 weeks (procurement and provisioning). Below 20%: reduce to 60 workers. Above 50%: add 40 workers (to 140 total). Above 60%: escalate to architecture review — queue model assumptions change qualitatively at that point.

**Assumption 2: Notifications per DAU = 8/day**
Anchored by the Twitter/X lower-bound reference and the Braze upper-quartile figure. Treated as the midpoint of a plausible range of 5–12/day.

*Validation commitment:* Measure from beta cohort event logs. Owner: product lead. Pass criterion: 5–12/day. Fail criterion: outside that range. If above 12/day, reassess batching thresholds in §2.2 before launch.

**Assumption 3: Push opt-in rate = 52%**
iOS opt-in rates post-ATT range from 40–65% for social apps (Liftoff, 2022; AppsFlyer, 2023). Android opt-in is higher but Android's share of the user base is unknown. 52% is a conservative midpoint.

*Validation commitment:* Measure from beta permission-prompt flow. Owner: mobile engineering lead. Pass criterion: 40–65%. Fail criterion: outside that range. Volume scales linearly with opt-in rate; engineering lead adjusts worker count using the same authority and lead time as Assumption 1.

**Assumption 4: Session-distribution fractions**
Email routing requires an estimate of how many users have no active session at notification time. We assume 40% of MAU are inactive at any given routing moment during primetime. This determines email volume. See email volume construction below.

*Validation commitment:* Measure session activity distribution from beta session logs. Owner: backend engineering lead. Pass criterion: 30–55% inactive fraction. Fail criterion: outside that range.

**Assumption 5: Email routing model**
Email is routed only to users with no active session at routing time, to avoid double-dispatch. The routing rule and its volume implications are constructed below.

*Validation commitment:* Audit routing logs from beta for double-dispatch rate. Owner: backend engineering lead. Pass criterion: double-dispatch rate below 0.5%. Fail criterion: above 2%.

#### Push and In-App: Clarifying the Relationship

Push and in-app are not two separate dispatch channels for the same event. They are different delivery mechanisms with different cost structures:

- **Push notification:** Delivered by FCM/APNs to the device OS, visible regardless of whether the app is open. Counts as a dispatch operation with an outbound API call to an external provider.
- **In-app notification:** A UI element rendered within the app for users in active session. This is a client-side read of the notification feed — not an outbound API call to an external provider. It does not add to the dispatch count.

A given notification event dispatches to at most one of {push, email} per user. In-app delivery is additive for users in active session who also receive push — they see both the push alert and the in-app badge — but it generates no additional dispatch operation. The failure mode where a user receives a push alert but sees nothing in-app on next open (Redis unavailable, circuit breaker open) is addressed in §4.3.

#### Email Volume Construction

Email volume is derived from the session-distribution model, not estimated independently. All steps shown:

- 10M MAU total; assume 60% have verified email addresses = 6M email-eligible users.
- Of those 6M, assume 70% are not in active session at routing time during primetime (Assumption 4 applied to the email-eligible subset).
- Not every notification event triggers email. Email is sent only for high-value events (new follower, direct message, comment on own post) — estimated at 30% of all notification events by type.
- Daily email volume: 6M eligible × 70% reachable × 30% high-value event fraction × ~6.3 events/day per eligible user ≈ **8M/day**.

The 6.3 events/day figure is derived from 8 events/day per DAU scaled to the email-eligible population, which skews slightly less active. The prior version of this document used a collapsed "78% weighted daily fraction" figure that obscured this construction. The construction above shows all steps. The 8M/day figure carries the same ±50% uncertainty as the push figure.

**Infrastructure note:** Email dispatch is rate-limited by provider API constraints (§3.3), not by internal worker capacity. Email volume does not drive the worker sizing argument.

#### Volume Summary

| Channel | Population Base | Reach | Daily Volume | Notes |
|---|---|---|---|---|
| Push | 3M DAU | 52% opt-in | 26.5M | FCM/APNs dispatch operations only |
| Email | 6M email-eligible MAU | 70% reachable × 30% event fraction | ~8.0M | Session-adjusted; routing-exclusive with push |
| SMS | Auth events only | Event-limited | ~50K | OTP and login alerts; SLA in §3.4 |
| In-app | Active session users | Session-dependent | Not counted | Client-side read; no outbound API call |
| **Total dispatch** | | | **~34.55M/day** | No double-counting |

#### DAU/MAU Sensitivity — Spike-Adjusted

The 5× column uses the upper bound of the Firebase-cited range as the standard stress case. The 8× scenario is addressed separately in §2.4 because it produces qualitatively different failure modes — queue may not