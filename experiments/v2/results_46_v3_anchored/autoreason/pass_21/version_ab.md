# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in §5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in §7.

**What this document does not claim:**

- That the system absorbs 4× viral spikes without degradation. It does not. Tiered degradation is the designed response for load above 2,650/sec. Tier 3 users experience delays during spikes. This is a deliberate tradeoff, not a failure mode — but calling it a deliberate tradeoff does not make it costless to those users.
- That 11/DAU/day is a derived figure. It is a midpoint estimate with explicit uncertainty bounds. §1.1 models what different batching assumptions produce and which implementation decisions drive the actual outcome.
- That the engineer-week budget is comfortable. It is not. §1.3 provides per-engineer allocation. Two scenarios break the budget; both trigger explicit stakeholder conversations, not silent scope absorption.

---

## Seven Items Requiring Explicit Sign-Off Before This Design Is Finalized

The owner column identifies who must decide, not which engineer implements. Engineer assignments reflect actual workload capacity analyzed in §1.3.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked; planning basis may be off by 4× |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | **End of Week 2** | Legal | E3 implements whichever is chosen | Default is synchronous guarantee. Schema work begins Week 3 and is not cleanly reversible. Retrofit to cached architecture is 1–2 engineer-weeks during Month 2 — a budget-breaking scenario. Legal must evaluate both architectures on correctness grounds, not latency grounds. See §2.4. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; full cost and timeline in §6.2 |
| Queue depth bounds, DM drop policy, and backpressure behavior | §1.1 | End of Month 1 | Engineering + Product + Legal | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded queue growth. DM drop policy may have regulatory implications requiring Legal input. Proposed defaults in §1.1; behavior at limit requires sign-off before implementation. |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before launch | Product | E4 implements rate limiting once policy is defined | Broadcast capability disabled at launch |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns enforcement layer | 429 responses produce invisible data loss for non-compliant producers |

**On the compliance deadline — the actual risk is architectural, not a latency optimization.** The synchronous and cached architectures have different data access patterns across all four channel dispatch paths. If the synchronous default is built into Month 1 schema work and Legal approves the cached architecture in Month 2, the retrofit requires changing query patterns across every dispatch path — not adding a cache layer on top. Legal needs to understand this framing before sign-off.

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

Worker ceiling sizing uses the Spike scenario, not the High scenario. Spike calculations apply explicit multipliers from the viral spike model below.

---

#### Per-DAU Rate — Sensitivity Analysis

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 8–14/DAU/day. The 11/DAU/day planning basis sits near the midpoint. This figure is not derived from first principles — it is an estimate. The sensitivity table below is required reading before accepting any throughput figure in this document.

**Peak rate sensitivity to per-DAU rate (High scenario, 90%/4hr concentration):**

```
Formula: peak_rate = (3,500,000 × per_DAU × 0.90) ÷ 14,400
```

| Per-DAU Rate | Peak Rate/sec | vs. 11/DAU baseline | Worker ceiling headroom |
|-------------|---------------|---------------------|------------------------|
| 6/DAU | 1,313/sec | −45% | Comfortable |
| 8/DAU | 1,750/sec | −27% | Comfortable |
| **11/DAU** | **2,406/sec** | **baseline** | **Narrow (244/sec)** |
| 14/DAU | 3,063/sec | +27% | **Default A fires at launch** |
| 16/DAU | 3,500/sec | +45% | **Default B fires at launch** |

**The critical finding:** If actual per-DAU delivery rate is 14/day — plausible if batching is less aggressive than assumed or DM volume is higher than modeled — Default A fires as a routine condition from day one. If per-DAU reaches 16/day, Default B is the normal operating mode before any spike occurs.

**The response to this uncertainty:** Per-DAU rate is measurable from day one. Instrument notification dispatch counts per active user as a daily metric. If the 30-day rolling average exceeds 13/DAU, the worker ceiling requires reassessment before it becomes a crisis. This is a defined measurement with a defined response threshold.

