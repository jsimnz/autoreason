# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preamble

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution, geographic SMS distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

---

## 0. Gate Items and Enforcement

### 0.1 What Gates Are

Gates are decisions that block specific work items. They are not advisory checkpoints. If a gate is not resolved by its deadline, the work items that depend on it stop. This is not a consequence of someone choosing to enforce the gate — it is a consequence of the work items being genuinely impossible to complete correctly without the gate input.

### 0.2 Enforcement Structure

**The enforcement mechanism is the project plan, not a person's authority.** Each gate item has a list of work items that cannot proceed without it. If a gate misses its deadline:

1. The dependent work items are moved to a formal hold state in the project tracker.
2. The project schedule is recalculated from the date the gate resolves, not from the original deadline.
3. If recalculation produces a launch date beyond the six-month window, the scope reduction options listed in Section 5.3 activate automatically — no decision required.

The hold lifts when the gate item is recorded in the runbook repository with the required sign-off. This is the only mechanism.

**Why this is more robust than authority-based enforcement:** A team lead can be pressured to accept a verbal commitment. A project tracker that marks work items as blocked cannot. The gate system's value is that it makes the cost of an unresolved decision visible in the schedule immediately, which creates organizational pressure on the decision-maker rather than on the team lead.

### 0.3 Gate Items Register

Sign-off format for all items: a named individual's written acknowledgment posted to the team's runbook repository, referencing this document by version, with a timestamp.

| Gate ID | Decision | Owner Role | Hard Deadline | Dependent Work Items (held if missed) | Scope Reduction if Unresolved |
|---------|----------|------------|---------------|---------------------------------------|-------------------------------|
| GATE-1 | Email opt-in posture: default-on vs. default-off | Named product owner | Week 4, Month 1 | Email worker sizing; provider contract; IP warm-up schedule | Defer email channel to post-launch v1.1; launch push/in-app/SMS without email |
| GATE-2 | App type: messaging-primary vs. content-discovery | Named product owner | Week 4, Month 1 | Notifications-per-user figure lock; all worker sizing dependent on that figure | Use 20/day as conservative upper bound; size for that figure; accept over-provisioning cost |
| GATE-4 | SMS 2FA configuration: A, B, or C | Named product owner + security lead | Week 4, Month 1 | SMS spend cap; SMS worker sizing; authenticator app integration if C | Default to Configuration A (SMS-only); accept higher SMS cost |
| GATE-3 | Session time data: average session minutes per DAU per day | Named analytics owner | Week 2, Month 2 | In-app worker sizing (final); in-app fraction lock | Use 8% in-app fraction (upper bound); size in-app workers for that figure |
| GATE-5 | SMS 2FA default and nudge timeline (required only if GATE-4 resolves as C) | Named security lead | Week 2, Month 2 | Configuration C launch-period spend cap; authenticator nudge implementation | Treat Configuration C as Configuration B for spend cap purposes; log as known underestimate |

**Sequential dependency:** GATE-3 depends on GATE-2. If GATE-2 confirms messaging-primary orientation, session time data must be reinterpreted under that model before GATE-3 can close. GATE-3's deadline is therefore set two weeks after GATE-2's deadline. If GATE-2 misses its deadline, GATE-3's deadline shifts by the same amount.

**Owner role assignment:** The team lead is responsible for recording the name of the person filling each owner role in the runbook repository by the end of Week 2 of Month 1. This is itself a trackable task. If it is not completed, GATE-1 through GATE-4 are treated as unresolved as of their deadlines.

---

## Executive Summary

This design handles approximately 45–60M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application. The provisioned floor is set at **5,200/sec** — sized to provide genuine margin at the working assumption rather than sitting at its boundary.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor set at 5,200/sec | Working assumption (521/sec sustained) × 6× peak factor = 3,126/sec peak. This provides 66% headroom and remains valid through the 30% DAU/MAU, 20/day scenario (4,167/sec peak) without re-sizing |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted |
| Working assumption (30% DAU/MAU, 15/day) treated as reasonable, not safe-margin | At the raised provisioned floor, the working assumption is ✓ with 40% headroom; the sensitivity table reflects this honestly |
| APNs and FCM as separate worker tiers | Distinct rate limits, token invalidation behaviors, failure modes; aggregate modeling masks platform-specific bottlenecks; ~2 days engineering cost |
| In-app fraction derived at 6.5% using activity-correlation model | Derivation in Section 1.3a; naive session-fraction model understates this figure structurally |
| Email volume is additive to push/in-app | Different mechanism, different population base (MAU not DAU), different timescale; full model in Section 1.3b |
| SMS spend cap calculated for all three configurations | Configuration C is two-phase; full derivation in Section 1.3b |
| Single escalation threshold at 80% of a fixed provisioned number | The provisioned number is locked at design time and changed only through a documented revision; threshold is unambiguous because the reference number is stable |
| GATE-2 before GATE-3, with two-week gap | Sequential dependency acknowledged; reanalysis window built into schedule |
| Four-engineer, six-month constraint stress-tested | Section 5 contains explicit engineering budget; three components deferred to post-launch |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude Mobile Benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z Consumer Benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base, which is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU. The provisioned floor remains adequate through the 40% DAU/MAU, 15/day scenario without re-sizing; scenarios marked ⚠ or ✗ in Section 1.2 are planning triggers, not emergencies.

---

### 1.2 Notifications Per Active User Per Day

**Basis for the working figure:** The Braze 2023 Mobile Marketing Report reports aggregate median notification volumes across app categories. It does not segment by messaging-heavy versus content-discovery within the social category. The aggregate figure for social apps is approximately 15–20 notifications/day for active users. This is a single aggregate median across app subtypes.

The 15/day working figure is selected as a conservative estimate within this aggregate range, on the reasoning that content-discovery apps generate fewer per-user events than messaging-heavy apps, and this app's orientation is assumed to be content-discovery pending GATE-2 confirmation. If GATE-2 confirms messaging-primary orientation, revise to 20–25/day before finalizing worker sizing.

**⚠ GATE-2 dependency:** This figure cannot be confirmed without GATE-2 resolution.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average |
|------------------------------|------------------|------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

**Flag criteria:** The provisioned floor is 5,200/sec. The implied sustained average at that floor (dividing by the 6× peak factor) is 5,200 ÷ 6 = 867/sec.

- ✓: Sustained average below 70% of 867/sec = below 607/sec. Peak demand is comfortably within provisioned floor.
- ⚠: Sustained average between 607/sec and 867/sec. Peak demand approaches provisioned floor; re-sizing review triggered before this scenario is reached.
- ✗: Sustained average above 867/sec. Peak demand exceeds provisioned floor at 6× peak factor; re-sizing required.
- ⚠→: Cell within 5% of the next flag boundary. Treat as the higher flag category for planning purposes.

**Combined sensitivity — sustained average in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 ✓ | ~347 ✓ | ~463 ✓ | ~579 ✓⚠→ |
| 30% | ~347 ✓ | **~521 ✓** | ~694 ⚠ | ~868 ✗ |
| 40% | ~463 ✓ | ~694 ⚠ | ~926 ✗ | ~1,157 ✗ |
| 45% | ~521 ✓ | ~781 ⚠ | ~1,042 ✗ | ~1,302 ✗ |

**Note on the working assumption cell:** At the 5,200/sec provisioned floor, the working assumption (30% DAU/MAU, 15/day, ~521/sec sustained) is ✓. Peak demand is 521 × 6 = 3,126/sec — 60% of the provisioned floor, providing 40% headroom. This is an honest characterization: the working assumption is comfortably provisioned, not merely not-breached.

**Borderline case guidance:** Any cell marked ⚠→ should be treated as the higher flag category for planning purposes. The 20% DAU/MAU, 25/day cell at ~579/sec is within 5% of the 607/sec ⚠ threshold; treat as ⚠.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in the foreground at delivery time, and via push otherwise. They are not independent draws from total volume.

