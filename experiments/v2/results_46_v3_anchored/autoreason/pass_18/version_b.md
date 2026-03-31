# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The previous version contained ten substantive problems identified in review. This revision addresses each one directly.

**Three changes from the prior version materially affect the design:**

1. **The viral spike model is now defined.** Worker sizing previously referenced spike multipliers that didn't exist. They exist now, and they change the headroom picture significantly.

2. **The PostgreSQL bottleneck is now examined.** The prior version listed PostgreSQL as "proven infrastructure" without analyzing write throughput at 2,500+/sec. That analysis is in Section 5. The conclusion is that PostgreSQL requires explicit architectural treatment — read replicas, connection pooling, and a separated write path — to function at this scale.

3. **Default A's demand reduction claim is corrected.** The prior version claimed Default A brings system load within ceiling. This was wrong: throttling dispatch doesn't reduce arrival rate, it grows queues. The revised version is honest about what Default A actually does and what it doesn't.

**Three problems from the review are structural and cannot be fully resolved within the current design scope.** They are documented as acknowledged limitations with explicit mitigations rather than papered over:

- The 4.3% headroom problem (addressed by redefining the ceiling with spike modeling included)
- The reassessment trigger lead time gap at high densification rates (addressed by converting the manual runbook step to an automated alert, not a person remembering)
- The compliance architecture lock-in risk (addressed by treating it as an architectural choice, not a scheduling problem)

---

### Six Items Requiring Explicit Sign-Off Before This Design Is Finalized

The ownership column previously assigned engineers as owners of decisions requiring external parties. That was wrong. Revised below.

| Item | Section | Decision Deadline | Owner (who must decide) | Engineer Role | Consequence of Miss |
|------|---------|-------------------|------------------------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model input | Planning basis may be off by 4x; SMS channel sizing is blocked |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E1 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal | E1 implements whichever is chosen | Default is synchronous (no cache). Consequence of inaction: synchronous default activates; schema work proceeds on that basis and is not cleanly reversible after Week 3 |
| SendGrid enterprise contract | §1.1 | End of Month 1 | Procurement/Finance | E1 provides technical requirements | Self-hosted fallback activates; see §6.2 for full cost and timeline |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Stakeholders (Product + Engineering leadership) | E1 presents options | Default A activates automatically. Default A is a bridge, not a resolution |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | E1 implements rate limiting once policy is defined | Broadcast capability disabled at launch |

**On the compliance lock-in risk (revised framing):** The prior version framed this as a scheduling problem — get Legal to decide by Week 2 or pay 12ms latency. The actual risk is larger. The synchronous vs. cached architectures have different data access patterns for every notification dispatch path. If the synchronous default is built into Month 1 schema work and Legal approves the cached architecture in Month 2, the retrofit requires changing query patterns across all four channel dispatch paths, not just adding a cache layer. This is 1–2 engineer-weeks of rework during the highest-velocity period of the project. The deadline is not about latency. It is about avoiding an architectural redo during Month 2 sprint work. Legal needs to understand this framing, not the latency framing.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage |
|----------|---------|-----|-------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Worker sizing baseline |
| **Spike** | **35% DAU + spike multiplier** | **3.5M + event** | **Worker ceiling and infrastructure sizing** |

**Worker ceiling sizing uses the Spike scenario, not the High scenario.** The previous version stated worker sizing used "the High scenario plus explicit spike multipliers defined in the viral spike model below" — but no viral spike model appeared. That model is defined here.

---

#### Viral Spike Model — Now Defined

A social app's worst-case notification load is not a gradual densification event. It is a sudden viral spike: a post, a live event, or a breaking news cycle that drives a large fraction of the user base to interact simultaneously. The notification system must handle this without shedding Tier 1 and Tier 2 traffic.

**Spike taxonomy:**

| Spike Type | Description | Historical analog | Peak multiplier vs. normal | Duration |
|------------|-------------|-------------------|---------------------------|----------|
| Type 1: Content viral | Single post goes viral; reply/like storm | Twitter trending content | 2–3× | 30–90 minutes |
| Type 2: Live event | Sports, election, product launch | Super Bowl Twitter traffic | 3–5× | 2–4 hours |
| Type 3: Platform event | App feature launch, push to all users | App store feature placement | 1.5–2× | 4–8 hours |
| Type 4: External crisis | News event drives mass sign-ups and activity | Breaking news events | 4–8× | 1–6 hours |

