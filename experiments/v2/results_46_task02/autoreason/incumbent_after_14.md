# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Revision

Eight specific problems were identified in the prior draft. This revision addresses each directly. Where a problem exposed a genuine error, the error is corrected. Where a problem exposed missing material, the material is added. Where a problem exposed a false precision claim, the claim is replaced with an honest bound.

The eight problems and their dispositions:

| # | Problem | Disposition |
|---|---------|-------------|
| 1 | 24 × 75/sec = 1,800/sec is arithmetically false | Corrected; floor is derived from per-channel worker math, not a single multiplier |
| 2 | Viral cohort derivation circular-references itself | Acknowledged; the 35% assumption is replaced with a range and explicit epistemic status |
| 3 | SMS volume derived from undisclosed Section 1.3 | Section 1.3 written and included |
| 4 | Stress case labels don't match the math | Labels replaced with descriptive names; the arithmetic stands on its own |
| 5 | APNs rate limit source misrepresented | Two claims separated; sources and uncertainty stated accurately |
| 6 | 4-minute scaling claim has no basis | Replaced with a range and the basis for that range |
| 7 | Email head-of-line argument doesn't support the conclusion | Argument rewritten around queue scheduling, not CPU utilization |
| 8 | Section 1.4 referenced but absent | Section 1.4 written and included |

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social application with a 4-engineer team over 6 months.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Provisioned delivery floor at ~1,800/sec via channel-specialized workers | Derived from per-channel worker arithmetic; covers sustained peak with margin |
| Channel-specialized workers | Push notifications waiting behind SMTP connection establishment is a scheduling problem, not a CPU problem; specialization eliminates cross-channel queue interference |
| Priority queue via Redis ZSET with encoded score | Atomic priority + time ordering in single structure |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures |
| SMS spend counter in isolated Redis with no eviction | Closes race condition on spend cap enforcement |
| Auto-scaling pre-configured but not pre-running for high-inbound scenarios | High-inbound scenarios require multiple inputs to be simultaneously wrong; pre-running that capacity is not justified |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. It does not make the estimates reliable. Section 1.4 defines re-sizing triggers and validation paths for every major assumption that drives infrastructure sizing.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU; social app benchmark |
| Notifications/DAU/day | 17 average | Engaged-user benchmark; see Section 1.4 for sensitivity |
| **Total notifications/day** | **~50M** | Planning baseline |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark; see Section 1.4 for consequences if wrong |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 |
| Provisioned delivery floor | ~1,800/sec | Derived in Section 1.2 |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android |
| In-app | ~10M/day (20%) | Logged-in users only |
| Email | ~4M/day (8%) | Digests + transactional |
| SMS | ~360K/day | Derived in Section 1.3 |

---

### 1.2 Burst Model and Worker Sizing

#### Viral Cohort Baseline — Honest Derivation

The prior draft criticized the naive 2× assumption and substituted a 35% volume-share figure attributed to a log-normal distribution calibrated against a Facebook 2014 paper. The criticism of the 2× assumption was valid. The replacement was not structurally sounder — it was longer. Applying a top-decile ratio from a 2014 Facebook paper to the top 5% of a different platform in a different era is an assumption of the same epistemic quality as the figure it replaced. The integration over the distribution was not shown.

**Revised position:** The cohort volume share is unknown. The working assumption is a range of 20–50%, with 35% as the midpoint for sizing calculations. This range is not derived; it is a prior that should be replaced with measurement at launch. Section 1.4 defines the measurement and the re-sizing trigger.

```
Top 5% of DAU          = 150,000 users
Volume share range     = 20–50% of 50M/day = 10M–25M notifications/day
Per-user cohort range  = 67–167/day
Working midpoint       = 35% → 117/day → ~0.00135/sec
```

The key structural point — that the top cohort's baseline is substantially higher than the all-user average — holds across the entire plausible range. Under any assumption from 20% to 50%, the cohort baseline is 4–10× the all-user average. The prior draft's 2× assumption was wrong across the full range, not just at the midpoint.

---

#### Viral Spike Multiplier

The multiplier is the ratio of spike-period notification rate to a user's baseline rate during a sustained 15-minute viral event.

**Calibration:**

| Event type | Multiplier range | Basis |
|-----------|-----------------|-------|
| Moderate viral content (10K–100K engagements in 15 min) | 4–12× | Estimated from engagement rate × notification fan-out |
| Large viral event on a platform this size | 10–20× | Twitter engineering retrospectives describe this range for significant events; direct comparability is uncertain |

