# Notification System Design — Synthesized
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
| SMS budget and 2FA policy | §1.1 | Week 2 | Product + E1 | Planning basis may be off by 4x; budget exposure up to $67.5K/month |
| Re-engagement email send rate | §1.1 | Week 2 | Product | SendGrid contract tier cannot be finalized |
| SendGrid enterprise contract | §1.1 | End of Month 1 | E1 | Self-hosted fallback activates; Month 2 in-app milestone slips to Month 3 |
| Opt-out compliance architecture | §2.4 | End of Week 3 | Legal + E1 | **Hard launch gate: system cannot go live** |
| Escalation default for capacity overruns | §1.1 | Before finalization | Stakeholders | Default A (priority throttling) activates automatically |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | Broadcast capability disabled at launch |

**On compliance specifically:** Section 2.4 presents two compliant architectures. Legal must select one by end of Week 3. If no decision is received, the **conservative architecture** (synchronous preference check, no cache) activates as the default. This is compliant under TCPA/CAN-SPAM/GDPR but carries a latency penalty documented in Section 2.4. The system will not launch with the cache-with-staleness path absent explicit legal confirmation. This is a hard launch gate, not a recommendation.

**On the engineer-week budget:** The described work fits within 96 engineer-weeks under the base case. Two scenarios break the budget: the self-hosted email fallback (6–8 engineer-weeks, displacing the Month 2 in-app milestone) and option (b) batching changes triggered by the capacity reassessment process (2 engineer-weeks from the active workstream). Both trigger explicit stakeholder conversations, not silent scope absorption.

**On internal consistency:** All calculations in this document use a single named scenario table. Worker sizing, spike calculations, and peak throughput all use the same scenario inputs. Any calculation that uses inputs from different scenarios is a document defect.

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

**Worker sizing input: 38.5M/day (High scenario, 11/DAU/day).** All downstream calculations use this figure.

---

#### The Graph Densification Factor: Modeled, Not Ignored

**Why DAU scaling alone misses densification:** A user with 500 followers generates more like-notifications per post than a user with 50, without any change in DAU. As the social graph matures, per-user notification rates rise even if DAU is flat. The correct monitoring signal is therefore **notifications/DAU/day**, not total notification volume. These require different responses:

- DAU growth → add worker capacity proportionally
- Graph densification → evaluate batching changes first, then add capacity

**Densification projection:** Based on typical social app graph growth curves, per-DAU notification rate is expected to increase by 0.5–1.5 notifications/DAU/day per quarter independent of DAU growth. At the high end, this adds approximately 6 notifications/DAU/day over 12 months — moving from 11 to 17/DAU/day. The reassessment trigger catches this before it becomes critical, but the response must distinguish the cause.

**Monitoring requirement (Section 5):** The monitoring dashboard must expose both total notification volume and notifications/DAU/day as separate time-series metrics. Alerts fire on the per-DAU metric, not just total volume.

---

#### Headroom: Two Distinct Concepts, Not Interchangeable

The prior versions stated "4% throughput headroom" and "25% volume headroom" in adjacent paragraphs without reconciling them. These are different things.

**Throughput headroom (operational margin):** Worker capacity is sized at 2,650/sec sustained. Calculated peak at the High scenario is 2,540/sec. This is **4.3% operational headroom** — the margin between peak demand and worker ceiling under current per-DAU rates. This is intentionally thin; it is not the growth buffer.

**Volume headroom (growth buffer):** Workers are sized to handle 48.1M/day (2,650/sec × 86,400 × utilization factor). Against the 38.5M/day planning basis, this is **25% daily volume headroom**. However, a 25% daily volume increase at the same concentration ratios produces a 25% peak rate increase: 2,540/sec × 1.25 = 3,175/sec — which exceeds the 2,650/sec worker ceiling.

