# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses eleven specific criticisms of the previous version. Each section notes what changed and why. Where a criticism identified a genuine error, the error is corrected. Where a criticism identified an underspecified mechanism, the mechanism is now specified. Where a criticism identified a false claim in the executive summary, the claim is either substantiated or removed.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions and their honest status:

1. **Traffic assumptions are explicit and sensitivity-tested.** The 45M/day planning figure compounds two uncertain inputs (DAU/MAU ratio, notifications per user). Both are range-tested across a 15M–100M envelope.

2. **Four isolated priority queues (P0–P3)** with TTL semantics enforced via a companion expiry sorted set and a background pruning process. The pruning process is now specified: frequency, failure behavior, and interaction with worker outages.

3. **ID-based queue entries with visibility timeout semantics**, not full payload storage. The previous version incorrectly claimed payload-fetch failure was unrecoverable. It is recoverable via visibility timeout. ID-based storage is the correct choice; full payload storage is the alternative with explicit tradeoffs.

4. **Deduplication uses atomic SET NX.** The race condition is solved, not described. The false-positive suppression risk under worker backup is now acknowledged with a mitigation.

5. **Worker pools are per-channel and per-priority**, reconciled in a single source-of-truth matrix. The P1-drains-P2/P3 mechanism is now fully specified, including starvation prevention.

6. **APNs capacity planning is range-based until month-2 validation**, with a floor of 300 req/sec/worker. The floor is now defended with a failure case analysis. If actual throughput is 100 req/sec/worker, the system has a capacity deficit — this is named, not hidden.

7. **SMS budget controls apply to all users**, including those without verified email. The previous OTP router had a gap that allowed budget bypass for users without email. This is corrected.

8. **Redis is a primary/replica setup with a bounded failover window.** The previous version claimed no single point of failure while accepting an unacknowledged failover gap in the queue store. The gap is now bounded and P0 behavior during failover is specified.

9. **WebSocket sequence numbers and reconnect catch-up logic are in Section 5.** The previous version referenced Section 5 that did not exist. It now exists.

10. **Channel split percentages are derived, not asserted.** Sensitivity analysis is applied to the channel split.

11. **Staffing risk is addressed directly**, including on-call structure and the month-2 APNs milestone timeline.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** The 30% planning figure is reasonable for mature social apps. The correct planning range for an unspecified social app at launch is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

### 1.2 Channel Split — Derived, Not Asserted

*Changed from previous version: the channel split was previously asserted without derivation. It now has a basis and sensitivity analysis, because the split directly determines worker counts and budget allocations.*

The channel split depends on platform mix (iOS/Android vs. web), session length, and product design. For a social app without validated data, the reference points are:

- **Consumer social apps (Instagram, TikTok):** Push-heavy, 80–90% of notifications delivered via push, minimal SMS.
- **Productivity/communication apps (Slack, LinkedIn):** Higher email share, 15–25%.
- **New apps without retention data:** Push share tends to be higher because email lists are smaller and in-app sessions are shorter.

**Planning split and sensitivity:**

| Channel | Conservative (push-light) | **Plan** | Push-heavy |
|---------|--------------------------|----------|-----------|
| Push (FCM + APNs) | 60% | **70%** | 85% |
| In-app | 25% | **20%** | 10% |
| Email | 12% | **8%** | 4% |
| SMS | 3% | **2%** | 1% |

The 70% push planning figure is used throughout. If production data at month 1 shows push share above 80%, the in-app worker count (5) has excess capacity that can be redeployed. If push share is below 60%, push utilization remains well within bounds. The worker matrix is robust to this range without re-provisioning.

**Daily volumes at plan:**

| Channel | Share | Daily volume |
|---------|-------|-------------|
| Push (FCM + APNs) | 70% | 31.5M/day |
| In-app | 20% | 9M/day |
| Email | 8% | 3.6M/day |
| SMS | 2% | 0.9M/day (capacity ceiling, not operating target) |

### 1.3 Queue Storage — ID-Based with Visibility Timeout

*Changed from previous version: the previous version incorrectly claimed that ID-based storage creates an "unrecoverable" crash window. This was wrong. The error is corrected here, and the actual tradeoff between approaches is stated honestly.*

