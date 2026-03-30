# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Critic Review

---

## Revision Notes

This revision addresses ten specific findings from the critic review. Each section that changed includes a margin note identifying which finding it addresses. Findings that required architectural changes (not just clarifications) are: #1 (OTP compliance), #3 (P0 capacity), #4 (credential breach architecture), #5 (FIFO resharding), #6 (alarm boundary), #7 (IP pool operations), #9 (single point of failure). Findings #2, #8, and #10 required clarification and additions rather than architectural change.

---

## How to Read This Document

This document specifies what the notification system does. Design decisions appear inline where relevant system behavior is described. Where a decision requires authorization outside the engineering team, the responsible role, required decision, and deadline are identified explicitly.

**Sections:**
1. Scale Model
2. Delivery Architecture and Priority Logic
3. Channel Specifications (Push, Email, SMS, In-App)
4. In-App Notification Store
5. Infrastructure and Cost
6. Failure Handling
7. Compliance and Preference Management
8. Team Scope and Feasibility

---

## Executive Summary

This proposal designs a notification system handling 20–225M notifications/day across push, email, in-app, and SMS channels. Four core architectural choices drive the design:

**SQS for durable queuing.** AWS SQS provides at-least-once delivery guarantees and dead-letter queues that a 4-engineer team cannot replicate in 6 months. Redis is used for preference caching only, not as the delivery backbone.

**Third-party delivery providers.** FCM/APNs for push, SendGrid for email, Twilio for SMS. Each is behind a thin interface layer; substitution requires no architectural change.

**Fail-closed on suppression checks, with OTP carved out on specific legal grounds.** When the preference database is unavailable, most notifications are not delivered. OTP and security alerts use a separate lightweight suppression path with a local cache fallback. The legal basis for this carve-out is analyzed in Section 6.3 — it rests on a specific GDPR legitimate interests argument, not on the circular claim that opt-out categories don't exist for OTP.

**Phased delivery.** The full feature set is not deliverable in 6 months by 4 engineers. Section 8 specifies exactly what ships in Phase 1 (months 1–4), Phase 2 (months 5–6), and what is deferred post-launch.

**Key tradeoffs made explicitly:**

- Fail-closed compliance behavior means no notifications are sent during a database outage. The alternative — delivering during an outage and reconciling after — creates compliance exposure that outweighs the availability cost. OTP is the deliberate exception on specific legal grounds.
- SQS FIFO is used for P1 (direct messages) because per-conversation ordering matters. SQS Standard is used for P0 (OTP, security alerts) because ordering does not matter and latency does.
- P0 workers are sized at 8 fixed instances, not 4. Derivation is in Section 2.5. The operational risk of a scaling delay on OTP delivery outweighs the cost of always-on capacity, but that capacity must first be demonstrated sufficient.
- Credential breach SMS is architecturally separated from P0 OTP. A 10M-recipient blast has different throughput characteristics than session-triggered OTP and cannot share the same worker pool without degrading OTP SLA. This is a distinct subsystem with its own capacity analysis in Section 2.6.
- Digest email and transactional email use separate IP pools. IP pool warm-up schedule, complaint rate monitoring, and operational ownership are specified in Section 3.3.
- SQS FIFO resharding for P1 requires a migration procedure that preserves ordering guarantees during the transition. The procedure is specified in Section 2.4.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. They are not interchangeable. Every volume estimate identifies which applies and why.

**MAU (10M):** Monthly active users. Used for push opt-in estimates and credential breach notifications. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from this assumption.

