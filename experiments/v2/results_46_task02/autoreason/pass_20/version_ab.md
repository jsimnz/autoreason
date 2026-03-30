# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown explicitly. Where assumptions carry material uncertainty, they are marked ⚠ and the consequences of being wrong are shown arithmetically.

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution, geographic SMS distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

---

## Executive Summary

This design handles approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range with capacity flags |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of Braze range given content-discovery product orientation |
| Peak factor range 5–8×; provisioned floor set at **4,200/sec** | 4× is unsupported by diurnal data. Published comparable-platform data yields 5–8×; working figure is 6×. Derivation in Section 1.4 |
| APNs and FCM treated as separate worker tiers | They have distinct rate limits, token invalidation behaviors, and failure modes. Aggregate push modeling masks platform-specific bottlenecks |
| In-app fraction set at 6.5% (range 5–8%) | Naive session-fraction model understates this figure because notification events correlate with user activity. Corrected derivation in Section 1.3a |
| Email volume base is MAU opt-in population, not DAU | Email opt-in is an account setting, not a daily behavior; using DAU understates volume ~3× |
| Email opt-in rate modeled across opt-in posture scenarios | Rate depends on default-on vs. default-off at signup — a product decision that changes email volume by 4–7× |
| SMS cost modeling accounts for geographic rate variation | International rates vary 6–20× above domestic rates; flat-rate modeling produces systematically wrong spend caps |
| Configuration C SMS volume set at B-range at launch | Prior inconsistency corrected: C resembles B at launch and declines toward A over 6–12 months as authenticator nudge converts users |
| SMS spend cap set at 1.5× working estimate | Cap must trigger during genuine anomalies; calibrated against working estimate, not upper bound |
| Single escalation threshold at 80% of provisioned capacity | Prior versions had two thresholds (75% and 85%) with no operator guidance on which to act on |
| SMS 2FA default includes time-bounded escalation path | Prior version blocked on external acknowledgment with no fallback; revised mechanism includes a 72-hour escalation path and a documented fallback |
| Runbook sign-off mechanism specified, not merely required | Sign-off is a named engineer's recorded acknowledgment in the team's runbook repository, required before launch readiness review completes |

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

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU. The provisioned floor remains adequate through the 40% DAU/MAU, 15/day scenario; scenarios marked ⚠ or ✗ in Section 1.2 are planning triggers, not emergencies.

---

### 1.2 Notifications Per Active User Per Day — Sensitivity Analysis

This figure multiplies the same sizing cascade as the DAU/MAU ratio and deserves equivalent treatment.

**Why this figure carries more uncertainty than DAU/MAU:** The DAU/MAU ratio can be approximated from existing analytics or comparable apps before launch. The notifications-per-active-user rate depends on product feature set, social graph density, and engagement patterns that may not stabilize until 30–60 days post-launch.

**Basis for the working figure:** The Braze 2023 Mobile Marketing Report reports a median of 15–20 notifications/day for active users of social apps. That range conflates two meaningfully different app types:

- **Messaging-heavy apps** (WhatsApp, Telegram, Messenger): dominated by direct messages, high-frequency and bidirectional. These sit at the high end (18–25/day) or above.
- **Content-discovery apps** (Instagram-style, TikTok-style): dominated by social graph events (likes, comments, follows) and algorithmic recommendations. These sit at the low-to-mid end (10–17/day).

**Working figure: 15/day**, placed at the low end for a content-discovery oriented app. If the DM feature is the primary engagement driver, this figure should be revised upward before launch — that is a product-context question that engineering cannot answer unilaterally.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average inbound |
|------------------------------|------------------|--------------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

These are 24-hour sustained averages. The provisioned floor is set against peak rates, derived in Section 1.4 using a 6× peak factor.