**Working assumption: 8×.** At 10M MAU, the platform is large enough to produce genuine viral events but unlikely to host accounts that produce Twitter-scale celebrity spikes. 8× sits at the upper end of the moderate-viral range and is the planning figure for sizing.

The multiplier depends on follower count of the viral account, content type, time of day, and fan-out configuration — none of which are known pre-launch. The 4–20× range reflects genuine uncertainty, not false precision around a point estimate.

---

#### Inbound Rate Estimates

Rather than labeling scenarios "2×" and "3×" — which implies a clean mathematical relationship that the arithmetic does not actually produce — the scenarios are named by their input assumptions.

**Base case** (working midpoint assumptions):
```
Viral cohort: 150,000 users × 0.00135/sec × 8× = ~1,620/sec
Remaining DAU: 2,850,000 × 17/day / 86,400    = ~560/sec
Total                                           = ~2,180/sec
```

**Elevated case** (cohort 50% larger, multiplier 50% higher):
```
Viral cohort: 225,000 × 0.00135 × 12 = ~3,645/sec
Remaining DAU:                          ~560/sec
Total                                  = ~4,205/sec
```
Both primary inputs simultaneously wrong by 50%. Plausible given no pre-launch data.

**High case** (cohort doubled, multiplier 75% higher):
```
Viral cohort: 300,000 × 0.00135 × 14 = ~5,670/sec
Remaining DAU:                          ~560/sec
Total                                  = ~6,230/sec
```
Both inputs simultaneously wrong by 75–100%. This corresponds to a genuinely viral launch event. The label "3×" was dropped because the output is ~2.85× the base case, not 3×. The scenario is real; the label was marketing.

These scenarios are not expected outcomes. They represent the range of plausible outcomes given the uncertainty in the inputs. The base case is not the expected case — it is the midpoint of a wide distribution.

---

#### Channel-Specialized Workers — The Actual Argument

The prior draft argued for channel specialization based on CPU utilization: email consuming 0.288 vCPU at scale would slow push workers. A reviewer correctly noted that this supports CPU allocation tuning within a multi-channel worker as readily as it supports specialization. That argument was wrong.

**The correct argument is about queue scheduling.**

In a multi-channel worker, a push notification waiting in the local dispatch queue sits behind whatever work the worker is currently executing. If the worker is mid-SMTP-handshake — which involves connection establishment, TLS negotiation, and a synchronous response from the mail relay — that push notification waits for the SMTP operation to complete before being dispatched. SMTP handshakes routinely take 100–300ms. APNs HTTP/2 dispatch takes ~5ms end-to-end.

This is not a CPU utilization problem. It is a head-of-line blocking problem caused by mixing operations with different latency profiles in the same execution queue. The solution is not to tune CPU allocation — it is to separate the queues so that a slow SMTP operation cannot delay a time-sensitive push dispatch.

Channel specialization also simplifies back-pressure handling: an email worker that is rate-limited by its SMTP relay applies back-pressure only to the email queue, not to push throughput. This isolation is operationally valuable independent of the throughput arithmetic.

---

#### Per-Worker Throughput

**APNs rate limits — honest statement of what is known:**

Apple's documentation states that a single HTTP/2 connection to APNs supports up to 1,000 concurrent streams. This is a documented figure (APNs documentation, current as of 2024).

Apple does not publish a per-connection notification rate limit. Observed limits reported in engineering discussions and third-party push library documentation range from 500 to 1,000 notifications/sec per connection before APNs returns 429 responses. These observations vary by account tier, bundle ID, and Apple's internal policies, which change without notice. They are not a reliable design ceiling.

**Design decision:** Rather than treating an observed lower bound as a conservative design figure, the worker throughput is set conservatively relative to what the CPU arithmetic supports, and the APNs connection count is sized to stay well below any plausible rate limit.

Each push worker holds 2 APNs connections and 1 FCM connection.

**Push worker critical-path CPU (async dispatch model):**

| Operation | Per-notification cost | Notes |
|-----------|----------------------|-------|
| ZPOPMIN batch fetch (50 items) | ~0.04ms | Amortized over batch |
| Payload serialization | ~0.1ms | |
| Idempotency write (pipelined Redis SET) | ~0.05ms | Pipelined, amortized |
| APNs dispatch initiation | ~0.05ms CPU | Non-blocking; response handled in separate goroutine pool |
| **Total critical-path CPU** | **~0.24ms** | |

