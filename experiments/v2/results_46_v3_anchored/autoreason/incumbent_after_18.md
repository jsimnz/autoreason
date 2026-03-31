# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

**Three design choices from Version X materially improve this synthesis:**

- The viral spike model is now defined, with a four-type taxonomy and explicit sizing rationale. Worker ceiling calculations use spike multipliers, not just the High scenario.
- The Default A demand-reduction claim is corrected. Throttling dispatch does not reduce arrival rate; it grows queues. The revised specification is honest about what Default A does and does not do, including the activation window limitation.
- Default B (Tier 3 suspension) is added for load levels between 2,650 and 4,000/sec where Default A's partial throttling is insufficient.

**Three problems are structural and cannot be fully resolved within the current design scope.** They are documented as acknowledged limitations with explicit mitigations:

- The 4.3% headroom problem — addressed by redefining the ceiling with spike modeling included and by making tiered degradation the designed response, not a failure mode.
- The reassessment trigger lead time gap at high densification rates — addressed by converting the manual runbook step to an automated alert rather than a person remembering.
- The compliance architecture lock-in risk — addressed by treating the Week 2 deadline as an architectural decision, not a latency preference.

---

### Six Items Requiring Explicit Sign-Off Before This Design Is Finalized

The owner column identifies who must decide, not which engineer implements.

| Item | Section | Decision Deadline | Owner (who must decide) | Engineer Role | Consequence of Miss |
|------|---------|-------------------|------------------------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model input | Planning basis may be off by 4×; SMS channel sizing is blocked |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E1 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal | E1 implements whichever is chosen | Default is synchronous (no cache). Direct cost of inaction: ~12ms p99 added to every dispatch path. See §2.4 for measurement methodology. Schema work begins Week 3 and is not cleanly reversible after that point. |
| SendGrid enterprise contract | §1.1 | End of Month 1 | Procurement/Finance | E1 provides technical requirements | Self-hosted fallback activates; see §6.2 for full cost and timeline |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Product + Engineering leadership | E1 presents costed options | Default A activates automatically. Default A is a bridge, not a resolution. |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | E1 implements rate limiting once policy is defined | Broadcast capability disabled at launch |

**On the compliance deadline — the actual risk is architectural, not latency.** The prior framing — "decide by Week 2 or pay 12ms latency" — understates the real consequence. The synchronous and cached architectures have different data access patterns across all four channel dispatch paths. If the synchronous default is built into Month 1 schema work and Legal approves the cached architecture in Month 2, the retrofit requires changing query patterns across every dispatch path — not adding a cache layer. This is 1–2 engineer-weeks of rework during the highest-velocity period of the project. The deadline is about avoiding an architectural redo during Month 2 sprint work. Legal needs to understand this framing, not the latency framing.

**On engineer-week budget:** Section 1.3 contains a complete aggregate engineer-week accounting. The described work fits within 96 engineer-weeks under the base case. The self-hosted email fallback and option (b) batching changes are the two scenarios that break the budget; both trigger explicit stakeholder conversations, not silent scope absorption.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage in This Document |
|----------|---------|-----|----------------------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Worker sizing baseline |
| **Spike** | **35% DAU + spike multiplier** | **3.5M + event** | **Worker ceiling and infrastructure sizing** |

**Worker ceiling sizing uses the Spike scenario, not the High scenario.** Spike calculations use the High scenario plus explicit multipliers from the viral spike model below.

---

#### Viral Spike Model

A social app's worst-case notification load is not gradual densification. It is a sudden viral spike — a post, live event, or breaking news cycle — that drives a large fraction of the user base to interact simultaneously. The notification system must handle this without shedding Tier 1 and Tier 2 traffic.

**Spike taxonomy:**

