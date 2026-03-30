# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day (planning figure; range-tested from 15M to 100M) across push, email, in-app, and SMS channels. The core architectural decisions:

1. **Traffic assumptions are explicit and sensitivity-tested.** The 45M/day planning figure compounds two uncertain inputs (DAU/MAU ratio, notifications per user). Both are range-tested. Channel split percentages are derived from reference points, not asserted.

2. **Four isolated priority queues (P0–P3)** with TTL semantics enforced directly via Sorted Set queue structure — no companion expiry set required, no O(N) scan costs. The LREM scaling problem is solved, not deferred.

3. **ID-based queue entries with visibility timeout semantics.** Full payload storage is the alternative; tradeoffs are stated honestly. The failure mode under ID-based storage is recoverable via visibility timeout — there is no silent loss.

4. **Deduplication uses atomic SET NX applied at the point of external delivery**, not at dequeue. The slow-worker race condition is solved. The crash-between-key-set-and-delivery gap is named, not hidden, with the correct tradeoff stated.

5. **FCM/APNs split treated as uncertain input** with sensitivity analysis. APNs workers are sized for the iOS-heavy scenario (711/sec peak), not the 50/50 scenario. Sizing for the optimistic split and being wrong creates an incident.

6. **Worker pools are per-channel and per-priority**, reconciled in a single source-of-truth matrix. Every zero cell is justified. The P1-drains-lower-priority mechanism is fully specified, including starvation prevention.

7. **APNs capacity planning accounts for the throttled-throughput failure case.** The 100 req/sec/worker scenario is named with mitigations specified. The month-2 APNs load test is a non-optional gate.

8. **SMS ceiling enforced at infrastructure level** with fallback behavior specified. The no-verified-email case is handled explicitly.

9. **Email OTP fallback routes to a dedicated P0 sub-queue**, not the standard P1 email queue. The priority hole is closed.

10. **WebSocket sequence numbers and reconnect catch-up logic** are specified. The catch-up burst (667/sec) is the in-app design point, not the steady-state estimate (63/sec).

11. **Redis is primary/replica with a bounded failover window.** P0 behavior during failover is specified.

Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% as a planning figure is reasonable for mature social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct planning range for an unspecified social app is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

### 1.2 Channel Split — Derived, Not Asserted

The channel split depends on platform mix, session length, and product design. Reference points:

- **Consumer social apps (Instagram, TikTok):** Push-heavy, 80–90% via push, minimal SMS
- **Productivity/communication apps (Slack, LinkedIn):** Higher email share, 15–25%
- **New apps without retention data:** Push share tends to be higher because email lists are smaller and in-app sessions are shorter

**Planning split and sensitivity:**

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
| SMS | 2% | 0.9M/day (ceiling; enforcement in §1.9) |

If production data at month 1 shows push share above 80%, in-app worker capacity has excess headroom that can be redeployed. The worker matrix is robust to this range without re-provisioning.

### 1.3 FCM/APNs Split — Treated as Uncertain Input

Platform mix varies significantly by geography, app category, and user demographics. Asserting 50/50 without justification is the same error as asserting any other number. This is an equally uncertain input to DAU/MAU ratio and must be sensitivity-tested because it directly governs APNs worker sizing.

**Reference points:**
- US-centric consumer social apps: iOS share often 55–65%
- Global or emerging-market apps: Android share often 70–85%
- Unknown app with no stated market: 40/60 to 60/40 iOS/Android is the defensible planning range

**Sensitivity table (push peak = ~1,094/sec):**

| Scenario | FCM share | FCM peak | APNs share | APNs peak |
|----------|-----------|----------|------------|-----------|
| Android-heavy | 70% | ~766/sec | 30% | ~328/sec |
| **Plan (50/50)** | **50%** | **~547/sec** | **50%** | **~547/sec** |
| iOS-heavy | 35% | ~383/sec | 65% | ~711/sec |

**Planning decision:** Size APNs workers for the iOS-heavy scenario (711/sec peak demand). This is the correct conservative choice because APNs has more constrained throughput per worker and more severe throttling risk for new bundle IDs. If production data shows Android-heavy split, APNs workers have excess capacity — an acceptable outcome. Sizing for the optimistic split and being wrong creates an incident.

**All APNs worker sizing below uses 711/sec peak demand, not 547/sec.**

### 1.4 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This correction applies differently by channel.

**Push:** Serves offline or background users. The correction does not apply — push peak demand is the full DAU-based volume.

- Push peak = 31.5M/day × 3 / 86,400 = **~1,094/sec total**
- APNs peak (iOS-heavy sizing): **~711/sec**
- FCM peak (iOS-heavy sizing): **~383/sec**

**In-app (steady-state):** Gated on WebSocket connection state. Offline users queue for next login.

- In-app steady-state = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

**In-app catch-up load — the design point, not steady-state:**

The 63/sec figure understates peak in-app delivery load. When users log back in after a period offline, queued notifications are delivered in a burst.

Assume a post-peak login surge: 20% of DAU (600K users) log in within 2 hours following peak. Each has an average of 8 queued in-app notifications (the offline backlog; lower than 15/day because active users receive in-app delivery in real time).

- Catch-up volume = 600K × 8 = 4.8M notifications over 2 hours
- Catch-up rate = 4.8M / 7,200 seconds = **~667/sec**

This is 10× the steady-state estimate. **The in-app worker pool must handle 667/sec burst, not 63/sec.** Worker sizing uses 667/sec as the in-app design point.

**Rate limiting on catch-up delivery:** To prevent the catch-up burst from creating a database write spike, the in-app delivery service applies a per-user delivery rate limit of 50 notifications/second on login flush. At 600K users logging in over 2 hours, this is not a binding constraint at the aggregate level but prevents pathological cases (a user with 10K queued notifications from a 30-day absence).

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Sorted Set Structure

**Decision: ID-based entries stored in Redis Sorted Sets.**

This combines the memory efficiency of ID-based storage with the O(log N) pruning characteristics of Sorted Sets. It eliminates both the O(N) LREM scaling problem and the need for a companion expiry sorted set.

**ID-based vs. full payload tradeoff:**

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Crash window behavior | Visibility timeout recovers message | Visibility timeout recovers message |
| Hot-path database dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Transient DB failure | Delays delivery; message not lost | No impact on hot path |

The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

**Why Sorted Sets, not Redis Lists:**

Redis Lists require `LREM` for targeted element removal. `LREM` is O(N) where N is the list length. At the provider-outage worst case of ~5M APNs messages in the queue, each LREM call scans up to 5M entries. Messages enqueued during a burst share similar TTLs, so many expire simultaneously — the pruning process would issue thousands of O(N) operations against a multi-million-entry list. This is a Redis latency spike that blocks all other operations on that instance.

**Solution:** Use notification enqueue timestamp as the Sorted Set score. Workers consume from the low end (ZPOPMIN); the pruning process removes expired entries with ZREMRANGEBYSCORE. Both operations are O(log N + K) where K is the number of elements removed.

```
# Enqueue (score = enqueue_unix_timestamp):
ZADD queue:<priority> <enqueue_timestamp> <message_id>

# Dequeue (worker atomically pops lowest-score entry):
ZPOPMIN queue:<priority> 1

# Pruning (remove all entries with TTL-expired enqueue timestamps):
ZREMRANGEBYSCORE queue:<priority> 0 <now - ttl_seconds>
```

**Tradeoff acknowledged:** Sorted Sets use more memory per entry than Lists (~64B vs. ~40B overhead). At 5M entries, this is ~320MB vs. ~200MB — an additional ~120MB. This is acceptable given that it eliminates the O(N) blocking problem.

**FIFO ordering note:** Sorted Sets ordered by enqueue timestamp preserve FIFO within the same second. Sub-second ordering is arbitrary. For notification delivery, this is acceptable — sub-second FIFO ordering has no user-visible impact.

