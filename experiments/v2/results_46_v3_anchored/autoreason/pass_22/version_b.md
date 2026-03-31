# Notification System Design — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Change Log from Revision 2

Ten problems were identified in review. Each is addressed below. Changes are structural, not cosmetic.

| Problem | Resolution | Section |
|---------|-----------|---------|
| Circular dependency between opt-out compliance and DM drop policy sign-offs | Dependency documented; sign-offs consolidated into a single Legal review | §Sign-Off Table, §2.4 |
| Document cut off mid-sentence in metrics process failure specification | Failure mode specification completed | §1.1 |
| Combined sensitivity finding (4,083/sec) has no infrastructure response | Worker ceiling, Redis sizing, and connection pool specifications revised to treat 14/DAU + 3-hour concentration as the design basis | §1.1, §1.2 |
| International load case analysis deferred to absent sections | Redis and connection pool sizing for sustained load included in this document | §1.1, §5, §6 |
| Default B threshold calibration deferred to post-launch | Threshold recalibrated before launch using pre-launch load testing protocol | §1.1 |
| E4 workload conflict between producer registry and broadcast rate limiting unanalyzed | E4 sequencing analyzed; one item deferred or reassigned | §1.3, §Sign-Off Table |
| Workload reassignment claims unverifiable (§1.3 absent) | §1.3 included in this document | §1.3 |
| Staggered restart jitter analysis incomplete without worker count | Worker count specified; jitter analysis completed relative to count | §1.1 |
| Per-DAU monitoring threshold has no owner, timeline, or reassessment definition | Owner named; reassessment procedure and timeline specified | §1.1 |
| Opt-out correctness difference not explained in terms Legal can evaluate | Failure scenarios described in plain language for Legal review | §2.4 |

---

## Seven Items Requiring Sign-Off Before This Design Is Finalized

**Revision note:** The circular dependency between the opt-out compliance sign-off (previously Week 2) and the DM drop policy sign-off (previously Month 1) has been identified and resolved by consolidating both into a single Legal review. The correctness of DM handling under the opt-out architecture and the permissibility of dropping DMs are not independent questions. Legal must answer them together. The consolidated deadline is **End of Week 2**. Schema work that was scheduled to begin Week 3 is blocked until this review is complete. The consequence of a missed deadline is a one-week slip in schema work, which compresses the Month 2 implementation window. This is documented in §1.3.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked; E2 implementation delayed |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized |
| **Opt-out compliance architecture AND DM drop policy — consolidated Legal review** | §2.4, §1.1 | **End of Week 2** | **Legal** | E3 implements whichever architecture is chosen; E2 implements DM handling | Schema work (Week 3) is blocked. These two items share a correctness dependency: whether DMs can be dropped under load depends on the opt-out architecture chosen. Legal must evaluate both simultaneously. The failure scenarios for each architecture are in §2.4. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; cost and timeline in §6.2 |
| Queue depth bounds and backpressure behavior | §1.1 | End of Month 1 | Engineering + Product | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded queue growth |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before launch | Product | E4 implements rate limiting after policy is defined; sequencing with producer registry in §1.3 | Broadcast capability disabled at launch |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns enforcement layer after broadcast policy is resolved; sequencing in §1.3 | 429 responses produce invisible data loss for non-compliant producers |

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

#### Per-DAU Rate — Sensitivity Analysis and Design Basis Selection

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day.

**Peak rate sensitivity (High scenario, 90%/4hr concentration):**

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

**Combined sensitivity — the critical scenario:**

