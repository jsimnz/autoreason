# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural Critiques

---

## How to Read This Document

This document specifies what the notification system does and why. Design decisions appear inline. Where a decision requires authorization outside the engineering team, the responsible role, required decision, and deadline are identified explicitly.

Ten structural problems were identified in the prior revision. Each is addressed directly. Where a problem exposed a genuine gap, the gap is filled. Where a problem exposed an assertion that cannot be substantiated, the assertion is replaced with a constraint or a decision.

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

**Fail-closed on suppression checks, with OTP carved out under specific conditions.** When the preference database is unavailable, most notifications are not delivered. OTP uses a separate suppression path with explicit TTL and cold-cache behavior — detailed in Section 6.3. The carve-out is bounded, not asserted.

**Phased delivery.** Section 8 specifies exactly what ships in Phase 1 (months 1–4), Phase 2 (months 5–6), and what is deferred post-launch. The feasibility argument is present in this document, not deferred to a missing section.

**Key changes from Revision 1:**

- OTP suppression cache behavior is now fully specified: TTL, cold-cache handling, and the acceptable staleness argument.
- Credential breach SMS is fully scoped in Section 5.3: cost, rate limits, regulatory requirements, and decision authority.
- Digest infrastructure is provisioned to the aggressive scenario ceiling before Day 7, independent of WAND estimation.
- P0 worker capacity is derived from load analysis, not asserted. The fixed-vs-auto-scale decision is justified against actual numbers.
- SQS FIFO resharding is treated as a deferred operation with explicit freeze/drain/repoint procedure, not a solved problem.
- The stable-day definition is revised to accommodate growth-phase traffic patterns.
- OneSignal benchmark limitations are addressed in both directions: the upside scenario is modeled alongside the downside.
- The Day 3 measurement protocol is revised to a same-day decision with a 4-hour action window.
- The digest recalibration job has a named primary owner and a named backup, with a documented handoff procedure.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. They are not interchangeable. Every volume estimate identifies which applies and why.

**MAU (10M):** Monthly active users. Used for push opt-in estimates and credential breach notifications. Push tokens are registered at install and persist across sessions.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from this assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used for digest email modeling at steady state. Cannot be meaningfully estimated until Week 4. Infrastructure provisioning for digest does not depend on this estimate — see Section 1.3.

| Model | Population | Boundary Type | Why |
|-------|-----------|--------------|-----|
| Push opt-in base | MAU (10M) | Install-bounded | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Install-bounded | Sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Session-bounded | Triggered by active session events |
| In-app | DAU (measured) | Session-bounded | Delivered to active sessions |
| Digest email | WAND (estimated from Week 4) | Engagement-bounded | Weekly cadence |
| Transactional email | Event-driven | Event-bounded | Not population-derived |
| Credential breach SMS | MAU (10M) | Administrative | Proactive; not bounded by session state |

**The credential breach row** is the only SMS model using MAU. The principled distinction: session-bounded events (OTP, security alerts) use DAU because they require an active session. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. The full operational scope of a 10M-user SMS send is addressed in Section 5.3.

---

### 1.2 Push Opt-In Rate

**Methodology:** OneSignal prompt-conversion benchmarks for social apps: iOS ~49%, Android ~81%. These measure the fraction of users who grant permission when shown a prompt — the correct metric for sizing a new app's opted-in population.

**Acknowledged limitation — both directions:** OneSignal's benchmarks derive from apps that chose OneSignal as a push provider, a self-selected sample. This bias is not directionally certain:

- If OneSignal customers are smaller or less-engaged apps, the benchmark understates what a well-designed social app achieves. Actual opt-in rates could exceed 75%.
- If OneSignal customers are more push-reliant than average, the benchmark overstates opt-in for apps where push is less central to the product experience. Actual opt-in could fall below 45%.

Both scenarios are modeled. Infrastructure is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day. The 75% ceiling is not treated as a safe upper bound — it is treated as the provisioning target, and the monitoring protocol below detects if actual rates exceed it.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share.

Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | 68.2% |
| 50/50 | 65.0% |
| **60/40 (assumed)** | **61.8%** |
| 70/30 | 58.6% |

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

**Revised Day 1 measurement protocol:**

Platform mix is read from device registration logs continuously from the first registration event. On Day 1 of production, once 10,000 push token registrations have been recorded (expected within the first hour of launch), the infrastructure lead reads the observed iOS/Android split.

**Decision rule — same-day, 4-hour window:**

If observed iOS share is outside 45%–75% at the 10,000-registration mark, the infrastructure lead has 4 hours to produce a revised cost and capacity model. The escalation goes to the engineering manager and product owner simultaneously, not sequentially. The 4-hour window is the decision deadline, not the start of a review cycle.

**Why 45%–75% and 4 hours:** Moving from 60/40 to 50/50 shifts push volume by ~5%, within planning tolerance. Moving outside the 45%–75% band shifts push volume by more than 10% and requires capacity reassessment. Four hours is the minimum operationally credible window for a same-day decision during a launch. If actual load is already stressing the current tier when the threshold is breached, the on-call engineer escalates immediately — the measurement protocol does not override an active capacity incident.

**What "operating on the existing tier" means during the window:** The system continues operating. If P95 push delivery latency exceeds 10 seconds (2× the P0 SLA), the on-call engineer pages the infrastructure lead immediately regardless of where the measurement protocol stands. The measurement protocol governs planned reassessment; active SLA breach governs emergency response.

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** A spam complaint spike from digest mail can blacklist the pool used for password resets. This is a deliverability decision with direct revenue impact and is not negotiable.

