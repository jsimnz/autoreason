# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 27.5–49M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. High-priority queues have dedicated workers that are never shared with social volume. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working push-only system in Month 2, in-app added Month 3, full channel parity by Month 5, hardened in Month 6 against the criteria defined in Section 7.

**Five items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy (OTP-on-every-login) is $67.5K/month ongoing — not a spike scenario. Decision deadline: Week 2.

- **Opt-out compliance architecture (Section 2.4):** The preference cache staleness window creates legally non-negotiable TCPA/CAN-SPAM/GDPR exposure. This is not a threshold question — it is a constraint. The cache-staleness-with-violations path is not available for selection regardless of stakeholder preference. Section 2.4 describes the two compliant architectures. Legal must confirm which is acceptable before finalization.

- **SendGrid enterprise contract (Section 1.1):** Required before launch. Procurement begins Week 1. E1 owns the contract; E2 delivers technical throughput requirements by end of Week 1. If not executed by end of Month 1, E1 presents the concrete tradeoff — in-app delivery milestone slips from Month 2 to Month 3 — to stakeholders within 48 hours.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A (throttle lower-priority queues) or Default B (shed load with dead-letter queue) before finalization. Default C (named escalation owner with discretion) requires a specific named person before finalization and does not appear as a selectable option until that person is named.

- **Broadcast notification policy (Section 1.1 and Section 6):** Hard cap of 100K recipients per job, enforced at the API layer, the worker layer, and the database write layer. A product owner must be named as the exception gate before launch; without a named owner, the cap is the policy with no exceptions.

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

---

#### Push and In-App Volume: Bottoms-Up Derivation

Push and in-app notifications originate from discrete trigger events. We model each event class separately rather than asserting a per-user rate.

**Event classes and per-DAU rates:**

| Event Class | Trigger | Estimated Events/DAU/Day | Notes |
|-------------|---------|--------------------------|-------|
| Likes on posts | User posts content; others react | 3–8 | Batched after first delivery; see Section 2.2 |
| Comments on posts | Others comment on user content | 1–4 | Batched similarly |
| New followers/friend requests | Social graph growth | 0.5–2 | Lower bound at maturity |
| Direct messages received | Peer-to-peer messaging | 2–6 | Highly variable; power users skew high |
| Mentions and tags | Others reference the user | 0.5–2 | |
| System/product notifications | Feature announcements, nudges | 0.5–1 | Capped by product policy |

**Raw event total per DAU per day:** 7.5–23 events. After batching (Section 2.2 reduces like/comment storms to single notifications), effective delivered notifications: **8–14/DAU/day**.

Planning basis: **11 notifications/DAU/day** (midpoint of 8–14 range).

```
Push + In-App volume = 2.5M DAU × 11 = 27.5M/day (planning basis)
```

**Sensitivity to DAU/MAU and notifications/DAU:**

| DAU/MAU | DAU | 8/DAU/day | 11/DAU/day | 14/DAU/day |
|---------|-----|-----------|------------|------------|
| 15% | 1.5M | 12M | 16.5M | 21M |
| 25% | 2.5M | 20M | 27.5M | 35M |
| 35% | 3.5M | 28M | 38.5M | 49M |

Worker sizing uses 38.5M/day (35% DAU/MAU × 11/DAU) as the capacity-conservative high-case input.

**Known unmodeled factor:** Notification volume grows with social graph density independent of DAU growth. A user with 500 followers receives more likes per post than a user with 50. As the app matures and graphs densify, per-user notification rates will increase without a corresponding increase in DAU. The Month 2 calibration checkpoint (below) measures observed notifications/DAU/day against the 11/day planning basis and triggers reassessment if the observed rate exceeds 13/DAU/day before Month 4.

---

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators.

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have these enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. These users cannot be reached by push or in-app, making email the primary retention channel for them. At planning basis: 10M − 2.5M = 7.5M lapsed users.

**The re-engagement send rate is a product policy assumption, not a neutral planning basis.** The 30% figure used below requires explicit justification:

- Weekly digest to all lapsed users: 1/7 = 14.3% daily send rate
- Daily digest to all lapsed users: 100%
- Weekly digest plus monthly re-engagement staggered: ~17.6%
- Bi-weekly digest plus additional triggered emails: ~30%

To reach 30%, the product must be running bi-weekly digests plus triggered re-engagement, or equivalent. This is not a default — it requires an explicit product decision. **Product must define the re-engagement send policy before the SendGrid contract can be finalized. E1 must obtain a written policy decision from product by end of Week 2.**

**Email volume sensitivity to re-engagement send rate:**

| Re-engagement send rate | Re-engagement emails/day | Total email/day | Peak email/sec (90% concentration) |
|------------------------|--------------------------|-----------------|-------------------------------------|
| 10% (weekly digest only) | 750K | 1.75M | 109/sec |
| 20% (weekly + triggered) | 1.5M | 2.5M | 156/sec |
| 30% (planning basis) | 2.25M | 3.25M | 203/sec |
| 50% (daily digest, partial) | 3.75M | 4.75M | 297/sec |
| 100% (daily digest, all lapsed) | 7.5M | 8.5M | 531/sec |

The difference between a 10% and 50% re-engagement policy is nearly 3× in email volume and peak throughput. This directly determines the required SendGrid contract tier.

**Email volume sensitivity to DAU/MAU (at 30% re-engagement rate):**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

