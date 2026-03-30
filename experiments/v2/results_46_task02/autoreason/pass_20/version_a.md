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
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range with capacity flags |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery product orientation |
| Provisioned floor set at 3,200/sec | Derived from 4× diurnal peak factor applied to working assumption; worker count derivation shown in Section 1.4 |
| Push and in-app treated as substitutes for the same event, not independent draws | In-app fraction derived from session duration data (~2.5%); push handles ~97.5% |
| Email volume base is MAU opt-in population, not DAU | Email opt-in is an account setting, not a daily behavior; correct base yields ~830K digest emails/day |
| 2FA SMS modeled across three configurations | Authenticator-first, SMS-default, and hybrid each have distinct cost curves; hybrid is the most common real-world case and must not be omitted |
| SMS spend cap set at 1.5× working estimate | Cap must trigger during genuine anomalies; setting it above the upper bound defeats its purpose |
| Channel-specialized workers for all four channels | Any channel pair with mismatched latency profiles creates head-of-line blocking |
| Escalation alert threshold at 85% of provisioned capacity | 75% fires within normal diurnal variance at working assumption |
| SMS cap runbook assigned to on-call lead designated at kickoff, with explicit sign-off gate | Named role resolved at kickoff via mechanism described in Section 1.3b; launch readiness review cannot complete without second-engineer sign-off |

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

The 800/sec sustained average threshold (3,200/sec ÷ 4× peak factor) is the boundary between ✓ and ⚠/✗ designations. Scenarios marked ✗ require a proactive re-sizing review as engagement metrics are observed — they are planning triggers, not emergencies.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume. Treating them as independent — and summing their shares to less than 100% — creates an unaccounted gap in the volume model.

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

**Working in-app share: ~2.5%.** Push handles ~97.5%.

**Why a 20% in-app figure would be wrong and what it implies:** A 20% in-app fraction requires users to spend approximately 192 minutes (3.2 hours) per day in active session. This is plausible for WhatsApp-primary markets or highly addictive short-video apps, but it is not a defensible default for a content-discovery social app. The error matters for worker sizing: at 2.5% in-app, in-app workers handle ~1.1M events/day rather than ~9M — roughly an 8× difference in provisioned worker count.

**⚠ Sensitivity note:** If the product is messaging-primary and session times are 90+ minutes/day, the in-app fraction rises to approximately 9–10%. Confirm against session time data from comparable apps or from beta/soft-launch data before finalizing worker sizing.

**Corrected channel allocation:**

| Channel | Share of total notification events | Volume at working assumption | Notes |
|---------|-----------------------------------|------------------------------|-------|
| Push (APNs + FCM) | ~97.5% | ~43.9M/day | All events where user is not in-session |
| In-app | ~2.5% | ~1.1M/day | Events where user is in-session; substitute for push |
| Email | Separate budget | ~830K/day | See Section 1.3b; base is MAU, not DAU |
| SMS | Separate budget (ceiling) | ~18K–43K/day typical | Transactional only; see Section 1.3b |

---

### 1.3b Email Volume, SMS Volume, and Spend Caps

#### Email Volume

Email digest opt-in is a one-time account setting. Users who haven't opened the app in weeks still receive digest emails if they opted in. The correct population base is **MAU (10M)**, not DAU (3M). Using DAU as the base understates email volume by approximately 3× and produces an incorrectly sized email worker tier and provider configuration.

| Component | Derivation | Daily volume |
|-----------|-----------|-------------|
| Digest emails (social notifications) | 10M MAU × 8% opt-in rate × 1 digest/day | ~800K/day |
| Transactional emails (account, password) | Estimated flat rate | ~30K/day |
| **Total email** | | **~830K/day** |

Sensitivity: at 5% opt-in, ~530K/day; at 12% opt-in, ~1.23M/day.

At ~830K emails/day (~9.6/sec sustained average, ~38/sec at 4× peak), the email provider tier shifts from entry-level SendGrid/SES configurations to mid-tier configurations with dedicated IP pools. This is addressed in Section 3 (Infrastructure).

