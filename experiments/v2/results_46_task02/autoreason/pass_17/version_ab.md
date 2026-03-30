# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown here. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution — are structural assumptions without pre-launch empirical validation. The arithmetic makes those inputs visible and the consequences of being wrong calculable. Sections carrying material uncertainty are marked ⚠. Section 1.5 consolidates all measurement triggers with the specific thresholds that should prompt re-sizing reviews.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. The revision table is not a completeness guarantee — it is an index of what was attempted. Problems introduced by this document are flagged inline.

---

## Executive Summary

This design handles approximately 45–50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU at 30%, with explicit 20–45% sensitivity range | Single most load-bearing ratio input; sizing shows consequences across full range |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery orientation; sensitivity treated equivalently to DAU/MAU |
| Channel split specified to sum to 100%, SMS at 0.5% | Closes accounting gap; SMS sized by bottom-up use-case derivation with conservative ceiling |
| Channel-specialized workers for all four channels | Any channel pair with mismatched latency profiles creates head-of-line blocking; consistency requires separation across all pairs |
| Fan-out modeled by notification type, not aggregate multiplier | Aggregate figures conflate event types with different mechanics; reshare is the only high-fan-out type |
| Viral event figures presented as order-of-magnitude bounds | Inputs are assumptions; false precision in planning figures causes downstream sizing errors |
| SMS spend cap tiered by 2FA product configuration | Single cap calibrated against an uncertain assumption is wrong on day one if that assumption is wrong; this is a pre-launch product decision |
| Provisioned floor at 2,500/sec sustained | 1,800/sec provides ~15% margin at diurnal peak under working assumption — consumed by normal variance before any viral contribution |
| Escalation ladder: alert → scale → shed → incident | Thresholds ordered so each tier fires before the next is needed; arithmetic shown |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs/FCM connection failures |

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

**Critical property of this input:** Unlike the notifications/day figure (Section 1.2), the DAU/MAU ratio can be approximated from existing user data or comparable app analytics before launch. It should be measured and updated before the provisioned floor is finalized.

---

### 1.2 Notifications Per Active User Per Day — Sensitivity Analysis

This figure multiplies the same sizing cascade as the DAU/MAU ratio and deserves equivalent treatment.

**Why this figure is harder to estimate than DAU/MAU:** The notifications-per-active-user rate depends on product feature set, social graph density, and engagement patterns that may not stabilize until 30–60 days post-launch. It carries more uncertainty than the DAU/MAU assumption and cannot be measured from pre-launch data.

**Basis for the working figure:** The Braze 2023 Mobile Marketing Report reports a median of 15–20 notifications/day for active users of social apps. That range conflates two meaningfully different app types:

- **Messaging-heavy apps** (WhatsApp, Telegram-style): notification volume dominated by direct messages, high-frequency and bidirectional. These sit at the high end (18–25/day) or above it.
- **Content-discovery apps** (Instagram/TikTok-style): notification volume dominated by social graph events (likes, comments, follows) and algorithmic recommendations. These sit at the low-to-mid end (10–17/day).

**Placement decision:** A social app with a content-discovery orientation and a secondary DM feature sits closer to the low end of the range. The working figure is **15/day**. If the DM feature is the primary engagement driver, this should be revised upward before launch — that is a product-context question engineering cannot answer unilaterally.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained avg inbound | Notes |
|------------------------------|------------------|----------------------|-------|
| 10 | 30M | ~347/sec | Low engagement, content-discovery only |
| **15** | **45M** | **~521/sec** | **Working assumption** |
| 20 | 60M | ~694/sec | Strong DM feature |
| 25 | 75M | ~868/sec | Messaging-dominant |

These are 24-hour averages. The provisioned floor is set against peak rates; see Section 1.4.

**Combined sensitivity (DAU/MAU × notifications/day) — sustained inbound in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 | ~347 | ~463 | ~579 |
| 30% | ~347 | **~521** | ~694 | ~868 |
| 40% | ~463 | ~694 | ~926 | ~1,157 |
| 45% | ~521 | ~781 | ~1,042 | ~1,302 |

The provisioned floor of ~2,500/sec (derived in Section 1.4 from peak factor analysis) provides headroom through the 45% DAU/MAU, 25/day scenario before viral effects are applied.

