# Notification System Design — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten specific criticisms of the previous draft. Each criticism is addressed directly; none are deferred. Where a criticism revealed a genuine error (SMS cost inconsistency, SendGrid planning-basis gap, circular spike model), the error is corrected and the correction is labeled. Where a criticism revealed a missing derivation (opt-out violation estimate, queue depth assumption), the derivation is added. Where a criticism revealed a structural problem (escalation default dependency, Section 5 reference to nonexistent content), the structure is fixed.

**Corrections that change prior conclusions:**

- **SendGrid is a Day 1 procurement problem, not a high-scenario problem.** The planning basis requires 181 emails/sec; standard SendGrid plans support ~27/sec. An enterprise contract is required before launch, not as a contingency. This is now in the procurement checklist with a Week 1 deadline.
- **The SMS aggressive scenario ($67.5K/month) and the executive summary worst-case ($33–40K/month) were inconsistent.** The executive summary figure was wrong. The correct worst-case under aggressive authentication policy is $67.5K/month. The executive summary is corrected.
- **The viral spike sizing argument was circular.** The document cannot simultaneously claim 3,500/sec covers the spike and that the spike is handled by queue backlog. The sizing logic is restructured: 3,500/sec is sized for normal-use peak; the spike is explicitly handled by queue depth with defined maximum backlog time. These are separate claims and are now stated separately.
- **"Add workers" was not an operational action without baseline worker counts.** Baseline worker counts are now specified in Section 2.

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid (enterprise contract required — see Section 1.1), and direct APNs/FCM integrations.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 1.1):** Planning basis is ~$17K/month. The realistic worst-case under aggressive authentication policy (OTP-on-every-login) is **$67.5K/month ongoing** — not a spike scenario. The $33–40K figure in the previous draft was an error; it is removed. Decision deadline: Week 2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. The derivation in Section 2.4 estimates **180–900 opt-out violations per day** during the propagation window. The derivation is fully shown; legal must assess whether this frequency constitutes a compliance problem, not merely acknowledge that mitigations exist.

- **SendGrid enterprise contract (Section 1.1):** The planning basis requires 181 emails/sec. Standard SendGrid plans support ~27/sec. An enterprise contract is required **before launch**, not as a contingency for high-growth scenarios. Procurement must begin Week 1. This is a corrected finding from the previous draft.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A or Default B before this document is finalized. Default C has been removed because its bracket dependency created a circular finalization condition. If stakeholders want a named escalation owner, that person must be identified before Default C is reintroduced — it cannot be added as a placeholder.

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

**Activity emails** go to daily active users with email notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50%; we use the midpoint). At planning basis: 2.5M × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — MAU who are not DAU. At planning basis: 10M − 2.5M = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.**

**Email volume sensitivity to DAU/MAU:**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

**Implication that was not drawn out in the previous draft:** Email volume is nearly flat across DAU/MAU scenarios because the two components move in opposite directions. This means email infrastructure costs are largely insensitive to whether the product succeeds or fails at engagement. A team expecting to reduce email costs by improving retention is wrong — re-engagement email volume falls, but activity email volume rises by approximately the same amount. Email cost is driven primarily by MAU count and send-frequency policy, not engagement rate. This is a constraint on the product's cost structure, not a validation of the model.

#### SendGrid Throughput: Day 1 Procurement Problem

**This section corrects an error in the previous draft.** The previous draft noted that standard SendGrid plans support ~27 emails/sec and flagged this as a concern for the 35%/30 high-growth scenario. That framing was wrong. The planning basis requires:

```
Email peak rate = (3.25M emails/day × 0.80 peak concentration) ÷ 14,400 seconds = 181 emails/sec
```

Standard SendGrid plans (up to ~100K emails/day on Pro tiers) support roughly 1–2 emails/sec continuously; their highest documented standard tier handles ~100K/hour = 27/sec. The planning basis of 181/sec exceeds this by **6.7×**. This is not a high-scenario problem. It is a Day 1 requirement.

