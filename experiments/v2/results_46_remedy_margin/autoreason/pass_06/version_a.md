# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated ~50M notifications/day across push, email, in-app, and SMS channels. Three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — a correctness decision, not a scale decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct, ElastiCache, RDS. Engineering time goes to integration quality, not infrastructure plumbing.
3. **Incremental delivery** — a working single-channel system by end of month 2, iterated through month 5, hardened in month 6.

**Five honest statements upfront:**

The 17 notifications/user/day figure drives all sizing and is a planning assumption. We get early signal from a 50K-user beta cohort in week 2, but that cohort is early adopters who will over-engage relative to the eventual population. Section 1.2 describes how we correct for this bias and what the decision gate actually requires.

The viral spike model makes explicit choices about design thresholds. Section 1.3 justifies why we size for 5× sustained rather than 10×, states the math behind that choice, and names what we accept as a consequence of not sizing for 10×.

SMS costs range from $240K to $1.38M/month depending on geographic distribution. This is not a technical problem with a technical solution — it is a business decision that must be made before launch. Section 1.4 states what that decision is and who owns it.

Worker counts in this document are fully derived. Section 2.3 shows the math for P0, P1, and P2 workers using channel-appropriate throughput figures — not push benchmarks applied to non-push channels.

The operational surface described here is at the edge of what 4 engineers can safely own. Section 7 names what we cut and why, including the designated overflow valve if unplanned work materializes. If scope is added mid-project, something on that list gets dropped — we say it explicitly rather than silently accept overcommitment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
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

### 1.2 The 17/Day Figure: Cohort Validation with Explicit Bias Correction

**The cohort bias problem:**

A 50K-user beta cohort consists of early adopters. Early adopters systematically over-engage: they explore features, generate content, and trigger social graph events at rates that do not reflect the eventual population of 3M DAU. A week-2 measurement from this cohort could confidently validate the wrong number. Treating cohort-derived data as representative without correction would replace one planning assumption with a better-sounding but equally wrong one.

**What we do instead — bias-corrected measurement:**

We instrument the 50K cohort from day one of beta. We measure notifications generated per active user per day, segmented by user behavior tier:

- **Tier 1 (power users):** Top 10% by content generation events
- **Tier 2 (engaged users):** Middle 40%
- **Tier 3 (passive users):** Bottom 50%

For a general social app population, the expected tier distribution at scale is approximately 5% / 35% / 60%. Early adopter cohorts typically skew toward 20–30% power users. We apply this correction explicitly: the adjusted estimate uses the scale-representative tier weights (5/35/60), not the observed cohort weights.

The adjusted estimate is our planning figure. It is still an estimate — we cannot perfectly predict how a 3M DAU population will distribute across tiers — but it removes the systematic upward bias from early adopter over-representation.

**The decision gate:**

At the end of week 2, E1 reviews the bias-corrected estimate. The gate compares the corrected figure against the 17/day planning assumption:

| Corrected Estimate vs. 17/day | Action | Decision Owner | Window |
|-------------------------------|--------|----------------|--------|
| ≤ 2× | Increase P1/P2 worker counts; Redis capacity unchanged | E1 | 72 hours |
| 2–5× | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier | E1 | 72 hours |
| > 5× | See contingency below | Engineering lead + executive sponsor | See below |

**The >5× contingency — honest timeline:**

A >5× deviation means queue infrastructure is undersized for the actual workload. The response is not a 72-hour decision. It requires: (1) immediately capping notification volume via aggressive batching and rate limiting to keep the existing system stable; (2) a Kafka or equivalent migration that, for a team of 4 engineers running a live system at 250M+ notifications/day while building new infrastructure, realistically takes 5–7 months — longer than the remaining project timeline under any scenario; (3) a decision about whether to hire additional engineers or reduce product scope.

The decision owner for this scenario is the engineering lead and executive sponsor jointly. E1 does not have authority to make hiring decisions or reduce product scope unilaterally. The realistic decision window is 1–2 weeks to assess options, followed by a go/no-go on the current architecture.

