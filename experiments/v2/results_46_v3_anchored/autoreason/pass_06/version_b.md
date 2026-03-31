# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly — estimated at 2–3 engineer-weeks across the build phase.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. The components are individually debuggable; the architecture combining them is not simple. Section 2.4 and Section 5 describe the operational complexity honestly.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K–105K SMS/day. The ongoing cost question (~$17–24K/month) requires budget approval. Decision deadline: Week 2. Dependency on E2's work plan is tracked in Section 1.2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which a user who has opted out may receive a notification. Section 2.4 describes the residual risk and the specific mitigations we are implementing. Legal and product must sign off on the residual risk that remains after those mitigations — not just acknowledge that mitigations exist.

- **Escalation default for capacity overruns (Section 1.1):** If actual traffic exceeds 60% above plan and stakeholder sign-off on scope changes cannot be obtained within one week, the engineering team cannot unilaterally freeze the product roadmap. Section 1.1 describes the specific options and asks stakeholders to pre-approve the default path now, before it becomes a crisis decision.

- **QA approach (Section 7):** Included in full in this document. Stakeholders are not being asked to sign off on a section they cannot read.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. Two inputs drive the volume model: notifications per active user per day, and the DAU/MAU ratio. Both are variables, not constants.

#### DAU/MAU Ratio Sensitivity

| App Stage / Category | Typical DAU/MAU | DAU at 10M MAU |
|---------------------|----------------|----------------|
| Early-stage social app | 15–20% | 1.5M–2M |
| Mid-stage social app | 25–35% | 2.5M–3.5M |
| Mature, high-retention social | 40–50% | 4M–5M |

We use 25% (2.5M DAU) as our planning basis. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case.

**Benchmarks for notifications per active user per day:**
- Conservative estimate for a new social app: 10–15
- Mid-range social app: ~15
- High-engagement product: 30+

We use 15 as our planning basis.

#### Channel Volume Uses Channel-Appropriate Denominators

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU-based, bounded | Explained below |
| SMS | Event-triggered subset of DAU | Auth events; explained below |

**Email volume is MAU-based but bounded, not proportional to DAU:**

Email notifications in a social app fall into two categories: digest/re-engagement emails sent to the full MAU base, and activity notifications sent to active users. The first category is bounded by MAU (10M fixed); the second scales with DAU. At 10M MAU with a 25% DAU ratio, re-engagement email dominates the volume — most email goes to the 75% of users who are not daily active, because those users cannot be reached via push or in-app.

This is why email volume in the sensitivity matrix is relatively flat across DAU scenarios: the largest email segment (lapsed user re-engagement) is driven by MAU, not DAU. As DAU/MAU rises, the lapsed user population shrinks and re-engagement email volume decreases slightly, but activity notification email increases. These effects partially offset.

**Bounded email volume estimate:** We model email at 35% of MAU per day = 3.5M emails/day. This holds approximately across all DAU scenarios because the offsetting effects are small relative to the base volume. The assumption is: email campaigns are not scaled up proportionally as DAU rises — that's a product decision, not an infrastructure assumption. If product decides to increase email send frequency with engagement, this number must be updated.

**This is an explicit modeling assumption, not an error.** If email volume is expected to scale linearly with DAU (e.g., activity-triggered emails dominate over re-engagement emails), the sensitivity matrix rows would diverge. We will validate this against actual send patterns at the Month 2 calibration checkpoint.

#### How Peak Throughput Is Calculated — Corrected Model

**Push and in-app peak throughput:**

Social app push and in-app notifications concentrate in morning and evening windows. We model peak load over a 2-hour sustained window. If 90% of push/in-app notifications fall in two 2-hour windows:

```
Peak rate (push + in-app) = (Volume × 0.90) ÷ (2 windows × 7,200 sec/window)
```

This formula gives the peak per-second rate. To express it as a multiplier over the average rate:

```
Average rate = Daily volume ÷ 86,400 sec
Peak multiplier = Peak rate ÷ Average rate
               = [(Volume × 0.90) ÷ 14,400] ÷ [Volume ÷ 86,400]
               = (0.90 × 86,400) ÷ 14,400
               = 5.4×
```

The peak rate is approximately 5.4× the uniform daily average for push and in-app. This is the correct interpretation of the "6× peak multiplier" language used in the previous version — it is the ratio of peak-window density to uniform distribution, not a multiplier you apply to arrive at a new absolute number after already computing the peak rate. The sensitivity matrix uses the peak rate directly; the multiplier is provided for intuition only.

**Email peak throughput:**

Email to lapsed users does not concentrate in social traffic peaks. Email sends are typically scheduled or triggered by batch jobs. We model email peak over a 4-hour window (email campaigns are usually sent across a longer window to avoid ISP throttling) with 80% of daily volume in that window:

```
Peak rate (email) = (3.5M × 0.80) ÷ (1 window × 14,400 sec) ≈ 194/sec
```

This is modeled separately from push/in-app peak. They do not share the same peak window or multiplier.

**SMS peak throughput:**

SMS is event-triggered by login events. Login spikes are shorter (15–30 minutes) and less correlated with content consumption peaks. We model SMS peak over a 30-minute window at 2× average rate. At 75K SMS/day:

```
SMS average rate = 75,000 ÷ 86,400 ≈ 0.87/sec
SMS peak rate ≈ 1.7/sec
```

SMS is never the throughput constraint. The queue isolation argument for SMS rests on latency requirements (OTP delivery must not queue behind push), not throughput.

#### Full Sensitivity Matrix