**The reconciliation:** The 25% volume headroom is not a throughput buffer. It is the trigger range — the distance between current planning basis and the point at which worker capacity must be added. The reassessment trigger fires at 12.5/DAU/day (not 13 — the earlier trigger provides the full reassessment window before ceiling breach). At typical densification trajectory, there are approximately 4–6 weeks between trigger and ceiling breach. The reassessment process below must complete and capacity must be operational before the ceiling is reached, not after the trigger fires.

---

#### Capacity Reassessment Process

If observed notifications/DAU/day exceeds **12.5** on three consecutive days:

1. **Day 1:** E3 produces a revised capacity projection with a 60-day forward estimate. (This is a monitoring-triggered event with pre-built runbooks, not a novel analysis.)
2. **Day 2:** E1 presents two costed options to stakeholders: (a) add worker capacity within existing infrastructure budget, or (b) implement more aggressive batching to reduce effective notification rate.
3. **Day 3:** Stakeholders select an option. If no decision by Day 3, **Default A** (throttle lower-priority queues to 70% of normal rate) activates automatically and persists until a decision is made.
4. If option (b) is selected, batching changes consume approximately 2 engineer-weeks from the active workstream. E1 communicates the specific milestone impact within 24 hours.
5. If option (a) is selected, new worker capacity must be provisioned and load-tested within 5 business days of the decision.

---

#### Viral Spike Model

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days. Monitoring identifies the problem; it does not prevent the delay. We cannot size workers for every conceivable spike. The question is not "can we handle the theoretical maximum?" but "what is the right degradation behavior when we cannot?"

**Spike classification and response:**

| Spike Type | Trigger | Expected Duration | Response |
|------------|---------|-------------------|----------|
| Micro-spike | Single viral post, <5x normal rate | Minutes to 1 hour | Absorbed by queue depth; no action |
| Mid-spike | Trending content, 5–15x for affected users | 1–4 hours | Priority queue throttling; lower-priority channels shed load |
| Major spike | Platform-wide event, 15–50x | 4–12 hours | Automatic load shedding activates; see below |
| Sustained overload | >12 hours above ceiling | 12+ hours | Escalation to stakeholders; capacity addition or batching change |

**Automatic load-shedding behavior** — these actions are implemented in code and require no human intervention:

When push queue depth exceeds 500,000 messages (approximately 3 minutes of backlog at normal peak rates):

1. **Batch-eligible notifications are held.** Like and comment notifications within their batching window are not dispatched until queue depth drops below 250,000. At peak, batching can reduce push volume by 40–60%.
2. **Re-engagement and digest emails are paused.** The scheduler stops dispatching non-critical emails. Activity emails (direct event triggers) continue.
3. **In-app notifications continue at full rate.** In-app delivery does not touch the push queue; users on the app still see notifications.
4. **SMS is unaffected.** The SMS queue is isolated and does not share workers with push.

**What we explicitly do not shed during a spike:**
- OTP or authentication SMS messages
- Direct message push notifications (highest priority push)
- In-app notifications for active sessions

**What we accept as degraded behavior during a major spike:**
- Like and comment notifications may be delayed up to 2 hours
- Re-engagement emails may be delayed up to 24 hours
- Some lower-priority push notifications may be coalesced beyond normal batching windows

**Why this is the right tradeoff:** The users most affected by a viral spike are receiving high volumes of like/comment notifications — exactly the least time-sensitive. The users least affected are receiving DMs and OTPs — exactly the most time-sensitive. The load-shedding hierarchy aligns with user value.

**Spike capacity ceiling:** Workers are sized at 2,650/sec. The queue absorbs bursts. At 500,000 message queue depth with automatic load shedding, the effective burst capacity is approximately 15 minutes of 3x normal peak before any notifications are meaningfully delayed. For the vast majority of viral events, this is sufficient. For a true platform-wide event (15x+ sustained), degraded behavior is the correct response — real-time capacity addition is not achievable within a 6-month build window for a 4-engineer team.

