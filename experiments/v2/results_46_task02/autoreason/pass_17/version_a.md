# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Document

This design synthesizes two prior drafts. Both made genuine progress on different problems. Version X produced the cleaner idempotency architecture, escalation ladder, and spare capacity reasoning. Version Y produced the stronger fan-out model, SMS cap redesign, and notification-rate sensitivity treatment. This document takes the strongest elements of each.

**What this document does not claim:** Several inputs — particularly the viral cohort volume share, fan-out parameters, and notifications/DAU/day rate — are structural assumptions without pre-launch empirical validation. The arithmetic makes those inputs visible and the consequences of being wrong calculable. Sections carrying material uncertainty are marked ⚠. Section 1.5 defines measurement triggers for every major assumption that drives infrastructure sizing.

The revision table is not a completeness guarantee. It is an index of what was attempted. Problems introduced by this document are flagged inline.

---

## Executive Summary

This design handles approximately 50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU at 30% with explicit 20–45% sensitivity range | Single most load-bearing ratio input; sizing shows consequences across full range |
| 17 notifications/DAU/day with explicit 10–25 sensitivity range | Multiplicatively equivalent to DAU/MAU; receives equivalent sensitivity treatment |
| Channel split treated as a range, not a point estimate | Push/in-app balance unknown pre-launch; worker table shows re-sizing triggers |
| Channel-specialized workers for all four channels | Head-of-line blocking applies to any channel pair with mismatched latency profiles; consistency requires separation across all pairs |
| Fan-out modeled by notification type, not aggregate multiplier | Aggregate figures conflate types with different mechanics; reshares are the only high-fan-out event type |
| SMS spend cap tiered by 2FA product configuration | Single cap calibrated against uncertain assumption is wrong on day one if assumption is wrong; this is a pre-launch product decision |
| Escalation ladder: alert → scale → shed → incident | Thresholds ordered so each tier fires before the next is needed; arithmetic shown |
| Spare capacity allocated by channel to specific failure modes | Cross-channel spare is useless in a channel-specialized architecture |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs/FCM connection failures |

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio — Sensitivity Analysis

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook 2012 era) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude mobile benchmarks 2023 |
| New social apps in growth phase | 20–35% | a16z consumer benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It is conservative for a growing app — it assumes a meaningful dormant account base. If the app is in early growth with a highly engaged core, 30% may understate DAU.

---

### 1.2 Notifications Per DAU Per Day — Sensitivity Analysis

The notifications/DAU/day figure multiplies the same sizing cascade as the DAU/MAU ratio. Prior drafts treated it as a constant. It is not, and it deserves equivalent scrutiny.

**Basis for the 17/day working figure:** The Braze 2023 Mobile Marketing Report reports a median of 15–20 notifications/day for active users of social apps. The 17/day working figure sits at the midpoint. "Social apps" in Braze's taxonomy includes messaging-heavy apps (which inflate the figure) and content-consumption apps (which deflate it). An app with a strong direct-messaging feature will sit at the high end; an app focused on content discovery with limited social graph interaction will sit at the low end.

**Critical distinction from DAU/MAU:** The DAU/MAU ratio can be measured from existing user data before launch. The notifications/day rate depends on product feature set, social graph density, and engagement patterns that may not be known until the app has been live for 30–60 days. This figure carries more uncertainty than the DAU/MAU assumption.

**Sizing consequences at 30% DAU/MAU (3M DAU):**

| Notifications/DAU/day | Notifications/day | Sustained inbound | Push workers needed | Notes |
|----------------------|------------------|------------------|-------------------|-------|
| 10 | 30M | ~1,040/sec | ~10 | Minimal social graph; low engagement |
| **17** | **~50M** | **~1,750/sec** | **~17** | **Working assumption** |
| 20 | 60M | ~2,080/sec | ~20 | High engagement, strong DM feature |
| 25 | 75M | ~2,600/sec | ~25 | Messaging-dominant app |

**Combined sensitivity (DAU/MAU × notifications/day) — sustained inbound in req/sec:**

