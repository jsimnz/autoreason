# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single queue with channel fanout. This is a deliberate choice after analyzing a specific failure mode the single-queue design cannot contain: FCM backpressure during upstream degradation blocks email and in-app delivery when queues are shared. The tradeoff is higher operational complexity (four queues instead of one) and a shared classifier that becomes a cross-channel dependency requiring its own reliability treatment. The benefit is channel isolation that makes failure modes containable.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation and its limits. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations — push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

**On peak throughput:** If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual sustained throughput during those windows is:

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

This figure already reflects elevated load — it is the average rate *within* the concentration window. Applying a separate spike multiplier on top compounds two elevation factors and requires empirical justification. Instead, we apply a 50% intra-window headroom buffer for momentary spikes within the peak window:

2,125 × 1.5 = **~3,190/sec design ceiling**

**Push opt-in rate uncertainty:** The 70% push opt-in assumption is a planning input, not a known quantity. Published data for social apps ranges from 40–60%; 70% represents an optimistic scenario. Because the design ceiling calculation is sensitive to this input, we run three scenarios:

| Opt-in Rate | Push-Eligible Users | Push Volume/Day (target) | Total/Day (target) | Peak Sustained |
|---|---|---|---|---|
| 45% (conservative) | 4.5M | 22.5M | 38.5M | ~1,604/sec |
| 60% (base case) | 6M | 30M | 46M | ~1,917/sec |
| 70% (optimistic) | 7M | 35M | 51M | ~2,125/sec |

**We size infrastructure to the optimistic scenario (3,190/sec design ceiling).** The conservative scenario is not a reason to under-build; it is a reason to treat the traffic model as a living document with a mandatory month 2 review. If actuals fall in the conservative range, we publish revised sizing and reduce over-provisioning. If actuals exceed the optimistic scenario, we have a capacity problem to solve immediately.

| Metric | Estimate | Basis |
|---|---|---|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 4.5M–7M | 45–70% opt-in; base case 6M |
| Push/push-eligible user/day | ~3 (launch), ~5 (target) | Conservative at launch; ramp gated on opt-out data |
| **Push volume/day (base case, target)** | **~30M** | 6M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional |
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback analyzed in §1.1a |
| **Total/day (launch, base)** | **~34M** | Sum at launch frequency, base opt-in |
| **Total/day (target, optimistic)** | **~51M** | Sum at target frequency, optimistic opt-in |
| **Design ceiling** | **~3,190/sec** | Sized to optimistic scenario with 50% intra-window buffer |

### 1.1a SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225,000/month — an existential budget problem. Restricting SMS to auth and security events brings this to 50,000/day × $0.0075 × 30 = **$11,250/month**.

**P0 SMS fallback budget:** P0 SMS fallback for failed push deliveries creates a second cost pathway not bounded by the auth/security allowlist. P0 notifications are defined as account security events, direct messages from persistent connections, and service alerts affecting the user's account. Estimated P0 volume: ~2% of push volume.

**The 2% push failure rate assumption is a planning input, not a known quantity.** Early push implementations commonly see 5–10% failure rates before infrastructure matures. We therefore model three failure rate scenarios:

| Push Failure Rate | P0 Push Volume/Day | P0 SMS Fallback/Day | Monthly Cost |
|---|---|---|---|
| 2% (optimistic) | ~600K | ~12,000 | ~$270 |
| 5% (realistic early) | ~600K | ~30,000 | ~$675 |
| 10% (poor early impl.) | ~600K | ~60,000 | ~$1,350 |

*(P0 push volume at base opt-in: 30M × 0.02 = 600K/day)*

Combined SMS ceiling across all scenarios is well under $15,000/month. A hard monthly cap of $15,000 is configured in Twilio's spend controls with on-call alerts at 80% of cap. If the cap is reached, P0 SMS fallback is suspended (push retry continues) and the incident is escalated as P1.

**Atomic counter implementation:** A naive spend counter check has a race condition — multiple workers reading before any write commits can allow spend to exceed the cap. This is addressed with an atomic Redis counter:

```lua
local current = redis.call('GET', KEYS[1]) or 0
if tonumber(current) >= tonumber(ARGV[1]) then
  return -1  -- cap exceeded, suppress dispatch
end
return redis.call('INCR', KEYS[1])
```

The Lua script executes atomically. If Redis is unavailable, the dispatcher **fails closed**: SMS is suppressed rather than dispatched without a counter check. We prefer missed SMS over uncapped spend. The counter is keyed by calendar month and reset at month boundary.

**Gate enforcement** is implemented in the channel dispatcher with two independent gates:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted for any notification type, but only after push retry exhaustion (3 attempts with exponential backoff over 90 seconds). The fallback gate executes the atomic counter check before dispatching.

**Emergency allowlist approval:** With 4 engineers, the on-call-engineer-plus-manager approval chain creates stalls when the manager is one of the 4 engineers or is unavailable. Revised chain:

- **Primary approvers:** Any two engineers who are not the change author. With 4 engineers, this is always satisfiable as long as the author is not the only engineer available.
- **If only the author is available:** The change is blocked. SMS allowlist additions are not authorized under single-engineer availability. The incident escalates to the VP of Engineering, who has explicit authority to authorize emergency SMS routing outside the normal gate.
- **Self-approval is prohibited** in the allowlist configuration tooling, enforced in code, not policy. Manager awareness is required (the on-call engineer pages the manager), but manager approval is not required for the emergency path.
- All emergency additions are reviewed in the next business day's standup regardless of outcome.

---

## 2. Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a maintenance process that continues through month 6.

**On the notification type taxonomy:** The taxonomy is a hard prerequisite for month 1 work across all downstream components. E1 owns the initial definition, allocated to week 1 of month 1 before queue infrastructure implementation begins — defining it first prevents rework. Time estimate: 2 days for initial definition, review by E2 and E3, and merge.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|---|---|---|---|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Why linear coverage and not circular pairing:** A circular structure (e.g., E2↔E4, E1↔E3) creates a specific failure: if E4 is unavailable, E2 covers email/SMS — but no one covers push while E2 is handling an email incident. The linear structure resolves this:

- E1 covers push when E2 is unavailable. E1 has no channel primary of their own, making them the natural backup.
- E3 covers email/SMS when E4 is unavailable. E3's preference and suppression work shares significant scope overlap with E4's email/SMS work.
- E4 covers in-app when E3 is unavailable.
- E2 covers infrastructure when E1 is unavailable.
- E1 serves as tertiary backup for all channels when both primary and coverage partner are simultaneously unavailable. This is documented in the runbook and verified at months 4 and 6.

### 2.1 E1's Dual-Role Conflict

E1 owns the most critical component (queue infrastructure) and serves as push coverage partner. During E1's Gate 3 push solo on-call week in month 2, an infrastructure incident could leave infrastructure without a primary responder.

**The honest assessment:** With 4 engineers, there is no staffing solution that eliminates this conflict. The options are:

1. Accept the conflict with an explicit escalation path (rather than assumed behavior)
2. Delay E1's Gate 3 push coverage until month 3, after infrastructure has run stably for two months
3. Assign push coverage to E4 instead of E1, accepting that E4 would cover two channels

**We choose option 2.** Delaying E1's Gate 3 to month 3 means push has no coverage-gate-qualified backup in month 2. This is accepted with the following mitigations: (a) push launches in month 2 with E2 as sole qualified responder; (b) E1 is available as an informal escalation path for infrastructure-related push failures, which is the most likely failure mode; (c) E1 completes Gates 1 and 2 for push in month 2 so that Gate 3 can execute in month 3 week 1 without delay. During E1's eventual Gate 3 week, E2 is explicitly designated as infrastructure incident backup in the on-call rotation.

**The residual risk is named explicitly:** In month 2, a push incident requiring E2's full attention simultaneously with an infrastructure incident creates a gap. The mitigation is that push runs at limited traffic in month 2 (ramp-up, not full load), reducing the probability of a severe push incident. This is a real risk accepted because the alternative — pretending E1 can reliably context-switch between two simultaneous incidents — is worse.

### 2.2 Coverage Gate Process

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability verified through three sequential gates, separated in time to create checkpoints with room to fix problems — not a single pre-launch test that can only fail at the worst possible moment.

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The primary owner **does not respond to simulation questions** for the duration, but remains reachable for genuine production emergencies unrelated to the simulation. The simulation is conducted in staging and time-boxed to 2 hours, scheduled during a low-traffic period to reduce the probability of a simultaneous real incident.

If the coverage partner cannot resolve the simulated incident without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt within 3 business days. If the second attempt also fails, the channel launch is deferred.

This preserves the purpose of Gate 2 — demonstrating independent capability without hand-holding — while eliminating the operational risk of a fully unreachable engineer during a live production environment.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

**Month 4 and month 6 spot-checks:**
Spot-checks re-execute the Gate 2 simulation against the current runbook. A failed spot-check triggers:

1. **Immediate:** The coverage partner is removed from the on-call rotation for that channel. The primary owner carries solo on-call.
2. **Within 5 business days:** The coverage partner re-executes the simulation. If the second attempt passes, the coverage partner is reinstated.
3. **If the second attempt fails:** The coverage partner assignment is permanently reassigned. E1 serves as tertiary backup. The gap is documented in the monthly engineering review and escalated to engineering leadership.

Solo on-call for a primary owner is operationally worse than a channel freeze on ramp-up. We accept this as the correct consequence: the primary owner bears the cost of their coverage partner's failure to maintain competency, which creates an incentive for the primary owner to keep runbooks current and conduct meaningful cross-training rather than checkbox training.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — a standard re-verified at months 4 and 6, not assumed to persist from launch.

### 2.3 Runbook Maintenance

- **Trigger-based updates:** Any production incident requiring knowledge not in the runbook generates a mandatory runbook update before the incident is closed. This is a condition of incident closure, enforced in the post-mortem template.
- **Monthly review:** On the first Monday of each month, each primary owner reviews their runbook against the previous month's changes. The review is documented with a timestamp and change log, or an explicit "no changes required" sign-off. This sign-off is a required field in the sprint planning template — creating a visible artifact and a specific moment of accountability, not aspirational intent.
- **Coverage partner spot-checks (months 4 and 6):** Each coverage partner re-executes the Gate 2 simulation. Failed spot-checks trigger the procedure above.

---

## 3. Delivery Milestones

**The gate timing constraint:** Coverage gates require a minimum 3-week span (Gate 1 at week -2, Gate 2 at week -1, Gate 3 at week 0). A channel cannot launch and complete its coverage gates within the same calendar month unless it launches in week 1. Treating coverage gates as month 1 deliverables for a channel also being built in month 1 is not a viable schedule.

The resolution: **separate channel build from coverage gate completion.** Month 1 delivers a working in-app system. Month 2 delivers a *covered* in-app system. This is an honest representation of what 4 weeks can accomplish.

**Implication for month 