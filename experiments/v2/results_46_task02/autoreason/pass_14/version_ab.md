# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Document

This synthesis takes the strongest elements from two drafts. Version X provided the clearest structural reasoning on burst modeling, worker architecture, and failure handling. Version Y provided more honest epistemic framing, corrected specific arithmetic errors, and supplied missing sections. Where the two drafts disagreed, this document explains which position is adopted and why.

Eight specific corrections from Version Y are incorporated throughout. Where Version Y's corrections were themselves imprecise (notably the APNs rate limit framing and the spin-up time claim), this document adopts the more careful Version Y position while preserving Version X's structural clarity.

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application with a 4-engineer team over 6 months.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned delivery floor at ~1,800/sec via channel-specialized workers | Derived from per-channel worker arithmetic summed across channels — not a single multiplier |
| Channel-specialized workers | SMTP operations block push dispatch in a shared queue; this is a scheduling problem, not a CPU problem |
| Priority queue via Redis ZSET with encoded score | Atomic priority + time ordering in a single structure; no separate index |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures |
| SMS spend counter in isolated Redis with no eviction | Closes race condition on spend cap enforcement |
| Auto-scaling pre-configured but not pre-running for elevated scenarios | Elevated scenarios require multiple inputs to be simultaneously wrong; pre-running that capacity is not justified |
| Shedding triggers independent of scaling status | Response plan must work whether spin-up takes 4 minutes or 12 minutes |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. It does not make the estimates reliable. Section 1.4 defines re-sizing triggers and validation paths for every major assumption that drives infrastructure sizing.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis | Validation Path |
|--------|----------|-------|-----------------|
| MAU | 10M | Given | — |
| DAU | 3M | 30% DAU/MAU; social app benchmark | Validate against analytics in month 1 |
| Notifications/DAU/day | 17 average | Engaged-user benchmark | Validate before final sizing; see Section 1.4 |
| **Total notifications/day** | **~50M** | Planning baseline | — |
| iOS/Android split | 60/40 | Industry benchmark | Validate against registration data month 1 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 | Monitor at launch |
| Provisioned delivery floor | ~1,800/sec | Derived in Section 1.2 | Load test month 1 |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS | — |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android | — |
| In-app | ~10M/day (20%) | Logged-in users only | — |
| Email | ~4M/day (8%) | Digests + transactional | — |
| SMS | ~360K/day | Derived in Section 1.3 | Validate against auth logs month 1 |

**The iOS/Android split matters operationally.** At 60/40, APNs carries 1.5× the push volume of FCM and is the dominant delivery path. If the split is actually 40/60, FCM becomes dominant and the APNs connection pool is over-provisioned relative to FCM. Section 1.4 specifies the re-sizing response.

**The 17 notifications/DAU/day figure drives the entire sizing model.** Section 1.4 specifies what changes at 8/day and 35/day and defines the hard re-sizing trigger.

---

### 1.2 Burst Model and Worker Sizing

#### Viral Cohort Baseline — Honest Derivation

**The structural error in the naive approach:** Assigning the top 5% of DAU a baseline of 34 notifications/day — framed as "2× the all-user average of 17" — is wrong. The all-user average includes the bottom 95% of users, who are low-engagement and pull the average down. Using that average to estimate the top cohort's baseline systematically underestimates the viral inbound ceiling.

**The replacement in the prior draft was not structurally sounder — it was longer.** Applying a top-decile ratio from a 2014 Facebook paper to the top 5% of a different platform in a different era is an assumption of the same epistemic quality as the figure it replaced. The integration over the log-normal distribution was asserted, not shown.

**Revised position:** The cohort volume share is unknown. The working assumption is a range of 20–50%, with 35% as the midpoint for sizing calculations. This range is not derived from first principles; it is a prior that should be replaced with measurement at launch.

```
Top 5% of DAU          = 150,000 users
Volume share range     = 20–50% of 50M/day = 10M–25M notifications/day
Per-user cohort range  = 67–167/day
Working midpoint       = 35% → 117/day → ~0.00135/sec
```

**Sensitivity on the volume share assumption:**

| Volume share | Per-user baseline | Cohort rate |
|-------------|-------------------|-------------|
| 20% (conservative) | ~67/day | ~0.00078/sec |
| 35% (working midpoint) | ~117/day | ~0.00135/sec |
| 50% (aggressive) | ~167/day | ~0.00193/sec |

The key structural point holds across the full range: under any assumption from 20% to 50%, the cohort baseline is 4–10× the all-user average. The prior 2× assumption was wrong across the entire plausible range, not just at the midpoint.

