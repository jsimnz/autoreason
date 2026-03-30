# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Version 3

---

## Preamble

**What this document claims:** A workable notification system design for the stated constraints, with explicit assumptions, derivations, and sensitivity bounds.

**What this document does not claim:** Pre-launch empirical validation of volume assumptions. Several inputs — DAU/MAU ratio, notifications per active user per day, fan-out distribution, geographic SMS distribution — are structural assumptions. The arithmetic makes those inputs visible and the consequences of being wrong calculable.

**Revision notes (Version 3):** This version addresses eleven problems identified in the second review.

1. **Gate enforcement mechanism:** The gate register now specifies what happens when a gate item is not resolved on time — not as a consequence of a team lead's voluntary action, but as a structural constraint on the project plan. Gates that miss their deadline automatically shift the project into a defined hold state with specific work items suspended. This is described in Section 0.2.

2. **Working assumption stress level:** The working assumption (30% DAU/MAU, 15/day) sits at the ⚠ threshold. This is treated as a problem requiring resolution, not a display of honesty. The provisioned floor is recalculated upward to provide genuine margin at the working assumption. Section 1.2 and 1.4 are updated accordingly.

3. **Section 1.4 is now present:** The 6× peak factor is derived from first principles using a diurnal load model. The derivation is written out in full in Section 1.4.

4. **Sensitivity table borderline cases:** Cells within 5% of a flag boundary are marked with a secondary indicator (⚠→) to signal proximity to the next threshold. Guidance for borderline cases is added to Section 1.2.

5. **Email volume section is completed:** Section 1.3b now contains a complete email volume model, opt-in population sizing, and provider contract implications. The truncated sentence is repaired.

6. **SMS spend cap for Configuration C is calculated:** Section 1.3b now contains explicit spend cap figures for all three configurations, including the two-phase cap for Configuration C.

7. **In-app fraction derivation:** The correction from 2.5% to 6.5% is now derived using a specific activity-correlation model rather than asserted from a range. The derivation is in Section 1.3a.

8. **Citation problem:** The Airship citation is replaced with a description of the structural argument and a clear statement that no single published source is cited for the specific figure. The figure is derived; the citations are supporting context only.

9. **Staffing constraint is stress-tested:** Section 5 now contains an explicit engineering budget analysis showing which components can be built in six months with four engineers, which must be deferred, and what the deferral costs.

10. **Escalation threshold:** The 80% threshold is replaced with a threshold defined against a fixed provisioned number that is locked at design time and changed only through a documented revision process. Section 4.2 is updated.

11. **GATE-2 and GATE-3 sequential dependency:** GATE-3's deadline is moved to Week 2 of Month 2, with explicit dependency notation. The reanalysis window is built into the project schedule. Section 0.2 and the gate register are updated.

---

## 0. Gate Items and Enforcement

### 0.1 What Gates Are

Gates are decisions that block specific work items. They are not advisory checkpoints. If a gate is not resolved by its deadline, the work items that depend on it stop. This is not a consequence of someone choosing to enforce the gate — it is a consequence of the work items being genuinely impossible to complete correctly without the gate input. The gate register formalizes this dependency so that the project plan reflects reality.

### 0.2 Enforcement Structure

**The enforcement mechanism is the project plan, not a person's authority.** Each gate item has a list of work items that cannot proceed without it. If a gate misses its deadline:

1. The dependent work items are moved to a formal hold state in the project tracker.
2. The project schedule is recalculated from the date the gate resolves, not from the original deadline.
3. If recalculation produces a launch date beyond the six-month window, the scope reduction options listed in Section 5.3 activate automatically — no decision required.

The team lead does not have discretion to proceed with held work items on the basis of a verbal commitment or a likely resolution. The hold lifts when the gate item is recorded in the runbook repository with the required sign-off. This is the only mechanism.

**Why this is more robust than authority-based enforcement:** A team lead can be pressured to accept a verbal commitment. A project tracker that marks work items as blocked cannot. The gate system's value is that it makes the cost of an unresolved decision visible in the schedule immediately, which creates organizational pressure on the decision-maker rather than on the team lead.

### 0.3 Gate Items Register

| Gate ID | Decision | Owner Role | Hard Deadline | Dependent Work Items (held if missed) | Scope Reduction if Unresolved at Week 6 |
|---------|----------|------------|---------------|---------------------------------------|----------------------------------------|
| GATE-1 | Email opt-in posture: default-on vs. default-off | Named product owner | Week 4, Month 1 | Email worker sizing; provider contract; IP warm-up schedule; GATE-1-dependent spend caps | Defer email channel to post-launch v1.1; push/in-app/SMS launch without email |
| GATE-2 | App type: messaging-primary vs. content-discovery | Named product owner | Week 4, Month 1 | Notifications-per-user figure lock; all worker sizing dependent on that figure | Use 20/day as conservative upper bound; size for that figure; accept over-provisioning cost |
| GATE-4 | SMS 2FA configuration: A, B, or C | Named product owner + security lead | Week 4, Month 1 | SMS spend cap; SMS worker sizing; authenticator app integration if C | Default to Configuration A (SMS-only, no authenticator nudge); accept higher SMS cost |
| GATE-3 | Session time data: average session minutes per DAU per day | Named analytics owner | Week 2, Month 2 | In-app worker sizing (final); in-app fraction lock | Use 8% in-app fraction (upper bound of range); size in-app workers for that figure |
| GATE-5 | SMS 2FA default and nudge timeline (required only if GATE-4 resolves as C) | Named security lead | Week 2, Month 2 | Configuration C launch-period spend cap; authenticator nudge implementation | If unresolved, treat Configuration C as Configuration B for spend cap purposes; log as known underestimate |

**Sequential dependency note:** GATE-3 depends on GATE-2. If GATE-2 resolves as messaging-primary, session time data must be reinterpreted under a messaging-primary model before GATE-3 can close. GATE-3's deadline is therefore set two weeks after GATE-2's deadline, not concurrently. GATE-2 must resolve by Week 4 of Month 1. GATE-3 must resolve by Week 2 of Month 2. If GATE-2 misses its deadline, GATE-3's deadline shifts by the same amount.

**Owner role assignment:** The team lead is responsible for recording the name of the person filling each owner role in the runbook repository by the end of Week 2 of Month 1. This is itself a trackable task in the project plan. If it is not completed, GATE-1 through GATE-4 are treated as unresolved as of their deadlines, and the dependent work items are held.

---

## Executive Summary

This design handles approximately 45–60M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application. The provisioned floor is set at **5,200/sec** — sized to provide genuine margin at the working assumption rather than sitting at its boundary.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned floor raised to 5,200/sec | Working assumption (521/sec sustained) × 6× peak factor = 3,126/sec peak. Prior floor of 4,200/sec provided only 34% headroom above this. New floor provides 66% headroom, accommodating the working assumption comfortably and remaining valid through the 30% DAU/MAU, 20/day scenario (4,167/sec peak) without re-sizing |
| Peak factor 6×, derived in Section 1.4 | Derived from diurnal load model; not asserted |
| Working assumption (30% DAU/MAU, 15/day) flagged as stressed baseline | The working assumption sits above the 70% threshold. This is a problem, addressed by raising the provisioned floor, not a display of analytical honesty |
| APNs and FCM as separate worker tiers | Distinct rate limits, token invalidation behaviors, failure modes; aggregate modeling masks platform-specific bottlenecks; ~2 days engineering cost |
| In-app fraction derived at 6.5% using activity-correlation model | Derivation in Section 1.3a; not asserted from external range |
| Email volume is additive to push/in-app | Different mechanism, different population base, different timescale; full model in Section 1.3b |
| SMS spend cap calculated for all three configurations | Full derivation in Section 1.3b; Configuration C is two-phase |
| Single escalation threshold at 80% of a fixed provisioned number | The provisioned number is locked at design time and changed only through a documented revision; threshold is unambiguous because the reference number is stable |
| GATE-2 before GATE-3, with two-week gap | Sequential dependency acknowledged; reanalysis window built into schedule |
| Four-engineer, six-month constraint stress-tested | Section 5 contains explicit engineering budget; three components are deferred to post-launch |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook circa 2012) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude Mobile Benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z Consumer Benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It is not a conservative assumption — the sensitivity table shows it produces a stressed baseline at the working notifications-per-user figure. The provisioned floor is set to accommodate this without sitting at the boundary.

---

### 1.2 Notifications Per Active User Per Day

**Source and limitations:** The Braze 2023 Mobile Marketing Report reports aggregate median notification volumes across app categories. The aggregate figure for social apps is approximately 15–20 notifications/day for active users. Braze does not segment this by app subtype within the social category in the published report. The 15/day working figure is selected as the low end of this aggregate range, on the assumption that this app is content-discovery-primary pending GATE-2 confirmation. If GATE-2 confirms messaging-primary orientation, revise to 20–25/day before finalizing worker sizing.

