# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Revision

This document synthesizes two prior drafts. Where they agreed, the shared position is stated once. Where they differed, the stronger argument is adopted and the reason given. Where both drafts contained genuine errors, the errors are corrected here.

**Material differences resolved in synthesis:**

| Issue | Version X position | Version Y position | Resolution |
|-------|-------------------|-------------------|------------|
| DAU/MAU sensitivity | Full sensitivity table with re-sizing triggers | Single 30% figure with caveats | Version X: the sensitivity table makes downstream consequences calculable |
| Viral multiplier derivation | Connected platform engagement counts to per-user rates explicitly | Acknowledged uncertainty; gave honest range | Both: explicit arithmetic from Version X with Version Y's honest uncertainty framing |
| Email head-of-line argument | Extended to all channel pairs | Rewritten around queue scheduling | Version Y: the queue scheduling argument is the correct one; Version X's extension is adopted on that corrected basis |
| APNs rate limit claim | Avoided over-claiming; set conservative throughput | Explicitly separated documented vs. observed limits | Version Y: cleaner epistemic separation |
| Auto-scaling time claim | No specific claim | Replaced 4-minute figure with honest range + shedding independence | Version Y: the shedding-independent response design is the right fix |
| SMS derivation | Explicit use-case table with 2FA sensitivity analysis | Explicit use-case table | Version X: includes the 2FA sensitivity case, which is the highest-risk assumption |

---

## Executive Summary

This design handles approximately 50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application with a 4-engineer team over 6 months.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| DAU/MAU at 30% with explicit 20–45% sensitivity range | Single most load-bearing input; downstream sizing shows consequences of being wrong |
| Channel split treated as a range, not a point estimate | Push/in-app balance is unknown pre-launch; worker table shows re-sizing triggers |
| Channel-specialized workers for all four channels | Head-of-line blocking from SMTP operations in a shared queue delays time-sensitive push dispatch; specialization eliminates cross-channel queue interference for all channel pairs with mismatched latency profiles |
| Provisioned delivery floor at ~1,800/sec via per-channel worker arithmetic | Derived by summing per-channel contributions; not a single multiplier |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures |
| Escalation ladder: alert → scale → shed → incident | Shedding engages independently of scaling status; response plan is valid whether spin-up takes 4 minutes or 12 |
| Spare capacity allocated per channel to specific failure modes | Channel-specialized architecture means cross-channel spare capacity is operationally useless |
| SMS spend counter in isolated Redis with no eviction | Closes race condition on spend cap enforcement |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. It does not make the estimates reliable. Section 1.5 defines measurement triggers and re-sizing criteria for every major assumption that drives infrastructure sizing.

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

**Working assumption: 30%.** This sits at the lower end of the mid-tier range. It assumes a meaningful dormant account base and is conservative for a growing app. If the app is in early growth with a highly engaged core, 30% may understate DAU.

**Sizing consequences across the plausible range:**

| DAU/MAU | DAU | Notifications/day (17/DAU) | Sustained peak inbound | Push workers needed |
|---------|-----|--------------------------|----------------------|-------------------|
| 20% | 2M | ~34M | ~1,180/sec | ~12 |
| **30%** | **3M** | **~50M** | **~1,750/sec** | **~17** |
| 40% | 4M | ~68M | ~2,360/sec | ~22 |
| 45% | 4.5M | ~76M | ~2,650/sec | ~25 |

The 30% assumption produces a provisioned floor that is adequate through 40% DAU/MAU without re-sizing. At 45%, provisioned capacity is reached before viral effects are applied.

**Re-sizing trigger:** If DAU/MAU exceeds 38% at 60 days post-launch, push worker count is reviewed immediately.

The 17 notifications/DAU/day figure is an engaged-user benchmark from Braze's 2023 mobile marketing report for social apps. Its sensitivity is analyzed in Section 1.5.

---

### 1.2 Channel Split — Derivation and Uncertainty

The channel split determines per-channel worker allocation. It is a structural assumption to be measured and revised, not a pre-launch fact.

**Basis for working split:**

*Push (APNs + FCM):* Push is the default delivery channel for mobile social apps when the app is not in the foreground. On a mobile-first social app, the majority of notification events target users who are not currently in-app. The 70% figure assumes exactly this, consistent with Airship's 2023 push benchmark for social category apps (65–75% range).