| DAU/MAU | 10/day | 17/day | 25/day |
|---------|--------|--------|--------|
| 20% | ~580 | ~990 | ~1,450 |
| 30% | ~1,040 | **~1,750** | ~2,600 |
| 40% | ~1,390 | ~2,360 | ~3,470 |
| 45% | ~1,560 | ~2,650 | ~3,910 |

The provisioned floor of ~1,800/sec (derived in Section 1.4) is adequate through the 30% DAU/MAU, 17/day midpoint. At 40% DAU/MAU with 20/day — a plausible outcome for a successful launch — the provisioned floor is exceeded before viral effects are applied.

**Section 1.5 triggers:**
- If DAU/MAU exceeds 38% at 60 days post-launch, push worker count is reviewed.
- If measured notifications/DAU/day exceeds 20 at 30 days post-launch, worker sizing is reviewed against the 25/day column.

---

### 1.3 Channel Split — Derivation and Uncertainty

The channel split determines per-channel worker allocation. It is a structural assumption, not a measured fact pre-launch.

**Basis for working split:**

*Push (APNs + FCM):* The default delivery channel when the user is not in-app. On a mobile-first social app, the majority of notification events target users who are not currently in the foreground. The 70% figure assumes 70% of events target non-foreground users, consistent with Airship's 2023 push benchmark for social apps (65–75% range).

*In-app:* Notifications delivered to users actively using the app. The channel split model is used directly here rather than deriving from concurrent session counts. The rationale: concurrent session counts tell you how many users *could* receive in-app notifications, not how many notification events are *routed* to in-app delivery. Routing is determined by whether the user has the app in the foreground at the moment the event fires — a property of the event-user pair, not the aggregate session count. The concurrent session model is decorative in this context and is retired. The 20% in-app share reflects the estimated foreground-session fraction of total notification events; in-app delivery substitutes for push when the user is in the foreground.

*Email:* Digest and transactional notifications. Typically opt-in; lower volume by design. The 8% figure is consistent with SendGrid's 2022 social app benchmark (6–10% range).

*SMS:* Below 1% of total volume; derived in Section 1.3 (SMS).

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

SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows).

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

Twilio standard tier supports 20 SMS/sec per account. One SMS worker handles this volume with 65% headroom.

**SMS spend cap — tiered by 2FA product configuration ⚠**

The 8% SMS-2FA selection rate is a product decision, not a measurement. If the app defaults 2FA to SMS rather than offering authenticator apps as the primary option, this figure becomes 40–60%, multiplying SMS volume by 5–7×. A single cap calibrated against the 8% assumption is wrong on day one if that assumption is wrong. **This is a decision that must be made before the system launches.**

At Twilio long-code rates (~$0.0079/SMS):
- 8% SMS-2FA: ~47,000/day → ~$371/day
- 50% SMS-2FA: ~200,000/day → ~$1,580/day

**Two-tier cap design:**

| 2FA configuration | Daily volume estimate | Cap setting | Margin above baseline |
|------------------|----------------------|-------------|----------------------|
| Authenticator-first (8% SMS selection) | ~47,000/day | $500/day | ~35% |
| SMS-default 2FA (50% SMS selection) | ~200,000/day | $2,000/day | ~25% |

**Cap margin and peak factor:** The 13× peak factor applied to the $371/day baseline produces ~$4,800/day — well above either cap. This must be stated clearly: **the spend cap is not designed to accommodate a 13× security event spike. It is designed to catch runaway notification loops before they become billing events.** A legitimate 13× spike (e.g., a credential stuffing attack triggering mass password reset flows) will hit the cap and require manual intervention. The on-call runbook must include a procedure for temporarily raising the cap during verified security incidents. The cap's 25–35% margin provides headroom for normal day-to-day variance, not peak-factor events.

The Redis counter uses a 24-hour sliding window to avoid end-of-day reset races. It is isolated with no eviction policy.

