# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system that trades bounded staleness for throughput.

Every tradeoff is named. Where a decision requires authorization outside the engineering team — budget, security posture, legal compliance — that decision point is identified with a named owner, a deadline, and an escalation path. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so consequences are visible.

**What this document commits to:**
- A scale model that is a range with explicit triggers, not a point estimate
- Push opt-in rates defended with industry data and sensitivity-tested across scenarios
- Email volume split into transactional and digest categories with separate models
- FIFO queue throughput ceiling modeled against realistic P1 traffic fractions
- SMS cost exposure controlled with tiered alarms and automated escalation
- Team allocation that resolves the E2 overload problem with specific redistribution
- Three blocking decision points that are named, owned, and deadlined — not papered over

---

## 1. Scale Model

### 1.1 Push Opt-In Rate — Sources, Uncertainty, and Sensitivity

The 55% blended opt-in rate used in the base scenario is derived from the following sources:

- **Airship Mobile Engagement Benchmarks (2023):** Median iOS opt-in of 44% across all categories; social and communication apps trend higher at 52–58% due to value-obvious prompting moments (first DM received, first mention).
- **OneSignal Push Notification Benchmark (2023):** Android opt-in approximately 81% for social apps (opt-out default); iOS approximately 49% across categories.
- **AppsFlyer State of App Marketing (2023):** Delayed permission prompts — shown after a first value moment rather than at install — improve iOS opt-in by 10–15 percentage points.

**Honest uncertainty range:** Based on the spread in these sources, 40–70% is a plausible range for a new social app. The 55% central estimate is defensible but not certain. The architecture is sized for the worst case within this range (70%); costs are modeled at 55% with an explicit delta to the high scenario.

**If actual opt-in falls below 40%:** This signals either a product problem (users are not finding value) or a prompt-design problem. Either way, it is a signal to investigate before treating low push volume as a cost savings.

### 1.2 Traffic Volume — Base and High Scenarios, Side by Side

All volume estimates depend on two figures: notifications per opted-in user per day and the push opt-in rate. Both are unknown before launch. The architecture is sensitive to both.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Traffic model — base and high scenarios:**

| Channel | Base (55%, 15/day) | High (70%, 30/day) | Notes |
|---------|-------------------|-------------------|-------|
| Push/day | 82.5M | 210M | |
| Email — transactional | 500K | 500K | Action-driven; does not scale with opt-in |
| Email — digest | ~526K | ~526K | Modeled in Section 1.3; not a ceiling |
| In-app/day | 30M | 60M | Stored, not delivered; lower cost impact |
| SMS — OTP/security | 175K | 175K | DAU-based; see Section 1.4 |
| Peak throughput | ~4,500/sec | ~9,700/sec | |

**Design choice:** Workers are sized for the high scenario (9,700/sec peak). Over-provisioned workers in the base scenario cost approximately $1,200/month in excess compute. Under-provisioned workers during a high-scenario growth surge cause queue backup during the exact period — rapid user growth — when it is least affordable. The asymmetry favors over-provisioning.

### 1.3 Email Volume — Transactional and Digest Modeled Separately

Treating all email as a single figure obscures two categories with different drivers and different controls. They require separate models.

**Transactional email** is driven by user actions and security events, not batching logic. It cannot be capped by a digest model:

| Event | Daily Volume |
|-------|-------------|
| Account verification (~0.5% of MAU/day) | ~50K |
| Password reset (~0.3% of MAU/day) | ~30K |
| Security alerts — new device login (~1% of MAU/day) | ~100K |
| Billing / policy notices | ~50K |
| **Transactional total** | **~230K–500K/day** |

We model 500K/day and alert if it exceeds 750K/day. Fifty percent above baseline signals either a security incident or an instrumentation error and warrants investigation before it becomes a cost or trust problem.

**Digest email** is explicitly opt-in and explicitly batched. The question is not "what is the ceiling" but "what fraction of users actually opt in and at what cadence."

