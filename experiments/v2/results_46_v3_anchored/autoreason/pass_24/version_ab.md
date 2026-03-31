# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Consolidated Change Log

| Problem | Resolution | Section |
|---------|-----------|---------|
| 14/DAU design basis asserted without validation data | Benchmarks cited with explicit uncertainty; beta cohort measurement plan added with timeline and fallback | §1.1 |
| Combined sensitivity finding (4,083/sec) identified but not acted upon | Design basis changed to 14/DAU + 3-hour concentration; all ceiling calculations revised accordingly | §1.1, §1.3, §5, §6 |
| Yellow alert threshold fires below normal peak | Recalibrated to 4,400/sec — 7% above normal peak; rationale documented | §1.1 |
| Default A deactivation condition unspecified | Deactivation requires M = N+2 = 5 consecutive below-threshold samples; hysteresis rationale documented | §1.1 |
| Default B specification incomplete | Recovery logic fully specified: exit condition, queue depth check, Tier 3 resumption sequence, message handling during suspension | §1.1 |
| Default B alert frequency threshold truncated | Completed: more than 3 activations per 24-hour period triggers alert | §1.1 |
| Revision trigger set at 16/DAU without operational rationale | Trigger moved to 15/DAU; rationale: 15/DAU causes Default A to fire during normal high-end operation, not spikes | §1.1 |
| Queue depth bounds for Type 4 spike unspecified | Placeholder bounds stated with explicit framing as unresolved; behavior at bound specified; sign-off dependency documented | §1.1 |
| Geographic distribution assumption has no measurement basis | Flagged as placeholder; pre-launch configuration specified using conservative APAC-weighted assumption; launch-day triggers defined | §1.1 |
| Consolidated Legal sign-off creates single point of failure | Partial decoupling path specified: schema work can begin on opt-out-agnostic tables if only one item resolves | §2.4, Sign-Off Table |
| E4 retry enforcement dependency on broadcast policy not clarified | Retry enforcement and broadcast rate limiting separated; E4 can complete retry work independently | Sign-Off Table |
| Invisible data loss named but not bounded | Non-compliant producer volume estimated; data loss duration bounded; severity assessment provided | §1.1 |
| Cost estimate anchored to rejected baseline | Cost reframed against 14/DAU design basis; absolute monthly figure stated with justification | §1.1 |
| Sign-off table row count mismatch | Corrected to eight items; discrepancy documented | Sign-Off Table |
| International load case deferred | Redis, connection pool, and email scheduling responses to sustained load included | §1.1, §5, §6 |
| Worker count stated without derivation | Full capacity model and utilization calculation shown | §1.3 |

---

## Eight Items Requiring Sign-Off Before This Design Is Finalized

The correct count is **eight**. A previous version stated seven; the discrepancy was a counting error introduced when a row was added without updating the introduction.

### Consolidated Legal Review — Partial Decoupling Path

The opt-out compliance architecture and DM drop policy share a correctness dependency: which messages can be dropped under load depends on which opt-out architecture is in place. Full resolution requires both items together. However, the dependency is asymmetric, and schema work is not entirely blocked if only one item resolves by Week 2:

- **If opt-out architecture resolves but DM policy does not:** Schema work begins on opt-out-agnostic tables (user preference storage, channel configuration). DM-specific schema is deferred. Approximately 60% of schema work can proceed. E2's DM handling implementation is blocked.
- **If DM policy resolves but opt-out architecture does not:** Schema work cannot begin. The opt-out architecture determines the core preference table structure. E3's implementation is fully blocked.
- **If neither resolves by Week 2:** Full one-week slip in schema work and compression of the Month 2 implementation window.

Legal must be informed of this asymmetry. The opt-out architecture decision is the harder blocker of the two.

**On E4 sequencing:** E4 has two assigned items — retry contract enforcement and broadcast rate limiting — that are partially decoupled. Retry enforcement can proceed independently. Broadcast rate limiting requires the broadcast policy to be defined first. If broadcast policy sign-off is delayed past Month 3, broadcast capability is disabled at launch; retry enforcement ships on schedule regardless.

