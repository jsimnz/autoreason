# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy (OTP-on-every-login) is **$67.5K/month ongoing** — not a spike scenario. Decision deadline: Week 2, with E2 work-plan consequences described in Section 1.2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. The derivation in Section 2.4 estimates **180–900 opt-out violations per day** during the propagation window. Legal must assess whether this frequency constitutes a compliance problem under applicable regulations — not merely acknowledge that mitigations exist. The number is in the document; the sign-off is on the number.

- **SendGrid enterprise contract (Section 1.1):** The planning basis requires 181 emails/sec. Standard SendGrid plans support ~27/sec. An enterprise contract is required **before launch**, not as a contingency for high-growth scenarios. Procurement must begin Week 1. This is a Day 1 requirement, not a scaling concern.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A or Default B before this document is finalized. Default C (named escalation owner) can be reintroduced only if a specific person is named before finalization — it cannot exist as a placeholder bracket, as this creates a circular finalization dependency.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### DAU/MAU Ratio

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

Planning basis: 25% DAU/MAU (2.5M DAU). Low case: 15% (1.5M DAU). High case: 35% (3.5M DAU).

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators:

**Activity emails** go to daily active users with email notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. These users cannot be reached by push or in-app, making email the primary retention channel for them. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

**Email volume sensitivity to DAU/MAU:**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Derived structural insight:** Email volume is nearly flat across DAU/MAU scenarios because the two components move in opposite directions. As engagement improves, activity email rises but re-engagement email falls by approximately the same amount. A team expecting to reduce email infrastructure costs by improving retention is wrong: email costs are driven primarily by MAU count and send-frequency policy, not engagement rate. This constrains the product's cost structure independently of growth trajectory.

#### SendGrid Throughput: Day 1 Procurement Problem

The planning basis requires:

```
Email peak rate = (3.25M emails/day × 0.80 peak concentration) ÷ 14,400 seconds = 181 emails/sec
```

Standard SendGrid plans (highest documented standard tier: ~100K emails/hour) support approximately 27/sec. The planning basis of 181/sec exceeds this by **6.7×**. This is not a high-scenario contingency — it is a Day 1 requirement.

**Required action:** An enterprise SendGrid contract supporting at least 250 emails/sec sustained throughput (planning basis with 38% headroom) must be procured before launch. If SendGrid enterprise pricing is unacceptable, the alternative is self-hosted email infrastructure (Postfix + SES relay), which trades procurement cost for operational complexity the team may not have capacity to absorb in the 6-month window.

**Owner:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. If not executed by end of Month 1, E1 escalates to stakeholders with a go/no-go on self-hosted email.

#### Peak Concentration Model

**All channels use consistent concentration assumptions within a scenario.** Channels are not assumed to peak independently.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

**Note on timezone distribution:** The 90% concentration assumption is reasonable for a US-focused early-stage social app and conservative for a globally distributed one. A 4-timezone distribution with equal user distribution reduces peak concentration to roughly 50–60% in 4 hours — peaks overlap and fill the trough, making the infrastructure easier to manage, not harder. We plan for US-centric; global distribution is a favorable deviation.

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

SMS peak is negligible at any concentration. Email peak is calculated consistently with push peak.

#### Viral Spike Model: Sizing Logic Separated from Normal-Use Sizing

Two separate claims are made here. They were conflated in earlier drafts, producing a circular argument.

**Claim 1: Worker throughput is sized for normal-use peak.** At 90% concentration (US-centric), combined peak is 2,552/sec. We size for **2,800/sec sustained worker throughput** — 10% headroom over the US-centric normal-use peak.

**Claim 2: Viral spikes are handled by queue backlog, with a defined maximum delay.** A 10-minute viral spike absorbing 5% of daily volume produces:

```
Spike arrival rate = (37.5M × 0.05) ÷ 600 seconds = 3,125/sec
Excess arrival rate during spike = 3,125 − 2,800 = 325/sec
Total backlog accumulated = 325/sec × 600 seconds = 195,000 notifications
Drain time after spike ends = 195,000 ÷ 2,800/sec ≈ 70 seconds
```

**Maximum delay for a notification enqueued at spike start: ~11 minutes 10 seconds.** This is acceptable for social push and in-app notifications. It is explicitly **not** acceptable for SMS/OTP, which is why the SMS queue has dedicated workers never shared with social volume — those workers cannot be backlogged by social notification spikes regardless of spike magnitude.

**Sizing target: 2,800/sec sustained worker throughput.** Viral spikes produce a maximum 11-minute delay on social push/in-app. SMS/OTP is unaffected by design.

#### Redis Scaling Ceiling: Queue Depth Derived, Not Assumed

Average queue depth under normal operation, derived from worker behavior:

- Worker poll interval: 100ms
- Provider API latency (FCM/APNs HTTP/2): ~150ms planning estimate
- Workers handle one notification at a time at the worker level; batching occurs at the queue level (see Section 2.2)