**Combined sensitivity (per-DAU × concentration):** The two largest sources of uncertainty compound. A 14/DAU rate with a 3-hour concentration window produces:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083/sec
```

This is inside Default B territory from launch. This scenario is plausible, not extreme. Infrastructure sizing must account for it as a realistic outcome.

---

#### Concentration Assumption — Sensitivity Analysis

**The 90% concentration in a 4-hour window is the single assumption that most affects all peak rate calculations.**

**What the assumption asserts:** 90% of daily notifications are delivered in a 4-hour peak window (6–10pm local time). This is commonly cited for consumer apps but is an assumption, not a measurement. This app has no production data yet.

**Where the assumption breaks down:** The 4-hour/90% figure is reasonable for apps with strong evening social patterns and no significant non-US user base. It breaks down if the app has substantial international users, content type drives morning engagement, or professional use cases distribute load more evenly.

**Sensitivity table:**

```
Formula: peak_rate = (3,500,000 × 11 × concentration_fraction) ÷ window_seconds
```

| Concentration % | Window (hours) | Peak Rate/sec | vs. 90%/4hr baseline |
|----------------|----------------|---------------|----------------------|
| 85% | 4 hours | 2,277 | −5.4% |
| **90%** | **4 hours** | **2,406** | **baseline** |
| 90% | 3.5 hours | 2,750 | +14.3% |
| 90% | 3 hours | 3,208 | +33.3% |
| 95% | 4 hours | 2,539 | +5.5% |
| 95% | 3 hours | 3,385 | +40.7% |

A 3-hour concentration window at 90% produces 3,208/sec — inside Default A territory before any spike occurs. A 3-hour/95% scenario produces 3,385/sec, inside Default B territory at launch.

**The international load case:** If the user base is 40% US, 30% Europe, 30% Asia-Pacific, no single 4-hour window dominates. The approximate profile:

```
US peak (6–10pm ET):     ~35% of daily load → ~875/sec sustained
EU peak (7–11pm CET):    ~30% of daily load → ~750/sec sustained
APAC peak (7–11pm JST):  ~30% of daily load → ~750/sec sustained
Overlap periods:          combined peaks add
```

The peak rate in this scenario is lower — approximately 1,400–1,800/sec at maximum overlap, well within the worker ceiling. But the international scenario creates a different problem: **sustained load with no recovery window.** In the 90%/4-hour scenario, the system runs at ~2,400/sec for 4 hours, then drops to ~270/sec for 20 hours. Workers, Redis, and downstream APIs get a 20-hour recovery window. In the international scenario, the system runs at 1,000–1,800/sec for 12–16 hours continuously. This affects Redis memory (no low-traffic window to expire stale keys), APNs/FCM connection pooling (persistent connections must be maintained across a longer active window), and SendGrid daily send limits (hit earlier in the day if email scheduling assumes US timing).

**The correct response to concentration uncertainty:** Use 90%/4-hour as the planning basis. Instrument peak window detection from day one — measuring actual concentration is straightforward via histogram of dispatch timestamps by hour. Set the automated densification alert to use the measured concentration window, not the assumed one, within 4 weeks of launch. If production data shows a 3-hour concentration window, the ceiling calculation changes and the reassessment trigger fires sooner than projected.

---

#### Viral Spike Model — Calibrated to 10M MAU

**Why large-platform multipliers do not apply directly:** At 10M MAU, a viral post engaging 5% of users affects 500K users — a smaller absolute burst than 5% of 300M MAU. The social graph is also less dense at 10M MAU, so viral content propagates through fewer second-degree connections before exhausting the relevant audience. Type 4 multipliers from large platforms (8–12×) are reduced to 4–6× here. These are judgment calls, not measurements; they will be observable after the first significant viral event.

| Spike Type | Description | Peak Multiplier | Duration | Planning Relevance |
|------------|-------------|----------------|----------|--------------------|
| Type 1: Content viral | Single post goes viral; reply/like storm | 2–2.5× | 30–90 min | Most common; system must absorb without Tier 1/2 impact |
| Type 2: Live event | Sports, election, product launch | 3–4× | 2–4 hours | **Infrastructure sizing target** |
| Type 3: Platform event | Feature launch, broad push | 1.5–2× | 4–8 hours | Handled by Default A alone |
| Type 4: External crisis | Breaking news drives mass activity | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Planning basis for infrastructure sizing: Type 2 spike, 3.5× multiplier.** Type 4 spikes represent a designed failure mode, not a design target — no notification system at this scale absorbs 5–6× peaks without shedding non-critical load. Type 1 at 2–2.5× is the most common and most important to absorb without degradation.

**Spike peak rate calculations:**

```
Normal peak (High scenario, 90%/4hr): 2,406/sec

