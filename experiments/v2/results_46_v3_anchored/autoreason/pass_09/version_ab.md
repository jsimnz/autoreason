# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Five items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy (OTP-on-every-login) is **$67.5K/month ongoing** — not a spike scenario. Decision deadline: Week 2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. The derivation in Section 2.4 estimates **180–900 opt-out violations per day** during the propagation window. Legal must assess whether this frequency constitutes a compliance problem under applicable regulations — not merely acknowledge that mitigations exist. The sign-off is on the number, not the methodology.

- **SendGrid enterprise contract (Section 1.1):** The planning basis requires 203 emails/sec at US-centric peak concentration. Standard SendGrid plans support ~27/sec. An enterprise contract supporting at least 270/sec sustained throughput is required **before launch** — this is a Day 1 requirement, not a scaling contingency. Procurement must begin Week 1.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A or Default B before this document is finalized. Default C (named escalation owner) is available only if a specific person is named before finalization — it cannot exist as a placeholder, as this creates a circular finalization dependency.

- **Broadcast notification policy (Section 1.1 and Section 6):** The system enforces a hard cap of 100K recipients per notification job. Push-to-all-MAU broadcasts require a separate architectural decision and are not supported by this design. A product owner must be named as the decision gate owner before launch; without a named owner, the cap is the policy.

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

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. These users cannot be reached by push or in-app, making email the primary retention channel for them. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

**Email volume sensitivity to DAU/MAU:**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Derived structural insight:** Email volume varies only 6% across DAU/MAU scenarios (3.15M to 3.35M) because the two components move in opposite directions — as engagement improves, activity email rises but re-engagement email falls by approximately the same amount. This holds because the re-engagement send rate (30% of lapsed users daily) is held constant across scenarios. Two implications follow:

First, a team expecting to reduce email infrastructure costs by improving retention is wrong: email costs are driven primarily by MAU count and send-frequency policy, not engagement rate. This constrains the product's cost structure independently of growth trajectory.

Second, if improved retention also changes re-engagement cadence policy — for example, a less aggressive cadence when the lapsed population shrinks — email volume could fall meaningfully. The flat-cost observation is a consequence of the 30% send-rate assumption, not a structural property of the product. Teams that intend to reduce email costs through retention improvement should model their actual re-engagement policy, not treat this table as a ceiling.

#### SendGrid Throughput: Day 1 Procurement Problem

**All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).**

```
Email peak rate = (3.25M emails/day × 0.90 peak concentration) ÷ 14,400 seconds = 203 emails/sec
```

Standard SendGrid plans (highest documented standard tier: ~100K emails/hour) support approximately 27/sec. The planning basis of 203/sec exceeds this by **7.5×**. This is not a high-scenario contingency — it is a Day 1 requirement.

**Required action:** An enterprise SendGrid contract supporting at least **270 emails/sec** sustained throughput (203/sec planning basis with 33% headroom) must be procured before launch. The 35%/30 scenario produces 210/sec — within the 270/sec contract target, so no renegotiation is required if that scenario materializes. If SendGrid enterprise pricing is unacceptable, the alternative is self-hosted email infrastructure (Postfix + SES relay), which trades procurement cost for operational complexity the team may not have capacity to absorb in the 6-month window.

**Owner:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. If not executed by end of Month 1, E1 escalates to stakeholders with a go/no-go on self-hosted email.

#### Peak Concentration Model

**All channels use a consistent concentration assumption within a scenario.** Channels are not assumed to peak independently.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

**Note on timezone distribution:** The 90% concentration assumption is conservative for a globally distributed app. A 4-timezone distribution with equal user distribution reduces peak concentration to roughly 50–60% — peaks overlap and fill the trough, making the infrastructure easier to manage, not harder. We plan for US-centric; global distribution is a favorable deviation.

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

SMS peak is negligible at any concentration level and is not a sizing driver.

#### Viral Spike Model: Sizing Logic Separated from Normal-Use Sizing

Two separate claims are made here. Conflating them produces circular sizing arguments.

**Claim 1: Worker throughput is sized for normal-use peak.** At 90% concentration (US-centric), combined peak is 2,552/sec. We size for **2,800/sec sustained worker throughput** — 10% headroom over the US-centric normal-use peak.

**Claim 2: Viral spikes are handled by queue backlog, with a defined maximum delay.** A viral spike is a temporary excess arrival rate above the normal-use peak. The drain calculation accounts for the fact that workers are already handling normal-use traffic during the spike.

```
Normal-use peak arrival rate (US-centric):           2,344/sec
Worker sustained throughput:                          2,800/sec
Excess capacity available during normal-use peak:       456/sec

Spike arrival rate (5% of daily volume in 10 min):
  = (37.5M × 0.05) ÷ 600 seconds                  = 3,125/sec

Total arrival rate during spike:
  = 3,125 (spike) + 2,344 (normal)                 = 5,469/sec

Excess arrival above worker capacity during spike:
  = 5,469 − 2,800                                  = 2,669/sec

Backlog accumulated over 10-minute spike:
  = 2,669/sec × 600 seconds                        = 1,601,400 notifications

Post-spike, excess capacity available to drain:
  = 2,800 − 2,344 (ongoing normal traffic)          = 456/sec

Drain time after spike ends:
  = 1,601,400 ÷ 456/sec                            ≈ 3,512 seconds (~58 minutes)

Maximum delay for notification enqueued at spike start:
  = 600 seconds (spike duration) + 3,512 seconds (drain) ≈ 69 minutes
```

