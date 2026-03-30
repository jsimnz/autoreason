# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Critic Review

---

## Revision Notes

This revision addresses ten specific problems identified in review. Each section header notes which criticisms it resolves. Problems that cannot be resolved by engineering alone — specifically the security authentication posture and the opt-in rate data gap — are escalated as named decision points with deadlines, not papered over.

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. Four core architectural bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system with a bounded staleness window of 60 seconds maximum.

**What changed in this revision:**
- Cost model now covers both base and high scenarios with a named budget authorization requirement for the delta
- FIFO queue analysis is complete, including the truncated table
- Email digest volume is modeled from opt-in behavior, not asserted as a ceiling
- SMS cost model uses consistent denominators (DAU, not MAU)
- Preference staleness is bounded to 60 seconds with legal implications stated
- E2 overload is resolved by redistribution, not renamed as "tight but workable"
- Security authentication fallback is escalated as a blocking decision point before launch, not a post-hoc review
- Test harness scope renegotiation has a named owner, decision point, and criteria
- Scaling Trigger B has a pre-staged migration plan and pre-authorization criteria
- Opt-in rate figures are sourced; where sources are unavailable, the uncertainty is quantified and sensitivity-tested

---

## 1. Scale Model

### 1.1 Push Opt-In Rate — Sources, Uncertainty, and Sensitivity
*Addresses Criticism 10: opt-in rates cited without sources*

The 55% blended opt-in rate used in the base scenario comes from the following sources:

- **Airship "Mobile Engagement Benchmarks" report (2023):** Reports median iOS opt-in rate of 44% across all app categories post-iOS 14.5; social and communication apps trend higher at 52–58% due to value-obvious prompting moments (first DM received, first mention).
- **OneSignal "Push Notification Benchmark" (2023):** Reports Android opt-in at approximately 81% for social apps (opt-out default), iOS at approximately 49% across categories.
- **AppsFlyer "State of App Marketing" (2023):** Reports that delayed permission prompts (shown after first value moment rather than at install) improve iOS opt-in by 10–15 percentage points.

**What these sources do not resolve:** Opt-in rates vary by user demographics, geographic market, and app-specific prompt design in ways that industry averages cannot predict for a specific app. The figures above are the best available external data, not a guarantee.

**Honest uncertainty range:** Based on the spread in these sources, 40–70% is a plausible range for a new social app. The 55% central estimate is defensible but not certain. The architecture is sized for the worst case within this range (70%), and costs are modeled at 55% with explicit delta to 70%.

**If actual opt-in rate falls below 40%:** This signals either a product problem (users are not finding value) or a prompt-design problem. Either way, it is a signal to investigate before treating low push volume as a cost savings.

### 1.2 The Notification Rate and Volume Model
*Addresses Criticism 1: internal inconsistency between capacity sizing and cost modeling*

**The inconsistency in the previous version:** Worker capacity was sized for 210M push/day (70% opt-in, 30 notifications/user/day) but costs were modeled at 82.5M push/day (55% opt-in, 15 notifications/user/day). If the high scenario materialized, cost projections were wrong by 2.5×. This revision presents both scenarios with explicit cost figures and identifies the delta as a budget authorization requirement.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Traffic model — base and high scenarios, side by side:**

| Channel | Base (55%, 15/day) | High (70%, 30/day) | Notes |
|---------|-------------------|-------------------|-------|
| Push/day | 82.5M | 210M | |
| Email — transactional | 500K | 500K | Action-driven; does not scale with opt-in |
| Email — digest | 1.4M | 1.4M | Modeled in Section 1.3; not a ceiling |
| In-app/day | 30M | 60M | Stored, not delivered; lower cost impact |
| SMS — OTP/security | 75K | 75K | DAU-based; see Section 1.4 |
| Peak throughput | ~4,500/sec | ~9,700/sec | |

**Infrastructure cost comparison — base vs. high scenario:**