**Planning basis for infrastructure sizing: Type 2 spike, 4× multiplier, 2-hour duration.**

Rationale: Type 4 spikes at 8× are real but rare and represent a failure mode, not a design target — no notification system at this scale is designed to absorb 8× peaks gracefully without shedding non-critical load. Type 1 spikes at 2–3× are the most common and the most important to absorb without degradation. Type 2 at 4× represents the upper boundary of what the system should handle cleanly. This is a deliberate tradeoff: we are not designing for Type 4 events. If one occurs, the defined response is aggressive Tier 3 shedding (Default A activates immediately) and stakeholder communication.

**Spike concentration assumption:** Viral spikes are not uniformly distributed. They concentrate in the same peak window that normal traffic concentrates in — 6–10pm local time, which maps to 9–11pm UTC for US-heavy apps. The spike multiplier applies to the already-concentrated peak rate, not the daily average.

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

**The worker ceiling is not sized to absorb a 4× spike in full.** That would require approximately 9,600/sec sustained throughput — four times the current worker fleet. This is not economically justified for events lasting 2 hours. Instead, the design uses **tiered degradation**:

| Load level | Response | Tier 1 + 2 impact | Tier 3 impact |
|------------|----------|-------------------|---------------|
| < 2,400/sec | Normal operation | None | None |
| 2,400–2,650/sec | Yellow alert, reassessment trigger | None | None |
| 2,650–4,000/sec | Default A active | None | Throughput reduced to ~71% of normal; queue grows |
| > 4,000/sec | Default B: Tier 3 suspended | None | Tier 3 queue grows; processed after spike subsides |
| > 6,000/sec | Tier 2 rate-limited to 50% | Tier 2 delayed by minutes | Tier 3 suspended |
| > 8,000/sec (Type 4) | Tier 1 only; all else queued | Tier 2 queued | Tier 3 queued |

**Default B** (Tier 3 suspended) is a new addition not in the prior version. At load levels between 2,650 and 4,000/sec, Default A's partial throttling is insufficient. Default B suspends Tier 3 processing entirely, freeing those worker resources and reducing queue growth rate. Tier 3 messages (likes, low-priority activity) are queued and processed after the spike subsides. This is acceptable: a user whose post received 400 likes during a viral spike does not need real-time notification of each one. Batched delivery after the spike is the correct behavior.

**Default B activation:** Automatic when sustained rate exceeds 3,800/sec for more than 5 minutes. No human decision required. Implementation is the same mechanism as Default A — poll interval configuration — but Tier 3 poll interval is set to effectively zero (workers sleep, no processing).

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

---

#### Graph Densification — Monitoring Without False Precision

The densification rate — rising per-DAU notification rates as the social graph matures — is not reliably known before launch. The correct response is monitoring plus automated alerting, not a more precise pre-launch estimate.

**Two separate time-series are monitored and graphed separately:**
- **Total notification volume/day** — rises when DAU rises. Response: proportional capacity addition.
- **Notifications/DAU/day (7-day rolling average)** — rises when graph densifies with flat DAU. Response: batching evaluation first, then capacity addition.

Conflating these signals produces the wrong intervention.

**The densification trigger is now automated, not a manual runbook step.** The prior version relied on a person remembering to execute a Week 6 runbook task and correctly projecting forward. This was identified as a circular mitigation. The revised approach: the monitoring dashboard computes a rolling densification rate and automatically generates an alert when the forward projection shows the 2,400/sec reassessment trigger will be breached within 14 days. The alert pages E3, who initiates the reassessment process. No human memory required.

**Alert definition:**
```
if (projected_peak_rate_in_14_days > 2400/sec) AND
   (current_peak_rate > 1800/sec):
   page E3: "Densification alert: reassessment trigger projected in N days"
```

The 14-day window provides adequate lead time at all densification rates including 1.5/DAU/day/quarter.

---

