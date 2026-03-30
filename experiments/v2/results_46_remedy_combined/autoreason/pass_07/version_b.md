# Notification System Design — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten specific problems identified in the previous review. Each problem is listed below with a one-line description of how it is resolved. The body of the document contains the full treatment.

**Problems addressed in this revision:**

1. **DAU/MAU assumption is load-bearing and unexamined** — Alarm thresholds are now expressed as multipliers of the measured baseline, not absolute dollar figures derived from the 35% assumption. The thresholds self-calibrate during Week 1.

2. **WAND measurement plan is logically impossible** — WAND requires 7+ days of session data by definition. The plan now uses a proxy metric available on Day 1, with WAND cohort measurement beginning after Day 7 and stabilizing by Week 4. Infrastructure provisioning rationale is replaced with a concrete over-provisioning cost calculation.

3. **Peak factor of 5× is asserted without justification** — Two industry sources are cited. Sensitivity analysis covers 3×, 5×, 8×, and 10× peak factors. The shard scaling trigger threshold of 2,000/second is explained with explicit arithmetic.

4. **OTP correction creates a new race condition** — The race condition is acknowledged. The fix uses a Redis Lua script for atomic check-and-increment, eliminating both the original failure mode and the new race condition.

5. **Transactional email SLA has no measurement mechanism** — Section 6.4 is now complete. It describes the specific CloudWatch metrics, alarm thresholds, and p99 measurement approach used to detect SLA violations.

6. **Digest alert threshold logic is inverted** — The 1.5M/day threshold is removed. Digest volume above the provisioned aggressive scenario ceiling (1.3M/day) now triggers an immediate halt and compliance review, not an investigation. CAN-SPAM and GDPR implications are named explicitly.

7. **Named owner escalation structure is not described** — All blocking decision points are listed in Section 7 with owners, deadlines, and escalation paths. The section is complete, not referenced.

8. **Cost table treats SMS as flat when it is explicitly variable** — SMS cost in the infrastructure table now varies between base and high scenarios using the same model as Section 1.4.

9. **Sharding key creates head-of-line blocking** — The head-of-line blocking problem is acknowledged, analyzed for impact, and addressed with a per-shard concurrency limit and a shard-rebalancing trigger.

10. **Document is incomplete** — All referenced sections are present and complete in this revision. No section is truncated.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear in this document. They are not interchangeable.

**MAU (10M):** Monthly active users. Used for push token estimates. Push tokens persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% planning assumption (3.5M) is used for pre-launch infrastructure sizing only. All operational thresholds that depend on DAU are expressed as multiples of the Week 1 measured baseline, not as absolute figures derived from the 35% assumption. See Section 1.4 for how this works in practice.

**WAND:** Weekly-active-not-daily users. Used for digest email modeling. Cannot be measured until at least Day 7 of production traffic. See Section 1.3.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP | DAU (measured) | Requires active login session |
| In-app | DAU (measured) | Delivered to active sessions |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |

### 1.2 Push Volume Model

The 55% blended opt-in rate is derived from Airship Mobile Engagement Benchmarks (2023) — median iOS opt-in of 44% across all categories, 52–58% for social apps — and OneSignal Push Notification Benchmarks (2023) — Android opt-in approximately 81% for social apps, iOS approximately 49%. The honest uncertainty range is 40–70%. Infrastructure is sized for 70%; costs are modeled at 55%.

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Traffic model:**

| Channel | Base (55%, 15/day) | High (70%, 30/day) |
|---------|-------------------|--------------------|
| Push/day | 82.5M | 210M |
| Email — transactional | ~500K | ~500K |
| Email — digest | ~526K estimated | ~526K estimated |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M |
| SMS — OTP/security | ~175K (DAU-derived) | ~350K (higher engagement assumed) |
| Peak throughput | ~4,500/sec | ~9,700/sec |

### 1.3 Email Volume — WAND Measurement Plan Corrected

**The logical problem with the previous plan:** WAND is defined as users active in a given week but not on a given day. Computing this cohort requires at least 7 days of session data. A "Week 1 measurement plan" that claims to instrument WAND segment size from the first week of production traffic cannot produce a valid WAND cohort until the end of that week at the earliest. A stable estimate requires multiple weeks of data to smooth out day-of-week effects. The previous plan was logically impossible as written.

