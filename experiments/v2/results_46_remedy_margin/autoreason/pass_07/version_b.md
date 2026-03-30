# Notification System Design — Revised v3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. It incorporates direct responses to eleven specific criticisms of the prior version. Where those criticisms identified real problems, the design changes. Where they identified presentation failures, the presentation changes. Where they identified genuine unresolvable tensions, those are stated plainly without the prior version's habit of treating transparency as a substitute for resolution.

**Three architectural bets:**

1. **Separate Redis instances per priority tier** — isolation is real only with separate infrastructure. Section 2.1 explains the cost and what it buys.

2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs, ElastiCache, RDS. Engineering time goes to integration quality, not plumbing.

3. **Validation before commitment** — the week-2 cohort checkpoint now precedes infrastructure procurement, not follows it. This required restructuring the timeline. Section 6 explains what changed and what it costs.

**Eleven criticisms addressed — summary before detail:**

The prior version's week-2 validation gate was presented as a check but functioned as post-hoc confirmation of decisions already made. The revised timeline defers infrastructure procurement until after the gate fires. This is the most significant structural change in this version.

The >5× gap between decision window and fix time was acknowledged but not handled. This version describes the actual interim operating mode during a hypothetical 5–7 month rebuild: aggressive batching, reduced notification volume, and explicit SLA degradation. "Executive sponsorship" is not a contingency plan and is removed.

LIFO behavior was understated. This version acknowledges it affects every period of meaningful queue accumulation, not just extreme spike drains, and changes the recommendation: P1 uses Redis Sorted Sets, not Lists. The throughput overhead is accepted.

The 3-minute manual scaling estimate was load-bearing and unvalidated. This version removes it from the spike math and replaces the spike delay calculations with ranges that span the plausible response time envelope.

P0 Sorted Sets were solving the wrong problem. Auth code correctness is a latency problem, not an ordering problem. The P0 design now addresses latency directly: P0 notifications bypass the queue entirely.

The DAU/MAU sensitivity analysis omitted compounding effects. This version shows the 35% scenario as a system-wide stress test, not a set of independent adjustments.

Tier reweighting assumed stable tier boundaries. This version acknowledges that within-tier rates may be inflated across all tiers in an early adopter cohort and treats the corrected estimate as a ceiling, not a point estimate.

The SMS default decision was an engineer making a financial commitment without authorization. This version requires explicit authorization before any uncapped spending path is implemented.

Scenario A spike math was never completed. This version provides the quantitative drain analysis.

Critical load-bearing numbers were deferred to sections not shown. This version includes all sections.

The incremental delivery timeline conflicted with the validation gate. This version restructures the schedule so the gate precedes the build commitment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — see Section 1.1a |
| Notifications/user/day | ~17 | Planning ceiling — see Section 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike — Scenario A | 20× instantaneous, 90–120 sec | Single viral post fanout |
| Viral spike — Scenario B | 5× sustained, 10–30 min | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

**On the 17/day figure as a planning ceiling, not a validated estimate:**

The prior version described cohort validation as if it would confirm or refine this number before infrastructure was built. The criticism is correct: all sizing decisions preceded the validation, making the gate a post-hoc check. This version makes the relationship explicit.

The 17/day figure is a planning ceiling derived from comparable social platforms at similar MAU. We size infrastructure to handle it. The week-2 cohort checkpoint (Section 1.2) cannot reduce this ceiling before procurement decisions are made — but it can detect if the actual rate is dramatically higher, which is the case that would break the design. We are buying insurance against the upside surprise, not validating the baseline.

Infrastructure procurement is deferred until after the week-2 checkpoint. Section 6 explains the timeline implications.

### 1.1a DAU/MAU Sensitivity: Compounding Effects

The prior version showed DAU/MAU ratio effects on individual variables in isolation. A 35% ratio does not produce independent adjustments — it stresses multiple components simultaneously. The correct analysis is a system-wide stress test.

**Baseline (30% DAU/MAU):**
- DAU: 3M
- Notifications/day: ~50M
- Sustained peak: ~1,750/sec
- P1 workers required: 30 (derived in Section 2.3)
- Redis P1 queue memory at 2M item spike ceiling: ~4GB
- RDS write throughput: ~2,000 writes/sec sustained peak

**35% scenario — compounded:**
- DAU: 3.5M
- Notifications/day: ~59.5M
- Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6)
- Redis P1 queue memory at 2M item spike ceiling: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Spike Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)
- 36 P1 workers at 350/sec: 12,600/sec — headroom holds
- Spike Scenario B arrival rate at 10×: ~20,800/sec — drain time extends to ~29 minutes vs. ~24 minutes at baseline

