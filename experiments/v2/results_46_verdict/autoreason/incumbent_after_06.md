# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single queue with channel fanout. This is a deliberate choice after analyzing a specific failure mode the single-queue design cannot contain: FCM backpressure during upstream degradation blocks email and in-app delivery when queues are shared. The tradeoff is higher operational complexity (four queues instead of one); the benefit is channel isolation that makes failure modes containable. The trigger criteria for revisiting this decision are defined in Section 2.3 as measurable operational thresholds.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations — push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, the naive peak throughput calculation distributes daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

**On peak throughput:** The naive calculation (51M × 3 / 86,400 = 1,770/sec) produces average throughput times a spike multiplier, which is wrong when traffic is concentrated. If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual sustained peak is:

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

The 3× multiplier applies to momentary spikes within those windows, giving a design envelope of **~6,375/sec**. We design to this number, not 1,770/sec. The distinction matters for queue sizing, worker pool sizing, and the stress test targets in Section 1.3a.

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

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals.

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. The gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. The allowlist requires two-engineer sign-off to modify and is version-controlled. Escalation paths for urgent additions are defined in Section 3.3.

**On push volume:** 5 notifications/day/installed user is the eventual target, not the launch configuration. We launch at 3/day and ramp based on observed opt-out data. The ramp criteria are defined in Section 1.4.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is paired ownership, documented runbooks, demonstrated coverage capability verified before each channel launches, and a runbook maintenance process that continues through month 6.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**Coverage partner relationships are mutual, not circular.** Each engineer is primary for their own channel and backup for their partner's. E1 serves as tertiary backup for all channels in the event both primary and coverage partner are simultaneously unavailable; this is documented in the runbook and verified at month 4 and month 6 spot-checks.

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems — not a single pre-launch test that can only fail at the worst possible moment.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. The standard is explicit: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Resolving E4's month 1 workload conflict:** A solo on-call engineer responding to incidents cannot simultaneously do focused design work. The resolution is explicit scope separation:

- **Weeks 1–2:** E4 does design and scaffolding for email/SMS integrations. E1 carries on-call for queue and in-app infrastructure during this period.
- **Weeks 3–4:** E4 transitions to Gate 3 solo on-call for queue/in-app scope. Email/SMS design work is paused. E4 resumes email/SMS implementation in month 2.

This means email/SMS scaffolding is 2 weeks in month 1, not 4. If month 2 email launch requires more scaffolding time than that provides, email launch slips to month 3 — not the coverage requirement.

**Runbook maintenance through month 6:**

- **Trigger-based updates:** Any production incident that required knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and a list of changes made (or an explicit "no changes required" sign-off). The monthly review sign-off is a required field in the sprint planning template for the first sprint of each month — this creates a visible artifact and a specific moment of accountability, which is meaningfully different from aspirational intent.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation against the current runbook. A failed spot-check is treated as a P2 operational issue.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and this standard is re-verified at months 4 and 6, not assumed to persist from launch.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification |
|-------|-------------|----------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | Gate 1 (week 2); Gate 2 (week 3); E4 Gate 3 solo on-call weeks 3–4 (queue/in-app scope) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E4 Gates 1–3 for push coverage; E2 Gates 1–3 for email coverage |
| 3 | Email digests, SMS (auth only), aggregation logic | E2 Gates 1–3 for SMS coverage |
| 4 | Full preference management, suppression lists, advanced batching; month 4 runbook spot-checks | Spot-checks for all channels; E1 tertiary backup verification |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Three-part validation suite (see Section 1.3a); month 6 runbook spot-checks | Spot-checks for all channels |

### 1.3a Month 6 Testing

Month 6 testing comprises three distinct tests with three distinct purposes. The distinction matters: collapsing them into a single test answers neither question well.

**Test 1 — 2× peak validation (pass/fail against operational envelope):**
Load generated at 2× sustained peak throughput (~4,250/sec) against a production-mirror staging environment. FCM is real (staging app credentials). This is the test against which we claim the system works.

Pass criteria (binary, all required):
- P0 SLA met (10s) for >99% of notifications
- P1 SLA met (60s) for >99% of notifications
- No data loss
- Backpressure engages before queue depth exceeds per-channel limits
- All monitoring alerts fire correctly

Failure on any criterion is a blocking defect.

**Why 2× and not 3×:** FCM staging credentials operate under production rate limits that cannot be increased for testing. Running 3× load with real FCM will trigger FCM rate limiting as a test artifact, not as a system behavior. The honest choice is to run the validation test at a load level where FCM behavior is real, and separately characterize higher-load behavior with explicit acknowledgment of what is being approximated and why.

**Test 2 — FCM degradation characterization (test the specific identified risk):**
FCM responses are artificially delayed via a proxy in the push channel worker to simulate degraded upstream response times, while push load is held at 1.5× normal. This tests the primary motivation for per-channel queues: does FCM slowness propagate to email and in-app queues?

Pass/fail criteria (these are correctness requirements, stated as such):
- Email and in-app P1 SLA is unaffected during FCM degradation
- Push notifications back up in the push queue without spilling into other channels
- P0 push notifications route to SMS fallback per Section 5.3
- Queue depth monitoring alerts fire for the push channel specifically

The test also characterizes FCM recovery time once the delay is removed — that output is documentation, not a pass/fail gate.

**Test 3 — Stress characterization beyond design envelope:**
Load generated at 3× peak throughput (~6,375/sec). FCM is mocked at this load level. This is an explicit limitation: we are testing our system's internal behavior under overload, not FCM's behavior. The question being answered is whether backpressure engages correctly, whether P2 load is shed before P1, and whether the system fails gracefully or catastrophically.

The FCM mock is appropriate here because FCM is not the variable under test — and we say so explicitly rather than pretending the mock is equivalent to production FCM. This test has no pass/fail criteria; its output is a documented characterization of failure modes and the capacity envelope.

### 1.4 Opt-Out Protection

Two structural problems with naive opt-out protection are worth naming upfront. First, a multi-week statistical baseline period accepts permanent audience damage as an interim condition — opted-out users do not come back. Second, a relative per-type alert (e.g., "3× the rate of other types") is statistically undefined at launch, when no stable distribution of notification types with sufficient volume per type yet exists.

Both problems are addressed by inverting the protection model: **conservative absolute limits operate from day one, and statistical alerting is layered on top as data accumulates.**

**Day-one absolute limits (enforced in the channel dispatcher, not by convention):**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max push per user per day | 3 | Launch target; 5/day is the eventual ceiling, not the starting point |
| Max push per user per hour | 1 | Prevents burst even within daily limit |
| Per-type daily cap | 1 per type per user per day | Prevents any single type from dominating |
| Aggregate weekly opt-out alert | 0.5% of push-eligible users (35K) in 7 days | P1 page; conservative enough to catch problems before widespread permanent damage |

**Why 3/day at launch:** The 5/day target is derived from industry benchmarks for mature notification programs with known-good content. At launch, we have neither the content track record nor the statistical tools to detect problems quickly. Starting at 3/day provides headroom to observe opt-out behavior before increasing frequency.

**Why 35K weekly opt-outs as the aggregate alert threshold:** 35K is 0.5% of the push-eligible audience. The correct way to avoid false positives is to set a conservative threshold and accept some investigation overhead, not to set a threshold that only fires after significant damage has already accumulated.

**Per-type absolute limits as the early warning mechanism:**
Each notification type has an absolute opt-out rate threshold of 2% of recipients per week, enforced from day one. Types with fewer than 2,500 recipients in the measurement window are excluded from automated alerting and reviewed manually in the weekly traffic review — this prevents false positives from small sample sizes without silently ignoring small-volume types.

**Addressing the gradual drift blind spot:**
Absolute per-user limits don't detect gradual increases in opt-outs across many users that individually stay below per-user caps. The mitigation during the first 8 weeks is explicit and honest about what it is: weekly cohort tracking of opt-out rates by notification type, reviewed as a required agenda item in the weekly team sync, with the dashboard link in the sync template. This is a manual process that depends on someone actually looking at the dashboard. It catches trends a reviewer notices, not trends that cross a computed threshold. We are stating this as the actual protection during weeks 1–8, not pretending the absolute limits are sufficient.

**Statistical alerting layered on top (week 9 onward):**
After 8 weeks of operation, we compute per-type baseline opt-out rates and add statistical alerting (μ + 2σ for P2, μ + 3σ for P1) as an additional layer. The absolute thresholds remain in force permanently — statistical alerting supplements, not replaces, them. Statistical alerts are more sensitive to gradual drift; absolute limits protect against acute spikes.

**Frequency ramp gate:**
Increasing push frequency from 3/day toward 5/day requires: (1) 8 weeks of operation without triggering the aggregate weekly opt-out alert, and (2) no notification type with an opt-out rate above 1% in the most recent 4-week window. The ramp proceeds in 0.5/day increments with 2-week observation periods. The dispatcher cap is a configuration value requiring a pull request with explicit team sign-off — not a unilateral configuration change.

---

## 2. System Architecture

### 2.1 