**⚠ GATE-2 dependency:** This figure cannot be confirmed without GATE-2 resolution.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/active user/day | Notifications/day | Sustained average |
|------------------------------|------------------|------------------|
| 10 | 30M | ~347/sec |
| **15** | **45M** | **~521/sec** |
| 20 | 60M | ~694/sec |
| 25 | 75M | ~868/sec |

**Flag criteria:**

The provisioned floor is set at 5,200/sec. The implied sustained average at that floor (dividing by the 6× peak factor) is 5,200 ÷ 6 = 867/sec.

- ✓: Sustained average below 70% of 867/sec = below 607/sec. Peak demand is comfortably within provisioned floor.
- ⚠: Sustained average between 607/sec and 867/sec. Peak demand approaches provisioned floor; re-sizing review triggered before this scenario is reached.
- ✗: Sustained average above 867/sec. Peak demand exceeds provisioned floor at 6× peak factor; re-sizing required before reaching this scenario.
- ⚠→ appended to any cell within 5% of the next flag boundary, indicating proximity to threshold change.

**Combined sensitivity — sustained average in req/sec:**

| DAU/MAU | 10/day | 15/day | 20/day | 25/day |
|---------|--------|--------|--------|--------|
| 20% | ~231 ✓ | ~347 ✓ | ~463 ✓ | ~579 ✓⚠→ |
| 30% | ~347 ✓ | **~521 ✓** | ~694 ⚠ | ~868 ✗ |
| 40% | ~463 ✓ | ~694 ⚠ | ~926 ✗ | ~1,157 ✗ |
| 45% | ~521 ✓ | ~781 ⚠ | ~1,042 ✗ | ~1,302 ✗ |

**Note on the working assumption cell:** At the raised provisioned floor of 5,200/sec, the working assumption (30% DAU/MAU, 15/day, ~521/sec sustained) is now ✓. Peak demand at this scenario is 521 × 6 = 3,126/sec, which is 60% of the 5,200/sec floor — providing 40% headroom. The working assumption is no longer a stressed baseline.

**Borderline case guidance:** Any cell marked ⚠→ (within 5% of the next boundary) should be treated as the higher flag category for planning purposes. The 20% DAU/MAU, 25/day cell at ~579/sec is 4.7% below the 607/sec ⚠ threshold; treat as ⚠ for planning.

---

### 1.3a Channel Split — Push and In-App

Push and in-app are substitutes at the event level. A single notification event is delivered via in-app if the target user is in-session at delivery time, and via push otherwise.

**Why the naive session-fraction model understates in-app share:**

The naive model assumes notification events are uniformly distributed across the active window. This is structurally wrong. Notification events on a social app are generated by user actions: likes, comments, shares, follows. These actions are concentrated when users are actively engaged with the app. A user posting content at 8pm generates notifications for their followers — who are disproportionately also active at 8pm, because social app usage is time-correlated across a social graph. The naive model treats notification generation as independent of session state; it is not.

**Deriving the correction:**

Let:
- S = average session minutes per DAU per day = 22.5 minutes (midpoint of the 20–25 minute range for content-discovery apps; pending GATE-3)
- W = active window = 960 minutes (16 hours)
- Naive fraction = S/W = 22.5/960 = 2.3%

The naive model assumes P(user in-session | notification generated) = P(user in-session) = 2.3%.

The correct model requires P(user in-session | notification generated), which is higher because notification generation correlates with activity. Specifically:

Let R = the ratio of notification generation rate while in-session to notification generation rate while out-of-session. On a social app, a user is significantly more likely to generate notifications for others while they are actively posting. R is not directly measurable without app-specific data, but it can be bounded:

- Lower bound: R = 1 (no correlation; naive model is correct). This is the assumption we know is wrong.
- Upper bound: R = ∞ (all notifications generated while someone is in-session). This is also wrong; asynchronous actions (scheduled posts, delayed reactions) generate notifications for users who are not in-session.
- Working estimate: R = 3. This means a user in-session generates notifications for others at 3× the rate of a user out-of-session. This is a conservative estimate of activity correlation for a content-discovery app; messaging-primary apps would have higher R.

Using Bayes:

P(in-session | notification generated) = P(notification generated | in-session) × P(in-session) / P(notification generated)

= R × (S/W) / [R ×