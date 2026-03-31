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

This figure already reflects elevated load — it is the average rate *within* the concentration window, not above the daily average. A separate spike multiplier applied on top of this would compound two elevation factors and require empirical justification for the compounding. We do not apply a stacked multiplier. Instead, we apply a 2× spike factor above the daily average as the conventional usage:

51M / 86,400 × 2 = **~1,180/sec design floor** (2× daily average)

We take the higher of the two figures — **2,125/sec** — as the sustained design envelope, and add a 50% headroom buffer for momentary spikes *within* the peak window to reach a **design ceiling of ~3,190/sec**. The 50% intra-window spike factor is conservative and does not require empirical justification at this scale; it is the headroom buffer, not the primary sizing input.

This is more conservative than the prior 6,375/sec figure, which compounded two elevation factors without justification. If load testing in months 4–5 reveals actual peak concentration exceeds these estimates, we revise before month 6. The traffic model is a living document, not a one-time calculation.

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
| **SMS/day** | **~50K** | Auth and security only; P0 fallback budget analyzed separately in Section 1.1a |
| **Total/day (launch)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target)** | **~51M** | Sum across channels at target frequency |
| Peak window share | 60% in 4 hours | Morning + evening concentration |
| **Peak sustained throughput (target)** | **~2,125/sec** | Average rate within concentration window |
| **Design ceiling (50% intra-window buffer)** | **~3,190/sec** | Headroom for momentary spikes within peak windows |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals.

### 1.1a SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225,000/month — an existential budget problem. Restricting SMS to auth and security events brings this to 50,000/day × $0.0075 × 30 = **$11,250/month** (the prior document stated ~$11K/month; $11,250 is the correct figure).

**P0 SMS fallback budget:** Section 5.3 introduces SMS fallback for P0 push notifications when push delivery fails. This creates a second SMS cost pathway not bounded by the auth/security allowlist. The budget analysis must account for both.

P0 notifications are defined as account security events, direct messages from connections with whom the user has a persistent conversation, and service alerts affecting the user's account. These are not the same population as all push notifications. Estimated P0 volume: ~2% of push volume at launch = 21M × 0.02 = 420,000/day. Not all P0 push notifications will fail — SMS fallback triggers only when push delivery fails after retry exhaustion. Assuming a 2% push failure rate, the fallback population is: 420,000 × 0.02 = **~8,400 SMS/day from P0 fallback**.

Combined SMS ceiling: 50,000 (auth/security) + 8,400 (P0 fallback) = **~58,400/day = ~$13,100/month**. This is the budget figure used for capacity planning. A hard monthly cap of $15,000 is configured in Twilio's spend controls; notifications to the on-call engineer fire at 80% of cap. If the cap is reached, P0 SMS fallback is suspended (push retry continues) and the incident is escalated as P1.

SMS gate enforcement is implemented in the channel dispatcher. Two separate gates are enforced:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted for any notification type, but only after push retry exhaustion (defined as 3 attempts with exponential backoff over 90 seconds). The fallback gate checks the monthly spend counter before dispatching; if the counter exceeds the cap, the fallback is suppressed and logged.

Escalation path for urgent allowlist additions: any engineer may open a draft PR with the `sms-allowlist-emergency` label. The on-call engineer and the engineer's manager are paged immediately. If both approve within 30 minutes, the change is merged and deployed without waiting for the standard review cycle. All emergency additions are reviewed in the next business day's standup.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a runbook maintenance process that continues through month 6.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**On E1's dual role:** E1 owns the most critical component (queue infrastructure) and serves as push coverage partner. These roles create a conflict during the period when push is newly launched and E1 is completing push coverage gates: an infrastructure incident during E1's push on-call coverage leaves infrastructure without a primary responder.

The resolution is sequencing, not structural reassignment. E1 completes push coverage gates in month 2, *after* infrastructure has been running in production for a full month and is in a stable state. During E1's Gate 3 push solo on-call week in month 2, E2 is designated as infrastructure incident backup — explicitly documented in the on-call rotation for that week. If an infrastructure incident occurs, E2 pages E1 immediately regardless of E1's push on-call status; E1 triages and determines whether to hand off the push incident to E2 or handle infrastructure with E2's support. This is a documented escalation path, not an assumed behavior.

This does not fully eliminate the conflict — E1 may be handling two simultaneous incidents during that week. We accept this risk because: (a) the window is one week, (b) infrastructure is stable by month 2, and (c) the alternative (E1 never completing push coverage gates) creates a permanent single point of failure on push. The one-week conflict is preferable to a permanent gap.

**On the notification type taxonomy ownership:** The taxonomy is a hard prerequisite for month 1 launch (see Section 1.4). It requires an owner and allocated time. **E1 owns the taxonomy definition.** The initial taxonomy definition is allocated to week 1 of month 1, before E1 begins queue infrastructure implementation. Rationale: the taxonomy is a schema decision that affects all downstream components; defining it first prevents rework. Time estimate: 2 days for initial definition, review by E2 and E3, and merge. This is not a compression risk — it is the first task, not a parallel task.

**Coverage partner structure — rationale for linear rather than circular pairing:**

A circular structure (E2↔E4, E1↔E3) creates a specific failure: if E4 is unavailable, E2 covers email/SMS — but no one covers push while E2 is handling email incidents. The linear structure resolves this:

- E1 covers push when E2 is unavailable. E1 has no channel primary of their own, making them the natural backup for push.
- E3 covers email/SMS when E4 is unavailable. E3's preference and suppression work shares significant overlap with E4's email/SMS scope.
- E4 covers in-app when E3 is unavailable.
- E2 covers infrastructure when E1 is unavailable.
- E1 serves as tertiary backup for all channels in the event both primary and coverage partner are simultaneously unavailable. This is documented in the runbook and verified at month 4 and month 6 spot-checks.

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The pager goes to the coverage partner only; the primary owner is unavailable for the duration. The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt within 3 business days. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Month 4 and month 6 spot-checks:**

Spot-checks re-execute the Gate 2 simulation against the current runbook. A failed spot-check is treated as a **channel freeze for new traffic ramp-up** — not merely a P2 issue. Specifically: the channel is held at its current traffic level (no further ramp-up, no new feature launches for that channel) until the spot-check passes. The coverage partner re-simulates within 5 business days. If the second attempt fails, the channel is rolled back to the previous traffic level and the incident is escalated to engineering leadership.

This is a stronger standard than the initial proposal, which treated failed spot-checks as P2 issues while the coverage partner remained in the role. A coverage partner who cannot pass the spot-check is not providing real coverage; treating the failure as merely a tracked issue accepts a gap while pretending it doesn't exist.

**Runbook maintenance through month 6:**

- **Trigger-based updates:** Any production incident that required knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and change log, or an explicit "no changes required" sign-off. The monthly review sign-off is a required field in the sprint planning template for the first sprint of each month.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation. A failed spot-check triggers the channel freeze procedure described above.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — and this standard is re-verified at months 4 and 6, not assumed to persist from launch.

### 1.3 Delivery Milestones

**Month 1 schedule — the gate timing problem, addressed explicitly:**

The prior version required E3 to complete Gates 1–2 for in-app while simultaneously building the preference API and in-app delivery system, with no slack for a gate failure before month 1 ends. This is not a viable schedule. The resolution is to separate channel build from coverage gate completion: **coverage gates for in-app complete in month 2, not month 1.**

Month 1 delivers a working in-app system. Month 2 delivers a *covered* in-app system. This is an honest representation of what 4 weeks can accomplish.

**Implication:** During month 1, in-app is in production but E3 is the sole person who can respond to incidents. This is an accepted risk with three mitigations: (a) in-app is the lowest-risk channel — no third-party dependencies, no cost implications, failure modes are well-understood; (b) E4 is available as an informal backup (not a coverage-gate-qualified backup, but a competent engineer who can read code and execute basic triage); (c) in-app traffic in month 1 is internal users only, not general availability.

**Month 2 coverage gate sequencing — push and in-app simultaneously:**

Month 2 must complete coverage gates for both in-app (E4 covering E3) and push (E1 covering E2). These run in parallel across different pairs, which is feasible. The sequencing:

- Weeks 1–2: E4 executes Gate 1 for in-app. E1 executes Gate 1 for push. Primary owners (E3, E2) support runbook reviews.
- Week 3: E4 executes Gate 2 for in-app. E1 executes Gate 2 for push. These are independent simulations.
- Week 4: E4 executes Gate 3 solo on-call for in-app. E1 executes Gate 3 solo on-call for push. E2 is designated infrastructure incident backup during E1's Gate 3 week (see Section 1.2).

**If either Gate 2 simulation fails in week 3:** The affected channel's Gate 3 slips to month 3. The other channel proceeds on schedule. Gate failures are channel-specific and do not cascade.

**If both Gate 2 simulations fail in week 3:** Month 2 ends with push and in-app operational but not yet covered. Both coverage completions slip to month 3. This is the worst-case scenario; the mitigation is that both channels remain at internal-user traffic levels until coverage gates clear.

| Month | Deliverable | Coverage Status |
|-------|