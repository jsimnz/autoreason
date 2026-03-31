# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

**What this document does not claim:**

- That the system absorbs 4× viral spikes without degradation. It does not. Tiered degradation is the designed response for load above 2,650/sec. Tier 3 users experience delays during spikes. This is a deliberate tradeoff, not a failure mode — but calling it "not a failure mode" does not make it costless to those users.
- That 11/DAU/day is a derived figure. It is a midpoint estimate with explicit uncertainty bounds. Section 1.1 models what different batching assumptions produce and which implementation decisions drive the actual outcome.
- That the engineer-week budget is comfortable. It is not. Section 1.3 provides per-engineer allocation. Two scenarios break the budget; both trigger explicit stakeholder conversations, not silent scope absorption.

---

### Seven Items Requiring Explicit Sign-Off Before This Design Is Finalized

The owner column identifies who must decide, not which engineer implements.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model input | SMS channel sizing blocked; planning basis may be off by 4× |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E1 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal | E1 implements whichever is chosen | Default is synchronous. Schema work begins Week 3 and is not cleanly reversible. Retrofit is 1–2 engineer-weeks during Month 2 — a budget-breaking scenario. See §2.4 for full consequences. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E1 provides technical requirements | Self-hosted fallback activates; full cost and timeline in §6.2 |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Product + Engineering | E1 presents costed options | Default A activates automatically. Default A is a bridge, not a resolution. |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | E1 implements rate limiting once policy is defined | Broadcast capability disabled at launch |
| Queue depth bounds and backpressure policy | §1.1 | End of Month 1 | Engineering + Product | E2 implements bounds; E1 defines upstream API behavior | Type 4 spike produces unbounded queue growth without explicit bounds. Proposed defaults in §1.1; behavior at limit requires sign-off before implementation. |

**On the compliance deadline — the actual risk is architectural, not latency.** The synchronous and cached architectures have different data access patterns across all four channel dispatch paths. If the synchronous default is built into Month 1 schema work and Legal approves the cached architecture in Month 2, the retrofit requires changing query patterns across every dispatch path — not adding a cache layer. This is 1–2 engineer-weeks of rework during the highest-velocity period of the project. Legal needs to understand this framing, not a "12ms latency" framing.

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

#### Concentration Assumption — Sensitivity Analysis

**The 90% concentration in a 4-hour window is the single assumption that most affects all peak rate calculations.** Before accepting any throughput figure downstream, read this section.

**What the assumption asserts:** 90% of daily notifications are delivered in a 4-hour peak window (6–10pm local time, mapping to approximately 9–11pm UTC for US-heavy apps). This is a commonly cited figure for consumer apps, but it is an assumption, not a measurement. This app has no production data yet.

**Where the assumption breaks down:** The 4-hour/90% figure is reasonable for apps with strong evening social patterns and no significant non-US user base. It breaks down if: (a) the app has substantial international users across multiple time zones, which flattens the peak; (b) content type drives morning rather than evening engagement; or (c) the app has a significant professional use case that distributes load more evenly. None of these are known pre-launch.

**Sensitivity table — peak rate under different concentration assumptions:**

```
Formula: peak_rate = (DAU × per_DAU_rate × concentration_fraction) ÷ window_seconds
High scenario: 3.5M DAU, 11/DAU/day
```

| Concentration % | Window (hours) | Window (seconds) | Peak Rate/sec | vs. 90%/4hr baseline |
|----------------|----------------|-----------------|---------------|----------------------|
| 85% | 4 hours | 14,400 | 2,277 | −5.4% |
| **90%** | **4 hours** | **14,400** | **2,406** | **baseline** |
| 90% | 3.5 hours | 12,600 | 2,750 | +14.3% |
| 90% | 3 hours | 10,800 | 3,208 | +33.3% |
| 95% | 4 hours | 14,400 | 2,539 | +5.5% |
| 95% | 3 hours | 10,800 | 3,385 | +40.7% |

**The critical finding:** A 3-hour concentration window at 90% produces 3,208/sec — already inside Default A territory before any densification occurs. A 3-hour/95% scenario produces 3,385/sec, inside Default B territory at launch.

**The correct response to this uncertainty is not to pick a more precise estimate.** The correct response is to:
1. Use 90%/4-hour as the planning basis while acknowledging it may be optimistic.
2. Instrument peak window detection from day one — measuring the actual concentration window in production is straightforward (histogram of notification dispatch timestamps by hour).
3. Set the automated densification alert to use the measured concentration window, not the assumed one, within 4 weeks of launch.

If production data shows a 3-hour concentration window, the ceiling calculation changes and the reassessment trigger fires sooner than projected. This is a known uncertainty with a defined measurement response, not a surprise.

---

#### Viral Spike Model — Calibrated to 10M MAU

**Why large-platform spike multipliers do not apply directly:** At 10M MAU, two factors reduce the applicable multiplier relative to platforms like Twitter. First, a viral post engaging 5% of 10M MAU affects 500K users — a smaller absolute notification burst than 5% of 300M MAU. Second, the social graph is less dense at 10M MAU, so a viral post propagates through fewer second-degree connections before exhausting the relevant audience. Accordingly, Type 4 multipliers from large platforms (8–12×) are reduced to 4–6× here. Type 2 multipliers (3–5×) are retained at 3–4×. These are judgment calls, not measurements; they will be observable after the first significant viral event.

**Spike taxonomy (10M MAU calibrated):**

| Spike Type | Description | Peak Multiplier | Duration | Planning Relevance |
|------------|-------------|----------------|----------|--------------------|
| Type 1: Content viral | Single post goes viral; reply/like storm | 2–2.5× | 30–90 min | Most common; system must absorb without Tier 1/2 impact |
| Type 2: Live event | Sports, election, product launch | 3–4× | 2–4 hours | **Infrastructure sizing target** |
| Type 3: Platform event | Feature launch, push to all users | 1.5–2× | 4–8 hours | Handled by Default A alone |
| Type 4: External crisis | Breaking news drives mass activity | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Planning basis for infrastructure sizing: Type 2 spike, 3.5× multiplier.** Type 4 spikes are real but represent a designed failure mode, not a design target — no notification system at this scale absorbs 5–6× peaks gracefully without shedding non-critical load. Type 1 spikes at 2–2.5× are the most common and most important to absorb without degradation. Type 2 at 3.5× is the upper boundary of what the system should handle cleanly.

**Spike peak rate calculations:**

```
Normal peak rate (High scenario, 90%/4hr):
= (3,500,000 × 11 × 0.90) ÷ 14,400 = 2,406/sec

Type 1 spike at 2.25×: 2,406 × 2.25 = 5,414/sec
Type 2 spike at 3.5×:  2,406 × 3.5  = 8,421/sec
Type 4 spike at 5×:    2,406 × 5.0  = 12,030/sec
```

The worker ceiling (2,650/sec) does not absorb these spikes. This is intentional. The designed response is tiered degradation, described below.

---

#### Tiered Degradation — Load Levels and Responses

| Load Level | Response | Tier 1 Impact | Tier 2 Impact | Tier 3 Impact |
|------------|----------|---------------|---------------|---------------|
| < 2,400/sec | Normal operation | None | None | None |
| 2,400–2,650/sec | Yellow alert; automated densification reassessment triggered | None | None | None |
| 2,650–3,800/sec | **Default A**: Tier 3 poll interval increased | None | None | Throughput reduced; queue grows |
| > 3,800/sec sustained ≥5 min | **Default B**: Tier 3 suspended | None | None | Suspended; delivered after spike |
| > 6,000/sec sustained ≥5 min | Tier 2 rate-limited to 50% | None | Delayed by minutes | Suspended |
| > 8,000/sec (Type 4) | Tier 1 only; Tier 2 and Tier 3 queued | None | Queued (bounded) | Queued (bounded) |

