# Notification System Design — Revised v2
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Five items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy is $67.5K/month ongoing. Decision deadline: Week 2.

- **Opt-out compliance architecture (Section 2.4):** The preference cache staleness window creates legally non-negotiable TCPA/CAN-SPAM/GDPR exposure. This is not a sign-off item — it is a constraint. Section 2.4 describes the two compliant architectures. The cache-staleness-with-violations path is not available for selection regardless of stakeholder preference. Legal must confirm which compliant architecture is acceptable before finalization.

- **SendGrid enterprise contract (Section 1.1):** Required before launch. Procurement begins Week 1. E1 owns this contract; E2 supports the technical requirements documentation. If not executed by end of Month 1, E1 presents the self-hosted tradeoff — including the specific workstream that slips — to stakeholders within 48 hours.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A (throttle lower-priority queues) or Default B (shed load with dead-letter queue) before this document is finalized. Default C requires a specific named person before finalization and is not presented as a selectable option in this document until that person is named.

- **Broadcast notification policy (Section 1.1 and Section 6):** Hard cap of 100K recipients per job, enforced at the API layer, the worker layer, and the database write layer. A product owner must be named as the exception gate before launch.

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

#### Push and In-App Volume: Derivation

The prior version asserted 15 notifications/user/day without derivation. This section replaces that assertion with a bottoms-up estimate.

Push and in-app notifications for a social app originate from discrete trigger events. We model each event class separately.

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

Worker sizing uses 38.5M/day (35% DAU/MAU × 11/DAU) as the high-case planning input. Peak rate calculations below use this figure for the capacity-conservative scenario.

**What is not modeled here:** Notification volume is not static — it grows with social graph density. A user with 500 followers receives more likes per post than a user with 50. As the app matures and graphs densify, per-user notification rates will increase without DAU growth. This is a known unmodeled factor. The Month 2 calibration checkpoint (below) measures observed notifications/DAU/day against this planning basis and triggers a reassessment if the observed rate exceeds 13/DAU/day before Month 4.

---

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators.

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population. At planning basis: 10M − 2.5M = 7.5M lapsed users.

**The 30% re-engagement send rate: justification and sensitivity.**

The prior version used 30% without source or sensitivity analysis. This section corrects that.

The 30% figure represents the fraction of the lapsed user population receiving a re-engagement or digest email on any given day. For a weekly digest sent to the full lapsed population, the daily send rate is 1/7 = 14.3%. For a daily digest sent to all lapsed users, the rate is 100%. For a weekly digest plus a monthly re-engagement email staggered across the month, the blended daily rate is approximately 14.3% + (1/30) = 17.6%.

To reach 30%, the product must be running either: (a) a bi-weekly digest plus additional triggered re-engagement emails, or (b) a daily digest to a 30% subset of lapsed users. Neither is a default — both require explicit product decisions.

**The 30% rate is therefore a product policy assumption, not a neutral planning basis.** The actual rate depends on decisions that have not been finalized. The sensitivity analysis below shows why this matters:

| Re-engagement send rate | Re-engagement emails/day | Total email/day | Peak email/sec (90% concentration) |
|------------------------|--------------------------|-----------------|-------------------------------------|
| 10% (weekly digest only) | 750K | 1.75M | 109/sec |
| 20% (weekly + triggered) | 1.5M | 2.5M | 156/sec |
| 30% (planning basis) | 2.25M | 3.25M | 203/sec |
| 50% (daily digest, partial) | 3.75M | 4.75M | 297/sec |
| 100% (daily digest, all lapsed) | 7.5M | 8.5M | 531/sec |

The difference between a 10% and 50% re-engagement policy is nearly 3× in email volume and peak throughput. **This directly determines whether a standard SendGrid enterprise tier is sufficient or whether a higher-capacity contract is required.**

**Required action before finalization:** Product must define the re-engagement send policy. The SendGrid contract tier is sized to the selected policy, not to the 30% planning basis. Until product defines this, the contract negotiation cannot be completed. E1 must obtain a written re-engagement policy decision from product by end of Week 2.

**For the remainder of this document, 30% is used as the planning basis with the explicit caveat that it requires product confirmation.** The infrastructure is sized to handle the 50% scenario without contract renegotiation (270/sec contract target covers up to 297/sec at 50%, within 10% headroom).

---

#### SendGrid Throughput: Day 1 Procurement Problem

All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).

```
Email peak rate (30% basis) = (3.25M × 0.90) ÷ 14,400 = 203/sec
Email peak rate (50% basis) = (4.75M × 0.90) ÷ 14,400 = 297/sec
```

Standard SendGrid plans support approximately 27/sec. The planning basis exceeds this by 7.5×. This is a Day 1 requirement, not a scaling contingency.

