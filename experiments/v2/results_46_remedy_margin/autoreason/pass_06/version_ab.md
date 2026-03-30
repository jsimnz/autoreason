# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three architectural bets, stated with their actual limitations:

1. **Separate priority queues with dedicated Redis instances per priority tier** — isolation is real only if the infrastructure is actually separate. Section 2.1 explains why we run three Redis instances rather than three queues on one instance, and what that costs. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches; separate instances make this a structural guarantee rather than a scheduling hope.

2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct, ElastiCache, RDS. Engineering time goes to integration quality, not infrastructure plumbing.

3. **Incremental delivery** — a working single-channel system by end of month 2, iterated through month 5, hardened in month 6.

**Eight honest statements upfront:**

The 17 notifications/user/day figure drives all sizing and is a planning assumption. Section 1.2 describes cohort-based validation with explicit bias correction — and names the limits of that correction. Tier reweighting removes one systematic bias but not all of them.

The 30% DAU/MAU ratio is load-bearing and has real uncertainty. Section 1.1 quantifies what a 25% or 35% ratio does to sizing and states which decisions are sensitive to this uncertainty.

The viral spike model sizes for 5× sustained, not 10×. Section 1.3 states the math, the consequences, and what the product team must decide before month 3. This is not a technical decision.

SMS costs range from $240K to $1.38M/month depending on geography. Section 1.4 distinguishes auth SMS from notification SMS — a distinction that matters for correctness — and states what business decision is required before month 3.

Worker counts are fully derived in Section 2.3, using channel-appropriate throughput figures. The spike math in Section 1.3 depends on numbers that appear in Section 2.3 — both sections are present and cross-referenced.

Redis Lists with BRPOP give LIFO behavior under accumulation. Section 2.2 acknowledges this, states the consequence for spike drain scenarios, and explains why we accept it for P1/P2 while using a different structure for P0.

The in-app ordering problem is real and addressed in Section 2.6, with explicit tradeoffs.

The operational surface is at the edge of what 4 engineers can safely own. Section 7 names what we cut, why, and identifies a non-circular overflow valve.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio — see sensitivity analysis below |
| Notifications/user/day | ~17 | Planning assumption; see Section 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike — Scenario A | 20× instantaneous, 90–120 seconds | Single viral post fanout |
| Viral spike — Scenario B | 5× sustained, 10–30 minutes | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

**DAU/MAU sensitivity analysis:**

The 30% ratio is a planning assumption based on comparable social apps. For a new product, the actual ratio is unknown and carries meaningful uncertainty.

| DAU/MAU Ratio | DAU | Notifications/Day | Peak Throughput | Worker Impact |
|---------------|-----|-------------------|-----------------|---------------|
| 25% | 2.5M | ~42.5M | ~1,475/sec | ~15% fewer workers needed |
| **30% (baseline)** | **3M** | **~50M** | **~1,750/sec** | **Baseline** |
| 35% | 3.5M | ~59.5M | ~2,080/sec | ~19% more workers needed |

**Decisions sensitive to this ratio:** Worker counts (Section 2.3), Redis memory sizing (Section 3.2), RDS write throughput planning (Section 3.3). A 35% ratio pushes P1 worker requirements up by approximately 6 workers. We provision at the 30% baseline and monitor actual DAU from the first week of operation. If DAU tracks above 32% for two consecutive weeks, E1 adds workers within 48 hours — this is a configuration change, not a rebuild.

**Decisions not sensitive to this ratio:** Queue architecture, channel selection logic, preference management design, failure handling. These are correct across the plausible range.

### 1.2 The 17/Day Figure: Cohort Validation with Explicit Bias Correction and Its Limits

**The cohort bias problem:**

A 50K-user beta cohort consists of early adopters. Early adopters over-engage: they explore features, generate content, and trigger social graph events at rates that do not reflect the eventual population. A week-2 measurement from this cohort could confidently validate the wrong number. Treating cohort-derived data as representative without correction replaces one planning assumption with a better-sounding but equally wrong one.

**What we do — and what it actually fixes:**

We instrument the 50K cohort from day one of beta and measure notifications generated per active user per day, segmented by behavioral tier:

- **Tier 1 (power users):** Top 10% by content generation events
- **Tier 2 (engaged users):** Middle 40%
- **Tier 3 (passive users):** Bottom 50%

