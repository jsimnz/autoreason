# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~37M notifications/day at launch (scaling to ~51–61M at target frequency) across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural decision: **per-channel queues with a shared priority classifier**, rather than a single logical queue with per-channel consumer pools. With a single queue and separate consumer pools, a FCM backpressure event that exhausts push consumers creates pressure to borrow from other pools—a decision made under incident stress that collapses the isolation you thought you had. Separate queues make isolation a structural property rather than an operational discipline. The tradeoff is higher operational complexity (four queues instead of one); the benefit is that channel isolation cannot be accidentally violated.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Two modeling errors to avoid upfront. First, different channels have different eligible populations—push reaches installed-app users regardless of daily activity; in-app only reaches logged-in users. Using DAU as the denominator for all channels produces wrong numbers. Second, naive peak throughput calculations distribute daily volume evenly across 24 hours. Traffic is concentrated in windows, and the design must account for that.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio—see §1.1a for sensitivity analysis |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~3 (launch), ~5 (target) | Conservative at launch; ramp gated on opt-out data |
| **Push volume/day** | **~21M (launch), ~35M (target)** | 7M × 3 / 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M (30% ratio), ~25M (50% ratio)** | See §1.1a |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K baseline** | Auth and security only; P0 fallback analyzed in §1.1c |
| **Total/day (launch, 30% ratio)** | **~37M** | Sum across channels at launch frequency |
| **Total/day (target, 30% ratio)** | **~51M** | Sum across channels at target frequency |
| **Total/day (target, 50% ratio)** | **~61M** | High-engagement scenario; see §1.1a |

These are estimates. We instrument from day one and publish a traffic model review in month 2 with actuals. Section 1.1a specifies exactly what gets re-provisioned if actuals diverge materially.

---

### 1.1a DAU/MAU Ratio Sensitivity Analysis

The 30% DAU/MAU ratio is the single assumption doing the most work in this model. A messaging-first app and a photo-sharing app have meaningfully different ratios—industry data shows 20–55% across social app categories. We cannot know our ratio before launch. This section bounds the error and states the provisioning response for each scenario.

**Why 30% as the planning baseline:** We use 30% because it is the conservative end of the range for social apps with active engagement loops. A lower ratio is possible for more passive consumption apps; we are not building one. If we are wrong low, we over-provision in-app capacity—a recoverable error. If we are wrong high, we under-provision—the more dangerous error, which is why we model it explicitly.

**Sensitivity table:**

| DAU/MAU ratio | DAU | In-app volume/day | Total/day (target) | Infrastructure delta vs. baseline |
|---------------|-----|-------------------|--------------------|----------------------------------|
| 20% | 2M | 10M | 46M | Under-provisioned; in-app consumers can be reduced |
| **30% (baseline)** | **3M** | **15M** | **51M** | **Design baseline** |
| 40% | 4M | 20M | 56M | In-app queue consumers scaled up ~33%; WebSocket connection pool expanded |
| 50% | 5M | 25M | 61M | In-app consumers scaled up ~67%; WebSocket pool expanded; sustained peak rate increases ~20% |

**Provisioning response by scenario:**

The in-app channel is the only one materially affected by DAU/MAU variation—push volume is bounded by push-eligible users (7M), email is not DAU-driven, and SMS is restricted by policy.

- **20–30% ratio:** Baseline provisioning. No action.
- **30–40% ratio:** Add in-app consumer instances to the existing queue. This is a configuration change, not an architectural one. Target: completed within 5 business days of month 2 traffic review confirming the ratio.
- **40–50% ratio:** Scale in-app consumers and expand the WebSocket connection pool. If sustained peak rate exceeds 2,500/sec (our 20% headroom above the baseline ceiling), re-evaluate the burst multiplier. Target: architectural review within 2 weeks of month 2 traffic review, provisioning changes deployed within 4 weeks.
- **Above 50% ratio:** Outside our modeled range. Trigger a full traffic model review immediately; do not apply the scaling rules above without re-deriving the model.

**Month 2 traffic review deliverables:** The review is not complete until it produces (1) the measured DAU/MAU ratio with confidence interval, (2) a determination of which provisioning scenario applies, (3) a concrete infrastructure change list with owner and deadline if the ratio exceeds 30%, and (4) a revised peak throughput calculation if the ratio exceeds 40%. A review that produces "the ratio looks about right" without these deliverables is not a review—it is a reassurance.

---

### 1.1b Peak Throughput Calculation

The daily volume figures above are inputs. The design ceiling requires a separate derivation.

**Step 1: Identify the peak window.** Morning and evening peaks each occupy approximately 2 hours and together account for approximately 60% of daily volume across a 4-hour window. This is an assumption we will validate in month 2. The 4-hour window and 60% concentration are planning inputs, not validated measurements.

**Step 2: Calculate sustained throughput within the peak window.**

51M × 0.60 / (4 hours × 3,600 sec/hour) = **~2,125/sec sustained**

This is the average rate within the peak window—already elevated above the daily average of ~590/sec.

**Step 3: Determine the burst multiplier.** The burst multiplier serves one purpose: handling momentary intra-window spikes from viral events. It does not address traffic model error—that is handled by the DAU/MAU sensitivity analysis and the month 2 review process. Conflating the two produces a multiplier doing double duty without being sized for either job specifically.

For viral spike sizing, we need an estimate of how much a viral event concentrates traffic. On a 10M MAU social app, a viral post or breaking social event can produce notification bursts concentrated in 30–60 seconds. Based on published incident reports from comparable-scale systems, viral spikes produce 3–5× the window average for short durations. We use **3× as the burst ceiling**—grounded in the specific scenario rather than general conservatism.

**Design ceiling: ~6,400/sec instantaneous, 2,125/sec sustained.**

This is higher than a naive 2× multiplier would produce. The difference matters: if we load-tested to a 2× ceiling and declared success, we would have tested to a number that doesn't cover the scenario it was supposed to cover. We validate both ceilings in month 5 load testing.

**What happens if month 2 data shows the peak window is 2 hours, not 4:** The sustained peak rate roughly doubles to ~4,250/sec. This triggers the 40–50% ratio provisioning response (queue consumer scaling) plus a re-evaluation of the burst ceiling. The month 2 review explicitly checks peak window concentration, not just daily volume totals.

---

### 1.1c SMS Budget Analysis

At Twilio's volume pricing (~$0.0075/message), unrestricted SMS would be an existential budget problem. We restrict SMS to two categories:

**Category 1 — Auth and security (primary channel):** OTP, password reset, suspicious login alerts. 50,000/day × $0.0075 × 30 = **$11,250/month**. These are never suppressed by budget gates. This is a fixed cost of operating the app securely.

**Category 2 — P0 push fallback:** SMS sent when push delivery fails after retry exhaustion for P0-classified notifications.

P0 fallback cost depends on two independent uncertain inputs: P0 volume and push failure rate. Both must be varied simultaneously.

**P0 volume uncertainty:**
- **Low (1%):** Moderate DM activity; security events are rare.
- **Baseline (2%):** Moderate engagement, typical security event rate.
- **High (5%):** High DM volume, active user base, higher security event rate. This is plausible for a social app with active messaging—not an edge case.

**Push failure rate uncertainty:** Token staleness (uninstalled apps, inactive users): 5–15%; device-state failures: 3–8%; FCM/APNs errors: <1%. We use 10% as baseline, 20% for stress.

**Full sensitivity matrix:**

| P0 volume | Push failure rate | P0 SMS fallback/day | Monthly cost (fallback only) |
|-----------|-----------------|---------------------|------------------------------|
| 1% (210K/day) | 5% | 10,500 | $2,363 |
| 1% (210K/day) | 10% | 21,000 | $4,725 |
| 1% (210K/day) | 20% | 42,000 | $9,450 |
| **2% (420K/day)** | **10%** | **42,000** | **$9,450** |
| 2% (420K/day) | 20% | 84,000 | $18,900 |
| 5% (1.05M/day) | 10% | 105,000 | $23,625 |
| **5% (1.05M/day)** | **20%** | **210,000** | **$47,250** |

The 5% P0 volume / 20% failure rate scenario produces $47,250/month in fallback costs alone, plus $11,250 for auth/security = **$58,500/month total**. This is not a tail-risk scenario; it is reachable under normal operational parameters.

**What this means for a hard-cap approach:** A hard cap with security-notification suppression as the enforcement mechanism is not an acceptable design when the cap can be breached by ordinary operational parameters. We replace it with a tiered escalation structure that never suppresses security-critical notifications automatically.

**Tiered response:**

- **Tier 1 — Auth/security SMS:** Unconditionally delivered. Exempt from all budget gates. Fixed cost: $11,250/month.
- **Tier 2 — P0 DM and service alert fallback:** Budget-gated with escalation, not suppression. When monthly P0 fallback spend exceeds $15,000, the system pages on-call engineering. When it exceeds $25,000, it escalates to engineering leadership. At no point are P0 DM or service alert notifications suppressed without an explicit human decision. The on-call engineer has three options: (1) investigate and remediate the underlying push failure rate, (2) explicitly approve continued spend with a stated ceiling, or (3) reclassify some notification types from P0 to P1, removing their SMS fallback eligibility. Option 3 is a product decision requiring product owner sign-off.

**Budget ceiling for planning:** $25,000/month operational target, with no automated hard cap on security-critical notifications. Automated suppression of security notifications based on a spend counter is a security control failure. The ceiling is enforced through human escalation.

**Month 2 action:** Measure actual P0 volume as a fraction of push volume. If it exceeds 3%, initiate a P0 classification review—the definition may be too broad, or the product needs to accept higher SMS spend.

**Gate enforcement** in the channel dispatcher:

1. **Type gate:** Only notification types on the auth/security allowlist may route to SMS as primary channel. The allowlist is a versioned configuration file requiring two-engineer PR review to modify.
2. **Fallback gate:** P0 SMS fallback is permitted after push retry exhaustion (3 attempts with exponential backoff over 90 seconds). Auth/security notifications bypass the fallback gate entirely.

**Escalation path for urgent allowlist additions:** Any engineer may open a draft PR with the `sms-allowlist-emergency` label. The on-call engineer and the engineer's manager are paged immediately. If both approve within 30 minutes, the change is merged and deployed without the standard review cycle. All emergency additions are reviewed in the next business day's standup.

---

## 2. Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** Cross-training in the sense of watching someone else work does not constitute coverage ability. The mitigation is structured coverage ownership with demonstrated capability, documented runbooks, and a runbook maintenance process that continues through month 6.

### 2.1 Notification Type Taxonomy

The taxonomy is a hard prerequisite for P0/P1/P2 classification (Section 4), SMS gate enforcement (§1.1c), and channel routing logic. Every downstream component is blocked on it, which makes it both the highest-priority week 1 deliverable and the highest-risk one to get wrong.

**The taxonomy is a week 1 team exercise, not a single-engineer task.** All four engineers participate in a structured working session on day 1 (2–3 hours) to enumerate notification types and surface classification disagreements. E1 owns synthesis and documentation. E2, E3, and E4 each contribute their channel-specific perspective: E2 on push delivery constraints that affect priority, E3 on preference management implications, E4 on SMS eligibility boundaries. The structural ambiguity below is resolved in this session, not deferred.

**Resolution of the structural ambiguity — priority vs. fallback eligibility:** `notification_priority` (P0/P1/P2) and `sms_fallback_eligible` (boolean) are **separate fields**, decided on day 1 and not revisited without a formal design review. The reason: priority and fallback eligibility have different stakeholders (engineering vs. product/budget) and different change cadences. Coupling them into a single field creates a governance problem—a product decision to promote a notification type to P0 automatically changes its SMS fallback behavior, which has budget implications that may not have been reviewed. Separate fields make each decision independently governable.

**Failure modes and escalation:**

- *Classification disagreements:* E1, E2, and E3 have 48 hours to resolve in a synchronous working session. If unresolved, the engineering lead makes a binding decision. Disputes affecting fewer than 5% of notification types do not block implementation—those types are temporarily classified as P2 and reclassified next sprint.
- *P0 classification disputes:* Because P0 directly gates SMS fallback logic, any unresolved P0 dispute blocks implementation immediately and is escalated to the engineering lead within 48 hours.
- *Timeline:* If week 1 ends without a merged taxonomy, the month 1 timeline slips by one week and the engineering lead is notified.

---

### 2.2 Engineer Assignments

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E1 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E4 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E3 |

**Coverage chain:** E1 covers push when E2 is unavailable. E3 covers email/SMS when E4 is unavailable. E4 covers in-app when E3 is unavailable. E2 covers infrastructure when E1 is unavailable. E1 serves as tertiary backup for all channels when both primary and coverage partner are simultaneously