---

#### Viral Spike Multiplier

The multiplier is the ratio of spike-period notification rate to a user's baseline rate during a sustained 15-minute viral event.

**Calibration from adjacent data:**

| Event type | Multiplier range | Basis |
|-----------|-----------------|-------|
| Moderate viral content (10K–100K engagements in 15 min) | 4–12× | Estimated from engagement rate × notification fan-out |
| Large viral event on a platform this size | 10–20× | Twitter engineering retrospectives describe this range; direct comparability is uncertain |

**Working assumption: 8×.** At 10M MAU, the platform is large enough to produce genuine viral events but unlikely to host accounts that produce Twitter-scale celebrity spikes. 8× sits at the upper end of the moderate-viral range.

The multiplier depends on follower count, content type, time of day, and fan-out configuration — none of which are known pre-launch. The 4–20× range reflects genuine uncertainty. If the true multiplier is 20× rather than 8×, the base case scales from ~2,200/sec to ~5,500/sec, which lands between the elevated and high scenarios defined below.

---

#### Inbound Rate Scenarios

The prior draft labeled scenarios "2×" and "3×," implying a clean mathematical relationship the arithmetic did not actually produce. The scenarios are renamed by their input assumptions. The arithmetic stands on its own.

**Base case** (working midpoint assumptions):
```
Viral cohort:   150,000 × 0.00135/sec × 8  = ~1,620/sec
Remaining DAU:  2,850,000 × 17 / 86,400    =   ~560/sec
Total                                       = ~2,180/sec
```

**Elevated case** (cohort 50% larger, multiplier 50% higher):
```
Viral cohort:   225,000 × 0.00135 × 12 = ~3,645/sec
Remaining DAU:                            ~560/sec
Total                                   = ~4,205/sec
```
Both primary inputs simultaneously wrong by 50%. Plausible given no pre-launch data.

**High case** (cohort doubled, multiplier 75% higher):
```
Viral cohort:   300,000 × 0.00135 × 14 = ~5,670/sec
Remaining DAU:                            ~560/sec
Total                                   = ~6,230/sec
```
Both inputs simultaneously wrong by 75–100%. This corresponds to a genuinely viral launch event. Historical examples exist; it is not a theoretical scenario. The output is ~2.85× the base case — the "3×" label was dropped because it was wrong.

These scenarios are not expected outcomes. They represent the plausible range given input uncertainty. The base case is the midpoint of a wide distribution, not the expected case.

---

#### Channel-Specialized Workers — The Correct Argument

An earlier draft argued for channel specialization based on CPU utilization: email consuming ~0.288 vCPU would slow push workers. A reviewer correctly noted this supports CPU allocation tuning within a multi-channel worker as readily as it supports specialization. That argument was wrong, and this document does not use it.

**The correct argument is about queue scheduling.**

In a multi-channel worker, a push notification waiting in the local dispatch queue sits behind whatever work the worker is currently executing. If the worker is mid-SMTP-handshake — which involves connection establishment, TLS negotiation, and a synchronous response from the mail relay — that push notification waits for the SMTP operation to complete. SMTP handshakes routinely take 100–300ms. APNs HTTP/2 dispatch takes ~5ms end-to-end.

This is not a CPU utilization problem. It is a head-of-line blocking problem caused by mixing operations with fundamentally different latency profiles in the same execution queue. The solution is not to tune CPU allocation — it is to separate the queues so that a slow SMTP operation cannot delay a time-sensitive push dispatch.

Channel specialization also simplifies back-pressure handling: an email worker that is rate-limited by its SMTP relay applies back-pressure only to the email queue, not to push throughput. This isolation is operationally valuable independent of the throughput arithmetic.

**Per-channel latency profiles:**

| Channel | Dispatch latency | Binding constraint |
|---------|-----------------|-------------------|
| APNs | ~5ms end-to-end | Connection pool / rate limit |
| FCM | ~5ms end-to-end | Rate limit |
| In-app | ~1ms (Redis write) | Redis throughput |
| Email | 100–300ms (SMTP handshake) | SMTP connection pool |
| SMS | ~50ms (Twilio API) | Twilio rate limit |

---

#### Per-Worker Throughput

**APNs rate limits — honest statement of what is known:**

Apple's documentation states that a single HTTP/2 connection to APNs supports up to 1,000 concurrent streams. This is a documented figure.

