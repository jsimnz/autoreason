# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Five items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy (OTP-on-every-login) is **$67.5K/month ongoing** — not a spike scenario. Decision deadline: Week 2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which opted-out users may receive notifications. The estimated rate is 180–900 violations per day. This is not a threshold question for legal to assess — individual violations under CAN-SPAM, TCPA, and GDPR are each independently actionable. The sign-off required here is a binary decision: either the cache staleness window is eliminated (synchronous preference reads, with the latency cost described in Section 2.4), or this system is not legally operable as designed. Legal and product must jointly select one of the two architectures in Section 2.4 before finalization.

- **SendGrid enterprise contract (Section 1.1):** The planning basis requires 203 emails/sec at US-centric peak concentration. Standard SendGrid plans support ~27/sec. An enterprise contract supporting at least 270/sec sustained throughput is required **before launch**. Procurement must begin Week 1. If the contract is not executed by end of Month 1, the SendGrid path is abandoned and the self-hosted email path (scoped in Section 1.1) activates.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A (throttle lower-priority queues) or Default B (shed load with dead-letter queue) before this document is finalized. Default C (named escalation owner with discretion) requires a specific person named before finalization. If no person is named, Default C is not available — it does not appear as a selectable option in the finalized document.

- **Broadcast notification policy (Section 1.1 and Section 6):** The system enforces a hard cap of 100K recipients per notification job, enforced at the API validation layer (Section 6 describes the enforcement point). Push-to-all-MAU broadcasts require a separate architectural decision and are not supported by this design. A product owner must be named as the decision gate owner before launch; without a named owner, the cap is the policy with no exceptions.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### DAU/MAU Ratio

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

Planning basis: 25% DAU/MAU (2.5M DAU). Low case: 15% (1.5M DAU). High case: 35% (3.5M DAU).

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators:

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. These users cannot be reached by push or in-app, making email the primary retention channel for them. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

**Email volume sensitivity to DAU/MAU:**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Note on this table:** Email volume varies only 6% across DAU/MAU scenarios because the two components move in opposite directions under a fixed 30% re-engagement send rate. This is a consequence of holding that send rate constant — it is not a structural property of the product. If the team intends to reduce email costs as retention improves (for example, by reducing re-engagement cadence when the lapsed population shrinks), the actual re-engagement policy must be modeled explicitly. The near-flat cost observation above does not generalize beyond the 30% send-rate assumption.

#### SendGrid Throughput: Day 1 Procurement Problem

**All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).**

```
Email peak rate = (3.25M emails/day × 0.90 peak concentration) ÷ 14,400 seconds = 203 emails/sec
```

Standard SendGrid plans (highest documented standard tier: ~100K emails/hour) support approximately 27/sec. The planning basis of 203/sec exceeds this by **7.5×**. This is not a high-scenario contingency — it is a Day 1 requirement.

**Required action:** An enterprise SendGrid contract supporting at least **270 emails/sec** sustained throughput (203/sec planning basis with 33% headroom) must be procured before launch. The 35%/30 scenario produces 210/sec — within the 270/sec contract target.

**If the SendGrid contract is not executed by end of Month 1, the self-hosted email path activates.** This is not a preferred fallback — it is a real option with real costs. The self-hosted path (Postfix cluster + Amazon SES relay) is scoped here:

- **Infrastructure:** 3 Postfix MTA instances behind a load balancer; SES relay for deliverability; dedicated IP warm-up over 4 weeks.
- **Engineering cost:** Estimated 6–8 engineer-weeks to build, configure, and harden (deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring). At 4 engineers, this consumes roughly 2 months of one engineer's capacity during the window where other Month 2–3 milestones are also scheduled.
- **Operational cost ongoing:** SES pricing at ~$0.10/1K emails = ~$325/day at planning basis, versus SendGrid enterprise (pricing varies; typically $0.001–0.002/email at volume = $3,250–6,500/day). SES relay is materially cheaper but requires the team to own deliverability operations that SendGrid handles.
- **The honest assessment:** With 4 engineers and a 6-month window, absorbing 6–8 engineer-weeks on email infrastructure in Month 1–2 is possible only if another planned workstream slips. E1 must assess which workstream slips before Month 1 ends, and present that tradeoff to stakeholders explicitly if the SendGrid contract is not on track.

**Owner:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. If not executed by end of Month 1, E1 presents the self-hosted tradeoff (including the specific workstream that slips) to stakeholders within 48 hours.

#### Peak Concentration Model and International Users

**All channels use a consistent concentration assumption within a scenario.** Channels are not assumed to peak independently.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

**On international users and the US-centric assumption:** The 90% concentration assumption produces the highest peak rate and therefore the most conservative infrastructure sizing — it is worst-case for capacity planning. However, treating US-centric architecture as a safe default for a social app at 10M MAU carries risks that are not resolved by lower peak rates:

- **Latency for non-US users:** Notification delivery from a US-only infrastructure adds 150–300ms round-trip latency for users in Europe, Asia, and South America. For in-app notifications this is perceptible; for push it is less critical but still affects perceived responsiveness.
- **Data residency:** GDPR (EU), PDPA (Thailand/Singapore), LGPD (Brazil), and similar regulations impose requirements on where user data is processed and stored. A US-only architecture may not be compliant for EU users at any MAU level. This is a legal exposure, not a performance tradeoff.
- **Regional compliance for SMS:** TCPA applies to US numbers; different opt-in and content rules apply in the EU, UK, India, and other markets. The SMS architecture must account for the user's country, not just the sending infrastructure's location.

