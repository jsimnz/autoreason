# Notification System Design — Revised v3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 28–49M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting and viral social spikes should never delay OTP or direct message delivery. We pay the monitoring overhead of four queues explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working push system in Month 2, full channel coverage by Month 4, hardening in Months 5–6.

**Three decisions are required from stakeholders before this design is finalized.** Each is a real choice between defined options.

| Decision | Options | Deadline | Owner |
|----------|---------|----------|-------|
| SMS budget approval | Approve $17K/month planning basis (see Section 1.3 for derivation) or reduce OTP-triggered SMS scope | Week 2 | Finance + Product |
| Capacity overrun default | Option A: throttle lower-priority queues. Option B: shed load to dead-letter queue | Week 2 | Engineering lead |
| Re-engagement send policy | Weekly digest (10%), weekly + triggered (20%), or bi-weekly + triggered (30%) — determines SendGrid contract tier | **Week 1** (before procurement begins) | Product |

**One item is a legal constraint, not a stakeholder decision.** User opt-out preferences must be honored within a bounded window that satisfies TCPA, CAN-SPAM, and GDPR. Section 2.4 presents two architectures that meet this constraint. Legal must confirm which is acceptable. The third path — accepting a staleness window that produces opt-out violations — is not available regardless of preference.

**One policy requires a named owner before launch.** Broadcast notifications are hard-capped at 100K recipients per job, enforced at three layers (API, worker, database write). A named product owner must be designated as the exception gate before the system goes live. This is an operational prerequisite, not a design decision.

**Note on procurement sequencing:** The re-engagement policy decision is moved to Week 1 — ahead of all other decisions — because it is the primary input to the SendGrid contract tier. Procurement cannot begin until this decision is made. E1 begins contract negotiation in Week 1 using the confirmed policy. If the decision slips past Week 1, E1 notifies stakeholders immediately with the specific consequence: contract execution moves to Month 2, which delays the email channel launch from Month 3 to Month 4.

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU and Push/In-App Volume

#### DAU/MAU Ratio

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

Planning basis: 25% DAU/MAU (2.5M DAU). Infrastructure sizing uses 35% (3.5M DAU) as the conservative high case.

#### Push and In-App Volume: Derivation

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery; see Section 2.2 |
| Comments on posts | 1–4 | Batched similarly |
| New followers/friend requests | 0.5–2 | |
| Direct messages received | 2–6 | Power users skew high |
| Mentions and tags | 0.5–2 | |
| System/product notifications | 0.5–1 | Capped by product policy |

Raw events: 7.5–23/DAU/day. After batching: **8–14 delivered notifications/DAU/day**. Planning basis: **11/DAU/day**.

**Volume and peak throughput — consistent high-case sizing throughout this document:**

All infrastructure sizing, worker targets, and throughput tables use 35% DAU/MAU (3.5M DAU) and 11 notifications/DAU/day, producing **38.5M push+in-app notifications/day**. The 25% planning basis appears in cost estimates only.

Push+in-app peak (90% concentration, 4-hour window):
```
= (38.5M × 0.90) ÷ 14,400 = 2,406/sec
```

Worker sizing target: **2,650/sec sustained** (10% headroom over high-case peak).

**Known unmodeled factor — graph density growth:** Notification volume grows as social graphs densify, independent of DAU growth. A user with 500 followers receives more likes per post than a user with 50. The Month 2 calibration checkpoint (Section 5) measures observed notifications/DAU/day against the 11/day planning basis. If observed rates exceed 13/DAU/day before Month 4, the response is:

1. Worker pool for social-channel queues increases by 25% (pre-provisioned headroom in the Kubernetes node pool).
2. Batching windows for likes and comments tighten from 15 minutes to 5 minutes to reduce per-event notification generation.
3. If observed rates exceed 16/DAU/day, the queue depth targets and Redis memory allocation in Section 3 are reassessed and a revised infrastructure cost estimate is presented to stakeholders within two weeks.

The checkpoint triggers a defined response, not an open reassessment.

---

### 1.2 Email Volume

Email divides into two populations with different concentration characteristics.

#### Activity Emails

Go to DAU with email activity notifications enabled. Estimated 40% of DAU (industry benchmark: 30–50%).

```
Activity emails/day = 3.5M × 0.40 = 1.4M/day (high-case)
```

Activity emails are user-driven and follow the same concentration model as push: 90% in a 4-hour peak window.

```
Activity email peak = (1.4M × 0.90) ÷ 14,400 = 87.5/sec
```

#### Re-engagement and Digest Emails

Go to the lapsed user population: 10M − 3.5M = 6.5M lapsed users (high-case basis).

**These emails are scheduled batch sends, not organic user-driven events.** Applying the same 90% concentration model as push notifications would misrepresent the actual load. Batch email sends are controlled by the sender and can be spread across any window. The correct model is: peak load equals the throughput required to complete the send within the scheduled window.

For a nightly digest sent between 18:00–22:00 local time (4 hours), the peak rate is:

```
Peak rate = (lapsed users × send_rate) ÷ 14,400
```

| Re-engagement send rate | Policy description | Re-engagement emails/day | Peak email/sec (4-hour send window) |
|------------------------|-------------------|--------------------------|-------------------------------------|
| 10% | Weekly digest only (1/7 per day) | 650K | 40.6/sec |
| 20% | Weekly digest + triggered re-engagement | 1.3M | 81.3/sec |
| 30% | Bi-weekly digest + triggered | 1.95M | 121.9/sec |

**The 30% rate requires explicit product authorization** — it implies either a bi-weekly digest plus triggered re-engagement emails, or a daily digest to 30% of the lapsed population. Neither is a default behavior.

**Combined email peak by policy (activity + re-engagement):**

| Re-engagement policy | Activity peak | Re-engagement peak | Combined peak |
|---------------------|--------------|-------------------|---------------|
| 10% (weekly digest) | 87.5/sec | 40.6/sec | 128/sec |
| 20% (weekly + triggered) | 87.5/sec | 81.3/sec | 169/sec |
| 30% (bi-weekly + triggered) | 87.5/sec | 121.9/sec | 209/sec |

Note: activity and re-engagement peaks do not necessarily coincide. The 4-hour send window for re-engagement is scheduled; activity email peaks during organic user activity hours. In practice, combined peak is lower than the sum if the send windows are staggered. The table above is a conservative bound assuming full overlap.

**This is why the re-engagement policy decision must precede contract negotiation.** The difference between a 10% and 30% policy is 1.6× in email peak throughput and a different SendGrid contract tier.

#### SendGrid Contract Sizing

Standard SendGrid plans support approximately 27/sec. All three policy options exceed this; an enterprise contract is required regardless of which policy is selected.

| Re-engagement policy | Required sustained throughput | Contract target (20% headroom) |
|---------------------|------------------------------|-------------------------------|
| 10% | 128/sec | 155/sec |
| 20% | 169/sec | 205/sec |
| 30% | 209/sec | 255/sec |

**E1 owns the SendGrid enterprise contract.** E2 provides the technical throughput specification (derived from the confirmed re-engagement policy) to E1 by end of Week 1. E1 begins negotiation once the policy decision is confirmed. Contract execution target: end of Month 1.

**Self-hosted fallback — concrete scope:**

If the SendGrid contract is not executed by end of Month 1, the self-hosted path (Postfix cluster + Amazon SES relay) activates.

Task breakdown for the self-hosted path:

| Task | Estimate | Owner |
|------|----------|-------|
| Postfix cluster provisioning and configuration | 1 week | E3 |
| DKIM, SPF, DMARC setup and DNS propagation | 3 days | E3 |
| IP warm-up schedule (4–6 weeks, overlapping with other work) | Ongoing | E3 |
| Bounce and complaint webhook handling | 4 days | E2 |
| Deliverability monitoring and alerting | 3 days | E2 |
| SES relay integration and throughput testing | 2 days | E3 |

**Total: 6.5 engineer-weeks, primarily E3 and E2.**

The Month 1–2 schedule assigns E3 to the in-app notification delivery milestone and E2 to the preference management system. Both of these cannot proceed in parallel with the self-hosted email build at full pace. The specific consequence: **the in-app notification delivery milestone moves from Month 2 to Month 3. Push-only delivery launches in Month 2 as planned. Preference management moves from Month 2 to Month 3, completing alongside in-app.** Email channel launches in Month 4 instead of Month 3.

This is the concrete tradeoff. E1 presents it to stakeholders within 48 hours of it becoming clear the Month 1 contract deadline will be missed.

---

### 1.3 SMS Volume and Cost

SMS notifications serve two distinct purposes with different volume characteristics:

**OTP and authentication SMS:** Sent to users completing phone-based authentication flows. Volume depends on authentication policy.

| Auth policy | OTP triggers/DAU/day | SMS/day (2.5M DAU basis) | SMS/day (3.5M DAU basis) |
|-------------|---------------------|--------------------------|--------------------------|
| Login only, no 2FA | 0.3 | 750K | 1.05M |
| Login + optional 2FA (30% adoption) | 0.5 | 1.25M | 1.75M |
| Login + required 2FA | 1.0 | 2.5M | 3.5M |
| Login + required 2FA + session re-auth | 1.5 | 3.75M | 5.25M |

**Social and marketing SMS:** Most social apps do not send social notifications via SMS to the general user population — the cost is prohibitive and opt-in rates are low. Planning basis: social SMS limited to users who have explicitly opted in and have no push token registered (estimated 1% of DAU).

```
Social SMS/day = 2.5M × 0.01 = 25K/day (planning basis)
```

**Combined SMS volume and cost:**

Using Twilio standard rates at $0.0079/SMS (US domestic, subject to volume negotiation):

| Auth policy | Total SMS/day (2.5M DAU) | Monthly SMS | Monthly cost |
|-------------|--------------------------|-------------|--------------|
| Login only, no 2FA | 775K | 23.25M | $183.7K |
| Login + optional 2FA (30%) | 1.275M | 38.25M | $302.2K |
| Login + required 2FA | 2.525M | 75.75M | $598.4K |

**The $17K/month planning basis in the executive summary requires correction.** It was not derived from a send policy assumption. Working backwards: $17K/month ÷ $0.0079/SMS = 2.15M SMS/month = ~71.7K SMS/day. This is consistent with social-only SMS (no OTP) at approximately 75K/day — which means the $17K/month figure assumed no OTP via SMS whatsoever.

**Revised planning basis:** The realistic minimum for a social app with any phone-based authentication is the "login only, no 2FA" row above. At 2.5M DAU, this is $183.7K/month — an order of magnitude above the original figure.

**If SMS costs at this level are not acceptable, the decision is not a budget adjustment — it is a product architecture decision:** either (a) eliminate phone-based authentication in favor of email-only or app-based 2FA (TOTP), or (b) restrict SMS OTP to account recovery only and use email for standard login verification.

**Required action:** Product and Finance must confirm the authentication policy and acceptable SMS budget by Week 2. The SendGrid contract discussion cannot substitute for this; they are independent line items. The infrastructure is designed to route OTP notifications through the high-priority SMS queue regardless of which policy is selected; the volume and cost implications change, the architecture does not.

---

### 1.4 Combined Peak Throughput

All figures use the 35% DAU/MAU high case for infrastructure sizing. The 25% planning basis is shown for reference.

**Planning basis (25% DAU/MAU, 30% re-engagement policy):**

| Channel | Daily volume | Peak/sec (90% concentration, 4h window) |
|---------|-------------|----------------------------------------|
| Push + In-App | 27.5M | 1,719/sec |
| Email | 3.25M | 203/sec |
| SMS | 75K | 4.7/sec |
| **Total** | **30.8M** | **1,927/sec** |

**Infrastructure sizing basis (35% DAU/MAU, 30% re-engagement policy):**

| Channel | Daily volume | Peak/sec |
|---------|-------------|---------|
| Push + In-App | 38.5M | 2,406/sec |
| Email | 3.75M | 234/sec |
| SMS | 105K | 6.6/sec |
| **Total** | **42.4M** | **2,647/sec** |

Worker sizing target: **2,650/sec sustained** — derived directly from the high-case infrastructure sizing basis.

Note on email concentration: the 234/sec figure for email at 35% DAU/MAU uses the 90% concentration model for activity email and a 4-hour scheduled send window for re-engagement email, as described in Section 1.2. These two peaks are assumed to overlap (conservative bound).

---

### 1.5 Viral Spike Model

**The problem with autoscaling as a spike response:** A spike that peaks in 5 minutes cannot be mitigated by autoscaling. Kubernetes HPA provisioning and pod warm-up time is 2–5 minutes under ideal conditions. By the time new workers are ready, the spike has already generated its backlog. Autoscaling handles sustained load increases, not instantaneous spikes.

**The correct mitigation is queue isolation, not worker scaling.** High-priority notifications (OTPs, direct messages, security alerts) run on dedicated workers that are never shared with social notification volume. A viral spike in social like/comment notifications does not affect these queues.

**Spike model for social-channel notifications:**

Worker throughput for social queue: 1,800/sec (out of 2,650/sec total, with the remainder reserved for high-priority channels).

Spike