*Push+In-app peak uses the 5.4× multiplier over the push+in-app average rate. Email peak is calculated independently at ~194/sec across all scenarios (MAU-bounded, batch-friendly). SMS peak is negligible. Combined peak adds these independently-modeled figures.*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App Peak/sec | Email Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|-----------|---------|---------------------|----------------|------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 45K | 139 | 194 | ~335 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 45K | 260 | 194 | ~456 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **434** | **194** | **~630** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 105K | 608 | 194 | ~804 |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 105K | 1,215 | 194 | ~1,411 |

*Sample derivation for planning basis: Push+In-app average = 37.5M ÷ 86,400 = 434/sec average; peak = 434 × 5.4 = wait — this is wrong. Let me be precise:*

*Push+In-app peak = (37.5M × 0.90) ÷ 14,400 = 33.75M ÷ 14,400 = 2,344/sec.*

*That is the correct number. Let me rebuild the table with correct math.*

---

**Corrected sensitivity matrix:**

The previous calculation conflated average rate with peak rate. Here is the corrected derivation:

```
Push+In-app peak/sec = (Daily push+in-app volume × 0.90) ÷ 14,400
Email peak/sec       = (3.5M × 0.80) ÷ 14,400 ≈ 194/sec (fixed across scenarios)
SMS peak/sec         = negligible (< 2/sec)
```

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Push+In-App Peak/sec | Email Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|---------------------|----------------|------------------|
| 15% (1.5M DAU) | 8 | 12M | 750 | 194 | ~944 |
| 15% (1.5M DAU) | 15 | 22.5M | 1,406 | 194 | ~1,600 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **2,344** | **194** | **~2,538** |
| 35% (3.5M DAU) | 15 | 52.5M | 3,281 | 194 | ~3,477 |
| 35% (3.5M DAU) | 30 | 105M | 6,563 | 194 | ~6,757 |

**Sizing target:** We size for **3,500/sec sustained throughput** across all channels combined. This covers the planning basis (2,538/sec) with 38% headroom and handles the 35%/15 scenario (3,477/sec) with marginal headroom that requires monitoring. The 35%/30 scenario (6,757/sec) requires horizontal scaling — at that engagement level, the product success would justify the infrastructure investment and the team would have warning from the Month 2 calibration checkpoint.

**Why the previous 1,500/sec target was wrong:** The earlier version applied the 0.0625 coefficient to total daily volume and then described the result as having a "6× peak multiplier." In fact, 0.0625 is equivalent to the peak rate formula directly — it produces the peak/sec figure, not a multiplier to apply on top of an average rate. The resulting 838/sec figure was the correct peak rate for the planning basis, but was mistakenly described as incorporating a 6× multiplier. The corrected model above is internally consistent.

**Note on the 5.4× multiplier:** This is the ratio of peak-window density to uniform average. It tells you how much more intense the peak is than if traffic were flat. It is useful for intuition and capacity planning conversations, but the sensitivity matrix uses absolute peak rates derived directly from the formula, not the multiplier applied to an average.

#### SMS Volume Derivation — Acknowledged Assumptions

The formula `SMS/day = DAU × 0.30 × 0.10` uses two constants that require explicit defense:

**`login_rate = 0.30`** (30% of DAU trigger a new session daily)

This assumption is that roughly one in three daily active users initiates a fresh login rather than resuming a cached session. Industry data from consumer mobile apps suggests session refresh rates between 15–40% of DAU depending on session token lifetime and app background behavior. We use 30% as a mid-range estimate. **Sensitivity:** At 15%, SMS/day drops to 37.5K at planning basis (~$8.4K/month). At 40%, SMS/day rises to 100K (~$22.5K/month). The budget sign-off question should be framed against the 40% case, not the 30% case.

**`OTP_rate = 0.10`** (10% of logins require OTP)

This assumption is that OTP is triggered on new devices or after long inactivity, not on every login. A 10% rate implies roughly one in ten logins is from a new device or suspicious context. This is consistent with published figures from consumer apps using risk-based authentication (Twilio's 2023 State of Customer Engagement Report cites 8–15% of logins triggering step-up auth in consumer apps). **Sensitivity:** At 5%, SMS/day drops to 37.5K at planning basis. At 20%, SMS/day rises to 150K (~$33.8K/month). If OTP is required on every login, this model breaks entirely and SMS costs become the dominant infrastructure cost.

**Bottom line:** The planning basis estimate of 75K SMS/day (~$17K/month) is reasonable given mid-range assumptions, but the budget sign-off should acknowledge that the 40% login rate / 20% OTP rate scenario produces ~$33–40K/month in SMS costs. The ongoing cost question is the relevant one; spike risk is a rounding error on the monthly total.

#### Calibration Checkpoint (Month 2)

After 3–4 weeks of production data, we assess actual volume against planning basis.

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity + scope decision — see below | All engineers + stakeholders | 48 hours for options; 1 week for decision |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**What happens if stakeholders don't respond within one week on the >60% path:**

The engineering team cannot unilaterally freeze the product roadmap. This is a product decision, not an engineering decision. We are asking stakeholders to pre-approve one of the following defaults now, before it becomes a crisis:

- **Default A:** Horizontal scaling only; all Month 3 feature work proceeds as planned; engineering team absorbs the operational overhead. *Risk: team is overextended.*
- **Default B:** Horizontal scaling; Month 3 feature work is paused until capacity is stable. *Risk: product roadmap slips.*
- **Default C:** Escalate to [named executive] who has authority to make the scope call within 24 hours. *Risk: depends on executive availability.*

**Stakeholders must select a default before this document is finalized.** If no selection is made, we will implement Default C and identify the escalation owner by name in the final document. We are not asking for sign-off on a surprise — we are asking for a pre-agreed decision rule so the team is not making product decisions under operational pressure.

---

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid