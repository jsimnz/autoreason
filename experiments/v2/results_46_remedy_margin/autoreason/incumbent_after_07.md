# Notification System Design — Synthesis
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three architectural bets, stated with their actual limitations:

1. **Separate Redis instances per priority tier** — isolation is real only with separate infrastructure. Section 2.1 explains the cost and what it buys. Three queues on one instance is not isolation; it is labeling.

2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs, ElastiCache, RDS. Engineering time goes to integration quality, not plumbing.

3. **Validation before commitment** — the week-2 cohort checkpoint precedes infrastructure procurement. This required restructuring the timeline. Section 6 explains what changed and what it costs.

**Eight honest statements before the detail:**

The 17 notifications/user/day figure is a planning ceiling, not a validated estimate. The week-2 cohort checkpoint cannot reduce this ceiling before procurement decisions are made — but it can detect if the actual rate is dramatically higher, which is the case that would break the design. Section 1.2 describes the validation logic, both bias corrections it applies, and what it cannot fix.

The 30% DAU/MAU ratio is load-bearing and uncertain. Section 1.1 treats a 35% ratio as a system-wide stress test, not a set of independent adjustments, because the compounding effects across Redis, RDS, and worker counts are the actual risk.

The viral spike model sizes for 5× sustained, not 10×. Section 1.3 provides complete quantitative analysis for both scenarios and states what the product team must decide before month 3.

SMS costs range from $240K to $1.38M/month depending on geography. The SMS authentication fallback described in prior versions — push notification when the budget cap is hit — does not work: a user requesting an auth code typically has no active session to receive push. Section 1.4 describes the correct options and what business decision is required before month 3.

Redis Lists with BRPOP give LIFO behavior under accumulation. This affects every period of meaningful queue depth, not only extreme spikes. Section 2.2 explains why P1/P2 accept this tradeoff and why P0 uses a different structure.

P0 notifications bypass the queue entirely. Auth codes are a latency problem, not an ordering problem. Sorted Sets were solving the wrong problem.

The >5× validation failure case produces a gap between the 1–2 week decision window and a 5–7 month rebuild. Section 1.2a describes the actual interim operating mode — deliberate volume reduction, aggressive batching, explicit SLA degradation — not "executive sponsorship."

The operational surface is at the edge of what 4 engineers can safely own. Section 7 names what is cut and why.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — see sensitivity analysis below |
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

### 1.1a DAU/MAU Sensitivity: Compounding Effects

A 35% DAU/MAU ratio does not produce independent adjustments to individual components — it stresses multiple components simultaneously. The correct analysis is a system-wide stress test.

**Baseline (30%):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory at 2M item spike ceiling: ~4GB
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario — compounded:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)
- 36 P1 workers at 350/sec: 12,600/sec — headroom holds at 5×
- Scenario B arrival rate at 10×: ~20,800/sec — drain time extends to ~29 minutes vs. ~24 minutes at baseline

**The compounding risk:** Redis memory and RDS write throughput both approach thresholds simultaneously. The 35% scenario does not break any single component, but it creates a situation where Redis needs additional nodes *and* RDS needs read replica offloading *and* worker counts need adjustment — all at once. If the system is running at 35% DAU/MAU and a Scenario B spike occurs, combined load on Redis (queue depth) and RDS (status writes) is approximately 40% above baseline planning figures.

**Trigger for action:** If DAU tracks above 32% for two consecutive weeks, E1 initiates a coordinated capacity review covering Redis, RDS, and workers together — not sequentially. The review completes within one week. This is a configuration change, not a rebuild.

**Decisions not sensitive to this ratio:** Queue architecture, channel selection logic, preference management design, failure handling. These are correct across the plausible range.

### 1.2 The 17/Day Ceiling: Cohort Validation with Corrected Scope

**What the cohort validation actually does:**

The 50K-user beta cohort produces a week-2 measurement. The purpose is not to validate the 17/day ceiling — it is to detect if the actual rate is dramatically higher than the ceiling, which would indicate the planning assumption is wrong in a direction that breaks the design.

The validation is asymmetric. A measurement showing 8/day is good news requiring no action. A measurement showing 100/day is a crisis. The gate is calibrated for asymmetric response.

