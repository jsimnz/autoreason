# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single queue with channel fanout. This prevents FCM backpressure during upstream degradation from blocking email and in-app delivery. The tradeoff is higher operational complexity (four queues instead of one) and a shared classifier that becomes a cross-channel dependency requiring its own reliability treatment — both are analyzed explicitly below.

Every tradeoff is named. Where we accept risk, we specify the mitigation and its limits. Where we defer complexity, we state the measurable trigger for revisiting. Where the critic identified real problems in the prior draft, we address them directly rather than papering over them.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations — push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

**On peak throughput:** If morning and evening peaks each occupy 2-hour windows and together account for 60% of daily volume, the actual sustained throughput during those windows is:

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained during peak windows**

We apply a 50% intra-window headroom buffer for momentary spikes within the peak window:

2,125 × 1.5 = **~3,190/sec design ceiling**

**Push opt-in rate uncertainty:** The prior draft treated 70% push opt-in as a known input. It is not. Published data for social apps ranges from 40–60%; 70% represents an optimistic scenario. Because the design ceiling calculation is sensitive to this input, we run three scenarios:

| Opt-in Rate | Push-Eligible Users | Push Volume/Day (target) | Total/Day (target) | Peak Sustained (target) |
|-------------|--------------------|--------------------------|--------------------|------------------------|
| 45% (conservative) | 4.5M | 22.5M | 38.5M | ~1,604/sec |
| 60% (base case) | 6M | 30M | 46M | ~1,917/sec |
| 70% (optimistic) | 7M | 35M | 51M | ~2,125/sec |

**We size infrastructure to the optimistic scenario (3,190/sec design ceiling) and validate against actuals in month 2.** The conservative scenario is not a reason to under-build; it is a reason to treat the traffic model as a living document with a mandatory month 2 review. If actuals fall in the conservative range, we publish revised sizing and reduce over-provisioning. If actuals exceed the optimistic scenario, we have a capacity problem to solve.

The sensitivity analysis also affects the SMS budget (Section 1.1a): lower push volume means fewer P0 SMS fallback events, so the budget impact is directionally favorable under conservative opt-in rates.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 4.5M–7M | 45–70% opt-in; base case 6M |
| Push/push-eligible user/day | ~3 (launch), ~5 (target) | Conservative at launch; ramp gated on opt-out data |
| **Push volume/day (target, base)** | **~30M** | 6M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional |
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback analyzed in 1.1a |
| **Total/day (launch, base)** | **~34M** | Sum at launch frequency, base opt-in |
| **Total/day (target, optimistic)** | **~51M** | Sum at target frequency, optimistic opt-in |
| **Design ceiling** | **~3,190/sec** | Sized to optimistic scenario |

### 1.1a SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225,000/month. Restricting SMS to auth and security events brings this to 50,000/day × $0.0075 × 30 = **$11,250/month**.

**P0 SMS fallback budget:** P0 SMS fallback for failed push deliveries creates a second cost pathway. P0 notifications are defined as account security events, direct messages from persistent connections, and service alerts affecting the user's account. Estimated P0 volume: ~2% of push volume.

**The 2% push failure rate assumption is a planning input, not a known quantity.** Early push implementations commonly see 5–10% failure rates before infrastructure matures. We therefore model three failure rate scenarios:

| Push Failure Rate | P0 Push Volume/Day | P0 SMS Fallback/Day | Monthly Cost |
|-------------------|--------------------|---------------------|-------------|
| 2% (optimistic) | ~600K | ~12,000 | ~$270 |
| 5% (realistic early) | ~600K | ~30,000 | ~$675 |
| 10% (poor early impl.) | ~600K | ~60,000 | ~$1,350 |

*(P0 push volume at base opt-in: 30M × 0.02 = 600K/day)*

Combined SMS ceiling across all scenarios is well under $15,000/month. The hard cap of $15,000 is configured in Twilio's spend controls with on-call alerts at 80% of cap. If the cap is reached, P0 SMS fallback is suspended (push retry continues) and the incident is escalated as P1.

**Gate enforcement and the race condition fix:** The prior draft's spend counter check had a race condition: multiple workers reading the counter simultaneously before any write commits could allow spend to exceed the cap before the check catches it. This is addressed with an atomic Redis counter using `INCR` with a compare-and-cap pattern:

```
result = redis.eval("""
  local current = redis.call('GET', KEYS[1]) or 0
  if tonumber(current) >= tonumber(ARGV[1]) then
    return -1  -- cap exceeded, do not dispatch
  end
  return redis.call('INCR', KEYS[1])
""", keys=[monthly_sms_counter], args=[cap_in_messages])

if result == -1:
    suppress_and_log()
else:
    dispatch_sms()
```

The Lua script executes atomically on the Redis instance. A single Redis node is the counter authority; the risk is Redis unavailability causing the counter to be bypassed. If Redis is unavailable, the dispatcher fails closed: SMS is suppressed rather than dispatched without a counter check. This is the correct failure mode — we prefer missed SMS over uncapped spend.

The $15,000 monthly cap translates to approximately 2,000,000 messages. The counter is keyed by calendar month and reset at month boundary.

**Gate enforcement** is implemented in the channel dispatcher with two independent gates:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted for any notification type, but only after push retry exhaustion (3 attempts with exponential backoff over 90 seconds). The fallback gate executes the atomic counter check before dispatching.

**Emergency allowlist approval:** The prior draft required approval from the on-call engineer and the engineer's manager within 30 minutes. With 4 engineers, the manager may be one of the 4, creating self-approval ambiguity. If the manager is traveling or in an incompatible time zone, the process stalls.

Revised approval chain:
- **Primary approvers:** Any two engineers who are not the change author. With 4 engineers, this is always satisfiable as long as the author is not the only engineer available.
- **If only the author is available:** The change is blocked. SMS allowlist additions are not authorized under single-engineer availability. The incident is escalated to the VP of Engineering or equivalent, who has explicit authority to authorize emergency SMS routing outside the normal gate.
- **Manager approval is not required** for the emergency path. Manager awareness is required — the on-call engineer pages the manager for awareness, not approval. This removes the manager-unavailability stall while preserving oversight.
- **Self-approval is explicitly prohibited** in the allowlist configuration tooling, which requires the approving engineer's identity to differ from the submitting engineer's identity. This is enforced in code, not policy.
- All emergency additions are reviewed in the next business day's standup regardless of outcome.

---

## 2. Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** The coverage system exists to ensure that any single engineer's unavailability does not leave a channel without a competent responder. The prior draft had two problems with this system: the Gate 2 simulation made the primary owner deliberately unavailable during a business day without analyzing the operational risk of doing so, and the month 4/6 spot-check standard was lower than the initial launch standard in a way that created perverse incentives. Both are addressed below.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Coverage pairing rationale:** Linear rather than circular. If E4 is unavailable, E2 covering email/SMS leaves push uncovered while E2 handles the email incident. The linear structure resolves this: E1 covers push when E2 is unavailable (E1 has no channel primary of their own), E3 covers email/SMS when E4 is unavailable, E4 covers in-app when E3 is unavailable, E2 covers infrastructure when E1 is unavailable. E1 is tertiary backup for all channels when both primary and coverage partner are simultaneously unavailable.

### 2.1 E1's Dual-Role Conflict

E1 owns the most critical component (queue infrastructure) and serves as push coverage partner. The prior draft called this "a one-week conflict" and accepted the residual risk. The critic correctly identified that "E2 pages E1 while E1 is simultaneously handling a push incident" is not a documented escalation path — it is hoping two incidents don't overlap.

**The honest assessment:** With 4 engineers, there is no staffing solution that eliminates this conflict. The options are:

1. **Accept the conflict with explicit escalation rules** (prior draft approach — understated the risk)
2. **Delay E1's Gate 3 push coverage until month 3**, after infrastructure has been running stably for two months rather than one
3. **Separate the roles**: assign push coverage to E4 instead of E1, accepting that E4 would be covering two channels (email/SMS primary + push backup) while E3 covers in-app

**We choose option 2.** Delaying E1's Gate 3 push coverage to month 3 means push has no coverage-gate-qualified backup in month 2. This is accepted with the following mitigations: (a) push launches in month 2 with E2 as sole qualified responder; (b) E1 is available as an informal escalation path for infrastructure-related push failures, which is the most likely failure mode; (c) E1 completes Gate 1 and Gate 2 for push in month 2 so that Gate 3 can be executed in month 3 week 1 without delay.

**The residual risk is named explicitly:** In month 2, a push incident requiring E2's full attention simultaneously with an infrastructure incident creates a gap. The mitigation is that push is at limited traffic in month 2 (ramp-up, not full load), reducing the probability of a severe push incident. This is a real risk accepted because the alternative — pretending E1 can reliably context-switch between two simultaneous incidents — is worse.

### 2.2 Coverage Gate Process

**Addressing the Gate 2 deliberate unavailability problem:** The prior draft required the primary owner to be "unavailable for the duration" of Gate 2. With 4 engineers, making any engineer fully unreachable during a business day creates operational risk. The rest of the system doesn't pause during a simulation.

**Revised Gate 2 protocol:** The primary owner is **not paged and does not respond to simulation questions**, but is reachable for genuine production emergencies unrelated to the simulation. The simulation is conducted in a staging environment. The distinction is:

- The coverage partner cannot ask the primary owner how to handle the simulated incident
- If a real production incident occurs during the simulation window, the primary owner is available to respond to that incident; the simulation is paused and rescheduled
- The simulation window is time-boxed to 2 hours and scheduled during a low-traffic period (early morning or weekend) to reduce the probability of a simultaneous real incident

This maintains the purpose of Gate 2 (demonstrating independent capability without hand-holding) while eliminating the operational risk of a fully unreachable engineer.

**Addressing the asymmetric standard problem:** The prior draft applied a higher standard for initial launch (failed Gate 2 → channel launch deferred) than for ongoing operation (failed month 4/6 spot-check → channel freeze on ramp-up only, channel continues operating). A coverage partner who cannot demonstrate competency is still on-call for existing traffic. This is not acceptable.

**Revised spot-check failure consequence:** A failed month 4 or month 6 spot-check triggers:

1. **Immediate**: The coverage partner is removed from the on-call rotation for that channel. The primary owner carries solo on-call.
2. **Within 5 business days**: The coverage partner re-executes the simulation. If the second attempt passes, the coverage partner is reinstated to the rotation.
3. **If the second attempt fails**: The coverage partner swap is made permanent — the coverage partner for that channel is reassigned to a different engineer (specifically, E1 for any channel, as tertiary backup). The original coverage partner's assignment is documented as a known gap in the monthly engineering review. This is escalated to engineering leadership.

Solo on-call for a primary owner is operationally worse than a channel freeze on ramp-up. We accept this as the correct consequence: the primary owner bears the cost of their coverage partner's failure to maintain competency, which creates an incentive for the primary owner to keep runbooks current and conduct meaningful cross-training rather than checkbox training.

**What "coverage partner" means operationally:**

**Gate 1 — Runbook quality review (2 weeks before channel launch):**
The coverage partner attempts to execute every runbook step in staging without asking the primary owner for clarification. Steps requiring clarification are flagged as incomplete. The runbook is rewritten and re-reviewed until the coverage partner can execute it independently. Standard: written for a competent backend engineer unfamiliar with the system. If Gate 1 is not passed 1 week before the scheduled launch date, the launch is deferred — not the gate.

**Gate 2 — Independent incident simulation (1 week before channel launch):**
The coverage partner independently handles a simulated incident in staging. The primary owner does not respond to simulation questions for the duration (2-hour window, scheduled during low-traffic period). The primary owner is reachable for real production emergencies unrelated to the simulation. If the coverage partner cannot resolve the simulated incident without contacting the primary owner, the simulation fails. A failed simulation triggers a runbook update and a second attempt within 3 business days. If the second attempt also fails, the channel launch is deferred.

**Gate 3 — Solo on-call rotation (first week of channel operation):**
The coverage partner carries solo on-call for the first week of channel operation. Problems surfaced during solo on-call are fixed before the channel reaches full traffic.

### 2.3 Runbook Maintenance

**Addressing the sprint template enforcement problem:** The prior draft enforced monthly runbook review via a "required field in the sprint planning template." The critic correctly identified this as process theater —