#### SMS Volume

**Use cases:** SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, reshares).

**⚠ 2FA configuration — three configurations required:**

The most common real-world 2FA deployment — SMS-default at signup with a post-enrollment nudge toward authenticator apps — must not be omitted from the cost model. It has its own cost curve, bounded by but not equivalent to either pure configuration.

| Configuration | Description | SMS-2FA adoption (of enrolled users) | Expected daily SMS-2FA volume |
|--------------|-------------|--------------------------------------|------------------------------|
| A — Authenticator-first | TOTP default; SMS as explicit fallback | 5–15% | ~6,750–22,500/day |
| B — SMS-default | SMS default; TOTP as explicit opt-out | 40–70% | ~18,000–31,500/day |
| C — Hybrid | SMS default at signup; TOTP nudge post-enrollment | 20–40% at launch, declining over 6–12 months | ~9,000–18,000/day at launch |

Configuration C is the most common real-world case. At launch it resembles B; after 6–12 months of nudge conversion it approaches A. The spend cap for Configuration C must be set against launch-time volume, not steady-state volume.

**Bottom-up SMS volume estimate (non-2FA base):**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone verification | 10M MAU × 1% monthly growth / 30 × 60% phone verification | ~2,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| **Non-2FA subtotal** | | **~11,000/day** |

**Total SMS volume by configuration:**

| Configuration | Non-2FA base | 2FA volume | Total working estimate |
|--------------|-------------|-----------|----------------------|
| A | ~11,000 | ~6,750–22,500 | ~17,750/day |
| B | ~11,000 | ~18,000–31,500 | ~42,500/day |
| C (at launch) | ~11,000 | ~9,000–18,000 | ~29,000/day |

**Spend cap design:**

The spend cap exists to catch runaway notification loops and billing accidents. It must trigger during genuine anomalies. Setting the cap above the upper bound of expected volume defeats this purpose — a cap that by construction cannot fire during anything describable as normal variance provides no protection.

The correct calibration: **1.5× the working estimate** (not 1.5× the upper bound, and not 2× the upper bound). The 1.5× multiplier tolerates normal variance — usage spikes, verification retry storms, minor attack traffic — while catching genuine billing accidents. A legitimate large-scale credential stuffing attack will exceed any reasonable daily cap and requires manual incident response regardless of cap placement.

| Configuration | Working estimate | Daily spend cap | Daily cost at cap ($0.0079/SMS) |
|--------------|-----------------|-----------------|--------------------------------|
| A | ~17,750/day | ~26,600/day | ~$210/day |
| B | ~42,500/day | ~63,750/day | ~$504/day |
| C (at launch) | ~29,000/day | ~43,500/day | ~$344/day |

**Product decision required before development begins:** Engineering documents all three configurations with their cost implications and requests an explicit written decision from product ownership. The development default — if no decision is received before sprint planning begins — is Configuration A. That default takes effect only when acknowledged in writing by a named product owner. A default that has not been acknowledged in writing is an undocumented assumption, not a valid default.

**SMS cap runbook — launch gate item:**

The runbook is assigned to the engineer designated as on-call lead at project kickoff. That designation is made at kickoff, not left as a role description. The runbook is a launch gate item: it must exist in the team's runbook repository and must carry sign-off from a second engineer before the launch readiness review. The launch readiness review cannot be marked complete without this sign-off.

The runbook must specify:

- **Who is authorized to raise the SMS cap:** Any on-call engineer, for up to 24 hours. Beyond 24 hours requires a second engineer's explicit acknowledgment.
- **What verification is required before raising:** Confirm the event is not a billing loop by checking notification dispatch logs. Confirm any security incident before escalating.
- **Temporary elevated cap ceiling:** 3× the normal cap. Not unlimited.
- **Duration before re-authorization:** 24 hours.
- **Restoration procedure:** Steps to restore the original cap after the incident resolves