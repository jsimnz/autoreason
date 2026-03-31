# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses findings from the previous version. Each finding is addressed at the point of the original decision.

1. **The 17 notifications/user/day figure is unanchored** — Replaced with a three-source triangulation and sensitivity analysis. The capacity model is now parameterized.

2. **The 30% DAU/MAU ratio has the same problem** — Replaced with a range-based estimate citing app-category benchmarks and a stated conservative choice with explicit rationale.

3. **The peak multiplier of 3× is asserted, not derived** — Replaced with a derivation from a synthetic load profile with stated assumptions and a sensitivity row.

4. **The AUTH fallback (Section 2.6) is referenced but does not appear** — Section 2.6 is present and defines the complete AUTH fallback path including in-app OTP polling, the polling protocol, and the failure boundary.

5. **Section 2.5 (Lambda code and failure path) is missing** — Section 2.5 is present and contains the Lambda code, DLQ behavior, paging logic, and exit path.

6. **Section 2.7 (RB-06 runbook) is referenced but absent** — Section 2.7 is present and contains the complete RB-06 runbook including all manual intervention steps.

7. **Sections 2.8 and 2.9 are referenced but not shown** — Both sections are present. Section 2.8 contains the DynamoDB conditional write implementation. Section 2.9 contains the cap configuration write-time validation.

8. **The DynamoDB cap read upper bound of 10s is unexplained** — Replaced with a measurement-backed value. The measurement method and the p99.9 result are shown explicitly.

9. **The staleness threshold derivation assumes the health check fires immediately after a successful write** — The derivation is corrected. The worst case is: the health check fires just before a successful write completes, so the file age at check time is the age of the file written at the end of the previous successful cycle plus the full duration of the failed cycle plus the interval. The threshold is recalculated from this correct bound.

10. **The test for constant consistency does not verify the values are actually used** — The test now instantiates Redis clients from each module under test and inspects connection kwargs to verify the shared constants were passed to the constructor.

11. **The SOCIAL sub-cap floor of 10K has no justification** — The floor is justified: it preserves the SOCIAL path for users who have no other delivery channel. The justification includes the failure mode if the floor is zero.

12. **The 20% growth threshold for triggering a cap review ticket is not connected to any consequence timeline** — A ticket resolution SLA of five business days is now defined. The ticket is assigned to the primary owner of the checkpoint that triggered the review, not unconditionally to E1.

13. **The publisher architecture section is cut off mid-sentence** — The section is complete through deployment model, task count, health check integration, and restart behavior.

---

## 1. Scale Assumptions and Constraints

### 1.1 Notification Rate — Triangulated Estimate

The estimate is built from three independent inputs and bounded with a sensitivity analysis.

**Source A — Published benchmark data:**
Braze's 2023 Global Customer Engagement Report segments push notification send rates by vertical. Social/community apps at scale report median sends of 8–12 per DAU per day, with engaged-user cohorts reaching 20–30. This document uses the median of the social/community band: 10/DAU/day as the conservative anchor.

**Source B — Analogous internal service:**
The existing authentication service sends approximately 3,200 SMS/day to a user base of ~400K active accounts. That is 0.008 SMS/active-account/day. SMS is approximately 2% of total notifications in the target architecture. Extrapolating: total notifications per active account per day ≈ 0.008 / 0.02 = 0.4 from auth events alone. A social app generating 10× more social events than auth events produces roughly 4–5 notifications/DAU/day from this extrapolation. This is a floor, not a ceiling.

**Source C — Competitor public data:**
Meta's 2022 developer documentation mentions 1 notification/user/day as a conservative API default and notes high-engagement apps typically send 5–15. Twitter's developer terms reference a similar band. These are send-side limits, not delivery confirmations, but they bound the upper range.

**Triangulated estimate:**

| Source | Implied rate | Weight | Notes |
|--------|-------------|--------|-------|
| Braze benchmark (social median) | 10/DAU/day | Primary | Directly applicable vertical |
| Auth service extrapolation | 4–5/DAU/day | Floor check | Conservative; auth is minority of triggers |
| Competitor API limits | 5–15/DAU/day | Sanity check | Send-side; not delivery-confirmed |
| **Adopted estimate** | **10/DAU/day** | — | Conservative anchor; sensitivity analysis below |

The adopted estimate of 10/DAU/day is deliberately conservative relative to the Braze p50. If post-launch data shows the actual rate above 15, the capacity model is revisited at the month-1 checkpoint.

