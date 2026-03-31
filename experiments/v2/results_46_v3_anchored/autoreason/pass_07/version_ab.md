# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly — the honest estimate of that overhead is in Section 2.2, and the architectural decision stands on its merits given that accounting. Push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation even without SMS in scope.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Section 5 describes the real on-call experience honestly: a single on-call rotation with a runbook covering the five most common failure patterns, owned and tested before Month 6. This system is not simple to operate; the runbook is the mitigation, not a claim that it is simple.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** The planning-basis estimate is ~$17–24K/month. The realistic worst-case under an aggressive authentication policy — OTP on every login — is $67.5K/month ongoing. This is not a spike scenario; it is what happens if the product ships a specific auth policy. The budget sign-off question is: "Are we comfortable committing to SMS if authentication policy produces $67.5K/month in ongoing costs?" Decision deadline: Week 2. E2's work plan consequences are described in Section 1.2 and are not passive — delay past Week 2 requires restructuring Month 1 deliverables.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. At planning-basis volume, the model estimates 150–750 opt-out violations per day during propagation delay. Legal must assess whether this frequency constitutes a compliance problem under applicable regulations — not merely acknowledge that mitigations exist. The number is in the document; the sign-off is on the number.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A, B, or C before this document is finalized. Default C requires naming the escalation owner in this document. **This document cannot be finalized with that bracket empty.**

- **QA approach (Section 7):** Included in full. Stakeholders are not being asked to sign off on a section they cannot read.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. Two inputs drive the volume model: notifications per active user per day, and the DAU/MAU ratio. Both are variables with explicit uncertainty ranges, not constants.

#### DAU/MAU Ratio Sensitivity

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

**Planning basis: 25% DAU/MAU (2.5M DAU).** Low case: 15% (1.5M DAU). High case: 35% (3.5M DAU). Benchmarks for notifications per active user per day: 8–15 for early-stage social apps, 30+ for high-engagement products. Planning basis: 15/user/day.

#### Channel Volume Uses Channel-Appropriate Denominators

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU-based, bounded | Re-engagement email dominates; derived below |
| SMS | Event-triggered subset of DAU | Auth events; derived below |

#### Email Volume: Derived, Not Asserted

Email notifications divide into two categories with different denominators:

**Activity emails** go to daily active users with email notifications enabled. Industry benchmark: 30–50% opt-in rate for social apps; we use 40%. At planning basis: 2.5M DAU × 0.40 = **1.0M activity emails/day.**

**Re-engagement and digest emails** go to the lapsed-user population — users who are MAU but not DAU, unreachable by push or in-app. At planning basis: 10M MAU − 2.5M DAU = 7.5M lapsed users. We send to 30% of lapsed users on any given day (consistent with weekly digest cadences staggered across the list): 7.5M × 0.30 = **2.25M re-engagement emails/day.**

**Total: ~3.25M emails/day at planning basis.** The two components move in opposite directions as DAU/MAU changes, which is why email volume is relatively flat across scenarios — this is now a derived result, not an assertion:

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

Email volume is moderately sensitive to product decisions about send frequency and opt-in defaults. If the re-engagement rate drops to 20%, total email falls to ~2.75M/day. We will validate actual send patterns at the Month 2 calibration checkpoint.

#### SMS Volume: Derived, Not Asserted

```
SMS/day = DAU × login_rate × OTP_rate
```