A 14/DAU rate with a 3-hour concentration window produces:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083/sec
```

This is inside Default B territory from launch. Revision 2 identified this scenario as "plausible, not extreme" and stated that infrastructure sizing "must account for it" — but then made no changes to the sizing. This revision corrects that omission.

**Design basis change:** This design is now sized to the 14/DAU + 3-hour concentration scenario (4,083/sec sustained peak) rather than the 11/DAU + 4-hour scenario (2,406/sec). This affects worker count (§1.3), Redis memory allocation (§5), and connection pool sizing (§6). The cost implication is approximately 30–40% higher infrastructure spend during the spike window. This is the correct tradeoff: the alternative is a system that enters Default B as a routine condition from day one, which produces real user impact (Tier 3 suspension) and misaligned stakeholder expectations.

The 11/DAU baseline is retained for cost modeling at normal load. The 14/DAU + 3-hour scenario is used for ceiling sizing and Default B threshold calibration.

---

#### Concentration Assumption — Sensitivity Analysis

**Standard concentration sensitivity (High scenario, 14/DAU design basis):**

| Concentration % | Window (hours) | Peak Rate/sec | Infrastructure status |
|----------------|----------------|---------------|----------------------|
| 85% | 4 hours | 2,604 | Below Default A |
| 90% | 4 hours | 3,063 | Default A territory |
| **90%** | **3 hours** | **4,083** | **Design basis ceiling** |
| 95% | 3 hours | 4,306 | 5% above design basis; Default B |
| 90% | 2.5 hours | 4,900 | Spike territory |

The design basis ceiling (4,083/sec) sits at the 90th percentile of plausible concentration scenarios at 14/DAU. Scenarios above it exist and are handled by the tiered degradation system — they produce Default B activation, which is designed behavior.

---

#### International Load Case — Sustained Load Analysis

**What flatter distribution means for this design:**

If the user base is 40% US, 30% Europe, 30% Asia-Pacific, the approximate sustained load profile is:

```
US peak (6–10pm ET):     ~35% of daily load in 4 hours → ~875/sec sustained
EU peak (7–11pm CET):    ~30% of daily load in 4 hours → ~750/sec sustained
APAC peak (7–11pm JST):  ~30% of daily load in 4 hours → ~750/sec sustained
Maximum overlap:          ~1,400–1,800/sec
```

The peak rate in this scenario is lower than the 4,083/sec design basis and does not change the worker ceiling. The international scenario creates a different problem: **sustained load with no recovery window.** The system runs at 1,000–1,800/sec for 12–16 hours continuously rather than 2,400–4,000/sec for 4 hours followed by 20 hours of low load.

**Infrastructure responses to the sustained load case — included in this document:**

**Redis memory (§5 preview):** The sustained load case prevents the low-traffic window that would normally allow stale key expiration and data structure compaction. Redis memory sizing uses the sustained load case: peak key count is assumed to be present for 16 hours rather than 4. The per-entry overhead calculation and resulting memory bound are in §5.

**Connection pooling (§6 preview):** APNs and FCM connections must be maintained across a 16-hour active window in the international case. Connection recycling logic that assumes a daily low-traffic window is not safe. The connection pool specification in §6 uses continuous operation assumptions: connections are recycled on a time-based schedule (every 4 hours) rather than an activity-based schedule (after a low-traffic period). This adds complexity but is required for correctness in the international case.

**SendGrid daily limits:** If re-engagement emails are scheduled based on US evening timing, they may conflict with APAC send volume against daily API limits. The email scheduling logic must distribute send volume across time zones rather than concentrating on a single evening window. This is specified in §6.2.

**Worker health:** Workers running at 60–70% capacity for 16 hours have different failure characteristics than workers at 95% for 4 hours. The worker health monitoring in §7 tracks per-worker error rate and memory consumption on a rolling 1-hour basis, not just during peak windows. Alerting thresholds are set for sustained load, not just spike conditions.

**Monitoring response:** Actual geographic distribution is measured within 4 weeks of launch. If 30% or more of DAU is outside the US, the connection recycling and Redis expiry configurations are reviewed against the sustained load case. Owner: E1. Timeline: within 2 weeks of the measurement crossing the threshold.

---

#### Viral Spike Model

| Spike Type | Peak Multiplier | Duration | Planning Relevance |
|------------|----------------|----------|--------------------|
| Type 1: Content viral | 2–2.5× | 30–90 min | Most common; handled by Default B at current threshold |
| Type 2: Live event | 3–4× | 2–4 hours | Infrastructure sizing target |
| Type 3: Platform event | 1.5–2× | 4–8 hours | Handled by Default A |
| Type 4: External crisis | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Spike peak rates (14/DAU design basis):**

```
Normal peak (High scenario, 14/DAU, 90%/3hr): 4,083/sec

