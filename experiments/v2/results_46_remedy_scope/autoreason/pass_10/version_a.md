# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four decisions that drive everything else:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via companion expiry sorted sets and worker-side backstop checking. The P1-drains-P2/P3 mechanism is fully specified with starvation prevention.

2. **ID-based queue entries with visibility timeout semantics.** Full payload storage is the alternative; the tradeoff is stated honestly. The failure behavior during PostgreSQL unavailability is specified in terms of actual delays, not just SLA percentages.

3. **Per-channel, per-priority worker pools** reconciled in a single source-of-truth matrix. Every zero cell is justified. The APNs failure case has a real mitigation, not just a load test date.

4. **Redis primary/replica with bounded failover.** P0 behavior during the failover window is quantified.

Every tradeoff is named explicitly. Where a mitigation is partial, that is stated.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** The 30% planning figure is reasonable for mature social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct planning range for an unspecified social app is 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Average-peak sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

**Temporal spike analysis — the 3× model is insufficient for social apps:**

The 3× multiplier models predictable daily rhythm. It does not model viral events. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** A celebrity post or breaking news can generate 10–20× baseline notification volume over 5–10 minutes. Unpredictable in timing, predictable in eventual occurrence.

**Why the system absorbs viral spikes without re-architecture:** At planning volume, worker capacity is ~26,000/sec against a 1,575/sec average peak. A 20× spike against the 3× peak figure yields ~10,500/sec — still 2.5× below worker processing capacity. The real ceiling is external provider rate limits. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike, FCM demand approaches this ceiling.

**Mitigation:** P2 and P3 notifications are shed first under provider throttling. The priority queue structure protects P0/P1 delivery. P2/P3 messages accumulate and drain after the spike. A "like" notification delayed 3 minutes during a viral event is not a product failure.

### 1.2 Channel Split — Derived, Not Asserted

Reference points: consumer social apps (Instagram, TikTok) are push-heavy at 80–90%. Productivity apps (Slack, LinkedIn) show 15–25% email share. New apps without retention data skew toward push because email lists are smaller.

| Channel | Conservative | **Plan** | Push-heavy |
|---------|-------------|----------|-----------|
| Push (FCM + APNs) | 60% | **70%** | 85% |
| In-app | 25% | **20%** | 10% |
| Email | 12% | **8%** | 4% |
| SMS | 3% | **2%** | 1% |

**Daily volumes at plan:**

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec (capacity ceiling, not operating target) |

FCM and APNs each handle ~50% of push volume: **~547/sec each at peak.**

The worker matrix is robust to push share ranging from 60–85% without re-provisioning. If production data at month 1 shows push share above 80%, in-app workers have excess capacity that can be redeployed.

### 1.3 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This correction applies differently by channel.

**Push:** Push serves offline and background users. The concurrent-user correction does not apply — the 70% channel allocation already represents full DAU-based volume. Applying a second population filter understates demand.
- Push peak demand = 31.5M/day × 3 / 86,400 = **~1,094/sec**

**In-app:** In-app delivery is gated on WebSocket connection state. A notification to an offline user does not consume in-app delivery resources; it falls back to push or queues for next login.
- In-app peak demand = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand.

**In-app worker sizing against the corrected figure:** 5 in-app workers at ~1,000 rows/sec/worker = 5,000/sec capacity against a 63/sec corrected peak. This is ~79× overcapacity, which is acknowledged. The workers are not sized down for three reasons: (1) in-app workers also handle read-state updates and delivery confirmations, which add load not captured in the delivery rate alone; (2) at 50% concurrency (plausible for a highly engaged app), demand reaches ~157/sec; (3) in-app workers make no external API calls and are the cheapest workers in the fleet. The in-app worker count is driven by ancillary workload and concurrency uncertainty, not delivery throughput.

### 1.4 Queue Storage — ID-Based with Visibility Timeout

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue.

**Honest comparison:**

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Crash window behavior | Visibility timeout recovers message | Visibility timeout recovers message |
| Hot-path database dependency | Yes — payload fetch on dequeue | No |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Primary failure mode | Transient DB unavailability delays delivery; message not lost | Eliminates DB dependency on hot path |

The notification database is a managed PostgreSQL instance with 99.99% availability. A transient fetch failure delays delivery; it does not lose the message. The memory savings are real and the failure mode is recoverable.

**Visibility timeout implementation:**

Redis Lists have no native visibility timeout. The implementation uses a two-list pattern:

```
# Dequeue: atomically move to processing list
RPOPLPUSH queue:<priority>:<channel> processing:<channel>

# Worker records in-flight state:
ZADD processing_timestamps:<channel> <unix_timestamp> <message_id>
```

A heartbeat coroutine within each worker updates the timestamp every 10 seconds:

```
ZADD processing_timestamps:<channel> <current_unix_timestamp> <message_id>
```

A recovery process (independent of workers, runs every 30 seconds) reclaims stale entries:

```
stale = ZRANGEBYSCORE processing_timestamps:<channel> 0 <now - 60>
for each id in stale:
    LREM processing:<channel> 1 <id>
    RPUSH queue:<priority>:<channel> <id>
    ZREM processing_timestamps:<channel> <id>
```

**The slow-worker race condition — acknowledged and addressed:**

A worker that is alive but blocked (slow database call, GC pause) will miss heartbeat updates. If the block exceeds 60 seconds, the recovery process reclaims the message and re-enqueues it. The original worker may then complete processing and attempt to acknowledge a message it no longer owns.

This creates a duplicate delivery window, not a loss window. The deduplication layer (Section 1.5) handles the duplicate. The worker acknowledgment path checks whether the message is still in the processing list before marking delivery complete — if reclaimed, the worker discards its result silently.

