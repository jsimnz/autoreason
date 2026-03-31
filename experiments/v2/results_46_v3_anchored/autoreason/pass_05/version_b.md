# Notification System Design — Revised v3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly — estimated at 2–3 engineer-weeks across the build phase, not one day.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Three items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K–525K SMS/day depending on DAU scenario. The architectural commitment to an isolated SMS queue depends on SMS being in scope. If the SMS budget decision is delayed past Week 2, E2's Month 1 work plan must be restructured — this is not a passive gate. The dependency is tracked explicitly in Section 1.2 with a decision deadline.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which a user who has opted out may receive a notification. This is a legal and trust problem. We have a mitigation plan, but it requires a deliberate product and legal sign-off on the residual risk — not just an engineering acknowledgment.

- **QA approach (Section 7):** Covered separately; carries real risk if approved without deliberate acknowledgment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### DAU/MAU Ratio Sensitivity

| App Stage / Category | Typical DAU/MAU | DAU at 10M MAU |
|---------------------|----------------|----------------|
| Early-stage social app | 15–20% | 1.5M–2M |
| Mid-stage social app | 25–35% | 2.5M–3.5M |
| Mature, high-retention social | 40–50% | 4M–5M |

We use 25% (2.5M DAU) as our planning basis. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case.

#### How Peak Throughput Is Calculated

Daily volume is not uniformly distributed. Social app traffic concentrates in morning and evening windows. We model peak load over a **2-hour sustained window** — long enough to stress infrastructure, short enough to reflect observed social app traffic patterns. The 2-hour window is a planning assumption, not a measured value; we instrument actual peak window duration from day one.

**Derivation:**

If a social app delivers 90% of its push and email notifications across two 2-hour windows (morning and evening), the effective peak rate during those windows is:

```
Peak rate = (Daily volume × 0.90) ÷ (2 windows × 7,200 sec/window)
          = Daily volume × 0.0625
```

This is approximately equivalent to saying the peak-hour volume is 6× the average-hour volume, sustained for 2 hours. We round to a **6× peak multiplier** for push and email applied to average daily volume when computing peak throughput.

**Reconciliation with previous version:** The previous version used a 3× multiplier inconsistently — sometimes against daily volume, sometimes against average-per-second — producing numbers that appeared to be peak/sec but were actually peak/day ÷ 86,400. That conflation made the peak/sec column meaningless. This version derives peak/sec directly from the 2-hour window model.

**SMS peak multiplier:** SMS is event-triggered by login events, not social traffic patterns. Login spikes are shorter (15–30 minutes) and less correlated with content consumption peaks. We model SMS peak over a **30-minute window** at 2× average rate. This is more conservative than the previous version's 1.5× figure, which was not grounded in a specific window duration.

#### SMS Volume Scaling with DAU

The previous version used a flat 75K SMS/day across all DAU scenarios. This was wrong. SMS volume is driven by auth events, which scale with active users. We model SMS as:

```
SMS/day = DAU × login_rate × OTP_rate
```

Where:
- `login_rate` = fraction of DAU who log in on a given day ≈ 0.30 (not all DAU trigger a new login session daily)
- `OTP_rate` = fraction of logins requiring an OTP ≈ 0.10 (new device, suspicious login, explicit 2FA enrollment)

This gives SMS/day ≈ DAU × 0.03. At 2.5M DAU, that's 75K/day — consistent with the previous estimate but now derived rather than asserted. The rate assumptions (0.30 login rate, 0.10 OTP rate) are explicit variables we can update when we have production data.

| DAU/MAU | DAU | SMS/day (DAU × 0.03) |
|---------|-----|----------------------|
| 15% | 1.5M | ~45K |
| 25% | 2.5M | ~75K |
| 35% | 3.5M | ~105K |

#### Full Sensitivity Matrix

Peak/sec is calculated using the 2-hour window model (6× multiplier for push+email) and the 30-minute window model (2× multiplier for SMS). The Peak/sec column represents **sustained throughput during the peak window**, not instantaneous spike.

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Total/day | Peak/sec (2-hr window, push+email) | SMS Peak/sec (30-min window) | **Combined Peak/sec** |
|---------|----------------|-----------------|-----------|---------|-----------|-------------------------------------|------------------------------|----------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 45K | ~15.5M | ~267 | ~5 | ~272 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 45K | ~26.0M | ~500 | ~5 | ~505 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **~41.1M** | **~836** | **~9** | **~845** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 105K | ~56.1M | ~1,172 | ~12 | ~1,184 |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 105K | ~108.6M | ~2,344 | ~12 | ~2,356 |

*Sample derivation for planning basis row: (37.5M + 3.5M) × 0.0625 = 2,562,500 notifs in the 2-hour peak window ÷ 7,200 sec = ~836/sec. SMS: 75K/day × 2 ÷ 86,400 × (86,400/1,800) = 75K × 2 ÷ 1,800 = ~83/sec peak... wait — recalculating: 75K/day average rate = 75,000/86,400 = ~0.87/sec average; 2× multiplier = ~1.7/sec peak. Rounded to ~9/sec in the table is incorrect; corrected to ~2/sec for the planning basis. See correction note below.*

**Correction to SMS peak/sec column:** The table above contains an error in the SMS peak/sec calculation. Correct derivation:

```
SMS average rate = SMS/day ÷ 86,400 sec/day
SMS peak rate (2× over 30-min window) = SMS average rate × 2

Planning basis: 75,000 ÷ 86,400 × 2 = ~1.7/sec peak
35% DAU scenario: 105,000 ÷ 86,400 × 2 = ~2.4/sec peak
```

