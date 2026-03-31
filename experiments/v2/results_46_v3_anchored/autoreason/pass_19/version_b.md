# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

**Known limitations acknowledged upfront:**

Four structural problems cannot be fully resolved within this design scope. They are documented with explicit mitigations, not papered over:

- **Spike model understates non-DAU surge.** The spike calculations use existing DAU as the base. Viral events pull in non-DAU users. This is corrected in Section 1.1 with a non-DAU surge adjustment, but the adjustment is itself an estimate. The correct posture is: size for the corrected estimate, monitor actual spike behavior at launch, and treat Type 4 events as requiring manual response regardless of pre-launch sizing.

- **Concentration assumption is the most fragile input in the model.** Every threshold calculation depends on the 90%/4-hour concentration figure, which is asserted, not measured. Section 1.1 contains a full sensitivity analysis. The primary mitigation is that the automated densification alert fires on observed data, not on concentration assumptions.

- **Default A activation window** is defined in Section 1.1. It is a time-of-day window, not a general mechanism. Activations outside the window behave differently and that behavior is now specified.

- **Lead time requirements** for the reassessment trigger are derived from actual provisioning timelines in Section 1.1, not assumed.

**Six items require sign-off before this design is finalized.** Implementation is distributed across all four engineers. The prior version incorrectly assigned all items to E1; the revised table corrects this.

---

### Six Items Requiring Explicit Sign-Off

| Item | Section | Decision Deadline | Owner (who must decide) | Implementing Engineer | Consequence of Miss |
|------|---------|-------------------|------------------------|----------------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E2 (channel infrastructure) | SMS channel sizing blocked; planning basis may be off by 4× |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 (channel infrastructure) | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | End of Week 2 | Legal | E1 (core dispatch) | Default is synchronous. Choosing cached after Month 1 schema work requires 1–2 engineer-weeks of rework across all four dispatch paths during the highest-velocity sprint. See §2.4 for both options described in full. |
| SendGrid enterprise contract | §1.1 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; see §6.2 for cost and timeline |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Product + Engineering leadership | E1 presents options; E3 monitors triggers | Default A activates automatically. Default A is a bridge, not a resolution. |
| Broadcast notification policy + exception gate | §1.1, §6 | Before launch | Legal + Product jointly | E4 (policy enforcement layer) | See §6 — capability is split into mandatory system communications (cannot be disabled) and discretionary broadcasts (disabled until policy defined). Legal must confirm which notification types are mandatory. |

**On engineer assignment:** E1 owns core dispatch pipeline. E2 owns channel integrations (push, email, SMS). E3 owns monitoring, alerting, and infrastructure. E4 owns preference management, policy enforcement, and rate limiting. The compliance architecture decision affects E1's schema work. The broadcast policy affects E4's enforcement layer. These are not interchangeable.

**On the compliance architecture deadline:** The real risk is not latency — it is that the synchronous and cached architectures have different data access patterns across all four channel dispatch paths. Building synchronous in Month 1 and retrofitting cached in Month 2 is not "adding a cache layer." It requires changing query patterns in every dispatch path. Legal needs to see both options (described in §2.4) and decide between them, not be told to decide quickly to avoid a millisecond penalty.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage in This Document |
|----------|---------|-----|----------------------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Normal operation worker sizing |
| **Spike** | **35% DAU + non-DAU surge** | **3.5M + surge** | **Worker ceiling and infrastructure sizing** |

**Worker ceiling sizing uses the Spike scenario.** The spike scenario is not simply High DAU plus a multiplier on existing activity — it includes non-DAU users pulled onto the platform by the event. This distinction is elaborated in the Viral Spike Model below.

---

#### Viral Spike Model

**The base rate error in the prior version:** The prior spike calculation applied a 4× multiplier to existing DAU activity (3.5M DAU × 11 notifications/DAU/day). This is wrong for Type 2 and Type 4 events. A viral spike on a 10M MAU app does not just intensify the behavior of users who were already active that day — it activates users who would not otherwise have opened the app, and it does so suddenly. The spike multiplier must be applied to a base that includes non-DAU surge, not just existing DAU.

**Corrected spike model:**

