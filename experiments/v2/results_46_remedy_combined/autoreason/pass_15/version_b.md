# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

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

**What changed in this revision:** Twelve structural problems identified in review have been addressed. Each is resolved inline at the point of first relevance. The major changes are: (1) the WAND estimate is replaced with a consent-ledger-derived derivation; (2) the consent ledger is specified with schema, consistency guarantees, and failure modes; (3) the OTP GDPR legitimate interests argument is made in full; (4) the P-CB credential breach architecture is completed; (5) the 35% DAU assumption is sourced and sensitivity-analyzed; (6) the stability assessment silent failure mode is closed; (7) the SQS FIFO resharding procedure is specified; (8) load test parameters are defined; (9) the IP pool warm-up schedule is included; (10) the P0 instance count derivation is shown; (11) Phase 1/2 scope boundaries are defined; (12) the ±10 point decision rule is corrected.

---

## Executive Summary

This proposal designs a notification system handling 20–225M notifications/day across push, email, in-app, and SMS channels. Five core architectural choices drive the design:

**SQS for durable queuing.** AWS SQS provides at-least-once delivery guarantees and dead-letter queues that a 4-engineer team cannot replicate in 6 months. Redis is used for preference caching only, not as the delivery backbone. Redis provides no durable at-least-once guarantee; a restart or failover during a queue drain loses in-flight messages silently. SQS visibility timeouts ensure unacknowledged messages are requeued without custom infrastructure.

**Third-party delivery providers.** FCM/APNs for push, SendGrid for email, Twilio for SMS. Each sits behind a thin interface layer; substitution requires no architectural change.

**Fail-closed on suppression checks, with OTP and security alerts carved out on specific legal grounds.** When the preference database is unavailable, most notifications are not delivered. OTP and security alerts use a separate lightweight suppression path with a local cache fallback. The legal basis for this carve-out is a GDPR Article 6(1)(b) contractual necessity argument, not a legitimate interests argument. The full analysis is in Section 7.2. The executive summary previously cited "legitimate interests" incorrectly; that error is corrected here.

**Credential breach SMS as a separate subsystem.** A 10M-recipient blast has fundamentally different throughput characteristics than session-triggered OTP. Sharing the same worker pool would degrade OTP SLA during a breach event. Credential breach is architecturally isolated with its own queue, worker pool, and capacity analysis. The full architecture and capacity analysis are in Section 2.6.

**Phased delivery.** The full feature set is not deliverable in 6 months by 4 engineers. Section 8 specifies exactly what ships in Phase 1 (months 1–4), Phase 2 (months 5–6), and what is deferred post-launch.

**Key tradeoffs made explicitly:**

- Fail-closed compliance behavior means no notifications are sent during a database outage. The alternative — delivering during an outage and reconciling after — creates compliance exposure that outweighs the availability cost. OTP and security alerts are the deliberate exception on specific legal grounds detailed in Section 7.2.
- SQS FIFO is used for P1 (direct messages) because per-conversation ordering matters. SQS Standard is used for P0 (OTP, security alerts) because ordering does not matter and latency does. The resharding migration procedure is in Section 2.4.
- P0 workers are fixed at 8 always-on instances. The derivation is in Section 2.5. The operational risk of a scaling delay on OTP delivery outweighs the cost of always-on capacity.
- Digest email and transactional email use separate IP pools. A spam complaint spike from digest mail blacklisting the password-reset pool is a direct revenue impact. The IP pool warm-up schedule is in Section 3.3.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. They are not interchangeable. Every volume estimate identifies which applies and why.

**MAU (10M):** Monthly active users. Used for push opt-in estimates and credential breach notifications. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 30% of MAU (3M) for pre-launch sizing. The derivation and sensitivity analysis are in Section 1.5. Used for SMS OTP, in-app delivery estimates, and alarm baseline calibration. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from this assumption.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. The WAND figure is *not used for pre-launch infrastructure sizing*. It is not estimable before Week 4 of production. Pre-launch digest sizing uses the consent-ledger-derived eligible population method described in Section 1.3. WAND enters the model at Week 4 as a cross-check against consent-ledger counts, not as the primary input.