**Combined sensitivity — sustained average inbound in req/sec, with capacity flags:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 | ~347 | ~463 | ~579 |
| 30% | ~347 | **~521 ✓** | ~694 ✓ | ~868 ⚠ |
| 40% | ~463 | ~694 ✓ | ~926 ⚠ | ~1,157 ✗ |
| 45% | ~521 | ~781 ⚠ | ~1,042 ✗ | ~1,302 ✗ |

**Key:** ✓ = within provisioned floor at 6× peak factor (sustained avg × 6 ≤ 4,200/sec); ⚠ = sustained avg × 6 exceeds 70% of provisioned floor, triggering re-sizing review; ✗ = exceeds provisioned floor, requires re-sizing before reaching this scenario.

The 700/sec sustained average threshold (4,200/sec ÷ 6× peak factor) is the boundary between ✓ and ⚠/✗ designations. Scenarios marked ✗ are planning triggers to be watched as engagement metrics are observed post-launch.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume. Treating them as independent creates an unaccounted gap in the volume model.

**Why the naive session-fraction model understates in-app share:**

The naive model calculates in-app fraction as session_minutes / active_window_minutes, which assumes notification events are uniformly distributed across the active window. This assumption is wrong in the direction that matters: notification events are *correlated* with user activity. Likes, comments, and reshares spike when users are actively posting and browsing — which is precisely when other users are also in-session. The uniform-distribution model therefore understates the in-app fraction.

**Naive calculation for reference:**

At 20–25 minutes of active session time per DAU per day across a 16-hour active window (960 minutes):
- At 20 min/day: 20/960 ≈ 2.1%
- At 25 min/day: 25/960 ≈ 2.6%

**Correction via empirical measurement:**

Mobile analytics studies (Localytics 2022, Adjust 2023) that have measured actual in-app notification delivery rates for social apps report **5–8% of notifications are delivered in-app** rather than via push. This is the empirically grounded range, and it is higher than the naive session-fraction model predicts precisely because of the correlation effect described above. The naive model's 2.1–2.6% figure should be treated as a lower bound, not a working estimate.

**Working in-app share: 5–8%, working figure 6.5%.** Push handles ~93.5%.

At 6.5% in-app, in-app workers handle ~2.9M events/day. Using the naive 2.5% figure would provision for ~1.1M events/day — approximately 2.6× too few workers for this tier.

**⚠ Sensitivity note:** If the product is messaging-primary and session times are 90+ minutes/day, the in-app fraction rises to approximately 15–20%. Confirm against session time data from comparable apps or from beta/soft-launch data before finalizing worker sizing.

**Channel allocation:**

| Channel | Share of total notification events | Volume at working assumption | Notes |
|---------|-----------------------------------|------------------------------|-------|
| Push — APNs | ~50% of push (~47% total) | ~21.2M/day | iOS; separate worker tier from FCM |
| Push — FCM | ~50% of push (~47% total) | ~21.2M/day | Android + web; separate worker tier |
| In-app | ~6.5% | ~2.9M/day | Substitute for push when user is in-session |
| Email | Separate budget | ~530K–4.53M/day | See Section 1.3b; base is MAU, not DAU |
| SMS | Separate budget (ceiling) | ~17K–43K/day typical | Transactional only; see Section 1.3b |

**Why APNs and FCM are separate worker tiers, not an aggregated push tier:**

APNs and FCM have different rate limits, different token invalidation behaviors, and different failure modes. APNs uses HTTP/2 with per-bundle-ID connection limits and returns token-invalid errors synchronously. FCM uses a different authentication model, has its own per-project quotas, and returns token-invalid errors asynchronously. An aggregated push worker that handles both cannot apply platform-specific retry logic, cannot respond correctly to token invalidation signals from each platform, and cannot be scaled independently when one platform's quota is the binding constraint. The additional worker tier costs approximately two days of engineering time to set up correctly and prevents an entire category of silent delivery failures.

---

### 1.3b Email Volume, SMS Volume, and Spend Caps

#### Email Volume

