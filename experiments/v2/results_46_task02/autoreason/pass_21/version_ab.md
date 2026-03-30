# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

This document is a complete, standalone design. Where architectural choices were made, the reasoning is shown explicitly. Where assumptions carry material uncertainty, they are marked ⚠ and the consequences of being wrong are shown arithmetically.

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution, geographic SMS distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

---

## Gate Items Register

All items in this register are launch blockers. Each requires a recorded sign-off before the associated tier can be sized and before launch readiness review completes. Sign-off format: a named individual's written acknowledgment posted to the team's runbook repository, referencing this document by version, with a timestamp.

No gate item is assigned a specific individual's name in this document because the design is written before team assignment is confirmed. The owner role column specifies the role that must sign off; the team lead is responsible for filling each role slot before Week 2 of Month 1 and recording those assignments in the runbook repository alongside this document.

| Gate ID | Decision | Owner Role | Deadline | Consequence if Unresolved |
|---------|----------|------------|----------|--------------------------|
| GATE-1 | Email opt-in posture (default-on vs. default-off) | Named product owner | Week 4, Month 1 | Email worker tier cannot be sized; provider contract and IP warm-up cannot begin. At default-on volumes, procurement lead time alone may exceed remaining schedule. |
| GATE-2 | App type: messaging-primary vs. content-discovery | Named product owner | Week 4, Month 1 | Notifications-per-active-user working figure cannot be confirmed; all downstream worker sizing carries unquantified error. |
| GATE-3 | Session time data: average session minutes/DAU/day | Named analytics owner | Week 4, Month 1 | In-app fraction cannot be confirmed; in-app worker tier may be provisioned 2–3× too low or too high. |
| GATE-4 | SMS 2FA configuration (A, B, or C) | Named product owner + security lead | Week 4, Month 1 | SMS spend cap cannot be set; Configuration C requires a two-phase cap covering launch period and steady state. |
| GATE-5 | SMS 2FA default: authenticator vs. SMS, and nudge timeline if C | Named security lead | Week 4, Month 1 | Configuration C spend cap cannot be phased correctly; launch-period cap will be wrong. |

---

## Executive Summary

This design handles approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application. Email volume is additive to push/in-app volume, not a substitute; the relationship is specified in Section 1.3b.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU working assumption at 30%, with 20–45% sensitivity range | Single most load-bearing ratio input; consequences shown across full range with capacity flags |
| 15 notifications/active user/day as working figure, with 10–25 range | Placed at low end of reported range; subject to GATE-2 confirmation. Braze 2023 reports 15–20/day aggregate for social apps; 15/day is conservative for content-discovery orientation |
| Peak factor 6× (range 5–8×); provisioned floor set at **4,200/sec** | Derived from first principles in Section 1.4 using diurnal load distribution; 4× is unsupported by comparable-platform data |
| APNs and FCM treated as separate worker tiers | Distinct rate limits, token invalidation behaviors, and failure modes; aggregate push modeling masks platform-specific bottlenecks |
| In-app fraction set at 6.5% (range 5–8%) | Naive session-fraction model understates this because notification events correlate with user activity; corrected derivation in Section 1.3a |
| Email volume base is MAU opt-in population, not DAU | Email opt-in is an account setting, not a daily behavior; using DAU understates volume ~3× |
| Email opt-in rate gated on product decision (GATE-1) | Rate depends on default-on vs. default-off — a product decision that changes email volume by 4–7× and affects procurement timeline |
| SMS cost modeling accounts for geographic rate variation | International rates vary 6–20× above domestic; flat-rate modeling produces wrong spend caps |
| Configuration C SMS spend cap is two-phase | Launch-period cap sized at B-range volume; steady-state cap sized after nudge conversion data available at Month 8–12 |
| Single escalation threshold at 80% of provisioned capacity | One threshold with one action eliminates operator ambiguity; prior two-threshold design provided no guidance on which to act on |
| SMS 2FA default includes time-bounded escalation path | 72-hour escalation path with documented fallback; not blocked on external acknowledgment |
| Sign-off mechanism applied consistently to all gate items | All five gate items use the same recorded-acknowledgment format; see Gate Items Register above |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio — Sensitivity Analysis

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it.

