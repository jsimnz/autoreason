# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown explicitly. Where assumptions carry material uncertainty, they are marked ⚠ and the consequences of being wrong are shown arithmetically.

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

---

## Executive Summary

This design handles approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery product orientation |
| Provisioned floor set at 3,200/sec | Derived from 4× diurnal peak factor applied to working assumption; accommodates plausible success scenarios without immediate re-sizing |
| Push and in-app treated as substitutes for the same event, not independent draws | Push captures ~80% of events; in-app captures ~20% (the in-session fraction); email and SMS draw from separate volume budgets |
| SMS spend cap calibrated against top-down volume ceiling, not bottom-up estimate | Caps sized against the bottom-up estimate would trigger constantly at provisioned volume |
| 2FA SMS configuration treated as a binary product decision with categorically different cost structures | Authenticator-first vs. SMS-default implies potentially an order-of-magnitude difference in SMS cost; engineering cannot set caps until product decides |
| Channel-specialized workers for all four channels | Any channel pair with mismatched latency profiles creates head-of-line blocking |
| Fan-out modeled by notification type, not aggregate multiplier | Aggregate figures conflate event types with different mechanics |
| Escalation alert threshold at 85% of provisioned capacity | 75% fires within normal diurnal variance at working assumption |
| SMS cap runbook assigned to a named engineer with explicit launch gate mechanism | On a four-engineer team, role-based assignment with no gate mechanism does not get done |

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

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU. The provisioned floor is set to remain adequate through the 40% DAU/MAU, 20/day scenario before requiring a re-sizing review; see Section 1.4.

---

### 1.2 Notifications Per Active User Per Day — Sensitivity Analysis

This figure multiplies the same sizing cascade as the DAU/MAU ratio and deserves equivalent treatment.

**Why this figure is harder to estimate than DAU/MAU:** The DAU/MAU ratio can be approximated from existing user data or comparable app analytics before launch. The notifications-per-active-user rate depends on product feature set, social graph density, and engagement patterns that may not stabilize until 30–60 days post-launch. It carries more uncertainty than the DAU/MAU assumption.

**Basis for the working figure:** The Braze 2023 Mobile Marketing Report reports a median of 15–20 notifications/day for active users of social apps. That range conflates two meaningfully different app types:

- **Messaging-heavy apps** (WhatsApp, Telegram, Messenger): notification volume is dominated by direct messages, which are high-frequency and bidirectional. These apps sit at the high end of the range (18–25/day) or above it.
- **Content-discovery apps** (Instagram-style, TikTok-style): notification volume is dominated by social graph events (likes, comments, follows) and algorithmic recommendations. These apps sit at the low-to-mid end (10–17/day).

**Placement decision:** A social app with a content-discovery orientation and a secondary DM feature sits closer to the low end of the range. The working figure is **15/day**. If the DM feature is the primary engagement driver, this figure should be revised upward before launch — that is a product-context question that engineering cannot answer unilaterally.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average inbound |
|------------------------------|------------------|--------------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

These figures are 24-hour sustained averages. The provisioned floor is set against peak rates, derived in Section 1.4 by applying a peak factor to these sustained averages.

**Combined sensitivity — sustained average inbound in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 | ~347 | ~463 | ~579 |
| 30% | ~347 | **~521** | ~694 | ~868 |
| 40% | ~463 | ~694 | ~926 | ~1,157 |
| 45% | ~521 | ~781 | ~1,042 | ~1,302 |

**What the provisioned floor of 3,200/sec covers:** Applying a 4× diurnal peak factor (see Section 1.4 for why the high end of the cited range is used), the 3,200/sec floor accommodates sustained averages up to 800/sec before viral effects. This covers: 30% DAU/MAU through 20/day (694/sec — accommodated with headroom), and 40% DAU/MAU at 15/day (694/sec — accommodated). Scenarios that require re-sizing review are flagged explicitly in Section 1.5.

---

### 1.3 Channel Split

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume. Treating them as independent — and summing their shares to less than 100% — creates an unaccounted gap in the volume model.

