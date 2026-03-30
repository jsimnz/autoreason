# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown explicitly. Where assumptions carry material uncertainty, they are marked ⚠ and the consequences of being wrong are shown arithmetically.

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

**Revision note:** This document addresses nine specific problems identified in review: hollow accountability structure, unjustified in-app/push split, email volume base error, false 2FA binary, duplicate section numbers, incomplete worker count derivation, flawed Redis isolation argument, missing sensitivity flags at table boundaries, and unjustified spend cap multiplier. Each correction is made in-place; the affected sections note what changed and why.

---

## Executive Summary

This design handles approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery product orientation |
| Provisioned floor set at 3,200/sec | Derived from 4× diurnal peak factor; worker count derivation shown in Section 1.4 |
| Push and in-app treated as substitutes for the same event, not independent draws | Push captures ~75% of events; in-app captures ~25%; split derived from session duration data in Section 1.3 |
| Email volume base is MAU opt-in population, not DAU | Email opt-in is an account setting, not a daily behavior; correct base yields ~800K digest emails/day |
| 2FA SMS modeled across three configurations, not two | Authenticator-first, SMS-default, and hybrid (SMS-default at signup with TOTP nudge) each have distinct cost curves |
| SMS spend cap set at 1.5× working estimate, not 2× stated upper bound | Cap is meant to catch runaway loops; setting it above the upper bound defeats its purpose |
| Channel-specialized workers for all four channels | Any channel pair with mismatched latency profiles creates head-of-line blocking |
| Escalation alert threshold at 85% of provisioned capacity | 75% fires within normal diurnal variance at working assumption |
| SMS cap runbook assigned to the engineer designated on-call lead at kickoff | Named role resolved at kickoff via explicit mechanism described in Section 1.3b |

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

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU. The provisioned floor remains adequate through the 40% DAU/MAU, 20/day scenario before requiring a re-sizing review; see Section 1.4.

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

**Combined sensitivity — sustained average inbound in req/sec, with capacity flags:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 | ~347 | ~463 | ~579 |
| 30% | ~347 | **~521 ✓** | ~694 ✓ | ~868 ⚠ |
| 40% | ~463 | ~694 ✓ | ~926 ⚠ | ~1,157 ✗ |
| 45% | ~521 | ~781 ⚠ | ~1,042 ✗ | ~1,302 ✗ |

**Key:** ✓ = within provisioned floor at 4× peak factor (sustained avg × 4 ≤ 3,200/sec); ⚠ = within provisioned floor but above 75% of capacity, triggering re-sizing review; ✗ = exceeds provisioned floor, requires re-sizing before reaching this scenario.

The 800/sec sustained average threshold (3,200/sec ÷ 4× peak factor) is the boundary between ✓ and ⚠/✗ designations. Any cell above 800/sec is flagged. Scenarios marked ✗ require re-sizing review before the app reaches those engagement levels — they are not emergencies if the review is conducted proactively as engagement metrics are observed.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume.

**Deriving the in-app share from session data:**

The in-app fraction equals the probability that a target user is in an active session at the moment a notification event is generated for them. This is a function of daily session duration, not an arbitrary assumption.

**Session duration reference points for social apps:**

| App type | Avg daily session time | Source |
|----------|----------------------|--------|
| Social/content apps (Instagram, TikTok) | 28–53 min/day | App Annie 2023, Sensor Tower 2023 |
| Messaging-primary apps | 30–60 min/day | Similar Web 2023 |
| Mid-engagement social apps | 15–30 min/day | Adjust Mobile Report 2023 |

**Working assumption:** 20–25 minutes of active session time per DAU per day, consistent with a content-discovery app where users check in multiple times but don't leave the app running continuously.

**Deriving the fraction:** If a user spends 20–25 minutes per day in-app across a 16-hour active window (6 AM–10 PM), the probability that a randomly timed notification event finds them in-session is approximately:

- At 20 min/day: 20 / (16 × 60) = 20/960 ≈ **2.1%**
- At 25 min/day: 25/960 ≈ **2.6%**

This is substantially lower than the previously asserted 20% figure. The 20% figure would require users to spend approximately 192 minutes (3.2 hours) per day in active session — consistent with a messaging-primary app but not a content-discovery app.

**Corrected in-app share: 2–3% of notification events.** Push handles ~97–98%.

**Why the previous 20% figure was wrong and what it would imply:** A 20% in-app fraction implies ~3.2 hours of daily active session time per DAU. This is plausible for WhatsApp-primary markets or highly addictive short-video apps, but it is not a defensible default for an unspecified social app. The error matters for worker sizing: at 2.5% in-app, in-app workers handle ~1.1M events/day, not 9M. This reduces in-app worker count by roughly 8×.

**⚠ Sensitivity note:** If the product is messaging-primary and session times are 90+ minutes/day, the in-app fraction rises to ~9–10% and the previous 20% figure becomes directionally plausible (though still high). This is a product-context input that should be confirmed against session time data from comparable apps or from the app's own beta/soft-launch data before finalizing worker sizing.

**Corrected channel allocation:**

| Channel | Share of total notification events | Volume at working assumption | Notes |
|---------|-----------------------------------|------------------------------|-------|
| Push (APNs + FCM) | ~97.5% | ~43.9M/day | All events where user is not in-session |
| In-app | ~2.5% | ~1.1M/day | Events where user is in-session; substitute for push |
| Email | Separate budget | ~800K–1.2M/day | See Section 1.3b |
| SMS | Separate budget (ceiling) | ~11K–78.5K/day | Transactional only; see Section 1.3b |

---

### 1.3b Email Volume, SMS Volume, and Spend Caps

**[Correction from review: the previous version used DAU as the email opt-in base. Email opt-in is an account setting, not a daily behavior. Users who haven't opened the app in weeks still receive digest emails if they opted in. The correct base is MAU or total registered users.]**

**Email volume basis:**

Email digest opt-in is a one-time account setting. The relevant population is everyone who has opted in, regardless of whether they were active today. The correct base is **MAU (10M)**, not DAU (3M).

| Component | Derivation | Daily volume |
|-----------|-----------|-------------|
| Digest emails (social notifications) | 10M MAU × 8% opt-in rate × 1 digest/day | ~800K/day |
| Transactional emails (account, password) | Estimated flat rate | ~30K/day |
| **Total email** | | **~830K/day** |

At 12% opt-in rate: ~1.23M/day. At 5% opt-in rate: ~530K/day.

This is approximately 3× the previously stated figure of ~270K/day. The email worker sizing and provider tier selection must be based on the corrected figure. At ~830K emails/day (~9.6/sec sustained average, ~38/sec at 4× peak), the email tier selection shifts from entry-level SendGrid/SES configurations to mid-tier configurations with dedicated IP pools. This is addressed in the infrastructure section.

**SMS volume and spend caps:**

**Use cases:** SMS is reserved for transactional and security events. It is not used for social notifications.

**⚠ 2FA configuration — three configurations, not two:**

The previous version presented authenticator-first vs. SMS-default as the complete decision space. This omits the most common real-world configuration: **SMS-default at signup with a post-enrollment nudge toward authenticator apps.** Many apps use SMS-default because it has higher onboarding completion rates, then surface TOTP enrollment prompts to active users over time. This hybrid configuration has its own cost curve.

| Configuration | Description | SMS-2FA adoption (of enrolled users) | Expected daily SMS-2FA volume |
|--------------|-------------|--------------------------------------|------------------------------|
| A — Authenticator-first | TOTP default; SMS as explicit fallback | 5–15% | ~22,500–67,500/day |
| B — SMS-default | SMS default; TOTP as explicit opt-out | 40–70% | ~180,000–315,000/day |
| C — Hybrid | SMS default at signup; TOTP nudge post-enrollment | 20–40% (declines over time as nudge converts users) | ~90,000–180,000/day at launch, declining |

Configuration C is bounded by A and B but is not equivalent to either. At launch it resembles B; after 6–12 months of nudge conversion it approaches A. The spend cap for Configuration C must be set against launch-time volume (B-like), not steady-state volume (A-like).

**The previous document stated "engineering cannot determine the correct SMS spend cap until the product team makes this choice" and then set a unilateral default of Configuration A. This is contradictory.** The corrected approach: engineering documents all three configurations with their cost implications and requests an explicit product decision. The development default — if no decision is made before sprint planning begins — is Configuration A, and that default must be explicitly acknowledged in writing by a product owner before it takes effect. Engineering's role is to flag the decision and document the default; product ownership's role is to either confirm or override it. A default that has not been acknowledged in writing by product ownership is not a valid default — it is an undocumented assumption.

**Bottom-up SMS volume estimate:**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone verification | 10M MAU × 1% monthly growth / 30 × 60% phone verification | ~2,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| 2FA SMS (Config A upper bound) | 450K enrolled × 15% SMS adoption × ~10% daily login rate | ~6,750/day |
| 2FA SMS (Config C at launch) | 450K enrolled × 40% SMS adoption × ~10% daily login rate | ~18,000/day |
| 2FA SMS (Config B upper bound) | 450K enrolled × 70% SMS adoption × ~10% daily login rate | ~31,500/day |
| **Total (Config A)** | | **~17,750/day** |
| **Total (Config C at launch)** | | **~29,000/day** |
| **Total (Config B)** | | **~42,500/day** |

**Corrected spend cap design:**

**[Correction from review: the previous version set caps at 2× the stated upper bound, meaning the cap would not trigger until volume reached 2× the worst plausible normal case. A cap that by construction cannot trigger during anything describable as normal variance does not function as a billing accident catch. The cap should be set at 1.5× the working estimate — not 1.5× the upper bound — to catch genuine anomalies while tolerating normal variance.]**

The distinction matters: the working estimate represents expected volume at normal operating conditions. The upper bound already incorporates pessimistic assumptions. Setting the cap at 