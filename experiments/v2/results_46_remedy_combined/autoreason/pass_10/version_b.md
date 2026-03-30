# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Read This Document

This document is organized as a forward-facing design specification. It does not assume familiarity with any prior draft. Where a design decision required choosing between alternatives, the choice and its reasoning are stated inline. Where a decision requires authorization from a role outside engineering, that role, the required decision, and the deadline are identified explicitly.

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

## 1. Scale Model

### 1.1 Population Definitions

Two population figures are used throughout this document. They are not interchangeable, and every volume estimate identifies which one it uses.

**MAU (10M):** Monthly active users. Used for push opt-in estimates. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and operational alarm baselines. The 35% figure is a planning assumption. All operational thresholds that depend on DAU are anchored to load test baselines, not to this assumption directly. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used only for digest email modeling. A stable estimate requires four weeks of production data. The pre-launch range (1M–3M users) is an assumption. Section 1.3 specifies what happens operationally before a stable estimate exists.

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in base | MAU (10M) | Token persists; opt-in is a device setting |
| SMS OTP / security alerts | DAU (measured) | Bounded by active session rate |
| In-app | DAU (measured) | Delivered to active sessions |
| Digest email | WAND (estimated until Week 4) | Target audience |
| Transactional email | Event-driven | Not population-derived |
| Credential breach notification | MAU (10M) | Proactive administrative action; not bounded by session state — see Section 1.5 |

---

### 1.2 Push Opt-In Rate

**Source selection and its limitations:**

We use OneSignal prompt-conversion benchmarks for social apps (iOS ~49%, Android ~81%) as the primary source. This is a prompt-conversion metric — the fraction of users who grant permission when shown a prompt — which is the right measurement for sizing a new app's opted-in population.

**Acknowledged limitation of this source:** OneSignal's benchmarks are derived from apps that chose OneSignal as their push provider. This is a self-selected sample. Apps that use OneSignal may differ systematically from social apps generally — in their user demographics, prompt design practices, or the aggressiveness of their prompt timing. We cannot quantify this selection bias before launch. The consequence is that our opt-in estimate carries an unquantifiable source bias in addition to the quantifiable uncertainty from platform mix.

**Platform mix assumption:**

We assume 60% iOS / 40% Android for a new social app in the US market, based on Statista US smartphone OS market share data (2023: iOS ~57%). We round to 60/40 for simplicity.

**This is the most uncertain input in the opt-in calculation.** A different mix produces materially different results:

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | (0.40 × 49%) + (0.60 × 81%) = 68.2% |
| 50/50 | (0.50 × 49%) + (0.50 × 81%) = 65.0% |
| **60/40 (assumed)** | **(0.60 × 49%) + (0.40 × 81%) = 61.8%** |
| 70/30 | (0.70 × 49%) + (0.30 × 81%) = 58.6% |

The range across plausible platform mixes is 58.6%–68.2%. We round our base estimate to **60%** and model over a **45%–75% range** to cover both platform mix uncertainty and source bias. The lower bound (45%) accommodates a heavier iOS mix or a below-benchmark prompt conversion rate. The upper bound (75%) accommodates an Android-heavy user base or above-benchmark prompt design.

**Calibration plan:** We will measure actual opt-in rates in Week 1 of production and update the model. Given the acknowledged source limitations, the Week 1 measurement supersedes this estimate.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% opt-in at 15 notifications/day.

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** A spam complaint spike from digest mail can blacklist the pool used for password resets. This is a deliverability decision with direct revenue impact and is not negotiable.

**Transactional email:**

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day new registrations |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | |

Alarm: >750K/day sustained for 30+ minutes. 50% above ceiling signals a security incident or instrumentation error.

**Digest email:**

The WAND population is unknown before Week 4. This creates a specific operational problem: the volume-based alert threshold may fire during the period when we cannot distinguish "our model was wrong" from "something is wrong." Section 1.3.1 addresses this directly.

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

---

#### 1.3.1 The Pre-Week-4 Measurement Gap — What Actually Happens

The proposal acknowledges a genuine problem: the volume alert threshold may fire before we have a reliable WAND estimate. Here is the explicit operational specification for that period.

**Days 1–6:** No digest sends. This is not a capability gap — it is deliberate. You cannot send a weekly digest before a week has elapsed. No measurement problem exists during this period because no digest sends occur.

**Day 7 — First digest send:** Volume is bounded by the number of users who completed onboarding in Week 1 and opted into digest email during that flow. This is a directly measurable count from the consent ledger — not a WAND estimate. We know exactly how many users opted in through the onboarding flow because we wrote those records. Day 7 volume is consent-ledger-bounded, not WAND-estimated.

**Days 7–27 (Weeks 1–4):** Digest send volume grows as more users complete their first week and become eligible. During this period, the eligible population is fully enumerable from the consent ledger — every user who (a) opted in and (b) has been registered for at least 7 days. The WAND estimate is irrelevant during this growth phase because we are not yet sending to a steady-state population; we are sending to a cohort that grows by roughly one week's worth of new registrations each day.

**Week 4 onward:** The first cohort has now completed four weeks. The WAND population — users who registered more than a month ago, are still active weekly, but not daily — is now estimable from session logs. This is when the WAND estimate becomes a necessary input to volume forecasting.

**Implication for the alert threshold:** The 1.3M/day threshold cannot be reached before Week 4 under any plausible new-user registration rate, because the eligible population in Weeks 1–3 is a subset of total registrations, not the full WAND population. The diagnostic therefore does not need to handle a "threshold fires before stable estimate exists" case — the timeline prevents it.

