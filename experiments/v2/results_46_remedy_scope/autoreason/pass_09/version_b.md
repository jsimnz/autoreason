# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. Four engineers have six months. That constraint is the first-order design input, not a footnote.

**The honest position on scope:** The full architecture described here — four priority queues, per-channel worker pools, visibility timeout recovery, TTL enforcement, deduplication, preference management, and failure handling — represents approximately 8–10 engineer-months of careful implementation and testing. With four engineers and six months, roughly half of that time is consumed by non-feature work: code review, deployment pipelines, monitoring setup, incident response, and coordination overhead. The design therefore distinguishes **load-bearing components** (must ship for the system to function) from **hardening components** (improve reliability but have defined degraded-mode fallbacks). Load-bearing components ship in months 1–4. Hardening components ship in months 4–6 or are deferred with explicit risk acceptance.

**Load-bearing:** Priority queues and worker pools, basic deduplication, channel dispatch, user preference storage, FCM/APNs/email delivery, failure retry with backoff.

**Hardening (with fallback):** Companion-set TTL enforcement (fallback: worker-side expiry check only), visibility timeout recovery process (fallback: manual re-enqueue tooling for incidents), starvation prevention logic (fallback: fixed round-robin with operator override), SMS channel (fallback: omit from v1 unless product requires it).

The executive summary no longer claims completeness as a virtue. It claims a system four engineers can actually build and operate.

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

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Traffic divergence response protocol** — replacing the previous "re-plan before month 3" non-answer:

Traffic is measured continuously from day 1. The response is tiered by severity and does not wait for a scheduled planning cycle:

| Condition | Detection | Immediate action | Owner |
|-----------|-----------|-----------------|-------|
| Measured rate 2–5× above plan (3,150–7,875/sec) | Day 1–30 dashboards | Scale worker replicas horizontally; no re-architecture needed within this range | On-call engineer, same day |
| Measured rate 5–10× above plan (7,875–15,750/sec) | Day 1–30 dashboards | Emergency horizontal scale + Redis cluster upgrade; page engineering lead | Engineering lead, within 24 hours |
| Measured rate >10× above plan (>15,750/sec) | Automated alert, threshold | Immediate incident; shed P2/P3, protect P0/P1; architecture review within 1 week | Full team |
| Measured rate <25% of plan (<394/sec) | 30-day review | Reduce worker count to cut cost; no reliability impact | Monthly review |

**What "re-plan" means concretely:** Horizontal scaling (adding worker replicas) is available within minutes via the container orchestration layer and requires no code changes. Redis cluster mode handles 10× volume without re-architecture. The only genuine re-architecture trigger is sustained >10× plan, which requires sharding the queue structure. That design is documented as a runbook but not built in v1.

**Temporal spike analysis — the 3× model is insufficient for social apps:**

The 3× multiplier models predictable daily rhythm. Social apps also have viral/event spikes: a celebrity post or breaking news can generate 10–20× baseline over 5–10 minutes.

**Why the system absorbs viral spikes — and the honest accounting:**

The worker pool is sized for 1,575/sec peak. Worker capacity at plan is ~26,000/sec aggregate. A 20× spike against 3× peak yields ~10,500/sec — within worker capacity, but this argument requires that the workers are actually running and available, not that the plan says they will be. Worker replicas are always-on, not auto-scaled-to-zero. The minimum replica count is set to cover the 3× peak with 2× headroom, so the capacity exists before the spike begins. Auto-scaling is configured as a ceiling, not a floor.

The real ceiling at spike volume is external provider rate limits, not internal workers. FCM's per-project rate limit is configurable up to ~10,000/sec. At a 20× spike, FCM demand approaches this ceiling. P2 and P3 notifications are shed first under provider throttling. The priority queue structure protects P0/P1. A "like" notification delayed 3 minutes during a viral event is not a product failure.

### 1.2 Channel Split

| Channel | Share | Daily volume | Peak demand |
|---------|-------|-------------|------------|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app | 20% | 9M/day | ~63/sec (active-user corrected) |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle ~50% of push volume: ~547/sec each at peak.

**SMS in v1:** SMS is included in the design but is the first channel cut if the team falls behind schedule. The product impact is low (2% of volume) and the operational complexity is disproportionate (Twilio synchronous API, carrier filtering, regulatory compliance). If SMS is cut from v1, affected notifications fall back to push for users with registered devices or are queued for email. This fallback is implemented regardless, because SMS delivery failure requires it anyway.

