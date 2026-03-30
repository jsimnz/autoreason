# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document covers a notification system handling 45M notifications/day (planning figure; range-tested from 15M to 100M) across push, email, in-app, and SMS channels. The primary architectural decisions:

- **Four priority queues (P0–P3)** with TTL enforcement via companion sorted sets and a pruning process that uses a Sorted Set–based queue structure to avoid O(N) scan costs
- **ID-based queue entries** with visibility timeout semantics; tradeoffs versus full payload storage are stated explicitly
- **Deduplication via atomic SET NX** applied at the point of external delivery, not at dequeue; the interaction with the visibility timeout recovery process is specified
- **Per-channel, per-priority worker pools** with a P1-drains-lower-priority mechanism and starvation prevention
- **APNs worker count sized for a throttled-throughput scenario**, with a genuine capacity mitigation (not just a monitoring plan), and an honest acknowledgment that the month-2 load test creates schedule risk in a 6-month project
- **FCM/APNs split treated as an uncertain input** with sensitivity analysis, not asserted as 50/50
- **SMS ceiling defined and enforced** at the infrastructure level, with fallback behavior specified
- **Preference cache memory estimated with a realistic range**, not a single figure
- **In-app catch-up load pattern addressed** alongside the steady-state estimate

The document is complete. All sections referenced in the body are present.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both primary inputs to daily volume are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% as a planning figure is reasonable for mature social apps. The correct planning range for an unspecified app is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

### 1.2 Channel Split — Derived, Not Asserted

| Channel | Conservative | **Plan** | Push-heavy |
|---------|-------------|----------|-----------|
| Push (FCM + APNs) | 60% | **70%** | 85% |
| In-app | 25% | **20%** | 10% |
| Email | 12% | **8%** | 4% |
| SMS | 3% | **2%** | 1% |

**Daily volumes at plan:**

| Channel | Share | Daily volume |
|---------|-------|-------------|
| Push (FCM + APNs) | 70% | 31.5M/day |
| In-app | 20% | 9M/day |
| Email | 8% | 3.6M/day |
| SMS | 2% | 0.9M/day (ceiling; enforcement in Section 1.9) |

### 1.3 FCM/APNs Split — Treated as Uncertain Input

The previous version asserted 50/50 FCM/APNs split without justification. Platform mix varies significantly by geography, app category, and user demographics. This is an equally uncertain input to DAU/MAU ratio and must be sensitivity-tested because it directly governs APNs worker sizing.

**Reference points:**
- US-centric consumer social apps: iOS share often 55–65% (higher income demographics, early adopters)
- Global or emerging-market apps: Android share often 70–85%
- Unknown app with no stated market: 40/60 to 60/40 iOS/Android is the defensible planning range

**Sensitivity table (push peak = ~1,094/sec):**

| Scenario | FCM share | FCM peak | APNs share | APNs peak |
|----------|-----------|----------|------------|-----------|
| Android-heavy | 70% | ~766/sec | 30% | ~328/sec |
| **Plan (50/50)** | **50%** | **~547/sec** | **50%** | **~547/sec** |
| iOS-heavy | 35% | ~383/sec | 65% | ~711/sec |

**Planning decision:** Size APNs workers for the iOS-heavy scenario (711/sec peak demand), not the 50/50 scenario. This is the correct conservative choice because APNs has the more constrained throughput per worker and the more severe throttling risk for new bundle IDs. If production data at month 1 shows Android-heavy split, APNs workers have excess capacity; this is an acceptable outcome. Sizing for the optimistic split and being wrong creates an incident.

**APNs worker sizing is therefore based on 711/sec peak demand, not 547/sec.** This changes the worker count and headroom analysis in Section 1.6.

### 1.4 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak.

**Push:** Serves offline or background users. The correction does not apply — push peak demand is the full DAU-based volume.

- Push peak = 31.5M/day × 3 / 86,400 = **~1,094/sec total**
- APNs peak (iOS-heavy sizing): ~711/sec
- FCM peak (iOS-heavy sizing): ~383/sec

**In-app (steady-state):** Gated on WebSocket connection state. Offline users queue for next login.

- In-app steady-state peak = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

**In-app catch-up load:** The 63/sec figure understates peak in-app delivery load. When users log back in after a period offline, queued notifications are delivered in a burst. This creates a catch-up spike that is not captured by the steady-state estimate.

