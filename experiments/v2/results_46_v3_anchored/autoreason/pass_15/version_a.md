# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

### Five Items Requiring Explicit Sign-Off Before This Design Is Finalized

| Item | Section | Decision Deadline | Owner |
|------|---------|-------------------|-------|
| SMS budget | §1.1 | Week 2 | E1 |
| Opt-out compliance architecture | §2.4 | Before finalization | Legal + E1 |
| SendGrid enterprise contract | §1.1 | End of Month 1 | E1 |
| Escalation default for capacity overruns | §1.1 | Before finalization | Stakeholders |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product |

**On the compliance item specifically:** The preference cache staleness window creates potential TCPA/CAN-SPAM/GDPR exposure. Section 2.4 presents two compliant architectures. The cache-with-staleness path is not available for selection — that determination requires a legal opinion, not a design document assertion. Legal must confirm which compliant architecture is acceptable before finalization.

**A note on internal consistency:** All calculations in this document use a single named scenario table. The spike model, worker sizing, and peak throughput calculations all use the same scenario inputs. Where prior versions used different DAU assumptions in different sections, this version resolves those inconsistencies explicitly. Any calculation that uses inputs from different scenarios is a document defect to be corrected.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### Scenario Framework

All calculations use one of three named scenarios:

| Scenario | DAU/MAU | DAU | Usage in This Document |
|----------|---------|-----|----------------------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | **Worker sizing and spike calculations throughout** |

**Worker sizing uses the High scenario throughout.** The prior versions inconsistently applied Base scenario inputs to spike calculations while using High scenario inputs for worker sizing — those numbers were not internally consistent and have been corrected here.

---

#### Push and In-App Volume

Push and in-app notifications originate from discrete trigger events modeled separately.

**Event classes and per-DAU rates:**

| Event Class | Trigger | Estimated Events/DAU/Day | Notes |
|-------------|---------|--------------------------|-------|
| Likes on posts | User posts content; others react | 3–8 | Batched after first delivery; see §2.2 |
| Comments on posts | Others comment on user content | 1–4 | Batched similarly |
| New followers/friend requests | Social graph growth | 0.5–2 | Lower bound at maturity |
| Direct messages received | Peer-to-peer messaging | 2–6 | Highly variable; power users skew high |
| Mentions and tags | Others reference the user | 0.5–2 | |
| System/product notifications | Feature announcements, nudges | 0.5–1 | Capped by product policy |

Raw event total per DAU per day: 7.5–23 events. After batching (§2.2 reduces like/comment storms to single notifications), effective delivered notifications: **8–14/DAU/day**.

Planning basis: **11 notifications/DAU/day** (midpoint of 8–14 range).

**Push + In-App volume by scenario:**

| Scenario | DAU | 8/DAU/day | 11/DAU/day | 14/DAU/day |
|----------|-----|-----------|------------|------------|
| Low | 1.5M | 12M | 16.5M | 21M |
| Base | 2.5M | 20M | **27.5M** | 35M |
| High | 3.5M | 28M | **38.5M** | 49M |

**Worker sizing input: 38.5M/day (High scenario, 11/DAU/day).** All spike calculations use this same figure.

#### The Unmodeled Graph Densification Factor

As the social graph densifies, per-user notification rates increase without DAU growth. A user with 500 followers receives more likes per post than a user with 50. This is a known unmodeled factor.

Worker sizing targets 38.5M/day with **25% headroom**, yielding an effective capacity ceiling of **48.1M/day** (approximately 13.8/DAU/day at High DAU). The reassessment trigger fires at **13/DAU/day** — corresponding to 45.5M/day at High DAU — leaving 2.6M/day (5.7%) of remaining headroom when reassessment begins. The system is not already saturated when the trigger fires.

**Reassessment process (not just a monitoring alert):**

If observed notifications/DAU/day exceeds 13 before Month 4, the following process activates within 5 business days:

1. **E3** (infrastructure lead) produces a revised capacity projection based on observed trajectory, with a 90-day forward estimate.
2. **E1** (team lead) presents two costed options to stakeholders: (a) add worker capacity within existing infrastructure budget, or (b) implement more aggressive batching to reduce effective notification rate.
3. Stakeholders select an option within 3 business days of the presentation.
4. If no decision is reached in 3 business days, **Default A** (throttle lower-priority queues) activates automatically until a decision is made.
5. If option (b) is selected, the batching changes consume approximately 2 engineer-weeks from the Month 4 workstream. E1 communicates the specific milestone impact within 24 hours of option selection.

---

#### SMS Volume: Separate Treatment from Social Push

SMS in this app is primarily OTP and authentication. The prior versions incorrectly applied the same 90%/4-hour concentration model used for social push to SMS. This section corrects that.

**Why SMS concentration differs from social push:** Social push notifications peak during social engagement hours — evenings and weekends. OTP and authentication SMS messages are triggered by login events, which are more evenly distributed across active hours and do not compress into a 4-hour window in the same way. Re-engagement campaigns sometimes trigger authentication flows (password resets, account reactivation) that are deliberately spread by the sending scheduler.

**SMS concentration model:**

| SMS Category | Concentration Model | Basis |
|-------------|--------------------|----|
| OTP / authentication | 60% in 6 hours | Login events distributed across active hours |
| Re-engagement triggered auth | 40% in 8 hours | Deliberately distributed by scheduler |
| **Blended (planning basis)** | **65% in 6 hours** | Weighted toward OTP; conservative |

**SMS volume derivation:** 1% of DAU trigger an SMS-required authentication event per day (2FA login, password reset, suspicious login alert). At High scenario: 3.5M × 0.01 = 35,000 SMS/day.

```
SMS peak rate (High, blended 65%/6hr)     = (35,000 × 0.65) ÷ 21,600 = 1.05/sec
SMS peak rate (High, worst-case 90%/4hr)  = (35,000 × 0.90) ÷ 14,400 = 2.19/sec
```

SMS peak rates are low enough that concentration model choice does not materially affect infrastructure sizing — the SMS queue and its dedicated workers are sized by reliability requirements, not throughput. However, the concentration model does affect cost projections.

**SMS budget sensitivity (High scenario, 35,000/day):**

| Policy | SMS/day | Monthly SMS | Cost at $0.0075/SMS | Cost at $0.015/SMS |
|--------|---------|------------|--------------------|--------------------|
| 1% DAU, standard auth | 35,000 | 1.05M | $7,875 | $15,750 |
| 3% DAU, aggressive 2FA | 105,000 | 3.15M | $23,625 | $47,250 |
| 5% DAU, all logins | 175,000 | 5.25M | $39,375 | $78,750 |

**Planning basis: ~$17K/month** (1% DAU, blended rate ~$0.016/SMS including international). Realistic worst-case under aggressive authentication policy: **$67.5K/month**. Decision deadline: Week 2.

---

#### Email Volume

Email notifications divide into two categories with different denominators and different concentration behaviors.

**Activity emails** (event-driven): 40% of DAU have email activity notifications enabled. At High scenario: 3.5M × 0.40 = 1.4M activity emails/day. These follow social engagement concentration: 90% in 4 hours is appropriate.

**Re-engagement and digest emails** (scheduled): At High scenario, lapsed users = 10M − 3.5M = 6.5M.

**Critical correction on concentration modeling:** Prior versions applied the same 90%/4-hour concentration model to scheduled re-engagement emails as to event-driven activity emails. This is incorrect. Scheduled sends are deliberately spread by the sending system. The concentration model for scheduled email depends on scheduler configuration:

- **With deliberate spreading (required architecture):** Scheduler distributes sends across a 4–8 hour window. Concentration: 50% in 6 hours.
- **Without spreading (pathological case):** All sends fire simultaneously at the scheduled time. Concentration: 95%+ in 15 minutes. This must be explicitly prevented by scheduler design — it is an architectural requirement, not an assumption.

**Planning basis for re-engagement email concentration: 50% in 6 hours (21,600 sec), assuming the scheduler implements rate-limited dispatch.** This is a launch prerequisite, not an assumption to be validated later.

**The 30% re-engagement send rate is a product policy assumption, not a neutral planning basis.** To reach 30% of lapsed users per day, the product must be running either a bi-weekly digest plus additional triggered re-engagement emails, or a daily digest to a 30% subset. Neither is a default. Product must confirm by end of Week 2.

**Email volume and peak rate by re-engagement policy (High scenario, corrected concentration models):**

