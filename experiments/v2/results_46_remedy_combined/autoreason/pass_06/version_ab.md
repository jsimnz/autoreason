# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system with a **defined 60-second staleness bound** — chosen specifically to allow legal-compliant opt-out propagation within a single cache TTL cycle.

**What this document commits to:**
- A scale model expressed as a range with explicit triggers, not a point estimate
- Push opt-in rates defended with industry data and sensitivity-tested across scenarios
- Email volume split into transactional and digest categories with separate models and separate sending infrastructure
- FIFO queue throughput ceiling modeled against realistic P1 traffic fractions, with horizontal sharding designed before launch
- SMS cost exposure controlled with tiered alarms and automated escalation, not a single threshold
- Population definitions used consistently throughout — MAU, DAU, and WAND are not interchangeable
- Three blocking decision points that are named, owned, and deadlined — not papered over

Every tradeoff is named. Where a decision requires authorization outside the engineering team — budget, security posture, legal compliance — that decision point is identified with a named owner, a deadline, and an escalation path. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so consequences are visible.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Three population figures appear in this document. They are not interchangeable and are not used interchangeably.

**MAU (10M):** Monthly active users. Used as the denominator for push opt-in, since push tokens are registered at install and persist across sessions. A user who opens the app once per month still has a push token. Also used for the worst-case SMS breach scenario, where forced re-authentication affects all accounts including inactive ones — this exception is labeled explicitly where it appears.

**DAU (3.5M):** Daily active users, modeled at 35% of MAU. Used for SMS OTP modeling (requires active login session), in-app notification delivery estimates, and all security incident scenarios short of a full credential breach. This figure requires instrumentation from Week 1; 35% is a planning assumption, not a measurement.

**WAND — Weekly-active, not daily-active (2M estimated):** Modeled at 20% of MAU. Used only for digest email modeling. This segment does not exist as a measured cohort before launch and is the figure most likely to be wrong. Section 1.3 describes how we handle that uncertainty.

**Where each population applies:**

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP baseline | DAU (3.5M) | Requires active login session |
| SMS worst-case breach | **MAU (10M)** | Forced reset of all accounts including inactive |
| In-app delivery | DAU (3.5M) | Delivered to active sessions |
| Digest email | WAND (2M estimated) | Natural digest audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |

Any model that switches population without explanation is a bug. This table is the reference.

### 1.2 Push Opt-In Rate — Sources, Uncertainty, and Sensitivity

The 55% blended opt-in rate used in the base scenario is derived from:

- **Airship Mobile Engagement Benchmarks (2023):** Median iOS opt-in of 44% across all categories; social and communication apps trend higher at 52–58% due to value-obvious prompting moments (first DM received, first mention).
- **OneSignal Push Notification Benchmark (2023):** Android opt-in approximately 81% for social apps (opt-out default); iOS approximately 49% across categories.
- **AppsFlyer State of App Marketing (2023):** Delayed permission prompts — shown after a first value moment rather than at install — improve iOS opt-in by 10–15 percentage points.

**Honest uncertainty range:** 40–70% is plausible for a new social app. The architecture is sized for 70%; costs are modeled at 55% with an explicit delta to the high scenario. If actual opt-in falls below 40%, this signals either a product problem or a prompt-design problem and warrants investigation before treating low push volume as a cost saving.

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
| Email — transactional | ~500K | ~500K | Action-driven; does not scale with opt-in |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | Stored, not pushed; cost is DB load, not throughput |
| SMS — OTP/security | ~175K | ~175K | DAU-based; see Section 1.4 |
| Peak throughput | ~4,500/sec | ~9,700/sec | |

**Note on in-app volume:** In-app notifications are stored in a database and fetched on session open, not pushed in real time. Volume is DAU × average unread notifications, not MAU × notification rate. The cost impact is read/write load on the notification store, not delivery throughput, and is modeled separately in Section 5.

**Worker sizing:** Workers are sized for the high scenario (9,700/sec peak). Over-provisioned workers in the base scenario cost approximately $1,200/month in excess compute. Under-provisioned workers during a high-scenario growth surge cause queue backup during the exact period — rapid user growth — when it is least affordable. The asymmetry favors over-provisioning.

### 1.3 Email Volume — Transactional and Digest Modeled Separately, With Honest Uncertainty

Treating all email as a single figure obscures two categories with different drivers, different controls, and different deliverability requirements. They require separate models and separate sending infrastructure.

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs (see Section 6.4). It cannot be capped by batching logic.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable | Activated when SMS rate-limited; see Section 1.4 |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if sustained volume exceeds 750K/day. Fifty percent above baseline signals either a security incident or an instrumentation error — both warrant investigation before they become cost or trust problems.

**Transactional SLAs:** Password reset email must arrive within 30 seconds of trigger. Security alerts must arrive within 60 seconds. These SLAs require a dedicated sending path — see Section 6.4.

**Digest email** is explicitly opt-in and explicitly batched. The 526K/day figure in the traffic table is a pre-launch estimate derived from a model with no empirical foundation. It should be treated as a planning assumption, not a forecast.