**Transactional email:**

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | |

Alert threshold: >750K/day sustained for 30+ minutes.

**Digest email:**

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Infrastructure provisioning:** Digest infrastructure is provisioned to the aggressive scenario ceiling (1.3M/day) before launch. This is not contingent on WAND estimation. The cost of over-provisioning digest infrastructure for the first 4 weeks is lower than the operational risk of being under-provisioned on Day 7 when the first digest send occurs. See Section 5.2 for the cost delta.

**Digest ramp timeline:**

*Days 1–6:* No digest sends. No user has completed a full week.

*Day 7 — First digest send:* Volume is bounded by users who completed onboarding in Week 1 and opted into digest email during that flow. This is a directly measurable count from the consent ledger. Infrastructure is already provisioned to 1.3M/day, so this send cannot exceed provisioned capacity regardless of how many users opted in.

*Days 7–27:* Digest volume grows as more users complete their first week. The eligible population is enumerable from the consent ledger.

*Week 4 onward:* WAND is estimable from session logs. Steady-state digest volume depends on WAND. If steady-state volume approaches 1.3M/day, infrastructure is scaled before the aggressive scenario ceiling is reached — not after.

**Dynamic threshold recalibration at steady state (Week 5+):**

1. Each Monday at 06:00 UTC, a scheduled job counts the current opt-in population from the consent ledger directly.
2. The threshold is set to 1.5× the prior week's actual digest send volume, with a floor of 1.3M/day.
3. If the consent ledger query fails, the threshold holds at its last valid value and an alert fires to the on-call engineer.
4. The recalibration job is owned by Engineer C (primary) and Engineer B (backup). See Section 1.3.1.
5. Output is logged to CloudWatch metric: `digest_threshold_current`.

---

#### 1.3.1 Recalibration Job Ownership

Engineer C owns the digest threshold recalibration job. Engineer B is the designated backup. "Ownership" means:

- The owner reviews the job output each Monday before 09:00 UTC and confirms the threshold updated correctly in Slack (#notifications-ops).
- If the owner is unavailable (illness, PTO, offboarding), the backup performs this review without requiring escalation.
- If both are unavailable, the on-call engineer performs the review. This is documented in the runbook, not an ad-hoc escalation.
- The job's failure behavior (hold last valid value, alert on-call) is a safety net for automated failures, not for ownership gaps. A human reviews the output every week.

The recalibration job is not a single point of failure for alert thresholds — the threshold holds at its last valid value on failure. It is a single point of failure for threshold *accuracy* if ownership lapses. The backup designation and runbook documentation address this directly.

---

### 1.4 Alarm Baseline Initialization

**Weeks 1–2:** Alarm thresholds use load test baselines established during the week before launch.

**Revised stable-day definition:**

The prior definition (a day is unstable if volume is >+20% above the 7-day rolling average) is unsuitable for a growth-phase launch. A social app growing 5% per day will consistently trip the +20% ceiling; the 7-consecutive-stable-days requirement may never be met, leaving load-test baselines active indefinitely.

The revised definition separates growth from anomaly:

A day is **anomaly-flagged** (not "unstable") if:
- A Warning-tier or higher alarm fired that was subsequently confirmed as a true positive (not a threshold calibration artifact), OR
- The day's total message volume is more than +50% above the 7-day rolling average (spike detection, not growth detection), OR
- The day's total message volume is more than −20% below the 7-day rolling average (outage detection).

The +50% ceiling replaces the prior +20% ceiling. This tolerates sustained growth of up to ~6% per day (compounding over 7 days reaches ~50%) before flagging a day as anomalous. Growth above 6%/day should be flagged — that rate is inconsistent with organic growth and warrants review regardless of whether it affects baseline promotion.

**Baseline promotion:** After 14 calendar days, the rolling average replaces the load test baseline regardless of how many anomaly-flagged days occurred, provided fewer than 3 of those 14 days were anomaly-flagged. If 3 or more days were anomaly-flagged, the infrastructure lead reviews manually before promotion.

**Why 14 days unconditional (with the 3-day exception):** Requiring 7 consecutive non-anomalous days during a growth phase creates indefinite baseline staleness. The 14-day promotion with a 3-of-14 exception captures genuine instability (3+ bad days in 2 weeks is a real signal) while preventing the baseline from being held hostage by normal growth volatility.

---

## 2. Delivery Architecture and Priority Logic

### 2.1 Priority Tiers

| Tier | Examples | Delivery SLA | Batching |
|------|---------|-------------|---------|
| P0 — Critical | OTP, account security alerts | <5 seconds P95 | None |
| P1 — High | Direct messages, mentions | <30 seconds P95 | None |
| P2 — Normal | Likes, comments, follows | <5 minutes P95 | Up to 60 seconds |
| P3 — Digest | Weekly digest, marketing | Best-effort, windowed | Batched per user |

P0 and P1 share no queue infrastructure with P2 and P3.

---

### 2.2 Queue Architecture

```
Ingestion API
     │
     ├─► P0 Queue (SQS Standard)       ──► P0 Workers (always-on, minimum 6 instances)
     │
     ├─► P1 Queue (SQS FIFO, sharded)  ──► P1 Workers (auto-scaling, 2–20 tasks)
     │
     ├─► P2 Queue (SQS Standard)       ──► P2 Workers (auto-scaling, 1–30 tasks)
     │
     └─► P3 Queue (SQS Standard)       ──► P3 Workers (scheduled windows, 0–10 tasks)
```

**Why SQS Standard for P0:** OTP