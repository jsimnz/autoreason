# Notification System Design — Revised (v4)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Revision

Ten problems were identified in v3. This revision addresses each directly. Where prior revisions claimed fixes that were incomplete or introduced new problems, this document shows the work rather than describing it.

| # | Problem | Disposition |
|---|---------|-------------|
| 1 | 17 notifications/DAU/day treated as a constant with no sensitivity analysis | Sensitivity table added; figure now receives equivalent scrutiny to DAU/MAU ratio |
| 2 | Fan-out arithmetic conflates notification types; 200/engagement figure underived | Fan-out rebuilt from first principles by notification type; each type's fan-out derived separately |
| 3 | 35% cohort volume share is circular and unvalidated | Acknowledged as unvalidated structural assumption; infrastructure consequence of being wrong is now explicit |
| 4 | SMS spend cap calibrated against low-confidence assumption; wrong on day one if 2FA defaults to SMS | Cap redesigned with two tiers; day-one configuration depends on product decision that must be made before launch |
| 5 | Email latency row cut off mid-entry | Latency table completed in full |
| 6 | Concurrent session arithmetic in 1.2 not connected to in-app worker sizing | Models reconciled; one model selected with explicit rationale; the other retired |
| 7 | Escalation ladder referenced but not shown | Escalation ladder shown in full with threshold arithmetic |
| 8 | Spare capacity redesign described but not shown | Spare capacity table shown by channel with failure modes |
| 9 | $500/day spend cap does not provide headroom for stated peak factors | Cap recalibrated against the 13× peak factor used elsewhere; "headroom" claim corrected |
| 10 | Revision table creates false completeness signal | This table is not a completeness guarantee; problems introduced by this revision are noted inline |

**On the revision table itself:** This table records what was attempted, not what was achieved. Readers should treat it as an index to check, not a warranty. Where this revision introduces new uncertainties or makes assumptions that may be wrong, those are flagged in the text.

---

## Executive Summary

This design handles approximately 50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application with a 4-engineer team over 6 months.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU at 30% with explicit 20–45% sensitivity range | Single most load-bearing ratio input; sizing shows consequences across full range |
| 17 notifications/DAU/day with explicit 10–25 sensitivity range | Multiplicatively equivalent to DAU/MAU; receives equivalent sensitivity treatment |
| Channel split treated as a range, not a point estimate | Push/in-app balance is unknown pre-launch; worker table shows re-sizing triggers |
| Channel-specialized workers for all four channels | Head-of-line blocking applies to any channel pair with mismatched latency profiles |
| Fan-out modeled by notification type | Aggregate fan-out figures conflate types with different mechanics; type-level modeling is more reliable |
| SMS spend cap tiered by 2FA product configuration | Single cap calibrated against low-confidence assumption is wrong on day one if assumption is wrong |
| Escalation ladder: alert → scale → shed → incident | Thresholds ordered so each tier fires before the next is needed; arithmetic shown |
| Spare capacity allocated by channel to specific failure modes | Cross-channel spare is useless in a channel-specialized architecture |

**What this document does not claim:** Several inputs — particularly the 35% cohort volume share and the viral fan-out parameters — are structural assumptions without pre-launch empirical validation. The arithmetic makes those inputs visible and the consequences of being wrong calculable. Section 1.5 defines measurement triggers. Sections that carry material uncertainty are marked with a ⚠ symbol.

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio — Sensitivity Analysis

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook 2012 era) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude mobile benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z consumer benchmark 2022 |

**Working assumption: 30%.** Conservative for a growing app; assumes a meaningful dormant account base.

---

### 1.2 Notifications Per DAU Per Day — Sensitivity Analysis *(previously missing)*

The notifications/DAU/day figure multiplies the same sizing cascade as the DAU/MAU ratio. Prior drafts treated it as a constant. It is not.

**Basis for the 17/day working figure:**

The Braze 2023 Mobile Marketing Report reports a median of 15–20 notifications/day for users of social apps who receive at least one notification. "Social apps" in Braze's taxonomy includes messaging-heavy apps (which inflate the figure) and content-consumption apps (which deflate it). The 17/day working figure sits at the midpoint of their reported range.

**What 17/day implies structurally:** This is a per-active-user figure, not a per-account figure. It counts notifications received, not sent. On a social app, this includes likes, comments, follows, mentions, direct messages, and system events. An app with a strong direct-messaging feature will sit at the high end; an app focused on content discovery with limited social graph interaction will sit at the low end.

