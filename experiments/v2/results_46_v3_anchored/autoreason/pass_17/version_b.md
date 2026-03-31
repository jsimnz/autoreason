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
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product + E1 | Planning basis may be off by 4x; see §1.1 for budget cascade |
| Re-engagement email send rate | §1.1 | Week 2 | Product | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal + E1 | Default is synchronous preference check (no cache). Latency penalty: add ~12ms p99 to every notification dispatch. See §2.4 for full measurement methodology. This is the direct cost of inaction. |
| SendGrid enterprise contract | §1.1 | End of Month 1 | E1 | Self-hosted fallback activates; see §1.1 for full cascade |
| Reassessment option selection (capacity vs. batching) | §1.1 | Day 3 of any reassessment | Stakeholders | Default A activates — Tier 3 throughput reduced to 71% of normal, email digest paused. See §1.1 for complete specification. Note: Default A is an operational bridge, not a decision substitute. It buys time; it does not provision capacity. |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | Broadcast capability disabled at launch |

**On the compliance deadline specifically:** The conservative architecture (synchronous preference check) is compliant under TCPA/CAN-SPAM/GDPR but adds approximately 12ms p99 latency to every notification dispatch path. This figure is derived in Section 2.4 from the synchronous PostgreSQL round-trip under expected load. Stakeholders reading this table should treat that 12ms figure as the cost of inaction — the penalty the system carries if no decision arrives by Week 2. The cached architecture eliminates that latency but requires legal sign-off on the staleness window. If no decision is received by end of Week 2, the conservative architecture activates as the default. Month 1 engineering begins schema work in Week 3; the compliance choice has direct index and query-pattern implications that cannot be cleanly retrofitted after that point.

**On the reassessment sign-off item:** This sign-off is about which option stakeholders select during a reassessment (add capacity vs. implement more aggressive batching). It is distinct from Default A, which activates automatically at the 2,550/sec emergency threshold without requiring any decision. The sign-off table entry covers the Day 3 decision deadline within the formal reassessment process. If that deadline is missed, Default A activates as a bridge — but Default A is not a substitute for the capacity or batching decision. It reduces peak demand by approximately 10–13% and provides operational breathing room, not a permanent resolution. See §1.1 for the complete Default A specification, its limitations during the activation window, and the explicit constraint that it does not protect the system during the 8-minute rolling restart window.

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

**Why DAU scaling misses densification:** A user with 500 followers generates more like-notifications per post than a user with 50 followers, without any change in DAU. As the social graph matures, per-user notification rates rise even if DAU is flat. This is a different problem from DAU growth and requires a different response.

**The densification rate is not reliably known before launch.** A figure of 0.5–1.5 notifications/DAU/day per quarter reflects a plausible range for consumer social apps, but this app's graph structure — follow-heavy vs. mutual-friend-heavy, feed algorithm, content velocity — may produce rates outside this range in either direction. The 3x variation in the range produces dramatically different timelines:

| Densification Rate | Quarters to reach 13/DAU/day from 11 | Quarters to reach 17/DAU/day |
|-------------------|--------------------------------------|------------------------------|
| 0.5/DAU/day/quarter | 4 quarters (12 months) | 12 quarters (3 years) |
| 1.0/DAU/day/quarter | 2 quarters (6 months) | 6 quarters (18 months) |
| 1.5/DAU/day/quarter | 1.3 quarters (~4 months) | 4 quarters (12 months) |

**The correct response to this uncertainty is monitoring plus forward projection, not a more precise projection.** The densification rate will be observable in production data within 4–6 weeks of launch. At that point, the measured rate feeds directly into a forward projection: given the observed rate, how many weeks until the reassessment trigger (2,400/sec 3-day rolling peak) is breached? If that projection shows breach within 10 weeks — the minimum time to complete a reassessment and provision capacity under option (a) — the reassessment process initiates immediately, without waiting for the throughput trigger to fire. This is the proactive step that closes the gap between measurement and action. See the trigger design section below for the complete integration.

**The monitoring dashboard exposes both metrics as separate time-series:**
- **Total notification volume/day** — rises when DAU rises; response is proportional capacity addition
- **Notifications/DAU/day (7-day rolling average)** — rises when graph densifies with flat DAU; response is batching evaluation first, then capacity

Conflating these signals leads to the wrong intervention.

---

#### Headroom: Throughput Margin vs. Volume Buffer — Corrected Reconciliation

Two headroom figures appear in this document. A previous version of this analysis presented the 25% volume buffer as meaningful context; it is not, and that framing is withdrawn here.

**Throughput headroom (operational margin):** Worker capacity is sized at 2,650/sec sustained. The calculated peak at the High scenario is 2,540/sec. This is **4.3% operational headroom** — approximately 110/sec between current peak and the worker ceiling. This is the number that matters operationally.

**The 25% volume buffer is not a meaningful operational metric.** A 25% daily volume increase at the same concentration ratios produces a 25% peak rate increase: 2,540/sec × 1.25 = 3,175/sec, which exceeds the 2,650/sec ceiling by 20%. The volume buffer describes the distance to a problem that has already passed the ceiling — it is not a safety margin. It is withdrawn from operational framing in this document.

**The actual operational buffer is 4.3%: 110/sec.** All trigger thresholds and escalation procedures are calibrated against this figure, not against volume percentages.

**Deriving the ceiling breach point:**