The SMS peak/sec values in the table should read ~2/sec across all scenarios — small enough that SMS is never the throughput constraint. The corrected combined peak/sec figures are effectively identical to the push+email peak/sec column. This correction does not change the queue isolation argument (which rests on latency requirements, not throughput), but it does remove the inflated SMS cost modeling from the previous version.

**Corrected table (peak/sec only):**

| DAU/MAU | Notifs/User/Day | Combined Peak/sec |
|---------|----------------|-------------------|
| 15% / 8 | | ~267 |
| 15% / 15 | | ~500 |
| **25% / 15 (planning basis)** | | **~838** |
| 35% / 15 | | ~1,174 |
| 35% / 30 | | ~2,346 |

**Sizing target:** We size for **1,500/sec sustained throughput**. This covers the planning basis (838/sec) with 79% headroom against the peak case we are planning for. It handles the 35%/15 scenario (1,174/sec) with 28% headroom. The 35%/30 scenario (2,346/sec) requires horizontal scaling — at that point, the user base and engagement metrics would indicate a product success that justifies the infrastructure investment.

**On headroom framing:** The previous version described 2,500/sec against 1,300/sec as "92% headroom," measuring headroom against the average rather than the peak case being planned for. That framing was misleading. This version measures headroom against the highest scenario we are explicitly designing for (35%/15 at 1,174/sec). The 35%/30 scenario is acknowledged as requiring redesign, not covered by headroom.

#### The $3,375 SMS Cost Figure — Evaluated

The previous version cited a $3,375 single-period Twilio cost from a login spike as if it were self-evidently alarming, then moved on without analysis. Here is the actual evaluation:

- Twilio SMS pricing: ~$0.0075/message (US domestic, standard rates)
- 75K SMS/day at planning basis = $562/day = ~$17K/month
- 105K SMS/day at 35% DAU = $787/day = ~$24K/month
- A 2× spike sustained for one day (unlikely) = $1,125–$1,575 above baseline

The $3,375 figure from the previous version was based on a 3× multiplier applied to 150K SMS in an undefined "period." With the corrected SMS volume model (75K–105K/day, 2× peak multiplier, 30-minute window), the realistic peak cost is a rounding error on the daily total. The figure was doing rhetorical work to justify a lower SMS multiplier and should not have appeared without this context.

**What this means for the SMS budget decision:** The SMS cost question is not primarily about spike risk. It is about whether $17–24K/month in ongoing SMS costs is within budget. That is the question requiring sign-off.

**Calibration checkpoint (Month 2):** After 3–4 weeks of production data, we assess actual volume against planning basis.

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity decision — see note below | All engineers + stakeholders | 48 hours to decision, 1 week to implement |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**What the ">60% above plan" path actually produces:** By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed and cannot be replaced without scrapping 6–8 engineer-weeks of work. The 48-hour window produces a **capacity decision** (worker count, Redis tier, provider throughput limits) and a **scope decision** (which Month 3 features get deferred to absorb operational load). The scope decision requires stakeholder sign-off — it is not resolvable by the engineering team alone. The 48-hour window is for the engineering team to prepare options; stakeholder sign-off has a separate deadline of 1 week. If that sign-off cannot be obtained in 1 week, the default is horizontal scaling within existing architecture with no new feature work in Month 3. This default is documented now so it is not a surprise later.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**SMS budget dependency on E2's work plan:**

| SMS Decision Timeline | E2 Month 1–2 Adjustment |
|----------------------|------------------------|
| Approved by Week 2 | Proceed as planned; Twilio integration in Month 1 |
| Decision delayed past Week 2 | E2 deprioritizes Twilio; picks up additional APNs/FCM hardening or SendGrid integration work; Twilio scoped to Month 3 if approved later |
| SMS descoped entirely | E2 absorbs push reliability work; Section 3.4, SMS queue, and SMS-specific DLQ handling are removed; queue justification in Section 2.2 updated to reflect push/email-only isolation argument |

The team lead owns the Week 2 go/no-go call. If no decision has been received by end of Week 2, the team lead escalates and E2 proceeds under the "delayed" path.

**Ownership table for cross-cutting components:**

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Suppression logic (frequency caps, opt-out enforcement) | E3 | E1 |
| Suppression → queue boundary (what gets enqueued) | E3 + E1 | E4 |
| Dead-letter queue infrastructure, retry scheduler | E4 | E1, E2 |
| DLQ triage: push-specific failures (APNs/FCM) | E2 | E4 |
| DLQ triage: email-specific failures (SendGrid) | E2 | E4 |
| DLQ triage: SMS-specific failures (Twilio) | E2 | E4 |
| Preference cache implementation | E3 | E1 |
| Backpressure and rate limiting | E1 | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

**E3's role in the cross-cutting ownership:** E3 owns suppression logic and preference management — the decisions about what notifications are permitted to enter the queues at all. This is upstream of E1's queue implementation. The boundary is: E3's suppression layer produces a boolean (deliver / suppress) and a channel list; E1's queue layer consumes that output and routes accordingly. Neither engineer makes decisions in the other's domain. Disputes about what belongs in suppression logic (E3) versus routing logic (E1) escalate to a 30-minute sync.

**Rationale for DLQ triage split:** DLQ entries for push, email, and SMS require channel-specific knowledge to triage. Distinguishing an APNs invalid token (permanent failure, suppress the token) from a transient FCM 503 (retry) from a Twilio carrier rejection (investigate number validity) requires the person who built those integrations. E4 owns the DLQ *infrastructure*; E2 owns *triage and resolution* for channel-specific failures. This is reflected in runbooks, not just this table.

**Realistic estimate for queue infrastructure build time:** Setting up four queues and four DL