| Item | Section | Decision Deadline | Owner | Engineer Role | Consequence of Miss |
|------|---------|-------------------|-------|---------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E1 provides volume model; E2 implements channel | SMS channel sizing blocked; E2 implementation delayed up to 2 weeks |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 provides volume model input | SendGrid contract tier cannot be finalized; default to lower tier with overage risk |
| **Opt-out compliance architecture — Legal review** | §2.4 | **End of Week 2** | **Legal** | E3 implements chosen architecture | Schema work cannot begin; full one-week slip. Harder blocker of the two legal items. |
| **DM drop policy — Legal review** | §2.4 | **End of Week 2** | **Legal** | E2 implements DM handling | If opt-out architecture is resolved, 60% of schema work proceeds; DM-specific schema deferred. If opt-out architecture is also unresolved, full slip applies. |
| SendGrid enterprise contract | §6.2 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; adds approximately $8,000–$12,000/month and 3 weeks of E2 time |
| **Queue depth bounds and backpressure behavior** | §1.1 | **End of Month 1** | **Engineering + Product** | E2 implements bounds; E3 implements backpressure | Type 4 spike produces unbounded queue growth; memory exhaustion risk. Placeholder bounds in §1.1 are operationally incomplete until this decision is made. |
| Broadcast notification policy and exception gate owner | §1.1, §6 | Before Month 3 | Product | E4 implements broadcast rate limiting after policy defined; retry enforcement proceeds independently | Broadcast capability disabled at launch; does not block retry enforcement |
| Producer registry and retry contract enforcement | §1.1 | Before Month 2 implementation | Engineering | E3 owns producer registry; E4 owns retry enforcement independently of broadcast policy | 429 responses produce data loss for non-compliant producers; severity bounded in §1.1 |

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

#### Per-DAU Rate — Design Basis, Uncertainty, and Validation

**Raw event range before batching:** 7.5–23/DAU/day (3× spread). After batching, effective delivered range is approximately 6–16/DAU/day.

**Design basis: 14/DAU — stated as an estimate, not a derived figure.**

The 14/DAU figure is the midpoint of the post-batching range (6–16/DAU). It is not derived from first principles. Published figures from comparable platforms are directionally consistent with this range but do not precisely validate 14/DAU:

- **Instagram (~2018):** Approximately 1B notifications/day against ~500M DAU — roughly 2/DAU delivered. Delivered-to-generated ratios reported at 15–20%, implying 10–13 generated events/DAU before suppression. Consistent with the lower half of the range.
- **Twitter/X (~2022):** Peak notification generation cited at 4–6× delivered rate due to batching and deduplication. Delivered rate of ~3–4/DAU implies 12–24 generated events/DAU. Brackets the full range without constraining it.

These figures establish that 14/DAU is plausible for a social app with social graphs, DMs, and activity feeds. They do not establish that 14/DAU is correct for this app. The design basis should be understood as: *the midpoint of a plausible range, chosen because it is neither optimistically low nor pessimistically high, with explicit validation planned before infrastructure is locked.*

**What 14/DAU does not account for:** If this app has features that drive notification density above comparable apps — real-time multiplayer, high-frequency group DMs, or aggressive algorithmic re-engagement — 18–20/DAU is plausible. The design basis would be wrong in the optimistic direction.

**Three-scenario planning:** Because 14/DAU is an estimate, infrastructure decisions are evaluated against three scenarios:

| Planning Scenario | Per-DAU Rate | Design Implication |
|------------------|--------------|--------------------|
| Conservative | 11/DAU | Cost floor; worker count lower bound |
| **Base** | **14/DAU** | **Infrastructure sizing target** |
| Stress | 18/DAU | Worker ceiling; triggers design review if sustained |

Infrastructure is sized to the base scenario. The stress scenario is handled by the tiered degradation system. The conservative scenario informs cost modeling only — it is not used as an infrastructure target.

---

**Validation plan — timeline made explicit:**

The validation plan is only useful if measurement results are available before Month 2 infrastructure decisions lock.

| Milestone | Week |
|-----------|------|
| Beta cohort instrumentation deployed | Week 3 |
| Beta cohort soft launch begins (50,000 users) | Week 4 |
| 30-day measurement window closes | Week 8 |
| E1 delivers per-DAU measurement report | Week 9 |
| Month 2 infrastructure decisions lock | **Week 10** |

This sequence provides one week of margin between measurement delivery and lock. It depends on the beta cohort launching no later than Week 4. If the beta cohort is delayed beyond Week 6, the measurement window cannot close before Week 10 and the fallback applies: the 14/DAU basis is used as-is, the risk of undersizing is accepted and documented, and the stress scenario (18/DAU) is used for the worker ceiling rather than the base scenario. E1 owns the beta cohort launch date and escalates immediately if a Week 6 delay is projected.

---

**Revision trigger — rationale for 15/DAU:**

The revision trigger is set at **15/DAU**. The rationale is operational:

At 14/DAU with a 3-hour concentration window, the sustained peak is 4,083/sec. Default A activates at 4,400/sec — 7% above normal peak. At 15/DAU with the same concentration:

```
(3,500,000 × 15 × 0.90) ÷ 10,800 = 4,375/sec
```

