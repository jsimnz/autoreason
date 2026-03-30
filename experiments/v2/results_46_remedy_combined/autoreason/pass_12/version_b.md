# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Read This Document

This document specifies what the notification system does, not how this document improved over a prior draft. All design decisions appear inline where the relevant system behavior is described. Cross-references point to sections that exist in this document.

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

**SQS for durable queuing.** AWS SQS provides at-least-once delivery guarantees and dead-letter queues. Redis is used for preference caching only, not as the delivery backbone.

**Third-party delivery providers.** FCM/APNs for push, SendGrid for email, Twilio for SMS. Each is behind a thin interface; substitution requires no architectural change.

**Fail-closed on suppression checks, with OTP carved out.** When the preference database is unavailable, most notifications are not delivered. OTP and security alerts use a separate lightweight suppression path with a local cache fallback — because blocking authentication during a database incident is a worse outcome than the compliance risk of delivering an OTP to a user who opted out of a non-existent OTP opt-out category. This tradeoff is explicit in Section 6.3.

**Phased delivery.** The full feature set is not deliverable in 6 months by 4 engineers. Section 8 specifies exactly what ships in Phase 1 (months 1–4), Phase 2 (months 5–6), and what is deferred post-launch.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. Every volume estimate identifies which applies and why.

**MAU (10M):** Monthly active users. Used for push opt-in estimates and credential breach notifications. Push tokens are registered at install and persist across sessions.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP, in-app delivery, and alarm baseline calibration. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline, not as absolute figures derived from this assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used for digest email modeling. Cannot be meaningfully estimated until Day 7; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model.

| Model | Population | Boundary Type | Why |
|-------|-----------|--------------|-----|
| Push opt-in base | MAU (10M) | Install-bounded | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Install-bounded | Sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Session-bounded | Triggered by active session events |
| In-app | DAU (measured) | Session-bounded | Delivered to active sessions |
| Digest email | WAND (estimated from Week 4) | Engagement-bounded | Weekly cadence; see Section 1.3 |
| Transactional email | Event-driven | Event-bounded | Not population-derived |
| Credential breach SMS | MAU (10M) | Administrative | Proactive; not bounded by session state |

The credential breach row is the only SMS model using MAU. The principled distinction is trigger type: session-bounded events use DAU; proactive administrative actions affecting all accounts use MAU. The full cost of a credential breach SMS send to all 10M users is modeled in Section 5.3.

---

### 1.2 Push Opt-In Rate

We use OneSignal prompt-conversion benchmarks for social apps as a single methodology-consistent source: iOS ~49%, Android ~81%. These measure the fraction of users who grant permission when shown a prompt — the right metric for sizing a new app's opted-in population.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share. Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | 68.2% |
| 50/50 | 65.0% |
| **60/40 (assumed)** | **61.8%** |
| 70/30 | 58.6% |

**Day 3 measurement protocol:** On Day 3 of production, platform mix is read directly from device registration logs — every push token registration records the OS. If observed iOS share is outside 50%–70%, the infrastructure lead produces a revised cost model within 2 business days. If the revised model requires a plan tier change, the decision is escalated to the engineering manager and product owner with a 24-hour decision window. The system can operate on the existing tier during this window; the aggressive scenario is already provisioned.

Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day.

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** A spam complaint spike from digest mail can blacklist the pool used for password resets. This is not negotiable.

**Transactional email:**

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | |

Alert threshold: >750K/day sustained for 30+ minutes. This is 50% above ceiling and signals a security incident or instrumentation error.

**Digest email:**

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Digest ramp timeline:**

*Days 1–6:* No digest sends. No user has completed a full week.

*Day 7 — First digest send:* Volume is bounded by users who completed onboarding in Week 1 and opted into digest email. This is a directly measurable count from the consent ledger, not a WAND estimate.

*Days 7–27:* Digest volume grows as more users complete their first week. The eligible population is fully enumerable from the consent ledger.

*Week 4 onward:* WAND is now estimable from session logs. Steady-state digest volume depends on WAND.

**Dynamic threshold recalibration at steady state:**

The digest anomaly threshold is not a fixed number. It is recalibrated weekly starting in Week 5, as follows:

1. Each Monday at 06:00 UTC, a scheduled job counts the current opt-in population from the consent ledger (not estimated from WAND).
2. The threshold is set to 1.5× the prior week's actual digest send volume, with a floor of 1.3M/day (the aggressive scenario ceiling).
3. If the consent ledger query fails, the threshold holds at its last valid value and an alert fires to the on-call engineer. The threshold does not silently reset to a default.
4. The recalibration job is owned by Engineer C (Section 8). Its output is logged to a named CloudWatch metric: `digest_threshold_current`.

This means the threshold tracks actual population growth rather than decaying against a stale WAND estimate.

---

### 1.4 Alarm Baseline Initialization

**Weeks 1–2:** Alarm thresholds use load test baselines. Load tests run during the week before launch and establish per-channel message rates at P50 and P95.

**Baseline promotion:** A 14-day rolling average promotes to replace the load test baseline after 7 consecutive stable days.

**Stable day definition:** A day is stable if:
- No Warning-tier or higher alarms fired during that calendar day (UTC), AND
- The day's total message volume is within +20% / −10% of the rolling average of the preceding 7 days.

The rolling average used to assess Day N uses Days N−7 through N−1 — it does not include Day N itself. This prevents a day from influencing its own stability assessment. Stability is assessed retrospectively at 00:05 UTC each day for the prior calendar day.

**Initialization:** The rolling average for Days 1–7 uses the load test baseline as a synthetic prior. Each day that passes with production data, one load test day is dropped and replaced with the production day. By Day 8, the rolling average is entirely production-derived.