**Pre-launch action required:** Engineering must obtain the 2FA product configuration decision before setting the day-one cap. If the decision is not made before launch, default to the SMS-default cap ($2,000/day) to avoid false positives on day one.

---

### 1.4 Burst Model and Worker Sizing

#### Fan-Out Arithmetic — Built From First Principles ⚠

Prior drafts used an aggregate "200 notifications per engagement" fan-out figure that conflated fundamentally different notification types. A like generates at most 1 notification (to the content creator). A reshare may notify the original creator and propagate through the resharer's follower graph. These are different mechanics with different fan-out ratios, and aggregating them produces a figure that is neither derivable nor verifiable.

**Fan-out by notification type:**

| Event type | Who is notified | Fan-out per event | Notes |
|------------|----------------|------------------|-------|
| Like on post | Content creator only | 1 | No follower fan-out |
| Comment on post | Content creator + prior commenters (capped) | 1–15 | Cap prevents notification spam |
| Mention in comment | Mentioned user only | 1 | |
| Reshare/repost | Original creator (1) + resharer's followers (F) | 1 + F | F = resharer's follower count |
| Follow | Followed user only | 1 | |
| Direct message | Recipient only | 1 | |

**The reshare is the only event type with significant fan-out.** A reshare from a user with 10,000 followers generates ~10,001 notifications. All other event types generate O(1) to O(tens) of notifications per event.

**Revised viral spike model:**

```
Total notifications from viral event =
  (likes × 1)
  + (comments × avg_comment_fanout)
  + (reshares × (1 + avg_resharer_followers))
```

For a **moderate viral event** (realistic for a 10M MAU platform, occurring over 15 minutes):

```
Likes:    30,000 × 1         =    30,000
Comments:  8,000 × 5         =    40,000
Reshares:  2,000 × (1 + 800) = 1,602,000
Total:                       ~1,672,000 notifications
Platform-wide rate: 1,672,000 / 900 sec = ~1,858/sec
```

For a **large viral event**:

```
Likes:   150,000 × 1           =    150,000
Comments: 40,000 × 5           =    200,000
Reshares: 10,000 × (1 + 2,000) = 20,010,000
Total:                         ~20,360,000 notifications
Platform-wide rate: ~22,600/sec
```

**Inbound rate estimates:**

| Scenario | Platform-wide notification rate | Notes |
|----------|--------------------------------|-------|
| Base (no viral event) | ~1,750/sec | Working assumption from Section 1.2 |
| Base + moderate viral event | ~3,600/sec | Additive; moderate viral overlaid on base |
| Base + large viral event | ~24,350/sec | Large viral; shedding is active |

The large viral event is not the planning figure — it is the incident-response scenario. The provisioned floor is designed for the base case. The escalation ladder (Section 3) handles the transition.

**⚠ Uncertainty note:** The reshare fan-out model is sensitive to the distribution of resharer follower counts. A platform where reshares are concentrated among high-follower accounts produces dramatically higher notification rates than a platform where reshares are evenly distributed. The avg_resharer_followers figure (800 for moderate, 2,000 for large) is an assumption, not a measurement. The large viral event arithmetic should be treated as an order-of-magnitude estimate, not a precise figure.

---

#### Channel-Specialized Workers — Consistent Application

The head-of-line blocking argument for separating email from push applies to any channel pair with mismatched latency profiles. Consistency requires separation across all pairs.

**Latency profiles by channel operation:**

| Channel | Operation | Latency range | Uncertainty |
|---------|-----------|--------------|-------------|
| Push (APNs/FCM) | HTTP/2 dispatch initiation | 1–10ms | Low; well-documented |
| In-app | Redis pipeline write | 0.5–5ms | Low; local network |
| Email | SMTP handshake + relay acceptance | 80–400ms | High; relay load and network conditions vary significantly |
| SMS | Twilio API call + carrier acceptance | 100–500ms | Medium; carrier routing introduces variability |

**Why separation is required for all pairs:** If email and push share a worker pool, a 300ms SMTP handshake blocks the worker thread for the duration. At 1,750/sec in