**Required:** Enterprise SendGrid contract supporting at least **320/sec** sustained throughput. The prior version used 270/sec (30% basis + 33% headroom). This version sizes to the 50% re-engagement scenario plus 10% headroom (297/sec × 1.10 = 327/sec, rounded to 320/sec). This prevents contract renegotiation if product selects a more aggressive re-engagement policy.

**Ownership correction from prior version:** E1 owns the SendGrid enterprise contract. The prior version assigned this to E2 while making E1 accountable for the fallback consequence — a standard accountability gap. E2 supports by providing technical throughput requirements by end of Week 1. E1 signs the contract.

**Self-hosted fallback, honestly scoped:**

If the SendGrid contract is not executed by end of Month 1, the self-hosted path (Postfix cluster + Amazon SES relay) activates. The prior version described this as a "real, scoped option." It is not. It is a contingency that consumes real capacity.

- **Engineering cost:** 6–8 engineer-weeks (deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring, IP warm-up).
- **Team capacity impact:** At 4 engineers over 6 months (96 engineer-weeks total), 6–8 engineer-weeks is 6–8% of total team capacity — not trivial, but not catastrophic in isolation.
- **The actual problem:** The self-hosted path lands in Month 1–2, which is the same window as the core queue infrastructure build (Section 5, Month 1–2 milestones). One of these slips. The specific workstream that slips if the SendGrid contract fails is **the Month 2 in-app notification delivery milestone**. In-app delivery moves from Month 2 to Month 3. Push-only delivery launches in Month 2 as planned. This is the concrete tradeoff, not an open question.
- **This tradeoff must be presented to stakeholders by E1 within 48 hours of it becoming clear the Month 1 contract deadline will be missed** — not after the deadline passes.

---

#### Peak Concentration Model

All channels use a consistent concentration assumption within a scenario.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours (14,400 sec) | Single timezone band |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands |

**Combined peak throughput (planning basis: 27.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 1,719 | 203 | 4.7 | 1,927 |
| Mixed (70%) | 1,337 | 158 | 3.6 | 1,499 |
| Global (50%) | 955 | 113 | 2.6 | 1,071 |

High case (35% DAU/MAU, 11/DAU/day, 90% concentration): 2,406/sec combined. Worker sizing targets **2,650/sec sustained** — 10% headroom over the high-case peak.

---

#### Viral Spike Model: Honest Treatment

The prior version acknowledged that its planning basis spike model was not conservative, declined to size for the realistic worst case, and deferred to production monitoring. This section replaces that approach.

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days, not minutes. Monitoring identifies the problem; it does not prevent the delay. A 3+ hour notification delay during a viral moment is a product failure, not an acceptable operating condition.

**The right framing:** We cannot size workers for every possible spike without holding enormous idle capacity. The correct approach is to separate what workers handle from what the queue absorbs, and to define explicit SLAs by notification priority rather than pretending all notifications have the same delay tolerance.

**Revised spike model:**

Worker throughput target: 2,650/sec sustained (sized for high-case normal peak).

Spike arrival rate (5% of daily volume in 10 minutes, same planning basis):
```
= (27.5M × 0.05) ÷ 600 = 2,292/sec spike traffic
+ 1,719/sec normal traffic
= 4,011/sec total arrival during spike

Excess above worker capacity: 4,011 − 2,650 = 1,361/sec
Backlog at spike end: 1,361 × 600 = 816,600 notifications
Post-spike drain rate: 2,650 − 1,719 = 931/sec
Drain time: 816,600 ÷ 931 ≈ 877 seconds (~15 minutes)
Maximum delay (low-priority social): ~25 minutes
```

**Spike sensitivity with revised worker sizing:**

| Spike assumption | Backlog | Drain time | Max delay |
|-----------------|---------|-----------|-----------|
| 3% of daily in 15 min | 261,000 | ~5 min | ~20 min |
| 5% of daily in 10 min (planning basis) | 816,600 | ~15 min | ~25 min |
| 8% of daily in 5 min | 3,174,000 | ~57 min | ~62 min |
| 10% of daily in 5 min | 3,967,500 | ~71 min | ~76 min |

The 8%/5min scenario still produces an unacceptable delay for any notification type where timeliness matters. The correct response is not to add more workers — it is to ensure that high-priority notifications (OTPs, direct messages, account security alerts) are never in the same queue as the social volume that generates the spike.

**The architectural consequence:** High-priority queues have dedicated workers that are never shared with social notification volume. During a viral spike, social like/comment notifications queue up and drain over 15–62 minutes depending on spike severity. Direct messages and security notifications are unaffected because their workers are isolated. This is the per-channel queue architecture described in Section 2.1, and it is the primary mitigation for spike-induced delay — not worker autoscaling.

**What autoscaling handles:** The 8%/5min scenario produces a 57-minute drain time for low-priority social notifications even with isolated high-priority queues. If the product requires better than 60-minute delivery for social notifications during major spikes, autoscaling of social-channel workers is the mechanism. This requires Kubernetes HPA or equivalent,