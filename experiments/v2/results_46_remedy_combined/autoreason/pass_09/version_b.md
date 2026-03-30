# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system whose cache TTL is a **performance optimization, not a compliance mechanism**.

**This revision addresses twelve new criticisms directly.** Each criticism is either accepted and corrected, or disputed with explicit reasoning. Where a prior claim was asserted without design, the design is now specified. Where referenced sections were absent, they are now present. Where governance was undefined, owners, consequences, and decision criteria are now named.

**Summary of changes in this revision:**

1. **Suppression flag was asserted, not designed** — Corrected. Section 2 now specifies the full opt-out flow: receiving system, database write path, failure behavior, worker check sequence, and third-party provider propagation with explicit timing bounds.

2. **15-minute diagnostic had no specified mechanism** — Corrected. Section 1.3 now describes the exact queries, data sources, decision logic, and build ownership for the automated diagnostic.

3. **Baseline stability criterion was circularly defined** — Corrected. The rolling average is computed excluding days that triggered Warning or higher alarms. The stability criterion operates on a filtered series, not the raw series.

4. **WAND provisioning dependency was not escaped by the insurance framing** — Accepted. The scenario range is explicitly acknowledged as assumption-derived. The insurance argument is reframed: we are insuring against the cost of under-provisioning given uncertainty in a range we cannot reduce pre-launch, not asserting the range is correct.

5. **Path A compliance review had no owner, no teeth, no defined outcome** — Corrected. Section 1.3 now names the review owner, specifies the required findings, defines consequences for non-completion, and specifies the remediation action if the review finds a problem.

6. **Section 8 on engineer scope was referenced but absent** — Corrected. Section 8 is now present and complete.

7. **OTP email fallback correction was claimed but Section 3.4 was absent** — Corrected. Section 3.4 is now present with the full cost model.

8. **Peak factor sensitivity analysis was claimed but Section 2.5 was absent** — Corrected. Section 2.5 is now present with the full table and arithmetic.

9. **SQS cost arithmetic was claimed but Section 5.2 was absent** — Corrected. Section 5.2 is now present with full derivation.

10. **Credential breach cost figure had no financial or operational governance** — Corrected. Authorization chain, per-incident budget ceiling, and operational execution plan are specified in Section 1.4.

11. **55% blended opt-in rate mixed incompatible source methodologies** — Accepted. The blended figure is replaced with a methodology-separated presentation. The 40–70% range is retained but its basis is now honest.

12. **Digest halt resumption path terminated in an engineering lead** — Corrected. The escalation path now terminates in a compliance officer or designated compliance deputy. Engineering leads cannot unblock a compliance halt unilaterally.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be measured until at least Day 7 of production traffic; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model. The scenario range (1M–3M) is an assumption, not a forecast. See Section 1.3 for how this uncertainty is handled.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate |
| In-app | DAU (measured) | Delivered to active sessions; stored, not pushed |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |
| Credential breach notification | **MAU (10M)** | Proactive administrative action; not bounded by session state — see Section 1.4 |

The final row is the only place in this document where MAU is used for an SMS model. A credential breach notification is a proactive administrative action, not triggered by session events. All other SMS rows remain DAU-bounded.

### 1.2 Push Volume Model

**On the 55% blended opt-in rate:** The three sources cited in the prior version use incompatible measurement methodologies and cannot be legitimately blended into a single figure.

- **Airship (2023)** measures the fraction of an app's existing user base that has push enabled at a point in time. This is an installed-base metric.
- **OneSignal (2023)** measures the fraction of users who grant permission when shown a push permission prompt. This is a prompt-conversion metric.
- **AppsFlyer (2023)** measures the effect of prompt timing on prompt-conversion rate. This is a prompt-design variable, not an opt-in rate.

These measure different things. Averaging them produces a number with no coherent interpretation. The prior "55% blended" figure is withdrawn.

**Replacement approach:** We use a single methodology-consistent source (OneSignal prompt-conversion benchmarks for social apps: iOS ~49%, Android ~81%) combined with a platform mix assumption (60/40 iOS/Android for a new social app). This yields:

- Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = 29.4% + 32.4% = **61.8%**
- We round to **60%** and model the range as **45–75%** to reflect genuine uncertainty in platform mix and prompt design.

The honest acknowledgment: this figure will be wrong. We will measure actual opt-in rates in the first week of production and recalibrate. The architecture is sized for 75%; costs are modeled at 60%.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M push/day | 67.5M push/day | 135M push/day |
| 60% (6M users) | 30M push/day | 90M push/day | 180M push/day |
| 75% (7.5M users) | 37.5M push/day | 112.5M push/day | 225M push/day |

**Traffic model — base and high scenarios:**

| Channel | Base (60%, 15/day) | High (75%, 30/day) | Notes |
|---------|-------------------|--------------------|-------|
| Push/day | 90M | 225M | |
| Email — transactional | ~500K | ~500K | Action-driven |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | Read/write load on store |
| SMS — OTP/security | ~175K | ~350K | |
| Peak throughput | ~4,500/sec | ~9,700/sec | See Section 2.5 |

### 1.3 Email Volume — Transactional and Digest Modeled Separately

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs. It cannot be capped by batching logic and must not share IP pools with digest mail. Mixing pools is a deliverability decision with direct revenue impact: a spam complaint spike from digest mail can blacklist the IP pool used for password resets.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained for more than 30 minutes.

