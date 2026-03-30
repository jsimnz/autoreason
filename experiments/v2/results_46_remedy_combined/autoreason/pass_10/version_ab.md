# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Read This Document

This is a forward-facing design specification. Where a decision required choosing between alternatives, the choice and reasoning are stated inline. Where a decision requires authorization outside engineering, the responsible role, required decision, and deadline are identified explicitly.

**Sections:**
1. Scale Model
2. Delivery Architecture and Priority Logic
3. Channel Specifications (Push, Email, SMS, In-App)
4. In-App Notification Store
5. Infrastructure and Cost
6. Failure Handling
7. Compliance and Preference Management
8. Team Scope and Feasibility

---

## Executive Summary

This proposal designs a notification system handling 20–225M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures; proven third-party delivery providers over self-operated infrastructure; incremental delivery with explicit failure handling over optimistic pipelines; and a preference system whose cache TTL is a **performance optimization, not a compliance mechanism** — opt-outs are enforced by writing a suppression flag to the database synchronously on receipt, not at TTL expiry.

**Twelve specific design decisions are addressed explicitly:**

1. **Opt-out staleness is not a compliance solution.** Suppression flags are written synchronously to the database on opt-out receipt. Cache TTL governs read performance only. Section 7 specifies the full opt-out flow: receiving system, database write path, failure behavior, worker check sequence, and third-party provider propagation with explicit timing bounds.

2. **Alarm thresholds during Weeks 1–2 use pre-launch load test baselines.** A 14-day rolling average of live traffic promotes to replace the load test baseline only after 7 consecutive stable days — evaluated on a filtered series that excludes days on which Warning-tier or higher alarms fired. A spike cannot contaminate its own baseline.

3. **Digest email halt has an explicit resumption SLA.** Resumption requires compliance owner sign-off within 4 business hours. Escalation goes to a designated compliance deputy at 4 hours, then to the compliance officer with full authority to unblock at 8 hours. The escalation path does not terminate in an engineering role.

4. **Volume anomalies trigger a three-check automated diagnostic, not a single query.** A single consent-record join is a tautology — it confirms the database says consent exists, which is precisely what a consent-writing bug would also produce. Three independent checks are required: record existence, record age distribution, and opt-in source attribution. Section 1.3 specifies the full design.

5. **Population boundaries are principled and consistent.** SMS OTP and security alerts are DAU-bounded because they are triggered by session events. Credential breach notifications are MAU-bounded because they are proactive administrative actions not bounded by session state. Every row in the population table identifies which boundary applies and why.

6. **Provisioning for the aggressive scenario is justified on cost-of-uncertainty grounds.** The ~$160/month delta between SendGrid plan tiers is the cost of insuring against under-provisioning given irreducible pre-launch uncertainty. This is a cost-of-uncertainty argument, not a forecast.

7. **OTP email fallback has an explicit upper bound and cost model.** Fallback conversion modeled at 40% of blocked SMS attempts. Delivery latency SLA defined at 60 seconds P95. Full cost model in Section 3.4.

8. **Peak factor sensitivity is fully specified.** Section 2.5 covers 3×, 5×, 8×, and 10× peak factors with explicit arithmetic showing queue depth, worker count, and scaling trigger at each factor.

9. **The blended opt-in rate is replaced with a methodology-consistent figure.** A single source (OneSignal prompt-conversion benchmarks) combined with an explicit platform mix assumption yields a 60% base rate modeled over a 45–75% range. The methodology is shown in full in Section 1.2.

10. **In-app notification durability is fully specified.** Retention policy: 90 days for read notifications, 365 days for unread. Storage growth model and archival strategy keep the hot store bounded. Full specification in Section 4.

11. **FIFO throughput ceiling is addressed before launch.** P1 uses per-conversation message group IDs. Real ceiling is 3,000 messages/second per queue; addressed with horizontal sharding designed pre-launch, not deferred.

12. **Team scope is explicitly examined.** Section 8 maps every component to specific engineer roles and time budgets. The original scope is not fully deliverable in 6 months by 4 engineers. A phased scope reduction with explicit tradeoffs is proposed.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. They are not interchangeable. Every volume estimate identifies which one it uses.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption, not a measurement. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. Cannot be meaningfully estimated until Day 7 of production traffic; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model. See Section 1.3 for how this uncertainty is handled operationally.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in base | MAU (10M) | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate |
| In-app | DAU (measured) | Delivered to active sessions |
| Digest email | WAND (estimated until Week 4) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |
| **Credential breach notification** | **MAU (10M)** | **Proactive administrative action; not bounded by session state** |

The credential breach row is the only place in this document where MAU is used for an SMS model. The principled boundary is trigger type: SMS OTP and security alerts are DAU-bounded because they are triggered by session events. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. Any model that switches population without this explanation is a bug. This table is the reference.

---

### 1.2 Push Opt-In Rate

**Why the prior blended figure is withdrawn:**

Three sources were previously averaged into a "55% blended" opt-in rate. Those sources use incompatible measurement methodologies:

- **Airship (2023):** Measures the fraction of an app's installed base that has push enabled at a point in time. An installed-base metric.
- **OneSignal (2023):** Measures the fraction of users who grant permission when shown a push permission prompt. A prompt-conversion metric.
- **AppsFlyer (2023):** Measures the effect of prompt timing on prompt-conversion rate. A prompt-design variable, not a standalone opt-in rate.

Averaging these produces a number with no coherent interpretation. The blended figure is withdrawn.

**Replacement approach — single methodology-consistent source:**

We use OneSignal prompt-conversion benchmarks for social apps (iOS ~49%, Android ~81%) as the sole source. This is the right measurement for sizing a new app's opted-in population: it measures what happens when a new user is shown a permission prompt.

