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
| SMS budget and 2FA policy | §1.1 | Week 2 | Product + E1 | Planning basis may be off by 4x |
| Re-engagement email send rate | §1.1 | Week 2 | Product | SendGrid contract tier cannot be finalized |
| SendGrid enterprise contract | §1.1 | End of Month 1 | E1 | Self-hosted fallback activates; see §1.1 for full cascade |
| Opt-out compliance architecture | §2.4 | End of Week 3 | Legal + E1 | **Launch gate activates; system cannot go live** |
| Escalation default for capacity overruns | §1.1 | Before finalization | Stakeholders | Default A activates automatically |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | Broadcast capability disabled at launch |

**On compliance specifically:** Section 2.4 presents two compliant architectures. Legal must select one by end of Week 3. If no decision is received by that date, the **conservative architecture** (synchronous preference check, no cache) activates as the default. This architecture is compliant under TCPA/CAN-SPAM/GDPR but carries a latency penalty documented in Section 2.4. The system will not launch with the cache-with-staleness path absent legal confirmation. This is a hard launch gate, not a recommendation.

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

#### The Graph Densification Factor: Modeled, Not Ignored

Prior versions named graph densification as an unmodeled factor and then proceeded to use DAU-scaled projections throughout. This version treats it explicitly.

**Why DAU scaling misses densification:** A user with 500 followers generates more like-notifications per post than a user with 50 followers, without any change in DAU. As the social graph matures, per-user notification rates rise even if DAU is flat. The reassessment trigger (described below) catches this only if it manifests as higher observed per-DAU rates in the monitoring data — which it will, but only after the fact.

**The correct monitoring signal is notifications/DAU/day, not total notification volume.** If total volume rises because DAU rises, that is a different problem than if total volume rises because the graph is densifying. The responses differ:

- DAU growth → add worker capacity proportionally
- Graph densification → evaluate batching changes first, then add capacity

**Densification projection:** Based on typical social app graph growth curves, we model per-DAU notification rate increasing by 0.5–1.5 notifications/DAU/day per quarter as the graph densifies, independent of DAU growth. At the high end, this adds approximately 6 notifications/DAU/day over 12 months — moving from 11 to 17/DAU/day. The reassessment trigger at 13/DAU/day catches this before it becomes critical, but the response must distinguish the cause.

**Monitoring requirement added to Section 5:** The monitoring dashboard must expose both total notification volume and notifications/DAU/day as separate time-series metrics. Alerts fire on the per-DAU metric, not just total volume.

---

#### Headroom: Reconciling the Two Figures

The prior version stated "4% throughput headroom" and "25% volume headroom" in adjacent paragraphs without reconciling them. These are different things and must be stated clearly.

**Throughput headroom (operational margin):** Worker capacity is sized at 2,650/sec sustained. The calculated peak at the High scenario is 2,540/sec. This is **4.3% operational headroom** — the margin between peak demand and worker ceiling under the High scenario with current per-DAU rates. This is intentionally thin; it is not the growth buffer.

**Volume headroom (growth buffer):** The 25% volume headroom refers to the difference between the planning basis (38.5M/day) and the capacity ceiling (48.1M/day). This is a **daily volume buffer**, not a peak throughput buffer. A 25% daily volume increase at the same concentration ratios produces a 25% peak rate increase: 2,540/sec × 1.25 = 3,175/sec — which exceeds the 2,650/sec worker ceiling.

**The reconciliation:** The 25% volume headroom is not a throughput buffer. It is the trigger range — the distance between current planning basis and the point at which we must add worker capacity. The reassessment trigger fires at 13/DAU/day (45.5M/day at High DAU), which corresponds to a peak rate of approximately 2,844/sec — 7.3% above the current worker ceiling. **This means the reassessment process must complete and capacity must be added before the trigger threshold is reached, not after.** The trigger is a leading indicator requiring advance action, not a lagging alarm.

This changes the reassessment timeline requirement: the trigger fires at 13/DAU/day, but capacity additions must be operational before the system reaches 2,650/sec sustained. At a typical densification trajectory, there is approximately 4–6 weeks between trigger and ceiling breach. The 8-business-day reassessment process fits within this window only if it starts immediately when the trigger fires.

**Revised reassessment process:**

If observed notifications/DAU/day exceeds **12.5** (not 13 — earlier trigger to provide the full 8-day window before ceiling breach) on three consecutive days:

1. **Day 1:** E3 produces a revised capacity projection with a 60-day forward estimate. (Reduced from 5 business days — this is a monitoring-triggered event with pre-built runbooks, not a novel analysis.)
2. **Day 2:** E1 presents two costed options to stakeholders: (a) add worker capacity within existing infrastructure budget, or (b) implement more aggressive batching.
3. **Day 3:** Stakeholders select an option. If no decision by Day 3, **Default A** (throttle lower-priority queues to 70% of normal rate) activates automatically and persists until a decision is made.
4. If option (b) is selected, batching changes consume approximately 2 engineer-weeks from the active workstream. E1 communicates the specific milestone impact within 24 hours.
5. If option (a) is selected, new worker capacity must be provisioned and load-tested within 5 business days of the decision.

**The monitoring signal that fires this trigger is notifications/DAU/day, not total volume** — for the densification reasons described above.