At 0.25 vCPU: ~1,040 notifications/sec theoretical maximum. Applied conservatively at sustained throughput of **75/sec per push worker**, leaving substantial headroom for queue contention, connection management, receipt processing, and real-world overhead. This is not 10% of a documented limit — it is a conservative sustained figure that can be validated and revised upward in load testing.

**Email workers:**

SMTP handoff with a connection pool of 10 connections, 200ms per email (connection establishment + relay acceptance):
```
10 connections / 0.200 sec = 50 emails/sec per worker
```

**In-app workers:**

Redis pipeline writes at ~10,000 writes/sec per connection, derated to ~3,000/sec sustained for pipeline flush overhead and key expiry operations.

**SMS workers:**

Twilio standard tier rate limit: 20 SMS/sec per account (Twilio documentation). One worker is sufficient for the volume derived in Section 1.3.

---

#### Worker Count and Provisioned Floor — Corrected Arithmetic

| Worker type | Channel load at 1,800/sec total | Per-worker throughput | Workers required | Deployed |
|------------|--------------------------------|----------------------|-----------------|----------|
| Push (APNs + FCM) | 1,260/sec (70% of 1,800) | 75/sec | 1,260 / 75 = 16.8 | **17** |
| Email | 144/sec (8% of 1,800) | 50/sec | 144 / 50 = 2.9 | **3** |
| In-app | 360/sec (20% of 1,800) | 3,000/sec | 0.12 | **1** |
| SMS | 7/sec (from Section 1.3) | 20/sec | 0.35 | **1** |
| **Total** | | | | **22 → round to 24 with 2 spare** |

**Provisioned floor derivation:**

```
Push:   17 workers × 75/sec  = 1,275/sec
Email:   3 workers × 50/sec  =   150/sec
In-app:  1 worker  × 3,000/sec → capped at 360/sec by inbound
SMS:     1 worker  × 20/sec  =     7/sec (from Section 1.3)
                               ─────────
Total provisioned             = ~1,792/sec → ~1,800/sec
```

This is how the 1,800/sec floor is reached: by summing the per-channel contributions from channel-specialized workers. The prior draft's "24 workers × 75/sec = 1,800/sec" was arithmetically false and is corrected here.

---

#### Auto-Scaling for Elevated and High Inbound Scenarios

The prior draft stated that scaling from 24 to 59 workers "takes ~4 minutes from pre-configured AMIs." No source was provided for this figure.

**Honest statement:** AWS EC2 instance launch time from a pre-configured AMI in a warm launch configuration (instance already initialized in a stopped state, or using EC2 Fleet with capacity reservations) is typically 2–5 minutes. Under regional load or availability zone pressure — which is correlated with the conditions that would trigger scaling — this can extend to 7–12 minutes. The 4-minute figure is plausible for a warm-cache AMI in a healthy region; it is not reliable as a design input for incident response planning.

**Design response:** The auto-scaling response plan does not depend on a specific spin-up time. Instead:

- Alert threshold: queue depth exceeds 60-second drain time at current throughput.
- Auto-scaling trigger: queue depth exceeds 3-minute drain time (fires before alert becomes critical).
- Shedding trigger: queue depth exceeds 10-minute drain time at current throughput, regardless of scaling status.

Shedding engages independently of whether new workers have come online. The response plan works whether spin-up takes 4 minutes or 12 minutes.

Worker counts for elevated/high scenarios:

| Scenario | Inbound | Workers needed | Scaling action |
|----------|---------|---------------|----------------|
| Base case | ~2,200/sec | ~30 | Auto-scale from 24 |
| Elevated | ~4,200/sec | ~57 | Auto-scale; shedding may engage |
| High | ~6,200/sec | ~84 | Incident response required; shedding active |

---

### 1.3 SMS Volume Derivation

This section was referenced but absent in the prior draft. SMS has the highest per-unit cost of any channel and drives the spend cap design, so the derivation must be explicit.

**SMS use cases on this platform:**

| Use case | Volume basis |
|----------|-------------|
| Phone number verification (registration) | New user registrations |
| Two-factor authentication (login) | Active user login events |
| Critical account alerts (password reset, suspicious login) | Security event rate |

SMS is not used for social notifications (likes, comments, follows) — those go to push and in-app. SMS is reserved for transactional and security events where delivery confirmation matters and the user may not have the app installed.

**Registration SMS:**

New user registrations on a growing 10M MAU app: assume 1% monthly growth = 100,000 new users/month = ~3,300/day. Phone verification rate: ~60% of new registrations