**Runbook ownership:** E3 owns the spike response runbook. It must be written and reviewed before Month 2 launch. The automatic behaviors above must be implemented and tested before launch; manual steps are documented for human-in-the-loop phases.

---

#### SMS Volume

SMS in this app is primarily OTP and authentication. The social push concentration model (90%/4-hour) does not apply.

**Why SMS concentration differs from social push:** Social push notifications peak during engagement hours — evenings and weekends. OTP and authentication SMS messages are triggered by login events distributed more evenly across active hours. Re-engagement campaigns that trigger authentication flows are deliberately spread by the sending scheduler.

**The 1% DAU assumption — derivation, not assertion:**

- Daily active users logging in from a new device or browser: approximately 3–5% of DAU
- Of those, fraction requiring SMS 2FA: at 20% enrollment, 2FA triggers on ~20% of new-device logins = 0.6–1.0% of DAU
- Additional triggers: password resets (~0.1% DAU/day), suspicious login alerts (~0.05% DAU/day)
- **Total: approximately 0.75–1.15% of DAU/day**

The 1% planning basis sits at the midpoint. It is sensitive to two product decisions:

1. **2FA enrollment policy:** Mandatory 2FA raises the SMS rate to 3–5% of DAU on days users access from new devices. Opt-in with low adoption may be 0.3–0.5%.
2. **Bot/fraud activity:** High bot registration rates generate large SMS verification volumes at account creation, not captured in the DAU-based model.

**Product must confirm the 2FA policy by Week 2.** The planning basis of ~$17K/month can reach $67.5K/month under aggressive 2FA — this is a product decision with a direct budget consequence.

**SMS concentration model:**

| SMS Category | Concentration Model | Basis |
|-------------|--------------------|----|
| OTP / authentication | 60% in 6 hours | Login events distributed across active hours |
| Re-engagement triggered auth | 40% in 8 hours | Deliberately distributed by scheduler |
| **Blended (planning basis)** | **65% in 6 hours** | Weighted toward OTP; conservative |

**SMS peak rates (High scenario, 35,000/day):**

```
Peak rate (blended 65%/6hr)    = (35,000 × 0.65) ÷ 21,600 = 1.05/sec
Peak rate (worst-case 90%/4hr) = (35,000 × 0.90) ÷ 14,400 = 2.19/sec
```

SMS peak rates are low enough that concentration model choice does not materially affect infrastructure sizing. The SMS queue is sized by reliability requirements, not throughput.

**SMS budget sensitivity:**

| Policy | SMS/day | Monthly SMS | Cost at $0.0075/SMS | Cost at $0.015/SMS |
|--------|---------|------------|--------------------|--------------------|
| 1% DAU, standard auth | 35,000 | 1.05M | $7,875 | $15,750 |
| 3% DAU, aggressive 2FA | 105,000 | 3.15M | $23,625 | $47,250 |
| 5% DAU, all logins | 175,000 | 5.25M | $39,375 | $78,750 |

**Planning basis: ~$17K/month** (1% DAU, blended rate ~$0.016/SMS including international). Realistic worst-case under aggressive 2FA: **$67.5K/month**.

---

#### Email Volume

Email notifications divide into two categories with different denominators and different concentration behaviors. Applying a single concentration model to both is an error that inflates peak rate estimates by approximately 35%.

**Activity emails** (event-driven): 40% of DAU have email activity notifications enabled. At High scenario: 3.5M × 0.40 = 1.4M activity emails/day. These follow social engagement concentration: **90% in 4 hours** is appropriate.

**Re-engagement and digest emails** (scheduled): At High scenario, lapsed users = 10M − 3.5M = 6.5M.

**Critical architecture requirement on scheduled sends:** Scheduled re-engagement emails must be dispatched by a rate-limited scheduler, not batch-dumped at a scheduled time. If the scheduler fires all sends simultaneously:

- At 30% re-engagement: instantaneous peak exceeds 600/sec
- This is a contract-breaking event with SendGrid and a deliverability failure

**This is an architectural