**Mixed stability window:** If the first 7 production days contain a mix of stable and unstable days, the 7-consecutive-stable-day counter resets on any unstable day. The load test baseline remains active until 7 consecutive stable days are observed. This may extend the load-test-baseline period beyond 14 days; that is acceptable — the cost is a slightly stale baseline, not a safety failure.

---

## 2. Delivery Architecture and Priority Logic

### 2.1 Priority Tiers

Every notification is assigned a priority tier at ingestion. The tier determines queue routing, delivery SLA, and batching behavior.

| Tier | Examples | Delivery SLA | Batching |
|------|---------|-------------|---------|
| P0 — Critical | OTP, account security alerts | <5 seconds P95 | None |
| P1 — High | Direct messages, mentions | <30 seconds P95 | None |
| P2 — Normal | Likes, comments, follows | <5 minutes P95 | Up to 60 seconds |
| P3 — Digest | Weekly digest, marketing | Best-effort, windowed | Batched per user |

P0 and P1 share no queue infrastructure with P2 and P3. A P2/P3 backlog cannot delay a P0 notification.

---

### 2.2 Queue Architecture

```
Ingestion API
     │
     ├─► P0 Queue (SQS Standard)      ──► P0 Workers (always-on, 4 instances min)
     │
     ├─► P1 Queue (SQS FIFO, sharded) ──► P1 Workers (auto-scaling)
     │
     ├─► P2 Queue (SQS Standard)      ──► P2 Workers (auto-scaling)
     │
     └─► P3 Queue (SQS Standard)      ──► P3 Workers (scheduled windows)
```

**Why SQS Standard for P0:** P0 notifications (OTP, security alerts) do not require ordering — a user receiving two OTPs in the same second benefits from neither FIFO nor deduplication. SQS Standard provides higher throughput and lower latency than FIFO. At-least-once delivery is acceptable; idempotency is enforced at the worker level via a delivery log keyed on `(user_id, notification_id)`.

**Why SQS FIFO for P1:** Direct messages and mentions benefit from per-conversation ordering. A user should not see "reply" before "original message." FIFO provides this at acceptable throughput for P1 volumes.

---

### 2.3 Batching Logic

**P2 batching:** Workers hold P2 notifications for a given user for up to 60 seconds before dispatching. If a user receives 5 "likes" in 60 seconds, they receive one push notification ("5 new likes") rather than 5. The batcher runs in-memory within the worker process; no external state store is required. If the worker crashes during a batch window, the undelivered notifications are re-read from SQS (visibility timeout: 90 seconds) and delivered individually — the batching optimization is lost but no notifications are dropped.

**P3 batching:** Digest notifications are assembled by a scheduled job, not a streaming worker. The job runs at configurable per-user delivery windows (default: 8 AM local time). Per-user delivery windows are stored in the preference database and cached in Redis with a 5-minute TTL.

---

### 2.4 SQS FIFO Sharding for P1

**The problem:** SQS FIFO supports up to 3,000 messages/second per queue with batching (300/second without). At the aggressive push scenario (225M notifications/day), average rate is ~2,600/second across all tiers. P1 is a subset of this, but during peak hours the P1 rate can exceed the single-queue ceiling.

**The solution:** P1 notifications are distributed across N FIFO queues using consistent hashing on `conversation_id`. Per-conversation ordering is preserved because all messages for a given conversation always route to the same queue. Cross-conversation ordering is not guaranteed — this is acceptable; a user does not need replies from conversation A to arrive before messages from conversation B.

**Shard count:** We provision 4 FIFO queues at launch. At 3,000 messages/second per queue, this supports 12,000 P1 messages/second — sufficient for 8× peak factor on the base estimate. Queue count is a configuration value; adding shards requires no code change, only worker configuration update and a queue provisioning step.

**Shard routing:** The ingestion API computes `queue_index = hash(conversation_id) % shard_count`. `shard_count` is read from a configuration parameter (AWS SSM Parameter Store) at worker startup and cached for 60 seconds. Changing `shard_count` requires a rolling worker restart; messages in-flight during the restart may be delivered out of per-conversation order for the duration of the restart window (~2 minutes). This is an acceptable brief degradation during a planned scaling event.

**Peak factor analysis:**

| Peak Factor | P1 messages/sec | Queues needed | Provisioned headroom |
|------------|----------------|---------------|---------------------|
| 3× | ~780 | 1 | 4× headroom |
| 5× | ~1,300 | 1 | 2.3× headroom |
| 8× | ~2,080 | 1 | 1.4× headroom |
| 10× | ~2,600 | 1 | At ceiling — add shard |

At 10× peak, a 5th shard is added. The CloudWatch alarm `p1_queue_depth_per_shard` triggers at 80% of throughput ceiling (2,400 messages/second) and initiates the shard-add runbook automatically via Lambda. The runbook is pre-written and tested pre-launch.

---

### 2.5 Worker Scaling

Workers are ECS Fargate tasks. Scaling is driven by SQS queue depth, not CPU.

| Queue | Scale-out trigger | Scale-in trigger | Min tasks | Max tasks |
|-------|-----------------|-----------------|-----------|-----------|
| P0 | Always-on | Never | 4 | 4 (fixed) |
| P1 | >1,000 messages | <100 messages for 5 min | 2 | 20 |
| P2 | >5,000 messages | <500 messages for 5 min | 1 | 30 |
| P3 | Scheduled window | End of window | 0 | 10 |

P0 workers are fixed at 4 instances. We do not scale P0 dynamically — the operational risk of a scaling delay on an OTP delivery outweighs the cost of 2 additional always-