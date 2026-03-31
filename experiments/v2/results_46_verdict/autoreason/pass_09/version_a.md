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

**On peak throughput:** The naive calculation distributes daily volume across 86,400 seconds. This is wrong when traffic is concentrated. If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual sustained throughput during those windows is:

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

This figure already reflects elevated load — it is the average rate *within* the concentration window, not above the daily average. Applying a separate spike multiplier on top of this compounds two elevation factors and requires empirical justification for the compounding. Instead, we apply a 50% intra-window headroom buffer for momentary spikes within the peak window:

2,125 × 1.5 = **~3,190/sec design ceiling**

The 50% buffer is conservative headroom, not a primary sizing input. If load testing in months 4–5 reveals actual peak concentration exceeds these estimates, we revise before month 6. The traffic model is a living document.

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
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback budget analyzed in Section 1.1a |
| **Total/day (launch)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target)** | **~51M** | Sum across channels at target frequency |
| Peak window share | 60% in 4 hours | Morning + evening concentration |
| **Peak sustained throughput (target)** | **~2,125/sec** | Average rate within concentration window |
| **Design ceiling (50% intra-window buffer)** | **~3,190/sec** | Headroom for momentary spikes within peak windows |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals.

### 1.1a SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225,000/month — an existential budget problem. Restricting SMS to auth and security events brings this to 50,000/day × $0.0075 × 30 = **$11,250/month**.

**P0 SMS fallback budget:** Section 5.3 introduces SMS fallback for P0 push notifications when push delivery fails. This creates a second SMS cost pathway not bounded by the auth/security allowlist. The budget analysis must account for both.

P0 notifications are defined as account security events, direct messages from connections with whom the user has a persistent conversation, and service alerts affecting the user's account. Estimated P0 volume: ~2% of push volume at launch = 21M × 0.02 = 420,000/day. SMS fallback triggers only when push delivery fails after retry exhaustion. Assuming a 2% push failure rate: 420,000 × 0.02 = **~8,400 SMS/day from P0 fallback**.

Combined SMS ceiling: 50,000 (auth/security) + 8,400 (P0 fallback) = **~58,400/day = ~$13,100/month**.

A hard monthly cap of $15,000 is configured in Twilio's spend controls; on-call alerts fire at 80% of cap. If the cap is reached, P0 SMS fallback is suspended (push retry continues) and the incident is escalated as P1.

**Gate enforcement** is implemented in the channel dispatcher with two independent gates:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted for any notification type, but only after push retry exhaustion (3 attempts with exponential backoff over 90 seconds). The fallback gate checks the monthly spend counter before dispatching; if the counter exceeds the cap, the fallback is suppressed and logged.

**Escalation path for urgent allowlist additions:** Any engineer may open a draft PR with the `sms-allowlist-emergency` label. The on-call engineer and the engineer's manager are paged immediately. If both approve within 30 minutes, the change is merged and deployed without waiting for the standard review cycle. All emergency additions are reviewed in the next business day's standup.

---

## 2. Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a runbook maintenance process that continues through month 6.

**On the notification type taxonomy ownership:** The taxonomy is a hard prerequisite for month 1 launch (see Section 4). E1 owns the taxonomy definition. The initial definition is allocated to week 1 of month 1, before E1 begins queue infrastructure implementation — defining it first prevents rework across all downstream components. Time estimate: 2 days for initial definition, review by E2 and E3, and merge.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Why linear coverage and not circular pairing:** A circular structure (E2↔E4, E1↔E3) creates a specific failure: if E4 is unavailable, E2 covers email/SMS — but no one covers push while E2 is handling an email incident. The linear structure resolves this:

- E1 covers push when E2 is unavailable. E1 has no channel primary of their own, making them the natural backup.
- E3 covers email/SMS when E4 is unavailable. E3's preference and suppression work shares significant overlap with E4's email/SMS scope.
- E4 covers in-app when E3 is unavailable.
- E2 covers infrastructure when E1 is unavailable.
- E1 serves as tertiary backup for all channels when both primary and coverage partner are simultaneously unavailable. This is documented in the runbook and verified at months 4 and 6.

**On E1's dual role conflict:** E1 owns the most critical component (queue infrastructure) and serves as push coverage partner. During E1's Gate 3 push solo on-call week in month 2, an infrastructure incident could leave infrastructure without a primary responder.

The resolution is sequencing: E1 completes push coverage gates in month 2, *after* infrastructure has been running in production for a full month and is in a stable state. During E1's Gate 3 week, E2 is explicitly designated as infrastructure incident backup in the on-call rotation. If an infrastructure incident occurs, E2 pages E1 immediately; E1 triages and determines whether to hand off the push incident to E2 or handle infrastructure with E2's support. This is a documented escalation path, not an assumed behavior.

We accept the residual risk that E1 may handle two simultaneous incidents during that week. The one-week conflict is preferable to a permanent gap in push coverage. This is an explicit tradeoff.

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems — not a single pre-launch test that can only fail at the worst possible moment.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt within 3 business days. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Month 4 and month 6 spot-checks:**

Spot-checks re-execute the Gate 2 simulation against the current runbook. A failed spot-check triggers a **channel freeze for new traffic ramp-up** — the channel is held at its current traffic level (no further ramp-up, no new feature launches for that channel) until the spot-check passes. The coverage partner re-simulates within 5 business days. If the second attempt fails, the channel is rolled back to the previous traffic level and the incident is escalated to engineering leadership.

A coverage partner who cannot pass the spot-check is not providing real coverage. Treating the failure as merely a tracked issue accepts a gap while pretending it doesn't exist.

**Runbook maintenance through month 6:**

- **Trigger-based updates:** Any production incident requiring knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and change log, or an explicit "no changes required" sign-off. The monthly review sign-off is a required field in the sprint planning template — this creates a visible artifact and a specific moment of accountability, not aspirational intent.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation. A failed spot-check triggers the channel freeze procedure above.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and this standard is re-verified at months 4 and 6, not assumed to persist from launch.

---

## 3. Delivery Milestones

**The gate timing constraint:** Coverage gates require a minimum 3-week span (Gate 1 at week -2, Gate 2 at week -1, Gate 3 at week 0). This means a channel cannot launch and complete its coverage gates within the same calendar month unless the channel launches in week 1 of that month. Treating coverage gates as month 1 deliverables for a channel that is also being built in month 1 is not a viable schedule.

The resolution: **separate channel build from coverage gate completion.** Month 1 delivers a working in-app system. Month 2 delivers a *covered* in-app system. This is an honest representation of what 4 weeks can accomplish.

**Implication for month 1:** In-app is in production but E3 is the sole person who can respond to incidents. This is an accepted risk with three mitigations: (a) in-app is the lowest-risk channel — no third-party dependencies, no cost implications, well-understood failure modes; (b) E4 is available as an informal backup (not coverage-gate-qualified, but a competent engineer who can triage); (c) in-app traffic in month 1 is internal users only, not general availability.

**Month 2 coverage gate sequencing — push and in-app simultaneously:**

Month 2 must complete coverage gates for both in-app (E4 covering E3) and push (E1 covering E2). These run in parallel across different pairs, which is feasible.

- Weeks 1–2: E4 executes Gate 1 for in-app. E1 executes Gate 1 for push. Primary owners support runbook reviews.
- Week 3: E4 executes Gate 2 for in-app. E1 executes Gate 2 for push. Independent simulations.
- Week 4: E4 executes Gate 3 solo on-call for in-app. E1 executes Gate 3 solo on-call for push. E2 is designated infrastructure incident backup during E1's Gate 3 week.

**If either Gate 2 simulation fails in week 3:** The affected channel's Gate 3 slips to month 3. The other channel proceeds on schedule. Gate failures are channel-specific and do not cascade.

**If both Gate 2 simulations fail in week 3:** Both channels remain at internal-user traffic levels until coverage gates clear in month 3. This is the worst-case scenario; it does not block email or SMS development.

| Month | Deliverable | Coverage Status |
|-------|-------------|-----------------|
| 1 | Infrastructure provisioned; in-app live (internal users); preference API skeleton; notification type taxonomy finalized | In-app operational, E3 sole responder. E4 informal backup. Internal traffic only. |
| 2 | Push (FCM + APNs) live; email transactional live; basic monitoring | In-app coverage gates complete (E4). Push coverage gates complete (E1). Both channels advance to general availability upon gate completion. |
| 3 | Email digests; SMS (auth only); aggregation logic | Email coverage gates complete (E3). SMS gate enforcement live at dispatcher. SMS coverage gates complete (E3). |
| 4 | Full preference management; suppression lists; advanced batching. Month 4 runbook spot-checks. | Spot-checks for all channels. Channel freeze procedure enforced for any failures. E1 tertiary backup verification. |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher); A/B framework | — |
| 6 | Three-part validation suite (Section 3a). Month 6 runbook spot-checks. | Spot-checks for all channels. |

### 3a. Month 6 Testing

Month 6 testing comprises three distinct tests with three distinct purposes. Collapsing them into a single test answers none of the questions well and obscures which system component is under test.

**Test 1 — Internal infrastructure validation at design ceiling (3,190/sec):**

Load generated at the full design ceiling against a production-mirror staging environment. FCM is mocked at this load level. This is an explicit