Email volume varies only 6% across DAU/MAU scenarios because the two components move in opposite directions under a fixed re-engagement send rate. This near-flatness is a consequence of holding that rate constant — it is not a structural property of the product and does not generalize to other send rate assumptions.

**For the remainder of this document, 30% is used as the planning basis with the explicit caveat that it requires product confirmation.**

---

#### SendGrid Throughput: Day 1 Procurement Problem

All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).

```
Email peak rate (30% basis) = (3.25M × 0.90) ÷ 14,400 = 203/sec
Email peak rate (50% basis) = (4.75M × 0.90) ÷ 14,400 = 297/sec
```

Standard SendGrid plans support approximately 27/sec. The 30% planning basis exceeds this by 7.5×. This is a Day 1 requirement, not a scaling contingency.

**Required:** Enterprise SendGrid contract supporting at least **320/sec** sustained throughput. This is sized to the 50% re-engagement scenario plus 10% headroom (297/sec × 1.10 = 327/sec, rounded to 320/sec), preventing contract renegotiation if product selects a more aggressive re-engagement policy.

**Ownership:** E1 owns the SendGrid enterprise contract. E2 delivers technical throughput requirements documentation by end of Week 1. E1 signs the contract by end of Month 1.

**Self-hosted fallback — concrete scope:**

If the SendGrid contract is not executed by end of Month 1, the self-hosted path (Postfix cluster + Amazon SES relay) activates. This is a contingency with real capacity consequences, not a preferred fallback.

- **Infrastructure:** 3 Postfix MTA instances behind a load balancer; SES relay for deliverability; dedicated IP warm-up over 4 weeks.
- **Engineering cost:** 6–8 engineer-weeks (deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring, IP warm-up). At 4 engineers over 6 months (96 engineer-weeks total), this is 6–8% of total team capacity.
- **The concrete tradeoff:** The self-hosted path lands in Month 1–2, the same window as the core queue infrastructure build. The specific workstream that slips is the **Month 2 in-app notification delivery milestone**. In-app delivery moves from Month 2 to Month 3. Push-only delivery launches in Month 2 as planned.
- **This tradeoff must be presented to stakeholders by E1 within 48 hours of it becoming clear the Month 1 contract deadline will be missed** — not after the deadline passes.
- **Ongoing cost comparison:** SES pricing at ~$0.10/1K emails ≈ $325/day at planning basis. SendGrid enterprise typically $0.001–0.002/email at volume = $3,250–6,500/day. SES relay is materially cheaper but requires the team to own deliverability operations that SendGrid handles.

---

#### Peak Concentration Model and International Users

All channels use a consistent concentration assumption within a scenario.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

The 90% concentration assumption produces the highest peak rate and therefore the most conservative infrastructure sizing. It is used for capacity planning, not as an architectural recommendation.

**On international users:** A US-only architecture at 10M MAU carries risks beyond peak rate calculations:

- **Latency:** Notification delivery from US-only infrastructure adds 150–300ms round-trip for users in Europe, Asia, and South America. Perceptible for in-app notifications.
- **Data residency:** GDPR (EU), PDPA (Thailand/Singapore), LGPD (Brazil), and similar regulations impose requirements on where user data is processed and stored. A US-only architecture may not be compliant for EU users at any MAU level. This is a legal exposure, not a performance tradeoff.
- **SMS compliance:** TCPA applies to US numbers; different opt-in and content rules apply in the EU, UK, India, and other markets. The SMS architecture must account for the user's country, not just the sending infrastructure's location.

A regional deployment decision (at minimum, EU and APAC regions) must be made before launch, independent of this notification system design. That decision is out of scope here but is flagged as a compliance prerequisite for non-US user populations.

**Combined peak throughput (planning basis: 27.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 1,719 | 203 | 4.7 | 1,927 |
| Mixed (70%) | 1,337 | 158 | 3.6 | 1,499 |
| Global (50%) | 955 | 113 | 2.6 | 1,071 |

High case (35% DAU/MAU, 11/DAU/day, 90% concentration): 2,406/sec combined. Worker sizing targets **2,650/sec sustained** — 10% headroom over the high-case peak.

---

#### Viral Spike Model

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days. Monitoring identifies the problem; it does not prevent the delay. The primary mitigation for spike-induced delay is architectural — isolated high-priority queues — not worker autoscaling.

**The correct framing:** We cannot size workers for every possible spike without holding enormous idle capacity. The correct approach is to separate what workers handle from what the queue absorbs, and to define explicit SLAs by notification priority. High-priority notifications (OTPs, direct messages, account security alerts) have dedicated workers that are never shared with social notification volume. During a viral spike, social like/comment notifications queue up and drain over minutes. Direct messages and security notifications are unaffected.

**Spike arrival model (5% of daily volume in 10 minutes):**

This assumption is derived from public incident reports for social apps where short-duration spikes have ranged from 3–8% of daily volume over 5–15 minutes. We use 5%/10min as a mid-range estimate. This figure is not validated for this specific app.

```
Worker throughput target:                              2,650/sec
Normal-use peak arrival rate (US-centric high case):   2,406/sec
Excess capacity available during normal-use peak:        244/sec

Spike arrival rate (5% of 27.5M in 10 min):
  = (27.5M × 0.05) ÷ 600                           = 2,292/sec

Total arrival rate during spike:
  = 2,292 (spike) + 1,719 (normal planning basis)   = 4,011/sec

Excess arrival above worker capacity during spike:
  = 4,011 − 2,650                                   = 1,361/sec

Backlog accumulated