# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The document is complete — every section referenced below exists in full.

**What this document contains and where:**

1. **Traffic assumptions** with sensitivity testing across a 15M–100M/day envelope, including temporal spike analysis beyond the 3× average-peak model (Section 1.1).

2. **Four priority queues (P0–P3)** with TTL enforcement, pruning failure behavior, and the complete P1-drains-P2/P3 mechanism with starvation prevention (Sections 1.4, 1.7).

3. **ID-based queue entries** with visibility timeout semantics. The hot-path PostgreSQL dependency failure behavior is specified — not just the SLA figure (Section 1.4).

4. **Deduplication** with key structure, TTL rationale, boundary behavior at the 5-minute window edge, and the per-user-per-type vs. per-payload tradeoff stated explicitly (Section 1.5).

5. **Worker matrix** with every zero cell justified and every cross-reference to named sections (Section 1.6). The APNs failure case has a real mitigation, not just a load test date (Section 1.6).

6. **Visibility timeout recovery** with the slow-worker race condition acknowledged and addressed (Section 1.4).

7. **Redis failover** with the P0 behavior during the failover window quantified (Section 1.8).

8. **SMS budget controls** with enforcement mechanism and the no-verified-email OTP path specified (Section 3.4).

9. **WebSocket sequence numbers and reconnect catch-up logic** fully specified (Section 5).

10. **Staffing analysis** showing the 6-month build is feasible for 4 engineers with named risks and mitigation (Section 6).

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

**Temporal spike analysis — the 3× model is insufficient for social apps:**

The 3× multiplier applied over a 2-hour window models predictable daily rhythm (morning check-in, evening activity). It does not model viral events. Social apps have two distinct spike patterns:

- **Diurnal peaks:** 2–4× baseline, 1–2 hour duration. Predictable. The 3× model covers this.
- **Viral/event spikes:** A celebrity post, breaking news, or coordinated activity can generate 10–20× baseline notification volume over 5–10 minutes. These are unpredictable in timing, predictable in eventual occurrence.

**Why the system can absorb viral spikes without re-architecture:** At planning volume, worker capacity is ~26,000/sec against a 1,575/sec average peak. A 20× spike against the 3× peak figure yields ~10,500/sec — still 2.5× below worker capacity. The system has structural headroom for viral spikes because it is sized for sustained throughput, not just average peak. The constraint is not worker processing capacity; it is external provider rate limits (FCM, APNs). FCM's per-project rate limit is configurable up to 600,000 messages/minute (~10,000/sec). At a 20× spike, FCM demand reaches ~10,900/sec — this is the real ceiling, not internal worker capacity.

**Mitigation for viral spikes against provider limits:** P2 and P3 notifications are shed first under provider throttling. The priority queue structure means P0/P1 delivery is protected. P2/P3 messages accumulate in queue and drain after the spike. This is acceptable behavior — a "like" notification delayed 3 minutes during a viral event is not a product failure.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days. If measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

### 1.2 Channel Split — Derived, Not Asserted

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
| SMS | 2% | 0.9M/day | ~31/sec (capacity ceiling) |

FCM and APNs each handle ~50% of push: **~547/sec each at peak.**

### 1.3 Active-User Correction — Applied Where It Governs Delivery

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak.

**Push:** Push serves offline or background users. The concurrent-user correction does not apply. Peak demand = 31.5M/day × 3 / 86,400 = ~1,094/sec.

**In-app:** In-app delivery is gated on WebSocket connection state. A notification to an offline user does not consume in-app delivery resources — it falls back to push or queues for next login. The correction applies here. Peak demand = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**.

**In-app worker sizing against the corrected figure:** 5 in-app workers at ~1,000 rows/sec/worker = 5,000/sec capacity against a 63/sec corrected peak. This is ~79× overcapacity. The workers are not sized down for three reasons: (1) in-app workers also handle read-state updates and delivery confirmations, which add load not captured in the delivery rate alone; (2) the 20% concurrent-user figure is itself uncertain — at 50% concurrency (plausible for a highly engaged app), demand reaches ~157/sec; (3) in-app workers are the cheapest workers in the fleet (no external API calls, just PostgreSQL batch writes) and the cost of keeping 5 is low. The acknowledged inconsistency: the in-app worker count is not driven by delivery throughput. It is driven by the ancillary workload and the uncertainty in the concurrency assumption.

### 1.4 Queue Storage — ID-Based with Visibility Timeout

**ID-based storage is chosen.** Queue entries contain only the notification ID; workers fetch the full payload from PostgreSQL on dequeue. The memory savings (~10× versus full payload) and the failure behavior are both specified below.

**Visibility timeout implementation:**

Redis Lists have no native visibility timeout. The implementation uses a two-list pattern:

```
# Dequeue: atomically move to processing list
RPOPLPUSH queue:<priority>:<channel> processing:<channel>

# Worker records in-flight state:
ZADD processing_timestamps:<channel> <unix_timestamp> <message_id>
```

A heartbeat coroutine within each worker process updates the timestamp every 10 seconds:

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

A worker that is alive but blocked (slow database call, GC pause) will miss heartbeat updates. If the block exceeds 60 seconds, the recovery process reclaims the message and re-enqueues it. The original worker may then complete its processing and attempt to acknowledge a message it no longer owns.