Email digest opt-in is a one-time account setting. Users who haven't opened the app in weeks still receive digest emails if they opted in. The correct population base is **MAU (10M)**, not DAU (3M). Using DAU as the base understates email volume by approximately 3× and produces an incorrectly sized email worker tier and provider configuration.

**Email opt-in rate depends on opt-in posture — a product decision:**

| Opt-in posture | Typical opt-in rate | Daily digest emails | Total daily email |
|----------------|--------------------|--------------------|-------------------|
| Default-on (pre-checked at signup) | 35–60% (working: 45%) | ~4.5M/day | ~4.53M/day |
| Default-off, prominent prompt | 8–15% (working: 8%) | ~800K/day | ~830K/day |
| Default-off, minimal prompt | 3–7% (working: 5%) | ~500K/day | ~530K/day |

Sources: Mailchimp Email Marketing Benchmarks 2023; Campaign Monitor 2023.

**⚠ Product decision required before worker sizing:** Engineering cannot determine the email opt-in rate without knowing the opt-in posture. The working assumption of 8% corresponds to default-off with a prominent prompt. If the product team selects default-on, email volume increases by approximately 4–7× and the email worker tier, provider configuration, and dedicated IP warm-up plan all require revision. This decision is a launch gate item — it must be recorded in writing from a named product owner before the email tier is sized.

**Working assumption: 8% opt-in (default-off, prominent prompt), yielding ~830K emails/day.**

At ~830K emails/day (~9.6/sec sustained average, ~58/sec at 6× peak), a mid-tier provider configuration with dedicated IP pools is required. At 4.5M/day (default-on), a high-volume provider contract and dedicated sending infrastructure are required — materially different procurement and IP warm-up timeline.

---

#### SMS Volume

**Use cases:** SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, reshares).

**⚠ 2FA configuration — three configurations required:**

The most common real-world 2FA deployment — SMS-default at signup with a post-enrollment nudge toward authenticator apps (Configuration C) — must not be omitted from the cost model. It has its own cost curve, bounded by but not equivalent to either pure configuration.

**Configuration C volume correction:** Configuration C at launch operates at B-range volume. A prior modeling inconsistency described C as "resembling B at launch" while assigning it a lower working estimate than B. This is corrected below: the launch-time working estimate for C is identical to B's. The spend cap for Configuration C must be sized against launch-time volume, not steady-state volume — a cap sized against steady-state will be triggered routinely during the first 6–12 months.

| Configuration | Description | SMS-2FA adoption at launch | SMS-2FA adoption at steady state |
|--------------|-------------|---------------------------|----------------------------------|
| A — Authenticator-first | TOTP default; SMS as explicit fallback | 5–15% | 5–15% (stable) |
| B — SMS-default | SMS default; TOTP as explicit opt-out | 40–70% | 40–70% (stable) |
| C — Hybrid | SMS default at signup; TOTP nudge post-enrollment | 40–70% (resembles B) | 10–25% (declining over 6–12 months) |

**Bottom-up SMS volume estimate (non-2FA base):**

| Use case | Derivation | Daily volume |
|----------|-----------|-------------|
| Phone verification | 10M MAU × 1% monthly growth / 30 × 60% phone verification | ~2,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| **Non-2FA subtotal** | | **~11,000/day** |

**Total SMS volume by configuration:**

| Configuration | Non-2FA base | 2FA volume | Working estimate | Notes |
|--------------|-------------|-----------|-----------------|-------|
| A | ~11,000 | ~6,750–22,500 | ~17,750/day | Stable |
| B | ~11,000 | ~18,000–31,500 | ~42,500/day | Stable |
| C — at launch | ~11,000 | ~18,000–31,500 | ~42,500/day | Resembles B; corrected from prior inconsistency |
| C — at 12 months | ~11,000 | ~4,500–11,250 | ~20,000/day | After nudge conversion |

---

#### SMS Cost Modeling — Geographic Rate Variation

A flat per-SMS rate produces systematically wrong spend caps for any app with international users. Twilio and