| Re-engagement send rate | Activity emails/day | Re-engagement emails/day | Total/day | Activity peak (90%/4hr) | Re-eng peak (50%/6hr) | Combined peak |
|------------------------|--------------------|--------------------------|-----------|--------------------------|-----------------------|---------------|
| 10% (weekly digest) | 1.4M | 650K | 2.05M | 87.5/sec | 15.0/sec | 102.5/sec |
| 20% (weekly + triggered) | 1.4M | 1.3M | 2.7M | 87.5/sec | 30.1/sec | 117.6/sec |
| **30% (planning basis)** | **1.4M** | **1.95M** | **3.35M** | **87.5/sec** | **45.1/sec** | **132.6/sec** |
| 50% (daily digest, partial) | 1.4M | 3.25M | 4.65M | 87.5/sec | 75.2/sec | 162.7/sec |
| 100% (daily digest, all lapsed) | 1.4M | 6.5M | 7.9M | 87.5/sec | 150.5/sec | 238/sec |

Applying the correct per-category concentration models reduces the 30% planning basis peak from the prior version's 203/sec to **132.6/sec** — a 35% reduction. This directly affects the SendGrid contract tier.

**However:** If the scheduler is misconfigured and re-engagement emails are batch-dumped rather than spread, the peak rate at 30% could reach 600+/sec. The contract target below assumes scheduler rate-limiting is implemented and verified before launch.

**Required SendGrid contract: 215/sec sustained** (50% re-engagement scenario at 162.7/sec + 32% headroom). This prevents contract renegotiation if product selects a more aggressive re-engagement policy, while being meaningfully lower than the prior version's 320/sec target — a real cost reduction.

**Ownership:** E1 owns the SendGrid enterprise contract. E2 supports by providing technical throughput requirements by end of Week 1. E1 signs the contract.

---

#### Self-Hosted Email Fallback: Calendar Time Is the Binding Constraint

If the SendGrid contract is not executed by end of Month 1, the self-hosted path (Postfix cluster + SES relay) activates. The prior versions described this as a "real, scoped option." The honest framing:

**The binding constraint is calendar time, not engineer effort.** IP warm-up for 1.75–4.65M emails/day takes 4–8 weeks of calendar time regardless of engineer availability. ISPs impose daily sending limits that increase gradually as the sending IP establishes reputation:

| Warm-up Week | Approximate Daily Limit per IP |
|-------------|-------------------------------|
| 1 | 5,000–10,000 |
| 2 | 20,000–50,000 |
| 3–4 | 100,000–500,000 |
| 5–8 | Full volume (with monitoring) |

Full sending capacity is not available until Week 5–8 of warm-up, regardless of how many engineers are working. Multiple IPs warmed in parallel can accelerate aggregate capacity, but each IP follows its own curve.

**Engineer cost:** 6–8 engineer-weeks for deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring, and IP warm-up management. At 4 engineers over 6 months (96 engineer-weeks total), this is 6–8% of total team capacity.

**The concrete tradeoff:** This work lands in Month 1–2, the same window as the core queue infrastructure build. The specific workstream that slips if the SendGrid contract fails is the **Month 2 in-app notification delivery milestone**. In-app delivery moves from Month 2 to Month 3. Push-only delivery launches in Month 2 as planned.

**This tradeoff must be presented to stakeholders by E1 within 48 hours of it becoming clear the Month 1 contract deadline will be missed** — not after the deadline passes.

---

#### Combined Peak Throughput

All channels use a consistent concentration assumption within a scenario. Push and in-app use 90%/4hr (event-driven, US-centric planning basis). Email uses per-category models as derived above. SMS uses the blended 65%/6hr model.

```
Peak rate = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

**Combined peak throughput (High scenario, 30% re-engagement basis):**

| Channel | Daily Volume | Concentration | Peak Rate |
|---------|-------------|---------------|-----------|
| Push + In-App | 38.5M | 90% / 4hr | 2,406/sec |
| Email (activity) | 1.4M | 90% / 4hr | 87.5/sec |
| Email (re-engagement) | 1.95M | 50% / 6hr | 45.1/sec |
| SMS | 35,000 | 65% / 6hr | 1.05/sec |
| **Combined** | | | **2,540/sec** |

Worker sizing target: **2,650/sec sustained** — approximately 4% headroom over this combined peak, with the 25% volume headroom described in the densification section providing the primary buffer against growth.

---

#### Viral Spike Model

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days. Monitoring identifies the problem; it does not prevent the delay.

**The right framing:** We cannot size workers for every