**What we know before launch:** Nothing. The WAND segment (2M) is not measured. The digest opt-in rate (40% assumed) is not measured. These are the two largest unknowns in the entire volume model.

| Scenario | WAND Segment | Digest Opt-in | Daily Digest Volume |
|----------|-------------|---------------|-------------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Week 1 measurement plan:** Instrument WAND segment size from actual session data in the first week of production traffic. Instrument digest opt-in rate from the first week of preference UI exposure. Update the digest volume model with real numbers before Month 2. Until then, infrastructure is provisioned for the aggressive scenario at SendGrid to avoid re-provisioning during early growth.

**Alert threshold:** If digest volume exceeds 1.5M/day sustained, investigate whether a bug is sending digests to non-opted-in users before attributing it to organic growth.

**What changes this model:** If the product team designs digest as an aggressive re-engagement lever rather than a convenience feature, opt-in rates could be 2–3× higher. If that is the product intent, the volume model should be revised upward before launch. This is a product decision, not an engineering one.

### 1.4 SMS Cost — DAU-Based Throughout, Tiered Alarms

SMS is the only channel where a security incident can generate unbounded costs within hours. The cost model uses DAU consistently, with one named exception.

**SMS cost model:**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (10% of DAU, campaign period) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% of DAU forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% of DAU forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full breach (all accounts, inactive included) | **MAU (10M)** | 10M/day | ~$79,000 |

**Why the final row uses MAU:** A full credential breach requires resetting all accounts regardless of session activity. This is the one exception to the DAU-based model, and it is labeled as such wherever it appears.

A single $5,000/day alarm creates a $4,999/day blind spot. A moderate credential stuffing attack generating ~630K forced re-auths sits entirely below that threshold with no automated response. The correct structure is tiered alarms with automated escalation at each tier.

**Alarm tiers — calibrated against the ~$1,383/day baseline:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $2,000/day | Log to dashboard; no page |
| Warning | $4,000/day | Page on-call; investigate source |
| Critical | $6,000/day | Page on-call + security team; rate limiting activates automatically |
| Emergency | $10,000/day | Fallback protocol activates; security incident declared |

**Rate limiter — increment occurs only on confirmed send:**

```python
ADVISORY_THRESHOLD_DAILY  = 2000   # USD
WARNING_THRESHOLD_DAILY   = 4000
CRITICAL_THRESHOLD_DAILY  = 6000
EMERGENCY_THRESHOLD_DAILY = 10000
MAX_OTP_SMS_PER_USER_PER_DAY = 5

class OTPSMSRateLimiter:
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD_DAILY:
            # Blocking Decision Point 1: fallback behavior when SMS disabled
            # Default: block with email fallback if available; see Section 3.5
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD_DAILY:
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"
            # Users without email OTP: Blocking Decision Point 1 applies

        # Per-user daily limit check — increment AFTER confirmed send
        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.get(user_key) or 0
        if int(count) >= MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"

    def record_confirmed_send(self, user_id: str):
        # Called only after Twilio confirms dispatch — not before
        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)
```

**Why increment-on-confirm matters:** If the counter increments before the send attempt, a Twilio API failure consumes a user's daily OTP quota without delivering anything. The user cannot authenticate for the rest of the day. Incrementing only on confirmed dispatch avoids this failure mode at the cost of a small race window under extreme concurrent requests — acceptable given the per-user limit is 5/day.

### 1.5 Infrastructure Cost — Base and High Scenarios

| Cost Component | Base/month | High/month | Delta |
|----------------|-----------|-----------|-------|
| SQS (all queues, P1 sharded ×4) | ~$1,100 | ~$2,800 | +$1,700 |
| FCM / APNs | $0 | $0 | Free |
| SendGrid — transactional (dedicated IP pool) | ~$300 | ~$300 | — |
| SendGrid — digest/marketing (shared IP pool) | ~$200 | ~$200 | — |
| Twilio (SMS baseline) | ~$1,383 | ~$1,383 | — |
| ECS compute (workers) | ~$800 | ~$2,000 | +$1,200 |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 |
| **Monthly total** | **~$4,483** | **~$7,883** | **+$3,400** |

**SendGrid line is split:** Transactional and digest email use separate sending infrastructure and separate IP pools. This is a deliverability decision, not a cost optimization. A digest campaign that damages sender reputation must not affect password reset delivery. See Section 6.4.

**Budget authorization requirement:** The high scenario adds approximately $3,400/month over base — $20,400 over six months. This is not an engineering decision. The base scenario is the operational planning assumption. If Scaling Trigger B materializes, the additional spend requires authorization from the infrastructure budget owner before workers are added. Engineering flags the trigger; the budget owner decides.

### 1.6 Scaling Triggers — Defined Before Launch, Not After an Incident

```
Scaling Trigger A: sustained peak > 6,000/sec for 15 minutes
  Action: Add workers across P1/P2 queues (pre-configured ECS task definitions)
          Re-evaluate per-shard P1 FIFO throughput (Section 2.2)
  Owner: E4 | Time budget: 4 hours | Pre-staged: yes

Scaling Trigger B: sustained peak > 10,000/sec for 15 minutes
  Action: P1 queue migration from FIFO to standard queue
          + application-level ordering enforcement
  Note: