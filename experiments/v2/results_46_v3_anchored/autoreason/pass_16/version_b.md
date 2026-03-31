# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

### Six Items Requiring Explicit Sign-Off Before This Design Is Finalized

| Item | Section | Decision Deadline | Owner | Consequence of Miss |
|------|---------|-------------------|-------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product + E1 | Planning basis used downstream before confirmation; see §1.1 for cascade |
| Re-engagement email send rate | §1.1 | Week 2 | Product | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal + E1 | Schema decisions in Month 1 will be made without this input; rework risk is high |
| SendGrid enterprise contract | §1.1 | End of Month 1 | E1 | Self-hosted fallback activates; see §1.1 for full cascade |
| Escalation default for capacity overruns | §1.1 | Before finalization | Stakeholders | Default A activates automatically; see §1.1 for complete specification |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | Broadcast capability disabled at launch |

**On compliance specifically:** Section 2.4 presents two compliant architectures. Legal must select one by end of **Week 2**, not Week 3. The reason for the earlier deadline is that the compliance architecture choice has direct schema implications — synchronous preference check requires different query patterns and index structures than the cached path — and Month 1 engineering will begin making those schema decisions in Week 3. A Week 3 decision arrives after those decisions are already in flight. If no decision is received by end of Week 2, the **conservative architecture** (synchronous preference check, no cache) activates as the default. This architecture is compliant under TCPA/CAN-SPAM/GDPR but carries a latency penalty documented in Section 2.4. The system will not launch with the cache-with-staleness path absent legal confirmation. This is a hard launch gate, not a recommendation.

**On Default A:** Default A is a fully specified operational procedure, not a named placeholder. The complete specification appears in §1.1 under "Reassessment Process." In brief: when stakeholders miss the Day 3 decision deadline during a reassessment, the push and email queues for Tier 3 (batch-eligible social) notifications are rate-limited to 70% of their current sustained throughput, implemented by reducing the worker poll rate for those queues from 500ms to 700ms intervals. This persists until a stakeholder decision is received and implemented. The specification is complete enough to implement without further clarification.

**On the engineer-week budget:** Section 1.3 contains a complete aggregate engineer-week accounting. The described work fits within 96 engineer-weeks under the base case. The self-hosted email fallback and option (b) batching changes are the two scenarios that break the budget; both trigger explicit stakeholder conversations, not silent scope absorption.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### Scenario Framework

All calculations use one of three named scenarios:

| Scenario | DAU/MAU | DAU | Usage in This Document |
|----------|---------|-----|----------------------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Worker sizing and spike calculations throughout |

**Worker sizing uses the High scenario throughout.** Spike calculations use the High scenario plus explicit spike multipliers defined in the viral spike model below.

---

#### Push and In-App Volume

**Event classes and per-DAU rates:**

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery; see §2.2 |
| Comments on posts | 1–4 | Batched similarly |
| New followers/friend requests | 0.5–2 | |
| Direct messages received | 2–6 | Power users skew high |
| Mentions and tags | 0.5–2 | |
| System/product notifications | 0.5–1 | Capped by product policy |

Raw event total: 7.5–23/DAU/day. After batching, effective delivered: **8–14/DAU/day**. Planning basis: **11/DAU/day**.

**Push + In-App volume by scenario:**

| Scenario | DAU | 8/DAU/day | 11/DAU/day | 14/DAU/day |
|----------|-----|-----------|------------|------------|
| Low | 1.5M | 12M | 16.5M | 21M |
| Base | 2.5M | 20M | 27.5M | 35M |
| High | 3.5M | 28M | **38.5M** | 49M |

**Worker sizing input: 38.5M/day (High scenario, 11/DAU/day).**

---

#### The Graph Densification Factor: Modeled with Explicit Uncertainty

**Why DAU scaling misses densification:** A user with 500 followers generates more like-notifications per post than a user with 50 followers, without any change in DAU. As the social graph matures, per-user notification rates rise even if DAU is flat.

**The densification rate is not reliably known.** The figure of 0.5–1.5 notifications/DAU/day per quarter does not come from a published reference this team can validate — it reflects a plausible range for consumer social apps, but this app's graph structure (follow-heavy vs. mutual-friend-heavy, feed algorithm, content velocity) may produce rates outside this range in either direction. A 3x variation in densification rate (0.5 vs. 1.5 per quarter) produces dramatically different timelines:

| Densification Rate | Quarters to reach 13/DAU/day from 11 | Quarters to reach 17/DAU/day |
|-------------------|--------------------------------------|------------------------------|
| 0.5/DAU/day/quarter | 4 quarters (12 months) | 12 quarters (3 years) |
| 1.0/DAU/day/quarter | 2 quarters (6 months) | 6 quarters (18 months) |
| 1.5/DAU/day/quarter | 1.3 quarters (~4 months) | 4 quarters (12 months) |

**Consequence:** At the high end of the densification range, the reassessment trigger could fire as early as Month 4 of operation — before the team has fully completed the Month 6 hardening phase. The planning basis cannot treat densification as a distant concern.

**The correct response to this uncertainty is not a more precise projection — it is monitoring.** The densification rate will be observable in production data within 4–6 weeks of launch, at which point a real rate can replace the range. Until then, the planning basis uses a **conservative 1.0/DAU/day/quarter** (middle of the range), and the trigger threshold is set to fire early enough that even the high-end scenario (1.5/quarter) leaves adequate response time.

**The monitoring signal is notifications/DAU/day, not total notification volume.** If total volume rises because DAU rises, the response is adding worker capacity proportionally. If total volume rises because the per-DAU rate is rising with flat DAU, the first response is evaluating batching changes. These are different problems with different responses; the metric must distinguish them.

**Monitoring requirement:** The monitoring dashboard must expose both total notification volume and notifications/DAU/day as separate time-series metrics. Alerts fire on the per-DAU metric. The per-DAU rate is computed daily and reported as a 7-day rolling average to reduce day-of-week noise.

---

#### Headroom: Throughput Margin vs. Volume Buffer — Complete Reconciliation

Two headroom figures appear in this document. They measure different things and must not be conflated.

**Throughput headroom (operational margin):** Worker capacity is sized at 2,650/sec sustained. The calculated peak at the High scenario is 2,540/sec. This is **4.3% operational headroom** — the margin between peak demand and worker ceiling under the High scenario with current per-DAU rates. This margin is intentionally thin; it is not the growth buffer.

**Volume headroom (growth buffer):** The difference between the planning basis (38.5M/day) and the capacity ceiling (48.1M/day) is approximately 25% in daily volume terms. This sounds like substantial buffer. It is not equivalent to 25% throughput buffer.

**The reconciliation:** A 25% daily volume increase at the same concentration ratios produces a 25% peak rate increase: 2,540/sec × 1.25 = 3,175/sec. This exceeds the 2,650/sec worker ceiling by 20%. The 25% volume buffer is therefore the distance between current planning basis and the point at which we must have already added worker capacity — not the distance at which we begin adding it.

**Deriving the trigger-to-ceiling timeline:** The reassessment trigger fires at 12.5/DAU/day (7-day rolling average). The worker ceiling is reached at the per-DAU rate that produces 2,650/sec peak. Working backward from the peak rate formula:

```
Peak rate = (DAU × per-DAU-rate × concentration%) ÷ concentration_window_seconds

At High DAU (3.5M) and 90%/4-hour concentration:
2,650/sec = (3,500,000 × R × 0.90) ÷ 14,400
R = (2,650 × 14,400) ÷ (3,500,000 × 0.90)
R = 38,160,000 ÷ 3,150,000
R = 12.11 notifications/DAU/day
```

**This means the worker ceiling is reached at approximately 12.1/DAU/day under the High DAU scenario with current concentration assumptions.** The trigger at 12.5/DAU/day fires *after* the ceiling is already breached under this scenario.

This is a problem with the prior trigger design, and it requires a corrected approach.

**Corrected trigger design:**

The trigger cannot be set as a per-DAU rate threshold alone, because the ceiling per-DAU rate varies with DAU. Instead, the trigger fires on **observed peak throughput rate**, not per-DAU volume:

- **Yellow alert:** 7-day rolling average peak rate exceeds **2,200/sec** (83% of ceiling). This is the monitoring signal that densification or DAU growth is accelerating.
- **Reassessment trigger:** 3-day rolling peak rate exceeds **2,400/sec** (91% of ceiling). This initiates the formal reassessment process.
- **Emergency threshold:** Peak rate exceeds **2,550/sec** on any single day. This activates Default A immediately, without waiting for the reassessment process.

