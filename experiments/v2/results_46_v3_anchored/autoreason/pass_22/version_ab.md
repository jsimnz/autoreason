# Notification System Design — Revision 4
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Change Log from Previous Revisions

This revision synthesizes Revisions 2 and 3. Structural problems resolved across both versions are consolidated here. No issues are carried forward unresolved.

| Problem | Resolution | Section |
|---------|-----------|---------|
| Combined sensitivity finding (4,083/sec) identified but not acted upon | Design basis changed to 14/DAU + 3-hour concentration; worker, Redis, and connection pool sizing revised accordingly | §1.1, §1.3, §5, §6 |
| Circular dependency between opt-out compliance and DM drop policy sign-offs | Consolidated into single Legal review; dependency explained | §Sign-Off Table, §2.4 |
| Document cut off mid-sentence in metrics process failure specification | Failure mode specification completed in full | §1.1 |
| Default B threshold calibrated against wrong design basis | Thresholds recalculated against 14/DAU + 3-hour basis; Default B now triggers on genuine spikes, not normal high-end operation | §1.1 |
| International load case deferred to absent sections | Redis, connection pool, and email scheduling responses to sustained load included in this document | §1.1, §5, §6 |
| Staggered restart jitter analysis incomplete without worker count | Worker count specified (24); jitter analysis completed relative to count with scaling threshold documented | §1.1 |
| E4 workload conflict between producer registry and broadcast rate limiting unanalyzed | E4 sequencing analyzed; conflict resolved with explicit ordering | §1.3, §Sign-Off Table |
| Per-DAU monitoring threshold had no owner, timeline, or reassessment procedure | Owner named (E1); reassessment procedure and timeline specified | §1.1 |
| Opt-out correctness difference not explained in terms Legal can evaluate | Failure scenarios described in plain language for Legal review | §2.4 |
| Metrics process failure mode inverted in earlier revision | Corrected and fully specified: failure defaults to Default A, not normal operation | §1.1 |

---

## Seven Items Requiring Sign-Off Before This Design Is Finalized

**On the consolidated Legal review:** The opt-out compliance architecture (previously a standalone sign-off) and the DM drop policy (previously a separate sign-off) share a correctness dependency. Whether DMs can be dropped under load depends on which opt-out architecture is chosen — they are not independent questions. Legal must evaluate them together. The consolidated deadline is **End of Week 2**. Schema work scheduled to begin Week 3 is blocked until this review is complete. A missed deadline causes a one-week slip in schema work, which compresses the Month 2 implementation window. This consequence is documented in §1.3.

**On E4 sequencing:** E4 has two assigned items — producer registry enforcement and broadcast rate limiting — that cannot be parallelized because the broadcast policy defines the rate limits that the enforcement layer must implement. The broadcast policy sign-off (Product, before launch) must precede E4's enforcement implementation. This ordering is documented in §1.3. If the broadcast policy sign-off is delayed past Month 3, broadcast capability is disabled at launch and the enforcement layer ships without broadcast support.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked; E2 implementation delayed |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized |
| **Opt-out compliance architecture AND DM drop policy — consolidated Legal review** | §2.4, §1.1 | **End of Week 2** | **Legal** | E3 implements whichever architecture is chosen; E2 implements DM handling | Schema work (Week 3) blocked. These two items share a correctness dependency and must be evaluated simultaneously. Failure scenarios for each architecture are in §2.4. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; full cost and timeline in §6.2 |
| Queue depth bounds and backpressure behavior | §1.1 | End of Month 1 | Engineering + Product | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded queue growth |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before Month 3 | Product | E4 implements rate limiting after policy is defined; must precede enforcement layer work (see §1.3) | Broadcast capability disabled at launch; enforcement layer ships without broadcast support |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns enforcement layer after broadcast policy is resolved | 429 responses produce invisible data loss for non-compliant producers |

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

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day. The 11/DAU/day figure sits near the midpoint of this range.

**Peak rate sensitivity (High scenario, 90%/4hr concentration):**

```
Formula: peak_rate = (3,500,000 × per_DAU × 0.90) ÷ 14,400
```