*In-app:* In-app notifications reach users who are actively using the app. The 20% in-app share reflects that a user receiving a push notification while in-app receives in-app instead — this substitution is the mechanism that keeps in-app at 20% rather than higher. It is not additive to push volume.

*Email:* Digest emails and transactional notifications. Email is typically opt-in on social apps, consistent with SendGrid's 2022 social app benchmark (6–10% range).

*SMS:* Derived separately in Section 1.3. Below 1% of total volume.

**Working split and sensitivity:**

| Channel | Working split | Plausible low | Plausible high | Consequence of high end |
|---------|--------------|--------------|----------------|------------------------|
| Push | 70% | 55% | 75% | At 55%, 4 fewer push workers; in-app workers increase |
| In-app | 20% | 15% | 35% | At 35%, single in-app worker approaches ceiling under elevated inbound |
| Email | 8% | 5% | 12% | At 12%, 4th email worker needed |
| SMS | <1% | — | — | Worker count unchanged |

**Critical sensitivity:** If in-app share reaches 35%, a single in-app worker at 3,000/sec handles ~2,170/sec at base inbound — within 30% of the ceiling before viral effects are applied.

**Re-sizing trigger:** If in-app share exceeds 28% at 30 days post-launch, a second in-app worker is provisioned.

---

### 1.3 SMS Volume Derivation

SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed. It is not used for social notifications (likes, comments, follows, reshares).

**SMS use cases:**

| Use case | Volume derivation | Daily volume |
|----------|------------------|-------------|
| Phone number verification (registration) | 10M MAU × 1% monthly growth / 30 days × 60% phone verification rate | ~2,000/day |
| Two-factor authentication (login) | 3M DAU × 15% 2FA enrollment × 8% SMS-2FA selection | ~36,000/day |
| Critical account alerts (password reset, suspicious login) | 3M DAU × 0.3% daily security event rate | ~9,000/day |
| **Total** | | **~47,000/day** |

```
47,000/day ÷ 86,400 sec/day = ~0.54/sec sustained average
Peak factor (security events cluster at login peaks): 12–15×
Peak rate: ~0.54 × 13 = ~7/sec
```

Twilio standard long-code rate: ~$0.0079/SMS → ~$371/day → ~$11,100/month. Spend cap set at $500/day (35% above daily estimate), using a 24-hour sliding window to avoid end-of-day reset races.

**2FA assumption sensitivity — the highest-risk figure in this section:**

The 8% SMS-2FA selection rate assumes authenticator apps are offered as the primary 2FA option and SMS is a fallback. If the app defaults 2FA to SMS, this rate could reach 40–60%, multiplying SMS volume by 5–7× and daily spend to ~$1,580/day at long-code rates. Both the spend cap and worker count would require revision.

**Re-sizing trigger:** If SMS volume exceeds 100,000/day at 30 days post-launch, the 2FA enrollment flow is reviewed and the spend cap is adjusted.

---

### 1.4 Burst Model and Worker Sizing

#### Viral Spike Multiplier — Calibrated Derivation

The multiplier is the ratio of spike-period notification rate to a user's baseline rate during a sustained 15-minute viral event.

**Connecting platform engagement counts to per-user rates:**

A viral event generating E engagements in T minutes with fan-out F (notifications per engagement) produces:

```
Platform notification rate = (E / T) × F notifications/minute
```

For a moderate viral event (20,000 engagements in 15 minutes, fan-out 200):
```
Platform rate = (20,000 / 15) × 200 = ~267,000/min = ~4,440/sec
Cohort share (top 5% of DAU, 150,000 users, receiving 35% of volume): ~1,554/sec
Per-user spike rate = 1,554 / 150,000 = ~0.0104/sec
Cohort baseline = 117/day / 86,400 = ~0.00135/sec
Multiplier = 0.0104 / 0.00135 ≈ 8×
```

**Multiplier range:**

| Event scale | Platform engagements in 15 min | Per-user multiplier |
|------------|-------------------------------|-------------------|
| Small viral | 5,000–10,000 | 2–4× |
| Moderate viral | 10,000–50,000 | 4–12× |
| Large viral | 50,000–200,000 | 12–20× |

**Working assumption: 8×.** This corresponds to a realistic moderate viral event for a 10M MAU platform. The large-viral range (12–20×) is not the planning figure — it is the incident-response scenario where shedding is active.