**The compounding concern:** Redis memory and RDS write throughput both approach thresholds simultaneously. The 35% scenario does not break any single component, but it creates a situation where Redis needs additional nodes *and* RDS needs read replica offloading *and* worker counts need adjustment — all at the same time. If the system is running at 35% DAU/MAU and a Scenario B spike occurs, the combined load on Redis (queue depth) and RDS (status writes) is approximately 40% above baseline planning figures.

**Trigger for action:** If DAU tracks above 32% for two consecutive weeks, E1 initiates a coordinated capacity review covering Redis, RDS, and workers together — not sequentially. The review completes within one week. This is a configuration change, not a rebuild, but it requires treating the components as a system rather than independent services.

**Decisions not sensitive to this ratio:** Queue architecture, channel selection logic, preference management design, failure handling. These are correct across the plausible range.

### 1.2 The 17/day Ceiling: Cohort Validation with Corrected Scope

**What the cohort validation actually does:**

The 50K-user beta cohort produces a week-2 measurement. The purpose of this measurement is not to validate the 17/day ceiling — it is to detect if the actual rate is dramatically higher than the ceiling, which would indicate the planning assumption is wrong in a direction that breaks the design.

The validation is not symmetric. A measurement showing 8/day is good news but does not require action (we have excess capacity). A measurement showing 100/day is a crisis. The gate is calibrated for asymmetric response.

**The cohort bias problems — both of them:**

*Problem 1: Wrong tier proportions.* Early adopter cohorts over-represent power users. We apply scale-representative tier weights (5%/35%/60%) rather than observed cohort weights (estimated 20–30% power users). This corrects for having too many power users in the cohort.

*Problem 2: Inflated within-tier rates.* The prior version acknowledged this but understated it. Tier reweighting adjusts proportions, not rates. Early adopters in every tier — including Tier 3 passive users — are likely more engaged than the eventual general population in the same tier. A Tier 3 early adopter chose to try a new social app; a Tier 3 general population user may have been invited by a friend and barely uses it. The within-tier rates we observe in week 2 are probably inflated across all tiers, not just in the power user tier.

**The consequence:** Even after tier reweighting, the corrected estimate is probably still an overestimate of steady-state rates. We treat it as a ceiling, not a point estimate. The ceiling is useful: if the corrected estimate is below 17/day, we proceed. If it is above 17/day, we have a problem. The exact value within the sub-17 range does not change our infrastructure decisions — we have already sized to 17/day.

**The decision gate:**

At end of week 2, E1 reviews the bias-corrected estimate:

| Corrected Estimate vs. 17/day | Signal Interpretation | Action | Owner | Window |
|-------------------------------|----------------------|--------|-------|--------|
| ≤ 17/day | Ceiling holds; within-tier inflation may mean actual rate is lower | Proceed with procurement | E1 | — |
| 17–34/day (≤ 2×) | Ceiling is wrong; moderate overrun | Increase worker counts before procurement; Redis sizing unchanged | E1 | 72 hours |
| 34–85/day (2–5×) | Ceiling is significantly wrong | Delay procurement; add Redis nodes; revisit architecture | E1 + lead | 1 week |
| > 85/day (> 5×) | Ceiling is fundamentally wrong | See Section 1.2a | Engineering lead + executive sponsor | See below |

**Timing:** The week-2 checkpoint fires before infrastructure procurement. Section 6 shows the revised timeline. If the checkpoint is missed or delayed, procurement is also delayed — not accelerated.

### 1.2a The >5× Case: Interim Operating Mode, Not Just a Gap

The prior version acknowledged the gap between the 1–2 week decision window and the 5–7 month rebuild time. It then described "executive sponsorship" and a "go/no-go" as the resolution. The criticism is correct: naming the gap is not closing it.

**What actually happens during a 5–7 month rebuild while the system is live:**

The existing queue infrastructure cannot handle >5× the planned load. The system will fall over if we run it at full volume. The interim operating mode is deliberate volume reduction:

1. **Aggressive batching:** All P1 and P2 notifications are batched at 15-minute intervals instead of near-real-time. This reduces instantaneous throughput by roughly 8–10× at the cost of notification latency. Users experience delayed notifications; they do not experience missing notifications.

2. **Notification type suppression:** Social engagement notifications (likes, comments on non-viral content) are suppressed or delivered as daily digests. Auth notifications, direct messages, and account security alerts are preserved. This reduces volume by an estimated 40–50%.