**Section 1.5 triggers:**
- If DAU/MAU exceeds 38% at 60 days post-launch, push worker count is reviewed.
- If measured notifications/active user/day exceeds 20 at 30 days post-launch, worker sizing is reviewed against the 25/day column.

---

### 1.3 Channel Split

The channel split determines per-channel worker allocation. It is a structural assumption pre-launch. All four channels must sum to 100%; SMS is specified at 0.5% to close the accounting gap present in designs that specify SMS as "<1%."

| Channel | Working split | Plausible low | Plausible high |
|---------|--------------|--------------|----------------|
| Push (APNs + FCM) | 71.5% | 55% | 75% |
| In-app | 20% | 15% | 35% |
| Email | 8% | 5% | 12% |
| SMS | 0.5% | 0.2% | 1% |
| **Total** | **100%** | | |

**Basis for push split:** On a mobile-first social app, the majority of notification events target users not currently in the foreground. The 71.5% figure is consistent with Airship's 2023 push benchmark for social apps (65–75% range).

**Basis for in-app split:** The 20% in-app share reflects the estimated fraction of notification events that fire while the target user has the app in the foreground. When a user is in-session, in-app delivery substitutes for push delivery — the two channels are substitutes for the same event, not complements. The routing decision (push vs. in-app) is made at dispatch time based on session presence, not at the channel split level. The 20% figure is derived from the substitution logic: if 20% of events fire while the target user is in-session, push captures ~71.5% of the remainder.

**Basis for SMS split:** The 0.5% figure is set conservatively above the bottom-up estimate of ~47,000/day (Section 1.3 SMS) to allow for SMS use cases not enumerated in the bottom-up model. At 45M notifications/day and 0.5% SMS share, this implies ~225,000 SMS/day — the gap between this and the bottom-up estimate is intentional headroom. The SMS spend cap is designed to catch the gap before it becomes a billing event.

**Sensitivity consequences:**

| Scenario | Action |
|----------|--------|
| In-app share exceeds 28% | Second in-app worker provisioned |
| Push share drops below 60% | Two push workers decommissioned; in-app workers reviewed |
| Email share exceeds 11% | Fourth email worker provisioned |
| SMS share exceeds 0.8% | SMS worker count and spend cap reviewed |

---

### 1.3 (SMS) SMS Volume — Bottom-Up Derivation

SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, reshares).

**Use case volume:**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone number verification | 10M MAU × 1% monthly growth / 30 days × 60% phone verification | ~2,000/day |
| Two-factor authentication | 3M DAU × 15% 2FA enrollment × [SMS-2FA selection rate — see below] | Variable |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |

**2FA product configuration — pre-launch decision required ⚠**

The 2FA SMS volume depends entirely on whether the app defaults to SMS-2FA or offers authenticator apps as the primary option. This is a product decision, not an engineering assumption. Engineering cannot set the SMS spend cap correctly until this decision is made. The 8% and 50% figures below are themselves assumptions representing the two ends of a plausible configuration range — they are not measurements. The point is that the choice of 2FA default changes daily SMS costs materially and must be made explicitly.

| 2FA configuration | SMS-2FA selection rate | 2FA SMS/day | Total daily SMS | Daily cost at $0.0079/SMS |
|------------------|----------------------|-------------|----------------|--------------------------|
| Authenticator-first | ~8% | ~3,600 | ~14,600 | ~$115 |
| SMS-default | ~50% | ~22,500 | ~33,500 | ~$265 |

**Spend cap design:**

The spend cap is designed to catch runaway notification loops and billing accidents, not to survive a major security incident. A large-scale credential stuffing attack will exceed any reasonable daily cap and requires manual intervention regardless of where the cap is set. The cap margin should be sized for normal variance — day-to-day usage spikes, verification retry storms, temporary attack traffic — not for attack scenarios. Attempting to set the cap high enough to survive an attack while low enough to catch runaway loops is a false optimization.

| 2FA configuration | Baseline daily cost | Cap setting | Margin above baseline |
|------------------|--------------------|-----------|-----------------------|
| Authenticator-first | ~$115 | $200/day | ~74% |
| SMS-default | ~$265 | $450/day | ~70% |