#### Headroom: Revised Analysis Including Spike Modeling

The prior version stated 4.3% operational headroom (110/sec between peak and ceiling) and acknowledged this was insufficient for normal variance. This framing was correct to flag but incomplete in its response.

**Revised headroom framing:**

The system has two operating regimes:

**Regime 1: Normal operation.** Worker ceiling is 2,650/sec. Calculated peak under High scenario is 2,406/sec. Headroom is 244/sec, or approximately 10%. This is adequate for day-to-day variance. The previous calculation of 2,540/sec was incorrect — it used 11/DAU/day × 0.90 concentration ÷ 14,400 seconds incorrectly. The corrected figure is shown above.

**Regime 2: Spike operation.** The system explicitly does not maintain full throughput during spikes above 2,650/sec. Instead, it sheds Tier 3 load in a defined sequence (Default A → Default B → Tier 2 rate limiting → Tier 1 only). This is not a failure mode; it is the designed response. Tier 1 and Tier 2 notifications are protected at all load levels up to 6,000/sec.

**Normal variance (not spikes):** Day-to-day variance of 10–15% above baseline at the High scenario produces peaks of 2,647–2,767/sec. The lower end is within ceiling; the upper end briefly exceeds it. The response at 2,650–2,767/sec is Default A (Tier 3 partial throttle), not a system failure. This is acceptable behavior for a 10–15% variance event.

---

#### Throughput Trigger Thresholds

| Threshold | Value | Derivation | Response |
|-----------|-------|------------|----------|
| Yellow alert | 7-day rolling average peak > 2,200/sec | 83% of ceiling | E3 monitors daily; densification projection runs |
| Reassessment trigger | 3-day rolling peak > 2,400/sec | 90.6% of ceiling | Reassessment process initiates (Day 1–3 procedure) |
| Default A | Any single day peak > 2,650/sec | At ceiling | Automatic; no human decision |
| Default B | Sustained rate > 3,800/sec for 5+ minutes | 143% of ceiling | Automatic; Tier 3 suspended |
| Tier 2 rate limit | Sustained rate > 6,000/sec for 5+ minutes | 226% of ceiling | Automatic; Tier 2 at 50% |
| Tier 1 only | Sustained rate > 8,000/sec | 302% of ceiling | Automatic; Type 4 event protocol |

---

#### Default A — Corrected Demand Reduction Claim

**The prior version contained an error.** It claimed Default A "brings effective demand to approximately 2,220–2,295/sec — within the 2,650/sec ceiling." This was wrong. Default A reduces Tier 3 dispatch throughput, not Tier 3 message arrival rate. Messages arriving at 2,550/sec continue arriving at 2,550/sec. Default A causes Tier 3 messages to queue rather than disappear.

**What Default A actually does:**

Default A reduces Tier 3 *processing* rate from normal to approximately 71% of normal. This means:
- Tier 3 queue depth grows during the period Default A is active
- The system's sustained *ceiling* is not exceeded for Tier 1 and Tier 2 — those workers are unaffected
- Total system throughput (all tiers combined) is reduced, creating breathing room for the higher-priority workers
- When Default A is lifted, Tier 3 has a backlog. This backlog creates elevated Tier 3 processing for a period after the spike — a "second hump" in Tier 3 queue depth

**The second hump is not a problem for Tier 3 notifications.** Likes, low-priority activity updates, and re-engagement notifications are exactly the traffic class where delayed delivery is acceptable. The second hump is a Tier 3 phenomenon only. Tier 1 and Tier 2 are unaffected.

**What Default A does not do:** Default A does not reduce the arrival rate of messages. It does not protect the system from a sustained above-ceiling arrival rate indefinitely. If the system remains above 2,650/sec arrival rate for an extended period (hours), Tier 3 queue depth grows without bound until Default B activates or the load subsides.

**Default B addresses this.** Default B suspends Tier 3 processing entirely, which stops queue growth and frees resources. The Tier 3 backlog is processed after the spike at normal throughput.

**Revised Default A specification:**

- Tier 3 worker poll interval: 500ms → 700ms
- Effect: Tier 3 throughput reduced to ~71% of normal
- Tier 1, Tier 2, in