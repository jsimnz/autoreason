# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 90–180M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system that trades occasional staleness for throughput.

Every tradeoff is named. Where a decision requires authorization from outside the engineering team — budget, product behavior, legal compliance — that decision point is identified and the engineering default is stated. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so the consequences of those decisions are visible.

**What changed from the prior draft, and why:** Ten specific problems were identified in review. Each is addressed directly below rather than folded silently into revised text. The changes are: (1) the document is now complete; (2) opt-in rate assumptions are defended and sensitivity-tested; (3) the P1 shard expansion correctness problem is acknowledged and a safe migration procedure is specified; (4) the Redis idempotency race condition is fixed with a version field; (5) FIFO deduplication window limitations are addressed with supplemental Redis coverage for P1; (6) email volume modeling is split into transactional and digest categories; (7) E2's allocation overload is resolved by redistributing SMS to E4; (8) the OTP fallback authorization framing is corrected to accurately reflect where the default sits; (9) Scaling Trigger B gets a time allocation and named owner; (10) the test harness hours are tied to designed components, with the remainder held as contingency until those designs exist.

---

## 1. Scale Model

### 1.1 The Notification Rate Problem

All volume estimates depend on two figures: notifications per opted-in user per day, and the push opt-in rate. Both are unknown before launch. The architecture is sensitive to both.

**Push opt-in rate — defended:**

The prior draft stated 60% opt-in rate for the conservative scenario and left dashes in the other columns, implicitly carrying 60% forward without acknowledgment. That was wrong. The figure requires justification.

Industry data for social apps: iOS opt-in rates post-iOS 14 permission prompt changes range from 40–55% for social apps that prompt at first launch; rates improve to 55–70% when apps delay the prompt until after demonstrated value. Android opt-in is higher, approximately 70–80%, because opt-out is the default. For a mixed-platform social app with a thoughtful prompt strategy, a blended 55% opt-in rate is a reasonable central estimate.

**Why this matters:** The difference between 40% and 60% opt-in on a 10M MAU base is 2M opted-in users — 30M push notifications/day at the base notification rate. That is not a rounding error; it changes worker sizing and provider costs materially.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|---------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Design choice:** We size push worker capacity for the 70% opt-in, 30 notifs/user/day cell — 210M push/day, approximately 9,700/sec peak. This is the worst case within plausible parameters. SQS worker over-provisioning costs almost nothing; under-provisioning causes queue backup during the exact period (rapid user growth) when we can least afford it.

We size costs against the 55% opt-in, 15 notifs/user/day cell — 82.5M push/day — and flag the delta to the high scenario.

**Traffic model:**

| Channel | Low (40% opt-in, 5/day) | Base (55% opt-in, 15/day) | High (70% opt-in, 30/day) |
|---------|------------------------|--------------------------|--------------------------|
| Push/day | 20M | 82.5M | 210M |
| Email — transactional | 500K | 500K | 500K |
| Email — digest | 3M | 3M | 3M |
| In-app/day | 10M | 30M | 60M |
| SMS — OTP/security | 150K | 150K | 150K |
| Peak throughput | ~1,100/sec | ~4,500/sec | ~9,700/sec |

Email is split into transactional and digest categories. This is addressed in Section 1.2.

### 1.2 Email Volume — Transactional and Digest Separated

The prior draft capped email at 4M/day across all scenarios with the note "digest model caps this," without defining the digest model or accounting for transactional email. That was wrong in two ways: the digest model was undefined, and transactional email volume scales with DAU and is not digest-bounded.

**Transactional email** includes: account verification, password reset, security alerts, billing receipts, and policy violation notices. This volume is driven by user actions and security events, not by the notification system's batching logic. Estimates:

| Event | Rate | Daily Volume |
|-------|------|-------------|
| New account verification | ~0.5% of MAU/day new signups | ~50K |
| Password reset | ~0.3% of MAU/day | ~30K |
| Security alerts (login from new device) | ~1% of MAU/day | ~100K |
| Billing / policy | Low, variable | ~50K |
| **Transactional total** | | **~230K–500K/day** |

Transactional email is not capped by digest logic. It scales with user base and security event rate. We model 500K/day and alert if it exceeds 750K/day (50% above baseline), which signals either a security incident or an instrumentation error.

**Digest email** is explicitly opt-in and explicitly batched. Users who opt into digest receive one email per configured cadence (daily or weekly), aggregating notifications they would otherwise have received individually. The digest model does cap this category:

- Daily digest: up to 3M users × 1 email/day = 3M emails/day
- Weekly digest: users on weekly cadence contribute 1/7 of that figure daily

The digest model is defined in Section 3.2 (email channel). The cap holds for this category only.

**Total email volume:** ~3.5M/day at base scenario, of which 500K is transactional and 3M is digest. The 4M/day figure in the prior draft was approximately right but for the wrong reasons. The corrected figure is modeled from components, not asserted.

### 1.3 SMS Cost — Tiered Alarms with Automated Response

SMS is the only channel where a security incident can generate unbounded costs. OTP and security SMS is exempt from the engagement cap but tracked separately.