**Pruning failure behavior:** If the pruning process is down, expired messages accumulate but are not processed. Workers check the enqueue timestamp on dequeue and discard expired messages without calling external providers — pruning prevents queue growth but is not the sole enforcement point. Queue depth alerts (§2.3) will fire before accumulation becomes a memory problem.

### 2.2 Visibility Timeout Implementation

Redis has no native visibility timeout. Two-structure pattern:

```
# Dequeue: atomically pop from queue Sorted Set
entry = ZPOPMIN queue:<priority> 1

# Worker records dequeue in processing sorted set:
ZADD processing_timestamps <unix_timestamp> <message_id>
```

A heartbeat process per worker (10-second interval) updates the timestamp for messages currently being processed. A recovery process (runs every 30 seconds) finds messages with timestamps older than 60 seconds and returns them to the source queue:

```
# Recovery process:
stale = ZRANGEBYSCORE processing_timestamps 0 <now - 60>
for each message_id in stale:
    ZADD queue:<priority> <original_enqueue_timestamp> <message_id>
    ZREM processing_timestamps <message_id>
```

### 2.3 Deduplication — Race Condition Solved, Not Described

The slow-worker race condition: a worker processing a message for 65 seconds causes the recovery process to return that message to the queue while the worker is still processing it. Without additional protection, this produces duplicate delivery.

**Solution:** The deduplication key is set **at the point of external delivery** — immediately before calling FCM, APNs, SendGrid, or Twilio — not at dequeue.

```
1. Worker dequeues message_id via ZPOPMIN
2. Worker fetches payload from PostgreSQL
3. Worker checks preference filters
4. Worker attempts: SET dedup:<message_id> <worker_id> NX EX 300
5. If SET NX returns 0 (key exists): another worker already delivered or is delivering.
   Worker discards the message. Done.
6. If SET NX returns 1: this worker owns delivery.
7. Worker calls external provider (FCM/APNs/SendGrid/Twilio)
8. On success: remove from processing sorted set, mark delivered in PostgreSQL
9. On failure: DEL dedup:<message_id>, allow visibility timeout to return message to queue
```

**What happens when the slow worker and the recovery worker both proceed:**
- Original worker sets dedup key at step 4, proceeds to step 7
- Recovery process returns message to queue at 65 seconds
- Second worker dequeues, reaches step 4, finds dedup key, discards
- Original worker completes delivery
- No duplicate delivery

**The crash-between-key-and-delivery gap — named explicitly:**

If the original worker crashes after setting the dedup key (step 4) but before delivery (step 7):
- Dedup key exists; second worker discards at step 4
- Message sits in processing sorted set
- Recovery process returns it to queue after 60 seconds
- Third worker dequeues, reaches step 4, finds dedup key **still active** (5-minute TTL)
- Message is not delivered until the dedup key expires — up to 5 minutes of delay

**This is a known gap.** A crash between dedup key set and external delivery produces at most one missed delivery per 5-minute TTL window per message. The alternative — setting the dedup key only after delivery — eliminates this gap but allows duplicates during the slow-worker race. For a social notification system, a missed delivery is preferable to a duplicate. The tradeoff is explicit.

**Mitigation:** Step 9 (delivery failure) DELetes the dedup key before releasing the message. This limits the gap to the worker-crash scenario only, not the recoverable-failure scenario.

### 2.4 Queue Accumulation and Memory Sizing

Under normal operation (1,575/sec peak input, ~26,000/sec worker capacity), queues do not accumulate — workers drain 16× faster than messages arrive. Even at the 100M/day high bound (~3,500/sec peak), the system remains well within worker capacity under normal conditions.

**Accumulation occurs only under external provider failure:**

- FCM outage, iOS-heavy scenario: ~383/sec accumulate. Over 2 hours: ~2.76M messages × 200B = **~552MB**
- APNs outage, iOS-heavy scenario: ~711/sec accumulate. Over 2 hours: ~5.12M messages × 