| Model | Population | Boundary Type | Why |
|-------|-----------|--------------|-----|
| Push opt-in base | MAU (10M) | Install-bounded | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Install-bounded | Sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Session-bounded | Triggered by active session events |
| In-app | DAU (measured) | Session-bounded | Delivered to active sessions |
| Digest email | Consent-ledger eligible population (pre-Week 4); WAND cross-check (Week 4+) | Consent-bounded | See Section 1.3 |
| Transactional email | Event-driven | Event-bounded | Not population-derived |
| Credential breach SMS | MAU (10M) | Administrative | Proactive; not bounded by session state |

The credential breach row is the only SMS model using MAU. The principled distinction is trigger type: session-bounded events (OTP, security alerts) use DAU because they require an active session. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. The architectural implications of a 10M-recipient SMS send are addressed in Section 2.6.

---

### 1.2 Push Opt-In Rate

**Methodology:** We use OneSignal prompt-conversion benchmarks for social apps as a single methodology-consistent source: iOS ~49%, Android ~81%. These measure the fraction of users who grant permission when shown a prompt — the correct metric for sizing a new app's opted-in population. Averaging across sources that use incompatible methodologies produces a number with no coherent interpretation. We use one source and state its limitations explicitly.

**Acknowledged limitation:** OneSignal's benchmarks derive from apps that chose OneSignal as their push provider — a self-selected sample. The selection bias cannot be quantified before launch.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share. This is the most uncertain single input in the calculation.

Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate | Volume at 15 notifs/day |
|---------------------------|---------------------|------------------------|
| 40/60 | 68.2% | 102M/day |
| 50/50 | 65.0% | 97.5M/day |
| **60/40 (assumed)** | **61.8%** | **92.7M/day** |
| 70/30 | 58.6% | 87.9M/day |

**Day 3 measurement protocol:** On Day 3 of production, platform mix is read directly from device registration logs — every push token registration records the OS. This is a direct measurement, not an estimate.

**Decision rule:** If observed iOS share is outside 55%–65% (±5 points from the assumed 60%), the infrastructure lead produces a revised cost model within 2 business days. If the revised model requires a plan tier change, the decision is escalated to the engineering manager and product owner with a 24-hour decision window.

**Why ±5 points, not ±10:** The previous version used ±10 points and described the 60/40→50/50 shift (~5% volume change) as "within planning tolerance" while placing 50/50 at the trigger boundary. These are inconsistent. A ±5 point threshold means 50/50 is comfortably inside the no-action zone (5 points from center), and 40/60 triggers recalibration at 8 points from center. This aligns the rule with the stated tolerance: shifts producing less than ~5% volume change are within tolerance; shifts producing ~10% or more are not.

Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day. Week 1 production measurement supersedes this estimate.

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** This is a deliverability decision with direct revenue impact. Warm-up schedule and operational ownership are in Section 3.3.

**Transactional email:**

| Event | Daily Volume (Planning Estimate) | Basis |
|-------|----------------------------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | Planning bound only |

**Pre-launch planning bound:** 750K/day is used to size the SendGrid plan tier and load test parameters. It is not an operational alarm threshold.

**Operational alarm threshold:** Set from load test output using the method in Section 1.4. The load test target for transactional email is 500K/day sustained, derived as follows: 230K/day is the low-end planning estimate; 500K/day provides a 2× headroom multiplier, which matches the headroom applied to other channels. The alarm threshold is 1.5× the load-test-established P95 volume baseline.

**Digest email — pre-launch sizing methodology:**

The previous version built digest volume scenarios around a 2M WAND figure with no derivation. WAND cannot be estimated before Week 4. Pre-launch digest sizing uses the consent ledger exclusively.