The week-2 checkpoint exists specifically to surface this scenario before the 6-month plan is fully locked. If the corrected estimate exceeds 5× at week 2, we say so immediately and do not proceed as if the timeline is intact.

**What the cohort measurement cannot capture:**

Accurate per-user rate estimation does not resolve uncertainty about viral spike shape and magnitude. A 50K cohort cannot reproduce viral dynamics at scale. Section 1.3 handles spike uncertainty separately and explicitly.

### 1.3 Spike Handling: Design Thresholds and Their Justification

**Two spike scenarios with fundamentally different handling requirements:**

*Scenario A — Short burst:* A single viral post fans out through the social graph. Generation rate spikes to ~20× instantaneous (~35,000/sec) for 60–120 seconds, then drops to near-normal. The queue absorbs the burst; workers drain over the following minutes. This scenario does not require workers to match the arrival rate — it requires the queue to have sufficient depth and workers to drain within an acceptable latency window.

*Scenario B — Sustained elevated rate:* A live event or trending topic holds elevated rates for 10–30 minutes. This tests whether worker throughput can match the sustained arrival rate, or whether the queue grows unboundedly. These two scenarios require different sizing logic; conflating them produces wrong answers for both.

**Why we size for 5× sustained, not 10×:**

Observed data from comparable social platforms shows that sustained viral events above 5× baseline peak are rare — roughly 3–5 times per year at this scale — and events above 10× sustained are rarer still, typically requiring coordinated external factors (major breaking news coinciding with a platform-specific viral moment). Sizing for the 10× case would require approximately double the P1 worker pool, adding ~$8–12K/month in compute cost and increasing operational complexity for an event that may not occur in the first year of operation.

**What we accept as a consequence of this choice:**

Under a genuine 10× sustained event, the P1 queue will accumulate faster than workers can drain it. Based on the math below, push notifications could be delayed by 20–25 minutes during the event. We accept this tradeoff explicitly: push notification delay during an extreme viral event is a degraded user experience, not a safety or correctness failure. P0 (security/account) notifications are unaffected by design — this is the architectural guarantee of separate queues.

If the product team determines that push delay during extreme viral events is unacceptable, the right response is to size for 10× sustained — approximately 60 P1 workers instead of 30, at roughly double the compute cost. That is a product and business decision, not a technical one, and it must be made before the month-3 milestone.

**Spike math — P1 queue under Scenario B (5× sustained for 30 minutes):**

P1 arrival rate at 5× sustained peak: ~8,750/sec. With 30 P1 workers at P1-appropriate throughput (derived in Section 2.3: ~350/sec per worker for push-dominant P1 load), sustained P1 capacity is ~10,500/sec. Net result: workers keep pace with 5× sustained load with ~20% headroom. The queue does not grow unboundedly under Scenario B as defined.

**Under 10× sustained (the undesigned-for case):** Arrival rate ~17,500/sec against 10,500/sec capacity. Net accumulation ~7,000/sec. Over 30 minutes: ~12.6M items. At post-event drain rate (~8,750/sec net), drain time ~24 minutes after the event ends. This is the consequence we accept.

**Scenario A behavior under the same worker pool:** 20× instantaneous for 90 seconds generates ~3.15M items. Workers drain at ~8,750/sec net post-spike. Drain time ~6 minutes after the spike ends. Acceptable.

**Real-time response:** Queue depth is monitored with alerts at 500K items (warning) and 2M items (page). The runbook for manual worker scaling is written before launch and tested in the month-5 load test. Manual scaling can add ~10 workers in approximately 3 minutes via deployment tooling.

### 1.4 SMS Cost: A Business Decision, Not a Technical One

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. The actual cost depends entirely on geographic distribution:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

**This is not a problem that technical budget gates solve.** A monthly cap prevents overspend but does not make an unaffordable SMS strategy affordable — it silently stops sending notifications when the cap is hit, which may mean users stop receiving authentication codes. The 5.75× cost range reflects a fundamental question about whether the product can support SMS for an international user base at all. That question requires a business answer before engineering can implement the right enforcement mechanism.