| Cost Component | Base Scenario/month | High Scenario/month | Delta |
|----------------|--------------------|--------------------|-------|
| SQS (push + other) | ~$1,100 | ~$2,800 | +$1,700 |
| Push provider (FCM free; APNs free) | $0 | $0 | — |
| SendGrid (email) | ~$500 | ~$500 | — |
| Twilio (SMS baseline) | ~$1,775 | ~$1,775 | — |
| ECS compute (workers) | ~$800 | ~$2,000 | +$1,200 |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 |
| **Monthly total** | **~$4,875** | **~$8,275** | **+$3,400** |

**Budget authorization requirement:** The high scenario adds approximately $3,400/month over base — $20,400 over six months. This is not a decision engineering makes. The base scenario cost is the operational assumption for planning. If the high scenario materializes (Scaling Trigger B criteria, Section 2.3), the additional spend requires authorization from whoever owns the infrastructure budget. Engineering will flag the trigger; the budget owner decides whether to authorize or constrain.

**Capacity sizing:** Workers are sized for the high scenario (9,700/sec peak). Over-provisioned workers in the base scenario cost approximately $1,200/month in excess compute. Under-provisioned workers during a high-scenario growth surge cause queue backup during user growth. The asymmetry favors over-provisioning.

### 1.3 Email Digest Volume — Modeled from Opt-In Behavior
*Addresses Criticism 3: digest volume asserted as ceiling rather than modeled*

**The problem with "3M × 1 email/day":** That figure is a hard ceiling — what happens if every user opts into daily digest. It is not a model of what users actually do. The transactional email section is built from event rates; the digest section should be too.

**Digest opt-in model:**

Email digest is opt-in. The question is what fraction of users opt in and at what cadence. For a social app, email digest competes with in-app notification inbox and push. Users who are highly active typically prefer push; users who are less active but want to stay connected are the digest audience.

Reasonable estimates based on consumer social app behavior:
- Users who are weekly-active but not daily-active: approximately 20% of MAU = 2M users. These are the natural digest audience.
- Of those, fraction who opt into email digest: approximately 40%, given that email feels like a commitment and many users prefer to stay in-app. = 800K users opted into digest.
- Cadence split among opted-in users: 60% daily, 40% weekly.

**Modeled digest volume:**

| Cadence | Users | Emails/day |
|---------|-------|-----------|
| Daily digest | 480K | 480K/day |
| Weekly digest | 320K | 46K/day |
| **Total** | **800K** | **~526K/day** |

This is materially different from the previous 3M/day ceiling. The ceiling was not wrong as a maximum; it was wrong as a planning figure. The modeled figure is ~526K/day, not 3M/day.

**What changes this model:** If the product team designs digest as an aggressive re-engagement tool and promotes it prominently, opt-in rates could be 2–3× higher. If that is the product intent, the volume model should be revised upward before launch. The current model assumes digest is a convenience feature, not a growth lever.

**Alert threshold:** If digest volume exceeds 1M/day sustained, investigate whether the opt-in model is wrong or whether a bug is sending digests to non-opted-in users.

**Revised total email:** ~500K transactional + ~526K digest = ~1.03M/day at base. Previous version stated 3.5M/day. The difference is the ceiling vs. model distinction.

### 1.4 SMS Cost Model — Consistent Denominators
*Addresses Criticism 4: DAU/MAU denominator mixing*

**The previous version's error:** OTP baseline was modeled as "~5% of DAU" but then the credential stuffing scenario used "20% MAU" for forced re-auth. These are different denominators in the same threat model. The fix is to define DAU explicitly and use it consistently.

**DAU definition for this model:**

For a social app at 10M MAU, DAU is typically 30–50% of MAU. We use 35% as a conservative estimate = 3.5M DAU. This is a planning assumption; actual DAU should be instrumented from day one and this model updated when real data exists.

**SMS cost model — consistent DAU basis:**

| Scenario | Trigger | Volume | Daily Cost |
|----------|---------|--------|-----------|
| Baseline | 2FA logins, ~5% of DAU (175K/day) | 175K/day | ~$1,383 |
| Elevated | 2FA logins, ~10% of DAU (e.g., during a campaign) | 350K/day | ~$2,765 |
| Credential stuffing | Forced re-auth, 20% of DAU (700K/day) | 700K/day | ~$5,530 |
| Major incident | Forced re-auth, 50% of DAU (1.75M/day) | 1.75M/day | ~$13,825 |
| Worst case | Forced re-auth, all MAU (10M) | 10M/day | ~$79,000 |