**Catch-up load analysis:**

Assume a post-peak login surge: 20% of DAU (600K users) log in within 2 hours following peak. Each has an average of 8 queued in-app notifications (lower than the 15/day planning figure because active users receive in-app delivery in real time; this queue represents the offline backlog).

- Catch-up volume = 600K users × 8 notifications = 4.8M notifications over 2 hours
- Catch-up rate = 4.8M / 7,200 seconds = **~667/sec**

This is 10× the steady-state estimate. The in-app worker pool must handle 667/sec burst, not 63/sec steady state. Worker sizing in Section 1.6 uses 667/sec as the in-app design point. The 63/sec figure is accurate for steady-state planning but not for capacity sizing.

**Rate limiting on catch-up delivery:** To prevent the catch-up burst from creating a database write spike, the in-app delivery service applies a per-user delivery rate limit of 50 notifications/second on login flush. At 600K users logging in over 2 hours, this is not a binding constraint at the user level but prevents pathological cases (a user with 10K queued notifications from a 30-day absence).

### 1.5 Queue Storage — ID-Based with Visibility Timeout

**Decision: ID-based.** Queue entries store the notification ID; workers fetch the full payload from PostgreSQL on dequeue. The alternative — full payload storage in Redis — eliminates the hot-path database dependency at the cost of 10–20× higher queue memory. At this scale, the notification database is a managed PostgreSQL instance with 99.99% SLA. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Crash window behavior | Visibility timeout recovers message | Visibility timeout recovers message |
| Hot-path database dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Transient DB failure | Delays delivery; message not lost | No impact |

**Visibility timeout implementation:**

Redis Lists have no native visibility timeout. Two-list pattern:

```
# Dequeue: atomically move to processing list
RPOPLPUSH source_queue processing_list

# Worker records: message_id → dequeue_timestamp in sorted set
ZADD processing_timestamps <unix_timestamp> <message_id>
```

A heartbeat process per worker (10-second interval) updates the timestamp. A recovery process (runs every 30 seconds) moves messages with timestamps older than 60 seconds back to the source queue.

**The slow-worker race condition — specified, not deferred:**

If a worker is processing a message that takes 65 seconds, the recovery process will return that message to the queue while the worker is still processing it. Without additional protection, this produces duplicate delivery.

The deduplication key (SET NX, described in Section 1.7) is set **at the point of external delivery** — immediately before calling FCM, APNs, SendGrid, or Twilio — not at dequeue. This is the critical design choice.

The sequence is:

```
1. Worker dequeues message_id
2. Worker fetches payload from PostgreSQL
3. Worker checks preference filters
4. Worker attempts: SET NX dedup:<message_id> <worker_id> EX 300
5. If SET NX returns 0 (key exists): another worker already delivered or is delivering.
   Worker discards the message and ACKs the queue entry.
6. If SET NX returns 1: this worker owns delivery.
7. Worker calls external provider (FCM/APNs/SendGrid/Twilio)
8. On success: worker removes message from processing list, marks delivered in PostgreSQL
9. On failure: worker releases the dedup key (DEL dedup:<message_id>) and allows
   visibility timeout to return the message to queue for retry
```

**What happens when the slow worker and the recovery worker both proceed:**

- Original worker sets dedup key at step 4, proceeds to step 7
- Recovery process returns message to queue at 65 seconds
- Second worker dequeues, reaches step 4, finds dedup key exists (step 5), discards
- Original worker completes delivery, removes from processing list
- No duplicate delivery

**What happens if the original worker crashes after setting the dedup key but before delivery:**

- Dedup key exists; second worker finds it at step 4 and discards
- Message is never delivered; it sits in the processing list
- Recovery process returns it to queue after 60 seconds
- Third worker dequeues, reaches step 4, finds dedup key **still active** (5-minute TTL)
- If the crash happened within the 5-minute TTL window: message is not delivered until dedup key expires

**This is a known gap.** A crash between dedup key set and external delivery call produces at most one missed delivery per 5-minute TTL window per message. The alternative — not setting the dedup key until after delivery — eliminates this gap but allows duplicates during the slow-worker race. For a social notification system, a missed delivery is preferable to a duplicate. The tradeoff is named explicitly.

