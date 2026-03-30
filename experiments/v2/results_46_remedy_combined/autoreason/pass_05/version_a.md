# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 20–210M notifications/day across push, email, in-app, and SMS channels, depending on which traffic scenario materializes. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system that trades occasional staleness for throughput.

Every tradeoff is named. Where a decision requires authorization from outside the engineering team — budget, product behavior, legal compliance — that decision point is identified and the engineering default is stated. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so the consequences are visible.

**Key design decisions and their rationale:**
- Scale model is a range with explicit scaling triggers, not a point estimate
- Push opt-in rate is defended with industry data and sensitivity-tested across scenarios
- Email volume is split into transactional and digest categories with separate models
- FIFO queue throughput ceiling is modeled against realistic P1 traffic fractions, not assumed safe
- DLQ processing is designed as a first-class feature with per-priority strategies
- SMS cost exposure is controlled with tiered alarms and automated escalation
- Team allocation resolves the E2 overload problem identified in review

---

## 1. Scale Model

### 1.1 The Notification Rate Problem

All volume estimates depend on two figures: notifications per opted-in user per day, and the push opt-in rate. Both are unknown before launch. The architecture is sensitive to both.

**Push opt-in rate — defended with industry data:**

Industry data for social apps: iOS opt-in rates post-iOS 14 range from 40–55% for apps that prompt at first launch; rates improve to 55–70% when apps delay the prompt until after demonstrated value. Android opt-in is higher, approximately 70–80%, because opt-out is the default. For a mixed-platform social app with a thoughtful prompt strategy, a blended 55% opt-in rate is a reasonable central estimate.

**Why this matters:** The difference between 40% and 70% opt-in on a 10M MAU base is 3M opted-in users — 45M push notifications/day at the base notification rate. That is not a rounding error; it changes worker sizing and provider costs materially.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Design choice:** We size push worker capacity for the 70% opt-in, 30 notifs/user/day cell — 210M push/day, approximately 9,700/sec peak. This is the worst case within plausible parameters. SQS worker over-provisioning costs almost nothing; under-provisioning causes queue backup during the exact period — rapid user growth — when we can least afford it.

We size costs against the 55% opt-in, 15 notifs/user/day cell — 82.5M push/day — and flag the delta to the high scenario.

**Traffic model across scenarios:**

| Channel | Low (40%, 5/day) | Base (55%, 15/day) | High (70%, 30/day) |
|---------|-----------------|-------------------|-------------------|
| Push/day | 20M | 82.5M | 210M |
| Email — transactional | 500K | 500K | 500K |
| Email — digest | 3M | 3M | 3M |
| In-app/day | 10M | 30M | 60M |
| SMS — OTP/security | 150K | 150K | 150K |
| Peak throughput | ~1,100/sec | ~4,500/sec | ~9,700/sec |

**Scaling triggers — defined before launch, not after an incident:**

```
Week 1 target: instrument actual sends per user per day,
               segmented by type (DM, mention, like, digest)

Scaling Trigger A: sustained peak > 6,000/sec for 15 minutes
  → Add 30 workers across P1/P2 queues
  → Re-evaluate FIFO queue headroom (see Section 2.2)
  Owner: E4 | Time budget: 100h reserved (see Section 1.3)

Scaling Trigger B: sustained peak > 10,000/sec for 15 minutes
  → P1 queue migration from FIFO to standard + application-level ordering
  → Architecture review required; this is a structural change
  Owner: E1 | Requires full team review before activation

Scaling Trigger C: daily volume > 150M notifications for 3 consecutive days
  → SQS cost re-projection
  → Evaluate whether direct provider integration remains cost-optimal
```

### 1.2 Email Volume — Transactional and Digest Separated

Treating all email as a single figure obscures two categories with different drivers and different controls.

**Transactional email** is driven by user actions and security events, not by batching logic. It cannot be capped by a digest model:

| Event | Daily Volume |
|-------|-------------|
| New account verification (~0.5% of MAU/day) | ~50K |
| Password reset (~0.3% of MAU/day) | ~30K |
| Security alerts (new device login, ~1% of MAU/day) | ~100K |
| Billing / policy notices | ~50K |
| **Transactional total** | **~230K–500K/day** |

We model 500K/day and alert if it exceeds 750K/day — 50% above baseline signals either a security incident or an instrumentation error, and warrants investigation before it becomes a cost or trust problem.

**Digest email** is explicitly opt-in and explicitly batched. Users who opt in receive one email per configured cadence aggregating notifications they would otherwise have received individually:

- Daily digest: up to 3M users × 1 email/day = 3M emails/day maximum
- Weekly digest: users on weekly cadence contribute 1/7 of that figure daily

The digest model caps this category. It does not cap transactional.

**Total email volume:** ~3.5M/day at base scenario, of which 500K is transactional and 3M is digest. These are modeled from components, not asserted.

### 1.3 SMS Cost — Tiered Alarms with Automated Response

SMS is the only channel where a security incident can generate unbounded costs. OTP and security SMS is exempt from the engagement cap but tracked separately.

| Scenario | OTP Volume | Daily Cost (Twilio ~$0.0079/msg) |
|----------|-----------|----------------------------------|
| Baseline (2FA logins, ~5% of DAU) | ~150K/day | ~$1,185 |
| Credential stuffing (forced re-auth, 20% MAU) | ~2M/day | ~$15,800 |
| Major security incident (all MAU forced re-auth) | ~10M/day | ~$79,000 |

A single $5,000/day alarm creates a $4,999/day blind spot. A moderate credential stuffing attack generating ~630K forced re-auths sits entirely below that threshold with no automated response. The correct structure is tiered alarms with automated escalation at each tier.

**Alarm tiers with automated escalation:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $500/day OTP SMS | Log to dashboard; no page |
| Warning | $1,500/day OTP SMS | Page on-call; investigate source |
| Critical | $3,000/day OTP SMS | Page on-call + security team; rate limiting activates |
| Emergency | $5,000/day OTP SMS | Fallback to email OTP; security incident declared |

**Automated response at Critical tier — does not wait for human:**

```python
class OTPSMSRateLimiter:
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD:
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD:
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"

        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)
        if count > MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"
```

**On the email OTP fallback:** The current default is email OTP fallback rather than blocking authentication entirely, because blocking authentication at scale during a security incident creates a second incident. This default is documented here so Security can review it and override it if their threat model requires a different posture. If Security requires a different default, the code changes. The default is not "pending authorization" — it is email fallback, implemented as shown above, subject to Security's review before launch.

### 1.4 Team Allocation — With Time Accounting and Overload Resolution

Named owners without time allocation are not accountability.

**Available hours:**

```
6 months × 4 engineers × ~160 hours/month = ~3,840 engineer-hours
Subtract: on-call, meetings, code review, ramp-up (~20%)
Net available: ~3,072 engineer-hours
Individual budget per engineer: ~768 hours
```

**The E2 overload problem:** A naive allocation gives E2 push (350h) + email (200h) + SMS (100h) + half of cross-channel consistency (100h) = 750h, leaving only 18h for code review, coordination, and integration work. That is not workable. The fix is to redistribute SMS to E4, who has lower cross-team coordination surface.

**Revised allocation:**