We then apply scale-representative tier weights (5% / 35% / 60%) rather than the observed cohort weights (estimated 20–30% power users in an early adopter cohort). This removes the bias introduced by the cohort having too many power users.

**What this correction does not fix:**

Tier reweighting corrects for the wrong *proportion* of power users. It does not correct for the possibility that power users in the early adopter cohort behave differently from power users in the eventual general population. Early adopter power users are exploring a new product; they may generate more notifications per session than a power user who has been on the platform for a year and has settled into habitual behavior. If this within-tier rate difference is real, our corrected estimate will still be systematically high.

We cannot fully correct for this with a 2-week cohort. We treat the result as a plausible upper bound on steady-state notification rate, not a point estimate. Worker sizing uses this upper bound. If actual production rates are lower, we have excess capacity — which is the better failure mode.

**The tier classification timing problem:**

Classifying 50K users into behavioral tiers requires enough behavioral data to distinguish power users from passive users. Two weeks of data from users still discovering the product will produce unstable tier assignments. Tier classification in week 2 uses a simple proxy (number of content creation events in the first 14 days) rather than a stable behavioral model. The resulting estimate is directional, not precise. The decision gate below is calibrated accordingly — we only act on large deviations, not small ones, because small deviations are within the noise of an unstable early measurement.

**The decision gate:**

At end of week 2, E1 reviews the bias-corrected estimate:

| Corrected Estimate vs. 17/day | Action | Decision Owner | Window |
|-------------------------------|--------|----------------|--------|
| ≤ 2× | Increase P1/P2 worker counts; Redis capacity unchanged | E1 | 72 hours |
| 2–5× | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier | E1 | 72 hours |
| > 5× | See contingency below | Engineering lead + executive sponsor | See below |

**The >5× contingency — honest timeline with an honest gap:**

A >5× deviation means queue infrastructure is undersized for the actual workload. The immediate response is to cap notification volume via aggressive batching and rate limiting to keep the existing system stable. The rebuild response — migrating to Kafka or equivalent — takes 5–7 months for a team of 4 engineers running a live system simultaneously. This is longer than the remaining project timeline.

There is a real gap between "we have 1–2 weeks to decide" and "the fix takes 5–7 months." We do not have a way to close that gap through technical cleverness. The honest path: the 1–2 week decision window is used to assess whether the >5× signal is real (early cohort measurement noise can produce false signals) and to make a go/no-go on the current architecture with executive sponsorship. If the signal is confirmed real, the project timeline does not survive intact. That is the actual consequence.

The week-2 checkpoint exists specifically to surface this before the 6-month plan is locked. E1 does not have authority to make hiring decisions or reduce product scope unilaterally; those decisions require engineering lead and executive sponsor jointly.

### 1.3 Spike Handling: Design Thresholds and Their Justification

**Two spike scenarios with fundamentally different handling requirements:**

*Scenario A — Short burst:* A viral post fans out through the social graph. Generation rate spikes to ~20× instantaneous (~35,000/sec) for 60–120 seconds, then drops to near-normal. The queue absorbs the burst; workers drain over the following minutes. This does not require workers to match the arrival rate — it requires sufficient queue depth and an acceptable drain window.

*Scenario B — Sustained elevated rate:* A live event holds elevated rates for 10–30 minutes. This tests whether worker throughput can match the sustained arrival rate, or whether the queue grows unboundedly. These scenarios require different sizing logic; conflating them produces wrong answers for both.

**Why we size for 5× sustained, not 10×:**

Observed data from comparable social platforms shows sustained events above 5× baseline are rare (~3–5 times per year at this scale) and events above 10× sustained are rarer still. Sizing for 10× would require approximately double the P1 worker pool — roughly 60 workers instead of 30 — adding ~$8–12K/month in compute and operational complexity for an event that may not occur in year one.

**What we accept as a consequence:**

Under a genuine 10× sustained event, push notifications could be delayed by 20–25 minutes during the event. P0 (security/account) notifications are unaffected by design — this is the architectural guarantee of separate queues. Push delay during an extreme viral event is a degraded user experience, not a safety or correctness failure. If the product team determines this tradeoff is unacceptable, sizing for 10× sustained must be decided before the month-3 milestone when worker infrastructure is finalized. If that decision arrives unmade, E1 implements the 30-worker configuration and the tradeoff is accepted by default.

**Spike math — P1 queue under Scenario B:**

The throughput figures below are derived in Section 2.3. Readers who want to verify these calculations should read Section 2.3 first.

