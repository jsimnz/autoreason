# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system with a **defined 60-second staleness bound** — chosen specifically to allow legal-compliant opt-out propagation within a single cache TTL cycle.

**Ten specific problems are addressed directly:**

1. **DAU/MAU assumption is load-bearing** — Alarm thresholds are expressed as multipliers of a measured Week 1 baseline, not absolute figures derived from the 35% planning assumption. Thresholds self-calibrate after launch.
2. **WAND measurement plan was logically impossible** — A proxy metric is available Day 1; a first WAND cohort is computed after Day 7; a stable estimate arrives Week 4. Infrastructure is provisioned for the aggressive scenario ceiling during the gap, at a known marginal cost.
3. **Peak factor of 5× was unexamined** — Two industry sources are cited. Sensitivity analysis covers 3×, 5×, 8×, and 10×. The shard scaling trigger is explained with explicit arithmetic.
4. **OTP rate limiter had a race condition** — Fixed with a Redis Lua script for atomic check-and-increment.
5. **Transactional email SLA had no measurement mechanism** — SLAs are defined (password reset < 30 seconds, security alert < 60 seconds), separate IP pools are specified, and CloudWatch monitoring is described.
6. **Digest alert threshold logic was inverted** — Volume above the aggressive scenario ceiling triggers an immediate halt and compliance review, not an investigation. CAN-SPAM and GDPR exposure are named explicitly.
7. **Escalation structure was missing** — All blocking decision points appear in Section 7 with named owners, deadlines, and escalation paths.
8. **SMS cost was modeled as flat** — SMS cost now varies between base and high scenarios using a consistent DAU-calibrated model.
9. **Sharding key created head-of-line blocking** — Acknowledged, analyzed for impact, and addressed with per-shard concurrency limits and a rebalancing trigger.
10. **FIFO throughput ceiling was deferred** — Analyzed before launch. P1 uses per-conversation message group IDs. The real ceiling is 3,000 messages/second per queue; addressed with horizontal sharding designed before launch.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable and are not used interchangeably.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption, not a measurement. All operational thresholds that depend on DAU are expressed as multiples of the Week 1 measured baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be measured until at least Day 7 of production traffic. The 2M estimate is the largest single unknown in the volume model. See Section 1.3.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP | DAU (measured) | Requires active login session |
| In-app | DAU (measured) | Delivered to active sessions; stored, not pushed |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |

Any model that switches population without explanation is a bug. This table is the reference.

### 1.2 Push Volume Model

The 55% blended opt-in rate is derived from three sources: Airship Mobile Engagement Benchmarks (2023) — median iOS opt-in of 44% across categories, 52–58% for social apps; OneSignal Push Notification Benchmarks (2023) — Android opt-in approximately 81% for social apps, iOS approximately 49%; AppsFlyer State of App Marketing (2023) — delayed permission prompts improve iOS opt-in by 10–15 percentage points. The honest uncertainty range is 40–70%. The architecture is sized for 70%; costs are modeled at 55%.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Traffic model — base and high scenarios:**

| Channel | Base (55%, 15/day) | High (70%, 30/day) | Notes |
|---------|-------------------|--------------------|-------|
| Push/day | 82.5M | 210M | |
| Email — transactional | ~500K | ~500K | Action-driven; does not scale with opt-in |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | Read/write load on store, not delivery throughput |
| SMS — OTP/security | ~175K | ~350K | High scenario: 2× authentication events |
| Peak throughput | ~4,500/sec | ~9,700/sec | |

**Note on in-app volume:** In-app notifications are stored in a database and fetched on session open. Volume is DAU × average unread notifications, not MAU × notification rate. Cost impact is read/write load on the notification store, modeled separately in Section 5.

### 1.3 Email Volume — Transactional and Digest Modeled Separately

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs. It cannot be capped by batching logic and must not share IP pools with digest mail.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable | Activated when SMS rate-limited |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained. 50% above baseline signals either a security incident or an instrumentation error.

**Digest email** is explicitly opt-in and explicitly batched. The 526K/day figure is a pre-launch estimate with no empirical foundation. It should be treated as an order-of-magnitude estimate, not a forecast.

**The logical problem with pre-launch WAND measurement:** WAND requires at least 7 days of session data by definition. A measurement plan claiming to produce a valid WAND cohort from the first week of production traffic is logically impossible. The stable estimate requires multiple weeks to smooth day-of-week effects.

**Corrected measurement approach:**

*Days 1–7 (proxy metric):* Instrument session frequency distribution from Day 1. Users with exactly one session in the trailing 24 hours are a rough proxy for the WAND segment's engagement level. This is a leading indicator, not the WAND cohort.

*Day 7 onward (first WAND estimate):* Compute users with at least one session in the trailing 7 days and zero sessions yesterday. Valid but noisy — one week cannot distinguish weekly-active users from users who skipped one day.

*Week 4 (stable estimate):* Compute WAND as a rolling 7-day cohort averaged over 4 weeks. This is the first number trustworthy enough to update the digest volume model.