| Category | Hours | Owner | Notes |
|----------|-------|-------|-------|
| Core pipeline + queue infrastructure | 400 | E1 | SQS setup, routing logic, worker framework |
| Push channel (APNs + FCM) | 350 | E2 | Token management, connection pools, feedback processing |
| Email channel (SendGrid) | 200 | E2 | Template system, digest scheduling, bounce processing |
| Cross-channel consistency | 200 | E1 + E2 | Shared ownership; see Section 5 |
| Preference management + user API | 300 | E3 | Opt-out, suppression, preference store |
| In-app notification store | 250 | E3 | PostgreSQL design, retention, inbox API |
| SMS channel (Twilio) | 120 | E4 | Rate limiting, OTP separation; moved from E2 |
| DLQ processing + failure handling | 180 | E4 | Four DLQ strategies; see Section 6 |
| Monitoring + alerting | 150 | E4 | CloudWatch, dashboards, runbooks |
| Scaling Trigger A contingency | 100 | E4 | Reserved, not pre-spent; releases if Trigger A fires |
| Infrastructure (IaC, deployments) | 120 | E4 | Terraform, ECS task definitions |
| Test harness | 200 | All | See Section 1.5 for scope constraints |
| Buffer (integration, bugs, scope creep) | 302 | All | ~10% of total |
| **Total** | **3,072** | | |

**E2 revised load:** 350 (push) + 200 (email) + 100 (cross-channel share) = 650h against 768h budget. Leaves 118h for coordination, integration, and code review. Still tight but workable.

**E4 revised load:** 120 (SMS) + 180 (DLQ) + 150 (monitoring) + 100 (Trigger A reserve) + 120 (infra) + ~50h (test harness share) = 720h against 768h budget. Manageable.

**Explicit out-of-scope for initial six months:**
- A/B testing framework for notification copy
- Send-time optimization
- Rich push notifications (images, deep action buttons)
- Analytics beyond delivery and open tracking

If product requires any of these, scope must be cut elsewhere. Engineering does not absorb additions silently.

### 1.5 Test Harness — Scope Tied to Designed Components

The test harness allocation is split into a committed tranche and a contingency tranche. Allocating fixed hours to test undesigned systems is not a scope commitment.

**Committed tranche (120h) — components fully designed in this document:**

| Failure Class | Component | Owner | Hours |
|---------------|-----------|-------|-------|
| Duplicate sends on standard queue retry | SQS + Redis idempotency | E4 | 25 |
| Missed suppressions during preference update | Preference store + routing | E3 + E4 | 30 |
| Token invalidation races (APNs/FCM) | Push channel | E2 + E4 | 25 |
| FIFO deduplication window expiry on P1 retry | Queue architecture | E4 | 20 |
| SMS rate limit bypass under Redis unavailability | SMS channel | E4 | 20 |

**Contingency tranche (80h) — held until dependent components are designed:**

| Failure Class | Blocked On | Releases When |
|---------------|-----------|---------------|
| Incorrect aggregation counts | Digest aggregation logic (Section 3.2) | Section 3.2 design complete |
| Timezone errors in digest scheduling | Digest scheduler design (Section 3.2) | Section 3.2 design complete |
| Broken unsubscribe links | Unsubscribe flow design (Section 4) | Section 4 design complete |

The 80h contingency is real allocation, not padding. It releases when the designs it covers exist. If those designs are simpler than expected, the hours return to buffer. If they are more complex, scope will be renegotiated at that point with actual information.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems make Redis the wrong choice for the primary queue tier.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. For P0 traffic (OTPs, security alerts), silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput and requires a replication topology we would need to operate ourselves.

**Problem 2 — Dequeue atomicity.** A Redis pipeline batches commands but does not provide atomicity. Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity we do not need when SQS solves the problem natively.

**Tradeoff explicitly accepted:** Four queue families means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept this because SQS's durability and correct concurrent dequeue semantics are non-negotiable for P0 traffic, and managed operations are less work than operating Redis with AOF replication ourselves.

**SQS cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately $1,800/month.

### 2.2 FIFO Queue Throughput — Modeled, Not Assumed

The SQS FIFO limit is 3,000 messages/second per queue. P0 is safe by nature — OTPs require a user action to trigger and are inherently low volume. P1 is the risk.

**Modeling P1 volume against traffic fraction:**

| Scenario | Total peak/sec | P1 fraction | P1/sec | FIFO headroom |
|----------|---------------|-------------|--------|---------------|
| Feed-first app |