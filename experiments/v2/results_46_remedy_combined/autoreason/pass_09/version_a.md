# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system whose cache TTL is a **performance optimization, not a compliance mechanism** — opt-outs are enforced by writing a suppression flag to the database synchronously on receipt, not at TTL expiry.

**Twelve specific problems are addressed directly:**

1. **Opt-out staleness was presented as a compliance solution** — Corrected. Suppression flags are written synchronously to the database on opt-out receipt. Cache TTL governs read performance only. A suppressed user cannot receive a notification even if the cache has not yet expired. Legal sufficiency of any specific implementation requires sign-off from legal counsel.

2. **Week 1 baseline calibration had a circular dependency** — Corrected. Alarm thresholds during Weeks 1–2 use pre-launch load test baselines. A 14-day rolling average of live traffic promotes to replace the load test baseline only after 7 consecutive stable days, defined as no single day exceeding 1.8× the rolling average.

3. **Digest email halt had no resumption SLA** — Corrected. Resumption requires compliance owner sign-off within 4 business hours. Escalation goes to designated backup, then to engineering lead with authority to unblock at 8 hours.

4. **Alert threshold logic conflated two failure modes** — Corrected. Volume above the aggressive scenario ceiling (1.3M/day) triggers a two-path diagnostic: if excess is attributable to a verified opt-in population, sending continues with an audit log and a compliance review within 5 business days; if excess cannot be attributed to a verified opt-in population within 15 minutes, digest sending halts immediately.

5. **The credential breach row was internally inconsistent** — Corrected. The principled boundary is trigger type, not session activity. Event-driven security notifications are bounded by DAU. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state, correctly bounded by MAU. The distinction is explicit everywhere it appears.

6. **Proxy metric was used to justify provisioning while being acknowledged as invalid** — Corrected. The provisioning decision for the aggressive scenario is justified on cost-of-insurance grounds alone (~$160/month delta between plan tiers), independent of any proxy metric.

7. **OTP email fallback had no upper bound or cost model** — Corrected. Fallback conversion rate modeled at 40% of blocked SMS attempts. Delivery latency SLA defined at 60 seconds P95. Cost ceiling derived and included in the cost table.

8. **Peak factor sensitivity analysis was claimed but absent** — Corrected. Sensitivity table covering 3×, 5×, 8×, and 10× peak factors appears in Section 2.5 with explicit arithmetic showing queue depth, worker count, and scaling trigger at each factor.

9. **SQS cost model did not show its arithmetic** — Corrected. Section 5.2 shows the full API call derivation including send, receive, delete, and empty poll costs.

10. **In-app notification durability was undefined** — Corrected. Retention policy: 90 days for read notifications, 365 days for unread. Storage growth model and archival strategy keep the hot store bounded.

11. **FIFO throughput ceiling was deferred** — Corrected. Analyzed before launch. P1 uses per-conversation message group IDs. Real ceiling is 3,000 messages/second per queue; addressed with horizontal sharding designed before launch.

12. **Four engineers for this scope was never examined** — Corrected. Section 8 maps every component, operational procedure, and incident response path to specific engineer roles and time budgets. The scope as originally specified is not deliverable in 6 months by 4 engineers. A phased scope reduction with explicit tradeoffs is proposed.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption, not a measurement. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be measured until at least Day 7 of production traffic. The 2M estimate is the largest single unknown in the volume model. See Section 1.3.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate |
| In-app | DAU (measured) | Delivered to active sessions; stored, not pushed |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |
| Credential breach notification | **MAU (10M)** | Proactive administrative action; not bounded by session state — see Section 1.4 |

The final row is the only place in this document where MAU is used for an SMS model. The justification is explicit: a credential breach notification is a proactive administrative action, not triggered by session events. All other SMS rows remain DAU-bounded. Any model that switches population without this level of explanation is a bug. This table is the reference.

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
| Peak throughput | ~4,500/sec | ~9,700/sec | See Section 2.5 for peak factor analysis |

**Note on in-app volume:** In-app notifications are stored in a database and fetched on session open. Volume is DAU × average unread notifications, not MAU × notification rate. Cost impact is read/write load on the notification store, modeled separately in Section 5.

### 1.3 Email Volume — Transactional and Digest Modeled Separately

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs. It cannot be capped by batching logic and must not share IP pools with digest mail. Mixing these pools is a deliverability decision with direct revenue impact: a single spam complaint spike from digest mail can blacklist the IP pool used for password resets.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; modeled in Section 3.4 | Activated when SMS rate-limited |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained for more than 30 minutes. 50% above baseline signals either a security incident or an instrumentation error.

**Digest email** is explicitly opt-in and explicitly batched. The 526K/day figure is a pre-launch estimate with no empirical foundation. It should be treated as an order-of-magnitude estimate, not a forecast.

