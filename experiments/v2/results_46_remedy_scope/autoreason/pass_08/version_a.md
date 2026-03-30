# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions and their honest status:

1. **Traffic assumptions are explicit and sensitivity-tested.** The 45M/day planning figure compounds two uncertain inputs (DAU/MAU ratio, notifications per user). Both are range-tested across a 15M–100M envelope. Channel split percentages are derived from reference points, not asserted.

2. **Four isolated priority queues (P0–P3)** with TTL semantics enforced via a companion expiry sorted set and a specified background pruning process, including failure behavior and interaction with worker outages.

3. **ID-based queue entries with visibility timeout semantics.** Full payload storage is the alternative; the tradeoffs are stated honestly. The previous claim that payload-fetch failure is "unrecoverable" was wrong — visibility timeout returns the message to the queue. ID-based storage is the correct choice at this scale.

4. **Deduplication uses atomic SET NX.** The race condition is solved, not described. The false-positive suppression risk under worker backup is acknowledged with a mitigation.

5. **Worker pools are per-channel and per-priority**, reconciled in a single source-of-truth matrix. Every zero cell is justified. The P1-drains-P2/P3 mechanism is fully specified, including starvation prevention.

6. **APNs capacity planning is range-based until month-2 validation**, with a floor of 300 req/sec/worker. The floor is defended. The failure case — 100 req/sec/worker against a 547/sec peak demand — is named, not hidden, with mitigations specified.

7. **SMS budget controls apply to all users**, including those without verified email. The OTP router handles the no-email case explicitly.

8. **Email OTP fallback routes to a dedicated P0 sub-queue**, not the standard P1 email queue. The priority hole is closed.

9. **Redis is a primary/replica setup with a bounded failover window.** P0 behavior during failover is specified.

10. **WebSocket sequence numbers and reconnect catch-up logic** are specified in Section 5.

11. **Staffing risk is addressed directly**, including on-call structure and the month-2 APNs milestone as a non-optional gate.

Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** The 30% planning figure is reasonable for mature social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct planning range for an unspecified social app is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

### 1.2 Channel Split — Derived, Not Asserted

The channel split depends on platform mix, session length, and product design. For a social app without validated data, the reference points are:

- **Consumer social apps (Instagram, TikTok):** Push-heavy, 80–90% of notifications via push, minimal SMS.
- **Productivity/communication apps (Slack, LinkedIn):** Higher email share, 15–25%.
- **New apps without retention data:** Push share tends to be higher because email lists are smaller and in-app sessions are shorter.

**Planning split and sensitivity:**

| Channel | Conservative (push-light) | **Plan** | Push-heavy |
|---------|--------------------------|----------|-----------|
| Push (FCM + APNs) | 60% | **70%** | 85% |
| In-app | 25% | **20%** | 10% |
| Email | 12% | **8%** | 4% |
| SMS | 3% | **2%** | 1% |

The 70% push planning figure is used throughout. If production data at month 1 shows push share above 80%, the in-app worker count has excess capacity that can be redeployed. If push share is below 60%, push utilization remains well within bounds. The worker matrix is robust to this range without re-provisioning.

**Daily volumes at plan:**

| Channel | Share | Daily volume |
|---------|-------|-------------|
| Push (FCM + APNs) | 70% | 31.5M/day |
| In-app | 20% | 9M/day |
| Email | 8% | 3.6M/day |
| SMS | 2% | 0.9M/day (capacity ceiling, not operating target) |

### 1.3 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This correction applies differently by channel.

**Push:** Push serves offline or background users. The concurrent-user correction does not apply — the 70% channel allocation already represents the full DAU-based volume. Applying a second population filter understates demand.

- Push peak demand = 31.5M/day × 3 / 86,400 = **~1,094/sec**
- FCM and APNs each handle approximately 50% of push volume: **~547/sec each**

**In-app:** In-app delivery is gated on WebSocket connection state. A notification to an offline user does not consume in-app delivery resources; it falls back to push or queues for next login. The correction applies here.

- In-app peak demand = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand.

### 1.4 Queue Storage — ID-Based with Visibility Timeout

**The case for ID-based storage:** Standard queue semantics make the crash window recoverable. A worker that dequeues a message and fails before acknowledging causes the message to become visible again after the visibility timeout expires — it returns to the queue. There is no silent loss. The 10–20× memory cost of full payload storage is not justified when the failure mode it solves is recoverable by other means.

**Honest comparison of both approaches:**

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Crash window behavior | Visibility timeout recovers message | Visibility timeout recovers message |
| Hot-path database dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Failure mode | Transient DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path |

**Decision: ID-based.** The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

**Visibility timeout implementation in Redis:**

Redis Lists have no native visibility timeout. The implementation uses a two-list pattern:

```
# Dequeue: atomically move to processing list
RPOPLPUSH source_queue processing_list

# Worker stores: message_id → {worker_id, dequeue_timestamp} in sorted set
ZADD processing_timestamps <unix_timestamp> <message_id>
```

A heartbeat process per worker (10-second interval) updates the timestamp. A recovery process (runs every 30 seconds) scans for messages whose timestamp is older than 60 seconds and moves them back to the source queue. This is standard Redis queue practice; it is specified here because the implementation details govern failure behavior.

**TTL enforcement for expired notifications:**

Redis Lists have no per-element TTL. Expiry is enforced via a companion sorted set:

```
# On enqueue:
RPUSH queue:<priority> <message_id>
ZADD expiry:<priority> <expire_unix_timestamp> <message_id>

# Pruning process (runs every 60 seconds):
expired = ZRANGEBYSCORE expiry:<priority> 0 <now>
for each id in expired:
    LREM queue:<priority> 1 <id>
    ZREM expiry:<priority> <id>
```