The per-DAU metric (notifications/DAU/day) is retained as a diagnostic signal to distinguish DAU growth from densification, but it is not the trigger. The trigger is the throughput rate, because that is what actually threatens the ceiling.

**Revised reassessment process (triggered by 2,400/sec 3-day rolling average):**

1. **Day 1:** E3 produces a revised capacity projection with a 30-day forward estimate, using the observed peak rate trajectory (not the densification model). Runbook is pre-built; this is execution, not novel analysis.
2. **Day 2:** E1 presents two costed options to stakeholders:
   - **(a) Add worker capacity** within existing infrastructure budget. Can be provisioned in 3–5 business days.
   - **(b) Implement more aggressive batching.** Reduces peak rate by an estimated 15–25% but consumes approximately 2 engineer-weeks from the active workstream. E1 states the specific milestone impact at presentation time.
3. **Day 3:** Stakeholders select an option. If no decision is received by end of Day 3, **Default A activates automatically.**

**Default A — Complete Specification:**

Default A is not a named placeholder. It is the following operational procedure, implementable without further design decisions:

- The Tier 3 queue (batch-eligible social notifications: likes, comments, follow suggestions) has its worker poll interval increased from 500ms to 700ms. This reduces Tier 3 throughput to approximately 71% of normal sustained rate.
- The email digest and re-engagement scheduler pauses new dispatch. Activity-triggered emails (direct user actions) continue unaffected.
- Push notifications for Tier 1 (DMs, OTPs) and Tier 2 (mentions, friend requests) are unaffected.
- Default A persists until a stakeholder decision is received and the selected option is implemented. E1 notifies stakeholders that Default A is active within 1 hour of activation.
- Default A does not require a code deployment. The poll interval is a configuration value in the worker environment; changing it requires a rolling restart of Tier 3 workers only (estimated 8 minutes).

Default A reduces effective peak throughput demand by approximately 25–35% (Tier 3 is typically 35–45% of push volume at peak). At the 2,550/sec emergency threshold, Default A brings effective demand to approximately 1,660–1,912/sec — well within the 2,650/sec ceiling. This provides operational breathing room while the longer-term option is implemented.

**If option (b) is selected:** Batching changes consume approximately 2 engineer-weeks from the active workstream. E1 communicates the specific milestone impact within 24 hours of the stakeholder decision. Default A remains active until the batching changes are deployed and validated.

**If option (a) is selected:** New worker capacity must be provisioned and load-tested within 5 business days of the decision. Default A remains active until new capacity is confirmed operational.

---

#### Viral Spike Model

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days. Monitoring identifies the problem; it does not prevent the delay.

**We cannot size workers for every conceivable spike.** A post going viral on a 10M MAU platform can generate 10–50x normal notification rates for the affected users, but this load is concentrated on a small fraction of total users. The question is not "can we handle the theoretical maximum?" but "what is the right degradation behavior when we cannot?"

**Spike classification and response:**

| Spike Type | Trigger | Expected Duration | Response |
|------------|---------|-------------------|----------|
| Micro-spike | Single viral post, <5x normal rate | Minutes to 1 hour | Absorbed by queue depth; no action |
| Mid-spike | Trending content, 5–15x for affected users | 1–4 hours | Priority queue throttling; lower-priority channels shed load |
| Major spike | Platform-wide event, 15–50x | 4–12 hours | Automatic load shedding activates; see below |
| Sustained overload | >12 hours above ceiling | 12+ hours | Escalation to stakeholders; capacity addition or batching change |

**Automatic load-shedding thresholds and hysteresis:**

When the push queue depth exceeds **450,000 messages**, load shedding activates. The threshold derivation:

```
Normal peak rate: 2,540/sec
Target "3 minutes of backlog" at peak: 2,540 × 180 = 457,200 messages
Rounded to: 450,000 (conservative, fires slightly early)
```

Load shedding deactivates when queue depth falls below **200,000 messages** (not 225,000 — the asymmetry is intentional).

**Why 200,000, not 225,000 (half of 450,000)?** A symmetric threshold (activate at X, deactivate at X/2) on a bursty queue creates oscillation risk: load shedding reduces inflow, queue drains toward the resume threshold, shedding deactivates, inflow resumes