**Mitigation:** On step 9 (delivery failure), the worker DELetes the dedup key before releasing the message. This limits the gap to the worker-crash scenario only, not the recoverable-failure scenario.

### 1.6 TTL Enforcement and the LREM Scaling Problem

**The problem with LREM:**

The previous version used `LREM queue:<priority> 1 <id>` to remove expired messages from Redis Lists. `LREM` is O(N) where N is the list length. At the provider-outage worst case of 3.9M FCM messages in the queue, each LREM call scans up to 3.9M entries. Messages enqueued during a burst share similar TTLs, so many expire simultaneously — the pruning process would issue thousands of O(N) operations against a multi-million-entry list. This is a Redis latency spike that blocks all other operations on that instance.

**Solution: Replace Redis Lists with Sorted Sets for queue storage.**

Use notification enqueue timestamp as the score. Workers consume from the low end (ZPOPMIN); the pruning process removes from the high end of the expired range (ZREMRANGEBYSCORE). Both operations are O(log N + K) where K is the number of elements removed — not O(N) per element.

```
# Enqueue (score = enqueue_unix_timestamp):
ZADD queue:<priority> <enqueue_timestamp> <message_id>

# Dequeue (worker atomically pops lowest-score entry):
ZPOPMIN queue:<priority> 1

# Pruning (remove all entries with TTL-expired enqueue timestamps):
ZREMRANGEBYSCORE queue:<priority> 0 <now - ttl_seconds>
```

**Tradeoff acknowledged:** Sorted Sets use more memory per entry than Lists (~64B vs. ~40B overhead per element). At 3.9M entries, this is ~250MB vs. ~160MB — an additional ~90MB. This is acceptable given that it eliminates the O(N) blocking problem.

**FIFO ordering note:** Sorted Sets ordered by enqueue timestamp preserve FIFO within the same second. If two messages are enqueued in the same second, ordering within that second is arbitrary. For notification delivery, this is acceptable — sub-second FIFO ordering has no user-visible impact.

**Separate expiry sorted set is no longer needed.** The queue itself is the sorted set; ZREMRANGEBYSCORE handles expiry directly. The companion expiry set from the previous version is eliminated.

**Pruning failure behavior:** If the pruning process is down, expired messages accumulate but are not processed. Workers check the enqueue timestamp on dequeue and discard expired messages without calling external providers — the pruning process prevents queue growth but is not the sole enforcement point. Queue depth alerts (Section 1.8) will fire before accumulation becomes a memory problem.

### 1.7 Queue Accumulation and Memory Sizing

Queue accumulation occurs when input rate exceeds worker capacity. At planning volume (1,575/sec peak input, ~26,000/sec worker capacity), queues do not accumulate under normal operation.

**Realistic accumulation scenario — provider outage:**

FCM or APNs begins rate-limiting or goes down. Messages accumulate in the outbound queue at the rate they're generated, not the rate they're processed.

- FCM input at peak: ~383/sec (iOS-heavy sizing scenario)
- Complete FCM outage over 2 hours: ~383 × 7,200 = ~2.76M messages
- At 200B per Sorted Set entry: ~552MB

- APNs input at peak: ~711/sec (iOS-heavy sizing scenario)
- Complete APNs outage over 2 hours: ~711 × 7,200 = ~5.12M messages
- At 200B per entry: ~1.02GB

**Redis memory sizing (Sorted Set–based queues):**

| Component | Calculation | Estimate |
|-----------|-------------|----------|
| Queue entries (normal operation) | 500K × 200B | ~100MB |
| Queue entries (APNs outage worst case) | 5.1M × 200B | ~1.02GB |
| Processing list (in-flight) | 50K × 200B | ~10MB |
| Deduplication keys (5-min TTL) | 156K × 50B | ~8MB |
| Preference cache | 3M users × 2KB (see note) | ~6GB |
| Aggregation state | 500K windows × 200B | ~100MB |
| Pub/Sub overhead | — | ~500MB |
| **Total (normal operation)** | | **~6.7GB** |
| **Total (provider outage worst case)** | | **~7.7GB** |

**Preference cache memory — honest range:**

The previous version estimated 500B/user. A social app with per-type notification toggles (likes, comments, follows, mentions, DMs), per-