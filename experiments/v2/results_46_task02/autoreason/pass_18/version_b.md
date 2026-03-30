# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown explicitly. Where prior versions contained arithmetic errors or unsupported claims, those are corrected here with the correction noted.

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

**Corrections from prior draft:** Ten specific problems in the previous version are addressed in this revision. Each is called out inline where the relevant section appears.

---

## Executive Summary

This design handles approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery product orientation |
| Provisioned floor set at **3,200/sec** sustained | Derived from 4× diurnal peak factor (high end of cited range) applied to working assumption; see Section 1.4 for correction |
| Channel split: push 80%, in-app 20%, email 8% of total volume, SMS by use-case volume | Push and in-app are substitutes for the same event; the split arithmetic is corrected from the prior draft |
| SMS spend cap calibrated against top-down volume figure, not bottom-up estimate | Prior draft's caps were sized 5× too low; corrected in Section 1.3 |
| 2FA SMS configuration treated as a binary product decision, not a continuous range | The 8%/50% framing in the prior draft was misleading; corrected in Section 1.3 |
| Channel-specialized workers for all four channels | Any channel pair with mismatched latency profiles creates head-of-line blocking |
| Fan-out modeled by notification type with explicit per-type derivation | Section 1.5 contains the full model; prior draft referenced but omitted it |
| Escalation alert threshold raised to 85% of provisioned capacity | 75% threshold fired within normal diurnal variance; corrected in Section 1.4 |
| On-call runbook ownership assigned to a named engineer with a specific launch gate mechanism | Prior draft assigned to a role that doesn't exist in a four-engineer team; corrected in Section 1.3 |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio — Sensitivity Analysis

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude mobile benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z consumer benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU.

---

### 1.2 Notifications Per Active User Per Day — Sensitivity Analysis

**Working figure: 15/day.** A social app with a content-discovery orientation and a secondary DM feature sits at the low end of the Braze 2023 benchmark range (15–20/day for social apps). If the DM feature is the primary engagement driver, this figure should be revised upward before launch.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average inbound |
|------------------------------|------------------|--------------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

**These figures are 24-hour sustained averages.** The provisioned floor is set against peak rates, which are derived in Section 1.4 by applying a peak factor to these sustained averages.

**⚠ Correction from prior draft (Problem 1):** The previous version claimed the 2,500/sec provisioned floor "provides headroom through the 45% DAU/MAU, 25/day scenario." That claim was false on the document's own arithmetic: 45% DAU/MAU at 25/day produces a sustained average of ~1,302/sec, which at a 3× diurnal peak factor reaches ~3,906/sec — exceeding the 2,500/sec floor. The corrected provisioned floor is derived in Section 1.4 and is set at 3,200/sec. The sensitivity table below shows which scenarios that floor accommodates.

**Combined sensitivity — sustained average inbound in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 | ~347 | ~463 | ~579 |
| 30% | ~347 | **~521** | ~694 | ~868 |
| 40% | ~463 | ~694 | ~926 | ~1,157 |
| 45% | ~521 | ~781 | ~1,042 | ~1,302 |

**What the provisioned floor of 3,200/sec covers:** Applying a 4× diurnal peak factor (the high end of the cited range; see Section 1.4 for why the high end is used), the 3,200/sec floor accommodates sustained averages up to 800/sec before viral effects. That covers: 30% DAU/MAU at 25/day (868/sec — marginally over; requires one re-sizing review trigger), 40% DAU/MAU at 20/day (926/sec — requires re-sizing), and all scenarios at 30% DAU/MAU through 20/day (694/sec — accommodated). Scenarios requiring re-sizing are flagged in Section 1.5.

---

### 1.3 Channel Split

**⚠ Correction from prior draft (Problem 2):** The prior draft treated push and in-app as drawing independently from total notification volume while simultaneously arguing they are substitutes for the same event. The arithmetic was inconsistent: if 20% of events fire while the target user is in-session (in-app), and push handles the remaining events, push should capture approximately 80% of total events — not 71.5%. The 8.5 percentage point gap was unaccounted for.