**The cohort bias — two distinct problems:**

*Problem 1: Wrong tier proportions.* Early adopter cohorts over-represent power users. We apply scale-representative tier weights (5% / 35% / 60%) rather than observed cohort weights (estimated 20–30% power users). This corrects for having too many power users in the cohort.

*Problem 2: Inflated within-tier rates.* Tier reweighting adjusts proportions, not rates. Early adopters in every tier — including Tier 3 passive users — are likely more engaged than the eventual general population in the same tier. A Tier 3 early adopter chose to try a new social app; a Tier 3 general population user may have been invited by a friend and barely uses it. The within-tier rates observed in week 2 are probably inflated across all tiers, not just the power user tier.

**The consequence:** Even after tier reweighting, the corrected estimate is probably still an overestimate of steady-state rates. We treat it as a ceiling, not a point estimate. If the corrected estimate is below 17/day, we proceed. If it is above 17/day, we have a problem. The exact value within the sub-17 range does not change infrastructure decisions — we have already sized to the ceiling.

**The tier classification timing problem:** Two weeks of data from users still discovering the product will produce unstable tier assignments. We use a simple proxy (content creation events in the first 14 days) rather than a stable behavioral model. The decision gate is calibrated to act only on large deviations, because small deviations are within the noise of an unstable early measurement.

**The decision gate:**

At end of week 2, E1 reviews the bias-corrected estimate. Infrastructure procurement is deferred until after this gate fires.

| Corrected Estimate vs. 17/day | Signal | Action | Owner | Window |
|-------------------------------|--------|--------|-------|--------|
| ≤ 17/day | Ceiling holds; within-tier inflation may mean actual rate is lower | Proceed with procurement | E1 | — |
| 17–34/day (≤ 2×) | Ceiling is wrong; moderate overrun | Increase worker counts before procurement; Redis sizing unchanged | E1 | 72 hours |
| 34–85/day (2–5×) | Ceiling is significantly wrong | Delay procurement; add Redis nodes; revisit architecture | E1 + lead | 1 week |
| >85/day (>5×) | Ceiling is fundamentally wrong | See Section 1.2a | Engineering lead + executive sponsor | See below |

**Timing:** The week-2 checkpoint fires before infrastructure procurement. If the checkpoint is missed or delayed, procurement is also delayed — not accelerated.

### 1.2a The >5× Case: Interim Operating Mode, Not a Gap

The prior version of this design acknowledged the gap between the 1–2 week decision window and the 5–7 month rebuild time, then described "executive sponsorship" as the resolution. Naming a gap is not closing it.

**What actually happens during a 5–7 month rebuild while the system is live:**

The existing queue infrastructure cannot handle >5× planned load at full volume. The interim operating mode is deliberate volume reduction:

1. **Aggressive batching:** All P1 and P2 notifications batch at 15-minute intervals instead of near-real-time. This reduces instantaneous throughput by roughly 8–10× at the cost of notification latency. Users experience delayed notifications; they do not experience missing notifications.

2. **Notification type suppression:** Social engagement notifications (likes, comments on non-viral content) are suppressed or delivered as daily digests. Auth notifications, direct messages, and account security alerts are preserved. This reduces volume by an estimated 40–50%.

3. **Explicit SLA degradation:** The product team communicates to users that notification delivery is operating in a reduced mode. This is a product decision, not a technical one, but the technical team must surface the requirement.

Combined, these measures reduce effective throughput demand by approximately 60–70%, buying time for the rebuild without causing correctness failures.

**What this costs:** User experience degrades materially for 5–7 months. The product team must make and communicate the SLA change. The rebuild runs in parallel with a degraded live system, which is harder than a greenfield build.

**The honest statement:** If the >5× case is confirmed in week 2, the 6-month project plan does not survive intact. There is no technical path that avoids this. The purpose of the week-2 checkpoint is to surface this before the month-2 build milestone, not to prevent it from happening.

**False positive risk:** Early cohort measurements are noisy. Before triggering the rebuild decision, E1 runs a second measurement in week 3 with a larger cohort sample if available, and reviews the raw event distribution for obvious outliers. The rebuild decision requires two consistent measurements or one measurement with a clear mechanistic explanation.