**Correction to prior version [Finding #8]:** The prior version claimed all DAU-dependent thresholds were expressed as load-test multiples, but the transactional email threshold of 750K/day was derived from population percentage estimates rather than load test output. This is corrected in Section 1.3: the 750K figure is now labeled a pre-launch planning bound, and the operational threshold is set from load test baselines using the same methodology as all other channels.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used for digest email modeling at steady state. Cannot be meaningfully estimated until Day 7; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model.

| Model | Population | Boundary Type | Why |
|-------|-----------|--------------|-----|
| Push opt-in base | MAU (10M) | Install-bounded | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Install-bounded | Sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Session-bounded | Triggered by active session events |
| In-app | DAU (measured) | Session-bounded | Delivered to active sessions |
| Digest email | WAND (estimated from Week 4) | Engagement-bounded | Weekly cadence; see Section 1.3 |
| Transactional email | Event-driven | Event-bounded | Not population-derived |
| Credential breach SMS | MAU (10M) | Administrative | Proactive; not bounded by session state |

The credential breach row is the only SMS model using MAU. The principled distinction is trigger type: session-bounded events (OTP, security alerts) use DAU because they require an active session. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. The architectural implications of a 10M-recipient SMS send are addressed in Section 2.6 — this is not simply a P0 send at higher volume.

---

### 1.2 Push Opt-In Rate

**Methodology:** We use OneSignal prompt-conversion benchmarks for social apps as a single methodology-consistent source: iOS ~49%, Android ~81%. These measure the fraction of users who grant permission when shown a prompt — the correct metric for sizing a new app's opted-in population.

**Acknowledged limitation:** OneSignal's benchmarks derive from apps that chose OneSignal as their push provider — a self-selected sample. The selection bias cannot be quantified before launch.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share.

Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | 68.2% |
| 50/50 | 65.0% |
| **60/40 (assumed)** | **61.8%** |
| 70/30 | 58.6% |

**Day 3 measurement protocol:** On Day 3 of production, platform mix is read directly from device registration logs. If observed iOS share is outside 50%–70%, the infrastructure lead produces a revised cost model within 2 business days.

Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day.

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** Operational ownership and warm-up schedule are in Section 3.3.

**Transactional email:**

The figures below are pre-launch planning estimates used to size infrastructure. They are not the source of operational alarm thresholds. Operational thresholds are set from load test baselines using the method in Section 1.4.

| Event | Daily Volume (Planning Estimate) | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | Planning bound only |

**Pre-launch planning bound:** 750K/day is used to size SendGrid plan tier and load test parameters. It is not an operational alarm threshold.

**Operational alarm threshold:** Set from load test output using the method in Section 1.4. The load test target for transactional email is 500K/day sustained, with P95 latency targets per Section 3.3. The alarm threshold is 1.5× the load-test-established P95 volume baseline.

**Digest email:**

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Digest ramp timeline and threshold behavior [Finding #2]:**

*Days 1–6:* No digest sends.

*Day 7 — First digest send:* Volume is bounded by users who completed onboarding in Week 1 and opted into digest email during that flow. This is a directly measurable count from the consent ledger.

**Day 7 anomaly threshold:** The prior version set the Day 7 anomaly floor at 1.3M/day (the aggressive scenario ceiling). This is wrong. On Day 7, the eligible population is fully enumerable from the consent ledger — it is the count of users who completed onboarding during Week 1 and opted in. The Day 7 anomaly threshold is set at 2× the consent-ledger-derived eligible population count, calculated at 05:00 UTC on Day 7 before the digest job runs. If the eligible population count is 200K users, the threshold is 400K sends. Using the aggressive WAND scenario ceiling as a floor on Day 7 would allow a bot-driven enrollment attack or instrumentation error to pass undetected. The consent-ledger-derived threshold catches both.

**What this does not fully solve:** If the consent ledger itself is corrupted by a bot attack, the threshold derived from it will be wrong. This is mitigated by the fraud detection controls on the onboarding flow (rate limiting, CAPTCHA), which are outside the scope of this document but are a dependency. The notification system cannot be the last line of defense against enrollment fraud.

*Days 7–27:* Digest volume grows as more users complete their first week. Threshold recalibrates daily from the consent ledger.

*Week 4 onward:* WAND is estimable. Threshold transitions to the dynamic recalibration method below.

**Dynamic threshold recalibration at steady state:**

1. Each Monday at 06:00 UTC, a scheduled job counts the current opt-in population from the consent ledger directly.
2. The threshold is set to 1.5× the prior week's actual digest send volume, with a floor of 1.3M/day.
3. If the consent ledger query fails, the threshold holds at its last valid value and an alert fires to the on-call engineer.
4. The recalibration job runs as a scheduled Lambda, not as a task owned by a named individual. Ownership is by role (on-call rotation), not by person. See Section 8 for rotation policy.

---

### 1.4 Alarm Baseline Initialization

**Weeks 1–2:** Alarm thresholds use load test baselines.

**Baseline promotion:** A 14-day rolling average promotes to replace the load test baseline after 7 consecutive stable days.

**Stable day definition:** A day is stable if:
- No Warning-tier or higher alarms fired during that calendar day (UTC), AND
- The day's total message volume is within +20% / −10% of the rolling average of the preceding 7 days.

**UTC day boundary attribution [Finding #6]:** An alarm that spans the UTC midnight boundary is attributed to the day on which it *fired*, not the day on which it cleared. An alarm firing at 23:55 UTC on Day N and clearing at 00:10 UTC on Day N+1 contaminates Day N's stability assessment. Day N+1 is unaffected. This rule is implemented in the stability assessment job: it queries CloudWatch for alarms with `StateTransitionTime` falling within the calendar day UTC window, not alarms that were in ALARM state at any point during the day. The distinction matters: an alarm that fired at 22:00 on Day N−1 and was still active at 00:01 on Day N does not contaminate Day N.

This creates an edge case: an alarm firing at 23:58 and clearing at 00:02 contaminates Day N but is invisible to an on-call engineer reviewing Day N+1's dashboard. The mitigation is that the stability assessment job logs the specific alarms that caused instability to a named CloudWatch metric (`baseline_instability_reason`), so the cause is auditable even if it's no longer active.

**Initialization:** The rolling average for Days 1–7 uses the load test baseline as a synthetic prior. Each day that passes with production data, one load test day is dropped and replaced with the production day.

**Mixed stability window:** If the first 7 production days contain a mix of stable and unstable days, the 7-consecutive-stable-day counter resets on any unstable day.

---

## 2. Delivery Architecture and Priority Logic

### 2.1 Priority Tiers

Every notification is assigned a priority tier at ingestion.

| Tier | Examples | Delivery SLA | Batching |
|------|---------|-------------|---------|
| P0 — Critical | OTP, account security alerts | <5 seconds P95 | None |
| P1 — High | Direct messages, mentions | <30 seconds P95 | None |
| P2 — Normal | Likes, comments, follows | <5 minutes P95 | Up to 60 seconds |
| P3 — Digest | Weekly digest, marketing | Best-effort, windowed | Batched per user |
| P-CB — Credential Breach | Credential breach SMS blast | Best-effort, <4 hours total | Separate subsystem |

Credential breach is assigned its own tier (P-CB) rather than P0. The rationale is in Section 2.6.

---

### 2.2 Queue Architecture

```
Ingestion API
     │
     ├─► P0 Queue (SQS Standard)       ──► P0 Workers (always-on, 8 instances fixed)
     │
     ├─► P1 Queue (SQS FIFO, sharded)  ──► P1 Workers (auto-scaling, 2–20 tasks)
     │
     ├─► P2 Queue (SQS Standard)       ──► P2 Workers (auto-scaling, 1–30 tasks)
     │
     ├─► P3 Queue (SQS Standard)       ──► P3 Workers (scheduled windows, 0–10 tasks)
     │
     └─► P-CB Queue (SQS Standard)     ──► CB Workers (on-demand, 0–20 tasks, rate-limited)
```

P0 and P1 share no queue infrastructure with P2, P3, or P-CB. A backlog in any lower tier cannot delay