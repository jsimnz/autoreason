# Notification System Design — Revised (v3)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Revision

Ten problems were identified in the prior draft. This revision addresses each directly.

| # | Problem | Disposition |
|---|---------|-------------|
| 1 | 30% DAU/MAU assumption is load-bearing and unjustified | Replaced with sourced range; sensitivity table added; sizing shows consequences of being wrong |
| 2 | 70/8/20 channel split asserted without derivation | Derivation added; split treated as a range with worker-count consequences shown |
| 3 | In-app worker capacity functionally unconstrained and concealed | In-app arithmetic shown explicitly; elevated/high scenario behavior analyzed |
| 4 | Section 1.3 cut off mid-sentence | Section 1.3 completed; 7/sec figure now has visible derivation |
| 5 | Shedding trigger thresholds internally inconsistent | Escalation ladder redesigned; ordering corrected and explained |
| 6 | "2 spare" workers have no principled basis | Spare capacity redesigned by channel with explicit failure modes |
| 7 | Viral spike multiplier mixes incompatible units | Calibration rewritten; engagement count and per-user rate ratio connected explicitly |
| 8 | Email head-of-line argument proves too much | Argument extended consistently to all channel pairs; in-app latency analyzed |
| 9 | Idempotency architecture mentioned but never specified | State machine specified: states, transitions, failure cases |
| 10 | Honest uncertainty applied selectively | SMTP latency range added; uncertainty treatment made consistent across all latency figures |

---

## Executive Summary

This design handles approximately 50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application with a 4-engineer team over 6 months.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU at 30% with explicit 20–45% sensitivity range | Single most load-bearing input; sizing shows consequences across full range |
| Channel split treated as a range, not a point estimate | Push/in-app balance is unknown pre-launch; worker table shows re-sizing triggers |
| Channel-specialized workers for all four channels | Head-of-line blocking applies to any channel pair with mismatched latency profiles; consistency requires separation across all pairs |
| Provisioned delivery floor at ~1,800/sec via per-channel worker arithmetic | Derived from per-channel contributions; not a single multiplier |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures; specified in Section 4 |
| Escalation ladder: alert → scale → shed → incident | Thresholds ordered so each tier fires before the next is needed; no gap between alert and shedding |
| Spare capacity allocated by channel to specific failure modes | Channel-specialized architecture means cross-channel spare is useless; spare is channel-specific |
| SMS spend counter in isolated Redis with no eviction | Closes race condition on spend cap enforcement |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. Section 1.5 defines re-sizing triggers and validation paths for every major assumption that drives infrastructure sizing.

---

## 1. Scale Assumptions and Constraints

### 1.1 DAU/MAU Ratio — Sensitivity Analysis

The DAU/MAU ratio is the first multiplier in the sizing cascade. Every downstream figure — worker count, queue depth, Redis memory, spend caps — scales with it. It receives explicit treatment here.

**Published reference points:**

| Platform type | DAU/MAU range | Source |
|--------------|--------------|--------|
| Mature social networks (Facebook 2012 era) | 50–60% | Meta investor filings |
| Mid-tier social apps (Discord, Snapchat disclosed figures) | 30–40% | Public earnings disclosures |
| Apps with significant dormant account bases | 15–25% | Amplitude mobile benchmarks 2023 |
| New social apps in growth phase | 20–35% | Andreessen Horowitz consumer benchmark 2022 |

**Working assumption: 30%.** This sits at the lower end of the mid-tier range, which is conservative for a growing app — it assumes a meaningful dormant account base. If the app is in early growth with a highly engaged core, 30% may understate DAU.

**Sizing consequences across the plausible range:**

| DAU/MAU | DAU | Notifications/day (17/DAU) | Sustained peak inbound | Push workers needed |
|---------|-----|--------------------------|----------------------|-------------------|
| 20% | 2M | ~34M | ~1,180/sec | ~12 |
| **30%** | **3M** | **~50M** | **~1,750/sec** | **~17** |
| 40% | 4M | ~68M | ~2,360/sec | ~22 |
| 45% | 4.5M | ~76M | ~2,650/sec | ~25 |

The 30% assumption produces a worker count that is adequate through 40% DAU/MAU without re-sizing. At 45%, the provisioned floor is reached and scaling is needed before viral effects are applied. Section 1.5 defines the measurement trigger: if DAU/MAU exceeds 38% at 60 days post-launch, the push worker count is reviewed.

