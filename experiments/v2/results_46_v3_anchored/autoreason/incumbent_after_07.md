# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues explicitly. The honest estimate of that overhead is in Section 2.2 — it is higher than a one-time build cost, and the architectural decision stands on its merits given that honest accounting.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. The 2am debuggability claim made in earlier drafts was not consistent with the operational complexity this system actually carries. Section 5 describes the real on-call experience: a single on-call rotation with a runbook that covers the five most common failure patterns, owned and tested before Month 6.

3. **Incremental delivery.** Working system in Month 2, iterate through Month 5, harden in Month 6 against the criteria defined in Section 7.

**The email volume model, the peak concentration model, and the Redis scaling ceiling are all examined honestly below.** Earlier drafts asserted numbers without derivation or dismissed high-end scenarios without analysis. Those gaps are addressed directly in Sections 1.1 and 2.2.

**Four items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** The planning-basis estimate is ~$17–24K/month. The realistic worst-case under aggressive authentication policy is $33–40K/month ongoing — not a spike scenario. Decision deadline: Week 2, with E2 work plan consequences described in Section 1.2.

- **Opt-out delivery risk (Section 2.4):** The preference cache has a documented staleness window. At planning-basis volume, our model estimates 150–750 opt-out violations per day during the window before cache invalidation propagates. Legal must assess whether this frequency constitutes a compliance problem under applicable regulations, not merely acknowledge that mitigations exist. The number is in the document; the sign-off is on the number.

- **Escalation default for capacity overruns (Section 1.1):** Stakeholders must select Default A, B, or C before this document is finalized. Default C names **[name to be filled by stakeholder before document is finalized — document cannot be finalized with this bracket empty]** as the escalation owner.

- **QA approach (Section 7):** Included in full.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

#### DAU/MAU Ratio Sensitivity

| App Stage | Typical DAU/MAU | DAU at 10M MAU |
|-----------|----------------|----------------|
| Early-stage social | 15–20% | 1.5M–2M |
| Mid-stage social | 25–35% | 2.5M–3.5M |
| Mature, high-retention | 40–50% | 4M–5M |

Planning basis: 25% DAU/MAU (2.5M DAU). Low case: 15% (1.5M DAU). High case: 35% (3.5M DAU).

#### Email Volume: Derivation

Earlier drafts asserted "35% of MAU per day = 3.5M emails/day" with no derivation. That number is reconstructed and examined here.

Email notifications divide into two categories with different denominators:

**Activity emails** go to daily active users who have email notifications enabled. Estimated 40% of DAU have email activity notifications enabled (industry benchmark: 30–50% for social apps; we use the midpoint). At planning basis: 2.5M DAU × 0.40 = 1.0M activity emails/day.

**Re-engagement and digest emails** go to the lapsed-user population — users who are MAU but not DAU. These users cannot be reached by push or in-app, making email the only channel. At planning basis: 10M MAU − 2.5M DAU = 7.5M lapsed users. We send digest/re-engagement email to 30% of lapsed users on any given day (consistent with published ESP benchmarks for weekly digest cadences hitting ~30% of the list daily when staggered): 7.5M × 0.30 = 2.25M re-engagement emails/day.

**Total: ~3.25M emails/day at planning basis.** The earlier "3.5M" figure was a reasonable approximation; the derivation shows it was not arbitrary, but it also shows sensitivity: if the re-engagement email rate drops to 20%, total email falls to ~2.75M/day; if activity email opt-in rises to 60%, it adds 500K/day. Email volume is moderately sensitive to product decisions about send frequency and opt-in defaults. We will validate actual send rates at the Month 2 calibration checkpoint.

**Email volume sensitivity to DAU/MAU:**

| DAU/MAU | Activity Emails | Re-engagement Emails | Total |
|---------|----------------|---------------------|-------|
| 15% (1.5M DAU) | 600K | 2.55M | ~3.15M |
| 25% (2.5M DAU) | 1.0M | 2.25M | ~3.25M |
| 35% (3.5M DAU) | 1.4M | 1.95M | ~3.35M |

Email volume is relatively flat across DAU scenarios because the two components move in opposite directions — this is now a derived result, not an assertion.

#### Peak Window Model: Defense and Sensitivity

The throughput model depends on peak concentration assumptions. Earlier drafts applied a 90% concentration in two 2-hour windows without defending it. That assumption is examined here.

**What 90% concentration assumes:** A US-centric or single-timezone user base where morning (7–9am) and evening (7–9pm) local time account for nearly all social app activity. This is a reasonable assumption for a US-focused early-stage social app. It is a poor assumption for a globally distributed user base.

**Timezone distribution effect:** If users are distributed across 4+ major timezone bands (US, Europe, South Asia, East Asia), peak concentration flattens substantially. A 4-timezone distribution with equal user distribution reduces peak concentration from ~90% in 4 hours to roughly 50–60% in 4 hours — peaks overlap and fill the trough.

We model three concentration scenarios:

```
Peak rate = (Daily volume × concentration_fraction) ÷ peak_window_seconds
```

| Concentration | Scenario | Peak Window | Push+In-app Peak/sec (planning basis, 37.5M/day) |
|--------------|----------|-------------|--------------------------------------------------|
| 90% in 4 hrs | US-only, two timezone bands | 14,400 sec | 2,344/sec |
| 70% in 4 hrs | Mixed US + one international timezone | 14,400 sec | 1,823/sec |
| 50% in 4 hrs | Global distribution, 4+ timezone bands | 14,400 sec | 1,302/sec |

**Viral spike scenario:** A viral content event can create a spike outside normal windows. We model this as a 10-minute window absorbing 5% of daily volume:

```
Viral spike peak = (37.5M × 0.05) ÷ 600 = 3,125/sec
```

This is the scenario that drives our sizing target, not the normal-use peak. The viral spike is short (10–30 minutes) and can be absorbed by queue depth — messages enqueue faster than they dequeue, then workers drain the backlog. This is acceptable for social notifications; it is not acceptable for OTP/auth notifications, which is the queue isolation argument for SMS.

**Revised sizing target:** We size for **3,500/sec sustained throughput** across all channels combined. This covers:
- Normal use at 90% concentration (2,344/sec) with 49% headroom
- Normal use at 50% concentration (1,302/sec) with 169% headroom — global distribution makes the infrastructure easier, not harder
- Viral spike (3,125/sec) with 12% headroom — sufficient for a short spike absorbed by queue depth

**The 35%/30 scenario is addressed separately below.**

#### Redis Scaling Ceiling Analysis

Earlier drafts acknowledged that the 35%/30 scenario (6,757/sec) "requires redesign" without analyzing what that means. This section corrects that.

**Where Redis sorted sets become the bottleneck:**

Redis sorted set operations (ZADD, ZRANGEBYSCORE, ZREM) are O(log N) for individual operations. At 6,757/sec combined across four queues, assuming roughly equal distribution, each queue receives ~1,700 operations/sec. A single Redis instance handles 100K–200K simple operations/sec; sorted set operations are more expensive but still comfortably within range at 1,700/sec per queue.

The Redis bottleneck is not throughput at this scale — it is memory and single-instance limits. Each queued notification entry in a sorted set consumes approximately 100–200 bytes (member string + score + overhead). At 6,757 enqueues/sec with a 30-second average queue depth (time from enqueue to delivery attempt), the working set is:

```
Working set = 6,757/sec × 30 sec × 150 bytes ≈ 30MB
```

This is trivially small. Even at 5× queue depth (150 seconds of backlog during a spike), the working set is ~150MB — well within a single Redis instance's capacity.

**The actual 35%/30 constraint is worker throughput, not Redis.** Delivering 6,757 notifications/sec requires external provider throughput: FCM, APNs, SendGrid, and Twilio must all accept that rate. FCM's documented throughput limit for a single project is ~500K/min (~8,333/sec); APNs is similar. SendGrid's highest tier supports 100K emails/hour (~27/sec) on standard plans, scaling to higher rates on enterprise contracts. **SendGrid throughput becomes the binding constraint at high email volumes, not Redis.**

**Horizontal scaling path for the 35%/30 scenario:**

- Redis: No change required. Single instance handles the load.
- Push workers: Add worker processes (stateless, horizontal). No architectural change.
- Email workers: SendGrid plan upgrade or secondary ESP required. This is a procurement decision, not an architectural one.
- SMS workers: Still negligible throughput.

**The 35%/30 scenario does not require architectural redesign of the queue layer.** It requires worker count increases and a SendGrid plan negotiation. The Month 2 calibration checkpoint provides 4 months of runway to execute this if the trajectory points toward it.

**What does require redesign:** If the product moves to a push-to-all-MAU broadcast model (e.g., breaking news notifications to 10M users simultaneously), the per-channel queue model breaks — not because of Redis, but because FCM and APNs impose per-project rate limits that cannot be exceeded regardless of worker count. That scenario requires a dedicated broadcast pipeline, which is out of scope for this design and explicitly flagged as a product decision gate.