| Per-DAU Rate | Peak Rate/sec | vs. 11/DAU baseline | Worker ceiling headroom |
|-------------|---------------|---------------------|------------------------|
| 6/DAU | 1,313/sec | −45% | Comfortable |
| 8/DAU | 1,750/sec | −27% | Comfortable |
| **11/DAU** | **2,406/sec** | **baseline** | **Narrow (244/sec)** |
| 14/DAU | 3,063/sec | +27% | Default A fires at launch |
| 16/DAU | 3,500/sec | +45% | Default B fires at launch |

**The 14/DAU scenario is plausible, not extreme.** It occurs if batching is less aggressive than assumed or if DM volume is higher than modeled. Both conditions are observable from day one.

**Combined sensitivity — the critical scenario:**

The two largest sources of uncertainty compound. A 14/DAU rate with a 3-hour concentration window produces:

```
(3,500,000 × 14 × 0.90) ÷ 10,800 = 4,083/sec
```

This is inside Default B territory under the 11/DAU-calibrated thresholds from day one. Previous revisions identified this scenario as "plausible, not extreme" but made no changes to sizing. This revision corrects that omission.

**Design basis change:** This design is sized to the 14/DAU + 3-hour concentration scenario (4,083/sec sustained peak) for all ceiling calculations: worker count, Redis memory, connection pool sizing, and Default B threshold calibration. The 11/DAU baseline is retained for normal-load cost modeling only.

**Cost implication of this choice:** Approximately 30–40% higher infrastructure spend during spike windows compared to 11/DAU sizing. This is the correct tradeoff. The alternative is a system that enters Default B as a routine condition from launch, producing real user impact (Tier 3 suspension) and misaligned stakeholder expectations about what "normal" looks like.

**Per-DAU monitoring and reassessment:**
- Instrument notification dispatch counts per active user as a daily metric from day one.
- Owner: E1. Metric: 30-day rolling average of delivered notifications per DAU.
- **Reassessment trigger:** If the 30-day rolling average exceeds 13/DAU, E1 initiates a worker ceiling reassessment within two weeks. The reassessment evaluates whether the worker count (§1.3) requires scaling before the next capacity planning cycle.
- This is a defined measurement with a defined response threshold, not a reactive process.

---

#### Concentration Assumption — Sensitivity Analysis

**Standard concentration sensitivity (High scenario, 14/DAU design basis):**

| Concentration % | Window (hours) | Peak Rate/sec | Infrastructure status |
|----------------|----------------|---------------|----------------------|
| 85% | 4 hours | 2,604 | Below Default A threshold |
| 90% | 4 hours | 3,063 | Default A territory |
| **90%** | **3 hours** | **4,083** | **Design basis ceiling** |
| 95% | 3 hours | 4,306 | 5% above design basis; Default B activates |
| 90% | 2.5 hours | 4,900 | Default B; Tier 3 suspended |

The design basis ceiling (4,083/sec) sits at the 90th percentile of plausible concentration scenarios at 14/DAU. Scenarios above it are handled by the tiered degradation system — they produce Default B activation, which is designed behavior, not failure.

---

#### International Load Case — Sustained Load Analysis

**Distribution assumption:** If the user base is 40% US, 30% Europe, 30% Asia-Pacific, no single 4-hour window dominates. The approximate sustained load profile:

```
US peak (6–10pm ET):     ~35% of daily load in 4 hours → ~875/sec sustained
EU peak (7–11pm CET):    ~30% of daily load in 4 hours → ~750/sec sustained
APAC peak (7–11pm JST):  ~30% of daily load in 4 hours → ~750/sec sustained
Maximum overlap:          ~1,400–1,800/sec
```

**The peak rate in this scenario is lower** than the 4,083/sec design basis and does not change the worker ceiling. The international scenario creates a different problem: **sustained load with no recovery window.** The system runs at 1,000–1,800/sec for 12–16 hours continuously, rather than 4,000/sec for 4 hours followed by 20 hours of low load.

**Infrastructure responses — all included in this document:**

**Redis memory (§5):** The sustained load case prevents the low-traffic window that normally allows stale key expiration and data structure compaction. Redis memory sizing uses the sustained load case: peak key count is assumed present for 16 hours rather than 4. The per-entry overhead calculation and resulting memory bound are in §5.

**Connection pooling (§6):** APNs and FCM connections must be maintained across a 16-hour active window. Connection recycling logic that assumes a daily low-traffic window is not safe in the international case. The connection pool specification in §6 uses continuous operation assumptions: connections are recycled on a time-based schedule (every 4 hours) rather than an activity-based schedule. This adds implementation complexity but is required for correctness when the low-traffic window does not reliably occur.