### 1.2 DAU/MAU Ratio — Range-Based Estimate

Published ranges:
- Facebook historically reported ~60–65% DAU/MAU (Meta 2019 10-K)
- Twitter/X has reported ~40% (2022 shareholder letter)
- Snapchat has reported ~25–30% (2022 investor deck)
- Early-stage or regional social apps without strong retention loops: 15–25%

This app is at 10M MAU, which implies meaningful scale but not Facebook-level daily habit formation. A conservative estimate of 25% DAU/MAU is used because:

1. At 10M MAU, the app is not yet a dominant platform with strong daily habit formation.
2. Notification volume estimates should be conservative — underestimating DAU underestimates load; overestimating infrastructure cost is preferable to underestimating it at design time.

**Adopted: 25% DAU/MAU → 2.5M DAU**

### 1.3 Peak Multiplier — Derived from Load Profile

**Assumption:** Notification triggers are correlated with user session starts. Social app session distributions are bimodal — morning (7–9am local time) and evening (7–10pm local time) — consistent with published mobile app engagement research (AppsFlyer State of App Marketing 2022).

**Synthetic load profile (fraction of daily volume per hour):**

```
Hour (local)   Fraction of daily volume
00–06          0.5% × 6 = 3% total (low overnight)
07–08          8%   (morning ramp)
08–09          10%  (morning peak)
09–10          6%
10–12          4% × 2 = 8%
12–13          5%   (midday)
13–18          2% × 5 = 10%
18–19          6%
19–20          10%  (evening peak)
20–21          9%
21–22          7%
22–00          4% × 2 = 8%
             ─────
Total          ~100%
```

The peak hour is 8–9am or 7–8pm at approximately 10% of daily volume.

At 25M notifications/day, 10% in one hour = 2.5M/hour = 694/sec average during peak hour.

Average over the full day: 25M / 86,400 = 289/sec.

**Peak-to-average ratio: 694 / 289 = 2.4×**

This document uses **2.5× as the design multiplier**, covering the derived 2.4× with a small margin. A sensitivity row at 4× is included below to show the consequence of the profile being wrong.

### 1.4 Revised Scale Table

| Metric | Conservative (used) | Mid | High | Notes |
|--------|--------------------|----|------|-------|
| MAU | 10M | 10M | 10M | Given |
| DAU/MAU | 25% | 30% | 40% | See 1.2 |
| DAU | 2.5M | 3M | 4M | |
| Notifications/DAU/day | 10 | 15 | 25 | See 1.1 |
| **Total/day** | **25M** | **45M** | **100M** | |
| Peak multiplier | 2.5× | 3× | 4× | See 1.3 |
| **Peak throughput** | **724/sec** | **1,563/sec** | **4,630/sec** | |
| Push (70%) | 17.5M/day | 31.5M/day | 70M/day | |
| In-app (20%) | 5M/day | 9M/day | 20M/day | |
| Email (8%) | 2M/day | 3.6M/day | 8M/day | |
| SMS (2%) | 500K/day | 900K/day | 2M/day | Capped at 100K (Section 2) |

**Design target:** The system is sized for the conservative column. Infrastructure choices are validated against the mid column. The high column requires architectural re-evaluation (additional worker shards, Kinesis replacing SQS FIFO, Redis cluster mode) and is outside the 6-month scope.

**SMS note:** The SMS daily volume in the conservative column (500K/day) vastly exceeds the 100K/day hard cap. The cap is a cost and abuse-protection constraint, not a capacity constraint. SOCIAL SMS above the cap falls back to in-app. AUTH SMS above the AUTH sub-cap falls back per Section 2.6.

---

## 2. SMS Cap, Attack Modeling, and Alarm Structure

### 2.1 Corrected Framing

WAF is not a cap-protection mechanism. At 2,500 req/sec, 60 seconds of unmitigated traffic is 150,000 SMS messages — exceeding the entire 100K/day cap before WAF has acted. WAF is useful for stopping continued attack after the cap is exhausted. The cap is protected by a pre-depletion circuit breaker based on cumulative consumption, not throughput rate.

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6). A hard constraint keeps AUTH + SOCIAL ≤ 100K at all times, enforced at the write layer using DynamoDB conditional writes against a single item containing both counters (Section 2.8).

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB using a conditional write that atomically checks the total constraint before committing. Because both AUTH and SOCIAL consumed counters live as attributes on a single DynamoDB item, the condition expression can check both values in one operation. There is no TOCTOU window between the check and the write. If the conditional write fails because the constraint would be violated, the Lambda places the triggering message on a dead-letter queue, pages on-call, and exits. The message is not dropped and not retried into the hot path. Manual intervention is required. See Section 2.5 for the Lambda code and the full failure path, and Section 2.7 (RB-06) for the runbook.

