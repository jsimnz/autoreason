# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 30–70M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

Two items require explicit sign-off before this design is finalized: the SMS budget (Section 3.4) and the QA approach (Section 7). Both carry real risk if approved without deliberate acknowledgment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. The critical input is notifications per user per day — a figure that varies significantly by product type, notification policy, and user segment.

**Benchmarks for context:**
- Twitter/X (feed-heavy social): ~8–12 notifications/day for active users
- Instagram (engagement-heavy): ~15–25 notifications/day
- Aggressive social apps: 30+ (often with user churn consequences)
- Conservative estimate for a new social app: 10–15

We use 15 as our planning basis, with explicit sensitivity cases:

| Scenario | Notifications/User/Day | Basis |
|----------|----------------------|-------|
| Conservative | 8 | Curated, low-noise product |
| **Planning basis** | **15** | Mid-range social app |
| Aggressive | 30 | High-engagement product |

**Notification volume is not limited to DAU.** Active users generate most notifications, but inactive users receive digests, re-engagement emails, and security alerts. The correct denominator depends on channel:

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU (3M) | Requires app installed and foreground/background |
| In-app | DAU (3M) | Only visible when logged in |
| Email | MAU (10M) + lapsed users | Email works regardless of app activity |
| SMS | Event-triggered, any user | Auth events happen to inactive users too |

This changes the volume calculation materially:

**Planning basis (15 notifications/user/day, mixed denominator):**

| Channel | Recipients | Rate | Volume/Day |
|---------|-----------|------|-----------|
| Push (70% of DAU activity) | 3M DAU | 10.5/day | ~31M |
| In-app (20% of DAU activity) | 3M DAU | 3/day | ~9M |
| Email digests | 10M MAU | 0.3/day | ~3M |
| Email transactional | Event-driven | — | ~0.5M |
| SMS | Event-driven | — | ~75K |
| **Total** | | | **~44M/day** |

**Sensitivity range:** 20M/day (conservative) to 90M/day (aggressive). Infrastructure must handle the aggressive case without redesign.

| Metric | Conservative | Planning | Aggressive |
|--------|-------------|----------|-----------|
| Total notifications/day | ~20M | ~44M | ~90M |
| Peak multiplier | 3× | 3× | 3× |
| Peak throughput | ~700/sec | ~1,530/sec | ~3,125/sec |
| Push workers needed | ~8 | ~16 | ~32 |

**Planning basis peak:** ~1,530/sec. We size for ~2,000/sec to accommodate the planning-to-aggressive gap without re-architecture. Worker counts are derived explicitly in Section 5.

**On these estimates generally:** We instrument actual volume from day one. Month 2 includes a mandatory calibration checkpoint: if actual volume is outside ±40% of planning basis, we revisit worker sizing and queue capacity before proceeding to month 3.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**Ownership boundaries for cross-cutting components:**

The boundary between E1 (queue infrastructure) and E4 (reliability) requires explicit definition because the most failure-prone components sit at that boundary:

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Dead-letter queue handlers, retry logic | **E4** | E1 |
| Backpressure and rate limiting | **E1** | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | **E4** | E2 |

The principle: E1 owns the path that works; E4 owns the path that fails. Where they overlap (backpressure, which is both infrastructure and a reliability mechanism), E1 owns the implementation and E4 owns the policy. Disputes escalate to a 30-minute sync, not a Slack thread.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Preference check  (Redis cache, write-through + version fencing, TTL=60s)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment
  - Channel selection
     │
     ├─→ [Push Queue]    (Redis Sorted Set)  → Push Workers   → APNs / FCM
     ├─→ [Email Queue]   (Redis Sorted Set)  → Email Workers  → SendGrid
     ├─→ [SMS Queue]     (Redis Sorted Set)  → SMS Workers    → Twilio
     └─→ [In-App Queue]  (Redis List)        → In-App Workers → PostgreSQL
                                    │
                          [Delivery Log]
                          (PostgreSQL + S3 archive)
                                    │
                          [Feedback Processor]
                          (bounces, opens, failures → suppression list)
```

### 2.2 Why Per-Channel Queues

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately one engineer-day to set up; the failure isolation benefit is worth it.

### 2.3 In-App Notifications — Queued, Not Direct Write

**Previous version asserted** that in-app notifications bypass queues because they're "cheap" and "don't need retry logic." This was wrong.

**The actual failure mode:** PostgreSQL is under write pressure during a spike — a large batch job, a slow migration, or simply peak load. With direct synchronous writes, the in-app write path blocks the router. When it times out, the notification is dropped with no retry path. This contradicts the reliability goals that motivated per-channel queues for other channels.

**Revised approach:** In-app notifications use a Redis List queue (not a Sorted Set — they're FIFO with no priority needed within this channel). In-app workers dequeue and write to PostgreSQL asynchronously. If the PostgreSQL write fails, the worker retries with backoff. The router is never blocked.

The "immediate consistency" argument was overstated: a 1–2 second delay through a queue is imperceptible to users reading their notification feed. The operational consistency with other channels (one pattern to understand, one failure mode to handle) is worth more than the marginal latency reduction of a direct write.

**In-app queue configuration:**
```
Queue type:      Redis List (LPUSH/BRPOP — FIFO)
Workers:         4 processes (in-app writes are cheap; this is conservative)
Retry on failure: exponential backoff, max 3 attempts, then DLQ
No priority tiers: all in-app notifications are equivalent priority
```

### 2.4 Preference Cache — Version Fencing

**The race condition in the previous version:** The write-through pattern (write DB, delete Redis key) has a window where a concurrent reader can repopulate the cache with stale data before the delete executes. The sequence:

```
Thread A: writes new prefs to DB
Thread B: reads old prefs from Redis (cache hit, old data)
Thread A: deletes Redis key
Thread B: re-caches old prefs with fresh TTL  ← stale data cached for 60s
```

**Fix: version fencing with compare-and-delete.**

Every preference record carries a `version` integer (monotonically incrementing on each write). The cache stores both the preferences and the version. On invalidation, we delete only if the cached version matches what we just wrote — or more simply, we use a Lua script to atomically check and delete:

```python
# Lua script: delete key only if stored version <= the version we just wrote
INVALIDATE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current then
    local data = cjson.decode(current)
    if data.version <= tonumber(ARGV[1]) then
        redis.call('DEL', KEYS[1])
        return 1
    end