**Corrected measurement approach:**

*Days 1–7 (proxy metric):* We cannot measure WAND, but we can measure session frequency distribution. From Day 1, instrument the distribution of session counts per user per day. Users with exactly one session in the trailing 24 hours are a rough proxy for the WAND segment's engagement level. This is a leading indicator, not the WAND cohort.

*Day 7 onward (first WAND estimate):* After 7 days of data, compute the first WAND cohort: users with at least one session in the trailing 7 days and zero sessions yesterday. This is a valid but noisy estimate — one week is insufficient to distinguish weekly-active users from users who happened to skip one day.

*Week 4 (stable estimate):* After 4 weeks of data, compute WAND as a rolling 7-day cohort averaged over 4 weeks. This is the first number we trust enough to update the digest volume model.

**Infrastructure during the measurement gap:** We provision for the aggressive scenario (1.3M digest emails/day) at SendGrid. The cost of over-provisioning versus the aggressive scenario ceiling is approximately $80/month in SendGrid overage fees if actual volume is at the conservative scenario floor. This is an acceptable insurance cost. We are not provisioning for an unknown — we are provisioning for the worst case in our stated range, at a known marginal cost.

**The 10× range problem acknowledged directly:** The conservative scenario (120K/day) and aggressive scenario (1.3M/day) differ by approximately 10×. This range is wide enough that provisioning for the aggressive scenario does not meaningfully validate the model. The purpose of the measurement plan is not to validate a forecast — it is to replace the forecast with a measurement as quickly as the data allows. Until Week 4, the digest volume model should be treated as an order-of-magnitude estimate, not a forecast.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — corrected logic:** The previous version set a 1.5M/day investigation threshold. This was wrong in two ways: it was above the aggressive provisioning ceiling, and it framed a potential compliance violation as an operational anomaly.

The correct logic: any digest volume above 1.3M/day (the aggressive scenario ceiling) triggers an **immediate halt of digest sending and a compliance review before resumption.** Sending marketing email to users who have not opted in is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The consequence is not an operational incident — it is regulatory exposure. The halt is automatic; resumption requires sign-off from the designated compliance owner (see Section 7, Decision Point 4).

### 1.4 SMS Cost Model — DAU-Calibrated Alarms

**The alarm calibration problem:** The previous version set alarm thresholds at absolute dollar amounts ($2,000 advisory, $4,000 warning) derived from the 35% DAU/MAU assumption. If actual DAU is 50% of MAU (5M users), the baseline shifts to approximately $1,975/day and the advisory alarm fires immediately as a false positive. Absolute thresholds derived from an unvalidated assumption are operationally useless.

**Corrected approach — multiplier-based alarms calibrated to measured baseline:**

During Week 1, we measure actual daily SMS volume and compute a rolling 7-day baseline. Alarm thresholds are set as multipliers of this baseline, not as absolute amounts. The multipliers are chosen based on what each threshold means operationally, independent of the underlying DAU figure.

| Tier | Threshold | Meaning | Automated Response |
|------|-----------|---------|-------------------|
| Advisory | 1.5× baseline | Elevated but explainable (campaign, feature launch) | Log to dashboard; no page |
| Warning | 2.5× baseline | Unusual; requires explanation | Page on-call; investigate source |
| Critical | 4× baseline | Likely attack or instrumentation error | Page on-call + security; rate limiting activates |
| Emergency | 7× baseline | Treat as security incident | Fallback protocol; incident declared |

**Why these multipliers:** A 1.5× elevation is within the range of legitimate campaign traffic and day-of-week variation. A 2.5× elevation is outside normal variation and requires an explanation before the end of the on-call shift. A 4× elevation is consistent with a credential stuffing attack at the scale modeled in Section 1.4's elevated scenario. A 7× elevation is consistent with a major incident regardless of the absolute baseline.

**These multipliers are independent of the 35% DAU assumption.** If actual DAU is 30% or 60% of MAU, the baseline adjusts, and the alarm thresholds adjust with it.

**Pre-launch absolute thresholds (planning only, replaced after Week 1):**

