# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. The distinction matters: the failure mode we're protecting against is not queue topology per se, but the operational reality of shared consumer pool management. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations—push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

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
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback analyzed in §1.1b |
| **Total/day (launch)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target)** | **~51M** | Sum across channels at target frequency |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals.

### 1.1a Peak Throughput Calculation

The daily volume figures above are inputs. The design ceiling requires a separate derivation.

**Step 1: Identify the peak window.** Morning and evening peaks each occupy approximately 2 hours and together account for approximately 60% of daily volume. This is an assumption we will validate against actual traffic in month 2 and revise. The 4-hour peak window is a planning input, not a validated measurement.

**Step 2: Calculate average throughput within the peak window.**

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained**

This is the average rate *within* the peak window—already elevated above the daily average of ~590/sec. It is the sustained rate we must handle during the worst typical day.

**Step 3: Determine the design ceiling.** The design ceiling is not 2,125/sec plus an undifferentiated multiplier. It is the capacity we provision to handle 2,125/sec with margin for two specific, named scenarios:

- **Momentary intra-window spikes:** Bursty social events (a viral post, a breaking news item) can produce 2–3× the window average for 30–60 seconds. We provision for 2× sustained peak = ~4,250/sec as the instantaneous ceiling, sized to absorb without queue backup for 60 seconds.
- **Traffic model error:** Our peak window concentration estimate may be wrong. The 2× factor provides headroom if concentration is higher than assumed.

**Design ceiling: 4,250/sec instantaneous, 2,125/sec sustained.**

Applying a separate spike multiplier on top of the already-elevated peak rate compounds two elevation factors without justification. This version separates sustained capacity from instantaneous burst capacity, names the specific scenario each addresses, and validates both against load test results in month 5.

### 1.1b SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), unrestricted SMS would be an existential budget problem. We restrict SMS to two categories:

**Category 1 — Auth and security (primary channel):** OTP, password reset, suspicious login alerts. 50,000/day × $0.0075 × 30 = **$11,250/month**.

**Category 2 — P0 push fallback:** SMS sent when push delivery fails after retry exhaustion for P0-classified notifications.

P0 fallback cost depends on two inputs: P0 volume and push failure rate. Both require explicit justification rather than assertion.

**P0 volume:** P0 notifications are account security events, direct messages from connections with a persistent conversation history, and service alerts affecting the user's account. Estimated at 2% of push volume at launch = 21M × 0.02 = 420,000/day. This will be measured directly once production data is available.

**Push failure rate:** Industry-observed push failure rates vary substantially by cause:
- Token staleness (uninstalled apps, months-inactive users): 5–15% of push-eligible population at any given time
- Device-state failures (device off, no network): 3–8% of attempted deliveries fail transiently
- FCM/APNs service errors: <1% under normal conditions

We use **10% as the baseline failure rate** (includes token staleness and device-state failures) and **20% for stress-test planning**.

| Scenario | Push failure rate | P0 SMS fallback/day | Monthly cost |
|----------|-----------------|---------------------|--------------|
| Optimistic | 5% | 21,000 | $4,725 |
| **Baseline (budget basis)** | **10%** | **42,000** | **$9,450** |
| Stress | 20% | 84,000 | $18,900 |

**Combined monthly SMS cost:**

| Scenario | Auth/security | P0 fallback | Total/month |
|----------|--------------|-------------|-------------|
| Optimistic | $11,250 | $4,725 | $15,975 |
| **Baseline** | **$11,250** | **$9,450** | **$20,700** |
| Stress | $11,250 | $18,900 | $30,150 |

The baseline spend is ~$20,700/month. A $15,000 hard cap—as a prior design considered—is breached at baseline push failure rates. The revised budget is **$25,000/month operational target**, with a **$30,000/month hard cap** configured in Twilio's spend controls. The stress scenario would breach this cap; if stress-scenario failure rates materialize, P0 fallback is suspended and the underlying push reliability problem is treated as a P1 incident, not a budget line to optimize.

**Why not lower the cap and accept degraded P0 delivery?** P0 notifications include account security events. Suppressing SMS fallback for a failed login alert because we're over budget is a security regression. The budget is sized to avoid that tradeoff under baseline conditions.

Alert thresholds: page on-call at 70% of monthly cap ($21,000); escalate to engineering leadership at 85% ($25,500).

**Gate enforcement** is implemented in the channel dispatcher with two independent gates:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted for any P0-classified notification, but only after push retry exhaustion (3 attempts with exponential backoff over 90 seconds). The fallback gate checks the monthly spend counter before dispatching; if the counter exceeds the hard cap, the fallback is suppressed, logged, and the on-call engineer is paged.

**Escalation path for urgent allowlist additions:** Any engineer may open a draft PR with the `sms-allowlist-emergency` label. The on-call engineer and the engineer's manager are paged immediately. If both approve within 30 minutes, the change is merged and deployed without waiting for the standard review cycle. All emergency additions are reviewed in the next business day's standup.

---

## 2. Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a runbook maintenance process that continues through month 6.

### 2.1 Notification Type Taxonomy

The taxonomy is a hard prerequisite for month 1 launch. It gates P0/P1/P2 classification (Section 4), SMS gate enforcement (§1.1b), and channel routing logic. E1 owns the initial definition, allocated to days 1–3 of week 1 before any implementation work begins. Defining it first prevents rework across all downstream components.

**A specific structural risk to resolve in week 1:** P0 is used both as a priority routing signal and as the trigger for SMS fallback. If the criteria diverge—for example, if the priority team wants P0 to include viral content notifications but the budget team does not want viral content triggering SMS fallback—the resolution is to separate the concepts: a `notification_priority` field (P0/P1/P2) for routing, and a separate boolean `sms_fallback_eligible` field for fallback gate control. These can be set independently. The taxonomy definition must explicitly address this separation.

**Failure modes and escalation:**
- *Classification disagreements:* E1, E2, and E3 have 48 hours to resolve in a synchronous working session. If unresolved, the engineering lead makes a binding decision. Disputes affecting fewer than 5% of notification types do not block implementation—those types are temporarily classified as P2 and reclassified next sprint.
- *P0 classification disputes:* Because P0 directly gates SMS fallback logic, any unresolved P0 dispute blocks implementation immediately and is escalated to the engineering lead within 48 hours.
- *Timeline:* If week 1 ends without a merged taxonomy, the month 1 timeline slips by one week and the engineering lead is notified.

### 2.2 Engineer Assignments

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Coverage chain:** E1 covers push when E2 is unavailable. E3 covers email/SMS when E4 is unavailable. E4 covers in-app when E3 is unavailable. E2 covers infrastructure when E1 is unavailable. E1 serves as tertiary backup for all channels when both primary and coverage partner are simultaneously unavailable.

**Why linear coverage and not circular pairing:** A circular structure (E2↔E4, E1↔E3) creates a specific failure: if E4 is unavailable, E2 covers email/SMS—but no one covers push while E2 is handling an email incident. The linear structure resolves this by giving E1 (no channel primary of their own) the natural backup role for push.

### 2.3 E1's Dual-Role Conflict

E1 owns the most critical component (queue infrastructure) and serves as push coverage partner. During E1's Gate 3 push solo on-call week in month 2, both roles could be active simultaneously.

Describing this conflict and then saying "E1 triages and decides whether to hand off" is not a resolution—it is a restatement of the problem under incident stress. The actual resolution requires three things:

**First, infrastructure must be genuinely stable before E1's Gate 3 week.** The bar is not merely "a full month of operation" but specifically: zero P0 infrastructure incidents in the final two weeks of month 1, all known issues resolved, and no open infrastructure PRs with unmerged fixes. If this bar is not met, E1's Gate 3 week slips to month 3 and push remains at internal-traffic levels.

**Second, E2 must have a defined infrastructure triage capability.** Not full ownership, but specifically: (a) identify whether an infrastructure alert is a false positive, (b) execute the top 5 most common infrastructure runbook procedures independently, and (c) know when to wake E1 versus handle it. E2 completes this preparation in month 1, week 3, verified by E1 review of E2's runbook execution in staging.

**Third, the on-call rotation during E1's Gate 3 week explicitly designates E2 as infrastructure secondary.** If an infrastructure alert fires, E2 triages first. If E2 determines it requires E1, E2 pages E1 and simultaneously takes ownership of the push incident. This is a documented handoff protocol written in the runbook and practiced in month 1—not an assumed behavior.

**Residual risk:** If a novel infrastructure failure occurs simultaneously with a push incident during E1's Gate 3 week, we have a genuine resource constraint. We accept this risk because the one-week exposure window is bounded, and the mitigations above make simultaneous novel failures unlikely rather than merely inconvenient. This is an explicit tradeoff.

### 2.4 Coverage Gate Structure

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems—not a single pre-launch test that can only fail at the worst possible moment.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred—not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. A failed simulation triggers a runbook update and a second attempt within 3 business days. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Month 4 and month 6 spot-checks:** Each coverage partner re-executes the Gate 2 simulation against the current runbook. A failed spot-check triggers a **channel freeze for new traffic ramp-up**—the channel is held at its current traffic level until the spot-check passes, with a 5-business-day re-simulation window. A second failure escalates to engineering leadership and rolls back the channel to its previous traffic level. A coverage partner who cannot pass the spot-check is not providing real coverage; treating the failure as a tracked issue accepts a gap while pretending it doesn't exist.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system—a standard re-verified at months 4 and 6, not assumed to persist from launch.

### 2.5 Runbook Maintenance

**Trigger-based updates:** Any production incident requiring knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.

**Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and change log, or an explicit "no changes required" sign-off. The monthly review