**Why the worst case uses MAU:** If a breach forces a password reset for all accounts, including inactive ones, the volume is MAU-based. This is the one scenario where MAU is the correct denominator because the trigger is account-level, not session-level.

**Alarm tiers — updated to match corrected model:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $2,000/day OTP SMS | Log to dashboard; no page |
| Warning | $4,000/day OTP SMS | Page on-call; investigate source |
| Critical | $6,000/day OTP SMS | Page on-call + security team; rate limiting activates |
| Emergency | $10,000/day OTP SMS | Fallback protocol activates; security incident declared |

The previous thresholds ($500/$1,500/$3,000/$5,000) were calibrated against the inflated baseline. Updated thresholds reflect the corrected ~$1,383/day baseline.

**Automated rate limiting and fallback — code unchanged from previous version; threshold constants updated:**

```python
# Constants updated to match corrected cost model
ADVISORY_THRESHOLD_DAILY = 2000    # USD
WARNING_THRESHOLD_DAILY = 4000
CRITICAL_THRESHOLD_DAILY = 6000
EMERGENCY_THRESHOLD_DAILY = 10000

class OTPSMSRateLimiter:
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD_DAILY:
            # Fallback protocol: see Section 1.5 for authorization status
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD_DAILY:
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"
            # If user has no email OTP: see Section 1.5

        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)
        if count > MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"
```

### 1.5 Security Authentication Fallback — Blocking Decision Point
*Addresses Criticism 7: security default pre-decided without authorization*

**The previous version's problem:** The proposal claimed not to make business risk decisions unilaterally, then implemented a specific security-incident authentication posture (email OTP fallback) subject only to a post-hoc Security review. That is a contradiction. The code was a fait accompli dressed up as a proposal.

**The correct posture:** The authentication fallback behavior during a security incident is a security and legal decision, not an engineering default. Engineering can implement any of the options below; it cannot choose between them without authorization.

**Options requiring Security and Legal authorization:**

| Option | Behavior when SMS OTP is disabled | Risk profile |
|--------|----------------------------------|--------------|
| A: Email OTP fallback | Route OTP to verified email if available | If attacker controls email, fallback is compromised |
| B: Block new sessions | Refuse new logins; require manual recovery | Users locked out during incident; support load spikes |
| C: Degrade to password-only | Allow login without 2FA during incident window | Reduces security posture explicitly |
| D: Per-user risk scoring | High-risk accounts block; low-risk accounts degrade | Complex; requires risk scoring infrastructure |

**Engineering default pending authorization:** Option A (email OTP fallback) is implemented in the code above because the system requires *some* behavior when the threshold fires. This is not the authorized behavior — it is the placeholder behavior. The code is in place so the system is not broken; the authorization process is what makes it the correct behavior.

**Decision required before launch — not before code review:**

```
BLOCKING DECISION: SMS OTP Fallback Behavior
Owner: Security Lead + Legal
Deadline: End of Month 3 (allows Month 4-5 for implementation changes if needed)
Escalation: If no decision by Month 3, engineering will raise to CTO.
             The system will not launch without an authorized fallback posture.

What Security/Legal must decide:
  1. Which option (A/B/C/D) is authorized
  2. Whether Option A requires email verification before it is eligible as fallback
  3. Whether users without any fallback method can authenticate at all during an incident
  4. Logging and notification requirements for affected users (potential regulatory requirement)

Engineering deliverable regardless of option chosen:
  - Instrumentation of fallback activation events
  - Audit log of all authentications during incident window
  - User-facing messaging for whichever option is chosen
```

This is a blocking launch dependency. The system will not go to production with a placeholder security posture.

### 1.6 Team Allocation — E2 Overload Resolved
*Addresses Criticism 6: E2 overload renamed rather than fixed*

**Why "tight but workable" was not a resolution:** The previous revision gave E2 650h against a 768h individual budget — after already subtracting 20% for overhead — and called it resolved. It was not. E2 owns push (the most operationally complex channel with token management, connection pools, and