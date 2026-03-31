# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. The trigger criteria for revisiting this decision are defined in Section 2.3 as measurable operational thresholds, not lagging MAU milestones.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

A critical modeling error to avoid upfront: different channels have different eligible populations. Push notifications reach installed-app users regardless of daily activity. In-app notifications only reach logged-in users. Treating DAU as the denominator for all channels produces wrong numbers.

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
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput (target)** | **~1,770/sec** | 51M × 3 / 86,400 |

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. The gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. The allowlist requires two-engineer sign-off to modify and is version-controlled. Governance and escalation paths for urgent additions are described in Section 3.3.

**On push volume:** 5 notifications/day/installed user is the eventual target, not the launch configuration. We launch at 3/day and ramp based on observed opt-out data. The ramp criteria are defined in Section 1.4. These are estimates; we instrument from day one and publish a traffic model review in month 2.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** "Cross-training" in the sense of watching someone else work does not constitute coverage ability. The mitigation is paired ownership, documented runbooks, demonstrated coverage capability verified before each channel launches, and a runbook maintenance process that continues through month 6.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates. The gates are separated in time specifically to create checkpoints with room to fix problems — not a single pre-launch test that can only fail at the worst possible moment.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The primary owner submits the runbook to the coverage partner, who attempts to execute every step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate. The runbook standard is explicit: written for a competent backend engineer unfamiliar with the system, not for the authors.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Runbook maintenance through month 6:**
Runbook quality at launch means nothing if runbooks aren't kept current. The maintenance process is structured, not aspirational:

- **Trigger-based updates:** Any production incident that required knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and a list of changes made (or an explicit "no changes required" sign-off). Skipped reviews are flagged in the weekly team sync.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation against the current runbook. A failed spot-check is treated as a P2 operational issue.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and that this standard is re-verified at months 4 and 6, not assumed to persist from launch.

**E4's month 1 workload:** E4's solo on-call in month 1 covers queue health, worker health, and in-app delivery — not FCM/APNs integrations that aren't live yet. E4's email/SMS integration work is scoped to design and scaffolding in month 1, with implementation in month 2. If month 1 scope proves unachievable, push launch in month 2 slips — not the coverage requirement.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification |
|-------|-------------|----------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | Gate 1 (week 2); Gate 2 (week 3); E4 Gate 3 solo on-call for queue/in-app scope |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E2 Gates 1–3 for email; E4 extends push coverage through Gates 1–3 |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 Gates 1–3 for SMS |
| 4 | Full preference management, suppression lists, advanced batching; month 4 runbook spot-checks | Spot-checks for all channels |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Three-part validation suite (see Section 1.3a); month 6 runbook spot-checks | Spot-checks for all channels |

### 1.3a Month 6 Testing

The prior approach had one structural flaw worth naming directly: proposing to mock FCM in the 4× stress test invalidates the test's primary purpose. The stated risk was quota exhaustion during FCM degradation scenarios. A test that removes FCM characterizes our system's internal backpressure in isolation — useful, but it doesn't test the actual risk. Month 6 testing comprises three distinct tests with three distinct purposes.

**Test 1 — 3× validation (pass/fail against design envelope):**
Load generated at 3× sustained peak throughput (~5,310/sec) against a production-mirror staging environment running continuously since month 2. FCM is real (staging app credentials). Pass criteria: P0 SLA met (10s), P1 SLA met (60s) for >99% of notifications, no data loss, backpressure engages before queue depth exceeds 1M entries, all monitoring alerts fire correctly. Failure on any criterion is a blocking defect.

**Test 2 — FCM quota pressure simulation (characterize the actual identified risk):**
FCM quota is artificially constrained to 60% of normal allocation in staging (via a test project with reduced quota), while push load is held at 2× normal. This tests the specific scenario from the FCM quota analysis: partial quota exhaustion during elevated load. Success criteria: push notifications back up without data loss, P0 notifications route to SMS fallback (Section 5.3), queue depth monitoring alerts fire correctly, and FCM quota metrics are visible in dashboards. This test does not pass or fail on delivery speed — it characterizes degradation behavior and documents it as the known failure mode. The 2× load level is an explicit limitation: FCM staging quota constraints make 3× impractical, and this is documented in the test plan.

**Test 3 — 4× stress (characterize graceful degradation beyond design envelope):**
Load generated at 4× peak throughput. FCM is mocked at this load level — not because mocking is ideal, but because the question being answered here is specifically about our system's behavior beyond design limits: does backpressure engage? Does the system shed P2 load before P1? Does it fail gracefully or catastrophically? The FCM mock is appropriate for this test because FCM is not the variable under test. This test has no pass/fail criteria; its output is a documented characterization of failure modes and a capacity envelope.

The FCM quota simulation (Test 2) is the test that addresses the actual identified risk. It is not the same test as Test 3, and conflating them produces a test plan that addresses neither question well.

### 1.4 Opt-Out Protection

Two structural problems with a naive approach are worth naming upfront. First, a multi-week baseline period for statistical alerting accepts permanent audience damage as an interim condition — opted-out users do not come back. Second, a relative per-type alert (e.g., "3× the rate of other types") is statistically undefined at launch: it requires a stable distribution of notification types with sufficient volume per type, a condition that doesn't exist in the first weeks of operation.

Both problems are addressed by inverting the protection model: **conservative absolute limits operate from day one, and statistical alerting is layered on top as data accumulates.**

**Day-one absolute limits (enforced in the channel dispatcher, not by convention):**

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max push per user per day | 3 | Launch target; 5/day is the eventual ceiling, not the starting point |
| Max push per user per hour | 1 | Prevents burst even within daily limit |
| Per-type daily cap | 1 per type per user per day | Prevents any single type from dominating |
| Aggregate weekly opt-out alert | 0.5% of push-eligible users (35K) in 7 days | P1 page; conservative enough to catch problems before widespread permanent damage |

**Why 3/day at launch, not 5/day:** The 5/day target is derived from industry benchmarks for mature notification programs with known-good content. At launch, we have neither the content track record nor the statistical tools to detect problems quickly. Starting at 3/day provides headroom to observe opt-out behavior before increasing frequency. The ramp toward 5/day is gated on the statistical alerting system being armed (see below) and on observed opt-out data meeting defined thresholds.

**Why 35K weekly opt-outs as the aggregate alert, not 140K:** 35K is 0.5% of the push-eligible audience — conservative enough to trigger before permanent damage is widespread. The correct way to avoid false positives is to set a conservative threshold and accept some investigation overhead, not to set a threshold that only fires after significant damage has accumulated.

**Per-type absolute limits as the early warning mechanism:**
Each notification type has an absolute opt-out rate threshold of 2% of recipients per week, enforced from day one. If "like" notifications generate opt-outs at >2% of recipients in a 7-day window, that is a P2 investigation regardless of what other types are doing. Types with fewer than 2,500 recipients in the measurement window (fewer than 50 expected opt-outs at the threshold) are excluded from automated alerting and reviewed manually in the weekly traffic review — this prevents false positives from small sample sizes without silently ignoring small-volume types.

**Statistical alerting layered on top (week 9 onward):**
After 8 weeks of operation, we compute per-type baseline opt-out rates and add statistical alerting (μ + 2σ for P2, μ + 3σ for P1) as an additional layer. The absolute thresholds remain in force — statistical alerting supplements, not replaces, them. Statistical alerts are more sensitive to gradual drift; absolute limits protect against acute spikes.

**Frequency ramp gate:**
Increasing push frequency from 3/day toward 5/day requires two conditions: (1) 8 weeks of operation without triggering the aggregate weekly opt-out alert, and (2) no notification type with an opt-out rate above 1% in the most recent 4-week window. The ramp proceeds in 0.5/day increments with 2-week observation periods between increments. The dispatcher cap is a configuration value that requires a pull request with explicit team sign-off documented — not a unilateral configuration change.

---

## 2. System Architecture

### 2.1 Redis Memory Budget

Before describing the architecture that depends on Redis, we establish that Redis can actually support it. Redis serves multiple functions in this system; their requirements must be sized together.

**Redis Sentinel cluster configuration:** 3 nodes, each with 32GB RAM allocated to Redis. We target maximum utilization of 70% (22GB), leaving 30% headroom for memory spikes, fragmentation, and replication buffer.

**Memory budget by function:**

| Function | Entries | Bytes/Entry | Total | Notes |
|----------|---------|-------------|-------|-------|
| Priority queue (P1/P2 sorted set) | Peak in-flight | 150 bytes | 750MB | See Section 2.1a for derivation |
| P0 sorted set (dedicated keyspace) | ~500 max | 150 bytes | <1MB | P0 volume <0.1% of total |
| Preference cache | 10M users | 200 bytes | 2GB | All MAU; TTL 5 min with LRU eviction |
| WebSocket pub/sub | Active sessions | — | 1.5GB | See Section 2.1b for derivation |
| APNs JWT store | ~10 keys | ~500 bytes | <1MB | One per app signing key; rotate every 30 min |
| Worker coordination (locks, heartbeats) | ~100 keys | ~1KB | <1MB | Negligible |
| **Total estimated** | | | **~4.3GB** | |
| **Safety margin (3×)** | | | **~12.9GB** | Accounts for overhead, fragmentation, key expiry lag |
| **Headroom remaining** | | | **~9.1GB** | Against 22GB target ceiling |

**The 32GB node specification is the binding constraint.** If Redis memory utilization crosses 80% in production, that triggers an architectural review within 2 weeks. See Section 2.3 for the complete set of review triggers.

### 2.1a Queue Memory Derivation

The sorted set does not hold 51M entries simultaneously. Entries are enqueued and deque