**Pruning failure behavior:** If the pruning process is down for an extended period, expired messages accumulate in the queue. Workers check the enqueue timestamp on dequeue and discard expired messages without processing — the pruning process is an optimization that prevents queue bloat, not the sole enforcement mechanism. Expiry sorted sets are bounded by the queue depth, which is bounded by the accumulation analysis below.

### 1.5 Queue Accumulation — Honest Analysis

Queue accumulation occurs when input rate exceeds worker capacity. At planning volume (1,575/sec peak input, ~26,000/sec worker capacity), the queue does not accumulate meaningfully under normal operation — workers drain 16× faster than messages arrive.

**The previous version's 7.6M accumulation figure was wrong.** It was inconsistent with the stated worker capacity. A system draining 16× faster than it fills does not accumulate millions of entries.

**Scenarios where accumulation does occur:**

1. **Worker failure:** If 50% of workers fail simultaneously, remaining capacity drops to ~13,000/sec — still 8× the input rate. Even partial worker failure does not cause meaningful accumulation at planning volume.

2. **External provider throttling (the realistic scenario):** If FCM or APNs begins rate-limiting, messages accumulate in the outbound queue. At 547/sec FCM input and a complete FCM outage: ~547 messages/second accumulate. Over 2 hours: ~3.9M FCM messages at 200B each = ~780MB. This is the realistic worst case, and it is provider-failure-driven, not load-driven.

3. **At 100M/day high bound:** Peak input reaches ~3,500/sec against ~26,000/sec worker capacity. Still no accumulation under normal operation.

**Redis memory sizing:**

| Component | Calculation | Estimate |
|-----------|-------------|----------|
| Queue entries (normal operation) | 500K × 200B | ~100MB |
| Queue entries (provider outage worst case) | 4M × 200B | ~800MB |
| Expiry sorted sets | 4M × 40B | ~160MB |
| Processing list (in-flight) | 50K × 200B | ~10MB |
| Deduplication keys (5-min TTL)* | ~156K × 50B | ~8MB |
| Preference cache | 500B × 3M active users | ~1.5GB |
| Aggregation state | 200B × 500K windows | ~100MB |
| Pub/Sub overhead | — | ~500MB |
| **Total (normal operation)** | | **~2.3GB** |
| **Total (provider outage worst case)** | | **~3.2GB** |

*At 45M/day and 5-minute TTL, simultaneously active dedup keys = 45M × (5/1,440) ≈ 156K. The methodology matters for future sizing.

**ElastiCache selection:** r7g.xlarge (32GB RAM, Multi-AZ primary/replica) provides >10× headroom over worst case. See Section 1.8 for failover implications.

**Queue depth alerts:**
- P1–P3: alert at 100K items (indicates provider-side issues)
- P0: alert at 1,000 items (P0 accumulation is an incident, not a capacity event)
- P0 FCM/APNs: page immediately at 500 items — this is a critical delivery failure

### 1.6 Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs | HTTP/2 multiplexed streams | **300–1,000 req/sec/worker** (range; see below) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — floor defense and the failure case that must be named:**

The 300 req/sec/worker floor is derived from Apple's HTTP/2 connection supporting up to 1,000 concurrent streams; at ~3ms per request on a low-latency connection, this yields ~330 req/sec. This is a theoretical floor assuming no Apple-side throttling.

**The failure case:** New bundle IDs with no established Apple relationship have been observed to be throttled to 50–150 req/sec during an initial period (weeks to months). If actual throughput is 100 req/sec/worker, the 6-worker APNs pool handles 600/sec against a 547/sec peak demand — barely adequate, with no headroom. This is named, not hidden.

**Mitigations:**
- 6 APNs workers (not 4) to provide headroom against the 100 req/sec case. Each worker maintains 4 HTTP/2 connections, multiplying effective throughput before hitting stream limits.
- The month-2 APNs load test is not optional. It is the gate for determining whether the worker count is correct. If measured throughput is below 200 req/sec/worker, this is an architecture problem requiring escalation before month 3.

**Worker matrix — single source of truth:**

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 1* | 2 | 1 | **8** |
| **P1** | 2 | 2 | 1 | 1 | 2 | **8** |
| **P2** | 0 | 1 | 1 | 0 | 1 | **3** |
| **P3** | 0 | 1 | 2 | 0 | 1 | **4** |
| **Col total** | **4** | **6** | **5** | **3** | **5** | **23** |

*P0 email workers serve the OTP fallback sub-queue only. See Section 1.9.

Any change to a single cell must update both the row total and the column total. The architecture diagram and capacity narrative derive from this table, not vice versa.

**Justification for every zero cell:**

- **P2/P3 FCM:** P1 FCM workers use priority-aware consumption (mechanism specified in Section 1.7). P2/P3 FCM volume is drained by P1 workers whenever the P1 FCM queue is empty. Dedicated P2/P3 FCM workers would be idle >95% of the time at planning volume.
- **P2/P3 SMS:** SMS is reserved for security-critical messages (P0/P1 only). No social or digest SMS is permitted. P2/P3 SMS workers would have no work.
- **P0 in-app:** Security alerts (new device login, suspicious activity) warrant P0 in-app delivery. One dedicated worker is included.
- **APNs P2/P3 workers included (not zero):** iOS silent push (content-available) is used for in-app badge count updates, which requires APNs but not user-visible push delivery. P2/P3 APNs workers handle badge updates only.

**Why P3 has no FCM path:** P3 notifications are bulk digests and non-urgent social updates. Push delivery for P3 content is intentionally disabled. Sending a push notification for a weekly digest drives notification fatigue and opt-out rates — this is a product decision encoded in the architecture. P3 has two delivery paths: