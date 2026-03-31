# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

**What this document does not claim:**

- That the system absorbs 4× viral spikes without degradation. It does not. Tiered degradation is the designed response for load above 2,650/sec, and that response means Tier 3 users experience delays. This is a deliberate tradeoff, not a failure mode — but calling it "not a failure mode" does not make it costless to those users.
- That 11/DAU/day is a derived figure. It is a midpoint estimate with explicit uncertainty bounds. Section 1.1 models what different batching assumptions produce and which implementation decisions drive the actual outcome.
- That the engineer-week budget is comfortable. It is not. Section 1.3 provides per-engineer allocation. Two scenarios break the budget; a third (compliance rework) is now in the risk register.

---

### Seven Items Requiring Explicit Sign-Off Before This Design Is Finalized

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model input | SMS channel sizing blocked; planning basis may be off by 4× |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E1 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | End of Week 2 | Legal | E1 implements whichever is chosen | Default is synchronous. Inaction cost: schema work begins Week 3 and is not cleanly reversible. Retrofit is 1–2 engineer-weeks during Month 2 — **this is a budget-breaking scenario; see risk register §1.3.** |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E1 provides technical requirements | Self-hosted fallback activates; full cost and timeline in §6.2 |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Product + Engineering | E1 presents costed options | Default A activates automatically. Default A is a bridge, not a resolution. |
| Broadcast notification policy + exception gate owner | §1.1, §6 | Before launch | Product | E1 implements rate limiting once policy is defined | Broadcast capability disabled at launch |
| Queue depth bounds and backpressure policy | §1.1 | End of Month 1 | Engineering + Product | E2 implements bounds; E1 defines upstream API behavior | Type 4 spike produces unbounded queue growth without explicit bounds. Default: 500K messages per tier queue; behavior at limit must be decided before implementation. |

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

**Worker ceiling sizing uses the Spike scenario.** Spike calculations use the High scenario plus explicit multipliers. The spike multiplier taxonomy below is calibrated to 10M MAU scale, not Twitter scale — this distinction is addressed directly in the viral spike model section.

---

#### Concentration Assumption — Sensitivity Analysis

**The 90% concentration in a 4-hour window is the single assumption that most affects all peak rate calculations.** Before accepting any throughput figure downstream, read this section.

**What the assumption asserts:** 90% of daily notifications are delivered in a 4-hour peak window (6–10pm local time, mapping to approximately 9–11pm UTC for US-heavy apps). This is a commonly cited figure for consumer apps, but it is an assumption, not a measurement. This app has no production data yet.

**Where the assumption comes from and where it breaks down:** The 4-hour/90% figure is reasonable for apps with strong evening social patterns and no significant non-US user base. It breaks down if: (a) the app has substantial international users across multiple time zones, which flattens the peak; (b) the content type drives morning rather than evening engagement; or (c) the app has a significant professional or utility use case that distributes load more evenly. None of these are known pre-launch.

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

**The critical finding:** A 3-hour concentration window at 90% produces 3,208/sec — already inside Default A territory before any densification occurs. A 3-hour/95% scenario produces 3,385/sec, which is inside Default B territory at launch.

**The correct response to this uncertainty is not to pick a more precise estimate.** The correct response is to:
1. Use 90%/4-hour as the planning basis while acknowledging it may be optimistic.
2. Instrument peak window detection from day one — measuring the actual concentration window in production is straightforward (histogram of notification dispatch timestamps by hour).
3. Set the automated densification alert to use the measured concentration window, not the assumed one, within 4 weeks of launch.

**If production data shows a 3-hour concentration window, the ceiling calculation changes and the reassessment trigger fires sooner than projected.** This is not a surprise; it is a known uncertainty with a defined measurement response.

---

#### Viral Spike Model — Calibrated to 10M MAU

**Why Twitter-scale spike multipliers do not apply directly:** The spike taxonomy below uses multipliers derived from large-platform behavior (Twitter, Facebook during live events). At 10M MAU, two factors reduce the applicable multiplier:

1. **Absolute user base.** A viral post that engages 5% of Twitter's 300M MAU affects 15M users. A post that engages 5% of this app's 10M MAU affects 500K users — a smaller absolute notification burst.
2. **Graph density.** At 10M MAU, the average social graph is less dense than at 300M MAU. A viral post propagates through fewer second-degree connections before exhausting the relevant audience.

**Adjustment:** Type 4 spike multipliers from large platforms (8–12×) are reduced to 4–6× for a 10M MAU app. Type 2 multipliers (3–5×) are retained at 3–4×. This is a judgment call, not a measurement. The multipliers will be observable after the first significant viral event.

**Spike taxonomy (10M MAU calibrated):**