3. **Explicit SLA degradation:** The product team communicates to users that notification delivery is operating in a reduced mode. This is a product decision, not a technical one, but the technical team must surface the requirement.

Combined, these measures can reduce effective throughput demand by approximately 60–70%, buying time for the rebuild without causing correctness failures.

**What this costs:**

- User experience degrades materially for 5–7 months.
- The product team must make and communicate the SLA change.
- The rebuild runs in parallel with a degraded live system, which is harder than a greenfield build.

**The honest statement:** If the >5× case is confirmed in week 2, the 6-month project plan does not survive intact. There is no technical path that avoids this. The purpose of the week-2 checkpoint is to surface this before the month-2 build milestone, not to prevent it from happening. If the signal is confirmed, the project timeline and scope are renegotiated with executive involvement. This is stated here, not deferred to a footnote.

**False positive risk:** Early cohort measurements are noisy. A >5× signal in week 2 may reflect measurement artifact rather than true load. Before triggering the rebuild decision, E1 runs a second measurement in week 3 with a larger cohort sample (if available) and reviews the raw event distribution for obvious outliers. The rebuild decision requires two consistent measurements or one measurement with a clear mechanistic explanation.

### 1.3 Spike Handling: Quantified for Both Scenarios

The prior version provided full math for Scenario B and qualitative description for Scenario A. The criticism is correct: Scenario A is the more extreme case and requires quantitative analysis.

**Worker throughput baseline (derived in Section 2.3):**
- P1 workers: 30, each processing ~350 notifications/sec for mixed-channel load
- Total P1 sustained capacity: ~10,500/sec
- Baseline sustained peak: ~1,750/sec
- Queue is near-empty under normal operation

**Scenario A: 20× instantaneous spike, 90–120 seconds**

Arrival rate during spike: ~35,000/sec
Worker capacity: ~10,500/sec
Net accumulation rate: ~24,500/sec

Items accumulated during 90-second burst: ~2.2M
Items accumulated during 120-second burst: ~2.94M

Post-spike: arrival rate drops to baseline (~1,750/sec). Workers are now draining at net ~8,750/sec (10,500 capacity minus 1,750 ongoing arrival).

Drain time for 2.2M items: ~252 seconds (~4.2 minutes)
Drain time for 2.94M items: ~336 seconds (~5.6 minutes)

The queue absorbs the burst. A user who received a social notification at the start of the spike will receive it approximately 4–6 minutes after generation. This is acceptable for social notifications. P0 notifications bypass the queue entirely (see Section 2.2) and are unaffected.

**Alert thresholds in context:** The 500K-item warning threshold fires approximately 20 seconds into a Scenario A burst. The 2M-item page threshold fires at approximately 82 seconds — near the end of the burst. This means the page fires as the burst is ending, not in time to trigger scaling before the burst completes. Manual scaling during a Scenario A burst does not help; the burst is over before intervention is possible. The alert exists to document the event, not to trigger a response.

**Scenario B: 5× sustained, 10–30 minutes**

Arrival rate: ~8,750/sec
Worker capacity: ~10,500/sec
Net headroom: ~1,750/sec

Under Scenario B as defined, the queue drains. No accumulation occurs. Workers handle the load.

**Scenario B at 10× (undesigned-for):**

Arrival rate: ~17,500/sec
Worker capacity: ~10,500/sec
Net accumulation: ~7,000/sec

Over 30 minutes: ~12.6M items

Manual scaling response — range, not point estimate: The prior version used 3 minutes as a load-bearing figure. This version does not. The actual response time depends on: time for the alert to fire and page the on-call engineer (typically 1–3 minutes), time for the engineer to assess and decide to scale (2–10 minutes depending on context), and time for new workers to come online (1–3 minutes). The plausible range is 4–16 minutes from spike onset to additional capacity online.

| Response time | Workers added | Capacity during response gap | Queue depth at response | Post-response drain rate | Drain time |
|---------------|---------------|------------------------------|------------------------|--------------------------|------------|
| 4 min | +20 | 10,500/sec | ~1.68M | ~17,500/sec net drain | ~96 sec |
| 10 min | +20 | 10,500/sec | ~4.2M | ~17,500/sec net drain | ~240 sec |
| 16 min | +20 | 10,500/sec | ~6.72M | ~17,500/sec net drain | ~384 sec |

Even at the 16-minute response time, post-response drain completes in approximately 6.4 minutes. Total delay for a notification generated at spike onset under the worst case: ~22 minutes. This is degraded but not catastrophic for social notifications. P