**This figure is uncertain in a way the DAU/MAU ratio is not.** The DAU/MAU ratio can be measured from existing user data before launch. The notifications/day rate depends on product feature set, social graph density, and engagement patterns that may not be known until the app has been live for 30–60 days.

**Sizing consequences across the plausible range (at 30% DAU/MAU = 3M DAU):**

| Notifications/DAU/day | Notifications/day | Sustained inbound | Push workers needed | Notes |
|----------------------|------------------|------------------|-------------------|-------|
| 10 | 30M | ~1,040/sec | ~10 | Minimal social graph; low engagement |
| **17** | **~50M** | **~1,750/sec** | **~17** | **Working assumption** |
| 20 | 60M | ~2,080/sec | ~20 | High engagement, strong DM feature |
| 25 | 75M | ~2,600/sec | ~25 | Messaging-dominant app |

**Combined sensitivity (DAU/MAU × notifications/day):**

| DAU/MAU | 10/day | 17/day | 25/day |
|---------|--------|--------|--------|
| 20% | ~580/sec | ~990/sec | ~1,450/sec |
| 30% | ~1,040/sec | **~1,750/sec** | ~2,600/sec |
| 40% | ~1,390/sec | ~2,360/sec | ~3,470/sec |
| 45% | ~1,560/sec | ~2,650/sec | ~3,910/sec |

The provisioned floor of ~1,800/sec (derived in Section 1.4) is adequate through the 30% DAU/MAU, 17/day midpoint. At 40% DAU/MAU with 20/day — a plausible outcome for a successful launch — the provisioned floor is exceeded before viral effects are applied. Section 1.5 defines the trigger for reviewing worker counts at 60 days post-launch.

**Section 1.5 trigger:** If the measured notifications/DAU/day exceeds 20 at 30 days post-launch, worker sizing is reviewed against the 25/day column.

---

### 1.3 Channel Split — Derivation and Uncertainty

The channel split determines per-channel worker allocation. It is a structural assumption, not a measured fact pre-launch.

**Basis for working split:**

*Push (APNs + FCM):* The default delivery channel when the user is not in-app. On a mobile-first social app, the majority of notification events target users who are not currently in the foreground. The 70% figure assumes 70% of events target non-foreground users, consistent with Airship's 2023 push benchmark for social apps (65–75% range).

*In-app:* Notifications delivered to users actively using the app. The key modeling question is whether to derive in-app volume from concurrent session counts or from the channel split directly. **This document uses the channel split model and retires the concurrent session model.** The rationale: concurrent session counts tell you how many users *could* receive in-app notifications, not how many notification events are *routed* to in-app delivery. Routing is determined by whether the user has the app in the foreground at the moment the event fires, which is a property of the event-user pair, not the aggregate session count. The channel split model captures this routing directly. The concurrent session arithmetic in prior drafts was decorative — it derived a user count that was never connected to notification volume — and is removed here.

The 20% in-app share reflects that in-app delivery substitutes for push when a user is in the foreground: a user who would receive a push notification while active instead receives an in-app notification. The 20% figure is the estimated foreground-session fraction of total notification events.

*Email:* Digest and transactional notifications. Typically opt-in; lower volume by design. The 8% figure is consistent with SendGrid's 2022 social app benchmark (6–10% range).

*SMS:* Derived in Section 1.3 (SMS). Below 1% of total volume.

**Working split and sensitivity:**

| Channel | Working split | Plausible low | Plausible high | Consequence of high end |
|---------|--------------|--------------|----------------|------------------------|
| Push | 70% | 55% | 75% | At 55%, 4 fewer push workers; in-app workers increase |
| In-app | 20% | 15% | 35% | At 35% with elevated inbound, second in-app worker needed |
| Email | 8% | 5% | 12% | At 12%, fourth email worker needed |
| SMS | <1% | — | — | Worker count unchanged |

**Trigger:** If in-app share exceeds 28% at 30 days post-launch, a second in-app worker is provisioned.

---

### 1.3 (SMS) SMS Volume Derivation

SMS is reserved for transactional and security events. It is not used for social notifications.

**SMS use cases:**

| Use case | Volume derivation | Daily volume |
|----------|------------------|-------------|
| Phone number verification | 10M MAU × 1% monthly growth / 30 days × 60% phone verification | ~2,000/day |
| Two-factor authentication | 3M DAU × 15% 2FA enrollment × 8% SMS-2FA selection | ~36,000/day |
| Critical account alerts | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| **Total** | | **~47,000/day** |