For a social app, email digest competes with in-app notification inbox and push. Users who are highly active typically prefer push; users who are weekly-active but want to stay connected are the natural digest audience.

**Digest opt-in model:**

| Segment | Estimate | Basis |
|---------|----------|-------|
| Weekly-active but not daily-active users | ~2M (20% of MAU) | Natural digest audience |
| Of those, fraction opting into email digest | ~40% = 800K users | Email feels like a commitment; many prefer in-app |
| Daily digest cadence (60% of opted-in) | 480K users | 480K emails/day |
| Weekly digest cadence (40% of opted-in) | 320K users | ~46K emails/day |
| **Modeled digest total** | **~800K opted-in** | **~526K emails/day** |

**What changes this model:** If the product team designs digest as an aggressive re-engagement lever and promotes it prominently, opt-in rates could be 2–3× higher. If that is the product intent, the volume model should be revised upward before launch. The current model assumes digest is a convenience feature, not a growth lever.

**Alert threshold:** If digest volume exceeds 1M/day sustained, investigate whether the opt-in model is wrong or whether a bug is sending digests to non-opted-in users.

**Revised total email:** ~500K transactional + ~526K digest = ~1.03M/day at base. The critical distinction is that the digest figure is a model, not a ceiling — it will be wrong in specific ways that are diagnosable. A hard ceiling is not diagnosable when it is violated.

### 1.4 SMS Cost — Consistent DAU Basis with Tiered Alarms

SMS is the only channel where a security incident can generate unbounded costs in hours. OTP and security SMS is exempt from engagement caps but tracked separately.

**DAU definition:** For a social app at 10M MAU, DAU is typically 30–50% of MAU. We use 35% as a conservative planning assumption = 3.5M DAU. Actual DAU should be instrumented from day one and this model updated when real data exists.

**SMS cost model — consistent DAU basis throughout:**

| Scenario | Trigger | Volume | Daily Cost (~$0.0079/msg) |
|----------|---------|--------|--------------------------|
| Baseline | 2FA logins, ~5% of DAU | 175K/day | ~$1,383 |
| Elevated | 2FA logins, ~10% of DAU (campaign period) | 350K/day | ~$2,765 |
| Credential stuffing | Forced re-auth, 20% of DAU | 700K/day | ~$5,530 |
| Major incident | Forced re-auth, 50% of DAU | 1.75M/day | ~$13,825 |
| Worst case — full breach | Forced re-auth, all MAU | 10M/day | ~$79,000 |

**Why worst case uses MAU:** If a breach forces password reset for all accounts including inactive ones, the volume is MAU-based. This is the one scenario where MAU is the correct denominator because the trigger is account-level, not session-level. All other scenarios use DAU.

A single $5,000/day alarm creates a $4,999/day blind spot. A moderate credential stuffing attack generating ~630K forced re-auths sits entirely below that threshold with no automated response. The correct structure is tiered alarms with automated escalation at each tier.

**Alarm tiers — calibrated against the corrected ~$1,383/day baseline:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $2,000/day OTP SMS | Log to dashboard; no page |
| Warning | $4,000/day OTP SMS | Page on-call; investigate source |
| Critical | $6,000/day OTP SMS | Page on-call + security team; rate limiting activates |
| Emergency | $10,000/day OTP SMS | Fallback protocol activates; security incident declared |

**Automated response — does not wait for human at Critical tier:**

```python
# Thresholds calibrated against corrected ~$1,383/day baseline
ADVISORY_THRESHOLD_DAILY  = 2000   # USD
WARNING_THRESHOLD_DAILY   = 4000
CRITICAL_THRESHOLD_DAILY  = 6000
EMERGENCY_THRESHOLD_DAILY = 10000

class OTPSMSRateLimiter:
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD_DAILY:
            # Fallback behavior: see Blocking Decision Point 1
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD_DAILY:
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"
            # Users without email OTP: see Blocking Decision Point 1

        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)
        if count > MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"
```