**Digest email** is explicitly opt-in and explicitly batched.

**The WAND measurement problem stated plainly:** The scenario range of 1M–3M WAND users is an assumption. We cannot reduce this uncertainty before launch. The insurance framing is correct but must be stated honestly: we are choosing infrastructure to cover the worst-case scenario in a range we have assumed, not measured. The $160/month delta between SendGrid Essentials and Pro is cheap enough that we accept it rather than accept the product risk of under-provisioning. This is a cost-of-uncertainty argument, not a forecast.

**Corrected measurement approach:**

*Days 1–7 (operational signal only):* Instrument session frequency from Day 1. Single-session-per-day users are a rough proxy for WAND engagement level. **Used only as an operational indicator. Not used as a forecast input. Does not influence provisioning decisions.**

*Day 7 onward (first WAND estimate):* Compute users with at least one session in the trailing 7 days and zero sessions yesterday. Valid but noisy.

*Week 4 (stable estimate):* Rolling 7-day cohort averaged over 4 weeks. First number trustworthy enough to update the digest volume model and revise SendGrid tier if warranted.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — two-path diagnostic (now fully specified):**

Volume above 1.3M/day triggers an automated diagnostic. This is not a human-initiated review; it runs automatically within 2 minutes of the threshold breach.

**What the diagnostic does:**

The diagnostic joins two data sources:
1. **Send log:** Count of digest emails dispatched in the trailing 24 hours, grouped by user ID.
2. **Consent ledger:** The canonical opt-in record for every user, with opt-in timestamp and source (e.g., onboarding flow, settings page, re-engagement campaign).

The diagnostic query: `SELECT COUNT(*) FROM send_log sl JOIN consent_ledger cl ON sl.user_id = cl.user_id WHERE sl.send_type = 'digest' AND sl.sent_at > NOW() - INTERVAL 24 HOURS AND cl.digest_optin = TRUE AND cl.optin_at < sl.sent_at`

If this count equals or exceeds the send log count (within a 0.1% tolerance for timing race conditions), **Path A** applies: every send is attributable to a verified opt-in. If the count is below the send log count by more than 0.1%, **Path B** applies: some sends cannot be attributed to a verified opt-in.

**Who built this:** This diagnostic is owned by Engineer B (data/compliance infrastructure lead — see Section 8). It must be built and tested in staging before launch. It is a launch gate, not a post-launch addition.

**Path A — Verified opt-in growth:**
Sending continues. An automated report is generated containing: total send count, opt-in attribution rate, opt-in source breakdown, and timestamp. This report is written to the compliance audit log and a Jira ticket is auto-created and assigned to the **Compliance Owner** (named pre-launch; not an engineering role) with:
- **Required finding:** Confirm that the opt-in mechanism producing this volume is functioning as designed and that consent records are complete and legally sufficient.
- **Deadline:** 5 business days from ticket creation.
- **Consequence of non-completion:** Digest sends above the 1.3M/day threshold are automatically paused on Day 6 until the ticket is resolved. This pause is enforced by the send pipeline checking ticket status, not by a human remembering to act.
- **Consequence if review finds a problem:** Digest sending halts immediately, same as Path B. Affected users are identified from the consent ledger gap and suppressed before resumption.

**Path B — Unattributed volume:**
Digest sending halts immediately, automated. Resumption requires compliance owner sign-off per Section 7, Decision Point 4. Escalation path is specified in Section 7 and does not terminate in an engineering role.

### 1.4 SMS Cost Model — DAU-Calibrated, Load-Test-Anchored Baselines

**Corrected baseline stability criterion:**

The prior criterion — "no single day exceeds 1.8× the rolling average" — is circularly defined. A spike raises the rolling average, which raises the threshold, which makes the spike less likely to disqualify the average. The criterion partially absorbed instability into the series it was supposed to protect.

**Corrected approach:** The 14-day rolling average is computed from a **filtered series** that excludes any day on which a Warning-tier alarm (2.5× threshold) or higher was triggered. Specifically:

1. Each day is tagged at end-of-day as Clean or Flagged based on whether any Warning+ alarm fired.
2. The rolling average uses only Clean days.
3. The stability criterion — 7 consecutive days with no day exceeding 1.8× the rolling average — is evaluated against the Clean-day series only.
4. If fewer than 7 Clean days exist in a 14-day window, the stability criterion cannot be met and the load test baseline remains authoritative.

This prevents a spike from contaminating its own baseline. It also means that a genuinely volatile launch period simply delays promotion of the live baseline, which is the correct behavior.

**Alarm multipliers (unchanged in values; basis clarified):**

| Tier | Threshold | Operational Meaning | Automated Response |
|------|-----------|--------------------|--------------------|
| Advisory | 1.5× baseline | Elevated but explainable | Log to dashboard; no page |
| Warning | 2.5× baseline | Outside normal variation | Page on-call; investigate source |
| Critical | 4× baseline | Consistent with credential stuffing | Page on-call + security; rate limiting activates |
| Emergency | 7× baseline | Treat as security incident | Fallback protocol; incident declared |

**SMS cost reference scenarios:**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (high engagement) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full credential breach — all accounts | **MAU (10M)** | Up to 10M/day | ~$79,000 |

**Credential breach row — financial and operational governance (new):**

The $79,000/day figure for a full credential breach is not a planning