| Spike Type | Description | Peak Multiplier (10M MAU) | Duration | Planning Relevance |
|------------|-------------|--------------------------|----------|--------------------|
| Type 1: Content viral | Single post goes viral; reply/like storm | 2–2.5× | 30–90 min | Most common; system must absorb without Tier 1/2 impact |
| Type 2: Live event | Sports, election, product launch | 3–4× | 2–4 hours | Infrastructure sizing target |
| Type 3: Platform event | Feature launch, push to all users | 1.5–2× | 4–8 hours | Handled by Default A alone |
| Type 4: External crisis | Breaking news drives mass activity | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Planning basis for infrastructure sizing: Type 2 spike, 3.5× multiplier.** (Reduced from the prior version's 4× to reflect 10M MAU calibration. This is a conservative adjustment; if the multiplier proves to be 4×, Default B activates earlier but Tier 1 and Tier 2 are still protected.)

**Spike peak rate calculations:**

```
Normal peak rate (High scenario, 90%/4hr concentration):
= (3,500,000 × 11 × 0.90) ÷ 14,400 = 2,406/sec

Type 1 spike at 2.25×: 2,406 × 2.25 = 5,414/sec
Type 2 spike at 3.5×:  2,406 × 3.5  = 8,421/sec
Type 4 spike at 5×:    2,406 × 5.0  = 12,030/sec
```

**The worker ceiling (2,650/sec) does not absorb these spikes.** This is intentional and explicit. The system is not designed to absorb a 3.5× spike at full throughput — doing so would require a worker fleet approximately 3.5× larger, which is not economically justified for 2–4 hour events. The designed response is tiered degradation, described below. The claim "tiered degradation is the designed response, not a failure mode" means we have defined the behavior in advance and it is not a surprise — it does not mean the behavior is costless to Tier 3 users.

---

#### Tiered Degradation — Load Levels and Responses

| Load Level | Response | Tier 1 Impact | Tier 2 Impact | Tier 3 Impact |
|------------|----------|---------------|---------------|---------------|
| < 2,400/sec | Normal operation | None | None | None |
| 2,400–2,650/sec | Yellow alert; densification reassessment triggered | None | None | None |
| 2,650–3,800/sec | **Default A**: Tier 3 poll interval increased to reduce worker consumption | None | None | Throughput reduced; queue grows |
| > 3,800/sec sustained ≥5 min | **Default B**: Tier 3 suspended | None | None | Suspended; delivered after spike |
| > 6,000/sec sustained ≥5 min | Tier 2 rate-limited to 50% | None | Delayed by minutes | Suspended |
| > 8,000/sec (Type 4) | Tier 1 only; Tier 2 and Tier 3 queued | None | Queued (bounded) | Queued (bounded) |

**What Default A actually does and does not do:**

Default A increases the poll interval for Tier 3 workers. This reduces the rate at which Tier 3 jobs are consumed from the queue. It does not reduce the arrival rate of Tier 3 notifications — those continue to arrive at whatever rate the app generates them. The Tier 3 queue grows during Default A. The queue will drain after the spike passes and Tier 3 workers return to normal poll intervals. Default A is appropriate when the spike is short-duration (Type 1, Type 3) and the queue depth does not approach its bound. Default A is not a solution for sustained high load; it is a bridge.

**Default B mechanism — fully specified:**

Default B is not a manual operation. The mechanism is:

1. **Detection:** A dedicated metrics process (not a worker) polls the Redis `LLEN` command on each tier queue every 10 seconds and publishes throughput rate to a time-series store. This process has no notification processing responsibility and is not under worker load.

2. **Threshold evaluation:** When the metrics process observes sustained rate > 3,800/sec for 5 consecutive 10-second samples (50 seconds total), it writes a flag to a Redis key: `system:degradation_mode = "default_b"`.

3. **Worker behavior:** All Tier 3 workers poll the `system:degradation_mode` key at the start of each processing loop. When the key reads `default_b`, workers sleep for 60 seconds before checking again. This is a configuration read, not a complex computation, and it executes before any job is dequeued.

4. **Recovery:** The metrics process clears `default_b` when sustained rate falls below 3,200/sec for 5 consecutive samples. Workers resume normal operation on their next loop cycle (within 60 seconds of recovery).

5. **Failure of detection process:** If the metrics process itself fails, workers default to normal operation (no degradation mode). This means Default B does not activate if the metrics process is down — a false negative, not a false positive. The tradeoff: a false positive (unnecessary Tier 3 suspension) is worse for users than a false negative (no suspension during a spike that might not have required it). The metrics process has its own health check and alerts within 2 minutes of failure.

6. **Logging:** Every Default B activation and deactivation is written to a persistent log. A stakeholder notification (Slack + email to product lead) is sent within 15 minutes of activation.

**Queue depth bounds and backpressure — Type 4 spike behavior:**

During a Type 4 spike at 5× load (12,030/sec), Tier 2 and Tier 3 queues receive messages faster than they are consumed. Without bounds, queues grow unboundedly. With a 6-hour Type 4 event:

```
Tier 2 queue growth rate during Type 4 (approximate):
= (total_rate − tier_1_processing_rate) × tier_2_fraction × duration
= (12,030 − 2,650) × 0.30 × 21,600 seconds
≈ 60.8M messages in Tier 2 queue alone
```

This is not acceptable. Queue bounds must be set before implementation.

**Proposed defaults (require sign-off per the sign-off table):**

| Queue | Proposed Bound | Behavior at Limit | Rationale |
|-------|---------------|-------------------|-----------|
| Tier 1 (OTP, safety) | No bound | Never drop; block producers | Tier 1 must never be dropped |
| Tier 2 (DMs, mentions) | 2M messages | Drop oldest Tier 2 messages; log drops | 2M × ~200 bytes ≈ 400MB in Redis; manageable |
| Tier 3 (likes, follows) | 500K messages | Drop oldest Tier 3 messages; log drops | Tier 3 notifications are low-value; staleness reduces value further |

**When a Tier 2 or Tier 3 queue reaches its bound, the oldest messages are dropped, not the newest.** Rationale: a like notification from 5 hours ago during a crisis event has less value than one from 5 minutes ago. Dropped messages are logged with user ID, notification type, and timestamp. No retry is attempted for dropped messages.

**Upstream backpressure:** The notification ingestion API returns HTTP 429 with `Retry-After: 30` when a queue is within 10% of its bound. This signals upstream producers to reduce send rate. The API does not block; it rejects with a retriable error. Producers (application servers) must implement retry logic — this is a contract between the notification service and its callers, and it must be documented before Month 2 implementation.

---

#### Push and In-App Volume — Batching Model

**The 11/DAU/day figure is not derived from first principles. It is an estimate with explicit uncertainty.