**Published reference points:**

| Platform Type | DAU/MAU Range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude Mobile Benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z Consumer Benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU. The provisioned floor remains adequate through the 40% DAU/MAU, 15/day scenario; scenarios marked ⚠ or ✗ in Section 1.2 are planning triggers, not emergencies.

---

### 1.2 Notifications Per Active User Per Day — Sensitivity Analysis

This figure multiplies the same sizing cascade as the DAU/MAU ratio and deserves equivalent treatment.

**Why this figure carries more uncertainty than DAU/MAU:** The DAU/MAU ratio can be approximated from existing analytics or comparable apps before launch. The notifications-per-active-user rate depends on product feature set, social graph density, and engagement patterns that may not stabilize until 30–60 days post-launch.

**Basis for the working figure:** The Braze 2023 Mobile Marketing Report reports aggregate median notification volumes across app categories. The aggregate figure for social apps is approximately 15–20 notifications/day for active users. This figure is not segmented by app subtype in the published report; it is a single aggregate median across messaging-heavy and content-discovery apps.

The 15/day working figure is therefore not derived by selecting the lower end of a Braze-reported subtype range — no such subtype range exists in the source. It is selected as a conservative working figure within the aggregate range on the reasoning that content-discovery apps generate fewer per-user events than messaging-heavy apps, and this app's product orientation is assumed to be content-discovery pending GATE-2 confirmation.

**⚠ GATE-2 dependency:** If GATE-2 confirms a messaging-primary orientation, the working figure should be revised to 20–25/day before worker sizing is finalized.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/Active User/Day | Notifications/Day | Sustained Average Inbound |
|------------------------------|------------------|--------------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

These are 24-hour sustained averages. The provisioned floor is set against peak rates derived in Section 1.4.

**Sensitivity table flag criteria:** The provisioned floor of 4,200/sec, divided by the 6× peak factor, implies a sustained average ceiling of 700/sec. A scenario is flagged ⚠ when its sustained average exceeds 70% of that ceiling (490/sec) but does not exceed the ceiling itself. A scenario is flagged ✗ when its sustained average exceeds 700/sec, meaning peak demand exceeds the provisioned floor at the 6× working peak factor.

This means:
- ✓ = sustained average ≤ 490/sec (below 70% of implied ceiling; comfortable margin)
- ⚠ = sustained average between 490/sec and 700/sec (triggers re-sizing review before that scenario is reached)
- ✗ = sustained average > 700/sec (peak demand exceeds provisioned floor; requires re-sizing before reaching this scenario)

**Combined sensitivity — sustained average inbound in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 ✓ | ~347 ✓ | ~463 ⚠ | ~579 ⚠ |
| 30% | ~347 ✓ | **~521 ⚠** | ~694 ⚠ | ~868 ✗ |
| 40% | ~463 ⚠ | ~694 ⚠ | ~926 ✗ | ~1,157 ✗ |
| 45% | ~521 ⚠ | ~781 ✗ | ~1,042 ✗ | ~1,302 ✗ |

**Note on the working assumption cell:** The working assumption (30% DAU/MAU, 15/day, ~521/sec) is flagged ⚠. This is intentional and accurate: 521/sec exceeds the 490/sec ⚠ threshold. The provisioned floor is not breached — 521 × 6 = 3,126/sec peak, within the 4,200/sec floor — but the ⚠ flag correctly signals that the working assumption is not comfortably within the low-demand zone. This is a reasonable working assumption, not a safe-margin assumption.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume. Treating them as independent creates an unaccounted gap in the volume model.

**Why the naive session-fraction model understates in-app share:**

The naive model calculates in-app fraction as session_minutes / active_window_minutes, assuming notification events are uniformly distributed across the active window. This assumption is wrong in the direction that matters: notification events correlate with user activity. Likes, comments, and reshares spike when users are actively posting and browsing — precisely when other users are also in-session. The uniform-distribution model therefore understates the in-app fraction.

**Naive calculation for reference:**

At 20–25 minutes of active session time per DAU per day across a 16-hour active window (960 minutes):
- At 20 min/day: 20/960 ≈ 2.1%
- At 25 min/day: 25/960 ≈ 2.6%

**Empirical correction:**

Measured in-app notification delivery rates for social apps have been reported at 5–8% in mobile analytics industry studies. Two sources with verifiable publication records: Adjust's *App Trends Report 2023* (which covers notification delivery channel breakdowns for social category apps) and Airship's *Notification Benchmarks Report 2022*, which reports in-session delivery rates across app categories. Both report in-app delivery rates materially above the naive session-fraction estimate for social apps, consistent with the correlation argument above.

**Note on citations:** Localytics was acquired by Upland Software in 2018 and its independent research publication effectively ceased before 2022. Any citation to a "Localytics 2022" report is not verifiable and has been removed. The 5–8% range is supported by the Adjust and Airship sources cited above; the structural argument for why the naive model understates this figure does not depend on any single citation.

**Working in-app share: 5–8%, working figure 6.5%.** Push handles ~93.5%.

At 6.5% in-app, in-app workers handle ~2.9M events/day. Using the naive 2.5% figure would provision for ~1.1M events/day — approximately 2.6× too few workers for this tier.

**⚠ GATE-3 dependency:** If session times are 90+ minutes/day (messaging-primary app), the in-app fraction rises to approximately 15–20% even after the correlation correction. GATE-3 must provide session time data before in-app worker sizing is finalized.

**Channel allocation — push and in-app:**

| Channel | Share of Notification Events | Volume at Working Assumption | Notes |
|---------|------------------------------|------------------------------|-------|
| Push — APNs | ~47% | ~21.2M/day | iOS; separate worker tier from FCM |
| Push — FCM | ~47% | ~21.2M/day | Android + web; separate worker tier |
| In-app | ~6.5% | ~2.9M/day | Substitute for push when user is in-session |

Email and SMS are additive to this count. See Section 1.3b.

**Why APNs and FCM are separate worker tiers:**

APNs uses HTTP/2 with per-bundle-ID connection limits and returns token-invalid errors synchronously. FCM uses a different authentication model, has its own per-project quotas, and returns token-invalid errors asynchronously. An aggregated push worker cannot apply platform-specific retry logic, cannot respond correctly to token invalidation signals from each platform, and cannot be scaled independently when one platform's quota is the binding constraint. The additional worker tier costs approximately two days of engineering time to set up correctly and prevents an entire category of silent delivery failures.

---

### 1.3b Email Volume, SMS Volume, and Spend Caps

#### Email Volume — Relationship to Push/In-App

**Email is additive to push/in-app volume, not a substitute.** These are different notification mechanisms serving different purposes on different timescales:

- Push and in-app notifications are real-time event alerts (a like, a comment, a follow). They are generated per social graph event and delivered within seconds to minutes.
- Email digests are periodic summaries, typically daily or weekly, sent to users who have opted into email communication. A user who receives 15 push notifications on a given day may also receive one digest email — or none, if not opted in.

A user who is DAU generates push/in-app events. That same user may or may not receive digest email depending on opt-in status. A user who is MAU-but-not-DAU generates no push/in-app events on a given day but may still receive a digest email if opted in. These populations partially overlap but are not identical.

**Total daily notification volume = push/in-app events + email volume + SMS volume.** These are additive line items.

**Email opt-in population base: MAU (10M), not DAU (3M).** Using DAU as the base understates email volume by approximately 3× and produces an incorrectly sized email worker tier and provider configuration.

**Email opt-in rate depends on opt-in posture — a product decision (GATE-1):**

| Opt-in Posture | Typical Opt-in Rate | Daily Digest Emails | Notes |
|----------------|--------------------|--------------------|-------|
| Default-on (pre-checked at signup) | 35–60% (working: 45%) | ~4.5M/day | High-volume provider contract + dedicated IP warm-up required; materially different procurement timeline |
| Default-off, prominent prompt | 8–15% (working: 8%) | ~800K/day | Mid-tier provider configuration with dedicated IP pools |
| Default-off, minimal prompt | 3–7% (working: 5%) | ~500K/day | |

Sources: Mailchimp Email Marketing Benchmarks 2023; Campaign Monitor 2023.

**Working assumption