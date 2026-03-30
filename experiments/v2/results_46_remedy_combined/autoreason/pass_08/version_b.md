# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system whose cache TTL is a performance optimization, not a compliance mechanism — opt-outs are enforced at write time, not at TTL expiry.

**Eleven specific problems from the previous revision are addressed directly:**

1. **The 60-second staleness bound was presented as a compliance solution** — Corrected. Opt-outs are now enforced by writing a suppression flag to the database synchronously on receipt. The cache TTL governs read performance only; a suppressed user cannot receive a notification even if the cache has not yet expired. The 60-second figure is removed from compliance language entirely. Section 4.3 describes the architecture and its limits honestly, with a note that the legal sufficiency of any specific implementation requires sign-off from legal counsel, not an engineering team.

2. **Week 1 baseline calibration had a circular dependency** — Corrected. Week 1 baselines are anchored to pre-launch load test results, not live traffic. Multiplier-based alarms use the load test baseline until a stable 14-day rolling average is established. The Week 1 live baseline is treated as suspect and cannot promote itself. Section 1.4 describes the transition protocol.

3. **Digest email halt had no resumption SLA** — Corrected. Resumption requires compliance owner sign-off within 4 business hours. If the primary owner is unavailable, the escalation path goes to their designated backup, then to the engineering lead with authority to unblock at 8 hours. Section 7 is now complete.

4. **The aggressive scenario ceiling conflated two different failure modes** — Corrected. Volume above 1.3M/day now triggers a two-path diagnostic: if the excess is attributable to a new population of legitimately opted-in users, sending continues with an audit log and a compliance review scheduled within 5 business days; if the excess cannot be attributed to a verified opt-in population, sending halts immediately. Section 1.3 defines the diagnostic logic.

5. **The full breach row was internally inconsistent** — Corrected. The principled boundary is not session activity but notification trigger type: event-driven security notifications (new device login, forced re-auth) are bounded by the triggering event rate, which is bounded by active sessions. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. The distinction is now explicit and the MAU row is labeled with this justification. Section 1.4 is revised.

6. **The proxy metric was used to justify provisioning while being acknowledged as invalid** — Corrected. The provisioning decision for the aggressive scenario is justified on cost-of-over-provisioning grounds alone ($80/month), independent of any proxy metric. The proxy metric is described only as an operational signal, not a forecast input. The $80/month derivation is now shown. Section 1.3 is revised.

7. **OTP email fallback had no upper bound or cost model** — Corrected. The fallback conversion rate is modeled at 40% of blocked SMS attempts (users who abandon the flow are not modeled as email conversions). Delivery latency SLA for OTP email is defined at 60 seconds P95. Cost ceiling is derived and included in the cost table. Section 3.4 is new.

8. **Peak factor sensitivity analysis was claimed but absent** — Corrected. The sensitivity table covering 3×, 5×, 8×, and 10× peak factors now appears in Section 2.5 with explicit arithmetic showing queue depth, worker count, and scaling trigger at each factor.

9. **SQS cost model did not show its arithmetic** — Corrected. Section 5.2 shows the full API call derivation including send, receive, delete, and empty poll costs. The revised estimate is higher than the previous figure.

10. **In-app notification durability was undefined** — Corrected. Section 4.5 defines retention policy (90 days for read notifications, 365 days for unread, configurable), storage growth model, and the archival strategy that keeps the hot store bounded.

11. **Four engineers for this scope was never examined** — Corrected. Section 8 maps every component, operational procedure, and incident response path to specific engineer roles and time budgets. It concludes that the scope as originally specified is not deliverable in 6 months by 4 engineers and proposes a phased scope reduction with explicit tradeoffs.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline, not as absolute figures derived from this assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be measured until at least Day 7 of production traffic. The 2M estimate is the largest single unknown in the volume model.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate; see Section 1.4 for the one exception |
| In-app | DAU (measured) | Delivered to active sessions; stored, not pushed |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |
| Credential breach notification | MAU (10M) | Proactive administrative action; not bounded by session state — see Section 1.4 |

The final row is the only place in this document where MAU is used for an SMS model. The justification is stated there and here: a credential breach notification is sent to all affected accounts as an administrative action, regardless of whether those accounts have active sessions. This is categorically different from event-driven security alerts (new device login, forced re-auth), which are triggered by session events and are correctly bounded by DAU. The distinction is principled, not arbitrary.

### 1.2 Push Volume Model

The 55% blended opt-in rate is derived from Airship Mobile Engagement Benchmarks (2023), OneSignal Push Notification Benchmarks (2023), and AppsFlyer State of App Marketing (2023). The honest uncertainty range is 40–70%. The architecture is sized for 70%; costs are modeled at 55%.

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
| Email — transactional | ~500K | ~500K | Action-driven |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | Read/write load on store |
| SMS — OTP/security | ~175K | ~350K | High scenario: 2× authentication events |
| Peak throughput | ~4,500/sec | ~9,700/sec | See Section 2.5 for peak factor analysis |

### 1.3 Email Volume — Transactional and Digest Modeled Separately

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs. It cannot be capped by batching logic and must not share IP pools with digest mail.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; modeled in Section 3.4 | Activated when SMS rate-limited |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained for more than 30 minutes.

**Digest email** is explicitly opt-in and explicitly batched.