**What Default A actually does and does not do:** Default A increases the poll interval for Tier 3 workers, reducing the rate at which Tier 3 jobs are consumed. It does not reduce the arrival rate of Tier 3 notifications — those continue arriving at whatever rate the app generates them. The Tier 3 queue grows during Default A. The queue drains after the spike passes. Default A is appropriate for short-duration spikes (Type 1, Type 3) where queue depth does not approach its bound. Default A is not a solution for sustained high load; it is a bridge.

**Default B mechanism — fully specified:**

Default B activates automatically. No human decision required.

1. **Detection:** A dedicated metrics process (not a worker) polls Redis `LLEN` on each tier queue every 10 seconds and publishes throughput rate to a time-series store. This process has no notification processing responsibility and is not under worker load.

2. **Threshold evaluation:** When the metrics process observes sustained rate > 3,800/sec for 5 consecutive 10-second samples (50 seconds total), it writes `system:degradation_mode = "default_b"` to Redis.

3. **Worker behavior:** All Tier 3 workers poll `system:degradation_mode` at the start of each processing loop. When the key reads `default_b`, workers sleep for 60 seconds before checking again. This is a configuration read, not a complex computation, and it executes before any job is dequeued.

4. **Recovery:** The metrics process clears `default_b` when sustained rate falls below 3,200/sec for 5 consecutive samples. Workers resume normal operation on their next loop cycle (within 60 seconds of recovery).

5. **Failure of detection process:** If the metrics process fails, workers default to normal operation. This is a deliberate false-negative design: unnecessary Tier 3 suspension during a spike that didn't require it is worse for users than no suspension. The metrics process has its own health check with a 2-minute alert SLA.

6. **Logging:** Every Default B activation and deactivation is written to a persistent log. A stakeholder notification (Slack + email to product lead) fires within 15 minutes of activation.

---

#### Queue Depth Bounds and Backpressure

During a Type 4 spike at 5× load (12,030/sec), Tier 2 and Tier 3 queues receive messages faster than they are consumed. Without bounds, queues grow unboundedly.

```
Tier 2 queue growth during a 6-hour Type 4 event (approximate):
= (12,030 − 2,650) × 0.30 × 21,600 seconds
≈ 60.8M messages in Tier 2 queue alone
```

This is not acceptable. Queue bounds must be set before implementation. The following are proposed defaults requiring sign-off per the sign-off table:

| Queue | Proposed Bound | Behavior at Limit | Rationale |
|-------|---------------|-------------------|-----------|
| Tier 1 (OTP, safety) | No bound | Never drop; block producers | Tier 1 must never be dropped |
| Tier 2 (DMs, mentions) | 2M messages | Drop oldest; log drops | 2M × ~200 bytes ≈ 400MB in Redis; manageable |
| Tier 3 (likes, follows) | 500K messages | Drop oldest; log drops | Tier 3 notifications are low-value; staleness further reduces value |

**When a Tier 2 or Tier 3 queue reaches its bound, the oldest messages are dropped, not the newest.** A like notification from 5 hours ago during a crisis event has less value than one from 5 minutes ago. Dropped messages are logged with user ID, notification type, and timestamp. No retry is attempted for dropped messages.

**Upstream backpressure:** The notification ingestion API returns HTTP 429 with `Retry-After: 30` when a queue is within 10% of its bound. The API does not block; it rejects with a retriable error. Producers (application servers) must implement retry logic — this is a contract between the notification service and its callers, documented before Month 2 implementation begins.

---

#### Push and In-App Volume — Batching Model

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery |
| Comments on posts | 1–4 | Batched similarly |
| New followers/friend requests | 0.5–2 | |
| Direct messages received | 2–6 | Power users skew high |
| Mentions and tags | 0.5–2 | |
| System/product notifications | 0.5–1 | Capped by product policy |

Raw event total: 7.5–23/DAU/day. After batching, effective delivered: **8–14/DAU/day**. Planning basis: **11/DAU/day**.

**The 11/DAU/day figure is not derived from first principles. It is a midpoint estimate