### 1.3 Active-User Correction

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak.

**Push:** Serves offline and background users. Active-user correction does not apply. Push peak = 31.5M/day × 3 / 86,400 = **~1,094/sec**.

**In-app:** Gated on WebSocket connection state. Offline users fall back to push or queue for next login. In-app peak = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**.

### 1.4 Queue Storage — ID-Based with Visibility Timeout

**Decision: ID-based.** Queue entries contain only the notification ID. Workers fetch the full payload from PostgreSQL on dequeue.

| | ID-based (chosen) | Full payload |
|--|---|---|
| Queue entry size | ~100–200B | ~500B–2KB |
| Memory at 500K queue depth | ~100MB | ~500MB–1GB |
| Hot-path database dependency | Yes — payload fetch blocks on DB availability | No |
| Primary failure mode | DB unavailability delays delivery; message not lost | Eliminates DB hot-path dependency |

The memory savings are real. The failure mode is recoverable but must be specified concretely, which follows in Section 1.4.2.

#### 1.4.1 Visibility Timeout Implementation

Redis Lists have no native visibility timeout. The implementation uses a two-list pattern:

```python
# Dequeue: atomically move to processing list
RPOPLPUSH queue:<priority>:<channel> processing:<channel>

# Worker records in-flight state
ZADD processing_timestamps:<channel> <unix_timestamp> <message_id>

# Heartbeat coroutine (every 10 seconds)
ZADD processing_timestamps:<channel> <current_unix_timestamp> <message_id>
```

A recovery process (independent of workers, runs every 30 seconds) reclaims stale entries:

```python
stale = ZRANGEBYSCORE processing_timestamps:<channel> 0 <now - 60>
for each id in stale:
    LREM processing:<channel> 1 <id>
    RPUSH queue:<priority>:<channel> <id>
    ZREM processing_timestamps:<channel> <id>
```

**The slow-worker race condition:** A worker alive but blocked past 60 seconds has its message reclaimed and re-enqueued. The original worker may complete and attempt to acknowledge a message it no longer owns. This creates a duplicate delivery window, not a loss window. The deduplication layer (Section 1.5) handles the duplicate. Workers check processing list membership before acknowledging; if reclaimed, the result is discarded silently.

Worker database connections have a 15-second connect timeout and 30-second query timeout, so a hung call resolves with an error before the 60-second reclaim threshold. The realistic cause of threshold breach is not GC pause but misconfiguration. Workers emit a heartbeat-sent metric; an alert fires if any worker's heartbeat rate drops below 1/30sec for two consecutive intervals.

#### 1.4.2 Recovery Process Concurrency — Acknowledged and Addressed

The recovery process sequence (ZRANGEBYSCORE → LREM → RPUSH → ZREM) is not atomic. If two recovery process instances run concurrently — during deployment, crash-restart, or multi-node operation — the same message can be reclaimed twice, producing a double-enqueue without a corresponding dedup key suppressing it.

**Mitigation:** The recovery process acquires a distributed lock before running:

```python
# Recovery process startup
lock_acquired = SET recovery_lock:<channel> <instance_id> NX EX 45

if not lock_acquired:
    exit  # Another instance is running; skip this cycle

# ... perform recovery ...

DEL recovery_lock:<channel>
```

Lock TTL is 45 seconds — longer than the 30-second recovery cycle, shorter than the 60-second reclaim threshold. If the lock-holding instance crashes mid-recovery, the lock expires before the next cycle. The instance ID in the lock value allows the holder to verify ownership before release.

**Residual risk:** If a recovery instance completes the LREM but crashes before RPUSH, the message is removed from the processing list without being re-enqueued. This is a loss window. Mitigation: a separate reconciliation job (runs every 5 minutes) compares the processing_timestamps sorted set against the processing list and re-enqueues any IDs present in the sorted set but absent from the processing list. This reconciliation job is a hardening component; before it ships, the loss window exists and is accepted for non-P0 channels.

**Staffing note:** The recovery process and its distributed lock add approximately 3 days of implementation and testing. This is included in the month 3–4 hardening sprint, not the initial delivery.

#### 1.4.3 TTL Enforcement

Redis Lists have no per-element TTL. Expiry is enforced via a companion sorted set:

```python
# On enqueue
RPUSH queue:<priority>:<channel> <message_id>
ZADD expiry:<priority> <expire_unix_timestamp> <message_id>

# Pruning process (every 60 seconds)
expired = ZRANGEBYSCORE expiry:<priority> 0 <now>
for each id in expired:
    LREM queue:<priority>:<channel> 1 <id>
    ZREM expiry:<priority> <id>
```

**Fallback:** If the pruning process is down, workers check the enqueue timestamp on dequeue and discard expired messages without processing. Worker-side checking is the enforcement backstop; the pruning process prevents queue bloat. Neither depends on the other being healthy.

**Staffing note:** The companion sorted set is a hardening component. In v1 launch (months 1–3), worker-side expiry checking is the only enforcement. The companion set ships in months 4–5.

#### 1.4.4 Hot-Path PostgreSQL Failure — Behavior Specified

The hot-path dependency means PostgreSQL availability directly gates notification delivery. The 99.99% SLA cited for managed RDS is a contractual figure that excludes scheduled maintenance, customer-caused outages, and events outside the provider's defined scope. Empirical availability of RDS Multi-AZ in production is typically 99.95–99.99%, with failover events (the relevant failure mode for this system) occurring 1–4 times per year and lasting 30–60 seconds each.

**During a PostgreSQL failover (30–60 seconds, 1–4 times/year):**

- Workers dequeue a notification ID. PostgreSQL fetch fails.
- Worker does not acknowledge the message. Visibility timeout expires and message re-enqueues.
- Worker enters exponential backoff (1s → 2s → 4s → max 30s).
- Messages accumulate in the processing list, bounded by active workers × reclaim threshold. At 23 workers with 60-second reclaim: ~1,380 messages maximum in-flight.
- P0 maximum delay = reclaim threshold (60s) + re-queue time + next worker pickup ≈ 60–90 seconds.

**The honest statement on OTP:** A 60–120 second PostgreSQL failover delay means a user waiting at a login screen waits 60–120 seconds for their OTP. The OTP remains valid (stored in Redis with 10-minute TTL) — this addresses code expiry but not the user experience problem. A user waiting 2 minutes for a login code will retry, contact support, or abandon the flow.

**The actual mitigation for OTPs, not a redefinition:** OTP delivery is classified P0 and uses a separate code path. The OTP value and the user's phone number or email address are written to Redis at generation time. If the PostgreSQL fetch fails, the worker falls back to the Redis-cached payload rather than failing entirely. This eliminates the PostgreSQL hot-path dependency for OTPs specifically. The fallback payload in Redis is a stripped structure (recipient, OTP value, expiry) sufficient to dispatch the notification without a database read.

```python
# OTP enqueue path (differs from standard path)
notification_id = generate_id()
otp_payload = {recipient: ..., value: ..., expires_at: ...}
SETEX otp_fallback:<notification_id> 600 serialize(otp_payload)
RPUSH queue:P0:sms <notification_id>

# Worker dequeue path
payload = fetch_from_postgres(notification_id)
if payload is None:  # DB unavailable
    payload = GET otp_fallback:<notification_id>
    if payload is None:
        # Both DB and Redis unavailable — genuine failure
        retry_with_backoff()
        return
```

This adds a Redis dependency to the OTP path but Redis failover is faster (seconds, not minutes) and the fallback is already present in the architecture.

### 1.5 Deduplication

**Implementation:** Atomic SET NX with TTL.

```python
SET dedup:<user_id>:<notification_type>:<content_hash> 1 NX EX 300
```

**Content hash definition — made explicit:**

The content hash is computed over the fields that make two notifications semantically distinct to the recipient. For social notification types:

```python
def compute_content_hash(notification):
    if notification.type == "like":
        # Hash includes: post_id, actor_id
        # Does NOT include: timestamp, notification_id
        # Two likes on the same post by the same actor = duplicate
        # Two likes on the same post by different actors = distinct
        return sha256(f"{notification.post_id}:{notification.actor_id}")

    if notification.type == "message":
        # Hash includes: conversation_id, message_id
        # Two messages in the same conversation = distinct (different message_id)
        return sha256(f"{notification.conversation_id}:{notification.message_id}")

    if notification.type == "follow":
        # Hash includes: actor_id
        # Same actor following twice within 5 minutes = duplicate
        return sha256(f"{notification.actor_id}")

    # Default: hash over full content fields, excluding metadata
    return sha256(serialize