**The channel split therefore works as follows:**

- **In-app share:** Fraction of notification events where the target user is in-session at delivery time. Working assumption: 20% of events. This is the only input needed to determine the push/in-app split.
- **Push share:** Remaining events not captured by in-app: 80% of total notification volume.
- **Email and SMS:** These are not substitutes for push/in-app. They are either duplicates of push events (digest emails for opted-in users) or independent event types (transactional SMS). They draw from separate volume budgets, not from the push/in-app pool.

**Corrected channel allocation:**

| Channel | Share of total notification events | Volume at working assumption | Notes |
|---------|-----------------------------------|------------------------------|-------|
| Push (APNs + FCM) | 80% | ~36M/day | All events where user is not in-session |
| In-app | 20% | ~9M/day | Events where user is in-session; substitute for push |
| Email | Separate budget | ~270–400K/day | Digest and transactional; see below |
| SMS | Separate budget (ceiling) | ~225K/day ceiling | Transactional only; see Section 1.3 (SMS) |

**Email volume basis:** Email notifications are a subset of push events (same underlying social graph events) sent to users who have opted into email digests. Working assumption: 8% of the user base opts into email notifications, receiving approximately 1 digest email/day. At 10M MAU and 30% DAU/MAU, that is roughly 3M engaged users × 8% × 1/day = ~240K emails/day from the social notification flow, plus transactional emails (account confirmations, password resets) estimated at ~30K/day. Total email volume: ~270–400K/day depending on opt-in rate. Email workers are sized against this volume, not against a percentage of the 45M total notification events.

**Why this matters for worker sizing:** Push workers handle ~36M events/day. In-app workers handle ~9M events/day. Email workers handle ~270–400K events/day. SMS workers handle up to ~225K events/day. These are the inputs to worker count derivation in Section 1.4.

**Sensitivity consequences:**

| Scenario | Impact |
|----------|--------|
| In-app share exceeds 30% | In-app worker count reviewed; push workers reduced proportionally |
| Email opt-in rate exceeds 12% | Additional email worker provisioned |
| SMS volume approaches 0.3% of total events | SMS worker count reviewed; spend cap reviewed |

---

### 1.3 (SMS) SMS Volume and Spend Caps

**Use cases:** SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, reshares).

**Top-down volume ceiling:** At 10M MAU, a provisioned SMS ceiling of 0.5% of total notification volume implies ~225K SMS/day. This is the ceiling, not the expected volume.

**Bottom-up volume estimate:**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone number verification | 10M MAU × 1% monthly growth / 30 days × 60% phone verification | ~2,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| 2FA SMS | See below | Variable |
| **Subtotal (non-2FA)** | | **~11,000/day** |

The gap between the bottom-up estimate and the top-down ceiling is intentional. The 0.5% ceiling accommodates SMS use cases not enumerated in the bottom-up model (promotional opt-ins, international user patterns, 2FA volume). The spend cap must be calibrated against the top-down ceiling — not the bottom-up estimate — to avoid triggering constantly during legitimate volume bursts.

**⚠ 2FA configuration — binary product decision required before launch**

There are two discrete product configurations with categorically different cost structures. Engineering cannot determine the correct SMS spend cap until the product team makes this choice explicitly. The configurations are:

**Configuration A — Authenticator-first:** TOTP apps (Google Authenticator, Authy) are the default and primary 2FA method. SMS-2FA is available as a fallback but requires explicit user selection. At 3M DAU with 15% 2FA enrollment (450K enrolled users), SMS-2FA adoption in authenticator-first apps typically falls in the 5–15% range, yielding an upper bound of ~22,500–67,500 SMS-2FA events/day (assuming one 2FA event per login; actual figure is lower because not all DAU log in daily).

**Configuration B — SMS-default:** SMS-2FA is the default. Authenticator apps are available but require explicit opt-out. SMS-2FA adoption on SMS-default apps is typically 40–70% of enrolled users, yielding an upper bound of ~180,000–315,000 SMS-2FA events/day under the same assumptions.