```
47,000 / 86,400 = ~0.54/sec sustained
Peak factor (security events cluster at login peaks): 12–15×
Peak rate: 0.54 × 13 = ~7/sec
```

**SMS spend cap — redesigned for 2FA configuration uncertainty ⚠**

The 8% SMS-2FA selection rate is the most uncertain figure in this section. It is a product decision: if the app defaults 2FA to SMS rather than offering authenticator apps as the primary option, this figure becomes 40–60%, multiplying SMS volume by 5–7×.

Prior drafts set a single $500/day cap calibrated against the 8% assumption and deferred the sensitivity to a 30-day post-launch trigger. This is wrong: the cap is enforced from day one, and if the product ships with SMS-default 2FA, the cap is wrong by a factor of 4–5 immediately.

**This is a decision that must be made before the system launches, not measured afterward.**

**Two-tier cap design:**

| 2FA product configuration | Daily SMS volume estimate | Cap setting | Basis |
|--------------------------|--------------------------|-------------|-------|
| Authenticator-first (8% SMS selection) | ~47,000/day | $500/day | 35% above $371/day baseline |
| SMS-default 2FA (50% SMS selection) | ~200,000/day | $2,000/day | 25% above $1,580/day baseline |

**Cap margin and peak factor reconciliation:**

The 13× peak factor from Section 1.3 applied to the $371/day baseline produces ~$4,800/day — well above either cap. This is intentional and must be stated clearly: **the spend cap is not designed to accommodate the 13× security event spike. It is designed to catch runaway notification loops before they become billing events.** A legitimate 13× security spike (e.g., a credential stuffing attack triggering mass password reset flows) will hit the cap and require manual intervention. The on-call runbook must include a procedure for temporarily raising the cap during verified security incidents. The cap's margin (25–35% above baseline) provides headroom for normal day-to-day variance in security event rates, not for peak-factor events.

The Redis counter uses a 24-hour sliding window to avoid end-of-day reset races. It is isolated with no eviction policy.

**Pre-launch action required:** Engineering must obtain the 2FA product configuration decision before setting the day-one cap. If the decision is not made before launch, the system should default to the SMS-default cap ($2,000/day) to avoid false positives on day one.

---

### 1.4 Burst Model and Worker Sizing

#### Fan-Out Arithmetic — Rebuilt From First Principles ⚠

Prior drafts used an aggregate "200 notifications per engagement" fan-out figure that conflated fundamentally different notification types. A like generates at most 1 notification (to the content creator). A comment may generate notifications to the creator and to other commenters. A reshare may notify the original creator and propagate to the resharer's followers. These are different mechanics with different fan-out ratios.

**Fan-out by notification type:**

| Event type | Who is notified | Fan-out per event | Notes |
|------------|----------------|------------------|-------|
| Like on post | Content creator only | 1 | No follower fan-out |
| Comment on post | Content creator + prior commenters (capped) | 1–15 | Platform-dependent; cap prevents spam |
| Mention in comment | Mentioned user only | 1 | |
| Reshare/repost | Original creator (1) + resharer's followers (F) | 1 + F | F = resharer's follower count |
| Follow | Followed user only | 1 | |
| Direct message | Recipient only | 1 | |

**The reshare is the only event type with significant fan-out.** A reshare from a user with 10,000 followers generates ~10,001 notifications. All other event types generate O(1) to O(tens) of notifications per event.

**Revised viral spike model:**

A viral event is characterized by high engagement volume on a single piece of content, with reshares from high-follower accounts driving secondary fan-out. The correct model is:

```
Total notifications from viral event =
  (likes × 1)
  + (comments × avg_comment_fanout)
  + (reshares × (1 + avg_resharer_followers))
```

For a moderate viral event (realistic for a 10M MAU platform):

```
Likes: 30,000 × 1 = 30,000 notifications
Comments: 8,000 × 5 = 40,000 notifications (avg 5 prior commenters notified)
Reshares: 2,000 × (1 + 800) = 1,602,000 notifications
Total: ~1,672,000 notifications
```

Occurring over 15 minutes (900 seconds):
```
Platform-wide rate: 1,672,000 / 900 = ~1,858/sec
```

For a large viral event:
```
Likes: 150,000 × 1 = 150,000
Comments: 40,000 × 5 = 200,000
Reshares: 10,000 × (1 + 2,000) = 20,010,000
Total: ~20,360,000 notifications over 15 minutes
Platform-wide rate: ~22,622/sec