**The logical problem with pre-launch WAND measurement:** WAND requires at least 7 days of session data by definition. A measurement plan claiming to produce a valid WAND cohort from the first week of production traffic is logically impossible. The stable estimate requires multiple weeks to smooth day-of-week effects.

**Corrected measurement approach:**

*Days 1–7 (proxy metric, operational signal only):* Instrument session frequency distribution from Day 1. Users with exactly one session in the trailing 24 hours are a rough proxy for the WAND segment's engagement level. **This signal is used only as an operational indicator — it is not used as a forecast input and does not influence provisioning decisions.**

*Day 7 onward (first WAND estimate):* Compute users with at least one session in the trailing 7 days and zero sessions yesterday. Valid but noisy — one week cannot distinguish weekly-active users from users who skipped one day.

*Week 4 (stable estimate):* Compute WAND as a rolling 7-day cohort averaged over 4 weeks. This is the first number trustworthy enough to update the digest volume model.

**Infrastructure during the measurement gap:** Provision for the aggressive scenario (1.3M digest emails/day) at SendGrid. The cost justification is cost-of-insurance, not forecast accuracy:

- Conservative scenario: 120K/day × 30 days = 3.6M emails/month → SendGrid Essentials ~$89/month
- Aggressive scenario: 1.3M/day × 30 days = 39M emails/month → SendGrid Pro ~$249/month
- Delta: ~$160/month

We accept the $160/month insurance cost to avoid under-provisioning a user-facing feature during launch. This figure does not depend on the proxy metric.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — two-path diagnostic:**

Volume above 1.3M/day triggers an automated diagnostic before any halt decision:

**Path A — Legitimate opt-in growth:** If the volume increase is attributable to a verified opt-in population (audit log shows opt-in events matching the volume increase, with timestamps and user IDs), sending continues. An automated report is generated and a compliance review is scheduled within 5 business days to verify that the opt-in mechanism is functioning correctly and consent records are complete.

**Path B — Unattributed volume increase:** If the volume increase cannot be attributed to a verified opt-in population within 15 minutes of automated diagnostic, digest sending halts immediately. Sending non-opted-in users marketing email is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The halt is automatic; resumption requires compliance owner sign-off per Section 7, Decision Point 4.

This distinction matters because a halt-on-any-excess policy would cause a product outage if the WAND estimate was simply too conservative. A correct but underestimated opt-in population is not a compliance emergency; it is a modeling error that requires verification, not an immediate halt.

### 1.4 SMS Cost Model — DAU-Calibrated, Load-Test-Anchored Baselines

**The problem with Week 1 live baselines:** Week 1 of production is the period of maximum baseline uncertainty. Press coverage, coordinated beta invites, viral moments, and opportunistic credential stuffing attacks all concentrate at launch. A baseline computed from Week 1 live traffic is likely to be abnormal in either direction. Setting alarm thresholds against an abnormal baseline miscalibrates all subsequent thresholds for the life of the system.

**Corrected approach — load test anchoring with controlled promotion:**

Pre-launch load tests establish the expected baseline for each traffic scenario. Multiplier-based alarms during Weeks 1–2 use the load test baseline. Starting Week 3, a 14-day rolling average of live traffic is computed daily. The live baseline **promotes to replace the load test baseline only when the rolling average has been stable for 7 consecutive days** — defined as no single day exceeding 1.8× the rolling average. Until that stability criterion is met, the load test baseline remains authoritative.

This prevents a Week 1 spike from becoming the permanent baseline. It also prevents a Week 1 lull from setting an artificially low baseline that makes normal Week 3 traffic appear anomalous.

The multipliers below are chosen based on operational meaning, independent of the underlying DAU figure:

| Tier | Threshold | Operational Meaning | Automated Response |
|------|-----------|--------------------|--------------------|
| Advisory | 1.5× baseline | Elevated but explainable (campaign, feature launch) | Log to dashboard; no page |
| Warning | 2.5× baseline | Outside normal variation; requires explanation | Page on-call; investigate source |
| Critical | 4× baseline | Consistent with credential stuffing attack | Page on-call + security; rate limiting activates |
| Emergency | 7× baseline | Treat as security incident regardless of cause | Fallback protocol; incident declared |

**Why these multipliers:** A 1.5× elevation is within the range of legitimate campaign traffic and day-of-week variation. A 2.5× elevation is outside normal variation and requires an explanation before the end of the on-call shift. A 4× elevation is consistent with a credential stuffing attack. A 7× elevation is consistent with a major incident regardless of the absolute baseline. These multipliers are independent of the 35% DAU assumption.

**SMS cost reference scenarios (pre-launch planning only; replaced by measured baseline after Week 1):**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (high engagement) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full credential breach — all accounts | **MAU (10M)** | 10M/day | ~$79,000 |

**Why the final row uses MAU, and why this is not inconsistent:** The DAU model for SMS is justified because SMS OTP and security alerts are triggered by