**Email scheduling (§6.2):** If re-engagement emails are scheduled based on US evening timing, they may conflict with APAC send volume against SendGrid daily API limits. The email scheduling logic distributes send volume across time zones rather than concentrating on a single evening window. Specification in §6.2.

**Worker health monitoring (§7):** Workers running at 60–70% capacity for 16 hours have different failure characteristics than workers at 95% for 4 hours. Worker health monitoring tracks per-worker error rate and memory consumption on a rolling 1-hour basis, not only during spike windows. Alerting thresholds are calibrated for sustained load conditions.

**Monitoring and reassessment trigger:** Actual geographic distribution is measured within 4 weeks of launch. If 30% or more of DAU is outside the US, connection recycling and Redis expiry configurations are reviewed against the sustained load case. Owner: E1. Review timeline: within 2 weeks of the measurement crossing the threshold.

---

#### Viral Spike Model

| Spike Type | Peak Multiplier | Duration | Planning Relevance |
|------------|----------------|----------|--------------------|
| Type 1: Content viral | 2–2.5× | 30–90 min | Most common; Default B activates at lower end of range |
| Type 2: Live event | 3–4× | 2–4 hours | Infrastructure sizing target |
| Type 3: Platform event | 1.5–2× | 4–8 hours | Handled by Default A |
| Type 4: External crisis | 4–6× | 1–6 hours | Designed failure mode; Tier 1 only |

**Spike peak rates (14/DAU design basis, 4,083/sec normal peak):**

```
Type 1 at 2.25×:   9,187/sec  → Default B; Tier 3 suspended
Type 2 at 3.5×:   14,291/sec  → Tier 1 only; Tier 2 queued
Type 4 at 5×:     20,415/sec  → Tier 1 only; Tier 2 queued (bounded)
```

**Framing:** Default B activates during Type 1 spikes. This is correct behavior. Default B should respond to genuine viral events, not to normal operation at the high end of the per-DAU range. Stakeholder communication must reflect this: Default B activation is operational log-level information. An alert is warranted only if Default B persists beyond 30 minutes or activates more than 3 times in a single day.

---

#### Tiered Degradation

| Load Level | Response | Tier 1 | Tier 2 | Tier 3 |
|------------|----------|--------|--------|--------|
| < 3,200/sec | Normal | Unaffected | Unaffected | Normal |
| 3,200–3,600/sec | Yellow alert — no action | Unaffected | Unaffected | Unaffected |
| 3,600–5,200/sec | Default A: Tier 3 poll interval increased | Unaffected | Unaffected | Reduced throughput; queue grows |
| > 5,200/sec ≥50 sec | **Default B: Tier 3 suspended** | Unaffected | Unaffected | Suspended; delivered after spike |
| > 7,500/sec ≥5 min | Tier 2 rate-limited to 50% | Unaffected | Delayed | Suspended |
| > 10,000/sec (Type 4) | Tier 1 only | Unaffected | Queued (bounded) | Queued (bounded) |

**Threshold rationale:** All thresholds are calculated against the 14/DAU + 3-hour design basis (4,083/sec normal peak). Default A activates at 3,600/sec — 12% above normal peak, providing a buffer before degradation engages. Default B activates at 5,200/sec — 27% above normal peak, corresponding to approximately the lower end of a Type 1 viral event. Thresholds are runtime-configurable without deployment to allow calibration after the first month of production data.

---

#### Default B — Complete Specification

**1. Detection:**

A dedicated metrics process polls Redis `LLEN` on each tier queue every 10 seconds and publishes the throughput rate to `system:throughput_rate`. This process has no notification processing responsibility and runs on its own thread pool with reserved CPU allocation to prevent it from being starved during high-load conditions.

**2. Threshold evaluation:**

- Default A activates when sustained rate exceeds 3,600/sec for 3 consecutive 10-second samples (30 seconds).
- Default B activates when sustained rate exceeds 5,200/sec for 5 consecutive 10-second samples (50 seconds).
- On activation, the metrics process writes `system:degradation_mode = "default_a"` or `"default_b"` to Redis.
- Both thresholds are runtime-configurable without deployment.

**3. Worker behavior under Default B:**

Tier 3 workers poll `system:degradation_mode` at the start of each processing loop. When `default_b` is set, workers complete their current job, then sleep 60 seconds before rechecking. Workers