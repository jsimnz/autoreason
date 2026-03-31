# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single queue with channel fanout. This is a deliberate choice after analyzing a specific failure mode the single-queue design cannot contain: FCM backpressure during upstream degradation blocks email and in-app delivery when queues are shared. The tradeoff is higher operational complexity (four queues instead of one); the benefit is channel isolation that makes failure modes containable.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations — push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

**On peak throughput:** If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual sustained peak is:

37M (launch volume) × 0.60 / (4 hours × 3,600 sec/hour) = **~1,542/sec sustained during peak windows**

51M (target volume) × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

We design to the target volume peak. A 3× multiplier applies to momentary spikes within those windows, giving a **design envelope of ~6,375/sec**. This is the number against which queue sizing, worker pool sizing, and validation targets are set.

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
| **Peak sustained throughput (target)** | **~2,125/sec** | Corrected for window concentration |
| **Design envelope (3× spike)** | **~6,375/sec** | Momentary spikes within peak windows |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals.

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. The gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. The allowlist requires two-engineer sign-off to modify; the escalation process for urgent additions is defined in Section 3.3.

**On push volume:** 5 notifications/day/installed user is the eventual target, not the launch configuration. We launch at 3/day and ramp based on observed opt-out data. The ramp criteria are defined in Section 1.4.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a runbook maintenance process that continues through month 6.

The coverage dependency structure is linear, not circular:

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Why linear and not the previous pairing:** The prior version paired E2↔E4 (push↔email/SMS) and E1↔E3 (infra↔in-app), creating a circular dependency: if E4 is unavailable, E2 covers email — but E2's primary is push, and no one covers push while E2 is handling email incidents. The linear structure resolves this:

- E1 covers push when E2 is unavailable. E1 has no channel primary of their own, making them the natural backup for push.
- E3 covers email/SMS when E4 is unavailable. E3's in-app scope shares significant overlap with E4's preference/suppression work.
- E4 covers in-app when E3 is unavailable.
- E2 covers infrastructure when E1 is unavailable.

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. A failed simulation triggers a runbook update and a second attempt. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Runbook maintenance through month 6:**

- **Trigger-based updates:** Any production incident that required knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and a change log (or an explicit "no changes required" sign-off). The monthly review sign-off is a required field in the sprint planning template for the first sprint of each month.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation against the current runbook. A failed spot-check is treated as a P2 operational issue.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and this standard is re-verified at months 4 and 6, not assumed to persist from launch.

### 1.3 Delivery Milestones

The month 2 timeline requires explicit sequencing. E4 completes Gate 3 solo on-call for queue/in-app scope at the end of month 1. Month 2 requires E1 (as push coverage partner) to complete Gates 1–3 for push, while E4 builds email transactional delivery. Gates 1–3 are sequential with a minimum 3-week span. The explicit sequencing:

**Month 2 sequencing:**
- Weeks 1–2: E1 executes Gate 1 runbook review for push coverage. E4 begins email scaffolding. E2 supports E1's runbook review questions.
- Week 3: E1 executes Gate 2 incident simulation for push. E4 continues email scaffolding.
- Week 4: E1 executes Gate 3 solo on-call for push. E4 completes email scaffolding and begins integration testing.

**If E1's Gate 2 simulation fails in week 3:** The push launch slips to month 3. Email scaffolding is not affected — E4 continues. E1 and E2 update the push runbook and re-simulate in week 4. Push launches in month 3 once gates are cleared.

**If E1's Gate 3 solo on-call surfaces blocking problems in week 4:** Push remains at limited traffic (internal users only) until the problems are resolved. Email transactional launches on schedule if its own gates are clear — channel launches are independent.

| Month | Deliverable | Coverage Gates |
|-------|-------------|----------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API skeleton | E3 Gates 1–2 for in-app (E3 is coverage partner for E4; E4 covers in-app). E4 Gate 3 solo on-call for queue/in-app scope weeks 3–4. |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E1 Gates 1–3 for push coverage (see sequencing above). E3 Gates 1–3 for email coverage (E3 is E4's coverage partner). |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 Gates 1–3 for SMS coverage. SMS gate enforcement live at dispatcher. |
| 4 | Full preference management, suppression lists, advanced batching; month 4 runbook spot-checks | Spot-checks for all channels. E2 tertiary backup verification for infrastructure. |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Three-part validation suite (Section 1.3a); month 6 runbook spot-checks | Spot-checks for all channels. |

### 1.3a Month 6 Testing

Month 6 testing comprises three distinct tests with three distinct purposes.

**Test 1 — 6,375/sec design envelope validation (pass/fail against operational envelope):**

Load generated at the full design envelope of **~6,375/sec** against a production-mirror staging environment. FCM is mocked at this load level. This is explicitly an internal system validation — we are testing queues, workers, priority logic, backpressure, and the database under full design load. We are not testing FCM behavior at this load, and we say so.

Pass criteria (binary, all required):
- P0 SLA met (10s) for >99% of notifications
- P1 SLA met (60s) for >99% of notifications
- No data loss
- Backpressure engages before queue depth exceeds per-channel limits
- Load shedding drops P2 before P1 under overload
- All monitoring alerts fire correctly

Failure on any criterion is a blocking defect.

**Why FCM is mocked at 6,375/sec:** FCM staging credentials operate under production rate limits that cannot be increased for testing. Running 6,375/sec with real FCM will trigger FCM rate limiting as a test artifact, not as a system behavior. Mocking FCM at this load level is the honest choice — we are characterizing our system's behavior, not FCM's.

**Test 2 — Real FCM validation at 2× sustained peak (~4,250/sec):**

Load generated at 2× sustained peak with real FCM staging credentials. This is the test that validates FCM integration behavior — realistic FCM latency, rate limit responses, token invalidation handling, and retry logic.

Pass criteria:
- P0 and P1 SLAs met with real FCM response times included
- Token invalidation detected and suppression list updated within 60 seconds
- FCM rate limit responses handled without data loss (retry with backoff, not drop)
- Delivery receipts reconcile with sent counts within 0.1%

**The relationship between Test 1 and Test 2:** These tests answer different questions. Test 1 answers: does our internal infrastructure hold at design load? Test 2 answers: does our FCM integration behave correctly under realistic conditions? Together they cover the design envelope. Neither alone is sufficient.

**Test 3 — FCM degradation characterization:**

FCM responses are artificially delayed via a proxy in the push channel worker to simulate degraded upstream response times, while push load is held at 1.5× normal. This tests the primary motivation for per-channel queues: does FCM slowness propagate to email and in-app queues?

Pass/fail criteria (correctness requirements):
- Email and in-app P1 SLA is unaffected during FCM degradation
- Push notifications back up in the push queue without spilling into other channels
- P0 push notifications route to SMS fallback per Section 5.3
- Queue depth monitoring alerts fire for the push channel specifically

The test also characterizes FCM recovery time once the delay is removed — that output is documentation, not a pass/fail gate.

### 1.4 Opt-Out Protection

Two structural problems with naive opt-out protection are worth naming upfront. First, a multi-week statistical baseline period accepts permanent audience damage as an interim condition — opted-out users do not come back. Second, a relative per-type alert is statistically undefined at launch when no stable distribution exists.

Both problems are addressed by inverting the protection model: **conservative absolute limits operate from day one, and statistical alerting is layered on top as data accumulates.**

**Day-one absolute limits (enforced in the channel dispatcher, not by convention):**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max push per user per day | 3 | Launch target; 5/day is the eventual ceiling |
| Max push per user per hour | 1 | Prevents burst even within daily limit |
| Per-type daily cap | 1 per type per user per day | Requires closed type taxonomy — see below |
| Aggregate weekly opt-out alert | 0.5% of push-eligible users (35K) in 7 days | P1 page; catches problems before widespread permanent damage |

**The per-type cap requires a closed notification type taxonomy.** Without a controlled, versioned taxonomy, "notification type" is caller-defined, the cap is trivially circumvented, and the protection is nominal. The taxonomy is therefore a hard prerequisite for month 1 launch, not a later refinement.

The taxonomy is defined as a closed enum in the notification service schema. Callers must specify a type from the enum; unrecognized types are rejected at ingestion with a 400 error. Adding a new type requires a pull request to the schema, reviewed by two engineers, and a corresponding runbook entry defining the type's expected volume and opt-out thresholds. The enum is version-controlled and its changelog is part of the monthly runbook review.

At launch, the taxonomy includes: `social_interaction` (likes, comments, mentions), `follow_request`, `direct_message`, `system_alert`, `auth_verification`, `digest_summary`, and `re_engagement`. Additional types require the pull request process. This list is not exhaustive of what will eventually exist; it is exhaustive of what is permitted at launch.

**Weeks 1–8 opt-out monitoring — explicit accountability structure:**

The document previously acknowledged that weeks 1–8 monitoring is manual. That acknowledgment was honest but incomplete — naming a gap without closing it is not a mitigation. The accountability structure is:

- **Owner:** E3 owns the opt-out dashboard and the weekly review. This is a named, non-rotating responsibility.
- **Artifact:** E3 posts