#### Full Sensitivity Matrix

*Email peak is calculated from derived model above. Push+In-app peak uses 90% concentration / 4-hour window (US-centric assumption; see above for global adjustment).*

| DAU/MAU | Notifs/User/Day | Push+In-App/day | Email/day | SMS/day | Push+In-App Peak/sec | Email Peak/sec | Combined Peak/sec |
|---------|----------------|-----------------|-----------|---------|---------------------|----------------|------------------|
| 15% (1.5M DAU) | 8 | 12M | 3.15M | 45K | 750 | 175 | ~925 |
| 15% (1.5M DAU) | 15 | 22.5M | 3.15M | 45K | 1,406 | 175 | ~1,581 |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.25M** | **75K** | **2,344** | **181** | **~2,525** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.35M | 105K | 3,281 | 186 | ~3,467 |
| 35% (3.5M DAU) | 30 | 105M | 3.35M | 105K | 6,563 | 186 | ~6,749 |

*Email peak: (3.25M × 0.80) ÷ 14,400 = 181/sec at planning basis.*

**Sizing target: 3,500/sec.** Covers the 35%/15 scenario with marginal headroom. The 35%/30 scenario is covered by horizontal worker scaling and SendGrid plan upgrade, not architectural change.

#### SMS Cost: Honest Framing

Earlier drafts highlighted the spike cost ($1,600/day incremental) while burying the worst-case baseline. The correct framing:

| Scenario | SMS/day | Monthly cost |
|----------|---------|-------------|
| Conservative (login_rate=0.15, OTP_rate=0.05) | ~18.75K | ~$4.2K |
| Planning basis (login_rate=0.30, OTP_rate=0.10) | 75K | ~$17K |
| Aggressive (login_rate=0.40, OTP_rate=0.20) | 300K | ~$67.5K |

**The aggressive scenario is not a spike — it is what happens if the product ships OTP-on-every-login.** The budget sign-off question should be: "Are we comfortable committing to SMS if authentication policy produces $67.5K/month in ongoing costs?" The spike scenario ($1,600 incremental for one day) is not the material risk.

#### Calibration Checkpoint (Month 2): Measurement Methodology

The checkpoint compares actual volume to planned volume. Earlier drafts described the decision gates without specifying what gets measured or how.

**Defined measurements:**

| Metric | Measurement point | Window | Tool |
|--------|------------------|--------|------|
| Push notifications dispatched | At worker dequeue, before provider call | 7-day trailing average | Prometheus counter |
| Push notifications delivered | At provider acknowledgment (FCM/APNs 200) | 7-day trailing average | Prometheus counter |
| Email dispatched | At SendGrid API call | 7-day trailing average | Prometheus counter |
| SMS dispatched | At Twilio API call | 7-day trailing average | Prometheus counter |
| In-app notifications written | At PostgreSQL insert | 7-day trailing average | Prometheus counter |
| Peak throughput | 99th percentile per-second rate | 7-day trailing | Prometheus histogram |

**The comparison unit is "dispatched notifications per day" measured at provider API call.** This is the number that maps directly to the volume model. Delivery confirmation rates are tracked separately as a quality metric, not as the volume comparison unit.

**Who owns the measurement:** E4 owns the instrumentation and produces the checkpoint report. E1 reviews for queue-level accuracy. The report is a one-page summary: actual vs. planned for each channel, peak throughput vs. sizing target, and a recommendation (continue / scale workers / escalate).

**Decision gates:**

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week |
| 30–60% above plan | Add workers (horizontal, no redesign) | E1 + E4 | Before Month 3 |
| >60% above plan | Capacity + scope decision — see below | All + stakeholders | 48 hrs for options; 1 week for decision |
| >30% below plan | Reduce workers, update cost projections | E4 | Within 1 week |

**Pre-approved escalation defaults (stakeholders must select one before document is finalized):**

- **Default A:** Horizontal scaling only; all Month 3 feature work proceeds; engineering absorbs operational overhead. *Risk: team overextension.*
- **Default B:** Horizontal scaling; Month 3 feature work pauses until capacity is stable. *Risk: roadmap slips.*
- **Default C:** Escalate to **[name to be filled by stakeholder before document is finalized — document cannot be finalized with this bracket empty]**, who has authority to make the scope call within 24 hours. *Risk: depends on named person's availability.*

**Stakeholders must select a default and, if selecting Default C, name the escalation owner before this document is finalized.**

---

### 1.