| Spike Type | Description | Historical Analog | Peak Multiplier vs. Normal | Duration |
|------------|-------------|-------------------|---------------------------|----------|
| Type 1: Content viral | Single post goes viral; reply/like storm | Twitter trending content | 2–3× | 30–90 min |
| Type 2: Live event | Sports, election, product launch | Super Bowl Twitter traffic | 3–5× | 2–4 hours |
| Type 3: Platform event | App feature launch, push to all users | App store feature placement | 1.5–2× | 4–8 hours |
| Type 4: External crisis | News event drives mass sign-ups and activity | Breaking news events | 4–8× | 1–6 hours |

**Planning basis for infrastructure sizing: Type 2 spike, 4× multiplier, 2-hour duration.**

Rationale: Type 4 spikes at 8× are real but rare and represent a failure mode, not a design target — no notification system at this scale absorbs 8× peaks gracefully without shedding non-critical load. Type 1 spikes at 2–3× are the most common and the most important to absorb without degradation. Type 2 at 4× represents the upper boundary of what the system should handle cleanly. This is a deliberate tradeoff: we are not designing for Type 4 events. If one occurs, the defined response is aggressive Tier 3 shedding (Default B activates immediately) and stakeholder communication.

**Spike concentration assumption:** Viral spikes concentrate in the same peak window as normal traffic — 6–10pm local time, mapping to 9–11pm UTC for US-heavy apps. The spike multiplier applies to the already-concentrated peak rate, not the daily average.

**Spike peak rate calculation:**

```
Normal peak rate (High scenario):
= (3,500,000 DAU × 11/DAU/day × 0.90 concentration) ÷ 14,400 seconds
= 34,650,000 ÷ 14,400
= 2,406/sec

Type 2 spike at 4× multiplier:
= 2,406 × 4 = 9,624/sec

Type 1 spike at 2.5× multiplier (most common):
= 2,406 × 2.5 = 6,015/sec
```

**The worker ceiling is not sized to absorb a 4× spike in full.** That would require approximately 9,600/sec sustained throughput — four times the current worker fleet — which is not economically justified for events lasting 2 hours. Instead, the design uses **tiered degradation**:

| Load Level | Response | Tier 1 + 2 Impact | Tier 3 Impact |
|------------|----------|-------------------|---------------|
| < 2,400/sec | Normal operation | None | None |
| 2,400–2,650/sec | Yellow alert; reassessment trigger | None | None |
| 2,650–3,800/sec | Default A active | None | Throughput reduced to ~71% of normal; queue grows |
| > 3,800/sec sustained 5+ min | Default B: Tier 3 suspended | None | Tier 3 suspended; processed after spike |
| > 6,000/sec sustained 5+ min | Tier 2 rate-limited to 50% | Tier 2 delayed by minutes | Tier 3 suspended |
| > 8,000/sec (Type 4) | Tier 1 only; all else queued | Tier 2 queued | Tier 3 queued |

This is not a failure mode taxonomy. It is the designed response. Tier 1 and Tier 2 notifications are protected at all load levels up to 6,000/sec.

**Default B** (Tier 3 suspended) activates automatically when sustained rate exceeds 3,800/sec for more than 5 minutes. No human decision required. Implementation is the same mechanism as Default A — poll interval configuration — but Tier 3 poll interval is set such that workers sleep and perform no processing. A user whose post received 400 likes during a viral spike does not need real-time notification of each one. Batched delivery after the spike is the correct behavior. Default B activation is logged and triggers a stakeholder notification within 15 minutes.

---

#### Push and In-App Volume

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery |
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

#### Graph Densification — Monitoring Without False Precision

**Why DAU scaling misses densification:** A user with 500 followers generates more like-notifications per post than a user with 50 followers, without any change in DAU. As the social graph matures, per-user notification rates rise even if DAU is flat. This is a different growth vector from user acquisition and requires a different operational response.

**The densification rate is not reliably known before launch.** A figure of 0.5–1.5 notifications/DAU/day per quarter reflects a plausible range for consumer social apps, but this app's graph structure — follow-heavy vs. mutual-friend-heavy, feed algorithm, content velocity — may produce rates outside this range in either direction. The 3× variation in the range produces dramatically different timelines:

| Densification Rate | Quarters to Reach 13/DAU/day from 11 | Quarters to Reach 17/DAU/day |
|-------------------|--------------------------------------|------------------------------|
| 0.5/DAU/day/quarter | 4 quarters (12 months) | 12 quarters (3 years) |
| 1.0/DAU/day/quarter | 2 quarters (6 months) | 6 quarters (18 months) |
| 1.5/DAU/day/quarter | 1.3 quarters (~4 months) | 4 quarters (12 months) |

**The correct response to this uncertainty is monitoring plus automated forward projection, not a more precise pre-launch estimate.** The densification rate will be observable in production data within 4–6 weeks of launch.

**The monitoring dashboard exposes two separate time-series:**
- **Total notification volume/day** — rises when DAU rises. Response: proportional capacity addition.
- **Notifications/DAU/day (7-day rolling average)** — rises when graph densifies with flat DAU. Response: batching evaluation first, then capacity addition.

Conflating these signals produces the wrong intervention. The per-DAU rate is the diagnostic; total throughput rate is the operational trigger.

**The densification trigger is automated, not a manual runbook step.** The prior version relied on a person remembering to execute a Week 6 runbook task and correctly projecting forward. The revised approach: the monitoring dashboard computes a rolling densification rate and automatically generates an alert when the forward projection shows the 2,400/sec reassessment trigger will be breached within 14 days. The alert pages E3, who initiates the reassessment process. No human memory required.

**Alert definition:**
```
if (projected_peak_rate_in_14_days > 2,400/sec) AND
   (current_peak_rate > 1,800/sec):
   page E3: "Densification alert: reassessment trigger projected in N days"
```

The 14-day window provides adequate lead time at all densification rates including 1.5/DAU/day/quarter, where the throughput-based trigger alone is borderline (6 days vs. 8 days required). The automated projection alert is the primary mitigation for that gap.

---

#### Headroom: Revised Analysis Including Spike Modeling

**The system has two operating regimes, not one.**

**Regime 1: Normal operation.** Worker ceiling is 2,650/sec. Calculated peak under the High scenario is 2,406/sec. Headroom is 244/sec, or approximately 10%. This is adequate for day-to-day variance.

**Regime 2: Spike operation.** The system explicitly does not maintain full throughput during spikes above 2,650/sec. Instead, it sheds Tier 3 load in a defined sequence (Default A → Default B → Tier 2 rate limiting → Tier 1 only). This is not a failure mode; it is the designed response. Tier 1 and Tier 2 notifications are protected at all load levels up to 6,000/sec.

**Normal variance (not spikes):** Day-to-day variance of 10–15% above baseline at the High scenario produces peaks of 2,647–2,767/sec. The lower end is within ceiling; the upper end briefly exceeds it. The response is Default A (Tier 3 partial throttle), not a system failure. This is acceptable behavior for a 10–15% variance event.

**The ceiling breach point:**

```
Peak rate = (DAU × per-DAU-rate × concentration%) ÷ concentration_window_seconds

At High DAU (3.5M) and 90%/4-hour concentration:
2,650/sec = (3,500,000 × R × 0.90) ÷ 14,400
R = (2,650 × 14,400) ÷ (3,500,000 × 0.90)
R = 38,160,000 ÷ 3,150,000
R ≈ 12.1 notifications/DAU/day
```

The ceiling is breached at approximately **12.1/DAU/day** under the High DAU scenario. The planning basis is 11/DAU/day. The distance between them is 1.1/DAU/day — roughly 1 quarter of densification at the 1.0/DAU/day/quarter rate, or approximately 10 weeks at the 1.5 rate. This is the primary reason the automated densification alert exists: the throughput trigger alone provides insufficient lead time at high densification rates.

---

#### Trigger Design: Lead Time Analysis

**The problem this section must solve:** The reassessment trigger must fire early enough that capacity can be