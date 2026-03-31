# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 28–49M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting and viral social spikes must never delay OTP or direct message delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working push system in Month 2, full channel coverage by Month 4, hardening in Months 5–6.

**Four items require action before this design is finalized:**

| Item | Type | Options | Deadline | Owner |
|------|------|---------|----------|-------|
| Re-engagement send policy | Decision | Weekly digest (10%), weekly + triggered (20%), bi-weekly + triggered (30%) — determines SendGrid contract tier | **Week 1** (before procurement begins) | Product |
| SMS budget and auth policy | Decision | See Section 1.3 for cost derivation by policy | Week 2 | Finance + Product |
| Capacity overrun default | Decision | Option A: throttle lower-priority queues. Option B: shed load to dead-letter queue | Week 2 | Engineering lead |
| Broadcast notification policy | Operational prerequisite | Hard cap at 100K recipients per job, enforced at three layers. A named product owner must be designated as exception gate | Before launch | Product |

**One item is a legal constraint, not a stakeholder decision.** User opt-out preferences must be honored within a bounded window satisfying TCPA, CAN-SPAM, and GDPR. Section 2.4 presents two architectures that meet this constraint. Legal must confirm which is acceptable. The path that accepts a staleness window producing opt-out violations is not available regardless of preference.

**Note on procurement sequencing:** The re-engagement policy decision is placed at Week 1 — ahead of all other decisions — because it is the primary input to the SendGrid contract tier. Procurement cannot begin until this decision is made. If it slips past Week 1, E1 notifies stakeholders immediately with the specific consequence: contract execution moves to Month 2, which delays the email channel launch from Month 3 to Month 4.

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU and Push/In-App Volume

#### DAU/MAU Ratio

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

Planning basis: 25% DAU/MAU (2.5M DAU). All infrastructure sizing uses 35% (3.5M DAU) as the conservative high case. Cost estimates use the 25% planning basis.

#### Push and In-App Volume: Derivation

The prior assertion of 15 notifications/user/day without derivation is replaced with a bottoms-up estimate by event class.

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery; see Section 2.2 |
| Comments on posts | 1–4 | Batched similarly |
| New followers/friend requests | 0.5–2 | Lower bound at maturity |
| Direct messages received | 2–6 | Power users skew high |
| Mentions and tags | 0.5–2 | |
| System/product notifications | 0.5–1 | Capped by product policy |

Raw events: 7.5–23/DAU/day. After batching (Section 2.2 reduces like/comment storms to single notifications): **8–14 delivered notifications/DAU/day**. Planning basis: **11/DAU/day**.

**Volume sensitivity:**

| DAU/MAU | DAU | 8/DAU/day | 11/DAU/day | 14/DAU/day |
|---------|-----|-----------|------------|------------|
| 15% | 1.5M | 12M | 16.5M | 21M |
| 25% | 2.5M | 20M | 27.5M | 35M |
| 35% | 3.5M | 28M | 38.5M | 49M |

**All infrastructure sizing uses 38.5M push+in-app notifications/day** (35% DAU/MAU × 11/DAU/day).

Push+in-app peak rate (90% concentration, 4-hour window):
```
= (38.5M × 0.90) ÷ 14,400 = 2,406/sec
```

Worker sizing target: **2,650/sec sustained** (10% headroom over high-case peak).

**Known unmodeled factor — graph density growth:** Notification volume grows as social graphs densify, independent of DAU growth. A user with 500 followers receives more likes per post than a user with 50. The Month 2 calibration checkpoint (Section 5) measures observed notifications/DAU/day against the 11/day planning basis. If observed rates exceed 13/DAU/day before Month 4, the response is defined and not open-ended:

1. Social-channel worker pool increases by 25% (pre-provisioned headroom in the Kubernetes node pool).
2. Batching windows for likes and comments tighten from 15 minutes to 5 minutes.
3. If observed rates exceed 16/DAU/day, the queue depth targets and Redis memory allocation in Section 3 are reassessed and a revised infrastructure cost estimate is presented to stakeholders within two weeks.

---

### 1.2 Email Volume

Email divides into two populations with structurally different concentration characteristics. Applying the same model to both misrepresents the actual load.

#### Activity Emails

Go to DAU with email activity notifications enabled. Estimated 40% of DAU (industry benchmark: 30–50%).

```
Activity emails/day = 3.5M × 0.40 = 1.4M/day (high-case)
```

Activity emails are user-driven and follow organic concentration: 90% in a 4-hour peak window.

```
Activity email peak = (1.4M × 0.90) ÷ 14,400 = 87.5/sec
```

#### Re-engagement and Digest Emails

Go to the lapsed user population: 10M − 3.5M = 6.5M lapsed users (high-case basis).

**These are scheduled batch sends, not organic events.** The correct model is: peak load equals the throughput required to complete the send within the scheduled window — not a concentration fraction applied to organic traffic.

For a nightly digest sent in a 4-hour window (18:00–22:00 local time):

```
Peak rate = (lapsed users × send_rate) ÷ 14,400
```

| Re-engagement policy | Policy description | Emails/day | Peak/sec (4-hour window) |
|---------------------|-------------------|------------|--------------------------|
| 10% | Weekly digest only (1/7 per day) | 650K | 40.6/sec |
| 20% | Weekly digest + triggered re-engagement | 1.3M | 81.3/sec |
| 30% | Bi-weekly digest + triggered | 1.95M | 121.9/sec |

**The 30% rate requires explicit product authorization.** It implies either a bi-weekly digest plus triggered re-engagement emails, or a daily digest to 30% of the lapsed population. Neither is a default. The product must select one of these three policies before the SendGrid contract can be negotiated — the contract tier is sized to the selected policy.

#### Combined Email Peak

Activity and re-engagement peaks do not necessarily coincide. The table below is a conservative bound assuming full overlap.

| Re-engagement policy | Activity peak | Re-engagement peak | Combined peak |
|---------------------|--------------|-------------------|---------------|
| 10% (weekly digest) | 87.5/sec | 40.6/sec | 128/sec |
| 20% (weekly + triggered) | 87.5/sec | 81.3/sec | 169/sec |
| 30% (bi-weekly + triggered) | 87.5/sec | 121.9/sec | 209/sec |

#### SendGrid Contract Sizing

Standard SendGrid plans support approximately 27/sec. All three policy options exceed this; an enterprise contract is required regardless of which policy is selected.

| Re-engagement policy | Combined peak | Contract target (20% headroom) |
|---------------------|--------------|-------------------------------|
| 10% | 128/sec | 155/sec |
| 20% | 169/sec | 205/sec |
| 30% | 209/sec | 255/sec |

**E1 owns the SendGrid enterprise contract.** E2 provides the technical throughput specification — derived from the confirmed re-engagement policy — to E1 by end of Week 1. E1 begins negotiation once the policy decision is confirmed. Contract execution target: end of Month 1.

**Self-hosted fallback — concrete scope:**

If the SendGrid contract is not executed by end of Month 1, the self-hosted path (Postfix cluster + Amazon SES relay) activates. This is not a neutral contingency — it consumes real capacity from a team that has no slack.

| Task | Estimate | Owner |
|------|----------|-------|
| Postfix cluster provisioning and configuration | 1 week | E3 |
| DKIM, SPF, DMARC setup and DNS propagation | 3 days | E3 |
| IP warm-up schedule (4–6 weeks, overlapping with other work) | Ongoing | E3 |
| Bounce and complaint webhook handling | 4 days | E2 |
| Deliverability monitoring and alerting | 3 days | E2 |
| SES relay integration and throughput testing | 2 days | E3 |

**Total: ~6.5 engineer-weeks, primarily E3 and E2.**

The Month 1–2 schedule assigns E3 to in-app notification delivery and E2 to preference management. Both workstreams cannot proceed at full pace in parallel with the self-hosted email build. The concrete consequence: **in-app notification delivery moves from Month 2 to Month 3; preference management moves from Month 2 to Month 3; email channel launches in Month 4 instead of Month 3. Push-only delivery launches in Month 2 as planned.**

This is the specific tradeoff, not an open question. E1 presents it to stakeholders within 48 hours of it becoming clear the Month 1 contract deadline will be missed — not after the deadline passes.

---

### 1.3 SMS Volume and Cost

SMS serves two distinct purposes with different volume characteristics. These must be modeled separately because they have different cost drivers and different architectural treatments.

**OTP and authentication SMS:** Sent to users completing phone-based authentication flows. Volume is entirely determined by authentication policy.

| Auth policy | OTP triggers/DAU/day | SMS/day (2.5M DAU) | Monthly cost at $0.0079/SMS |
|-------------|---------------------|-------------------|----------------------------|
| Login only, no 2FA | 0.3 | 750K | $177.8K |
| Login + optional 2FA (30% adoption) | 0.5 | 1.25M | $296.3K |
| Login + required 2FA | 1.0 | 2.5M | $592.5K |

**Social SMS:** Limited to users who have explicitly opted in and have no push token registered. Estimated 1% of DAU.

```
Social SMS/day = 2.5M × 0.01 = 25K/day (planning basis)
Monthly cost = 750K × $0.0079 = $5.9K/month
```

**The original $17K/month planning basis requires correction.** Working backwards: $17K/month ÷ $0.0079/SMS ÷ 30 days = ~71.7K SMS/day. This is consistent only with social-only SMS and no OTP delivery whatsoever. Any phone-based authentication makes this figure incorrect by an order of magnitude.

**The realistic minimum for any app with phone-based authentication is $177.8K/month** (login only, no 2FA, 2.5M DAU). This is not a worst case — it is the floor.

**If SMS costs at this level are not acceptable, the decision is not a budget adjustment.** It is a product architecture decision: either (a) eliminate phone-based authentication in favor of email-only or app-based TOTP, or (b) restrict SMS OTP to account recovery only and use email for standard login verification.

The infrastructure routes OTP notifications through the high-priority SMS queue regardless of which policy is selected. The volume and cost implications change; the architecture does not.

**Required action:** Product and Finance must confirm the authentication policy and acceptable SMS budget by Week 2.

---

### 1.4 Combined Peak Throughput

All infrastructure sizing uses the 35% DAU/MAU high case and the 30% re-engagement policy planning basis. The 25% planning basis is shown for cost estimation only.

**Infrastructure sizing basis (35% DAU/MAU):**

| Channel | Daily volume | Peak/sec |
|---------|-------------|---------|
| Push + In-App | 38.5M | 2,406/sec |
| Email | 3.75M | 234/sec |
| SMS | 105K | 6.6/sec |
| **Total** | **42.4M** | **2,647/sec** |

**Worker sizing target: 2,650/sec sustained** — derived directly from the high-case infrastructure sizing basis, not from the planning basis.

**Peak concentration model:**

All channels use a consistent concentration assumption within a scenario.

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours | Single timezone band |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands |

Note: batch email sends (re-engagement) are controlled by the sender and use the scheduled window model from Section 1.2, not a concentration fraction. The 234/sec email peak above uses 90% concentration for activity email and a 4-hour scheduled send window for re-engagement, with the conservative assumption that both windows overlap.

---

### 1.5 Viral Spike Model

**The problem with autoscaling as a spike response:** A spike peaking in 5 minutes cannot be meaningfully mitigated by autoscaling. Kubernetes HPA provisioning and pod warm-up time is 2–5 minutes under ideal conditions. By the time new workers are ready, the spike has already generated its backlog. Autoscaling handles sustained load increases; it does not prevent spike-induced backlog.

**The correct primary mitigation is queue isolation, not worker scaling.**

High-priority notifications (OTPs, direct messages, security alerts) run on dedicated workers that are never shared with social notification volume. A viral spike in social like/comment notifications does not affect these queues. This is the architectural consequence of the per-channel queue design — and it is the primary reason for that design choice.

**Spike model for social-channel notifications:**

Social queue worker allocation: 1,800/sec (out of 2,650/sec total; the remainder is reserved for high-priority channels and held as headroom).

Spike arrival rate (5% of daily social volume in 10 minutes):
```
= (38.5M × 0.05) ÷ 600 = 3,208/sec spike traffic
+ 2,406/sec normal background traffic
= 5,614/sec total arrival during spike

Social queue arrival during spike: approximately 3,208 + 1,719 = 4,927/sec
Social worker capacity: 1,800/sec
Excess: 3,127/sec
Backlog at spike end (10 minutes): 3,127 × 600 = 1,876,200 notifications
Post-spike drain rate: 1,800 − 1,719 = 81/sec

Wait — this drain rate is too slow to be acceptable. Revised: after spike ends, 
the full social worker pool (1,800/sec) minus normal arrival (1,719/sec) 
= 81/sec net drain. At this rate, draining 1.87M notifications takes ~6.4