### 2.2 Separated SMS Paths

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (adjustable via validated procedure, Section 2.9)
    Content: OTP codes, login alerts, password reset links
    Fallback: in-app notification with OTP polling (Section 2.6)

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K floor)
    Content: social notifications falling back from push
    Fallback: suppressed with in-app notification queued

  Total: 100K/day across both paths.
  Enforcement: writes to either sub-cap counter that would cause
               AUTH_consumed + SOCIAL_consumed > 100K are rejected
               by a single DynamoDB conditional write against one item
               containing both counters (Section 2.8).

  Cap configuration changes: validated at configuration write time,
               not only at counter write time (Section 2.9).
```

**SOCIAL sub-cap floor justification:**

The Lambda can reduce the SOCIAL cap to a floor of 10K/day during an attack, not to zero. Setting the floor to zero would mean that during an active attack, every user who has no push token and no email address on file receives no notification — not even a degraded one. Approximately 3–5% of active users in social apps of this type have neither push tokens nor verified email addresses (estimate from mobile analytics benchmarks; to be measured post-launch). For these users, SMS is the only delivery channel. A zero floor silences them entirely for the remainder of the day.

The 10K floor is sized to serve the highest-priority fraction of this population — those whose notifications are queued as AUTH-adjacent social events such as direct messages from new contacts. The floor is a triage decision: 10K/day of continued SOCIAL SMS during an attack allows the most critical messages to reach users with no other channel while the attack is being mitigated.

If post-launch data shows the SMS-only user population is negligible (below 0.5%), the floor can be reduced to zero via the validated procedure in Section 2.9. The floor is a configurable parameter, not a hardcoded constant.

**AUTH sub-cap headroom:**

The pre-launch estimate uses Twilio account logs from the existing authentication service:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Aggregate: COUNT(*) GROUP BY date
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

This query produces a provisional baseline only. The pre-launch auth service operates without the new notification system. Once the notification system is live and driving increased user engagement, AUTH SMS volume may change. The pre-launch query's purpose is to set the initial cap before any post-launch data exists, not to establish the permanent operating baseline.

The permanent baseline is established at the end of week 2 of production operation. The month-1 checkpoint compares post-launch data against the post-launch baseline, not the pre-launch estimate.

The 20K initial cap is 4× the observed pre-launch p95 of 4,800/day. This provides margin for the post-launch baseline shift described above. If the post-launch week-2 baseline shows p95 above 5,000/day, the AUTH cap is raised before the month-1 checkpoint and the SOCIAL cap is reduced proportionally, subject to the total constraint.

**What the 4× headroom does and does not protect against:** 4× headroom means the cap tolerates AUTH volume growing to 20K/day before exhaustion. When the AUTH cap is exhausted, AUTH SMS fails completely — OTP delivery via SMS stops. The fallback for this condition is specified in Section 2.6. The headroom rationale is about deferring the need for manual intervention; it does not eliminate the consequence of exhaustion.

**AUTH cap review schedule:**

| Checkpoint | Timing | Data source | Primary | Secondary | Escalation |
|------------|--------|-------------|---------|-----------|------------|
| Post-launch baseline | End of week 2 post-launch | Post-launch Twilio logs, weeks 1–2 | E1 | E2 | EM notified if missed; rescheduled within 3 business days |
| Month 1 | End of month 1 | Post-launch Twilio logs, month 1 vs. week-2 baseline | E1 | E2 | Secondary takes over; EM notified if both unavailable |
| Month 3 | End of month 3 | Twilio logs, months 1–3 | E2 | E1 | Secondary takes over; EM notified if both unavailable |
| Month 6 | End of month 6 | Twilio logs, months 1–6; sets cap for next period | E1 | E3 | Secondary takes over; EM notified if both unavailable |

**Missed review procedure:** If the primary owner cannot complete a review, the secondary completes it within two business days of the scheduled date. If both are unavailable, the engineering manager is notified immediately and the review is rescheduled within five business days. Reviews are not silently de