The cost difference between these configurations is potentially an order of magnitude in absolute SMS spend, not a smooth 2.3× tradeoff. The choice is categorical.

**Corrected spend cap design:**

The spend cap is designed to catch runaway notification loops and billing accidents, not to survive a major credential stuffing attack. A legitimate large-scale attack will exceed any reasonable daily cap and requires manual incident response regardless of where the cap is set.

| Configuration | Expected daily SMS volume (upper bound) | Daily cost at $0.0079/SMS | Spend cap | Basis for cap |
|--------------|----------------------------------------|--------------------------|-----------|--------------|
| A (authenticator-first) | ~78,500/day | ~$620 | $1,200/day | ~2× upper bound of expected volume |
| B (SMS-default) | ~326,000/day | ~$2,575 | $5,200/day | ~2× upper bound of expected volume |

The 2× multiplier above the expected upper bound provides margin for normal variance — usage spikes, verification retry storms, minor attack traffic — without triggering false positives during normal operation.

**Default if no product decision is made before development begins:** Configuration A (authenticator-first), because it is the lower-cost failure mode. This default must be explicitly acknowledged by product ownership. Engineering's responsibility is to flag the open decision and document the default; product ownership's responsibility is to either confirm the default or make the explicit choice.

**SMS cap runbook — launch gate item:**

The runbook is assigned to **[Engineer Name — to be filled in at project kickoff]**, one of the four backend engineers. It is a launch gate item with the following specific mechanism: the runbook document must exist in the team's runbook repository and must be reviewed and signed off by a second engineer before the launch readiness review. The launch readiness review cannot be marked complete without this sign-off.

The runbook must specify:
- **Who is authorized to raise the SMS cap:** Any on-call engineer, for up to 24 hours. Beyond 24 hours requires a second engineer's acknowledgment.
- **What verification is required before raising:** Confirm the event is not a billing loop by checking notification dispatch logs. Confirm the event is a legitimate security incident before elevating.
- **Temporary elevated cap ceiling:** 3× the normal cap, not unlimited.
- **Duration before re-authorization:** 24 hours.
- **Restoration procedure:** How to restore the original cap after the incident resolves.

**Redis spend counter implementation:**

A 24-hour sliding window counter tracks SMS spend. The window is sliding (not midnight-reset) to prevent end-of-day burst abuse where two separate bursts straddle midnight and each falls within a separate daily window.

The spend counter runs on a dedicated Redis instance for two reasons: (1) **operational isolation** — a failure in the main notification Redis cluster must not take down the spend cap counter, because losing the counter means losing the only mechanism preventing runaway SMS billing; (2) **configuration isolation** — the spend counter instance runs with no `maxmemory` policy set (meaning Redis will not evict keys regardless of memory pressure), whereas the main cluster may run with an eviction policy appropriate to its workload. These are incompatible configurations on the same instance.

A t3.micro instance ($0.0104/hour, ~$7.50/month) is sufficient. The counter key requires negligible memory (<1KB). The dedicated instance is justified by operational and configuration isolation, not by memory requirements.

---

### 1.4 Peak Factor, Provisioned Floor, and Worker Sizing

#### Peak Factor Derivation

Notification delivery is not uniformly distributed across 24 hours. Two independent sources of peaking apply:

**Diurnal peak factor:** Consumer app usage concentrates in morning (7–9 AM), lunch (12–1 PM), and evening (7–10 PM) local time. For a US-primary app, these three windows overlap partially. For a global app, timezone spread flattens the peak. Working assumption: US-primary with partial international audience.

Published mobile analytics benchmarks (Localytics 2022, AppsFlyer 2023) show 3–5× peak-to-average ratios for social app notification delivery. The working assumption uses **4×** — the high end of the conservative portion of this range — for the provisioned floor derivation. Using the low end (3×) would produce a floor that is adequate at the working assumption but insufficient under a modestly successful launch.

**Viral burst factor:** Covered in Section 1.5. This is an independent multiplier applied on top