**The previous claim was wrong.** Standard queue semantics (SQS, or Redis with explicit visibility timeout implementation) make the crash window recoverable: a worker that dequeues a message and fails before acknowledging it causes the message to become visible again after the visibility timeout expires. It returns to the queue. There is no silent loss.

**Correct framing — two legitimate approaches with different tradeoffs:**

**Option A: ID-based queue entries**
- Queue entry contains: notification ID, priority, enqueue timestamp, channel
- Worker dequeues ID, fetches full payload from the notification database, processes, acknowledges
- Crash window behavior: visibility timeout returns the message to the queue; payload fetch is retried on the next dequeue
- Memory cost: ~100–200B per queue entry
- Failure mode: payload fetch fails if the notification database is unavailable. This is a recoverable failure (message returns to queue) but creates a dependency between the queue and the database on the hot path.

**Option B: Full payload in queue entries**
- Queue entry contains the complete notification payload
- Worker dequeues and processes without a database fetch
- Crash window behavior: same visibility timeout semantics apply; no additional database dependency
- Memory cost: ~500B–2KB per queue entry (10–20× more than Option A)
- Failure mode: eliminates the database dependency on the hot path; payload is self-contained

**Decision: Option A (ID-based).** The database dependency on the payload fetch is acceptable because: (a) the notification database is a managed PostgreSQL instance with 99.99% availability, and (b) the visibility timeout means a transient fetch failure does not lose the message. The 10–20× memory cost of Option B is not justified when the failure mode it solves is recoverable by other means.

**Visibility timeout implementation in Redis:**

Redis Lists do not have native visibility timeout semantics. The implementation uses a two-list pattern:

```
PROCESSING_LIST: rpoplpush SOURCE_QUEUE PROCESSING_LIST
```

A message moved to the processing list is invisible to other workers. A separate heartbeat process (one per worker, 10-second interval) resets a per-message timestamp in a sorted set. A recovery process (runs every 30 seconds) scans the sorted set for messages whose timestamp is older than 60 seconds and moves them back to the source queue. This is standard Redis queue practice; it is specified here because the implementation details matter for failure behavior.

**Memory sizing with ID-based storage:**

At 1,575/sec input and the queue accumulation scenario described in Section 1.4, peak queue depth is ~500K entries at planning volume (the 7.6M figure from the previous version was wrong; see Section 1.4 for the corrected analysis).

| Component | Calculation | Estimate |
|-----------|-------------|----------|
| Queue entries (ID-based) | 500K × 200B | ~100MB |
| Expiry sorted sets | 500K × 40B | ~20MB |
| Processing list (in-flight) | 50K × 200B | ~10MB |
| Deduplication keys (5-min TTL) | ~156K × 50B | ~8MB |
| Preference cache | 500B × 3M active users | ~1.5GB |
| Aggregation state | 200B × 500K windows | ~100MB |
| Pub/Sub overhead | — | ~500MB |
| **Total** | | **~2.3GB** |

**ElastiCache selection:** r7g.xlarge (32GB RAM) provides >10× headroom. This is a primary/replica setup with Multi-AZ failover. The failover implications for P0 queues are addressed in Section 1.6.

### 1.4 Queue Accumulation — Corrected Analysis

*Changed from previous version: the previous version claimed 7.6M entries accumulate during the 2-hour spike while simultaneously stating that worker capacity (26,000/sec) exceeds input rate (1,575/sec) by 16×. These claims are contradictory. The accumulation scenario is corrected here.*

**The previous math was wrong.** If worker capacity exceeds input rate at all times, the queue drains continuously and accumulation does not occur. The 7.6M figure was not defensible.

**Correct accumulation analysis:**

Queue accumulation occurs when input rate exceeds worker capacity. At the planning volume (1,575/sec peak input, ~26,000/sec worker capacity), the queue does not accumulate meaningfully — workers drain faster than messages arrive. The system operates in continuous-drain mode.

**Scenarios where accumulation does occur:**

1. **Worker failure:** If 50% of workers fail simultaneously (e.g., a bad deploy), remaining capacity drops to ~13,000/sec — still 8× the input rate. Even partial worker failure does not cause accumulation at planning volume.

