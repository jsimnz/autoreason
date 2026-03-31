# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly, with the operational cost accounted for in Section 5.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required before launch — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**Eight items require explicit sign-off before this design is finalized.** These are not optional reviews — each blocks a specific architectural or procurement decision that cannot be reversed cheaply after Month 1.

- **SMS budget (Section 1.1):** The SMS budget is determined by the authentication policy, not by scale. Two policies are modeled. Policy A (session-persistent, OTP on new device or 30-day expiry) costs ~$18–20K/month. Policy B (OTP-on-every-login) costs ~$562K/month. There is no credible middle ground without a defined session model. Product and security must jointly select a policy before this document is finalized; the SMS infrastructure is sized for the selected policy. If Policy B is selected, it is the dominant infrastructure cost and requires a separate budget approval before build begins.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window during which opted-out users may receive notifications. The violation rate derivation is shown in full in Section 2.4. Individual violations under CAN-SPAM, TCPA, and GDPR are each independently actionable — this is a binary architectural decision, not a threshold for legal to assess. Legal and product must jointly select one of the two architectures in Section 2.4 before finalization.

- **SendGrid enterprise contract (Section 1.1):** The planning basis requires 203 emails/sec at US-centric peak. Standard SendGrid plans support ~27/sec. An enterprise contract supporting at least 270/sec sustained throughput is required before launch. Procurement begins Week 1. If the contract is not executed by end of Month 1, the self-hosted path activates with the workstream tradeoffs described in Section 1.1. A named backup owner for E2 is required before Month 1 begins.

- **Escalation default for capacity overruns (Section 1.1):** Default A (throttle lower-priority queues), Default B (shed load with dead-letter queue), or Default C (named escalation owner with discretion) must be selected before finalization. Default C requires a specific named person; without a named person it is not a selectable option.

- **Broadcast notification policy (Section 1.1 and Section 6):** The 100K recipient cap per notification job is enforced at the API validation layer. Push-to-all-MAU broadcasts are not supported by this design. This is a hard product constraint, not a safe default. A named decision-gate owner must be identified before launch; without one, the cap is policy with no exceptions.

- **Spike delay acceptance (Section 1.1):** The planning basis spike model produces a maximum 69-minute notification delay. Product must explicitly accept this bound or request different worker sizing. The model's assumptions and known limitations are documented in full; acceptance must be informed.

- **Re-engagement send rate (Section 1.1):** Email volume varies 4.9× across re-engagement send rate scenarios versus 6% across DAU/MAU scenarios. The send rate is the cost lever. Product must confirm the 30% daily re-engagement send rate or provide an alternative before finalization, because the SendGrid contract throughput requirement is derived from this number.

- **International user population (Section 1.1):** Data residency requirements (GDPR, PDPA, LGPD) and per-country SMS compliance rules are legal prerequisites for operating in non-US regions, independent of this notification system design. Legal must confirm the app's geographic scope before launch. Regional deployment is out of scope for this document but is flagged as a hard prerequisite.

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

---

#### SMS Budget: Authentication Policy Is the Primary Variable

The SMS budget is determined by the authentication policy. Two policies are modeled. Product and security must select one; the infrastructure is sized for the selected policy.

**Policy A: Session-persistent authentication (OTP on new device or 30-day session expiry)**
- Daily SMS OTP volume: 2.5M DAU ÷ 30 days = ~83,333 OTPs/day
- Monthly SMS OTP volume: ~2.5M OTPs/month
- At $0.0075/SMS blended (US + international): ~$18,750/month

**Policy B: OTP-on-every-login**
- Daily SMS OTP volume: 2.5M OTPs/day
- Monthly SMS OTP volume: ~75M OTPs/month
- At $0.0075/SMS: ~$562,500/month

There is no credible middle ground without a defined session model. Any intermediate figure requires a stated assumption about session length; that assumption is the policy.

Additional SMS volume from opted-in marketing/transactional notifications is estimated at 75K/day (~$562/day, ~$17K/month) and is not the sizing driver under either policy.

**Required action:** Product and security select Policy A or Policy B before finalization. If Policy B is selected, a separate budget approval is required before build begins.

---

#### Email Volume: Derivation

Email notifications divide into two categories with different denominators and different sensitivities to product decisions.

**Activity emails** go to daily active users with email activity notifications enabled. Estimated 40% of DAU have these enabled (industry benchmark: 30–50%; midpoint used). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. These users cannot be reached by push or in-app, making email the primary retention channel for them. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send to 30% of lapsed users on any given day (consistent with weekly digest cadences staggered across the list): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

#### Re-engagement Send Rate Is the Primary Cost Driver

The DAU/MAU sensitivity table shows email volume varying only 6% across scenarios. This is an artifact of holding the re-engagement send rate constant — it is not a structural property of the product. The variable that actually drives email cost is the send rate itself.

**Email volume sensitivity to re-engagement send rate (at planning basis DAU/MAU of 25%):**

