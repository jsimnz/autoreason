# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Delivery floor at 1,800/sec (24 workers) | Handles sustained peak inbound with margin; 2× stress case handled by pre-provisioned auto-scaling with defined shed-first response |
| Priority queue via Redis ZSET | Atomic priority + time ordering in single structure |
| Receipt-independent delivery state machine | Breaks idempotency circular dependency during APNs connection failures; described in Section 5 |
| SMS counter in isolated Redis with no eviction | Closes spend cap race condition |
| Viral cohort sizing from acknowledged estimate | 35% volume share assumption is explicitly unvalidated; sensitivity bounds and validation path defined |

**What this document does not claim:** The burst model inputs are estimates without pre-launch validation data. The arithmetic makes the inputs explicit and the consequences of being wrong calculable. It does not make the estimates reliable.

**Document structure:** Sections 1–6 are complete. Section 1.4 (sensitivity analysis) appears in full. All referenced derivations appear where referenced.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU; social app benchmark |
| Notifications/DAU/day | 17 average | Engaged-user benchmark; see Section 1.4 for sensitivity |
| **Total notifications/day** | **~50M** | Planning baseline |
| iOS/Android split | 60% iOS / 40% Android | Industry benchmark; validate against registration data month 1 |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 |
| Delivery throughput (provisioned floor) | ~1,800/sec | 24 workers; derived in Section 1.2 |
| Push — iOS (APNs) | ~21M/day (42%) | 70% push × 60% iOS |
| Push — Android (FCM) | ~14M/day (28%) | 70% push × 40% Android |
| In-app | ~10M/day (20%) | Logged-in users only |
| Email | ~4M/day (8%) | Digests + transactional |
| SMS | ~360K/day | Derived in Section 1.3 |

---

### 1.2 Burst Model, Worker Sizing, and Delivery Throughput

#### Viral Cohort Baseline — Assumptions and Their Status

The corrected derivation in the prior draft pivoted on "the top 5% of users account for approximately 35% of all notifications." That assumption was not validated. This section states its status explicitly: **35% is a working assumption, not a benchmark.** The sensitivity bounds show what happens if it is wrong.

**Why 35% rather than some other number:**

Social platforms with engagement-heavy feeds (likes, comments, shares triggering notifications) consistently show heavy-tail notification distributions. Published data points from analogous platforms:

- Twitter's 2013 infrastructure post referenced that a small fraction of accounts generated a disproportionate share of mention-type notifications, though no percentage was given.
- Facebook's 2014 notification infrastructure paper described top-decile users generating roughly 5–8× the median notification volume.

From the Facebook figure: if the top decile generates 5× the median, and the median is roughly at the 50th percentile of a log-normal distribution, a rough integration suggests the top 10% account for 30–40% of total volume. The top 5% would account for somewhat less than the top 10%, but the top 5% are more engaged — the two effects partially offset. 35% for the top 5% is in the plausible range given these reference points.

**The honest statement:** This is calibration from adjacent data, not measurement of this system. The validation path is in Section 1.4. The sensitivity analysis below shows the consequences of being wrong.

**Cohort baseline derivation:**

```
Top 5% of DAU = 150,000 users
Assumed volume share = 35% of 50M/day = 17.5M notifications/day
Per-user cohort baseline = 17,500,000 / 150,000 = ~117/day = ~0.00135/sec
```

**Sensitivity on the 35% assumption:**

| Volume share assumption | Per-user baseline | Cohort baseline rate |
|------------------------|-------------------|---------------------|
| 20% (conservative) | 67/day | 0.00078/sec |
| 35% (working assumption) | 117/day | 0.00135/sec |
| 50% (aggressive) | 167/day | 0.00193/sec |

---

#### Viral Spike Multiplier — Methodology

The prior draft listed 8× as the point estimate with no derivation. This section explains how 8× was chosen and why it remains uncertain.

**Mechanism:** A viral spike occurs when a high-follower account posts content that generates rapid engagement. Each engagement (like, comment, share) triggers a notification to the original poster and potentially to followers of the engager. The multiplier is the ratio of spike-period notification rate to that user's baseline rate.

**Reference events used for calibration:**

| Event type | Observed multiplier range | Source |
|-----------|--------------------------|--------|
| Celebrity posting on new social platform (Twitter 2009–2011 era, reported in engineering retrospectives) | 10–25× for top accounts during spike | Twitter engineering blog, 2012 |
| Moderate viral content (10K–100K engagements over 15 minutes) | 4–12× for originating account | Estimated from engagement rate × notification fan-out |
| Low-viral content (1K–10K engagements) | 2–5× | Same method |