**Infrastructure during the measurement gap:** Provision for the aggressive scenario (1.3M digest emails/day) at SendGrid. The cost of over-provisioning versus the conservative scenario floor is approximately $80/month in SendGrid overage fees — an acceptable insurance cost. We are not provisioning for an unknown; we are provisioning for the worst case in our stated range, at a known marginal cost.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — correct logic:** Any digest volume above 1.3M/day (the aggressive scenario ceiling) triggers an **immediate halt of digest sending and a compliance review before resumption.** Sending marketing email to users who have not opted in is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The consequence is regulatory exposure, not an operational incident. The halt is automatic; resumption requires sign-off from the designated compliance owner (Section 7, Decision Point 4).

### 1.4 SMS Cost Model — DAU-Calibrated, Multiplier-Based Alarms

**The problem with absolute alarm thresholds:** Setting alarms at fixed dollar amounts derived from the 35% DAU/MAU assumption produces false positives if actual DAU differs from the assumption. If actual DAU is 50% of MAU (5M users), the baseline shifts and a $2,000/day advisory threshold fires immediately.

**Corrected approach — multiplier-based alarms calibrated to measured baseline:**

During Week 1, measure actual daily SMS volume and compute a rolling 7-day baseline. Alarm thresholds are set as multipliers of this baseline. The multipliers are chosen based on operational meaning, independent of the underlying DAU figure.

| Tier | Threshold | Operational Meaning | Automated Response |
|------|-----------|--------------------|--------------------|
| Advisory | 1.5× baseline | Elevated but explainable (campaign, feature launch) | Log to dashboard; no page |
| Warning | 2.5× baseline | Outside normal variation; requires explanation | Page on-call; investigate source |
| Critical | 4× baseline | Consistent with credential stuffing attack | Page on-call + security; rate limiting activates |
| Emergency | 7× baseline | Treat as security incident regardless of cause | Fallback protocol; incident declared |

**Why these multipliers:** A 1.5× elevation is within the range of legitimate campaign traffic and day-of-week variation. A 2.5× elevation is outside normal variation and requires an explanation before the end of the on-call shift. A 4× elevation is consistent with a credential stuffing attack at the scale of the elevated scenario. A 7× elevation is consistent with a major incident regardless of the absolute baseline. These multipliers are independent of the 35% DAU assumption.

**SMS cost reference scenarios (pre-launch planning, replaced by measured baseline after Week 1):**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (high engagement scenario) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full breach (all accounts) | **MAU (10M)** | 10M/day | ~$79,000 |

**Why the final row uses MAU:** A full credential breach requires resetting all accounts regardless of session activity. This is the one exception to the DAU-based model, and it is labeled as such everywhere it appears.

### 1.5 Infrastructure Cost

SMS cost now varies between base and high scenarios. The high scenario involves higher engagement, producing more authentication events. We model high-scenario SMS at 2× baseline (350K/day) based on higher per-user engagement, not higher DAU count.

| Cost Component | Base/month | High/month | Delta | Notes |
|----------------|-----------|-----------|-------|-------|
| SQS (all queues, Section 2.3) | ~$1,100 | ~$2,800 | +$1,700 | |
| FCM / APNs | $0 | $0 | — | Free |
| SendGrid — transactional (dedicated IP pool) | ~$300 | ~$300 | — | Action-driven; does not scale with opt-in |
| SendGrid — digest/marketing (shared IP pool) | ~$200 | ~$200 | — | Provisioned for aggressive scenario |
| Twilio (SMS) | ~$1,383 | ~$2,765 | +$1,382 | High: 2× authentication events |
| ECS compute (workers, Section 2.4) | ~$800 | ~$2,000 | +$1,200 | |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 | |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 | |
| **Monthly total** | **~$4,483** | **~$11,265** | **+$6,782** | |

**SendGrid is split into two lines** — transactional and digest/marketing use separate IP pools. This is a deliverability decision: transactional email reputation must not be contaminated by digest sending patterns. See Section 6.4.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems eliminate Redis as the primary queue tier.

**Problem 1 — Durability.** Redis in default configuration loses data on crash. Configuring `appendfsync always` degrades write throughput to approximately 10K writes/second and requires a replication topology the team would need to operate. SQS durability is managed by AWS.

**Problem 2 — Dequeue atomicity.** Two workers executing `ZRANGE + ZREM` simultaneously dequeue overlapping items. The correct fix requires a Lua script. SQS solves this natively with visibility timeouts.

**Tradeoff accepted:** Four queue families means four DLQs and four sets of CloudWatch alarms — more operational surface than a single Redis sorted set. We accept this because correct concurrent dequeue and durability are non-negotiable for P0 traffic.

### 2.2 FIFO Throughput Ceiling — Analyzed Before Launch, Not Deferred

SQS FIFO queues are capped at **3,000 messages/second with batching** (10 messages/batch = 300 API calls/second) per queue. This is a hard AWS limit. It must be designed around before launch, not treated as a future scaling concern.

**P0 analysis:** P0 (OTP, security alerts) is triggered by authentication events. At 5% of DAU triggering OTP SMS, average P0 throughput is approximately 2 messages/second. Even during a concentrated attack generating 700K forced re-auths, peak P0 throughput is approximately 8 messages/second. A single FIFO queue is sufficient for P0 with substantial headroom.

**P1 analysis — this is where the ceiling matters:**

P1 (DMs