```
Peak rate = (DAU × per-DAU-rate × concentration%) ÷ concentration_window_seconds

At High DAU (3.5M) and 90%/4-hour concentration:
Ceiling breach = (3,500,000 × R × 0.90) ÷ 14,400 = 2,650/sec
R = (2,650 × 14,400) ÷ (3,500,000 × 0.90)
R = 38,160,000 ÷ 3,150,000
R ≈ 12.1 notifications/DAU/day
```

The ceiling is breached at approximately **12.1/DAU/day** under the High DAU scenario. The planning basis is 11/DAU/day. The distance between them is 1.1/DAU/day — roughly 1 quarter of densification at the 1.0/DAU/day/quarter rate, or 10 weeks at the 1.5 rate.

---

#### Trigger Design: Lead Time Analysis

**The problem this section must solve:** The reassessment trigger must fire early enough that capacity can be added before the ceiling is breached. The trigger is useless if the ceiling is breached before the process completes.

**Process timeline under option (a) — add capacity:**

| Step | Duration |
|------|----------|
| Day 1: E3 produces revised projection | 1 day |
| Day 2: E1 presents options to stakeholders | 1 day |
| Day 3: Stakeholder decision | 1 day |
| Provisioning and validation | 3–5 business days |
| **Total: trigger to relief** | **6–8 calendar days minimum** |

**Required trigger lead time:** The trigger must fire at least 8 days before the ceiling is breached. If the rate is rising linearly at 1.0/DAU/day/quarter (approximately 0.011/DAU/day/week), the distance from trigger to ceiling must be at least 8 days of rate increase.

**Throughput-based trigger thresholds:**

| Threshold | Value | Derivation | Lead time at 1.0 rate | Lead time at 1.5 rate |
|-----------|-------|------------|----------------------|----------------------|
| Yellow alert | 7-day rolling average peak > **2,200/sec** | 86% of ceiling | ~19 days | ~13 days |
| Reassessment trigger | 3-day rolling peak > **2,400/sec** | 90.6% of ceiling | ~9 days | ~6 days |
| Emergency threshold | Any single day peak > **2,550/sec** | 96.2% of ceiling | Already above ceiling |

**The reassessment trigger provides adequate lead time at the 1.0/DAU/day/quarter densification rate (9 days vs. 8 days required) but is borderline at the 1.5 rate (6 days vs. 8 days required).** This is an acknowledged limitation. The mitigation is the forward-projection step described above: once the densification rate is measured at 4–6 weeks post-launch, if the rate is ≥1.3/DAU/day/quarter, the reassessment process initiates immediately rather than waiting for the throughput trigger. This provides approximately 10–12 weeks of lead time at that rate — well within the provisioning window.

**Integration with densification measurement:**

At 4–6 weeks post-launch, E3 computes the observed densification rate and answers one question: does the observed rate imply the reassessment trigger (2,400/sec) will be breached within 10 weeks? If yes, the reassessment process initiates immediately. If no, monitoring continues on the standard trigger schedule. This forward-projection step is added to the post-launch runbook as a mandatory Week 6 task, not an optional analysis.

**The per-DAU metric is retained as a diagnostic signal** to distinguish DAU growth from densification, but it is not the primary operational trigger. The throughput rate is what threatens the ceiling; that is what triggers the process.

---

#### Default A — Complete Specification Including Activation Window Limitation

Default A is an operational procedure, implementable without a code deployment. It activates automatically at the 2,550/sec emergency threshold. It also activates if stakeholders miss the Day 3 decision deadline during a formal reassessment.

**Activation window limitation — disclosed explicitly:** Default A requires a rolling restart of Tier 3 workers, estimated at 8 minutes. During those 8 minutes, the system is already above the 2,550/sec emergency threshold and Default A has not yet taken effect. This window is not protected by Default A. The following describes what happens during it and what does not:

- **What continues normally:** Tier 1 (DMs, OTPs) and Tier 2 (mentions, friend requests) workers are not restarted and are unaffected. In-app notifications continue at full rate. SMS is isolated and unaffected.
- **What is already degraded:** The system is above its sustained ceiling. Tier 3 queue depth is rising. No additional degradation is introduced by the restart; Tier 3 workers that are restarting are not processing messages they would otherwise have processed, which is equivalent to the throttling Default A implements.
- **The restart does not make things worse for Tier 3.** Tier 3 workers restart one at a time (rolling restart). During the 8-minute window, some Tier 3 workers are active at the old poll interval and some are offline mid-restart. The net Tier 3 throughput during the restart is lower than normal — consistent with the intended throttled state — but not zero. The transition is monotone: throughput decreases during the restart and stabilizes at the throttled rate after.
- **The 8-minute window is not a gap in protection for Tier 1 and Tier 2.** It is a transition period for Tier 3 only.

**Default A operational parameters:**

- Tier 3 worker poll interval increases from 500ms to 700ms → throughput reduced to approximately 71% of normal sustained rate
- Email digest and re-engagement scheduler pauses new dispatch; activity-triggered emails continue
- Push notifications for Tier 1 and Tier 2 are unaffected
- Default A persists until a stakeholder decision is received and the selected option is implemented
- E1 notifies stakeholders that Default A is active within 1 hour of activation
- Implementation: poll interval is a configuration value in the worker environment; rolling restart of Tier 3 workers only

**Default A demand reduction calculation:**

Tier 3 is typically 35–45% of push volume at peak. Reducing Tier 3 throughput to 71% of normal reduces effective peak demand by:

```
0.35 × (1 – 0.71) = 10.2%
0.45 × (1 – 0.71) = 13.1%
Range: 10–13%
```

At the 2,550/sec