**The required business decision, before the month-3 milestone:**

The product and finance teams must answer: what is the geographic distribution of our user base, and what is the maximum monthly SMS budget? The three possible outcomes are:

1. **SMS is affordable at our geographic mix** → implement budget tracking with a hard monthly cap and alerting at 80% of cap.
2. **SMS is affordable only for specific use cases** → restrict SMS to authentication and account recovery only, eliminating all other SMS notification types. This reduces volume by approximately 60–70% based on typical social app SMS usage patterns.
3. **SMS is not affordable at international rates** → SMS is US-only or eliminated entirely. The architecture supports this as a configuration change, not a rebuild.

If this decision is not made before the month-3 milestone, E2 implements Option 1 with a conservative budget cap as a default, and the cap is treated as a placeholder pending formal review. This default is not a recommendation — it is a fallback that prevents the project from blocking on an unresolved business question.

**Technical enforcement (conditional on the above decision):**

The SMS budget gate is a counter in Redis, incremented on every SMS send and checked before every SMS dispatch. The gate rejects sends when the counter exceeds the configured monthly cap. The counter resets on the first of each month via a scheduled job. Rejected sends are logged with reason code `SMS_BUDGET_EXCEEDED` and are not retried. Users affected by budget exhaustion receive a push notification if a device token is available. E2 owns this gate.

### 1.5 Team Allocation

| Engineer | Primary Responsibility | Explicit Exclusions |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, week-2 recalibration authority | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), SMS budget enforcement | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic, notification coordination records | Delivery workers |
| E4 | ElastiCache configuration and capacity planning, RDS schema and query performance, Datadog configuration, reconciliation job (Section 2.5), partition management automation | See scope note below |

**E4 scope — full allocation with no slack:**

| Month | Primary Focus | Estimated Hours/Week |
|-------|--------------|---------------------|
| 1 | RDS schema design, ElastiCache configuration, Datadog setup | 40 |
| 2 | Reconciliation job development (Section 2.5) | 40 |
| 3 | Partition management automation, query performance work | 40 |
| 4–5 | Ongoing monitoring, performance investigation, capacity planning | 30 |
| 6 | Hardening, runbook completion, load testing support | 35 |

This is a full-time allocation with no buffer. E4 cannot absorb unplanned work without dropping something scheduled.

**The database performance overflow problem — named in advance:**

If query performance becomes a sustained time sink (more than 8 hours/week for more than two consecutive weeks), neither E1 nor E3 has identified slack time to absorb it. The honest answer: sustained query performance problems in months 4–5 will require dropping a lower-priority deliverable. The designated overflow valve is the advanced analytics dashboard (Section 7). This is named explicitly now so the decision is made under no pressure rather than under crisis conditions.

**On-call:** All 4 engineers rotate. No engineer is the sole on-call for any component.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Block suppression check (Postgres direct — structurally
    isolated by interface design; see Section 2.2)
  - Preference check (Redis cache, 5-min TTL, write-through)
  - Priority assignment
  - Channel selection
  - Coordination record creation (for multi-channel events)
     │
     ├─► [P0 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P0 Worker Pool (8 workers — derived Section 2.3)
     │
     ├─► [P1 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P1 Worker Pool (30 workers — derived Section 2.3)
     │
     ├─► [P2 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P2 Worker Pool (20 workers — derived Section 2.3)
     │
     └─► [In-App Store] (PostgreSQL — direct write, bypasses queue;
                         ordering behavior described in Section 2.6)
                    │
                    ▼
           [Channel Dispatcher]
             ├── Push (APNs / FCM)
             ├── Email (SendGrid)
             └── SMS (Twilio — budget-gated per Section 1.4)
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archive)
                    │
                    ▼
           [Feedback Processor]
           (bounces, opens, failures, token invalidation)
                    │
                    ▼
           [Reconciliation