**The US-centric planning basis is retained for capacity sizing because it produces conservative (high) peak estimates.** It is not retained as an architectural recommendation. If the app has meaningful non-US user populations — which is probable at 10M MAU — a regional deployment decision (at minimum, EU and APAC regions) must be made before launch, independent of this notification system design. That decision is out of scope here but is flagged as a prerequisite for compliance in those regions.

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

SMS peak is negligible at any concentration level and is not a sizing driver.

#### Viral Spike Model

Two separate claims are made here. Conflating them produces circular sizing arguments.

**Claim 1: Worker throughput is sized for normal-use peak.** At 90% concentration (US-centric), combined peak is 2,552/sec. We size for **2,800/sec sustained worker throughput** — 10% headroom over the US-centric normal-use peak.

**Claim 2: Viral spikes are handled by queue backlog, with a defined maximum delay.**

The spike model requires an assumption about spike shape. We have no historical data for this app. The assumption used here — **5% of daily volume arriving in 10 minutes** — is derived from public incident reports for social apps (Twitter's 2013 Super Bowl spike, Instagram's documented peak events) where short-duration spikes have ranged from 3–8% of daily volume over 5–15 minutes. We use 5%/10min as a mid-range estimate. **This figure is not validated for this specific app.** The sensitivity analysis below shows what happens if it is wrong.

```
Normal-use peak arrival rate (US-centric):           2,344/sec
Worker sustained throughput:                          2,800/sec
Excess capacity available during normal-use peak:       456/sec

Spike arrival rate (5% of daily volume in 10 min):
  = (37.5M × 0.05) ÷ 600 seconds                  = 3,125/sec

Total arrival rate during spike:
  = 3,125 (spike) + 2,344 (normal)                 = 5,469/sec

Excess arrival above worker capacity during spike:
  = 5,469 − 2,800                                  = 2,669/sec

Backlog accumulated over 10-minute spike:
  = 2,669/sec × 600 seconds                        = 1,601,400 notifications

Post-spike, excess capacity available to drain:
  = 2,800 − 2,344 (ongoing normal traffic)          = 456/sec

Drain time after spike ends:
  = 1,601,400 ÷ 456/sec                            ≈ 3,512 seconds (~58 minutes)

Maximum delay for notification enqueued at spike start:
  = 600 seconds (spike duration) + 3,512 seconds (drain) ≈ 69 minutes
```

**Spike model sensitivity:**

| Spike assumption | Backlog | Drain time | Max delay |
|-----------------|---------|-----------|-----------|
| 3% of daily in 15 min | 576,000 | ~21 min | ~36 min |
| 5% of daily in 10 min (planning basis) | 1,601,400 | ~58 min | ~69 min |
| 8% of daily in 5 min | 5,136,000 | ~188 min | ~193 min |
| 10% of daily in 5 min | 6,420,000 | ~235 min | ~240 min |

The 8%/5min scenario produces a 3+ hour delay — not acceptable even for low-priority social notifications. **The planning basis spike model is therefore not conservative.** The appropriate response is not to size workers for the 10%/5min scenario (which would require ~10× normal worker capacity sitting idle), but to:

1. Accept the 69-minute delay bound for the planning basis scenario with explicit product sign-off.
2. Classify any notification where a 69-minute delay is unacceptable as high-priority, routing it to a dedicated queue with workers that are never shared with social volume (Section 2.1).
3. Monitor spike arrival rates in production from Month 2 onward. If observed spikes exceed 5%/10min, revisit worker sizing or add a spike-specific autoscaling trigger.

The 69-minute figure is a planning estimate, not a guarantee. Product and engineering must agree on the acceptable delay bound before Month 2 launch, and the monitoring in Section 7 must alert before that bound is approached.

#### Sustained Overload vs. Viral Spikes

The viral-spike model above applies only to temporary excess arrival. The 35%/15 scenario (3,498/sec sustained peak) is a different problem: if normal-use peak exceeds worker throughput of 2,800/sec, the queue grows continuously during every peak window and never fully drains. This requires additional workers before it occurs, not queue absorption.

Adding stateless worker processes requires no architectural change to the queue layer. The constraint for email workers is SendGrid throughput, which is why the enterprise contract target (270/sec) is sized to cover the 35%/30 scenario without renegotiation.

#### Month 2 Calibration Checkpoint

This checkpoint is the mechanism for detecting trajectory toward sustained overload with sufficient runway to respond. It is defined here, not referenced as undefined.

**What is measured:**
- Observed DAU/MAU ratio against the 25% planning basis
- Observed notifications/user/day against the 15 planning basis
- Observed peak arrival rate against the 2,344/sec planning basis
- Queue depth at peak: should be near-zero under normal conditions; sustained nonzero depth indicates worker undersizing

**Thresholds that trigger action:**
- DAU/MAU ≥ 30% (trajectory toward 35% by Month 6)
- Peak arrival rate ≥ 2,500/sec sustained over 3 