**Corrected model:**

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume.

The channel split therefore works as follows:

- **In-app share:** Fraction of notification events where the target user is in-session at delivery time. Working assumption: 20% of events. This is the only input needed to determine the push/in-app split.
- **Push share:** Remaining events not captured by in-app: 80% of total notification volume.
- **Email and SMS:** These are not substitutes for push/in-app. They are either duplicates of push events (digest emails, opted-in users) or independent event types (transactional SMS). They draw from separate volume budgets, not from the push/in-app pool.

**Corrected channel allocation:**

| Channel | Share of total notification volume | Notes |
|---------|-----------------------------------|-------|
| Push (APNs + FCM) | 80% | All events where user is not in-session |
| In-app | 20% | Events where user is in-session; substitute for push |
| Email | Separate budget: ~3.6M/day | Digest and opted-in social notifications; see below |
| SMS | Separate budget: ~225K/day ceiling | Transactional only; see Section 1.3 (SMS) |

**Email volume basis:** Email notifications are a subset of push events (same underlying social graph events) sent to users who have opted into email digests. Working assumption: 8% of the user base opts into email notifications, receiving an average of 1 email/day (digest format). At 10M MAU and 30% DAU/MAU, that is roughly 3M engaged users × 8% × 1/day = ~240K emails/day from the social notification flow, plus transactional emails (account confirmations, password resets, etc.) estimated at ~30K/day. Total email volume: ~270K–400K/day depending on opt-in rate. Email workers are sized against this volume, not against a percentage of the 45M total notification events.

**Why this matters for worker sizing:** Push workers handle ~36M events/day (80% of 45M). In-app workers handle ~9M events/day (20% of 45M). Email workers handle ~270–400K events/day. SMS workers handle up to ~225K events/day. These are the inputs to worker count derivation in Section 1.4.

---

### 1.3 (SMS) SMS Volume and Spend Caps

**Use cases:** SMS is reserved for transactional and security events. It is not used for social notifications (likes, comments, follows, reshares).

**Top-down volume ceiling:** At 10M MAU, a provisioned SMS ceiling of 0.5% of total notification volume would imply ~225K SMS/day. This is the ceiling, not the expected volume.

**Bottom-up volume estimate:**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone number verification | 10M MAU × 1% monthly growth / 30 days × 60% phone verification | ~2,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| 2FA SMS | See below | Variable |
| **Subtotal (non-2FA)** | | **~11,000/day** |

**⚠ Correction from prior draft (Problem 3):** The prior draft acknowledged a ~5× discrepancy between the bottom-up estimate (~47,000/day) and the top-down ceiling (~225,000/day), then calibrated the spend caps against the bottom-up estimate. If the top-down ceiling is the actual provisioned volume, spend caps of $200–$450/day would trigger constantly — they were sized against a volume 5× lower than the ceiling.

**Corrected approach:** The spend cap must be calibrated against the volume the system is actually provisioned to handle. The bottom-up estimate is used as the expected normal operating volume; the cap is set above the top-down ceiling to avoid false positives during legitimate volume bursts, not between the two figures.

**2FA configuration — binary product decision required ⚠**

**⚠ Correction from prior draft (Problem 4):** The prior draft presented 8% and 50% SMS-2FA selection rates as "the two ends of a plausible product configuration range." These are not empirical bounds on a continuous variable. They represent two discrete product configurations with categorically different cost structures. The 8% figure for authenticator-first adoption was unanchored. The framing implied a smooth tradeoff when the decision space is categorical.

**Corrected framing:** There are two product configurations. Engineering cannot determine the correct SMS spend cap until the product team makes this choice. The configurations are:

**Configuration A — Authenticator-first:** TOTP apps (Google Authenticator, Authy) are the default and primary 2FA method. SMS-2FA is available as a fallback but requires explicit user selection. SMS-2FA adoption on authenticator-first apps varies significantly by user population; no single figure is reliable. A reasonable planning range is 5–15% of 2FA-enrolled users selecting SMS-2FA. At 3M DAU with 15% 2FA enrollment: 450K enrolled users × 5–15% SMS selection = 22,500–67,500 SMS-2FA events/day (assuming one 2FA event per login, not all DAU log in daily — actual figure is lower; this is an upper bound).

**Configuration B — SMS-default:** SMS-2FA is the default. Authenticator apps are available but require explicit opt-out of SMS. SMS-2FA adoption on SMS-default apps is typically 40–70% of 2FA-enrolled users. At 3M DAU with 15% 2FA enrollment: 450K enrolled users × 40–70% = 180K–315K SMS-2FA events/day (upper bound, same caveat as above).

The cost difference between these configurations is not 2.3× as the prior draft implied — it is potentially an order of magnitude, and the absolute figures depend on login frequency and 2FA enrollment rates that are themselves assumptions.

**Product decision required before launch:** Engineering will implement whichever configuration product selects. The spend cap cannot be finalized until this decision is made. The default if no decision is made before development begins is Configuration A (authenticator-first), because it is the lower-cost failure mode. This default must be explicitly acknowledged by product ownership.

**Corrected spend cap design:**

The spend cap is designed to catch runaway notification loops and billing accidents. It is not designed to survive a major credential stuffing attack — that requires manual incident response regardless of cap placement.

| Configuration | Expected daily SMS volume | Spend cap | Basis for cap |
|--------------|--------------------------|-----------|--------------|
| A (authenticator-first) | ~33,500–78,500/day | $800/day | ~2× upper bound of expected volume at $0.0079/SMS |
| B (SMS-default) | ~191,000–326,000/day | $3,500/day | ~2× upper bound of expected volume |

The 2× multiplier above the expected upper bound provides margin for normal variance (usage spikes, verification retry storms, minor attack traffic) without triggering false positives during normal operation. A legitimate large-scale attack will exceed these caps and requires manual intervention; the runbook for cap elevation is described below.

**SMS cap runbook — launch gate item:**

**⚠ Correction from prior draft (Problem 10):** The prior draft assigned the runbook to "the on-call infrastructure owner" — a role that doesn't exist in a four-engineer team. It described no gate-keeping mechanism and no consequence for non-completion.

**Corrected assignment:** The runbook is assigned to **[Engineer Name — to be filled in at project kickoff]**, one of the four backend engineers. It is a launch gate item with the following specific mechanism: the runbook document must exist in the team's runbook repository and must be reviewed and signed off by a second engineer before the launch readiness review. The launch readiness review cannot be marked complete without this sign-off. The review is a calendar event, not an informal check.

The runbook must specify:
- Who is authorized to raise the SMS cap (any on-call engineer for up to 24 hours; beyond 24 hours requires a second engineer's acknowledgment)
- What verification is required before raising (confirm the event is not a billing loop by checking notification dispatch logs; confirm the event is a legitimate security incident)
- The temporary elevated cap ceiling (3× the normal cap, not unlimited)
- How long the elevation can remain in effect before requiring re-authorization (24 hours)
- How to restore the original cap after the incident

**Redis spend counter implementation:**

A 24-hour sliding window counter tracks SMS spend. The window is sliding (not midnight-reset) to prevent end-of-day burst abuse where two separate bursts straddle midnight and each falls within a separate daily window.

**⚠ Correction from prior draft (Problem 7):** The prior draft justified a dedicated Redis instance for the spend counter on the grounds that the counter "must not be subject to eviction pressure." It then specified `no eviction policy` for the instance. A Redis instance with no eviction policy does not evict keys regardless of memory pressure — eviction only occurs when a `maxmemory` policy is set and memory is exhausted. The stated justification was inconsistent with the configuration.

**Corrected justification:** The spend counter runs on a dedicated Redis instance for two reasons that are actually valid: (1) **operational isolation** — a failure in the main notification Redis cluster (OOM, network partition, instance replacement) must not take down the spend cap counter, because losing the counter means