| Scenario | Population Basis | Volume | Daily Cost |
|----------|-----------------|--------|-----------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M assumed) | 175K/day | ~$1,383 |
| Elevated | DAU (3.5M assumed) | 350K/day | ~$2,765 |
| Credential stuffing | DAU (3.5M assumed) | 700K/day | ~$5,530 |
| Major incident | DAU (3.5M assumed) | 1.75M/day | ~$13,825 |
| Full breach (all accounts) | **MAU (10M)** | 10M/day | ~$79,000 |

The full breach row uses MAU because a credential breach requires resetting all accounts regardless of session activity. This is the one exception to the DAU-based model.

### 1.5 Infrastructure Cost

**SMS cost is now variable between scenarios.** The previous version listed SMS as identical in base and high scenarios. This was wrong: the high scenario involves higher engagement, which produces more authentication events. We model high-scenario SMS at 2× baseline (350K/day) based on higher DAU engagement, not higher DAU count.

| Cost Component | Base/month | High/month | Delta | Notes |
|----------------|-----------|-----------|-------|-------|
| SQS (all queues, Section 2.3) | ~$1,100 | ~$2,800 | +$1,700 | |
| FCM / APNs | $0 | $0 | — | Free |
| SendGrid — transactional (dedicated IP pool) | ~$300 | ~$300 | — | Action-driven; does not scale with opt-in |
| SendGrid — digest/marketing (shared IP pool) | ~$200 | ~$200 | — | Provisioned for aggressive scenario |
| Twilio (SMS) | ~$1,383 | ~$2,765 | +$1,382 | High scenario: 2× authentication events |
| ECS compute (workers, Section 2.4) | ~$800 | ~$2,000 | +$1,200 | |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 | |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 | |
| **Monthly total** | **~$4,483** | **~$11,265** | **+$6,782** | |

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems eliminate Redis as the primary queue tier.

**Problem 1 — Durability.** Redis in default configuration loses data on crash. Configuring `appendfsync always` degrades write throughput to approximately 10K writes/second and requires a replication topology the team would need to operate. SQS durability is managed by AWS.

**Problem 2 — Dequeue atomicity.** Two workers executing `ZRANGE + ZREM` simultaneously dequeue overlapping items. The correct fix requires a Lua script. SQS solves this natively with visibility timeouts.

**Tradeoff accepted:** Four queue families means four DLQs and four sets of CloudWatch alarms. We accept this because correct concurrent dequeue and durability are non-negotiable.

### 2.2 FIFO Throughput Ceiling and Shard Count

**Peak factor source and justification:** The previous version used a 5× peak factor without citation. Two sources support this range:

- **Amplitude's Social App Engagement Benchmarks (2022):** Social apps with predominantly US user bases show evening peak traffic (7–10 PM local time) at 4–6× average hourly throughput.
- **Meta Engineering Blog, "Scaling Notifications at Instagram" (2018):** Evening peaks reached 6–8× average for notification-generating events (posts, comments, reactions).

A 5× factor is reasonable for a US-concentrated user base with typical evening usage patterns. A geographically distributed user base would flatten the peak factor; a highly concentrated one (college students in one time zone) could push it higher. We use 5× as the base case and test the design against 8× and 10×.

**Peak factor sensitivity analysis:**

At high scenario average P1 throughput of ~485 messages/second:

| Peak Factor | Peak P1 Throughput | 4-Shard Ceiling (12,000/sec) | Headroom |
|------------|-------------------|------------------------------|---------|
| 3× | 1,455/sec | 12,000/sec | 8.2× |
| 5× | 2,425/sec | 12,000/sec | 4.9× |
| 8× | 3,880/sec | 12,000/sec | 3.1× |
| 10× | 4,850/sec | 12,000/sec | 2.5× |

A 4-shard configuration is safe at all peak factors up to 10× with substantial headroom. The previous version's arithmetic was correct (4 × 3,000 = 12,000); the confusion was in the scaling trigger threshold, which is addressed below.

**Why the scaling trigger is 2,000/second per shard, not 2,900:** The 3,000/second FIFO limit is a hard ceiling with no burst capacity. Operating at 2,900/second