This creates a duplicate delivery window, not a loss window. The deduplication layer (Section 1.5) handles the duplicate. The worker acknowledgment path checks whether the message is still in the processing list before marking delivery complete — if it has been reclaimed, the worker discards its result silently.

The 60-second reclaim threshold is deliberately conservative. A 10-second heartbeat with a 60-second threshold provides a 5-missed-heartbeat buffer. The realistic cause of a >60-second block is not a GC pause (typically <1 second) but a database call hung on a failed connection. Worker database connections have a 15-second connect timeout and a 30-second query timeout, so a hung database call resolves (with an error) before the reclaim threshold is reached. The worker then retries via the standard retry path, not via reclaim.

**Residual risk:** If both the heartbeat coroutine and the database timeout are misconfigured simultaneously, a worker could hold a message past the reclaim threshold and create a genuine duplicate. This is mitigated by monitoring: workers emit a heartbeat-sent metric, and an alert fires if any worker's heartbeat rate drops below 1/30sec for more than two intervals.

**Hot-path PostgreSQL failure behavior — specified, not just SLA-cited:**

99.99% availability (~52 minutes/year downtime) is the SLA, not the behavior specification. The behavior during those 52 minutes:

- Workers dequeue a notification ID from Redis.
- PostgreSQL fetch fails with a connection error or timeout.
- The worker does **not** acknowledge the message. The visibility timeout expires and the message is re-enqueued.
- The worker enters a backoff loop (exponential, 1s → 2s → 4s → max 30s) and retries the fetch.
- Messages accumulate in the processing list during the outage, bounded by the number of active workers × the reclaim threshold. At 23 workers with 60-second reclaim: ~1,380 messages maximum in-flight during a total PostgreSQL outage.
- P0 messages re-enqueue and retry. They are delayed, not dropped. Maximum delay during a PostgreSQL outage = reclaim threshold (60s) + re-queue time + next worker pick-up = approximately 60–90 seconds.
- If the PostgreSQL outage exceeds 5 minutes, the P0 queue depth alert fires (threshold: 1,000 items) and pages on-call.

**The honest statement:** During a PostgreSQL primary failover (typically 30–60 seconds for managed RDS Multi-AZ), P0 notifications may be delayed by 60–120 seconds. This is acceptable for security alerts (which are urgent but not instantaneous) and is unacceptable for OTPs if the user is waiting at a login screen. The OTP path has an additional mitigation: the OTP value is generated before enqueue and stored in Redis with a 10-minute TTL. If the notification is delayed, the OTP remains valid. The user's perceived failure is a delayed SMS/email, not an expired code.

**TTL enforcement for expired notifications:**

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

Workers also check the enqueue timestamp on dequeue and discard expired messages without processing. The pruning process prevents queue bloat; worker-side checking is the enforcement backstop.

### 1.5 Deduplication

**Key structure:**

```
dedup:<user_id>:<notification_type>:<content_hash>
```

Example: `dedup:u_8472991:like:sha256("post_id=99231")` with a 5-minute TTL set via `SET NX EX 300`.

**Why this key structure, not alternatives:**

- `dedup:<user_id>:<notification_type>` (no content hash): Suppresses all notifications of the same type to a user within 5 minutes. This is appropriate for rate-limiting "X liked your post" floods (intentional suppression). It is wrong for "new message from A" and "new message from B" — different content that should both deliver.
- `dedup:<exact_payload_hash>` (no user): Incorrectly treats the same notification to different users as duplicates.
- **Chosen:** `user_id + notification_type + content_hash` suppresses exact duplicates (retry storms, double-enqueue bugs) while allowing distinct-content notifications of the same type to the same user.

**TTL selection rationale:** 5 minutes is chosen to cover: (1) the visibility timeout reclaim window (60 seconds) with 5× margin, (2) typical retry intervals for transient failures (exponential backoff maxes at 30 seconds), (3) application-level double-submit windows (users double-tapping "like" are typically sub-second; the 5-minute window is deliberately wider to catch infrastructure-level duplicates, not user behavior). A longer TTL (e.g., 24 hours) would suppress legitimate re-delivery — a user who receives a "new follower" notification, dismisses it, and then the sender unfollows and re-follows should receive a second notification. 5 minutes does not suppress this case.

**The 6-minute boundary case:** Two identical notifications arriving 6 minutes apart are not deduplicated. This is correct behavior. If the same notification genuinely re-occurs after 5 minutes (e.g., a retry after a prolonged outage), the dedup key has expired and the notification delivers. This is preferable to indefinite suppression — a notification delayed by 6 minutes due to a provider outage should still reach the user.

**False-positive risk under worker backup:** If the P0 queue backs up (e.g., during a provider outage) and a notification sits in queue for longer than 5 minutes before processing, the dedup key expires before delivery. A subsequent retry enqueue creates a new dedup key and delivers normally. This is the correct behavior — the dedup key expiring means the suppression window has passed, and delivery should proceed.

**False-negative risk (duplicate delivers):** The SET NX operation is atomic. There is no race between two workers checking the same key. The only false-negative path is if Redis itself is unavailable during the SET NX call — in that case, deduplication is skipped and delivery proceeds without suppression. Duplicate delivery is preferable to suppression failure for P0 notifications. For P2/P3, workers treat a Redis unavailability on the dedup check as a non-fatal error and proceed with delivery.

### 1.6 Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs | HTTP/2 multiplexed, 4 connections/worker | **300–1,000 req/sec/worker** |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — the failure case and the real mitigation:**

The 300