The 17 notifications/DAU/day figure is an engaged-user benchmark from Braze's 2023 mobile marketing report for social apps. The sensitivity of this figure is analyzed in Section 1.5.

---

### 1.2 Channel Split — Derivation and Uncertainty

The channel split determines per-channel worker allocation. It is not a fact pre-launch; it is a structural assumption that should be measured and revised.

**Basis for working split:**

*Push (APNs + FCM):* Push notifications are the default delivery channel for mobile social apps when the app is not in the foreground. On a mobile-first social app, the majority of users are accessing via mobile. The 70% figure assumes that 70% of notification events target users who are not currently in-app. This is consistent with published figures from Airship's 2023 push benchmark report for social category apps (65–75% range).

*In-app:* In-app notifications reach users who are actively using the app. At 30% DAU/MAU, approximately 3M users are active daily, but they are not all simultaneously in-app. Concurrent session rate for social apps is typically 5–15% of DAU. At 10% concurrent sessions, ~300K users are in-app at any moment, receiving in-app notifications. The 20% in-app share reflects that in-app events are a subset of total events, not a supplement to push — a user receiving a push notification while in-app receives in-app instead. This substitution is the mechanism that keeps in-app at 20% rather than higher.

*Email:* Digest emails and transactional notifications (password reset, account alerts). Email is typically opt-in on social apps and has lower volume than push by design. The 8% figure is consistent with SendGrid's 2022 social app benchmark (6–10% range).

*SMS:* Derived separately in Section 1.3. At 7/sec sustained, SMS is below 1% of total volume.

**Working split and sensitivity:**

| Channel | Working split | Plausible low | Plausible high | Consequence of high end |
|---------|--------------|--------------|----------------|------------------------|
| Push | 70% | 55% | 75% | At 55%, 4 fewer push workers needed; in-app workers increase |
| In-app | 20% | 15% | 35% | At 35%, single in-app worker hits ceiling at elevated inbound |
| Email | 8% | 5% | 12% | At 12%, 4th email worker needed |
| SMS | <1% | — | — | Worker count unchanged |

**The critical sensitivity:** If in-app share reaches 35% (plausible for an app with strong web presence or high concurrent session rates), the single in-app worker at 3,000/sec handles 6,200/sec × 35% = 2,170/sec — still within capacity at base inbound, but within 30% of the ceiling before viral effects. Section 1.5 defines the trigger: if in-app share exceeds 28% at 30 days post-launch, a second in-app worker is provisioned.

---

### 1.3 SMS Volume Derivation

SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, etc.).

**SMS use cases:**

| Use case | Volume derivation | Daily volume |
|----------|------------------|-------------|
| Phone number verification (registration) | 10M MAU × 1% monthly growth / 30 days × 60% phone verification rate | ~2,000/day |
| Two-factor authentication (login) | 3M DAU × 15% 2FA enrollment × 8% SMS-2FA selection (vs. authenticator app) | ~36,000/day |
| Critical account alerts (password reset, suspicious login) | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| **Total** | | **~47,000/day** |

```
47,000/day ÷ 86,400 sec/day = ~0.54/sec sustained average
Peak factor (security events cluster at login peaks): 12–15×
Peak rate: ~0.54 × 13 = ~7/sec
```

This is the 7/sec figure used in the worker table. Twilio standard tier supports 20 SMS/sec per account, so one SMS worker handles this volume with 65% headroom.

**SMS spend cap basis:**

At Twilio's standard long-code rate of ~$0.0079/SMS:
```
47,000/day × $0.0079 = ~$371/day → ~$11,100/month
```

At Twilio's short-code rate (~$0.005/SMS for high-volume):
```
~$235/day → ~$7,050/month
```

The spend cap in the Redis counter is set at $500/day (35% above the long-code daily estimate) to catch runaway loops before they become billing events, while leaving headroom for legitimate security event spikes. The counter uses a 24-hour sliding window, not a calendar day, to avoid end-of-day reset races.

**2FA assumption sensitivity:** The 8% SMS-2FA selection rate is the most uncertain figure here. If the app defaults 2FA to SMS rather than offering authenticator apps as the primary option, this could be 40–60%, multiplying SMS volume by 5–7×. At 60% SMS-2FA, daily volume reaches ~200,000 SMS/day (~$1,580/day at long-code rates). The spend cap and worker count would both require revision. Section 1.5 defines the trigger: if SMS volume exceeds 100,000/day at 30 days post-launch, the 2FA enrollment flow is reviewed.

---

### 1.4 Burst Model and Worker Sizing

#### Viral Spike Multiplier — Corrected Calibration

The prior draft defined the multiplier as "the ratio of spike-period notification rate to a user's baseline rate" but calibrated it against platform-level engagement counts. These are different units. The correction connects them explicitly.

**The multiplier is a per-user rate ratio:**
```
Multiplier = (spike-period notification rate for cohort user) / (baseline notification rate for cohort user)
```

**Connecting platform engagement counts to per-user rate:**

A viral event generating E engagements in T minutes on a platform with F average followers per viral account produces:
```
Notification rate = (E / T) × (fan-out per engagement) notifications/minute
```

For a piece of content receiving 50,000 engagements in 15 minutes with average fan-out of 200 notifications per engagement (likes notifying the content creator, comments notifying followers, reshares notifying resharer's followers):

```
Notification rate = (50,000 / 15 min) × 200 = 666,667 notifications/min = ~11,111/sec platform-wide
```

This platform-wide rate is distributed across users. The cohort of top-5% users (150,000 users) who are likely to be involved in viral events (as creators, early engagers, or high-follower amplifiers) receives a disproportionate share. If the cohort receives 35% of viral event notifications:

```
Cohort notification rate during spike = 11,111/sec × 35% = ~3,889/sec across 150,000 users
Per-user spike rate = 3,889 / 150,000 = ~0.026/sec
Cohort baseline rate = 117/day / 86,400 = ~0.00135/sec
Multiplier = 0.026 / 0.00135 = ~19×
```

This is the high end of the range. For a moderate viral event (10,000 engagements in 15 minutes, fan-out 150):

```
Platform rate = (10,000 / 15) × 150 = ~1,667/sec
Cohort share (35%) = ~583/sec across 150,000 users
Per-user spike rate = 583 / 150,000 = ~0.0039/sec
Multiplier = 0.0039 / 0.00135 = ~2.9×
```

**Revised multiplier table with connected arithmetic:**

| Event scale | Platform-level engagements in 15 min | Per-user multiplier (derived) |
|------------|--------------------------------------|------------------------------|
| Small viral event | 5,000–10,000 | 1.4–2.9× |
| Moderate viral event | 10,000–50,000 | 2.9–14× |
| Large viral event | 50,000–200,000 | 14–57× |

**Working assumption: 8×.** This corresponds to approximately 20,000–25,000 engagements in 15 minutes at the assumed fan-out, which is a realistic moderate viral event for a 10M MAU platform. The large-viral-event range (14–57×) is not the planning figure — it is the incident-response scenario where shedding is active.

The 35% cohort volume share appears in both the baseline derivation and the spike multiplier derivation. This is not circular — it is the same structural assumption (the top-5% cohort receives 35% of platform notification volume) applied in two contexts. The assumption should be measured at launch; see Section 1.5.

---

#### Inbound Rate Estimates

**Base case** (working midpoint assumptions, 8× multiplier):
```
Viral cohort: 150,000 users × 0.00135/sec × 8× = ~1,620/sec
Remaining DAU: 2,850,000 × 17/day / 86,400    =   ~560/sec
Total                                           = ~2,180/sec
```

**Elevated case** (cohort 50% larger, multiplier at 12× — moderate-to-large viral event):
```
Viral cohort: 225,000 × 0.00135 × 12 = ~3,645/sec
Remaining DAU:                         =   ~560/sec
Total                                  = ~4,205/sec
```

**High case** (cohort doubled, multiplier at 19× — large viral event):
```
Viral cohort: 300,000 × 0.00135 × 19 = ~7,695/sec
Remaining DAU:                         =   ~560/sec
Total                                  = ~8,255/sec
```

The high case now uses 19× rather than 14×, derived from the corrected multiplier arithmetic above. This is a genuine large viral event on the platform, not a planning figure.

---

#### Channel-Specialized Workers — Consistent Application

The prior draft correctly identified SMTP handshake latency (100–300ms) as a head-of-line blocking problem that justifies separating email from push. A reviewer correctly noted that the same argument applies to any channel pair with mismatched latency profiles. The argument is extended consistently here.

**Latency profiles by channel operation:**

| Channel | Operation | Latency range | Uncertainty |
|---------|-----------|--------------|-------------|
| Push (APNs/FCM) | HTTP/2 dispatch initiation | 1–10ms | Low; well-documented |
| In-app | Redis pipeline write | 0.5–5ms | Low; local network |
| Email | SMTP handshake + relay acceptance | 80–400ms | **High**; see below |