### 1.3 Spike Handling: Quantified for Both Scenarios

Worker throughput figures are derived in Section 2.3. Readers verifying spike math should read that section first. The key figure: 30 P1 workers at ~350/sec each = 10,500/sec sustained capacity.

**Scenario A: 20× instantaneous spike, 90–120 seconds**

Arrival rate during spike: ~35,000/sec
Worker capacity: ~10,500/sec
Net accumulation rate: ~24,500/sec

Items accumulated during 90-second burst: ~2.2M
Items accumulated during 120-second burst: ~2.94M

Post-spike, arrival drops to baseline (~1,750/sec). Net drain rate: ~8,750/sec.

Drain time for 2.2M items: ~252 seconds (~4.2 minutes)
Drain time for 2.94M items: ~336 seconds (~5.6 minutes)

The queue absorbs the burst. A user who received a social notification at spike onset receives it approximately 4–6 minutes after generation. P0 notifications bypass the queue entirely and are unaffected.

**Alert thresholds in context:** The 500K-item warning threshold fires approximately 20 seconds into a Scenario A burst. The 2M-item page threshold fires at approximately 82 seconds — near the end of the burst. Manual scaling during a Scenario A burst does not help; the burst is over before intervention is possible. The alert exists to document the event, not to trigger a real-time response.

**Scenario B: 5× sustained, 10–30 minutes**

Arrival rate: ~8,750/sec against 10,500/sec capacity. Queue does not grow. Workers handle the load with ~20% headroom.

**Scenario B at 10× (undesigned-for):**

Arrival rate: ~17,500/sec against 10,500/sec capacity. Net accumulation: ~7,000/sec. Over 30 minutes: ~12.6M items.

Manual scaling response — range, not point estimate. The actual response time depends on: time for the alert to fire and page on-call (typically 1–3 minutes), time for the engineer to assess and decide to scale (2–10 minutes depending on context), and time for new workers to come online (1–3 minutes). The plausible range is 4–16 minutes from spike onset to additional capacity online. This range is an assumption until the month-5 load test validates it.

| Response time | Queue depth at response | Post-response drain rate | Drain time |
|---------------|------------------------|--------------------------|------------|
| 4 min | ~1.68M | ~17,500/sec net drain | ~96 sec |
| 10 min | ~4.2M | ~17,500/sec net drain | ~240 sec |
| 16 min | ~6.72M | ~17,500/sec net drain | ~384 sec |

Even at the 16-minute response time, post-response drain completes in approximately 6.4 minutes. Total delay for a notification generated at spike onset under the worst case: ~22 minutes. This is degraded but not catastrophic for social notifications.

**The product decision required before month 3:** If the product team determines that push delay during extreme viral events is unacceptable, sizing for 10× sustained requires approximately 60 P1 workers instead of 30 — roughly double the compute cost. If this decision is not made before the month-3 milestone when worker infrastructure is finalized, E1 implements the 30-worker configuration and the decision is treated as "accept the tradeoff."

### 1.4 SMS Cost: A Business Decision, Not a Technical One

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

**The SMS authentication fallback problem:**

A user requesting an auth code is typically logging in and therefore has no active session to receive a push notification. Describing push as a fallback for SMS auth is incorrect. When the SMS budget cap is hit, the actual options are:

1. **Block the send and surface an error** — the user cannot complete authentication. Honest but creates support load.
2. **Route to email authentication** — slower, but works if the product supports email-based auth independently of the app login.
3. **Exempt authentication SMS from the budget cap** — auth codes are a small fraction of total SMS volume (estimated 15–20%) and are correctness-critical. The budget cap applies only to notification SMS. Auth SMS is tracked separately with alerting but no hard cap.

**Option 3 is the correct technical default.** E2 implements two separate counters and two separate enforcement paths. The product and finance teams must confirm this distinction is acceptable before month 3.

**The required business decision, before month 3:** What is the geographic distribution of the user base, and what is the maximum monthly SMS notification budget (excluding auth)? Three possible outcomes:

1. **SMS notifications are affordable at our geographic mix** → hard monthly cap with alerting at 80%. Auth SMS uncapped with alerting.