*What the consent ledger contains at launch:* Every user who completes onboarding is recorded with their digest email preference (opt-in / opt-out / not-shown). The consent ledger schema is specified in Section 7.1. At the moment the first digest job runs (Day 7), the eligible population is the exact count of users who (a) completed onboarding during Days 1–6, (b) opted into digest email, and (c) have a valid email address on record. This count is directly queryable. It is not an estimate.

*Infrastructure sizing:* Because the eligible population on Day 7 is bounded by total users who completed onboarding in the first 6 days, and because that total cannot exceed total new user registrations, the pre-launch sizing bound is derived from the user acquisition plan, not from a WAND estimate. If the acquisition plan projects 500K users in Week 1 and digest opt-in rates are expected to be 20%–60%, the Day 7 ceiling is 300K digest sends. This ceiling is used to size the digest job's worker pool and SendGrid plan tier, not the 2M WAND estimate.

*Week 4 transition:* At Week 4, WAND becomes estimable from session logs. It enters the model as a cross-check: if WAND-derived eligible population diverges more than 20% from the consent-ledger count, the discrepancy is investigated before the next digest send. WAND does not replace the consent ledger as the authoritative source; it supplements it.

| Scenario | Eligible Population Source | Digest Opt-In | Weekly Volume |
|----------|---------------------------|---------------|--------------|
| Day 7 (launch week) | Consent ledger (exact count) | Measured | Consent-ledger-derived ceiling |
| Weeks 2–3 | Consent ledger (cumulative) | Measured | Grows with registration volume |
| Week 4+ steady state | Consent ledger (primary) + WAND (cross-check) | Measured | Recalibrated weekly |

**Dynamic threshold recalibration at steady state:**

1. Each Monday at 06:00 UTC, a scheduled Lambda counts the current opt-in population from the consent ledger directly.
2. The threshold is set to 1.5× the prior week's actual digest send volume, with a floor equal to the consent-ledger-derived eligible population count (not a fixed 1.3M ceiling, which was derived from the now-removed WAND estimate).
3. If the consent ledger query fails, the threshold holds at its last valid value and an alert fires to the on-call engineer. The threshold does not silently reset to a default.
4. The recalibration job's output is logged to a named CloudWatch metric: `digest_threshold_current`. Ownership is by role (on-call rotation).

**Day 7 anomaly threshold:** The eligible population on Day 7 is fully enumerable from the consent ledger. The Day 7 anomaly threshold is set at 2× the consent-ledger-derived eligible population count, calculated at 05:00 UTC on Day 7 before the digest job runs. Using any WAND-derived ceiling as the threshold would allow a bot-driven enrollment attack or instrumentation error to pass undetected. The consent-ledger-derived threshold catches both.

**Dependency note:** If the consent ledger is corrupted by a bot attack, the threshold derived from it will be wrong. This is mitigated by fraud detection controls on the onboarding flow (rate limiting, CAPTCHA), which are outside the scope of this document but are a hard dependency. The notification system cannot be the last line of defense against enrollment fraud.

---

### 1.4 Alarm Baseline Initialization

**Weeks 1–2:** Alarm thresholds use load test baselines. Load tests run during the week before launch per the parameters defined in Section 2.7.

**Baseline promotion:** A 14-day rolling average promotes to replace the load test baseline after 7 consecutive stable days.

**Stable day definition:** A day is stable if:
- No Warning-tier or higher alarms fired *and cleared* during that calendar day (UTC), AND
- No Warning-tier or higher alarms were *active at the start* of that calendar day (UTC), AND
- The day's total message volume is within +20% / −10% of the rolling average of the preceding 7 days.

The second condition closes the silent failure mode identified in review. A sustained outage beginning at 22:00 on Day N−1 and still active at 00:01 on Day N previously left Day N's stability assessment uncontaminated, because the alarm fired on Day N−1. Under the revised rule, Day N is contaminated because a Warning-tier alarm is active at Day N's start. This means a multi-hour outage straddling midnight contaminates both days, which is the correct behavior.

The asymmetric volume bounds are intentional: a traffic spike cannot contaminate its own baseline, and an outage day (traffic 10%+ below average) is excluded to prevent the baseline from drifting downward. The rolling average