| Re-engagement send rate | Activity emails | Re-engagement emails | Total | Cost at $0.001/email |
|------------------------|----------------|---------------------|-------|---------------------|
| 10% of lapsed/day | 1.0M | 750K | 1.75M | $1,750/day |
| 20% of lapsed/day | 1.0M | 1.5M | 2.5M | $2,500/day |
| **30% of lapsed/day (planning basis)** | **1.0M** | **2.25M** | **3.25M** | **$3,250/day** |
| 50% of lapsed/day | 1.0M | 3.75M | 4.75M | $4,750/day |
| 100% of lapsed/day | 1.0M | 7.5M | 8.5M | $8,500/day |

Email volume varies **4.9×** across the re-engagement send rate range versus 6% across DAU/MAU scenarios. The send rate is the cost lever.

The DAU/MAU sensitivity table is retained for completeness but is not a useful planning tool for email cost because it holds the more consequential variable fixed:

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Required action:** Product must confirm the 30% daily re-engagement send rate or provide an alternative before finalization. The SendGrid contract throughput requirement is derived from this number.

---

#### SendGrid Throughput: Day 1 Procurement Problem

**All peak calculations use a consistent 90% concentration / 4-hour window (US-centric planning basis).**

```
Email peak rate = (3.25M emails/day × 0.90 peak concentration) ÷ 14,400 seconds = 203 emails/sec
```

Standard SendGrid plans support approximately 27/sec. The planning basis of 203/sec exceeds this by 7.5×. This is a Day 1 requirement, not a growth contingency.

**Required action:** An enterprise SendGrid contract supporting at least 270 emails/sec sustained throughput (203/sec planning basis with 33% headroom) must be procured before launch. If the re-engagement send rate is confirmed above 30%, the contract target must be recalculated before procurement begins.

**Owner:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. **Backup owner: [NAME REQUIRED before Month 1 begins].** This is not a single point of failure that can remain unnamed — the procurement deadline is hard and the consequences of missing it are defined below.

**If the SendGrid contract is not executed by end of Month 1, the self-hosted email path activates:**

- **Infrastructure:** 3 Postfix MTA instances behind a load balancer; SES relay for deliverability; dedicated IP warm-up over 4 weeks.
- **Build cost:** Estimated 6–8 engineer-weeks (deliverability tuning, bounce handling, DKIM/SPF/DMARC, monitoring). At 4 engineers, this consumes roughly 2 months of one engineer's capacity during the window where other Month 2–3 milestones are already scheduled.
- **Ongoing cost — the honest assessment:** SES relay pricing at $0.10/1K emails = ~$325/day at planning basis. SendGrid enterprise at $0.001–0.002/email = $3,250–6,500/day. SES relay is materially cheaper on a per-email basis. However, this comparison omits the ongoing engineering labor to maintain deliverability operations: bounce rate monitoring, IP reputation management, blocklist removal, DMARC aggregate report processing, and feedback loop handling with major ISPs. SendGrid's enterprise pricing includes these operations. A conservative estimate for ongoing deliverability operations is 0.25–0.5 FTE equivalent (~$37,500–$100,000/year at fully-loaded cost), which likely exceeds the SendGrid contract cost at this volume. **The self-hosted path is cheaper on a per-email basis and more expensive in total cost of ownership.** This tradeoff must be presented explicitly to stakeholders if the SendGrid contract is not on track.
- **The workstream that slips:** With 4 engineers and a 6-month window, absorbing 6–8 engineer-weeks on email infrastructure in Months 1–2 requires explicit identification of which planned workstream slips. E1 must identify that workstream and present the tradeoff to stakeholders within 48 hours of the Month 1 deadline passing without a signed contract.

---

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

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

SMS peak is negligible at any concentration level and is not a sizing driver.

**On international users:** The US-centric assumption is retained for capacity sizing because it produces the highest peak rates and therefore the most conservative infrastructure sizing. It is not an architectural recommendation. Three distinct risks apply to non-US populations and must not be collapsed together:

- **Latency:** Notification delivery from US-only infrastructure adds 150–300ms round-trip for users in Europe, Asia, and South America. For in-app notifications this is perceptible.
- **Data residency:** GDPR (EU), PDPA (Thailand/Singapore), LGPD (Brazil), and similar regulations impose requirements on where user data is processed and stored. A US-only architecture may not be compliant for EU users at any MAU level. This is a legal exposure, not a performance tradeoff.
- **SMS compliance:** TCPA applies to US numbers; different opt-in and content rules apply in the EU, UK, India, and other markets. The SMS architecture must account for the user's country of origin, not just the sending infrastructure's location (see Section 2.5).

**Required action:** Legal must confirm the app's geographic scope before launch. Regional deployment for data residency is out of scope for this document but is flagged as a hard prerequisite for EU and APAC operations.

---

#### Viral Spike Model

Two claims are made separately. Conflating them produces circular sizing arguments.

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
  