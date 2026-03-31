# Notification System Design — Revision 2
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Change Log from Revision 1

This revision addresses eleven structural problems identified in review. Each is resolved or explicitly carried as a documented risk with owner and consequence. Changes are not cosmetic — several require design decisions that were deferred in Revision 1.

| Problem | Resolution | Section |
|---------|-----------|---------|
| E1 overloaded in sign-off table without workload analysis | E1 workload fully specified; three items reassigned | §1.3, §Sign-Off Table |
| Tier 1 unbounded queue with no blocking analysis | Tier 1 blocking analyzed; producer timeout and thread exhaustion addressed | §1.1 |
| Default B fires during ordinary viral events | Thresholds recalculated; Default B reframed as routine, not exceptional | §1.1 |
| Thundering herd on Default B recovery | Staggered restart with jitter specified | §1.1 |
| Metrics process failure mode inverted | Corrected: failure defaults to Default B, not normal operation | §1.1 |
| Redis memory arithmetic wrong | Corrected with per-entry overhead; bound reduced | §1.1 |
| Compliance architecture framed as latency, not correctness | Reframed; synchronous vs. cached described as correctness choice | §2.4 |
| Tier 2 drop policy ignores DM regulatory risk | DMs separated from Tier 2 drop logic; escalation path added | §1.1 |
| No sensitivity analysis for per-DAU rate | Sensitivity table added | §1.1 |
| International load case acknowledged then ignored | Sustained moderate load case analyzed | §1.1 |
| 429 backpressure contract underdefined | Producer registry, enforcement mechanism, and ownership specified | §1.1 |

---

## Seven Items Requiring Explicit Sign-Off Before This Design Is Finalized

**Revision note:** The original table assigned too many items to E1 without workload analysis. Three items have been reassigned. The E1 column now reflects actual implementation capacity. Where E1 is listed, the workload is accounted for in §1.3.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture — **correctness choice, not performance choice** | §2.4 | **End of Week 2** | Legal | E3 implements whichever architecture is chosen | Default is synchronous guarantee. Cached architecture has different correctness properties. Schema work begins Week 3; retrofit is 1–2 engineer-weeks and changes correctness guarantees, not just performance. Legal must evaluate both architectures on correctness grounds before sign-off. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; full cost and timeline in §6.2 |
| Queue depth bounds, DM drop policy, and backpressure behavior | §1.1 | End of Month 1 | Engineering + Product + Legal | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded growth; DM drop policy may have regulatory implications requiring Legal input |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before launch | Product | E4 implements rate limiting once policy is defined | Broadcast capability disabled at launch |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns enforcement layer | 429 responses produce invisible data loss for non-compliant producers |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage |
|----------|---------|-----|-------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Worker sizing baseline |
| Spike | 35% DAU + multiplier | 3.5M + event | Worker ceiling and infrastructure sizing |

---

#### Per-DAU Rate — Sensitivity Analysis

**Revision note:** Revision 1 provided concentration sensitivity but no per-DAU sensitivity, despite acknowledging the 11/DAU/day figure is a midpoint estimate over a 7.5–23/DAU/day raw range. This was an inconsistency in methodology. The table below applies the same treatment.

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day. The 11/DAU/day planning basis sits near the midpoint.

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

**The critical finding:** If actual per-DAU delivery rate is 14/day — plausible if batching is less aggressive than assumed or if DM volume is higher than modeled — Default A fires as a routine condition from day one, not an exceptional response. If per-DAU reaches 16/day, Default B is the normal operating mode.

**The response to this uncertainty:** Per-DAU rate is measurable from day one. Instrument notification dispatch counts per active user as a daily metric. If the 30-day rolling average exceeds 13/DAU, the worker ceiling requires reassessment before it becomes a crisis. This is a defined measurement with a defined response threshold, not a surprise.

**Combined sensitivity (per-DAU × concentration):**

