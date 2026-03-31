# Notification System Design — Revised v2
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Nine items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** The planning basis of ~$17K/month assumes one SMS OTP per user per 30-day period. OTP-on-every-login produces ~$67.5K/month. These are not worst-case and best-case — they are two different authentication policy decisions. Product and security must jointly select the authentication policy before this document is finalized, because the SMS budget follows from that decision, not the other way around.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. The derivation of the violation rate is shown in full in Section 2.4. Legal and product must select one of two architectures before finalization.

- **SendGrid enterprise contract (Section 1.1):** Required before launch. Procurement begins Week 1. If not executed by end of Month 1, the self-hosted path activates with explicit workstream tradeoffs described in Section 1.1.

- **Escalation default for capacity overruns (Section 1.1):** Default A, B, or C (with named owner) must be selected before finalization.

- **Broadcast notification policy (Section 1.1 and Section 6):** The 100K recipient cap is a hard product constraint, not a safe default. Product stakeholders must affirmatively acknowledge this constraint and name a decision gate owner, or request an architectural scope change before finalization.

- **Spike delay acceptance (Section 1.1):** The planning basis spike model produces a maximum 69-minute notification delay. Product must explicitly accept this bound or request a different worker sizing. The model's known limitations are documented; acceptance must be informed.

- **Re-engagement send rate policy (Section 1.1):** The email cost model is more sensitive to the re-engagement send rate than to DAU/MAU ratio. Product must confirm the 30% daily send rate assumption or provide an alternative before finalization.

- **International user population (Section 1.1 and Section 2.5):** The SMS architecture includes country-of-origin routing for compliance. The international deployment decision (EU/APAC regions for data residency) remains out of scope for this document but is a legal prerequisite for operating in those regions. Legal must confirm the app's geographic scope before launch.

- **E2 backup for SendGrid procurement (Section 1.1):** A named backup owner must be designated before Month 1 begins.

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

#### SMS Budget: Authentication Policy Is the Primary Variable

The previous version of this document presented ~$17K/month as a "planning basis" and ~$67.5K/month as a "realistic worst-case under aggressive authentication policy." That framing was wrong. OTP-on-every-login is standard practice for apps with any security posture. Calling it a worst case implies a more lenient policy is the expected baseline, which was never justified.

The correct framing: the SMS budget is determined by the authentication policy. Two policies are modeled here. Product and security must select one.

**Policy A: Session-persistent authentication (OTP on new device or 30-day session expiry)**
- Assumption: each DAU triggers one SMS OTP per 30-day period on average
- Daily SMS OTP volume: 2.5M DAU ÷ 30 days = ~83,333 OTPs/day
- Monthly SMS OTP volume: ~2.5M OTPs/month
- At $0.0075/SMS (Twilio US standard): ~$18,750/month
- At $0.0075 blended (US + international premium): ~$17K–20K/month

**Policy B: OTP-on-every-login**
- Assumption: each DAU logs in once per active day
- Daily SMS OTP volume: 2.5M OTPs/day
- Monthly SMS OTP volume: ~75M OTPs/month
- At $0.0075/SMS: ~$562,500/month

**The $67.5K/month figure cited in the previous version was based on an undocumented intermediate assumption (approximately 9M OTPs/month, implying roughly one login per user per 3 active days). That assumption was neither Policy A nor Policy B and was not stated. It has been removed.**

The correct options are approximately $18–20K/month (Policy A) or ~$562K/month (Policy B). There is no credible middle ground that holds at scale without a defined session model.

**Required action:** Product and security select Policy A or Policy B. The SMS infrastructure is sized for the selected policy. If Policy B is selected, SMS is not a minor line item — it is a dominant infrastructure cost that requires a separate budget approval before this system is built.

Additional SMS volume (non-OTP notifications to opted-in users) is estimated at 75K/day at planning basis, adding ~$562/day or ~$17K/month regardless of authentication policy. This is not the sizing driver.

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators:

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

#### Re-engagement Send Rate Is the Primary Cost Driver — Sign-Off Required

The previous version presented a DAU/MAU sensitivity table showing email volume varies only 6% across DAU/MAU scenarios, then correctly noted this was an artifact of holding the re-engagement send rate constant. What it did not do was analyze sensitivity to the variable that actually drives email cost: the re-engagement send rate itself.

**Email volume sensitivity to re-engagement send rate (at planning basis DAU/MAU of 25%):**

| Re-engagement send rate | Activity emails | Re-engagement emails | Total | Cost at $0.001/email |
|------------------------|----------------|---------------------|-------|---------------------|
| 10% of lapsed/day | 1.0M | 750K | 1.75M | $1,750/day |
| 20% of lapsed/day | 1.0M | 1.5M | 2.5M | $2,500/day |
| **30% of lapsed/day (planning basis)** | **1.0M** | **2.25M** | **3.25M** | **$3,250/day** |
| 50% of lapsed/day | 1.0M | 3.75M | 4.75M | $4,750/day |
| 100% of lapsed/day | 1.0M | 7.5M | 8.5M | $8,500/day |