| Scenario | OTP Volume | Daily Cost (Twilio ~$0.0079/msg) |
|----------|-----------|----------------------------------|
| Baseline (2FA logins, ~5% of DAU) | ~150K/day | ~$1,185 |
| Credential stuffing (forced re-auth, 20% MAU) | ~2M/day | ~$15,800 |
| Major security incident (all MAU forced re-auth) | ~10M/day | ~$79,000 |

**Alarm tiers with automated escalation:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $500/day OTP SMS | Log to dashboard; no page |
| Warning | $1,500/day OTP SMS | Page on-call; investigate source |
| Critical | $3,000/day OTP SMS | Page on-call + security team; rate limiting activates |
| Emergency | $5,000/day OTP SMS | Fallback to email OTP; security incident declared |

**Automated response at Critical tier:**

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

**On the email OTP fallback — correcting the authorization framing:**

The prior draft described the email OTP fallback as requiring authorization from Security before launch, while simultaneously writing the code with email fallback as the default and arguing the rationale for it. That framing was inconsistent. The decision has been made: the default is email OTP fallback rather than blocking authentication entirely, because blocking authentication at scale during a security incident creates a second incident. This default is documented here so Security can review it and override it if their threat model requires a different posture. If Security requires a different default, the code changes. But the current default is email fallback, not "pending authorization."

### 1.4 Team Allocation — With Time Accounting and Overload Resolution

**Prior draft problem:** E2 was allocated push (350h) + email (150h) + SMS (100h) + half of cross-channel consistency (100h) = 700h, against an individual budget of approximately 768h (3,072 ÷ 4). This left E2 with 68h for code review, on-call rotation, coordination overhead, and integration work — which is not enough. The fix is to redistribute SMS to E4, who has lower coordination surface.

**Available hours:**

```
6 months × 4 engineers × ~160 hours/month = ~3,840 engineer-hours
Subtract: on-call, meetings, code review, ramp-up (~20%)
Net available: ~3,072 engineer-hours
Individual budget per engineer: ~768 hours
```

**Revised allocation:**

| Category | Hours | Owner | Notes |
|----------|-------|-------|-------|
| Core pipeline + queue infrastructure | 400 | E1 | SQS setup, routing logic, worker framework |
| Push channel (APNs + FCM) | 350 | E2 | Token management, connection pools, feedback |
| Email channel (SendGrid) | 200 | E2 | Template system, digest scheduling, bounce processing |
| Cross-channel consistency | 200 | E1 + E2 | Shared ownership; see Section 5 |
| Preference management + user API | 300 | E3 | Opt-out, suppression, preference store |
| In-app notification store | 250 | E3 | PostgreSQL design, retention, inbox API |
| SMS channel (Twilio) | 120 | E4 | Rate limiting, OTP separation; moved from E2 |
| DLQ processing + failure handling | 180 | E4 | Four DLQ strategies; see Section 6 |
| Monitoring + alerting | 150 | E4 | CloudWatch, dashboards, runbooks |
| Scaling Trigger B contingency | 100 | E4 | See Section 2.1; reserved, not pre-spent |
| Infrastructure (IaC, deployments) | 120 | E4 | Terraform, ECS task definitions |
| Test harness | 200 | All | See Section 1.5 for scope constraints |
| Buffer (integration, bugs, scope creep) | 302 | All | ~10% of total |
| **Total** | **3,072** | | |

**E2 revised load:** 350 (push) + 200 (email) + 100 (cross-channel share) = 650h against 768h budget. Leaves 118h for coordination, integration, and code review. Still tight but workable.

**E4 revised load:** 120 (SMS) + 180 (DLQ) + 150 (monitoring) + 100 (Trigger B reserve) + 120 (infra) + share of test harness (~50h) = 720h against 768h budget. Manageable.

**Explicit out-of-scope for initial six months:**
- A/B testing framework for notification copy
- Send-time optimization
- Rich push notifications (images, deep action buttons)
- Analytics beyond delivery and open tracking

If product requires any of these, scope must be cut elsewhere. Engineering does not absorb additions silently.

### 1.5 Test Harness — Scope Tied to Designed Components

**Prior draft problem:** 200 hours were allocated to test six named failure classes, four of which depend on components (aggregation logic, digest scheduling, unsubscribe flow, token refresh) that were either in missing sections or undesigned. Allocating fixed hours to test undesigned systems is not a scope commitment.

**Revised approach:** The test harness allocation is split into a committed tranche and a contingency tranche.

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

The 80h contingency is real allocation, not padding. It releases when the designs it covers exist. If those designs are simpler than expected, the hours return to buffer. If they are more complex, the hours may be insufficient and scope will be renegotiated at that point with actual information.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems make Redis the wrong choice for this tier.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. For P0 traffic (OTPs, security alerts), silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput and requires a replication topology we would need to operate ourselves.

**Problem 2 — Dequeue atomicity.** A Redis pipeline batches commands but does not provide atomicity. Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity we do not need when SQS solves the problem natively.

**Tradeoff explicitly accepted:** Four queue families means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept this because SQS's durability and correct concurrent dequeue semantics are non-negotiable for P0 traffic, and managed operations are less work than operating Redis with AOF replication ourselves.

**SQS cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately $1,800/month.

### 2.2 FIFO Queue Throughput and Shard Expansion — Correctness Problem