# Notification System Design — Revised v3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Five items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy is $67.5K/month ongoing. Decision deadline: Week 2.

- **Opt-out compliance architecture (Section 2.4):** Cache staleness creates potential TCPA/CAN-SPAM/GDPR exposure. Legal must review and confirm which compliant architecture is acceptable before finalization. This document presents two compliant architectures and does not recommend the cache-with-staleness path — that determination requires a legal opinion, not a design document assertion.

- **SendGrid enterprise contract (Section 1.1):** Required before launch. Procurement begins Week 1. E1 owns this contract; E2 supports the technical requirements documentation. If not executed by end of Month 1, E1 presents the self-hosted tradeoff to stakeholders within 48 hours.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A (throttle lower-priority queues) or Default B (shed load with dead-letter queue) before this document is finalized.

- **Broadcast notification policy (Section 1.1 and Section 6):** Hard cap of 100K recipients per job, enforced at the API layer, the worker layer, and the database write layer. A product owner must be named as the exception gate before launch. Section 6 specifies the interaction between enforcement layers, including the failure path when a job passes the API check but fails the database write check.

**A note on internal consistency:** All calculations in this document use a single DAU/MAU scenario table. The spike model, worker sizing, and peak throughput calculations all use the same scenario inputs. Where prior versions used different DAU assumptions in different sections, this version resolves those inconsistencies explicitly.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### Scenario Framework

All calculations in this document use one of three named scenarios. The scenario name appears in every table and calculation that depends on it. Mixing scenarios between calculations is a document error; if a reviewer identifies a calculation that uses inputs from different scenarios, that is a defect to be corrected.

| Scenario | DAU/MAU | DAU | Notes |
|----------|---------|-----|-------|
| Low | 15% | 1.5M | Early-stage retention |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Strong retention; used for worker sizing |

**Worker sizing uses the High scenario throughout.** Peak throughput calculations present all three scenarios. The spike model uses the High scenario, consistent with worker sizing. The prior version used the Base scenario for spike calculations while using the High scenario for worker sizing — those numbers were not internally consistent and have been corrected here.

---

#### Push and In-App Volume: Derivation

Push and in-app notifications originate from discrete trigger events modeled separately.

**Event classes and per-DAU rates:**

| Event Class | Trigger | Estimated Events/DAU/Day | Notes |
|-------------|---------|--------------------------|-------|
| Likes on posts | User posts content; others react | 3–8 | Batched after first delivery; see Section 2.2 |
| Comments on posts | Others comment on user content | 1–4 | Batched similarly |
| New followers/friend requests | Social graph growth | 0.5–2 | Lower bound at maturity |
| Direct messages received | Peer-to-peer messaging | 2–6 | Highly variable; power users skew high |
| Mentions and tags | Others reference the user | 0.5–2 | |
| System/product notifications | Feature announcements, nudges | 0.5–1 | Capped by product policy |

Raw event total per DAU per day: 7.5–23 events. After batching (Section 2.2 reduces like/comment storms to single notifications), effective delivered notifications: **8–14/DAU/day**.

Planning basis: **11 notifications/DAU/day** (midpoint of 8–14 range).

**Push + In-App volume by scenario:**

| Scenario | DAU | 8/DAU/day | 11/DAU/day | 14/DAU/day |
|----------|-----|-----------|------------|------------|
| Low | 1.5M | 12M | 16.5M | 21M |
| Base | 2.5M | 20M | **27.5M** | 35M |
| High | 3.5M | 28M | **38.5M** | 49M |

**Worker sizing input: 38.5M/day (High scenario, 11/DAU/day).** All spike calculations below use this same 38.5M/day figure.

---

#### The Unmodeled Graph Densification Factor: Honest Treatment

The document explicitly acknowledges that as the social graph densifies, per-user notification rates increase without DAU growth. A user with 500 followers receives more likes per post than a user with 50. This is a known unmodeled factor.

The prior version acknowledged this and then set a reassessment trigger at 13/DAU/day — but worker sizing used 11/DAU/day with 10% headroom (12.1/DAU/day effective ceiling). The headroom was entirely consumed before the reassessment trigger fired. The system would already be at capacity by the time the trigger activated.

**This version resolves the gap as follows:**

Worker sizing targets **38.5M/day** (High scenario, 11/DAU/day) with **25% headroom**, yielding an effective capacity ceiling of **48.1M/day** (approximately 13.8/DAU/day at High DAU). The reassessment trigger fires at **13/DAU/day** — which corresponds to **45.5M/day** at High DAU, leaving **2.6M/day (5.7%) of remaining headroom** when reassessment begins.

This means the reassessment has a concrete buffer to work within: the system is not already saturated when the trigger fires, and the reassessment can produce a capacity decision that takes effect before headroom is exhausted.

**Reassessment process (not just a trigger):**

If observed notifications/DAU/day exceeds 13 before Month 4, the following process activates within 5 business days:

1. **E3** (infrastructure lead) produces a revised capacity projection based on observed trajectory, with a 90-day forward estimate.
2. **E1** (team lead) presents two options to stakeholders: (a) add worker capacity within the existing infrastructure budget, or (b) implement more aggressive batching to reduce effective notification rate. Both options are costed.
3. Stakeholders select an option within 3 business days of the presentation.
4. If no decision is reached in 3 business days, Default A (throttle lower-priority queues) activates automatically until a decision is made.
5. Month 4 and Month 5 milestones are not affected unless option (b) is selected, in which case the batching changes consume approximately 2 engineer-weeks from the Month 4 workstream. E1 communicates the specific milestone impact within 24 hours of option selection.

The reassessment trigger is not a monitoring alert — it is a process with owners, timelines, and defined consequences for inaction.

---

#### SMS Volume and Concentration: Separate Treatment

SMS in this app is primarily OTP and authentication. This is categorically different from social push notifications, and the prior version's application of the same 90%/4-hour concentration model to SMS was unjustified. This section corrects that.

**Why SMS concentration differs from social push:**

Social push notifications peak during social engagement hours — evenings and weekends, concentrated in the user's local timezone. OTP and authentication SMS messages are triggered by login events. Login behavior has a different distribution: it is concentrated around app open events (morning, commute, lunch, evening) but is more evenly distributed across the day than social engagement, and it does not compress into a 4-hour window in the same way.

Additionally, re-engagement campaigns sometimes trigger authentication flows (password resets, account reactivation), which can create scheduled SMS bursts that are deliberately spread by the sending system rather than event-driven.

**SMS concentration model:**

| SMS Category | Concentration Model | Basis |
|-------------|--------------------|----|
| OTP / authentication | 60% in 6 hours (21,600 sec) | Login events distributed across active hours; less compressed than social engagement |
| Re-engagement triggered auth | Spread by scheduler; 40% in 8 hours | Deliberately distributed; scheduler controls the rate |
| Blended (planning basis) | 65% in 6 hours | Weighted toward OTP; conservative |

**SMS volume derivation:**

1% of DAU trigger an SMS-required authentication event per day (login with 2FA, password reset, suspicious login alert). At High scenario: 3.5M × 0.01 = 35,000 SMS/day.

```
SMS peak rate (High scenario, 65%/6hr) = (35,000 × 0.65) ÷ 21,600 = 1.05/sec
SMS peak rate (High scenario, worst-case 90%/4hr) = (35,000 × 0.90) ÷ 14,400 = 2.19/sec
```

SMS peak rates are low enough that concentration model choice does not materially affect infrastructure sizing — the SMS queue and its dedicated workers are sized by reliability requirements, not throughput. However, the concentration model does affect cost projections, so the distinction matters for budget accuracy.

**SMS budget sensitivity (High scenario, 35,000/day):**

| Policy | SMS/day | Monthly SMS | Cost at $0.0075/SMS | Cost at $0.015/SMS |
|--------|---------|------------|--------------------|--------------------|
| 1% DAU, standard auth | 35,000 | 1.05M | $7,875 | $15,750 |
| 3% DAU, aggressive 2FA | 105,000 | 3.15M | $23,625 | $47,250 |
| 5% DAU, all logins | 175,000 | 5.25M | $39,375 | $78,750 |

Planning basis: **$17K/month** (1% DAU, blended rate ~$0.016/SMS including international). Realistic worst-case under aggressive authentication policy: **$67.5K/month**. Decision deadline: Week 2.

---

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators and different concentration behaviors.

**Activity emails** (event-driven): 40% of DAU have email activity notifications enabled. At High scenario: 3.5M × 0.40 = 1.4M activity emails/day. These are event-driven and follow social engagement concentration: 90% in 4 hours is reasonable.

**Re-engagement and digest emails** (scheduled): At High scenario, lapsed users = 10M − 3.5M = 6.5M.

**Critical distinction from prior version:** The prior version applied the same 90%/4-hour concentration model to scheduled re-engagement emails as to event-driven activity emails. This is incorrect. Scheduled sends are deliberately spread or batched by the sending system. The concentration model for scheduled email depends on how the scheduler is configured:

- **Scheduled sends with deliberate spreading:** The scheduler distributes sends across a 4–8 hour window, producing a flat or gently peaked distribution. Concentration: 40–60% in 4 hours.
- **Scheduled sends without spreading (batch dump):** All sends fire simultaneously at the scheduled time. Concentration: 95%+ in 15 minutes. This is a pathological case that must be explicitly prevented by the scheduler design.
- **Planning basis for re-engagement email concentration:** 50% in 6 hours (21,600 sec), assuming the scheduler deliberately spreads sends. This is an architectural requirement, not an assumption — the scheduler must implement rate-limited dispatch.

**Re-engagement send rate — product policy decision:**

| Re-engagement send rate | Re-engagement emails/day (High) | Total email/day (High) |
|------------------------|--------------------------------|----------------------|
| 10% (weekly digest only) | 650K | 2.05M |
| 20% (weekly + triggered) | 1.3M | 2.7M |
| **30% (planning basis)** | **1.95M** | **3.35M** |
| 50% (daily digest, partial) | 3.25M | 4.65M |
| 100% (daily digest, all lapsed) | 6.5M | 7.9M |

The 30% rate requires explicit product policy decisions (bi-weekly digest plus triggered re-engagement, or daily digest to a 30% subset). This is not a neutral planning basis. Product must confirm by end of Week 2.

**Email peak rate calculations — with correct concentration models by category:**

| Email Category | Volume (High, 30% basis) | Concentration | Peak rate |
|---------------|--------------------------|---------------|----------|
| Activity (event-driven) | 1.4M/day | 90% in 4hr (14,400s) | 87.5/sec |
| Re-engagement (scheduled, spread) | 1.95M/day | 50% in 6hr (21,600s) | 45.1/sec |
| **Combined** | **3.35M/day** | — | **132.6/sec** |

Compare to prior version's 203/sec (which applied 90%/4hr to all email): the corrected model reduces the peak rate estimate by 35%. This has a direct consequence for the SendGrid contract tier.

**Revised SendGrid throughput requirement:**

| Re-engagement policy | Combined peak (corrected model) | Contract target (+20% headroom) |
|---------------------|--------------------------------|---------------------------------|
| 10% | 81/sec | 100/sec |
| 30% (planning basis) | 133/sec | 160/sec |
| 50% | 177/sec | 215/sec |

The prior version targeted 320/sec. The corrected model requires **215/sec** to cover the 50% re-engagement scenario with headroom. This is a meaningful reduction in contract cost. However, **if the scheduler is misconfigured and re-engagement emails are batch-dumped rather than spread**, the peak rate could reach 600+/sec. The 215/sec contract target assumes the scheduler spreading requirement is implemented. This is an architectural dependency that must be documented as a launch prerequisite.

**Required SendGrid contract: 215/sec sustained, with the explicit caveat that this assumes scheduler rate-limiting is implemented and verified before launch.**

---

#### Self-Hosted Email Fallback: Calendar Time vs. Engineer-Weeks

The prior version estimated the self-hosted fallback at "6–8 engineer-weeks" without distinguishing engineer effort from calendar time. This conflation was incorrect and potentially misleading.

**The binding constraint for self-hosted email is calendar time, not engineer effort:**

IP warm-up for a sending volume of 1.75–4.75M emails/day typically takes **4–8 weeks of calendar time** regardless of engineer availability. ISP reputation is built incrementally — major ISPs (Gmail, Yahoo, Outlook) impose daily sending limits that increase gradually as the sending IP establishes a positive reputation. A new IP attempting to send 4M emails/day on Day 1 will be blocked or heavily filtered. The warm-up schedule typically looks like:

| Week | Approximate daily send limit per IP |
|------|-------------------------------------|
| 1 | 5,000–10,000 |
| 2 | 20,000–50,000 |
| 3–4 | 100,000–500,000 |
| 5–8 | Full volume (with monitoring) |

At our planning basis volume, full sending capacity is not available until **Week 5–8 of warm-up**, regardless of how many engineers are working on the problem. Multiple IPs can be warmed in parallel to accelerate aggregate capacity, but each IP follows its own warm-up curve.

**Realistic self-hosted timeline:**

- Engineer