The two largest sources of uncertainty compound. A 14/DAU rate with a 3-hour concentration window produces:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083/sec
```

This is inside Default B territory from launch. This scenario is plausible, not extreme. The infrastructure sizing must account for it as a realistic outcome, not an edge case.

---

#### Concentration Assumption — Sensitivity Analysis

*(Retained from Revision 1 with one addition: the international load case, previously acknowledged then ignored.)*

**Standard concentration sensitivity:**

| Concentration % | Window (hours) | Peak Rate/sec | vs. 90%/4hr baseline |
|----------------|----------------|---------------|----------------------|
| 85% | 4 hours | 2,277 | −5.4% |
| **90%** | **4 hours** | **2,406** | **baseline** |
| 90% | 3.5 hours | 2,750 | +14.3% |
| 90% | 3 hours | 3,208 | +33.3% |
| 95% | 4 hours | 2,539 | +5.5% |
| 95% | 3 hours | 3,385 | +40.7% |

**The international load case — previously unanalyzed:**

Revision 1 acknowledged that significant international users flatten the peak distribution, then proceeded to use the 90%/4-hour assumption for all sizing. This was an error. The flatter distribution case requires separate analysis because it changes the nature of the problem, not just the magnitude.

**What flatter distribution means for this design:**

If the user base is 40% US, 30% Europe, 30% Asia-Pacific, no single 4-hour window dominates. Instead of 90% of load in one window, load is distributed across three overlapping peaks. The approximate profile:

```
US peak (6–10pm ET):     ~35% of daily load in 4 hours → ~875/sec sustained
EU peak (7–11pm CET):    ~30% of daily load in 4 hours → ~750/sec sustained
APAC peak (7–11pm JST):  ~30% of daily load in 4 hours → ~750/sec sustained
Overlap periods:          combined peaks add
```

**The peak rate in this scenario is lower** — approximately 1,400–1,800/sec at maximum overlap — well within the worker ceiling. The 90%/4-hour scenario is the harder problem for peak rate. But the international scenario creates a different problem: **sustained load with no recovery window.**

In the 90%/4-hour scenario, the system processes at ~2,400/sec for 4 hours, then drops to ~270/sec for 20 hours. Workers, Redis, and downstream APIs get a 20-hour recovery window. In the international scenario, the system runs at 1,000–1,800/sec for 12–16 hours continuously. This affects:

- **Redis memory:** No low-traffic window to expire stale keys or compact data structures. Redis memory consumption is higher at steady state.
- **Worker health:** Workers running continuously at 60–70% capacity for 16 hours have different failure characteristics than workers running at 95% for 4 hours and idle for 20.
- **APNs/FCM connection pooling:** Persistent connections need to be maintained across a longer active window. Connection recycling logic that assumes a daily low-traffic window may not function correctly.
- **SendGrid rate limits:** Daily send limits hit earlier in the day. If re-engagement emails are scheduled based on US evening timing, they may conflict with APAC send volume.

**The correct response:** The international distribution is not captured in the worker ceiling calculation, but it is not ignored. The Redis memory sizing in §5 uses the sustained load case. The connection pool sizing in §6 uses continuous operation assumptions. The monitoring alerting in §7 measures actual distribution within 4 weeks of launch and triggers a reassessment if the international case applies.

---

#### Viral Spike Model

*(Retained from Revision 1 with revised framing of Default B.)*

| Spike Type | Peak Multiplier | Duration | Planning Relevance |
|------------|----------------|----------|--------------------|
| Type 1: Content viral | 2–2.5× | 30–90 min | **Most common; Default B fires routinely** |
| Type 2: Live event | 3–4× | 2–4 hours | Infrastructure sizing target |
| Type 3: Platform event | 1.5–2× | 4–8 hours | Handled by Default A |
| Type 4: External crisis | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Spike peak rates:**

```
Normal peak (High scenario, 90%/4hr): 2,406/sec