end
return 0
"""

def update_user_preferences(user_id: str, updates: dict) -> int:
    # DB write returns new version number
    new_version = db.execute("""
        UPDATE user_preferences
        SET ..., version = version + 1
        WHERE user_id = %s
        RETURNING version
    """, user_id).fetchone()['version']

    # Atomic check-and-delete: only evicts if cache holds version <= new_version
    redis.eval(INVALIDATE_SCRIPT, 1, f"prefs:{user_id}", new_version)
    return new_version

def get_user_preferences(user_id: str) -> UserPreferences:
    cache_key = f"prefs:{user_id}"
    cached = redis.get(cache_key)
    if cached:
        return UserPreferences.parse(cached)

    prefs = db.query(
        "SELECT *, version FROM user_preferences WHERE user_id = %s", user_id
    )
    # Cache includes version for fencing
    redis.setex(cache_key, 60, prefs.json_with_version())
    return prefs
```

**Residual window:** A reader that already holds a stale cache entry in local memory (not Redis) will still use it until its local TTL expires. We don't cache preferences in process memory — Redis is the only cache layer. The Lua script closes the Redis-level race.

**Remaining acceptable staleness:** Up to 60 seconds in the case where a reader populates the cache legitimately just before a write, and the write's invalidation fires against an already-populated cache. This is acceptable: a user who disables push notifications may receive one more push notification. This is disclosed in the preference UI ("changes take effect within 1 minute").

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of DAU activity — ~31M/day)

**Provider:** FCM (Android) and APNs (iOS) via direct API integration. No intermediary (OneSignal, Braze) in v1. Intermediaries would save 4–6 weeks of integration work but cost $50–150K/year at this scale. We accept the upfront engineering cost.

**FCM Configuration:**
```
Worker processes:   8 (see Section 5 for derivation)
Connection pool:    50 persistent HTTP/2 connections per worker
Batch size:         500 tokens per FCM v1 batch request
Sustained rate:     400 req/sec (FCM limit: ~600/sec; we operate at 67% headroom)
Token validation:   validate on first send failure, purge on 404/InvalidRegistration
```

**APNs Configuration and JWT Handling:**

Two distinct concepts that must not be conflated:

- The **signing key** (`.p8` file from Apple Developer portal) does not expire on a timer. It is rotated manually when revoked or compromised. Store in AWS Secrets Manager.
- The **JWT token** (signed using that key) expires after 60 minutes per APNs documentation. Regenerate every 55 minutes.

The `APNsTokenManager` in the previous version had a check-then-act race condition: two threads could simultaneously find `_token is None`, both generate a JWT, and update `_token` and `_token_generated_at` non-atomically. In a multi-threaded push worker, this produces intermittent authentication failures that are difficult to diagnose. Fix: use a threading lock.

```python
import threading
import time
import jwt

class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: str):
        self.key_id = key_id
        self.team_id = team_id
        self.private_key = private_key  # Loaded from Secrets Manager at startup
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = threading.Lock()   # Prevents check-then-act race

    def get_token(self) -> str:
        # Fast path: check without lock (acceptable; worst case we enter slow path)
        now = time.time()
        if self._token and (now - self._token_generated_at) < 3300:
            return self._token

        # Slow path: acquire lock to regenerate
        with self._lock:
            # Re-check after acquiring lock (another thread may have regenerated)
            now = time.time()
            if self._token and (now - self._token_generated_at) < 3300:
                return self._token

            self._token = self._generate_jwt(now)
            self._token_generated_at = now
            return self._token

    def _generate_jwt(self, now: float) -> str:
        payload = {"iss": self.team_id, "iat": int(now)}
        headers = {"alg": "ES256", "kid": self.key_id}
        return jwt.encode(
            payload, self.private_key, algorithm="ES256", headers=headers
        )
```

**Note on multi-process workers:** If push workers are separate processes (not threads), each process has its own `APNsTokenManager` instance. The lock is only needed within a single process. For multi-process deployments, the lock is still correct (it becomes a no-op between processes) and costs nothing.

**Additional APNs configuration:**
```
Connection pool:    20 persistent HTTP/2 connections per worker
Priority header:    10 (immediate) for P0/P1; 5 (power-saving) for P2
Collapse key:       notification_type + entity_id
apns-expiration:    P0=300s, P1=3600s, P2=86400s
```

**Token management:**
- Store in `push_tokens` table with `last_used_at`, `is_valid`, `invalidated_reason`
- On FCM `InvalidRegistration` or APNs 410: mark `is_valid = false` immediately
- On APNs 410: Apple provides a timestamp; tokens registered *after* that timestamp are valid — do not purge them
- Nightly job: purge tokens where `is_valid = false` or `last_used_at < NOW() - INTERVAL '90 days'`

### 3.2 Email (digests ~3M/day, transactional ~0.5M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES is cheaper at volume but SendGrid's suppression list management, deliverability tooling, and webhook reliability justify the premium for a 4-engineer team. Revisit at 50M MAU.

**Email types