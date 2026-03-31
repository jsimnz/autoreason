# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly — estimated at 2–3 engineer-weeks across the build phase. This justification holds even without SMS: push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation on their own.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am. The components are individually well-understood; the architecture combining them carries operational complexity we describe honestly in Section 5.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Volume estimates assume ~75K–105K SMS/day depending on DAU. The relevant question is ongoing cost (~$17–24K/month), not spike risk — a 2× spike for a full day adds at most ~$1,600 above the daily baseline. The architectural commitment to an isolated SMS queue depends on SMS being in scope. If the decision is delayed past Week 2, E2's work plan must be restructured — this is not a passive gate. Decision deadline: Week 2. The dependency is tracked explicitly in Section 1.2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which a user who has opted out may receive a notification. We have a mitigation plan, but there is a structural race condition that cannot be fully eliminated with write-through caching. Legal and product must sign off on the residual risk after mitigations — not just acknowledge that mitigations exist.

- **Escalation default for capacity overruns (Section 1.1):** If actual traffic exceeds 60% above plan and stakeholder sign-off on scope changes cannot be obtained within one week, the engineering team cannot unilaterally freeze the product roadmap. Stakeholders must pre-approve a default path now, before it becomes a crisis decision. The options are enumerated in Section 1.1.

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

We use 25% (2.5M DAU) as our planning basis. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case. Benchmarks for notifications per active user per day: 10–15 for a new social app, ~15 for mid-range, 30+ for high-engagement products. We use 15 as our planning basis.

#### Channel Volume Uses Channel-Appropriate Denominators

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU-based, bounded | Re-engagement email dominates; explained below |
| SMS | Event-triggered subset of DAU | Auth events; explained below |

**Email volume is MAU-based but bounded, not proportional to DAU.** Email notifications fall into two categories: digest/re-engagement emails sent to the full MAU base, and activity notifications sent to active users. The re-engagement segment dominates volume — most email goes to the 75% of users who are not daily active, because those users cannot be reached via push or in-app. As DAU/MAU rises, the lapsed user population shrinks and re-engagement email decreases slightly, but activity notification email increases. These effects partially offset, which is why email volume is relatively flat across DAU scenarios.

**Bounded email volume estimate:** 35% of MAU per day = 3.5M emails/day across all scenarios. This is an explicit modeling assumption: email campaigns are not scaled up proportionally as DAU rises. If product decides to increase email send frequency with engagement, this number must be updated. We will validate against actual send patterns at the Month 2 calibration checkpoint.

**SMS volume is derived, not asserted:**

```
SMS/day = DAU × login_rate × OTP_rate
        = DAU × 0.30 × 0.10
        = DAU × 0.03
```

Where `login_rate` (0.30) is the fraction of DAU triggering a new session daily, and `OTP_rate` (0.10) is the fraction of logins requiring an OTP. These constants carry explicit uncertainty:

- **`login_rate = 0.30`:** Industry data from consumer mobile apps suggests session refresh rates of 15–40% of DAU depending on session token lifetime. At 15%, SMS/day drops to 37.5K at planning basis (~$8.4K/month). At 40%, SMS/day rises to 100K (~$22.5K/month). The budget sign-off question should be framed against the 40% case.
- **`OTP_rate = 0.10`:** Consistent with published figures from consumer apps using risk-based authentication (Twilio's 2023 State of Customer Engagement Report cites 8–15% of logins triggering step-up auth). At 5%, SMS/day drops to 37.5K at planning basis. At 20%, SMS/day rises to 150K (~$33.8K/month). If OTP is required on every login, this model breaks entirely and SMS costs become the dominant infrastructure cost line.

At planning basis (2.5M DAU), this yields 75K SMS/day. The budget sign-off should acknowledge that the 40% login rate / 20% OTP rate scenario produces ~$33–40K/month in ongoing SMS costs.

#### How Peak Throughput Is Calculated

**Push and in-app:** Social app notifications concentrate in morning and evening windows. We model peak load over a 2-hour sustained window. If 90% of push/in-app notifications fall across two 2-hour windows:

```
Peak rate (push + in-app) = (Daily volume × 0.90) ÷ (2 windows × 7,200 sec/window)
                          = Daily volume × 0.0625
```

This is the peak per-second rate — not a multiplier to apply on top of an average rate. For intuition: it is approximately equivalent to a **5.4× multiplier** over the uniform daily average, sustained for 2 hours. The sensitivity matrix uses absolute peak rates derived directly from this formula.

**Email:** Email to lapsed users does not concentrate in social traffic peaks. We model email peak over a 4-hour window (ISP throttling considerations) with 80% of daily volume in that window:

```
Peak rate (email) = (3.5M × 0.80) ÷ 14,400 ≈ 194/sec
```

This is modeled independently from push/in-app peak. They do not share the same peak window.

**SMS:** Login spikes are shorter (15–30 minutes) and less correlated with content consumption peaks. We model SMS peak over a 30-minute window at 2× average rate. At 75K SMS/day:

```
SMS average rate = 75,000 ÷ 86,400 ≈ 0.87/sec
SMS peak rate ≈ 1.7/sec
```

SMS is never the throughput constraint. The queue isolation argument for SMS rests on latency requirements, not throughput.

#### Full Sensitivity Matrix

*Push+In-app peak uses the formula above. Email peak is fixed at ~194/sec (MAU-bounded, batch-scheduled). SMS peak is negligible (<2/sec).*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App Peak/sec | Email Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|-----------|---------|---------------------|----------------|------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.5M | 45K | 750 | 194 | ~944 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.5M | 45K | 1,406 | 194 | ~1,600 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **2,344** | **194** | **~2,538** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 105K | 3,281 | 194 | ~3,477 |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 105K | 6,563 | 194 | ~6,757 |

*Sample derivation for planning basis: Push+In-app peak = (37.5M × 0.90) ÷ 14,400 = 2,344/sec. Email peak = (3.5M × 0.80) ÷ 14,400 = 194/sec. Combined = ~2,538/sec.*

**Sizing target:** We size for **3,500/sec sustained throughput** across all channels combined. This covers the planning basis (2,538/sec) with 38% headroom and handles the 35%/15 scenario (3,477/sec) with marginal headroom requiring active monitoring. The 35%/30 scenario (6,757/sec) requires horizontal scaling — at that engagement level, the product success would justify the infrastructure investment, and the Month 2 calibration checkpoint provides early warning.

**Headroom is measured against the highest scenario we are explicitly designing for** (35%/15 at 3,477/sec). The 35%/30 scenario is acknowledged as requiring redesign, not covered by headroom.

#### Calibration Checkpoint (Month 2)

After 3–4 weeks of production data, we assess actual volume against planning basis.

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity + scope decision — see below | All engineers + stakeholders | 48 hours for options; 1 week for decision |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**What the ">60% above plan" path produces:** By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed architecture — they cannot be replaced without scrapping 6–8 engineer-weeks of work. The 48-hour window produces a capacity decision (worker count, Redis tier, provider throughput limits) and a scope decision (which Month 3 features get deferred). The scope decision requires stakeholder sign-off; it is not resolvable by the engineering team alone.

Stakeholders must pre-approve one of the following defaults now, before it becomes a crisis:

- **Default A:** Horizontal scaling only; all Month 3 feature work proceeds as planned; engineering team absorbs the operational overhead. *Risk: team is overextended.*
- **Default B:** Horizontal scaling; Month 3 feature work is paused until capacity is stable. *Risk: product roadmap slips.*
- **Default C:** Escalate to [named executive] who has authority to make the scope call within 24 hours. *Risk: depends on executive availability.*

**Stakeholders must select a default before this document is finalized.** If no selection is made, we implement Default C and identify the escalation owner by name in the final document.

---

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
| SMS descoped entirely | E2 absorbs push reliability work; Section 3.4, SMS queue, and SMS-specific DLQ handling are removed; queue isolation justification in Section 2.2 updated to reflect push/email-only argument |

The team lead owns the Week 2 go/no-go call. If no decision has been received by end of Week 2, the team lead escalates and E2 proceeds under the "delayed" path.

**Ownership table for cross-cutting components:**

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Suppression logic (frequency caps, opt-out enforcement) | E3 | E1 |
| Suppression → queue boundary | E3 + E1 | E4 |
| Dead-letter queue infrastructure, retry scheduler | E4 | E1, E2 |
| DLQ triage: push-specific failures (APNs/FCM) | E2 | E4 |
| DLQ triage: email-specific failures (SendGrid) | E2 | E4 |
| DLQ triage: SMS-specific failures (Twilio) | E2 | E4 |
| Preference cache implementation | E3 | E1 |
| Backpressure and rate limiting | E1 | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

**Ownership principles:** E3 owns suppression logic — the decisions about what notifications are permitted to enter queues at all. The boundary is explicit: E3's suppression layer produces a boolean (deliver/suppress) and a channel list; E1's queue layer consumes that output and routes accordingly. Neither engineer makes decisions in the other's domain.

E4 owns DLQ *infrastructure*; E2 owns *triage and resolution* for channel-specific failures. Distinguishing an APNs invalid token (permanent failure, suppress the token) from a transient FCM 503 (retry) from a Twilio carrier rejection (investigate number validity) requires the person who built those integrations. This split is reflected in runbooks, not just this table.

The principle: E1 owns the path that works; E4 owns the path that fails at the infrastructure level; E2 owns the path that fails at the provider level. Disputes escalate to a 30-minute sync, not a Slack thread.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  ├─ Preference check   (Redis cache — staleness model in Section 2.4)
  ├─ Suppression check  (frequency caps, do-not-contact lists)
  ├─ Priority assignment
  └─ Channel selection
     │
     ├──→ [Push Queue]    (Redis Sorted Set, scored by priority+time) → Push