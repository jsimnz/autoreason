# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against criteria defined in Section 7.

**Four structural problems are acknowledged upfront, not papered over:**

- **The concentration assumption is the most fragile input in the model.** Every threshold calculation depends on the 90%/4-hour concentration figure, which is asserted, not measured. Section 1.1 contains a full sensitivity analysis. The primary mitigation is that the automated densification alert fires on observed data, not on concentration assumptions.
- **The spike model involves non-DAU surge that is difficult to pre-estimate.** Viral events pull in users who would not otherwise have opened the app. The corrected spike model accounts for this; the surge percentages are planning inputs, not precise forecasts, and should be recalibrated after the first spike events post-launch.
- **Default A does not reduce arrival rate.** Throttling dispatch grows queues. The tiered degradation design is honest about what each mode does and does not do, including a new Default B for sustained load between 2,650 and 4,000/sec where Default A's partial throttling is insufficient.
- **The compliance architecture decision is architectural, not a latency preference.** Building synchronous in Month 1 and retrofitting cached in Month 2 requires changing query patterns across all four dispatch paths — not adding a cache layer. Legal needs to see both options and decide by end of Week 2.

---

### Six Items Requiring Explicit Sign-Off Before This Design Is Finalized

The owner column identifies who must decide, not which engineer implements. Engineer assignments reflect actual system ownership: E1 owns core dispatch pipeline; E2 owns channel integrations (push, email, SMS); E3 owns monitoring, alerting, and infrastructure; E4 owns preference management, policy enforcement, and rate limiting.

| Item | Section | Decision Deadline | Owner (who must decide) | Implementing Engineer | Consequence of Miss |
|------|---------|-------------------|------------------------|----------------------|---------------------|
| SMS budget and 2FA enrollment rate | §1.1 | Week 2 | Product | E2 (channel infrastructure) | SMS channel sizing blocked; planning basis may be off by 4× |
| Re-engagement email send rate | §1.1 | Week 2 | Product | E2 (channel infrastructure) | SendGrid contract tier cannot be finalized |
| Opt-out compliance architecture | §2.4 | End of Week 2 | Legal | E1 (core dispatch) | Default is synchronous. Retrofitting cached after Month 1 schema work requires 1–2 engineer-weeks of rework across all four dispatch paths during the highest-velocity sprint. See §2.4 for both options. |
| SendGrid enterprise contract | §1.1 | End of Month 1 | Procurement/Finance | E2 provides technical requirements | Self-hosted fallback activates; see §6.2 for cost and timeline |
| Reassessment option selection | §1.1 | Day 3 of any reassessment | Product + Engineering leadership | E1 presents options; E3 monitors triggers | Default A activates automatically. Default A is a bridge, not a resolution. |
| Broadcast notification policy + exception gate | §1.1, §6 | Before launch | Legal + Product jointly | E4 (policy enforcement layer) | Capability split into mandatory system communications (cannot be disabled) and discretionary broadcasts (disabled until policy defined). Legal must confirm which types are mandatory. |

**On the compliance deadline:** The real risk is not latency — it is that the synchronous and cached architectures have different data access patterns across all four channel dispatch paths. The deadline is about avoiding an architectural redo during Month 2 sprint work. Legal needs to understand this framing, not a "12ms p99 penalty" framing.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

#### Scenario Framework

| Scenario | DAU/MAU | DAU | Usage in This Document |
|----------|---------|-----|----------------------|
| Low | 15% | 1.5M | Lower-bound cost modeling |
| **Base (planning basis)** | **25%** | **2.5M** | Mid-stage social app |
| High | 35% | 3.5M | Normal operation worker sizing |
| **Spike** | **35% DAU + non-DAU surge** | **3.5M + event** | **Worker ceiling and infrastructure sizing** |

**Worker ceiling sizing uses the Spike scenario.** The spike scenario is not simply High DAU plus a multiplier on existing activity — it includes non-DAU users pulled onto the platform by the event. This distinction is elaborated in the Viral Spike Model below.

---

#### Viral Spike Model

A social app's worst-case notification load is not gradual densification. It is a sudden viral spike — a post, live event, or breaking news cycle — that drives a large fraction of the user base to interact simultaneously. The notification system must handle this without shedding Tier 1 and Tier 2 traffic.

**The base rate error in naive spike modeling:** Applying a 4× multiplier to existing DAU activity alone is wrong for Type 2 and Type 4 events. A viral spike does not just intensify the behavior of users already active that day — it activates users who would not otherwise have opened the app, suddenly. The spike multiplier must be applied to a base that includes non-DAU surge.

**Spike taxonomy:**

| Spike Type | Description | Peak Multiplier vs. Normal | Non-DAU Surge | Effective Active Users at Peak | Duration |
|------------|-------------|---------------------------|---------------|-------------------------------|----------|
| Type 1: Content viral | Single post goes viral; reply/like storm | 2–3× | ~5% of remaining MAU | ~4.0M effective | 30–90 min |
| Type 2: Live event | Sports, election, product launch | 3–5× | ~15% of remaining MAU | ~4.9M effective | 2–4 hours |
| Type 3: Platform event | App feature launch, push to all users | 1.5–2× | ~8% of remaining MAU | ~4.1M effective | 4–8 hours |
| Type 4: External crisis | Breaking news drives mass activation | 4–8× | ~30% of remaining MAU | ~6.2M effective | 1–6 hours |

**Non-DAU surge methodology:** The remaining MAU pool (10M MAU minus 3.5M DAU = 6.5M non-daily users) has a subset reachable by push notification who will open the app during a sufficiently significant event. The surge percentages above are estimates derived from observed behavior on comparable social platforms. They are not precise. Non-DAU users generate fewer notifications per session (newly arriving, not deeply engaged in the graph), so per-user rate for surge users is estimated at 40–60% of the normal DAU rate. This partially offsets the volume increase.

**Planning basis for infrastructure sizing: Type 2 spike, 4× multiplier, 2-hour duration.** Type 4 spikes at 8× are real but rare and represent a failure mode, not a design target — no notification system at this scale absorbs 8× peaks gracefully without shedding non-critical load. Type 1 spikes at 2–3× are the most common and important to absorb without degradation. Type 2 at 4× is the upper boundary of what the system should handle cleanly. This is a deliberate tradeoff: we are not designing for Type 4 events. If one occurs, Default B activates immediately and stakeholder communication is triggered within 15 minutes.

**Corrected spike peak rate calculation:**

```
Normal peak rate (High scenario):
= (3,500,000 DAU × 11/DAU/day × 0.90 concentration) ÷ 14,400 seconds
= 2,406/sec

Type 2 spike — existing DAU contribution:
= (3,500,000 × 11 × 0.90 × 4×) ÷ 14,400 = 9,625/sec

Type 2 spike — non-DAU surge contribution (15% of 6.5M = 975,000 users):
= (975,000 × 11 × 0.50 × 0.90) ÷ 14,400 = 335/sec

Type 2 spike total: ~9,960/sec

Type 1 spike — existing DAU:
= (3,500,000 × 11 × 0.90 × 2.5×) ÷ 14,400 = 6,016/sec
Type 1 spike — non-DAU surge (5% of 6.5M = 325,000):
= (325,000 × 11 × 0.50 × 0.90) ÷ 14,400 = 112/sec
Type 1 spike total: ~6,128/sec
```

The non-DAU surge adds approximately 3–5% to spike peak rates. It is not the dominant factor — the activity multiplier on existing DAU is — but for Type 4 events the surge contribution becomes material (~1,400/sec additional load).

**The worker ceiling is not sized to absorb a 4× spike in full.** That would require approximately 9,600/sec sustained throughput — four times the current worker fleet — which is not economically justified for events lasting 2 hours. Instead, the design uses tiered degradation, described below.

---

#### Tiered Degradation: The Designed Response to Spikes

Default A does not reduce arrival rate. Throttling dispatch grows queues. The table below is honest about what each mode does and does not do.

| Load Level | Mode | What Actually Happens | Tier 1 + 2 Impact | Tier 3 Impact |
|------------|------|-----------------------|-------------------|---------------|
| < 2,400/sec | Normal | Full throughput on all tiers | None | None |
| 2,400–2,650/sec | Yellow alert | Reassessment trigger fires; no behavioral change | None | None |
| 2,650–3,800/sec | **Default A** | Tier 3 poll interval increased; workers process Tier 3 at ~71% normal rate; Tier 3 queue grows | None | Throughput reduced; queue grows; notifications delayed, not dropped |
| > 3,800/sec sustained 5+ min | **Default B** | Tier 3 workers suspended; Tier 3 queue grows until spike clears | None | Suspended; processed after spike |
| > 6,000/sec sustained 5+ min | Tier 2 rate-limited | Tier 2 dispatch throttled to 50% | Tier 2 delayed by minutes | Suspended |
| > 8,000/sec (Type 4) | Tier 1 only | All non-Tier-1 queued | Tier 2 queued | Queued |

**Default A** activates automatically when sustained rate exceeds 2,650/sec for more than 2 minutes. It operates within a defined time-of-day window (6pm–midnight local time, the peak usage window). Activations outside this window behave differently: the threshold for automatic activation is raised to 3,000/sec, because off-peak rate spikes are more likely to be anomalies than genuine load events. Outside-window activations are logged and page E3 for manual review rather than triggering automatically.

**Default B** activates automatically when sustained rate exceeds 3,800/sec for more than 5 minutes. No human decision required. A user whose post received 400 likes during a viral spike does not need real-time notification of each one. Batched delivery after the spike is the correct behavior. Default B activation triggers a stakeholder notification within 15 minutes.

**This is not a failure mode taxonomy. It is the designed response.** Tier 1 and Tier 2 notifications are protected at all load levels up to 6,000/sec.

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

**Batching reduction methodology:** The batching policy is:

- **Like events:** Grouped per post per user. After the first like notification is delivered, subsequent likes on the same post are batched into a summary notification delivered at most once per 30 minutes. A post receiving 50 likes in 30 minutes generates 2 delivered notifications (first like + one batch), not 50. Under a power-law distribution of engagement, this reduces total like notifications by approximately 60–70% of raw events.
- **Comment events:** Grouped per post per user. Same 30-minute batching window. Reduction approximately 40–50% of raw events (comments are less bursty than likes).
- **DMs:** Not batched. Each message delivers a notification unless the user is currently active (in-app suppression).
- **System notifications:** Not batched. Low volume; batching adds complexity without benefit.

**Post-batching effective notification rate:**

```
Like events (35% of raw): 2.6–8.1/DAU/day raw → 0.8–2.4/DAU/day after batching (70% reduction)
Comment events (20% of raw): 1.5–4.6/DAU/day raw → 0.8–2.5/DAU/day after batching (45% reduction)
DMs + follows + mentions + system (45% of raw): 3.4–10.4/DAU/day → no reduction

Post-batching total:
Low end: 0.8 + 0.8 + 3.4 = 5.0/DAU/day
High end: 2.4 + 2.5 + 10.4 = 15.3/DAU/day
```

**Revised post-batching range: 5–15/DAU/day. Planning basis: 11/DAU/day.**

The 11/DAU/day planning basis sits at the 67th percentile of the corrected range, which is appropriate — biased slightly toward higher load. If batching is less effective than assumed (e.g., the product team disables 30-minute batching for likes in favor of real-time delivery), the effective rate approaches the raw upper bound of 23/DAU/day and the worker ceiling is breached at normal High scenario load. This is a product decision with infrastructure consequences that must be communicated explicitly.

**Push + In-App volume by scenario:**

| Scenario | DAU | 5/DAU/day | 11/DAU/day | 15/DAU/day |
|----------|-----|-----------|------------|------------|
| Low | 1.5M | 7.5M | 16.5M | 22.5M |
| Base | 2.5M | 12.5M | 27.5M | 37.5M |
| High | 3.5M | 17.5M | **38.5M** | 52.5M |

**Worker sizing input: 38.5M/day (High scenario, 11/DAU/day).**

---

#### Concentration Assumption: Sensitivity Analysis

**The concentration assumption is asserted, not measured.** The 90%/4-hour window (meaning 90% of daily notifications are delivered during a 4-hour peak window) is reasonable for a US-heavy social app, but every critical threshold in this document depends on it.

**What the concentration assumption affects:**

```
Peak rate = (DAU × per-DAU-rate × concentration%) ÷ concentration_window_seconds

At High DAU (3.5M) and 11/DAU/day:
- 80% / 4-hour window: 2,139/sec
- 90% / 4-hour window: 2,406/sec  ← current assumption
- 95% / 4-hour window: 2,540/sec
- 90%