2. **External provider throttling:** If FCM or APNs begins rate-limiting at the provider end, messages accumulate in the outbound queue. At 1,575/sec input and FCM handling 547/sec of that, a complete FCM outage accumulates ~547 messages/second. Over 2 hours: ~3.9M FCM messages. At 200B each: ~780MB. This is the realistic accumulation scenario, and it is provider-failure-driven, not load-driven.

3. **At 100M/day high bound:** Peak input reaches ~3,500/sec. Worker capacity remains ~26,000/sec. Still no accumulation under normal operation.

**Honest conclusion:** The memory sizing exercise in the previous version was built on a number that contradicted the capacity figures. The correct Redis memory requirement for queue storage is ~100MB under normal operation, with a realistic worst-case of ~1–2GB under sustained provider outage. The r7g.xlarge selection has more than sufficient headroom for all scenarios.

**Queue depth alerts (corrected):**
- P1–P3: alert at 100K items (indicating provider-side issues)
- P0: alert at 1,000 items (P0 accumulation is an incident)
- P0 FCM/APNs: page immediately at 500 items; this is a critical delivery failure

### 1.5 Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2 multiplexed streams | **300–1,000 req/sec/worker** (unvalidated range; see below) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — floor defense and failure case:**

*Changed from previous version: the 300 req/sec/worker floor was stated without defense. It is now defended, and the failure case (100 req/sec/worker) is explicitly named.*

The 300 req/sec/worker floor is derived from: Apple's HTTP/2 connection supports up to 1,000 concurrent streams; at ~3ms per request on a low-latency connection, this yields ~330 req/sec. This is a theoretical floor assuming no Apple-side throttling.

**The failure case that must be named:** New bundle IDs with no established Apple relationship have been observed in production environments to be throttled to 50–150 req/sec during the initial period (weeks to months). If actual throughput is 100 req/sec/worker, the 4-worker APNs pool handles 400/sec against a 547/sec peak demand. The system ships with a known iOS push capacity deficit.

**Mitigations for the 100 req/sec failure case:**
- Increase APNs workers to 8 before launch (costs one additional ECS task, ~$50/month; acceptable insurance)
- Implement APNs connection pooling: each worker maintains 4 HTTP/2 connections, multiplying effective throughput
- The month-2 load test is not optional — it is the gate for determining whether the APNs worker count is correct

The revised worker matrix below includes 6 APNs workers (not 4) to provide headroom against the 100 req/sec failure case.

**Worker matrix — single source of truth:**

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 1* | 2 | 1 | **8** |
| **P1** | 2 | 2 | 1 | 1 | 2 | **8** |
| **P2** | 0 | 1 | 1 | 0 | 1 | **3** |
| **P3** | 0 | 1 | 2 | 0 | 1 | **4** |
| **Col total** | **4** | **6** | **5** | **3** | **5** | **23** |

*P0 email workers serve the OTP fallback sub-queue only. See Section 1.7.

**Justification for every zero cell:**

- **P2/P3 FCM:** P1 FCM workers use priority-aware consumption (mechanism specified below). P2/P3 FCM volume is drained by P1 workers during any period when the P1 FCM queue is empty. Dedicated P2/P3 FCM workers would be idle >95% of the time at planning volume.
- **P2/P3 SMS:** SMS is reserved for security-critical messages (P0/P1 only). No social or digest SMS is permitted.
- **P0 in-app:** Security alerts (new device login, suspicious activity) warrant P0 in-app delivery. One dedicated worker.

**Why P3 has no FCM path:** P3 notifications are bulk digests and non-urgent social updates. Sending push for weekly digests drives notification fatigue and opt-out. This is a product decision encoded in the architecture. P3 has two delivery paths: in-app for active sessions, email for everyone else. APNs P2/P3 workers are included because iOS silent push (content-available) is used for in-app badge count updates, which requires APNs but not user-visible push delivery.

### 1.6 P1-Drains-P2/P3 — Mechanism Specified

*Changed from previous version: the P1-drains-P2/P3 behavior was asserted without specifying the mechanism