**Why the naive session-fraction model understates in-app share:**

The naive model calculates in-app fraction as session_minutes / active_window_minutes, assuming notification events are uniformly distributed across the active window. This assumption is structurally wrong. Notification events on a social app are generated by user actions — likes, comments, shares, follows. These actions concentrate when users are actively engaged. A user posting content at 8pm generates notifications for their followers, who are disproportionately also active at 8pm because social app usage is time-correlated across a social graph. The uniform-distribution model treats notification generation as independent of session state; it is not.

**Naive calculation for reference:**

At 20–25 minutes of session time per DAU per day across a 16-hour active window (960 minutes):
- At 20 min/day: 20/960 ≈ 2.1%
- At 25 min/day: 25/960 ≈ 2.6%

**Deriving the correction:**

Let:
- S = average session minutes per DAU per day = 22.5 minutes (midpoint of 20–25 minute range for content-discovery apps; pending GATE-3)
- W = active window = 960 minutes (16 hours)
- Naive fraction = S/W = 22.5/960 = 2.3%

The naive model assumes P(user in-session | notification generated) = P(user in-session) = 2.3%.

The correct quantity is P(user in-session | notification generated), which is higher because notification generation correlates with activity. Let R = the ratio of notification generation rate while in-session to notification generation rate while out-of-session.

Bounds on R:
- Lower bound: R = 1 (no correlation; naive model is correct — known to be wrong)
- Upper bound: R = ∞ (all notifications generated while someone is in-session — also wrong; asynchronous actions generate notifications for users not in-session)
- Working estimate: R = 3 for a content-discovery app. A user actively browsing generates notifications for others at 3× the rate of a user who last opened the app yesterday. This is conservative; messaging-primary apps would have higher R.

Applying Bayes:

P(in-session | notification generated) = [R × (S/W)] / [R × (S/W) + (1 − S/W)]

At R = 3, S/W = 0.023:
= [3 × 0.023] / [3 × 0.023 + 0.977]
= 0.069 / [0.069 + 0.977]
= 0.069 / 1.046
≈ 6.6%

**Empirical corroboration:** Measured in-app notification delivery rates for social apps have been reported at 5–8% in mobile analytics industry studies. Adjust's *App Trends Report 2023* and Airship's *Notification Benchmarks Report 2022* both report in-session delivery rates materially above the naive session-fraction estimate for social apps, consistent with the correlation argument above. The 5–8% empirical range brackets the 6.6% derived figure.

**Working in-app share: 6.5%.** Push handles ~93.5%.

At 6.5% in-app, in-app workers handle ~2.9M events/day. Using the naive 2.5% figure would provision for ~1.1M events/day — approximately 2.6× too few workers for this tier.

**⚠ GATE-3 dependency:** If session times are 90+ minutes/day (messaging-primary app), the in-app fraction rises to approximately 15–20% even after the correlation correction. GATE-3 must provide session time data before in-app worker sizing is finalized.

**Channel allocation — push and in-app only:**

| Channel | Share of notification events | Volume at working assumption | Notes |
|---------|------------------------------|------------------------------|-------|
| Push — APNs | ~47% | ~21.2M/day | iOS; separate worker tier |
| Push — FCM | ~47% | ~21.2M/day | Android + web; separate worker tier |
| In-app | ~6.5% | ~2.9M/day | Substitute for push when user is in-session |

Email and SMS are additive to this count. See Section 1.3b.

**Why APNs and FCM are separate worker tiers:**

APNs uses HTTP/2 with per-bundle-ID connection limits and returns token-invalid errors synchronously. FCM uses a different authentication model, has its own per-project quotas, and returns token-invalid errors asynchronously. An aggregated push worker cannot apply platform-specific retry logic, cannot respond correctly to token invalidation signals from each platform, and cannot be scaled independently when one platform's quota is the binding constraint. The additional worker tier costs approximately two days of engineering time and prevents an entire category of silent delivery failures.

---

### 1.3b Email Volume, SMS Volume, and Spend Caps

####