Type 1 at 2.25×:   9,187/sec  → Default B territory; Tier 3 suspended
Type 2 at 3.5×:   14,291/sec  → above Type 4 threshold; Tier 1 only
Type 4 at 5×:     20,415/sec  → Tier 1 only; Tier 2 queued
```

**Note on Default B threshold calibration:** See the dedicated subsection below.

---

#### Tiered Degradation

| Load Level | Response | Tier 1 | Tier 2 | Tier 3 |
|------------|----------|--------|--------|--------|
| < 3,200/sec | Normal | Unaffected | Unaffected | Normal |
| 3,200–3,600/sec | Yellow alert | Unaffected | Unaffected | Unaffected |
| 3,600–5,200/sec | Default A: Tier 3 poll interval increased | Unaffected | Unaffected | Reduced throughput; queue grows |
| > 5,200/sec ≥50 sec | **Default B: Tier 3 suspended** | Unaffected | Unaffected | Suspended; delivered after spike |
| > 7,500/sec ≥5 min | Tier 2 rate-limited to 50% | Unaffected | Delayed | Suspended |
| > 10,000/sec (Type 4) | Tier 1 only | Unaffected | Queued (bounded) | Queued (bounded) |

**Threshold revision note:** All thresholds have been recalculated using the 14/DAU + 3-hour concentration design basis (4,083/sec normal peak). Default A now activates at 3,600/sec, which is 12% above the normal peak, providing a buffer before degradation engages. Default B activates at 5,200/sec, which requires a 27% spike above normal peak — corresponding to approximately a Type 1 viral event at the lower end of its multiplier range. This is the correct framing: Default B should respond to genuine spikes, not to normal operation at the higher end of the per-DAU range.

---

#### Default B — Fully Specified

**1. Detection:**

A dedicated metrics process polls Redis `LLEN` on each tier queue every 10 seconds and publishes throughput rate to a separate Redis key (`system:throughput_rate`). This process has no notification processing responsibility and runs on its own thread pool with reserved CPU allocation.

**2. Threshold evaluation:**

Default B activates when sustained rate exceeds 5,200/sec for 5 consecutive 10-second samples (50 seconds total). The metrics process writes `system:degradation_mode = "default_b"` to Redis. Default A activates when sustained rate exceeds 3,600/sec for 3 consecutive samples (30 seconds). Both thresholds are runtime-configurable without deployment.

**3. Worker behavior:**

Tier 3 workers poll `system:degradation_mode` at the start of each processing loop. When `default_b` is set, workers complete their current job, then sleep 60 seconds before rechecking.

**4. Recovery with staggered restart:**

The metrics process clears `default_b` when sustained rate falls below 4,200/sec for 5 consecutive samples. On waking from the 60-second sleep, each Tier 3 worker checks the degradation flag and, if cleared, waits an additional `random(0, 30)` seconds before resuming. Workers process at 50% of normal rate for the first 5 minutes after recovery, implemented by sleeping 2× the normal inter-job interval. Full rate resumes after 5 minutes if the degradation flag has not been re-set.

**Worker count and jitter analysis:** The Tier 3 worker pool is sized at 24 workers (see §1.3). With 24 workers and a 30-second uniform jitter window, the expected number of workers waking in any given second is 24/30 = 0.8 workers/second. The maximum plausible clustering (all workers in the same 5-second window by chance) has probability (5/30)^24 ≈ 0, making meaningful clustering negligible. The 30-second jitter window is sufficient for 24 workers. If the worker count is scaled beyond 60, the jitter window should be increased to 60 seconds. This threshold is documented in the runbook.

**5. Metrics process failure mode — complete specification:**

The metrics process publishes a heartbeat key (`system:metrics_heartbeat`) with a 15-second TTL every 10 seconds. Tier 3 workers check this key in addition to the degradation flag.

- **If the