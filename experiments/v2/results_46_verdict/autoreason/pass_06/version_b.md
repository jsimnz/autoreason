# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single queue with channel fanout. This is a deliberate revision from an earlier single-queue design after analysis showed that FCM backpressure — an explicitly identified risk — would block email and in-app delivery in a shared queue. The tradeoff is slightly higher operational complexity (four queues instead of one); the benefit is channel isolation that makes failure modes containable. The trigger criteria for further architectural revision are defined in Section 2.3 as measurable operational thresholds.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

A critical modeling error to avoid upfront: different channels have different eligible populations, and the peak throughput calculation must account for actual traffic concentration rather than distributing daily volume evenly across 24 hours.

**On peak throughput:** The naive calculation (51M × 3 / 86,400 = 1,770/sec) produces average-times-multiplier, which is wrong when traffic is concentrated in windows. If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual peak is:

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

The 3× multiplier then applies to momentary spikes within those windows, giving a design envelope of **~6,375/sec**. We design to this number, not 1,770/sec. The distinction matters for queue sizing, worker pool sizing, and the stress test targets in Section 1.3a.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~3 (launch), ~5 (target) | Conservative at launch; ramp gated on opt-out data |
| **Push volume/day** | **~21M (launch), ~35M (target)** | 7M × 3 / 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K** | Auth and security only |
| **Total/day (launch)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target)** | **~51M** | Sum across channels at target frequency |
| Peak window share | 60% in 4 hours | Morning + evening concentration |
| **Peak sustained throughput** | **~2,125/sec** | Corrected for window concentration |
| **Design envelope (3× spike)** | **~6,375/sec** | Momentary spikes within peak windows |

These are estimates; we instrument from day one and publish a traffic model review in month 2 with actuals.

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. The gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. The allowlist requires two-engineer sign-off to modify and is version-controlled. Escalation paths for urgent additions are defined in Section 3.3.

**On push volume:** 5 notifications/day/installed user is the eventual target, not the launch configuration. We launch at 3/day and ramp based on observed opt-out data. The ramp criteria are defined in Section 1.4.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** The mitigation is paired ownership, documented runbooks, demonstrated coverage capability verified before each channel launches, and a runbook maintenance process that continues through month 6.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**Resolving the coverage circularity in month 2:** E4 is E2's coverage partner for push. When email launches in month 2, E2 becomes E4's coverage partner for email. This creates a mutual coverage relationship, not a circular dependency — each engineer is primary for their own channel and backup for their partner's. The coverage gates (below) apply in both directions. E1 serves as the tertiary backup for both channels in the event both primary and coverage partner are unavailable; this is documented in the runbook and verified at month 4 spot-checks.

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner executes every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. If the coverage partner cannot resolve it without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Resolving E4's month 1 workload conflict:** The prior design papered over a real time conflict: a solo on-call engineer responding to incidents cannot simultaneously do focused design work. The resolution is explicit scope separation:

- **Weeks 1–2:** E4 does design and scaffolding for email/SMS integrations. E1 carries on-call for queue and in-app infrastructure during this period.
- **Weeks 3–4:** E4 transitions to solo on-call (Gate 3) for in-app/queue scope. Email/SMS design work is paused during on-call week. E4 resumes email/SMS implementation in month 2.

This means email/SMS scaffolding is 2 weeks, not 4. That is a real constraint on month 2 scope. If month 2 email launch requires more than 2 weeks of scaffolding, the email launch slips to month 3 — not the coverage requirement.

**Runbook maintenance through month 6:**

- **Trigger-based updates:** Any production incident that required knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and a list of changes made (or an explicit "no changes required" sign-off).

**On enforceability of the monthly review:** "Flagged in weekly sync" is social pressure, not a process control. The actual enforcement mechanism is that the monthly review sign-off is a required field in the team's sprint planning template for the first sprint of each month. A sprint cannot be marked complete without it. This is a lightweight process control — it can be gamed — but it creates a visible artifact and a specific moment of accountability, which is meaningfully different from aspirational intent.

- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation against the current runbook. A failed spot-check is treated as a P2 operational issue.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and this standard is re-verified at months 4 and 6.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification |
|-------|-------------|----------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | Gate 1 (week 2); Gate 2 (week 3); E4 Gate 3 solo on-call weeks 3–4 (queue/in-app scope only) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E4 Gates 1–3 for push coverage; E2 Gates 1–3 for email coverage |
| 3 | Email digests, SMS (auth only), aggregation logic | E2 Gates 1–3 for SMS coverage |
| 4 | Full preference management, suppression lists, advanced batching; month 4 runbook spot-checks | Spot-checks for all channels; E1 tertiary backup verification |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Three-part validation suite (see Section 1.3a); month 6 runbook spot-checks | Spot-checks for all channels |

### 1.3a Month 6 Testing

Month 6 testing comprises three distinct tests with three distinct purposes. The FCM mocking criticism from an earlier design iteration is addressed directly: the difference between a mock and an artificially constrained staging project is smaller than it appears, and the test plan needs to be honest about what each test actually characterizes.

**Test 1 — 2× peak validation (pass/fail against operational envelope):**
Load generated at 2× sustained peak throughput (~4,250/sec) against a production-mirror staging environment. FCM is real (staging app credentials). This is the test against which we claim the system works. Pass criteria: P0 SLA met (10s), P1 SLA met (60s) for >99% of notifications, no data loss, backpressure engages before queue depth exceeds per-channel limits, all monitoring alerts fire correctly. Failure on any criterion is a blocking defect.

**Why 2× and not 3×:** FCM staging credentials operate under production rate limits that cannot be increased for testing. Running 3× load with real FCM in staging will trigger FCM rate limiting as a test artifact, not as a system behavior. The honest choice is to run the validation test at a load level where FCM behavior is real, and separately characterize behavior at higher load levels with explicit acknowledgment of what's being mocked and why.

**Test 2 — FCM degradation characterization:**
FCM responses are artificially delayed (via a proxy in the push channel worker) to simulate degraded upstream response times, while push load is held at 1.5× normal. This tests channel isolation: does FCM slowness propagate to email and in-app queues? It should not, given the per-channel queue architecture. Success criteria (these are correctness requirements, not characterization targets): email and in-app P1 SLA is unaffected during FCM degradation, push notifications back up in the push queue without spilling into other channels, P0 push notifications route to SMS fallback per Section 5.3, and queue depth monitoring alerts fire for the push channel specifically. These are binary pass/fail criteria. The test also characterizes how long FCM recovery takes once the delay is removed — that output is documentation, not a pass/fail gate.

**Naming the earlier contradiction directly:** A previous version of this document said Test 2 "does not pass or fail on delivery speed" while listing specific required behaviors. That is contradictory. Required behaviors are pass/fail criteria. This version states them as such.

**Test 3 — Stress characterization beyond design envelope:**
Load generated at 3× peak throughput (~6,375/sec). FCM is mocked at this load level. This is an explicit limitation: we are testing our system's internal behavior under overload, not FCM's behavior. The question being answered is whether backpressure engages correctly, whether P2 load is shed before P1, and whether the system fails gracefully or catastrophically. This test has no pass/fail criteria; its output is a documented characterization of failure modes and the capacity envelope. The FCM mock is appropriate because FCM is not the variable under test — and we say so explicitly rather than pretending the mock is equivalent to production FCM.

### 1.4 Opt-Out Protection

**Day-one absolute limits (enforced in the channel dispatcher):**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max push per user per day | 3 | Launch target; 5/day is the eventual ceiling |
| Max push per user per hour | 1 | Prevents burst within daily limit |
| Per-type daily cap | 1 per type per user per day | Prevents any single type from dominating |
| Aggregate weekly opt-out alert | 0.5% of push-eligible users (35K) in 7 days | P1 page; conservative threshold |

**Addressing the 8-week blind spot for gradual drift:** The prior design acknowledged that absolute per-user limits don't detect gradual increases in opt-outs across many users that stay below per-user caps. Statistical alerting at week 9 leaves an 8-week gap. The gap is real and the mitigation is explicit:

- **Weekly cohort tracking from day one:** We track the opt-out rate for each weekly cohort of notification recipients by type. This is not statistical anomaly detection — it's a weekly human review of a dashboard showing opt-out rates over time. A visual upward trend in the weekly review triggers a P2 investigation. This is a manual process, and it depends on someone actually looking at the dashboard. The review is a required agenda item in the weekly team sync for months 1–8, with the dashboard link in the sync template.
- **This is not equivalent to automated drift detection.** It catches trends that a reviewer notices, not trends that cross a computed threshold. We are being explicit that this is the actual protection during the first 8 weeks, not pretending the absolute limits are sufficient.
- **Statistical alerting at week 9** adds automated drift detection as a supplement. The absolute limits remain in force permanently.

**Frequency ramp gate:**
Increasing push frequency from 3/day toward 5/day requires: (1) 8 weeks of operation without triggering the aggregate weekly opt-out alert, and (2) no notification type with an opt-out rate above 1% in the most recent 4-week window. The ramp proceeds in 0.5/day increments with 2-week observation periods. The dispatcher cap is a configuration value requiring a pull request with explicit team sign-off.

---

## 2. System Architecture

### 2.1 Why Per-Channel Queues, Not a Single Queue

The initial design used a single priority queue with channel fanout. That design was revised after analyzing a specific failure mode it couldn't contain.

**The FCM backpressure problem:** FCM is the highest-volume channel (35M/day at target) and the most likely to experience upstream degradation. In a single shared queue, FCM workers consuming from that queue will slow down during FCM degradation. If the queue is shared, the backpressure manifests as queue depth growth that affects all channels — email digests and in-app notifications accumulate behind the FCM backlog. The document explicitly identifies FCM quota exhaustion as a risk worth testing for; a single-queue architecture makes that risk contagious to unrelated channels.

**The per-channel queue design:** Four separate queues — push, email, in-app, SMS — each with their own worker pools and independent backpressure. A priority classifier upstream of the queues assigns each notification to the appropriate channel queue with its priority level. Channel degradation is contained to that channel's queue.

**The tradeoff:** Four queues are more operationally complex than one. Four