| Spike Type | Description | Peak Multiplier vs. Normal | Non-DAU Surge | Effective Active Users at Peak | Duration |
|------------|-------------|---------------------------|---------------|-------------------------------|----------|
| Type 1: Content viral | Single post goes viral; reply/like storm | 2–3× activity | ~5% of remaining MAU activated | ~4.0M effective | 30–90 min |
| Type 2: Live event | Sports, election, product launch | 3–5× activity | ~15% of remaining MAU activated | ~4.9M effective | 2–4 hours |
| Type 3: Platform event | App feature launch, push to all users | 1.5–2× activity | ~8% of remaining MAU activated | ~4.1M effective | 4–8 hours |
| Type 4: External crisis | Breaking news drives mass activation | 4–8× activity | ~30% of remaining MAU activated | ~6.2M effective | 1–6 hours |

**Non-DAU surge methodology:** The remaining MAU pool (10M MAU minus 3.5M DAU = 6.5M non-daily users) has a subset who are reachable by push notification and will open the app when a sufficiently significant event occurs. The surge percentages above (5–30% of the 6.5M non-DAU pool) are estimates derived from observed behavior on comparable social platforms during major events. They are not precise. The correct response to this uncertainty is to treat them as planning inputs, monitor actual non-DAU activation rates during the first spike events post-launch, and recalibrate.

**Non-DAU users generate fewer notifications per session** (they are newly arriving, not deeply engaged in the graph), so the per-user rate for surge users is estimated at 40–60% of the normal DAU rate. This partially offsets the volume increase.

**Corrected spike peak rate calculation:**

```
Type 2 spike (planning basis for sizing):

Existing DAU contribution:
= (3,500,000 × 11 × 0.90 × 4×) ÷ 14,400
= 9,625/sec

Non-DAU surge contribution (15% of 6.5M = 975,000 users):
= (975,000 × 11 × 0.50 × 0.90) ÷ 14,400
  [50% of normal per-user rate; same concentration window]
= 4,821,250 ÷ 14,400
= 335/sec

Type 2 spike total: ~9,960/sec

Type 1 spike (most common):
Existing DAU: (3,500,000 × 11 × 0.90 × 2.5×) ÷ 14,400 = 6,016/sec
Non-DAU surge (5% of 6.5M = 325,000): (325,000 × 11 × 0.50 × 0.90) ÷ 14,400 = 112/sec
Type 1 spike total: ~6,128/sec
```

The non-DAU surge adds approximately 3–5% to spike peak rates. This is not the dominant factor — the activity multiplier on existing DAU is — but it is not zero, and for Type 4 events the surge contribution becomes material (~1,400/sec additional load).

**Planning basis for infrastructure sizing: Type 2 spike, ~10,000/sec peak.** This is higher than the prior version's 9,624/sec but the difference is not operationally significant. The tiered degradation design remains the same; the correction matters for accuracy of the model, not for the infrastructure decision.

---

#### Concentration Assumption: Sensitivity Analysis

**The prior version treated concentration as a known input.** It is not. The 90%/4-hour window (meaning 90% of daily notifications are delivered during a 4-hour peak window) is a reasonable assumption for a US-heavy social app, but it is asserted without measurement. Every critical threshold in this document depends on it.

**What the concentration assumption affects:**

```
Peak rate = (DAU × per-DAU-rate × concentration%) ÷ concentration_window_seconds

At High DAU (3.5M) and 11/DAU/day:
- 80% / 4-hour window: (3.5M × 11 × 0.80) ÷ 14,400 = 2,139/sec
- 90% / 4-hour window: (3.5M × 11 × 0.90) ÷ 14,400 = 2,406/sec  ← current assumption
- 95% / 4-hour window: (3.5M × 11 × 0.95) ÷ 14,400 = 2,540/sec
- 90% / 3-hour window: (3.5M × 11 × 0.90) ÷ 10,800 = 3,208/sec  ← exceeds ceiling
```

**The 3-hour concentration window scenario (90%/3hr) produces a peak rate of 3,208/sec — above the 2,650/sec worker ceiling — under normal High scenario conditions, without any spike.** If the app's actual usage pattern is more concentrated than assumed (common for apps with strong push-to-open mechanics, where notifications themselves drive the peak), the system operates in Default A territory during normal peak hours.

**Sensitivity table:**

| Concentration | Window | Normal Peak (High DAU, 11/DAU) | Ceiling Breach? | Default A Trigger? |
|--------------|--------|-------------------------------|-----------------|-------------------|
| 80% | 4 hr | 2,139/sec | No | No |
| 90% | 4 hr | 2,406/sec | No | No (244/sec headroom) |
| 95% | 4 hr | 2,540/sec | No | No (110/sec headroom) |
| 90% | 3 hr | 3,208/sec | Yes | Yes — continuously |
| 95% | 3 hr | 3,387/sec | Yes | Yes — continuously |

**Mitigations for concentration uncertainty:**

1. **Measure concentration within the first two weeks of launch.** The monitoring dashboard exposes peak-hour notification volume as a time series. The actual concentration percentage and window shape are observable from production data. The 90%/4-hour assumption should be replaced with measured values by the end of Month 2.

2. **The worker ceiling is set conservatively relative to the 90%/4-hour assumption.** 244/sec headroom is not large, but the automated densification alert (described below) fires before the ceiling is breached, not after.

3. **If measured concentration shows a 3-hour window, Default A will be a steady-state condition, not an exception.** That is an acceptable operating mode — Tier 3 notifications are slightly throttled during peak — but it should be a conscious decision, not a surprise. The monitoring dashboard will surface this within days of launch.

4. **The worker ceiling can be raised by 33% (to ~3,500/sec) by adding two additional worker instances.** This is a provisioning change, not an architectural one. If concentration measurements show the 3-hour window is accurate, this change should be made before Month 3.

---

#### Push and In-App Volume

| Event Class | Estimated Events/DAU/Day | Notes |
|-------------|--------------------------|-------|
| Likes on posts | 3–8 | Batched after first delivery |
| Comments on posts | 1–4 | Batched similarly |
| New followers/friend requests | 0.5–2 | |
| Direct messages received | 2–6 | Power users skew high |
| Mentions and tags | 0.5–2 | |
| System/product notifications | 0.5–1 | Capped by product policy |

**Raw event total: 7.5–23/DAU/day.**

**Batching reduction methodology:** The prior version claimed batching reduces the upper bound from 23 to 14/DAU/day (39% reduction) without specifying the batching policy. That claim is now grounded.

The batching policy is:
- **Like events:** Grouped per post per user. After the first like notification is delivered, subsequent likes on the same post are batched into a summary notification delivered at most once per 30 minutes. A post receiving 50 likes in 30 minutes generates 2 delivered notifications (first like + one batch), not 50. Under a power-law distribution of engagement (most posts get few likes; a small number get many), this reduces total like notifications by approximately 60–70% of raw events.
- **Comment events:** Grouped per post per user. Same 30-minute batching window. Reduction approximately 40–50% of raw events (comments are less bursty than likes).
- **DMs:** Not batched. Each message delivers a notification unless the user is currently active (in-app suppression).
- **System notifications:** Not batched. Low volume; batching adds complexity without benefit.

**Post-batching effective notification rate:**

```
Raw events: 7.5–23/DAU/day

Like events (assume 35% of raw): 2.6–8.1/DAU/day raw → 0.8–2.4/DAU/day after batching (70% reduction)
Comment events (assume 20% of raw): 1.5–4.6/DAU/day raw → 0.8–2.5/DAU/day after batching (45% reduction)
DMs + follows + mentions + system (45% of raw): 3.4–10.4/DAU/day → no reduction

Post-batching total:
Low end: 0.8 + 0.8 + 3.4 = 5.0/DAU/day
High end: 2.4 + 2.5 + 10.4 = 15.3/DAU/day
```

**Revised post-batching range: 5–15/DAU/day. Planning basis: 11/DAU/day.**

The prior version's 8–14 range was directionally correct but the derivation was absent. The corrected range is slightly wider (5–15 vs. 8–14) because the methodology makes explicit that low-engagement users receive fewer notifications than the lower bound assumed, and high-engagement users (power users receiving many DMs) are not reduced by batching. The 11/DAU/day planning basis is unchanged and sits at the 67th percentile of the corrected range, which is appropriate for a planning basis (biased slightly toward higher load).

**If batching is less effective than assumed** (e.g., the product team disables 30-minute batching for likes in favor of real-time delivery), the effective rate approaches the raw upper bound of 23/DA