**Acknowledged limitation:** OneSignal's benchmarks are derived from apps that chose OneSignal as their push provider — a self-selected sample. We cannot quantify this selection bias before launch. It is an irreducible source of uncertainty.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share. This is the most uncertain input in the calculation.

Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | 68.2% |
| 50/50 | 65.0% |
| **60/40 (assumed)** | **61.8%** |
| 70/30 | 58.6% |

We model over a **45%–75% range** to cover platform mix uncertainty and source bias. Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day. The Week 1 production measurement supersedes this estimate.

**Sensitivity table:**

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** A spam complaint spike from digest mail can blacklist the pool used for password resets. This is a deliverability decision with direct revenue impact and is not negotiable.

**Transactional email:**

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | |

Alert threshold: >750K/day sustained for 30+ minutes. 50% above ceiling signals a security incident or instrumentation error.

**Digest email:**

The WAND population is unknown before Week 4. The $160/month delta between SendGrid plan tiers is the cost of insuring against under-provisioning given irreducible uncertainty. We accept it. This is a cost-of-uncertainty argument, not a forecast.

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**The measurement timeline:**

*Days 1–6:* No digest sends. The eligible population is zero — you cannot send a weekly digest before a week has elapsed. No measurement problem exists during this period.

*Day 7 — First digest send:* Volume is bounded by users who completed onboarding in Week 1 and opted into digest email during that flow. This is a directly measurable count from the consent ledger, not a WAND estimate.

*Days 7–27 (Weeks 1–4):* Digest send volume grows as more users complete their first week and become eligible. The eligible population is fully enumerable from the consent ledger — every user who (a) opted in and (b) has been registered for at least 7 days. The WAND estimate is irrelevant during this growth phase.

*Week 4 onward:* The WAND population is now estimable from session logs. This is when the WAND estimate becomes a necessary forecast input. The 1.3M/day threshold cannot be reached before Week 4 under any plausible new-user registration rate.

---

#### 1.3.1 The Three-Check Automated Diagnostic

Volume above 1.3M/day triggers an automated diagnostic within 2 minutes of the threshold breach. This is not a human-initiated review.

**Why three checks, not one:**

The original single-query design was a tautology — it confirmed that the database said consent existed, which is precisely what a consent-writing bug would also produce. The three-check design requires consent records to be present, to have arrived through a plausible mechanism, and to be attributable to a known opt-in flow. A bug that writes bad consent records is much less likely to pass all three checks simultaneously.

**Check 1 — Consent record existence (necessary, not sufficient):**

```sql
SELECT
  COUNT(*) AS total_sends,
  COUNT(cl.user_id) AS sends_with_consent_record,
  COUNT(*) - COUNT(cl.user_id) AS sends_without_consent_record
FROM send_log sl
LEFT JOIN consent_ledger cl
  ON sl.user_id = cl.user_id
  AND cl.digest_optin = TRUE
  AND cl.optin_at < sl.sent_at
WHERE sl.send_type = 'digest'
  AND sl.sent_at > NOW() - INTERVAL '24 hours'
```

If `sends_without_consent_record > 0`: Path B fires immediately. Sending to a user with no consent record is not a race condition; it is a violation.

**Check 2 — Consent record age distribution:**

A sudden volume spike accompanied by a cluster of consent records created in a narrow time window signals a batch-write bug or a dark pattern in the onboarding flow.

```sql
SELECT
  DATE_TRUNC('hour', optin_at) AS hour_bucket,
  COUNT(*) AS new_optins
FROM consent_ledger
WHERE digest_optin = TRUE
  AND optin_at > NOW() - INTERVAL '48 hours'
GROUP BY 1
ORDER BY 1
```

If any single hour contains more than 3× the rolling 7-day hourly average of new opt-ins, this is flagged as an anomaly. Sending does not automatically halt, but the Path A compliance review deadline is shortened from 5 business days to 2 business days.

**Check 3 — Opt-in source attribution:**

Every consent record must have an `optin_source` field (e.g., `onboarding_v2`, `settings_page`, `re_engagement_email_2024_01`).

```sql
SELECT optin_source, COUNT(*) AS count
FROM consent_ledger
WHERE digest_optin = TRUE
  AND optin_at > NOW() - INTERVAL '48 hours'
GROUP BY optin_source
```

If any records have a null or unrecognized `optin_source`, Path B fires. Unknown consent sources are not a race condition.

**Path A applies only if:** Check 1 finds zero unconsented sends, Check 2 finds no anomalous hour-level clustering, and Check 3 finds all sources are known and active.

**Path B applies if:** Any check fails.

---

#### 1.3.2 Path Outcomes and Compliance Gate Enforcement

**Path A — Verified opt-in growth:**

Sending continues. An automated report is written to the compliance audit log. A compliance gate record is inserted and a Jira ticket is created as a reference (not as the enforcement mechanism — see below).

**Path B — Unattributed volume:**

Digest sending halts immediately. Sending non-opted-in users marketing email is a CAN-SPAM violation in the US and a GDPR Article 6 lawful basis failure in the EU. The halt is automatic and enforced by the send pipeline. Resumption requires compliance owner sign-off per Section 7. The escalation path does not terminate in an engineering role.

**Why the Jira API is not the enforcement mechanism:**

Jira ticket states are informal and not designed for pipeline gating. Jira can be slow, ticket states can be ambiguous, and the integration adds a dependency on a third-party SaaS for a compliance-critical path.

**Actual enforcement mechanism — compliance gate table:**

```sql
CREATE TABLE compliance_gates (
  gate_id         UUID PRIMARY KEY,
  gate_type       VARCHAR(50)  NOT NULL,   -- e.g., 'digest_volume_review'
  status          VARCHAR(20)  NOT NULL