**WAND measurement approach:**

*Days 1–7 (operational signal only):* Instrument session frequency from Day 1. Users with exactly one session in the trailing 24 hours are a rough proxy for WAND engagement level. **This signal is used only as an operational indicator — it is not used as a forecast input and does not influence provisioning decisions.**

*Day 7 onward (first WAND estimate):* Compute users active in the trailing 7 days with zero sessions yesterday. Valid but noisy.

*Week 4 (stable estimate):* Rolling 7-day cohort averaged over 4 weeks. First number trustworthy enough to update the digest volume model.

**Provisioning during the measurement gap:** We provision for the aggressive scenario (1.3M digest emails/day) at SendGrid. The justification is cost-of-insurance, not forecast accuracy. The marginal cost of provisioning for the aggressive scenario versus the conservative scenario is derived as follows:

- Conservative scenario: 120K/day × 30 days = 3.6M emails/month → SendGrid Essentials plan at ~$89/month
- Aggressive scenario: 1.3M/day × 30 days = 39M emails/month → SendGrid Pro plan at ~$249/month
- Delta: ~$160/month

We accept the $160/month insurance cost to avoid under-provisioning a user-facing feature during launch. This figure does not depend on the proxy metric; it is a straightforward cost comparison between two plan tiers.

**Digest volume scenarios:**

| Scenario | WAND Segment | Digest Opt-in | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Alert threshold — two-path diagnostic:**

Volume above 1.3M/day triggers an automated diagnostic before any halt decision:

**Path A — Legitimate opt-in growth:** If the volume increase is attributable to a verified opt-in population (audit log shows opt-in events matching the volume increase, with timestamps and user IDs), sending continues. An automated report is generated and a compliance review is scheduled within 5 business days to verify that the opt-in mechanism is functioning correctly and that consent records are complete.

**Path B — Unattributed volume increase:** If the volume increase cannot be attributed to a verified opt-in population within 15 minutes of automated diagnostic, digest sending halts immediately. Sending non-opted-in users marketing email is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The halt is automatic; resumption requires compliance owner sign-off per Section 7, Decision Point 4.

This distinction matters because the original halt-on-any-excess logic would cause a product outage if the WAND estimate was simply too conservative. A correct but underestimated opt-in population is not a compliance emergency; it is a modeling error that requires verification, not an immediate halt.

### 1.4 SMS Cost Model — DAU-Calibrated, Load-Test-Anchored Baselines

**The circular dependency problem with Week 1 baselines:**

Week 1 of production is the period of maximum baseline uncertainty. Press coverage, coordinated beta invites, viral moments, and opportunistic credential stuffing attacks all concentrate at launch. A baseline computed from Week 1 live traffic is likely to be abnormal in either direction. Calibrating alarm thresholds to an abnormal baseline miscalibrates all subsequent thresholds for the life of the system.

**Corrected approach — load test anchoring with controlled promotion:**

Pre-launch load tests establish the expected baseline for each traffic scenario. Multiplier-based alarms during Weeks 1–2 use the load test baseline. Starting Week 3, a 14-day rolling average of live traffic is computed daily. The live baseline **promotes to replace the load test baseline only when the rolling average has been stable for 7 consecutive days** — defined as no single day exceeding 1.8× the rolling average. Until that stability criterion is met, the load test baseline remains authoritative.

This prevents a Week 1 spike from becoming the permanent baseline. It also prevents a Week 1 lull (suppressed launch traffic) from setting an artificially low baseline that makes normal Week 3 traffic appear anomalous.

| Tier | Threshold | Operational Meaning | Automated Response |
|------|-----------|--------------------|--------------------|
| Advisory | 1.5× baseline | Elevated but explainable | Log to dashboard; no page |
| Warning | 2.5× baseline | Outside normal variation | Page on-call; investigate |
| Critical | 4× baseline | Consistent with credential stuffing | Page on-call + security; rate limiting activates |
| Emergency | 7× baseline | Treat as security incident regardless of cause | Fallback protocol; incident declared |

**SMS cost reference scenarios:**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (high engagement) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full credential breach — all accounts | **MAU (10M)** | 10M/day | ~$79,000 |

**Why the final row uses MAU, and why this is not inconsistent with the DAU model:**

The DAU model for SMS is justified by the claim that SMS OTP and security alerts are triggered by session events. This is correct for those notification types. A credential breach notification is categorically different: it is a proactive administrative action initiated by the operations team, not triggered by user session activity. The appropriate population is all affected accounts, which in a full breach is MAU. The other rows remain DAU-bounded because their trigger conditions remain session-bounded. The boundary is the trigger type, not an arbitrary modeling choice.

### 1.5 Infrastructure Cost

| Cost Component | Base/month | High/month | Delta | Notes |
|----------------|-----------|-----------|-------|-------|
| SQS (all queues; see Section 5.2 for derivation) | ~$2,800 | ~$6,400 | +$3,600 | Revised upward from previous estimate |
| FCM / APNs | $0 | $0 | — | Free |
| SendGrid — transactional (dedicated IP pool) | ~$300 | ~$300 | — | |
| SendGrid — digest/marketing (shared IP pool) | ~$249 | ~$249 | — | Provisioned for aggressive scenario |
| Twilio (SMS) | ~$1,383 | ~$2,765 | +$1,382 | |
| OTP email fallback (