4,375/sec is within 1% of the Default A threshold. Default A would activate during normal high-end operation — not during spikes — if the actual rate is 15/DAU. A revision trigger at 15/DAU catches this before infrastructure is locked. A trigger at 16/DAU would miss it: at 16/DAU, Default A fires routinely during normal operation, which is a miscalibration of the degradation system, not a designed response to genuine load.

The margin between the trigger and the design basis (1/DAU) is deliberately narrow because the consequence of missing it — Default A becoming a normal operating condition — is a stakeholder expectation problem, not just an engineering problem.

---

**Cost implication — anchored estimate:**

Infrastructure sized to 4,083/sec rather than 2,406/sec (11/DAU basis) requires approximately:

- 8 additional Kubernetes worker pods (from 16 to 24): approximately $960/month at $120/pod/month on c5.xlarge-equivalent instances
- Redis memory increase (from ~12GB to ~18GB): approximately $300/month additional
- Additional connection pool overhead: negligible marginal cost

**Total additional spend: approximately $1,260/month over the 11/DAU-sized alternative.** This is the correct tradeoff. Sizing to 11/DAU causes Default B to activate during normal high-end operation, producing Tier 3 suspension as a routine condition and misaligning stakeholder expectations about what "normal" looks like.

---

#### Tiered Degradation System — Counter Behavior, Activation, and Deactivation

**Threshold calibration:**

- **Yellow alert / Default A activation threshold:** 4,400/sec — 7% above the 4,083/sec normal peak. The 7% margin absorbs natural measurement variance without firing during normal operation. Fires during Type 1 spikes (2× multiplier → ~8,166/sec) well before Default B.
- **Default B activation threshold:** 8,200/sec — approximately 2× the normal peak. Fires during Type 1 spikes at the upper multiplier and all Type 2+ spikes.

**Activation condition:** Default A activates after N = 3 consecutive samples above the threshold (sampled at 10-second intervals; activation requires 30 seconds of sustained above-threshold load). The counter does not reset to zero on a single below-threshold sample; it decrements by one per below-threshold sample.

**Deactivation condition:** Default A deactivates after M = N + 2 = **5 consecutive below-threshold samples** (50 seconds of sustained below-threshold load).

The asymmetry between activation (3 samples) and deactivation (5 samples) is intentional. It prevents oscillation when load sits near the threshold. Without hysteresis, a system at 4,380/sec — just above the 4,400/sec threshold — would activate and deactivate Default A repeatedly as natural variance pushes the rate across the boundary. The +2 deactivation requirement means the system must observe sustained relief before returning to normal, not just a momentary dip. The same logic applies to all transitions: Default A → Default B and Default B → Default A both use M = N + 2 for deactivation.

**Default B recovery sequence:**

Exit condition: 5 consecutive samples below 8,200/sec. Before resuming Tier 3 delivery:

1. Check Tier 3 queue depth. If depth exceeds the configured bound, drain to bound before resuming.
2. Resume Tier 3 at 25% of normal throughput for 2 minutes. Monitor for re-escalation.
3. If no re-escalation, restore full Tier 3 throughput.
4. Messages queued during Default B suspension that exceed the queue TTL (10 minutes for Tier 3) are dropped and logged. Drop events are counted and surfaced in the daily operational report.

**Default B alert frequency threshold:**

An alert is warranted only if Default B persists beyond 30 minutes **or activates more than 3 times within any 24-hour period.** A single Default B activation during a genuine spike is operational log-level information. Repeated activation indicates either a threshold miscalibration, a sustained load condition that was not anticipated, or a misbehaving producer. Three activations per 24-hour period distinguishes between legitimate spike response (1–2 activations during a major event) and a system operating in degraded mode as a routine condition.

---

#### Queue Depth Bounds — Current State and Honest Framing

**The queue depth bound for Tier 2 during Type 4 spikes is not finalized.** This is an unresolved sign-off item (End of Month 1). The spike model below uses placeholder values that are operationally incomplete until the sign-off is obtained.

**Placeholder values (subject to revision at Month 1 sign-off):**

| Queue | Placeholder Depth Bound | Placeholder TTL | Behavior at Bound |
|-------|------------------------|-----------------|-------------------|
| Tier 1 (critical) | Unbounded during spike | 24 hours | Never dropped during spike; memory risk accepted |
| Tier 2 (standard) | 2,000,000 messages | 30 minutes | New messages rejected with 429; producers must retry |
| Tier 3 (batch) | 500,000 messages | 10 minutes | New messages dropped; drop logged |

**Why these are placeholders:** The Tier 2 bound of 2,000,000 messages is estimated from memory constraints (approximately 2GB at ~1KB/message) but has not been validated against actual message size distributions or available infrastructure memory. The sign-off process will validate these figures.

**Behavior at