**Maximum delay for a notification enqueued at spike start: ~69 minutes.** This is acceptable for digest and re-engagement email, and for non-urgent social notifications (likes, follows, comments) where users do not have real-time expectations. It is **not** acceptable for:
- SMS/OTP (dedicated queue, unaffected by design — see below)
- Direct messages where latency expectations are higher
- Any notification the product has explicitly classified as time-sensitive

**Implication for product:** The notification priority classification in Section 2.1 must include a real-time tier routed to a separate high-priority queue with dedicated workers. The 69-minute figure applies to the standard social queue only.

**SMS/OTP is unaffected by design.** The SMS queue has dedicated workers never shared with social volume. Those workers cannot be backlogged by social notification spikes regardless of spike magnitude.

#### Sustained Overload vs. Viral Spikes: A Critical Distinction

The viral-spike model above applies only to temporary excess arrival. The 35%/15 scenario (3,498/sec sustained peak) is a different problem: if normal-use peak exceeds worker throughput of 2,800/sec, the queue grows continuously during every peak window and never fully drains. This is not handled by queue backlog logic — it requires additional workers before it occurs.

**The 35%/15 scenario is handled by horizontal worker scaling, not by queue absorption.** Adding stateless worker processes requires no architectural change to the queue layer. Redis remains a single instance (memory constraints are not binding — see Redis Scaling Ceiling below). The constraint for email workers is SendGrid throughput, which is why the enterprise contract target (270/sec) is sized to cover the 35%/30 scenario without renegotiation.

The Month 2 calibration checkpoint (Section 1.1) is the mechanism for detecting trajectory toward this scenario with sufficient runway to add workers before it becomes a problem. The 4-month runway between checkpoint and the 35%/30 scenario boundary provides adequate time for this response.

#### Redis Scaling Ceiling: Queue Depth Derived from Batching Behavior

Workers process notifications in batches. The queue depth and memory estimates depend on batching behavior defined in Section 2.2. If those parameters change, these estimates must be recalculated.

**Section 2.2 defines:** Batch size of 100 notifications per dequeue operation; worker poll interval of 100ms; provider API latency (FCM/APNs HTTP/2) of ~150ms per batch call.

```
Per worker, per poll cycle:
  - Dequeue 100 notifications: ~5ms (Redis LMPOP)
  - Provider API call for batch: ~150ms
  - Total cycle time per worker: ~155ms
  - Notifications processed per worker per second: 100 ÷ 0.155 ≈ 645/sec

Workers required to sustain 2,800/sec: ⌈2,800 ÷ 645⌉ = 5 workers

Average queue depth under normal operation:
  = (arrival rate) × (average time in queue)
  = 2,344/sec × 0.155 sec (one worker cycle)
  ≈ 363 entries across all workers
```

**Redis working set:**

| Condition | Entries in queue | Memory at 150 bytes/entry |
|-----------|-----------------|--------------------------|
| Normal operation | ~363 | ~55 KB |
| Viral spike (peak backlog) | 1,601,400 | ~228 MB |
| 5× spike (model upper bound) | 8,007,000 | ~1.1 GB |

The viral spike backlog (228 MB) is within a standard Redis instance. The 5× spike model upper bound (1.1 GB) warrants a Redis instance with at least 2 GB allocated memory as the minimum specification. **The binding constraint at high throughput is provider throughput, not Redis memory.**

**What does require redesign:** A push-to-all-MAU broadcast (e.g., breaking news to 10M users simultaneously) breaks the per-channel queue model — not because of Redis memory, but because FCM and APNs impose per-project rate limits that worker count cannot overcome. That scenario requires a dedicated broadcast pipeline, is out of scope for this design, and is the subject of the broadcast notification policy sign-off item in the Executive Summary.

#### SMS Cost

| Scenario | Assumptions | SMS/day | Monthly cost |
|----------|-------------|---------|-------------|
| Conservative | login_rate=0.15, OTP_rate=0.05 | ~18.75K | ~$4.2K |
| Planning basis | login_rate=0.30, OTP_rate=0.10 | 75K | ~$17K |
| Aggressive | login_rate=0.40, OTP_rate=0.20 | 300K | ~$67.5K |

The aggressive scenario is what happens if the product ships OTP-on-every-login. It is an ongoing baseline under that authentication policy, not a spike. The budget sign-off question is: "Are we comfortable committing to SMS if authentication policy produces $67.5K/month in ongoing costs?" The one-day spike scenario is not the material risk.

#### Full Sensitivity Matrix

*All channels use consistent 90% concentration / 4-hour window (US-centric planning basis).*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|---------|----------------|-----------------|-----------|---------|----------------|-----------|---------|-------------|
| 15% | 8 | 12M | 3.15M | 45K | 750 | 197 | 2.8 | 950 |
| 15% | 15 | 22.5M | 3.15M | 45K | 1,406 | 197 | 2.8 | 1,606 |
| **25%** | **15** |