Type 1 at 2.25×:  5,414/sec  → above Default B threshold (3,800/sec)
Type 2 at 3.5×:   8,421/sec  → well above Default B
Type 4 at 5×:    12,030/sec  → Tier 1 only
```

**Revised framing of Default B:** Revision 1 described Default B as appropriate for Type 2 events and exceptional. The math shows this is wrong: Type 1 spikes — the most common spike type — produce 5,414/sec, which exceeds the Default B threshold of 3,800/sec. Default B is not an exceptional response. It is the routine response to any meaningful viral event. The design, monitoring, and stakeholder communication must treat it as such. Specifically:

- The Slack/email notification on Default B activation (retained from Revision 1) should not create alarm. It should be a routine operational log entry, with alarm reserved for Default B activations exceeding 30 minutes or occurring more than 3 times per day.
- The Default B threshold may need to be raised if routine Type 1 spikes trigger it — a threshold calibration exercise after the first month of production data.
- The framing in stakeholder communication changes from "degraded state" to "spike management mode, operating as designed."

---

#### Tiered Degradation

| Load Level | Response | Tier 1 | Tier 2 | Tier 3 |
|------------|----------|--------|--------|--------|
| < 2,400/sec | Normal | None | None | None |
| 2,400–2,650/sec | Yellow alert | None | None | None |
| 2,650–3,800/sec | Default A: Tier 3 poll interval increased | None | None | Reduced throughput; queue grows |
| > 3,800/sec ≥50 sec | **Default B: Tier 3 suspended** | None | None | Suspended; delivered after spike |
| > 6,000/sec ≥5 min | Tier 2 rate-limited to 50% | None | Delayed | Suspended |
| > 8,000/sec (Type 4) | Tier 1 only | None | Queued (bounded) | Queued (bounded) |

---

#### Default B — Fully Revised Specification

**Four changes from Revision 1:** (1) failure mode corrected to default to suspension, not normal operation; (2) thundering herd on recovery addressed with jitter; (3) Tier 1 blocking consequences analyzed; (4) DMs separated from Tier 3 drop policy.

**1. Detection (unchanged from Revision 1):**

A dedicated metrics process polls Redis `LLEN` on each tier queue every 10 seconds and publishes throughput rate. This process has no notification processing responsibility.

**2. Threshold evaluation (unchanged):**

Default B activates when sustained rate exceeds 3,800/sec for 5 consecutive 10-second samples (50 seconds total). The metrics process writes `system:degradation_mode = "default_b"` to Redis.

**3. Worker behavior (unchanged):**

Tier 3 workers poll `system:degradation_mode` at the start of each loop. When `default_b` is set, workers sleep 60 seconds before rechecking.

**4. Recovery — revised to address thundering herd:**

Revision 1 specified that workers resume "within 60 seconds of recovery," which causes all workers to wake approximately simultaneously after the same sleep cycle, finding a large accumulated queue and hammering Redis concurrently.

Revised recovery procedure:
- The metrics process clears `default_b` when sustained rate falls below 3,200/sec for 5 consecutive samples.
- Each Tier 3 worker, on waking from its 60-second sleep, checks the degradation flag and, if cleared, waits an additional `random(0, 30)` seconds before resuming processing. The jitter window is 30 seconds.
- Workers process at 50% of normal rate for the first 5 minutes after recovery (configurable). This is implemented by sleeping 2× the normal inter-job interval.
- Full rate resumes after 5 minutes if the degradation flag has not been re-set.

With N Tier 3 workers, the staggered restart distributes wakeup events across a 30-second window, and the 50% rate reduction prevents the queue drain from spiking Redis at the moment of maximum queue depth. The queue drains at half speed for 5 minutes, then full speed — a controlled drain rather than a burst.

**5. Metrics process failure mode — corrected:**

Revision 1 stated that metrics process failure defaults to normal operation, justified as preferring false negatives. This is backwards. The scenario being protected against is a spike occurring while the detection process is down, during which Tier 3 workers continue consuming at full rate. At high load, Tier 3 consumption competes with Tier 1 and Tier 2 for Redis I/O and worker thread capacity. An undetected spike that would have triggered Default B instead produces resource contention without the designed response.

**Corrected behavior:** If the metrics process fails to publish a reading for 30 seconds (3 missed cycles), workers default to Default A behavior (reduced Tier 3 poll interval). If the process fails for 90 seconds