*5× sustained for 30 minutes (the designed-for case):*
- P1 arrival rate at 5× sustained peak: ~8,750/sec
- 30 P1 workers at 350/sec each (P1-appropriate mixed-channel throughput): 10,500/sec sustained capacity
- Net headroom: ~20% above the 5× case
- Queue does not grow unboundedly under Scenario B as defined

*10× sustained for 30 minutes (the undesigned-for case):*
- Arrival rate: ~17,500/sec against 10,500/sec capacity
- Net accumulation: ~7,000/sec
- Over 30 minutes: ~12.6M items
- Post-event drain rate (workers now ahead of arrival): ~8,750/sec net
- Drain time after event ends: ~24 minutes

*Scenario A (20× instantaneous for 90 seconds):*
- Items generated: ~3.15M
- Post-spike drain at ~8,750/sec net: ~6 minutes
- Acceptable

**LIFO behavior during drain — acknowledged:**

Redis Lists with BRPOP give LIFO semantics under accumulation. During the post-event drain, the oldest notifications are delivered last. A user who received a social event notification at minute 1 of the spike may not receive it until after users who triggered events at minute 28. For time-sensitive social notifications, this inverts the desired delivery order.

We accept this for P1/P2 because the alternative — Redis Sorted Sets with timestamp scores — adds ~30% overhead per operation and complicates the worker implementation. At normal operation (queue nearly empty), LIFO and FIFO are equivalent. The ordering inversion only manifests during drain after a large spike, which is rare by construction.

For P0 notifications, we use a Redis Sorted Set with timestamp scores. P0 volume is low enough that the overhead is acceptable, and P0 ordering correctness (authentication codes, account security alerts) is more important than throughput. See Section 2.2.

**Real-time response:**

Queue depth is monitored with alerts at 500K items (warning) and 2M items (page). The manual scaling runbook adds ~10 workers in approximately 3 minutes via deployment tooling. This time estimate is an assumption until validated in the month-5 load test. If a large spike occurs before month 5, manual scaling response time may differ from the 3-minute estimate. The runbook is written and reviewed by all 4 engineers before the month-2 milestone.

### 1.4 SMS Cost: A Business Decision, Not a Technical One

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. The actual cost depends entirely on geographic distribution:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

**The SMS authentication failure mode — addressed directly:**

A user who needs an SMS auth code is typically logging in and therefore has no active session to receive a push notification. Describing push as a fallback for SMS auth is incorrect. The actual options when the SMS budget cap is hit:

1. **Block the send and surface an error** — the user cannot complete authentication. Honest but creates support load.
2. **Route to email authentication** — slower, but works if the product supports email-based auth and the user can access email independently of the app login.
3. **Exempt authentication SMS from the budget cap** — auth codes are a small fraction of total SMS volume (estimated 15–20%) and are correctness-critical. The budget cap applies only to notification SMS (account activity alerts, social notifications via SMS). Auth SMS is tracked separately and has no cap, only alerting.

**Option 3 is the correct technical default.** It requires the budget decision to distinguish between auth SMS and notification SMS. E2 implements two separate counters and two separate enforcement paths. The product and finance teams must confirm this distinction before the month-3 milestone.

**The required business decision, before month 3:**

The product and finance teams must answer: what is the geographic distribution of our user base, and what is the maximum monthly SMS notification budget (excluding auth)?

1. **Notification SMS affordable at our geographic mix** → implement budget tracking with a hard monthly cap and alerting at 80% of cap. Auth SMS is uncapped with alerting.
2. **Notification SMS affordable only for specific use cases** → restrict notification SMS to account recovery only. Auth SMS is uncapped.
3. **Notification SMS not affordable internationally** → notification SMS is US-only or eliminated. Auth SMS remains available globally.

If this decision is not made before month 3, E2 implements Option 2 (restricted notification SMS, uncapped auth SMS) as the default. This is the most conservative option that preserves auth functionality.

**Technical enforcement:**

The notification SMS budget gate is a counter in Redis, incremented on every notification SMS send and checked before every dispatch. The gate rejects sends when the counter exceeds the configured monthly cap. The counter resets on the first of each month via a scheduled job. Rejected sends are logged with reason code `SMS_BUDGET_EXCEEDED` and are not retried. Auth SMS uses a separate counter with no cap and alerts at 120% of the prior month's auth SMS volume. E2 owns both gates.

### 1.5