Type 1 at 2.25×:  5,414/sec  → above Default B threshold
Type 2 at 3.5×:   8,421/sec  → well above Default B
Type 4 at 5×:    12,030/sec  → Tier 1 only
```

**Critical framing for Default B:** Type 1 spikes — the most common spike type — produce 5,414/sec, which exceeds the Default B threshold of 3,800/sec. Default B is not an exceptional response. It is the routine response to any meaningful viral event. The design, monitoring, and stakeholder communication must reflect this:

- The stakeholder notification on Default B activation should not create alarm. Alarm is reserved for Default B activations exceeding 30 minutes or occurring more than 3 times per day.
- The Default B threshold may require upward calibration after the first month of production data.
- Stakeholder framing: "spike management mode, operating as designed" — not "degraded state."

---

#### Tiered Degradation — Load Levels and Responses

| Load Level | Response | Tier 1 Impact | Tier 2 Impact | Tier 3 Impact |
|------------|----------|---------------|---------------|---------------|
| < 2,400/sec | Normal operation | None | None | None |
| 2,400–2,650/sec | Yellow alert; reassessment triggered | None | None | None |
| 2,650–3,800/sec | **Default A**: Tier 3 poll interval increased | None | None | Reduced throughput; queue grows |
| > 3,800/sec ≥50 sec | **Default B**: Tier 3 suspended | None | None | Suspended; delivered after spike |
| > 6,000/sec ≥5 min | Tier 2 rate-limited to 50% | None | Delayed | Suspended |
| > 8,000/sec (Type 4) | Tier 1 only; Tier 2 and Tier 3 queued | None | Queued (bounded) | Queued (bounded) |

**What Default A does and does not do:** Default A increases the poll interval for Tier 3 workers, reducing the rate at which Tier 3 jobs are consumed. It does not reduce the arrival rate of Tier 3 notifications. The Tier 3 queue grows during Default A and drains after the spike. Default A is appropriate for short-duration spikes where queue depth does not approach its bound. Default A is a bridge, not a resolution for sustained high load.

---

#### Default B — Fully Specified

**Detection:**
A dedicated metrics process — not a worker, carrying no processing load — polls Redis `LLEN` on each tier queue every 10 seconds and publishes throughput rate to a time-series store.

**Threshold evaluation:**
Default B activates when sustained rate exceeds 3,800/sec for 5 consecutive 10-second samples (50 seconds total). The metrics process writes `system:degradation_mode = "default_b"` to Redis.

**Worker behavior:**
All Tier 3 workers poll `system:degradation_mode` at the start of each processing loop. When the key reads `default_b`, workers sleep 60 seconds before rechecking. This is a configuration read executed before any job is dequeued.

**Recovery — with thundering herd mitigation:**
The metrics process clears `default_b` when sustained rate falls below 3,200/sec for 5 consecutive samples. On waking from the 60-second sleep, each Tier 3 worker checks the degradation flag and, if cleared, waits an additional `random(0, 30)` seconds before resuming. Workers then process at 50% of normal rate for the first 5 minutes after recovery (implemented by doubling the inter-job sleep interval). Full rate resumes after 5 minutes if the degradation flag has not been re-set.

This distributes wakeup events across a 30-second window and prevents the accumulated queue from triggering an immediate secondary spike. The queue drains at half speed for 5 minutes, then full speed — a controlled drain rather than a burst.

**Metrics process failure mode:**
If the metrics process fails to publish a reading for 30 seconds (3 missed cycles), workers default to Default A behavior (