**Epistemic status of the 35% cohort volume share:** This is a prior assumption, not a derived figure. The range 20–50% is plausible; 35% is the midpoint for sizing. Under any assumption from 20% to 50%, the cohort baseline is 4–10× the all-user average, which means the 2× assumption in the original draft was wrong across the full range, not just at the midpoint. The 35% figure should be replaced with measurement at launch.

---

#### Inbound Rate Estimates

**Base case** (working midpoint assumptions):
```
Viral cohort: 150,000 users × 0.00135/sec × 8× = ~1,620/sec
Remaining DAU: 2,850,000 × 17/day / 86,400    =   ~560/sec
Total                                           = ~2,180/sec
```

**Elevated case** (cohort 50% larger, multiplier at 12× — moderate-to-large viral event, both primary inputs simultaneously wrong by 50%):
```
Viral cohort: 225,000 × 0.00135 × 12 = ~3,645/sec
Remaining DAU:                         =   ~560/sec
Total                                  = ~4,205/sec
```

**High case** (cohort doubled, multiplier at 19× — large viral event, inputs simultaneously wrong by 75–100%):
```
Viral cohort: 300,000 × 0.00135 × 19 = ~7,695/sec
Remaining DAU:                         =   ~560/sec
Total                                  = ~8,255/sec
```

These are not expected outcomes. They represent the range of plausible outcomes given uncertainty in the inputs. The base case is the midpoint of a wide distribution, not the expected case.

---

#### Channel-Specialized Workers — The Correct Argument

**The argument is about queue scheduling, not CPU utilization.**

In a multi-channel worker, a push notification waiting in the local dispatch queue sits behind whatever work the worker is currently executing. If the worker is mid-SMTP-handshake — which involves connection establishment, TLS negotiation, and a synchronous response from the mail relay — that push notification waits for the SMTP operation to complete. SMTP handshakes routinely take 100–400ms. APNs HTTP/2 dispatch initiation takes ~1–10ms.

This is a head-of-line blocking problem caused by mixing operations with different latency profiles in the same execution queue. The solution is not CPU allocation tuning within a shared worker — it is queue separation so that a slow SMTP operation cannot delay a time-sensitive push dispatch.

The same argument applies consistently to every channel pair with mismatched latency profiles:

| Channel pair | Faster channel latency | Slower channel latency | Head-of-line risk |
|-------------|----------------------|----------------------|------------------|
| Push vs. Email | 1–10ms (APNs dispatch) | 100–400ms (SMTP handshake) | High |
| In-app vs. Email | 0.5–5ms (Redis write) | 100–400ms (SMTP handshake) | High |
| Push vs. SMS | 1–10ms | 50–200ms (Twilio API round-trip) | Moderate |

Channel specialization also simplifies back-pressure handling: an email worker rate-limited by its SMTP relay applies back-pressure only to the email queue, not to push throughput. This isolation is operationally valuable independent of the throughput arithmetic.

**Latency uncertainty note:** SMTP handshake latency varies substantially by relay provider, network path, and relay load. The 100–400ms range is an honest estimate, not a precise measurement. The architectural argument holds across the full range — even at 100ms, the blocking risk for push is an order of magnitude worse than the APNs dispatch time.

---

#### APNs Rate Limits — Honest Statement

Apple's documentation states that a single HTTP/2 connection to APNs supports up to 1,000 concurrent streams. This is documented (APNs documentation, current as of 2024).

Apple does not publish a per-connection notification rate limit. Observed limits reported in engineering discussions and third-party push library documentation range from 500 to 1,000 notifications/sec per connection before APNs returns 429 responses. These observations vary by account tier, bundle ID, and Apple's internal policies, which change without notice. They are not a reliable design ceiling.

**Design response:** Worker throughput is set conservatively relative to CPU arithmetic, and APNs connection count is sized to remain well below any plausible rate limit. The conservative throughput figure can be validated and revised upward in load testing.

---

#### Per-Worker Throughput

**Push workers (async dispatch model):**

| Operation | Per-notification cost | Notes |
|-----------|----------------------|-------|
| ZPOPMIN batch fetch (50 items) | ~0.04ms | Amortized over batch |
| Payload serialization | ~0.10ms | |
| Idempotency write (pipelined Redis SET) | ~0.05ms | Pipelined, amortized |
| APNs dispatch initiation | ~0.05ms CPU | Non-blocking; response in separate goroutine pool |
| **Total critical-path CPU** | **~0.24ms** | |

Theoretical maximum at 0.25 vCPU: ~1,040