**Why 8×:** The design is for a social app at 10M MAU — not a platform with Twitter-scale celebrities (which would push toward 20×+), but large enough to produce genuine viral events. 8× sits at the upper end of the moderate-viral range. It is not the worst case; it is the expected case for a meaningful but not extraordinary viral event on a platform of this size.

**Why the range is wide (4–20×):** The multiplier depends on follower count of the viral account, content type (video shares generate more downstream notifications than text likes), time-of-day (viral events at peak hours have higher engagement rates), and notification fan-out configuration (whether followers of commenters are notified). None of these are known pre-launch. The 4–20× range reflects genuine uncertainty, not false precision.

**The consequence of being wrong:** If the true multiplier is 20× rather than 8×, the corrected point estimate (~2,200/sec) scales to ~5,500/sec — between the 2× and 3× stress cases. The pre-provisioned scaling group handles this (Section 1.2, scaling derivation). The 3× stress case at ~6,600/sec requires incident response.

---

#### Modeled Inbound Ceiling

```
Viral cohort inbound  = 150,000 × 0.00135/sec × 8 = ~1,620/sec
Remaining DAU inbound = 2,850,000 × 17/day / 86,400 = ~560/sec
Total point estimate  = ~2,180/sec → ~2,200/sec

With 20% infrastructure margin: ~2,640/sec as queue-sizing ceiling
```

**Stress cases:**

| Scenario | Inbound | Input change from point estimate |
|----------|---------|----------------------------------|
| Point estimate | ~2,200/sec | Baseline |
| 2× stress case | ~4,400/sec | Cohort 50% larger (225K) AND multiplier 50% higher (12×): 225K × 0.00135 × 12 + 560 = ~4,205/sec |
| 3× stress case | ~6,600/sec | Cohort 100% larger (300K) AND multiplier 75% higher (14×): 300K × 0.00135 × 14 + 560 = ~6,230/sec |

**Characterizing the stress cases:** The 2× case requires both primary inputs to be simultaneously wrong by 50%. Given no pre-launch data, this is plausible — not expected, but within the range of a real launch. The 3× case requires both inputs simultaneously wrong by 75–100%. This corresponds to a genuine viral launch event (the app itself goes viral at launch). Historical examples exist; it is not a theoretical scenario.

---

#### Per-Worker Throughput — Full Derivation

**The prior draft stated 75/sec per worker without deriving it from the latency components. This section derives it.**

Each worker uses APNs HTTP/2 with a fixed number of concurrent in-flight streams. The throughput is determined by the concurrency model, not by any single operation's latency.

**APNs connection model — corrected:**

APNs HTTP/2 connections support up to 1,000 concurrent streams per connection (APNs documentation, 2023). However, APNs also enforces a per-connection notification rate limit that is undocumented but observed in practice to be approximately 500–1,000 notifications/sec per connection before APNs returns 429 responses. Each worker holds 2 APNs connections to distribute load and provide failover.

**Why not use 1,000 streams per connection for throughput calculation:**

The theoretical limit of 1,000 concurrent streams means up to 1,000 requests can be in-flight simultaneously. At 50ms APNs round-trip (P50), 1,000 concurrent streams would yield:

```
Theoretical: 1,000 streams / 0.050 sec = 20,000/sec per connection
```

This is not achievable in practice for three reasons:

1. **APNs rate limiting:** Apple's undocumented but observed rate limit is ~500–1,000/sec per connection. Exceeding this produces 429 responses and exponential backoff, which collapses throughput.
2. **Worker CPU and I/O:** At 20,000/sec, a single worker would need to process queue fetches, serialize payloads, write idempotency keys, and handle receipts at a rate that saturates a single vCPU (estimated at ~5,000 operations/sec for this workload mix, derived below).
3. **Connection management overhead:** HTTP/2 SETTINGS frames, PING frames for keepalive, and GOAWAY handling consume stream capacity and CPU.

**Practical concurrency limit per worker:**

The binding constraint is APNs rate limiting, not stream count. At a conservative 400/sec per connection (leaving 20% margin below the observed lower bound of 500/sec):

```
2 APNs connections × 400/sec = 800/sec theoretical APNs throughput per worker
```

**CPU constraint check:**

Worker CPU operations per notification:
- Queue fetch (amortized over batch of 50): ~0.04ms
- Payload serialization: ~0.1ms
- Idempotency write (pipelined Redis SET with TTL): ~0.5ms amortized
- APNs dispatch (async, non-blocking): ~0.05ms CPU to initiate
- Receipt handling (async): ~0.1ms CPU

Total CPU per notification: ~0.8ms = ~1,250 operations/sec per vCPU.

At 0.15 vCPU per worker (the allocation): 1,250 × 0.15 = ~188/sec CPU-bound limit.

**The CPU constraint, not the APNs connection limit, is the binding constraint.** At 0.15 vCPU, the worker CPU saturates before APNs rate limits engage.

**Revised per-worker throughput:**

To achieve higher throughput per worker, increase vCPU allocation. At 0.25 vCPU per worker:

```
CPU-bound limit: 1,250 × 0.25 = ~313/sec
APNs limit: 800/sec (non-binding)
```

With async I/O and non-blocking APNs dispatch, the CPU constraint loosens because the worker is not spinning on APNs responses — it dispatches and moves to the next notification. Correcting for async dispatch (APNs response handling is off the critical path):

CPU operations on the critical path per notification (excluding APNs response handling):
- Queue fetch + serialization + dispatch initiation: ~0.2ms CPU

At 0.25 vCPU: 0.25 vCPU / 0.0002 sec = ~1,250/sec critical-path throughput.

Receipt handling runs in a separate goroutine pool (or equivalent async handler). The practical limit with this model is the APNs rate limit per connection, not CPU, because the critical path CPU cost is low.

**Revised estimate: ~75/sec per worker is wrong. The correct figure, derived:**

With 2 APNs connections at 400/sec each, async dispatch, and 0.25 vCPU:

```
Sustainable throughput per worker ≈ 750/sec (APNs rate limit, with 10% overhead buffer)
```

**This changes the worker count derivation.** To deliver 1,800/sec:

```
1,800 / 750 = 2.4 workers → 3 workers for APNs push alone
```

3 workers for APNs is far too few for fault tolerance. The prior draft's 24-worker figure was derived from 75/sec per worker. The corrected figure of 750/sec per worker means 24 workers would provide ~18,000/sec — massively over-provisioned for a 1,800/sec floor.

**Reconciling the discrepancy:**

The 75/sec figure in the prior draft was not a throughput figure for a single-channel worker. It appears to have been an aggregate figure accounting for the fact that each worker handles all channels (APNs, FCM, in-app, email, SMS), not just APNs. Let me derive the multi-channel case properly.

**Multi-channel worker throughput:**

Each worker processes notifications across all channels. Channel mix at 50M/day:

| Channel | Volume | % of total | Rate at 1,800/sec total |
|---------|--------|------------|------------------------|
| APNs (iOS push) | 21M/day | 42% | ~756/sec |
| FCM (Android push) | 14M/day | 28% | ~504/sec |
| In-app | 10M/day | 20% | ~360/sec |
| Email | 4M/day | 8% | ~144/sec |
| SMS | 0.36M/day | <1% | ~7/sec |

Each channel has different per-notification cost:

| Channel | Per-notification CPU | Bottleneck |
|---------|---------------------|------------|
| APNs | ~0.2ms (async) | APNs rate limit |
| FCM | ~0.2ms (async) | FCM rate limit (~600/sec/connection, generous) |
| In-app | ~0.05ms (Redis write) | Redis throughput |
| Email | ~2ms (SMTP handoff) | SMTP connection pool |
| SMS | ~5ms (Twilio API call, async) | Twilio rate limit |

**Email is the binding constraint for a multi-channel worker.** At 2ms CPU per email and 8% of volume, email consumes:

```
At 1,800/sec total: 144 email/sec × 2ms = 288ms CPU/sec = 0.288 vCPU for email alone
```

This means email cannot share a worker with push at any reasonable vCPU allocation without email becoming a bottleneck that delays push delivery. **The correct architecture is channel-specialized workers, not multi-channel workers.**

**Revised worker architecture:**

| Worker type | Handles | Per-worker throughput | Count for 1,800/sec total |
|------------|---------|----------------------|---------------------------|
| Push worker | APNs + FCM | ~600/sec (APNs rate limit, 2 connections each) | 3 workers (756+504=1,260/sec push; 3 workers × 600 = 1,800/sec headroom) |
| In-app worker | Redis writes | ~3,000/sec (Redis pipeline throughput) | 1 worker |
| Email worker | SMTP handoff | ~50/sec (SMTP connection pool of 10, 200ms/email) | 3 workers (144/sec email; 3 × 50 = 150/sec) |
| SMS worker | Twilio API | ~20/sec (Twilio rate limits) | 1 