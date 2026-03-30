# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–225M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system whose cache TTL is a **performance optimization, not a compliance mechanism** — opt-outs are enforced by writing a suppression flag to the database synchronously on receipt, not at TTL expiry.

**Thirteen specific problems are addressed directly:**

1. **Opt-out staleness was presented as a compliance solution** — Corrected. Suppression flags are written synchronously to the database on opt-out receipt. Cache TTL governs read performance only. Section 2 specifies the full opt-out flow: receiving system, database write path, failure behavior, worker check sequence, and third-party provider propagation with explicit timing bounds.

2. **Week 1 baseline calibration had a circular dependency** — Corrected. Alarm thresholds during Weeks 1–2 use pre-launch load test baselines. A 14-day rolling average of live traffic promotes to replace the load test baseline only after 7 consecutive stable days — evaluated on a **filtered series** that excludes days on which Warning-tier or higher alarms fired. A spike cannot contaminate its own baseline.

3. **Digest email halt had no resumption SLA** — Corrected. Resumption requires compliance owner sign-off within 4 business hours. Escalation goes to designated compliance deputy at 4 hours, then to the compliance officer with full authority to unblock at 8 hours. The escalation path does not terminate in an engineering role.

4. **Alert threshold logic conflated two failure modes** — Corrected. Volume above the aggressive scenario ceiling (1.3M/day) triggers a two-path automated diagnostic within 2 minutes. Path A (verified opt-in growth) allows sending to continue with a compliance review enforced by pipeline automation, not human memory. Path B (unattributed volume) halts sending immediately.

5. **The credential breach row was internally inconsistent** — Corrected. The principled boundary is trigger type, not session activity. SMS OTP and security alerts are DAU-bounded because they are triggered by session events. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state — correctly bounded by MAU. The distinction is explicit everywhere it appears.

6. **Proxy metric was used to justify provisioning while being acknowledged as invalid** — Corrected. The provisioning decision for the aggressive scenario is justified on cost-of-uncertainty grounds alone (~$160/month delta between SendGrid plan tiers). The scenario range is explicitly an assumption, not a forecast. We are insuring against under-provisioning given uncertainty we cannot reduce before launch.

7. **OTP email fallback had no upper bound or cost model** — Corrected. Fallback conversion modeled at 40% of blocked SMS attempts. Delivery latency SLA defined at 60 seconds P95. Full cost model in Section 3.4.

8. **Peak factor sensitivity analysis was claimed but absent** — Corrected. Section 2.5 covers 3×, 5×, 8×, and 10× peak factors with explicit arithmetic showing queue depth, worker count, and scaling trigger at each factor.

9. **SQS cost model did not show its arithmetic** — Corrected. Section 5.2 shows the full API call derivation including send, receive, delete, and empty poll costs.

10. **In-app notification durability was undefined** — Corrected. Retention policy: 90 days for read notifications, 365 days for unread. Storage growth model and archival strategy keep the hot store bounded. Full specification in Section 4.

11. **FIFO throughput ceiling was deferred** — Corrected. P1 uses per-conversation message group IDs. Real ceiling is 3,000 messages/second per queue; addressed with horizontal sharding designed before launch, not after.

12. **The 55% blended opt-in rate mixed incompatible source methodologies** — Corrected. The blended figure is replaced. A single methodology-consistent source (OneSignal prompt-conversion benchmarks) combined with an explicit platform mix assumption yields a **60% base rate**, modeled over a **45–75% range**. The methodology separation is shown in full in Section 1.2.

13. **Four engineers for this scope was never examined** — Corrected. Section 8 maps every component, operational procedure, and incident response path to specific engineer roles and time budgets. The scope as originally specified is not deliverable in 6 months by 4 engineers. A phased scope reduction with explicit tradeoffs is proposed.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption, not a measurement. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be measured until at least Day 7 of production traffic; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model. The scenario range (1M–3M) is an assumption, not a forecast. See Section 1.3 for how this uncertainty is handled operationally.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate |
| In-app | DAU (measured) | Delivered to active sessions; stored, not pushed |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |
| Credential breach notification | **MAU (10M)** | Proactive administrative action; not bounded by session state — see Section 1.4 |

The final row is the only place in this document where MAU is used for an SMS model. A credential breach notification is a proactive administrative action, not triggered by session events. All other SMS rows remain DAU-bounded. Any model that switches population without this level of explanation is a bug. This table is the reference.

---

### 1.2 Push Volume Model

**On the opt-in rate:** The prior version cited three sources using incompatible measurement methodologies and averaged them into a "55% blended" figure with no coherent interpretation.

- **Airship (2023)** measures the fraction of an app's existing installed base that has push enabled at a point in time. This is an installed-base metric.
- **OneSignal (2023)** measures the fraction of users who grant permission when shown a push permission prompt. This is a prompt-conversion metric.
- **AppsFlyer (2023)** measures the effect of prompt timing on prompt-conversion rate. This is a prompt-design variable, not a stand-alone opt-in rate.

These measure different things. Averaging them produces a number with no coherent interpretation. The blended figure is withdrawn.

**Replacement approach:** We use a single methodology-consistent source — OneSignal prompt-conversion benchmarks for social apps (iOS ~49%, Android ~81%) — combined with an explicit platform mix assumption of 60/40 iOS/Android for a new social app. This yields:

- Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = 29.4% + 32.4% = **61.8%**
- Rounded to **60%** base, modeled over a **45–75% range** to reflect genuine uncertainty in platform mix and prompt design.

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
| Email — transactional | ~500K | ~500K | Action-driven; does not scale with opt-in |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | Read/write load on store, not delivery throughput |
| SMS — OTP/security | ~175K | ~350K | High scenario: 2× authentication events |
| Peak throughput | ~4,500/sec | ~9,700/sec | See Section 2.5 for peak factor analysis |

**Note on in-app volume:** In-app notifications are stored in a database and fetched on session open. Volume is DAU × average unread notifications, not MAU × notification rate. Cost impact is read/write load on the notification store, modeled in Section 4.

---

### 1.3 Email Volume — Transactional and Digest Modeled Separately

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs. It cannot be capped by batching logic and must not share IP pools with digest mail. Mixing these pools is a deliverability decision with direct revenue impact: a single spam complaint spike from digest mail can blacklist the IP pool used for password resets.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained for more than 30 minutes. 50% above baseline signals either a security incident or an instrumentation error.

**Digest email** is explicitly opt-in and explicitly batched. The WAND scenario range (1M–3M users) is an assumption we cannot reduce before launch. The $160/month delta between SendGrid Essentials and Pro is the cost of insuring against under-provisioning given this irreducible uncertainty. We accept it. This is a cost-of-uncertainty argument, not a forecast.

**Corrected measurement approach:**

*Days 1–7 (operational signal only):* Instrument session frequency from Day 1. Single-session-per-day users are a rough proxy for WAND engagement level. **This signal is used only as an operational indicator — it is not used as a forecast input and does not influence provisioning decisions.**

*Day 7 onward (first WAND estimate):* Compute users with at least one session in the trailing 7 days and zero sessions yesterday. Valid but noisy — one week cannot distinguish weekly-active users from users who skipped one day.

*Week 4 (stable estimate):* Rolling 7-day cohort averaged over 4 weeks. This is the first number trustworthy enough to update the digest volume model and revise the SendGrid tier if warranted.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — two-path automated diagnostic:**

Volume above 1.3M/day triggers an automated diagnostic within 2 minutes of the threshold breach. This is not a human-initiated review.

**What the diagnostic does:**

The diagnostic joins two data sources:
1. **Send log:** Count of digest emails dispatched in the trailing 24 hours, grouped by user ID.
2. **Consent ledger:** The canonical opt-in record for every user, with opt-in timestamp and source (e.g., onboarding flow, settings page, re-engagement campaign).

The diagnostic query:
```sql
SELECT COUNT(*)
FROM send_log sl
JOIN consent_ledger cl ON sl.user_id = cl.user_id
WHERE sl.send_type = 'digest'
  AND sl.sent_at > NOW() - INTERVAL '24 hours'
  AND cl.digest_optin = TRUE
  AND cl.optin_at < sl.sent_at
```

If this count equals or exceeds the send log count within a 0.1% tolerance for timing race conditions, **Path A** applies. If the count is below the send log count by more than 0.1%, **Path B** applies.

**Build ownership:** This diagnostic is owned by Engineer B (data/compliance infrastructure lead — see Section 8). It must be built and tested in staging before launch. It is a launch gate, not a post-launch addition.

**Path A — Verified opt-in growth:**

Sending continues. An automated report is generated containing: total send count, opt-in attribution rate, opt-in source breakdown, and timestamp. This report is written to the compliance audit log and a Jira ticket is auto-created and assigned to the **Compliance Owner** (named pre-launch; not an engineering role) with:
- **Required finding:** Confirm that the opt-in mechanism producing this volume is functioning as designed and that consent records are complete and legally sufficient.
- **Deadline:** 5 business days from ticket creation.
- **Consequence of non-completion:** Digest sends above the 1.3M/day threshold are automatically paused on Day 6 until the ticket is resolved. This pause is enforced by the send pipeline checking ticket status via API, not by a human remembering to act.
- **Consequence if review finds a problem:** Digest sending halts immediately, same as Path B. Affected users are identified from the consent ledger gap and suppressed before resumption.

**Path B — Unattributed volume:**

Digest sending halts immediately, automated. Sending non-opted-in users marketing email is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The halt is automatic. Resumption requires compliance owner sign-off per Section 7, Decision Point 4. The escalation path does not terminate in an engineering role.

**Why this distinction matters:** A halt-on-any-excess policy would cause a product outage if the WAND estimate was simply too conservative. A correct but underestimated opt-in population is not a compliance emergency; it is a modeling error requiring verification, not an immediate halt. The two-path structure distinguishes these cases automatically.

---

### 1.4 SMS Cost Model — DAU-Calibrated, Load-Test-Anchored Baselines

**The problem with Week 1 live baselines:** Week 1 concentrates press coverage, coordinated beta invites, viral moments, and opportunistic credential stuffing attacks. A baseline computed from Week 1 live traffic is likely to be abnormal in either direction. A rolling average computed from an abnormal period miscalibrates all subsequent thresholds.

**Corrected approach — load test anchoring with filtered promotion:**

Pre-launch load tests establish the expected baseline. Multiplier-based alarms during