Where `login_rate` is the fraction of DAU triggering a new session daily, and `OTP_rate` is the fraction of logins requiring an OTP (risk-based authentication; Twilio's 2023 State of Customer Engagement Report cites 8–15% of logins triggering step-up auth).

Both constants carry explicit uncertainty with material cost consequences:

| Scenario | login_rate | OTP_rate | SMS/day | Monthly cost |
|----------|-----------|---------|---------|-------------|
| Conservative | 0.15 | 0.05 | ~18.75K | ~$4.2K |
| **Planning basis** | **0.30** | **0.10** | **75K** | **~$17K** |
| Aggressive | 0.40 | 0.20 | 300K | ~$67.5K |

**The aggressive scenario is not a spike — it is what happens if the product ships OTP-on-every-login.** Budget sign-off must acknowledge the aggressive scenario, not just the planning basis. The spike cost (~$1,600 incremental for a single 2× day) is not the material risk; the authentication policy decision is.

At planning basis (2.5M DAU), SMS peak is negligible: 75K/day ÷ 86,400 ≈ 0.87/sec average, ~1.7/sec peak. SMS is never the throughput constraint. The queue isolation argument for SMS rests on latency requirements — OTP delivery must not be delayed by push backpressure — not throughput.

#### Peak Throughput Model: Defended and Stress-Tested

**How peak rates are calculated:**

Social app notifications concentrate in morning and evening windows. We model peak load over a 2-hour sustained window per period, with two periods per day:

```
Peak rate = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

The 90% concentration assumption holds for a US-centric or single-timezone user base. It is a poor assumption for a globally distributed user base. We model three concentration scenarios explicitly:

| Concentration | Scenario | Push+In-app Peak/sec (planning basis, 37.5M/day) |
|--------------|----------|--------------------------------------------------|
| 90% in 4 hrs | US-only, two timezone bands | 2,344/sec |
| 70% in 4 hrs | Mixed US + one international timezone | 1,823/sec |
| 50% in 4 hrs | Global distribution, 4+ timezone bands | 1,302/sec |

**Viral spike scenario:** A viral content event can create a spike outside normal windows. We model this as a 10-minute window absorbing 5% of daily volume:

```
Viral spike peak = (37.5M × 0.05) ÷ 600 = 3,125/sec
```

This is the scenario that drives our sizing target. The spike is short (10–30 minutes) and can be absorbed by queue depth for social notifications. It is not acceptable for OTP/auth notifications — which is the queue isolation argument for SMS.

Email peak is modeled independently over a 4-hour batch window (ISP throttling considerations):
```
Email peak = (3.25M × 0.80) ÷ 14,400 ≈ 181/sec
```
Email peak does not coincide with push/in-app peak.

**Sizing target: 3,500/sec sustained throughput across all channels combined.** This covers:
- Normal use at 90% concentration (2,344/sec) with 49% headroom
- Normal use at 50% concentration (1,302/sec) with 169% headroom — global distribution makes the infrastructure easier, not harder
- Viral spike (3,125/sec) with 12% headroom, sufficient for a short spike absorbed by queue depth
- The 35%/15 scenario (3,467/sec) with marginal headroom requiring active monitoring

#### Redis Scaling Ceiling: Analyzed, Not Dismissed

The 35%/30 scenario (6,749/sec combined) is addressed explicitly rather than deferred.

**Redis sorted set operations** (ZADD, ZRANGEBYSCORE, ZREM) are O(log N). At 6,749/sec across four queues, each queue receives ~1,700 operations/sec. A single Redis instance handles 100K–200K operations/sec; sorted set operations are more expensive but well within range. **Redis is not the bottleneck at this scale.**

**Memory:** Each queued notification entry consumes approximately 150 bytes. At 6,749 enqueues/sec with a 30-second average queue depth, the working set is ~30MB. Even at 5× queue depth (150-second backlog during a spike), the working set is ~150MB — well within a single Redis instance's capacity.

**The actual 35%/30 constraint is worker throughput and external provider limits.** FCM's documented throughput limit is ~500K/min (~8,333/sec). APNs is similar. SendGrid's standard plans cap at 100K emails/hour (~27/sec), scaling to higher rates on enterprise contracts. **SendGrid throughput becomes the binding constraint at high email volumes, not Redis.**

**Horizontal scaling path for the 35%/30 scenario:**
- Redis: No change required.
- Push workers: Add stateless worker processes. No architectural change.
- Email workers: SendGrid plan upgrade or secondary ESP. This is a procurement decision.
- SMS workers: Negligible throughput; no change.

**The 35%/30 scenario does not require architectural redesign.** It requires worker count increases and a SendGrid plan negotiation. The Month 2 calibration checkpoint provides 4 months of runway to execute this if the trajectory points toward it.

**What does require redesign:** A push-to-all-MAU broadcast model (e.g., breaking news to 10M users simultaneously) breaks the per-channel queue model — not because of Redis, but because FCM and APNs impose per-project rate limits that cannot be exceeded regardless of worker count. That scenario requires a dedicated broadcast pipeline, is out of scope for this design, and is explicitly flagged as a product decision gate.

#### Full Sensitivity Matrix

*Push+In-app peak uses 90% concentration / 4-hour window (US-centric; see above for global adjustment). Email peak from derived model.*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App Peak/sec | Email Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|-----------|---------|---------------------|----------------|------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.15M | 45K | 750 | 175 | ~925 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.15M | 45K | 1,406 | 175 | ~1,581 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.25M** | **75K** | **2,344** | **181** | **~2,525** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.35M | 105K | 3,281 | 186 | ~3,467 |
| 35% (3.5M DAU) | 30 | 105M | 3.35M | 105K | 6,563 | 186 | ~6,749 |

*Sample derivation for planning basis: Push+In-app peak = (37.5M × 0.90) ÷ 14,400 = 2,344/sec. Email peak = (3.25M × 0.80) ÷ 14,400 = 181/sec. Combined = ~2,525/sec.*

#### Calibration Checkpoint (Month 2): Measurement Methodology

**Defined measurements:**

| Metric | Measurement point | Window | Tool |
|--------|------------------|--------|------|
| Push notifications dispatched | At worker dequeue, before provider call | 7-day trailing average | Prometheus counter |
| Push notifications delivered | At provider acknowledgment (FCM/APNs 200) | 7-day trailing average | Prometheus counter |
| Email dispatched | At SendGrid API call | 7-day trailing average | Prometheus counter |
| SMS dispatched | At Twilio API call | 7-day trailing average | Prometheus counter |
| In-app notifications written | At PostgreSQL insert | 7-day trailing average | Prometheus counter |
| Peak throughput | 99th percentile per-second rate | 7-day trailing | Prometheus histogram |

**The comparison unit is dispatched notifications per day measured at provider API call.** This maps directly to the volume model. Delivery confirmation rates are tracked separately as a quality metric.

**Who owns the measurement:** E4 owns instrumentation and produces the checkpoint report. E1 reviews for queue-level accuracy. The report is a one-page summary: actual vs. planned per channel, peak throughput vs. sizing target, recommendation (continue / scale workers / escalate).

**Decision gates:**

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Capacity + scope decision — see below | All engineers + stakeholders | 48 hrs for options; 1 week for decision |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

**What the ">60% above plan" path produces:** By Month 2, per-channel queues, Redis sorted sets, and PostgreSQL for in-app are committed architecture. The 48-hour window produces a capacity decision (worker count, Redis tier, provider throughput limits) and a scope decision (which Month 3 features get deferred). The scope decision requires stakeholder sign-off; it is not resolvable by the engineering team alone.

**Pre-approved escalation defaults — stakeholders must select one before this document is finalized:**

- **Default A:** Horizontal scaling only; all Month 3 feature work proceeds as planned; engineering team absorbs operational overhead. *Risk: team overextension.*
- **Default B:** Horizontal scaling; Month 3 feature work pauses until capacity is stable. *Risk: roadmap slips.*
- **Default C:** Escalate to **[name to be filled by stakeholder before document is finalized — this document cannot be fin