**Required action:** An enterprise SendGrid contract supporting at least 250 emails/sec sustained throughput (planning basis with 38% headroom) must be procured before launch. Procurement conversations must begin Week 1. If SendGrid enterprise pricing is unacceptable, the alternative is a self-hosted email infrastructure (Postfix + SES relay), which trades procurement cost for operational complexity that the team may not have capacity to absorb in the 6-month window.

**Procurement checklist item:** E2 owns the SendGrid enterprise contract negotiation. Target: contract executed by end of Month 1. If not executed by end of Month 1, E1 escalates to stakeholders with a go/no-go on self-hosted email.

#### Peak Concentration Model

**Correction from previous draft:** The previous draft's "Combined Peak/sec" column added push+in-app peak (using 90% concentration in 4 hours) and email peak (using 80% concentration in 4 hours) without acknowledging the inconsistency, and omitted SMS entirely. The corrected table uses consistent concentration assumptions and includes all four channels.

We model three concentration scenarios. All channels use the same concentration assumption within a scenario; the channels are not assumed to peak independently.

```
Peak rate per channel = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

**Concentration scenarios:**

| Scenario | Concentration | Basis |
|----------|--------------|-------|
| US-centric | 90% in 4 hours (14,400 sec) | Single timezone band, two daily peaks |
| Mixed | 70% in 4 hours | US + one international timezone |
| Global | 50% in 4 hours | 4+ timezone bands, peaks overlap |

**Combined peak throughput (planning basis: 37.5M push/in-app, 3.25M email, 75K SMS per day):**

| Scenario | Push+In-App/sec | Email/sec | SMS/sec | Combined/sec |
|----------|----------------|-----------|---------|-------------|
| US-centric (90%) | 2,344 | 203 | 4.7 | 2,552 |
| Mixed (70%) | 1,823 | 158 | 3.6 | 1,985 |
| Global (50%) | 1,302 | 113 | 2.6 | 1,418 |

SMS peak is negligible at any concentration. Email peak is now calculated consistently with push peak.

#### Viral Spike Model: Corrected Logic

**The previous draft's spike argument was circular.** It sized for 3,500/sec because of a 3,125/sec viral spike, then said the spike was "absorbed by queue depth" with 12% headroom. These two claims are contradictory: if the spike is absorbed by queue backlog, the sizing target is not driven by the spike — it is driven by normal-use peak with the spike handled separately.

**Corrected framing — two separate claims:**

**Claim 1: Worker throughput is sized for normal-use peak.** At 90% concentration (US-centric), combined peak is 2,552/sec. We size for **2,800/sec sustained worker throughput** (10% headroom over US-centric peak, adequate for planning basis). This covers normal operation.

**Claim 2: Viral spikes are handled by queue backlog, with a defined maximum backlog time.** A 10-minute viral spike absorbing 5% of daily volume produces:

```
Spike rate = (37.5M × 0.05) ÷ 600 seconds = 3,125/sec
```

At 2,800/sec worker throughput, the excess arrival rate during the spike is 325/sec for 10 minutes = 195,000 queued notifications. At 2,800/sec drain rate, the backlog clears in:

```
Clearance time = 195,000 ÷ 2,800/sec = 70 seconds after spike ends
```

Total maximum delay for a notification enqueued at the start of the spike: 10 minutes (spike duration) + 70 seconds (drain) = approximately **11 minutes 10 seconds.** This is acceptable for social notifications. It is explicitly not acceptable for SMS/OTP, which is why the SMS queue has dedicated workers that are not shared with social push — those workers are never backlogged by social volume.

**Sizing target: 2,800/sec sustained worker throughput.** Viral spikes produce a maximum 11-minute delay on social push/in-app notifications. SMS/OTP is unaffected.

#### Redis Scaling Ceiling: Queue Depth Assumption Justified

**The previous draft used "30-second average queue depth" without justification.** This section derives it.

Average queue depth (in seconds) = average time from enqueue to delivery attempt. This depends on:

1. **Worker poll interval:** Workers poll the queue every 100ms (see Section 2). A notification sits in the queue for at most 100ms before a worker picks it up, assuming a worker is available.
2. **Provider API latency:** FCM and APNs HTTP/2 calls typically return in 50–200ms. We use 150ms as the planning estimate.
3. **Worker concurrency:** Each worker handles one notification at a time (no internal batching at the worker level; batching happens at the queue level — see Section 2.2).

Under normal operation with adequate workers, average queue depth is approximately:

```
Poll interval + provider latency = 100ms + 150ms = 250ms ≈ 0.25 seconds
```

The 30-second figure from the previous draft was wrong for normal operation. The correct normal-operation queue depth is under 1 second.

**During a viral spike**, with 195,000 notifications queued and workers draining at 2,800/sec, the average queue depth for a notification enqueued mid-spike is:

```
Average wait = (195,000 ÷ 2) ÷ 2,800/sec ≈ 35 seconds
```

(The factor of 2 accounts for the average position in the queue being halfway through the backlog.)

**Revised Redis working set calculation:**

| Condition | Queue depth | Entries in queue | Memory at 150 bytes/entry |
|-----------|------------|-----------------|--------------------------|
| Normal operation | 0.25 sec | 2,800 × 0.25 = 700 | ~105 KB |
| Viral spike (peak backlog) | 195,000 entries | 195,000 | ~28 MB |
| 5× spike (model upper bound) | 975,000 entries | 975,000 | ~140 MB |

All scenarios are well within a single Redis instance's memory capacity. The conclusion from the previous draft — that Redis memory is not the binding constraint — holds, but is now derived from a justified queue depth model rather than an assumed one.

#### SMS Cost: Corrected

**The previous draft contained an inconsistency:** the executive summary stated the realistic worst-case was $33–40K/month, while the sensitivity table showed $67.5K/month under aggressive authentication assumptions. These cannot both be correct. The $33–40K figure in the executive summary was an error. It is removed. The correct figures:

| Scenario | Assumptions | SMS/day | Monthly cost |
|----------|-------------|---------|-------------|
| Conservative | login_rate=0.15, OTP_rate=0.05 | ~18.75K | ~$4.2K |
| Planning basis | login_rate=0.30, OTP_rate=0.10 | 75K | ~$17K |
| Aggressive | login_rate=0.40, OTP_rate=0.20 | 300K | ~$67.5K |

The aggressive scenario is what happens if the product ships OTP-on-every-login. It is not a spike — it is an ongoing baseline under that authentication policy. The budget sign-off question is: "Are we comfortable committing to SMS if authentication policy produces $67.5K/month in ongoing costs?" The one-day spike scenario is not the material risk.

#### Full Sensitivity Matrix (Corrected)

*All channels use consistent 90% concentration / 4-hour window (US-centric). SMS peak is included. Email peak uses same concentration as push.*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App Peak/sec | Email Peak/sec | SMS Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|-----------|---------|---------------------|----------------|-------------|------------------|
| 15% | 8 | 12M | 3.15M | 45K | 750 | 197 | 2.8 | 950 |
| 15% | 15 | 22.5M | 3.15M | 45K | 1,406 | 197 | 2.8 | 1,606 |
| **25%** | **15** | **37.5M** | **3.25M** | **75K** | **2,344** | **203** | **4.7** | **2,552** |
| 35% | 15 | 52.5M | 3.35M | 105K | 3,281 | 210 | 6.6 | 3,498 |
| 35% | 30 | 105M | 3.35M | 105K | 6,563 | 210 | 6.6 | 6,780 |

**Sizing target: 2,800/sec sustained.** The 35%/15 scenario (3,498/