```
Normal operation average queue depth ≈ 100ms + 150ms = 250ms
```

During a viral spike with 195,000 notifications backlogged and 2,800/sec drain rate:

```
Average wait for notification enqueued mid-spike = (195,000 ÷ 2) ÷ 2,800/sec ≈ 35 seconds
```

**Redis working set:**

| Condition | Entries in queue | Memory at 150 bytes/entry |
|-----------|-----------------|--------------------------|
| Normal operation | 2,800 × 0.25 sec = 700 | ~105 KB |
| Viral spike (peak backlog) | 195,000 | ~28 MB |
| 5× spike (model upper bound) | 975,000 | ~140 MB |

All scenarios are well within a single Redis instance's memory capacity. **The binding constraint at high throughput is not Redis — it is provider throughput.** FCM's documented limit is ~500K/min (~8,333/sec); SendGrid enterprise throughput is the procurement negotiation target (250/sec). For the 35%/30 scenario (6,780/sec combined), the horizontal scaling path is:

- **Redis:** No architectural change required. Single instance handles the load.
- **Push workers:** Add stateless worker processes. No architectural change.
- **Email workers:** SendGrid enterprise plan upgrade or secondary ESP. Procurement decision, not an architectural one.
- **SMS workers:** Negligible throughput; no change required.

The 35%/30 scenario does not require architectural redesign of the queue layer. It requires worker count increases and a SendGrid plan negotiation, with the Month 2 calibration checkpoint providing 4 months of runway to execute if trajectory warrants it.

**What does require redesign:** A push-to-all-MAU broadcast model (e.g., breaking news to 10M users simultaneously) breaks the per-channel queue model — not because of Redis, but because FCM and APNs impose per-project rate limits that worker count cannot overcome. That scenario requires a dedicated broadcast pipeline, is out of scope for this design, and is flagged as a product decision gate.

#### SMS Cost

| Scenario | Assumptions | SMS/day | Monthly cost |
|----------|-------------|---------|-------------|
| Conservative | login_rate=0.15, OTP_rate=0.05 | ~18.75K | ~$4.2K |
| Planning basis | login_rate=0.30, OTP_rate=0.10 | 75K | ~$17K |
| Aggressive | login_rate=0.40, OTP_rate=0.20 | 300K | ~$67.5K |

The aggressive scenario is what happens if the product ships OTP-on-every-login. It is an ongoing baseline under that authentication policy, not a spike. The budget sign-off question is: "Are we comfortable committing to SMS if authentication policy produces $67.5K/month in ongoing costs?" The one-day spike scenario is not the material risk.

#### Full Sensitivity Matrix

*All channels use consistent 90% concentration / 4-hour window (US-centric). All four channels included.*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|---------|----------------|-----------------|-----------|---------|----------------|-----------|---------|-------------|
| 15% | 8 | 12M | 3.15M | 45K | 750 | 197 | 2.8 | 950 |
| 15% | 15 | 22.5M | 3.15M | 45K | 1,406 | 197 | 2.8 | 1,606 |
| **25%** | **15** | **37.5M** | **3.25M** | **75K** | **2,344** | **203** | **4.7** | **2,552** |
| 35% | 15 | 52.5M | 3.35M | 105K | 3,281 | 210 | 6.6 | 3,498 |
| 35% | 30 | 105M | 3.35M | 105K | 6,563 | 210 | 6.6 | 6,780 |

**Sizing target: 2,800/sec sustained worker throughput.** The 35%/15 scenario (3,498/sec) is handled by viral-spike queue logic with an approximately 14-minute maximum delay. The 35%/30 scenario is handled by horizontal worker scaling and SendGrid plan upgrade.

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

**The comparison unit is dispatched notifications per day measured at provider API call.** Delivery confirmation rates are tracked separately as a quality metric, not as the volume comparison unit.

**Owner:** E4 owns the instrumentation and produces the checkpoint report. E1 reviews for queue-level accuracy. Output: a one-page summary of actual vs. planned volume per channel, peak throughput vs. sizing target, and a recommendation.

**Decision gates:**

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week |
| 30–60% above plan | Add workers (horizontal, no redesign) | E1 + E4 | Before Month 3 |
| >60% above plan | Capacity + scope decision — see escalation defaults | All + stakeholders | 48 hrs for options; 1 week for decision |
| >30% below plan | Reduce workers, update cost projections | E4 | Within 1 week |

**Pre-approved escalation defaults (stakeholders must select one before this document is finalized):**

- **Default A:** Horizontal scaling only; all Month 3 feature work proceeds; engineering absorbs operational overhead. *Risk: team overextension if scaling is sustained.*
- **Default B:** Horizontal scaling; Month 3 feature work pauses until capacity is stable. *Risk: roadmap slips by up to 4 weeks.*
- **Default C:** Named escalation owner with authority to make the scope call within 24 hours.