**What this means for the two-path diagnostic:** The diagnostic is relevant only after Week 4, when the full WAND population is eligible. We build and test it before launch, but it will not fire during the measurement gap period. This closes the gap identified in the critique.

---

#### 1.3.2 The Two-Path Diagnostic — Corrected Design

The prior version had a fundamental logic error: it treated a successful database join as proof of valid consent. A bug in the onboarding flow that writes bad consent records would cause Path A to fire and sending to continue. The corrected design separates consent record existence from consent record validity.

**What triggers the diagnostic:** Digest send volume exceeds 1.3M/day (the aggressive scenario ceiling).

**What the diagnostic actually checks:**

The diagnostic runs three independent checks, not one. All three must pass for Path A to apply.

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

If `sends_without_consent_record > 0`: Path B fires immediately. No tolerance. Sending to a user with no consent record is not a race condition; it is a violation.

**Check 2 — Consent record age distribution:**

A sudden volume spike accompanied by a cluster of consent records created in a narrow time window is a signal of a batch-write bug or a dark pattern in the onboarding flow. The diagnostic checks:

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

If any single hour contains more than 3× the rolling 7-day hourly average of new opt-ins, this is flagged as an anomaly. Sending does not automatically continue — the anomaly is included in the Path A report and the compliance review deadline is shortened from 5 business days to 2 business days.

**Check 3 — Opt-in source attribution:**

Every consent record must have an `optin_source` field (e.g., `onboarding_v2`, `settings_page`, `re_engagement_email_2024_01`). The diagnostic checks that all consent records in the volume spike are attributable to a known, active opt-in mechanism:

```sql
SELECT optin_source, COUNT(*) AS count
FROM consent_ledger
WHERE digest_optin = TRUE
  AND optin_at > NOW() - INTERVAL '48 hours'
GROUP BY optin_source
```

If any records have a null or unrecognized `optin_source`, Path B fires. Unknown consent sources are not a race condition.

**Path A applies only if:** Check 1 finds zero unconsented sends, Check 2 finds no anomalous clustering, and Check 3 finds all sources are known and active.

**Path A outcome:** Sending continues. Automated report written to compliance audit log. Jira ticket created and assigned to Compliance Owner with a 5-day deadline (shortened to 2 days if Check 2 flagged clustering). See Section 1.3.3 for the ticket enforcement mechanism.

**Path B applies if:** Any check fails.

**Path B outcome:** Digest sending halts immediately. Resumption requires Compliance Owner sign-off per Section 7. The halt is enforced by the send pipeline, not by human memory.

**Why three checks instead of one:** The original single-query design was a tautology — it confirmed that the database said consent existed, which is precisely what a consent-writing bug would also produce. The three-check design requires consent records to be present, to have arrived through a plausible mechanism (not a batch spike), and to be attributable to a known opt-in flow. A bug that writes bad consent records is much less likely to pass all three checks simultaneously.

**What this design cannot catch:** A sophisticated, sustained dark pattern that consistently writes consent records through a recognized opt-in flow. This is a product/legal review problem, not a data pipeline problem. The compliance ticket (Path A) exists precisely to route this to human review. The diagnostic's job is to filter out the obvious automated failures; it is not a substitute for compliance oversight.

---

#### 1.3.3 Jira Ticket Enforcement — Specified

The prior version claimed that digest sends would be "automatically paused on Day 6" if a Jira ticket wasn't resolved, enforced by the "send pipeline checking ticket status via API." This was presented without any design. Here is the actual design.

**The Jira API is not the enforcement mechanism.** Jira ticket states are informal and not designed for pipeline gating. Relying on a Jira API call to block a send pipeline is fragile: Jira can be slow, ticket states can be ambiguous, and the integration adds a dependency on a third-party SaaS for a compliance-critical path.

**Actual enforcement mechanism — a compliance gate table:**

```sql
CREATE TABLE compliance_gates (
  gate_id UUID PRIMARY KEY,
  gate_type VARCHAR(50) NOT NULL,  -- e.g., 'digest_volume_review'
  status VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'open', 'approved', 'blocked'
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deadline_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ,
  resolved_by VARCHAR(255),
  jira_ticket_id VARCHAR(50),  -- reference only; not used for enforcement
  notes TEXT
);
```

When the diagnostic fires Path A, it:
1. Inserts a row into `compliance_gates` with `status = 'open'` and `deadline_at = NOW() + INTERVAL '5 days'` (or 2 days if Check 2 flagged clustering).
2. Creates a Jira ticket (reference only).
3. Sends a notification to the Compliance Owner via email and Slack with a link to an internal review page.

**The send pipeline checks `compliance_gates`** before each digest batch:

```sql
SELECT COUNT(*) FROM compliance_gates
WHERE gate_type = 'digest_volume_review'
  AND status = 'open'
  AND deadline_at < NOW()
```

If this query returns any rows, the digest send batch does not proceed. This check is a local database query — no external API call, no Jira dependency.

**Compliance Owner resolves the gate** by navigating to the internal review page and clicking "Approve" or "Block." This action updates `status` in `compliance_gates` and writes an audit log entry. The Jira ticket is updated as a side effect, not as the enforcement mechanism.

**Escalation:** If `deadline_at` is reached with `status = 'open'` (neither approved nor blocked), an automated alert fires to the compliance escalation chain (Section 7). The gate remains open — the pipeline remains paused — until explicit resolution. There is no timeout that auto-approves.

**This mechanism is owned by Engineer B and is a launch gate.** It must be built, tested in staging, and verified before production traffic is enabled.

---

### 1.4 SMS Volume