### 1.5 Infrastructure Cost — Base and High Scenarios

| Cost Component | Base Scenario/month | High Scenario/month | Delta |
|----------------|--------------------|--------------------|-------|
| SQS (push + other queues) | ~$1,100 | ~$2,800 | +$1,700 |
| FCM / APNs | $0 | $0 | Free |
| SendGrid (email) | ~$500 | ~$500 | — |
| Twilio (SMS baseline) | ~$1,383 | ~$1,383 | — |
| ECS compute (workers) | ~$800 | ~$2,000 | +$1,200 |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 |
| **Monthly total** | **~$4,483** | **~$7,883** | **+$3,400** |

**Budget authorization requirement:** The high scenario adds approximately $3,400/month over base — $20,400 over six months. This is not an engineering decision. The base scenario is the operational planning assumption. If the high scenario materializes (Scaling Trigger B, Section 2.1), the additional spend requires authorization from the infrastructure budget owner. Engineering will flag the trigger; the budget owner decides whether to authorize or constrain.

### 1.6 Scaling Triggers — Defined Before Launch, Not After an Incident

```
Week 1 target: instrument actual sends per user per day,
               segmented by type (DM, mention, like, digest)

Scaling Trigger A: sustained peak > 6,000/sec for 15 minutes
  Action: Add 30 workers across P1/P2 queues
          Re-evaluate FIFO queue headroom (Section 2.2)
  Owner: E4 | Time budget: 100h reserved (see Section 1.7)

Scaling Trigger B: sustained peak > 10,000/sec for 15 minutes
  Action: P1 queue migration from FIFO to standard queue
          + application-level ordering
  Note: This is a structural change requiring full team review
        and budget authorization before activation
  Owner: E1 | Pre-staged migration plan written in Month 4

Scaling Trigger C: daily volume > 150M notifications for 3 consecutive days
  Action: SQS cost re-projection
          Evaluate whether direct provider integration remains cost-optimal
  Owner: E1
```

Trigger B has a pre-staged migration plan because discovering the need for structural changes under load is the failure mode. The plan is written in Month 4 when the architecture is stable enough to reason about migration paths. It is not written now because the current architecture may evolve before then.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems make Redis the wrong choice for the primary queue tier.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. For P0 traffic (OTPs, security alerts), silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput to approximately 10K writes/second and requires a replication topology the team would need to operate continuously.

**Problem 2 — Dequeue atomicity.** Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity that SQS solves natively with visibility timeouts and message locking.

**Tradeoff explicitly accepted:** Four queue families means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept this because SQS's durability and correct concurrent dequeue semantics are non-negotiable for P0 traffic, and managed operations require less work than operating Redis with AOF replication.

**SQS cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately $1,800/month at base scenario.

### 2.2 Priority Queue Structure

Four queue families, each with a main queue and a DLQ:

| Priority | Queue Type | Use Case | Retention | Visibility Timeout |
|----------|-----------|----------|-----------|-------------------|
| P0 | FIFO | OTP, security alerts, account recovery | 4 hours | 30 seconds |
| P1 | FIFO | DMs, mentions, replies | 24 hours | 60 seconds |
| P2 | Standard | Likes, follows, reactions | 24 hours | 90 seconds |
| P3 | Standard | Digest, marketing, re-engagement | 72 hours | 120 seconds |

**Why FIFO for P0 and P1:** P0 OTPs must not be delivered out of order — a second OTP invalidating a first is correct behavior; delivering them in reverse order is not. P1 direct messages in a conversation must maintain ordering. Standard queues offer best-effort ordering only.

**Why standard for P2 and P3:** Engagement notifications (likes, follows) have no meaningful ordering requirement. Standard queues offer higher throughput and lower cost for this traffic