Apple does not publish a per-connection notification rate limit. Observed limits reported in engineering discussions and third-party push library documentation range from 500–1,000 notifications/sec per connection before APNs returns 429 responses. These observations vary by account tier, bundle ID, and Apple's internal policies, which change without notice. They are not a reliable design ceiling.

**Design decision:** Worker throughput is set conservatively relative to what the CPU arithmetic supports, and APNs connection count is sized to stay well below any plausible observed rate limit. The conservative sustained throughput figure will be validated and revised in load testing.

**Push worker critical-path CPU (async dispatch model):**

| Operation | Per-notification cost | Notes |
|-----------|----------------------|-------|
| ZPOPMIN batch fetch (50 items) | ~0.04ms | Amortized over batch |
| Payload serialization | ~0.10ms | — |
| Idempotency write (pipelined Redis SET) | ~0.05ms | Pipelined, amortized |
| APNs dispatch initiation | ~0.05ms CPU | Non-blocking; response in separate goroutine pool |
| **Total critical-path CPU** | **~0.24ms** | — |

At 0.25 vCPU: ~1,040 notifications/sec theoretical maximum. Design sustained throughput: **75/sec per push worker.** This leaves substantial headroom for queue contention, connection management, receipt processing, and real-world overhead. Running at well below theoretical maximum is intentional — it provides burst absorption without queue growth and avoids operating near APNs rate limits.

**Email workers:**

SMTP connection pool of 10 connections, 200ms per email (connection + relay acceptance):
```
10 connections / 0.200 sec = 50 emails/sec per worker
```

**In-app workers:**

Redis pipeline writes derated to ~3,000/sec sustained (accounting for pipeline flush overhead and key expiry operations).

**SMS workers:**

Twilio standard tier: 20 SMS/sec per account. One worker is sufficient for the volume derived in Section 1.3.

---

#### Worker Count and Provisioned Floor — Corrected Arithmetic

| Worker type | Channel load at 1,800/sec total | Per-worker throughput | Workers required | Deployed |
|------------|--------------------------------|----------------------|-----------------|----------|
| Push (APNs + FCM) | 1,260/sec (70% of 1,800) | 75/sec | 1,260 / 75 = 16.8 | **17** |
| Email | 144/sec (8% of 1,800) | 50/sec | 144 / 50 = 2.9 | **3** |
| In-app | 360/sec (20% of 1,800) | 3,000/sec capped at inbound | < 1 | **1** |
| SMS | 7/sec (from Section 1.3) | 20/sec | < 1 | **1** |
| **Total** | | | | **22 → 24 with 2 spare** |

**Provisioned floor — summed correctly:**

```
Push:   17 workers × 75/sec   = 1,275/sec
Email:   3 workers × 50/sec   =   150/sec
In-app:  1 worker, capped at  =   360/sec
SMS:     1 worker × 20/sec    =     7/sec
                               ──────────
Total provisioned              = ~1,792/sec → ~1,800/sec
```

This is how the 1,800/sec floor is derived: by summing per-channel contributions from channel-specialized workers. The prior draft's "24 workers × 75/sec = 1,800/sec" treated all workers as push workers and was arithmetically false. That error is corrected here.

**Instance sizing:**

Each push worker: ~0.25 vCPU, ~200MB RAM. On a c6g.2xlarge (8 vCPU, 16GB RAM): 8 push workers per instance, 3 email workers per instance (separate pool for scheduling isolation). Total instances: ~3 for push, 1 for email/in-app/SMS, plus 1 spare = **5 instances baseline.**

---

#### Auto-Scaling for Elevated and High Inbound Scenarios

The prior draft stated that scaling from 24 to 59 workers "takes ~4 minutes from pre-configured AMIs" without providing a source.

**Honest statement:** AWS EC2 instance launch time from a pre-configured AMI in a warm launch configuration is typically 2–5 minutes. Under regional load or availability zone pressure — which is correlated with the conditions that would trigger scaling — this can extend to 7–12 minutes. The 4-minute figure is plausible for a warm-cache AMI in a healthy region; it is not a reliable design input for incident response planning.

**Design response:** The response plan does not depend on a specific spin-up time. Shedding engages independently of whether new workers have come online.

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Alert | Queue depth > 60-second drain time at current throughput | Page on-call |
| Auto-scale | Queue depth > 3-minute drain time | Spin up additional workers |
| Shedding | Queue depth > 10-minute drain time, regardless of scaling status | Drop low-priority notifications; protect P0/P1 |

**Worker counts by scenario:**

| Scenario | Inbound | Workers needed | Response |
|----------|---------|---------------|----------|
| Base case | ~2