---

#### Viral Spike Model

**The problem with "we'll monitor and respond":** The system launches in Month 2. If a significant viral event occurs in Month 3, the response time to add worker capacity is measured in hours to days. Monitoring identifies the problem; it does not prevent the delay. The prior version began this section and was cut off. This version completes it.

**We cannot size workers for every conceivable spike.** A post going viral on a 10M MAU platform can generate 10–50x normal notification rates for the affected users, but this load is concentrated on a small fraction of total users. The question is not "can we handle the theoretical maximum?" but "what is the right degradation behavior when we cannot?"

**Spike classification and response:**

| Spike Type | Trigger | Expected Duration | Response |
|------------|---------|-------------------|----------|
| Micro-spike | Single viral post, <5x normal rate | Minutes to 1 hour | Absorbed by queue depth; no action |
| Mid-spike | Trending content, 5–15x for affected users | 1–4 hours | Priority queue throttling; lower-priority channels shed load |
| Major spike | Platform-wide event, 15–50x | 4–12 hours | Automatic load shedding activates; see below |
| Sustained overload | >12 hours above ceiling | 12+ hours | Escalation to stakeholders; capacity addition or batching change |

**Automatic load-shedding behavior (not "we'll respond"):**

When the push queue depth exceeds 500,000 messages (approximately 3 minutes of backlog at normal peak rates), the following happens automatically, without human intervention:

1. **Batch-eligible notifications are held.** Like and comment notifications that are within their batching window are not dispatched until queue depth drops below 250,000. This is the highest-leverage lever: at peak, batching can reduce push volume by 40–60%.
2. **Re-engagement and digest emails are paused.** The email scheduler stops dispatching non-critical emails. Activity emails (direct triggers) continue.
3. **In-app notifications continue at full rate.** In-app delivery does not touch the push queue. Users on the app still see notifications.
4. **SMS is unaffected.** The SMS queue is isolated; it does not share workers with push.

**What we explicitly do not do during a spike:**
- Drop OTP or authentication SMS messages
- Drop direct message notifications (highest priority push)
- Drop in-app notifications for active sessions

**What we accept as degraded behavior during a major spike:**
- Like and comment notifications may be delayed by up to 2 hours
- Re-engagement emails may be delayed by up to 24 hours
- Some lower-priority push notifications may be coalesced beyond normal batching windows

**Why this is the right tradeoff:** The users most affected by a viral spike are the ones receiving high volumes of like/comment notifications — exactly the notifications that are least time-sensitive. The users least affected are those receiving DMs and OTPs — exactly the notifications that are most time-sensitive. The load-shedding hierarchy aligns with user value.

**Spike capacity ceiling:** Workers are sized at 2,650/sec. The queue absorbs bursts. At 500,000 message queue depth with automatic load shedding, the effective burst capacity is approximately 15 minutes of 3x normal peak before any notifications are meaningfully delayed. For the vast majority of viral events, this is sufficient. For a true platform-wide event (15x+ sustained), degraded behavior is the correct response — adding capacity in real time is not achievable within a 6-month build window for a 4-engineer team.

**Runbook ownership:** E3 owns the spike response runbook. It must be written and reviewed before Month 2 launch. The automatic behaviors above must be implemented and tested before launch; manual intervention steps are documented for the human-in-the-loop phases.

---

#### SMS Volume

SMS in this app is primarily OTP and authentication. Social push concentration models (90%/4-hour) do not apply.

**The 1% DAU assumption requires explicit grounding.** The prior version stated this figure without basis. Here is the derivation:

- Daily active users who log in from a new device or browser: approximately 3–5% of DAU (industry range for consumer social apps)
- Of those, fraction requiring SMS 2FA: depends on 2FA enrollment rate. At 20% enrollment, 2FA triggers on 20% of new-device logins = 0.6–1.0% of DAU
- Additional triggers: password resets (~0.1% DAU/day), suspicious login alerts (~0.05% DAU/day)
- **Total: approximately 0.75–1.15% of DAU/day**

The 1% planning basis sits at the midpoint of this range. It is sensitive to two product decisions that may already be made:

1. **2FA enrollment policy:** If the product mandates 2FA for all users, the SMS rate rises to 3–5% of DAU on days users access from new devices. If 2FA is opt-in with low adoption, it may be 0.3–0.5%.
2. **Bot/fraud activity:** High bot registration rates can generate large volumes of SMS verification at account creation, which is not captured in the DAU-based model.

**Product must confirm the 2FA policy by Week 2.** The planning basis of ~$17K/month can reach $67.5K/month under aggressive 2FA — this is a product decision with a direct budget consequence, not a modeling uncertainty.

**SMS concentration model:**

| SMS Category | Concentration Model | Basis |
|-------------|--------------------|----|
| OTP / authentication | 60% in 6 hours | Login events distributed across active hours |
| Re-engagement triggered auth | 40% in 8 hours | Deliberately distributed by scheduler |
| **Blended (planning basis)** | **65% in 6 hours** | Weighted toward OTP |

**SMS volume (High scenario, 1% DAU = 35,000/day):**

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

**Planning basis: ~$17K/month** (1% DAU, blended rate ~$0.