70% margin accommodates normal variance without triggering false positives during normal operation.

**If the 2FA configuration decision is not made before launch:** Default to the SMS-default cap ($450/day). This is the conservative choice — less likely to cause a false positive on day one. **However, this is a financial control decision. It must be explicitly acknowledged by product ownership, not silently defaulted by engineering.** Engineering's responsibility is to flag the open decision and document the default; product ownership's responsibility is to either confirm the default or make the explicit choice.

**Operational dependency:** The on-call runbook must include a procedure for temporarily raising the SMS cap during verified security incidents. This is a required deliverable before launch, not optional documentation. It must specify: who is authorized to raise the cap, what verification is required, what the temporary elevated cap ceiling is, and how long the elevation can remain in effect before requiring re-authorization. This is assigned to the on-call infrastructure owner as a launch gate item.

**Redis counter implementation:** The SMS spend counter uses a 24-hour sliding window — not a midnight-reset counter — to avoid end-of-day reset races where a burst at 11:59 PM and another at 12:01 AM each fall within separate daily windows and together exceed twice the intended daily cap. The counter runs on a dedicated Redis instance with no eviction policy. Memory requirement is negligible (< 1KB for a single counter key); the dedicated instance is justified by operational isolation, not memory: the spend cap counter must not be subject to eviction pressure from the main notification Redis cluster. A t3.micro instance ($0.0104/hour) is sufficient.

---

### 1.4 Peak Factor, Provisioned Floor, and Worker Sizing

#### Peak Factor Derivation

Notification delivery is not uniformly distributed across 24 hours. Two independent sources of peaking apply.

**Diurnal peak factor:** Consumer app usage concentrates in morning (7–9 AM), lunch (12–1 PM), and evening (7–10 PM) local time. For a US-primary app, these windows overlap partially. For a global app, timezone spread flattens the peak. Working assumption: US-primary with partial international audience. Diurnal peak factor: **3× above 24-hour average** (consistent with Localytics 2022 and AppsFlyer 2023 mobile benchmarks showing 3–5× peak-to-average ratios for social apps; the lower bound is used as the conservative working figure).

**Viral burst factor:** Covered below. This is an independent multiplier applied on top of the diurnal peak.

**Provisioned floor derivation:**

```
Sustained average at working assumption (30% DAU/MAU, 15/day):
  3M DAU × 15 notifications/day / 86,400 sec = ~521/sec

Diurnal peak (3× factor):
  521 × 3 = ~1,563/sec

Provisioned floor (60% headroom above diurnal peak):
  1,563 × 1.6 = ~2,500/sec
```

The 60% headroom serves two purposes: (1) it accommodates the 40% DAU/MAU, 20/day scenario (~926/sec sustained, ~2,778/sec at 3× diurnal peak) without requiring immediate re-sizing on a successful launch; (2) it provides buffer before the escalation ladder's alert tier fires. The alert tier fires at 75% of provisioned capacity (~1,875/sec); at the working assumption diurnal peak of 1,563/sec, this leaves ~20% margin before alerting.

**Why a floor of 1,800/sec is inadequate:** At the working assumption diurnal peak of 1,563/sec, a floor of 1,800/sec provides 15% margin. That margin is consumed by normal intraday variance before any viral contribution. At 40% DAU/MAU with 20/day — a plausible outcome for a successful launch — the diurnal peak reaches ~2,778/sec, which exceeds the 1,800/sec floor before the escalation ladder has time to respond. The provisioned floor must be set against the plausible success scenario, not the working assumption alone.

---

#### Fan-Out Arithmetic — Built From First Principles ⚠

Prior approaches have used aggregate "200 notifications per engagement event" fan-out figures that conflate fundamentally different notification types. A like generates at most 1 notification (to the content creator). A reshare may notify the original creator and propagate through the resharer's follower graph. These are different mechanics with different fan-out ratios. Aggregating them produces a figure that is neither derivable nor verifiable and causes planning errors in both directions.

**Fan-out by notification type:**

| Event type | Who is notified | Fan-out per event | Notes |
|------------|----------------|------------------|-------|
| Like on post | Content creator only | 1 