The 60-second reclaim threshold is deliberately conservative. A 10-second heartbeat with a 60-second threshold provides a 5-missed-heartbeat buffer. The realistic cause of a >60-second block is not a GC pause (typically <1 second) but a database connection hung on failure. Worker database connections have a 15-second connect timeout and a 30-second query timeout, so a hung call resolves with an error before the reclaim threshold is reached. The worker retries via the standard retry path.

**Residual risk:** If both the heartbeat coroutine and the database timeout are misconfigured simultaneously, a worker could hold a message past the reclaim threshold and create a genuine duplicate. Mitigation: workers emit a heartbeat-sent metric, and an alert fires if any worker's heartbeat rate drops below 1/30sec for more than two consecutive intervals.

**Hot-path PostgreSQL failure — behavior specified, not just SLA-cited:**

99.99% availability (~52 minutes/year) is the SLA, not the behavior specification. During those 52 minutes:

- Workers dequeue a notification ID from Redis. PostgreSQL fetch fails.
- The worker does **not** acknowledge the message. The visibility timeout expires and the message re-enqueues.
- The worker enters exponential backoff (1s → 2s → 4s → max 30s) and retries.
- Messages accumulate in the processing list during the outage, bounded by active workers × reclaim threshold. At 23 workers with 60-second reclaim: ~1,380 messages maximum in-flight during a total PostgreSQL outage.
- P0 messages re-enqueue and retry. Maximum delay during a PostgreSQL outage = reclaim threshold (60s) + re-queue time + next worker pickup = approximately 60–90 seconds.
- If the PostgreSQL outage exceeds 5 minutes, the P0 queue depth alert fires and pages on-call.

**The honest statement:** During a PostgreSQL primary failover (typically 30–60 seconds for managed RDS Multi-AZ), P0 notifications may be delayed by 60–120 seconds. This is acceptable for security alerts but not for OTPs with users waiting at a login screen. The OTP mitigation: the OTP value is generated before enqueue and stored in Redis with a 10-minute TTL. If the notification is delayed, the OTP remains valid. The user's perceived failure is a delayed message, not an expired code.

**TTL enforcement for expired notifications:**

Redis Lists have no per-element TTL. Expiry is enforced via a companion sorted set:

```
# On enqueue:
RPUSH queue:<priority>:<channel> <message_id>
ZADD expiry:<priority> <expire_unix_timestamp> <message_id>

# Pruning process (runs every 60 seconds):
expired = ZRANGEBYSCORE expiry:<priority> 0 <now>
for each id in expired:
    LREM queue:<priority>:<channel> 1 <id>
    ZREM expiry:<priority> <id>
```

**Pruning failure behavior:** If the pruning process is down for an extended period, expired messages accumulate. Workers check the enqueue timestamp on dequeue and discard expired messages without processing — the pruning process prevents queue bloat, but worker-side checking is the enforcement backstop. These are independent mechanisms; neither depends on the other being healthy.

### 1.5 Deduplication

**Implementation:** Atomic SET NX with TTL.

```
SET dedup:<user_id>:<notification_type>:<content_hash> 1 NX EX 300
```

The SET NX operation is atomic. There is no race between two workers checking the same key.

**Key structure rationale:**

- `dedup:<user_id>:<notification_type>` (no content hash): Suppresses all notifications of the same type within 5 minutes. Correct for rate-limiting "X liked your post" floods. Wrong for "new message from A" and "new message from B" — different content that should both deliver.
- `dedup:<exact_payload_hash>` (no user): Incorrectly treats the same notification to different users as duplicates.
- **Chosen:** `user_id + notification_type + content_hash` suppresses exact duplicates (retry storms, double-enqueue bugs) while allowing distinct-content notifications of the same type to the same user.

**TTL selection rationale:** 5 minutes covers: (1) the visibility timeout reclaim window (60 seconds) with 5× margin; (2) typical retry intervals for transient failures (exponential backoff maxes at 30 seconds); (3) infrastructure-level double-submit windows. A longer TTL (e.g., 24 hours) would suppress legitimate re-delivery — a user who receives a "new follower" notification, dismisses it, and the sender then unfollows and re-follows should receive a second notification after a reasonable interval. 5 minutes does not suppress this.

**The 6-minute boundary case:** Two identical notifications arriving 6 minutes apart are not deduplicated. This is correct behavior. A notification delayed 6 minutes by a provider outage should still reach the user. Indefinite suppression is worse than occasional duplicates.

**False-positive risk under worker backup:** If a P0 notification sits in queue longer than 5 minutes before processing (e.g., during a provider outage), the dedup key expires before delivery. A subsequent retry enqueue creates a new dedup key and delivers normally. This is the correct behavior — the suppression window has passed.

**False-negative risk:** The only false-negative path is Redis unavailability during the SET NX call. In that case, deduplication is skipped and delivery proceeds without suppression. Duplicate delivery is preferable to suppression failure for P0 notifications. For P2/P3, Redis unavailability on the dedup check is treated as a non-fatal error and delivery proceeds.

**Memory sizing for dedup keys:**
At 45M/day and 5-minute TTL, simultaneously active dedup keys = 45M × (5/1,440) ≈ 156K keys × 50B each ≈ **~8MB**. Not a meaningful memory constraint.

### 1.6 Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs | HTTP/2, 4 connections/worker | **300–1,000 req/sec/worker** (range; see below) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — the floor defense and the failure case:**

The 300 req/sec/worker floor is derived from Apple's HTTP/2 connection supporting up to 1,000 concurrent streams; at ~3ms per request on a low-latency connection, this yields ~330 req/sec. This is a theoretical floor assuming no Apple-side throttling.

**The failure case that must be named:** New bundle IDs with no established Apple relationship have been observed to be throttled to 50–150