Email volume varies by **4.9×** across the re-engagement send rate range, versus 6% across DAU/MAU scenarios. The send rate is the cost lever, not retention.

The DAU/MAU sensitivity table from the previous version is retained below for completeness, but it is not a useful planning tool for email cost because it holds the more consequential variable fixed.

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Required action:** Product must confirm the 30% daily re-engagement send rate or provide an alternative. If the team intends to reduce re-engagement cadence as retention improves, the actual policy must be documented here before finalization, because the SendGrid contract throughput requirement is derived from this number.

#### SendGrid Throughput: Day 1 Procurement Problem

**All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).**

```
Email peak rate = (3.25M emails/day × 0.90 peak concentration) ÷ 14,400 seconds = 203 emails/sec
```

Standard SendGrid plans support approximately 27/sec. The planning basis of 203/sec exceeds this by 7.5×. This is a Day 1 requirement, not a growth contingency.

**Required action:** An enterprise SendGrid contract supporting at least 270 emails/sec sustained throughput must be procured before launch. If the re-engagement send rate is confirmed above 30%, the contract target must be recalculated before procurement begins.

**If the SendGrid contract is not executed by end of Month 1, the self-hosted email path activates:**

- **Infrastructure:** 3 Postfix MTA instances behind a load balancer; SES relay for deliverability; dedicated IP warm-up over 4 weeks.
- **Build cost:** Estimated 6–8 engineer-weeks (deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring).
- **Ongoing operational cost:** This is where the previous version understated the tradeoff. SES relay pricing at $0.10/1K emails = $325/day at planning basis is arithmetically correct. But this comparison omits the ongoing engineering labor to maintain deliverability operations indefinitely: bounce rate monitoring, IP reputation management, blocklist removal requests, DMARC aggregate report processing, and feedback loop handling with major ISPs. SendGrid's enterprise pricing includes these operations. The self-hosted path does not eliminate these costs — it converts them from a vendor line item to an engineering time commitment that competes with product feature work for the life of the system. A conservative estimate for ongoing deliverability operations is 0.25–0.5 FTE equivalent, which at fully-loaded engineering cost ($150–200K/year) is $37,500–100,000/year — likely exceeding the SendGrid contract cost at this volume. **The self-hosted path is cheaper on a per-email basis and more expensive in total cost of ownership.** This tradeoff must be presented explicitly if the SendGrid contract is not on track.
- **The workstream that slips:** With 4 engineers and a 6-month window, absorbing 6–8 engineer-weeks on email infrastructure in Months 1–2 requires explicit identification of which planned workstream slips. E1 must identify this workstream and present the tradeoff to stakeholders within 48 hours of the Month 1 deadline passing without a signed contract.

**Owner:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. **Backup owner: [NAME REQUIRED before Month 1 begins].** If E2 is unavailable for any reason during Month 1, the backup owner assumes full responsibility for contract execution. This is not a single point of failure that can remain unnamed — the procurement deadline is hard and the consequences of missing it are defined above.

#### Peak Concentration Model and International Users

**All channels use a consistent concentration assumption within a scenario.**

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric (planning basis) | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

**On international users:** The US-centric assumption is retained for capacity sizing because it produces the highest peak rates and therefore the most conservative infrastructure sizing. It is not an architectural recommendation. Data residency (GDPR, PDPA, LGPD), latency, and per-country SMS compliance requirements are real constraints for non-US user populations. The SMS architecture addresses country-of-origin routing in Section 2.5. Regional deployment for data residency is out of scope for this document but is flagged as a legal prerequisite for EU and APAC operations.

#### Viral Spike Model

Two claims are made separately.

**Claim 1: Worker throughput is sized for normal-use peak.** At 90% concentration (US-centric), combined peak is 2,552/sec. Workers are sized for **2,800/sec sustained throughput** — 10% headroom over the US-centric normal-use peak.

**Claim 2: Viral spikes are handled by queue backlog, with a defined maximum delay.**

The spike shape assumption — 5% of daily volume arriving in 10 minutes — is derived from public incident reports for social apps (Twitter's 2013 Super Bowl spike, Instagram's documented peak events) where short-duration spikes have ranged from 3–8% of daily volume over 5–15 minutes. This figure is not validated for this specific app.

```
Normal-use peak arrival rate (US-centric):           2,344/sec
Worker sustained throughput:                          2,800/sec
Excess capacity during normal-use peak:                 456/sec

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
  ≈ 69 minutes
```

**Spike model sensitivity:**

| Spike assumption | Backlog | Drain time | Max delay |
|-----------------|---------|-----------|-----------|
| 3% of daily in 15 min | 576,000 | ~21 min | ~36 min |
| 