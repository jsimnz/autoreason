# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 40–50M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against defined entry and exit criteria.

Two items require explicit sign-off before this design is finalized: the SMS budget (Section 3.4) and the QA approach (Section 7). Both carry real risk if approved without deliberate acknowledgment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. The critical input — notifications per user per day — varies significantly by product type and notification policy.

**Benchmarks for context:**
- Twitter/X (feed-heavy): ~8–12 notifications/day for active users
- Instagram (engagement-heavy): ~15–25 notifications/day
- Conservative new social app: 10–15

We use 15 as our planning basis with explicit sensitivity cases:

| Scenario | Notifications/User/Day | Basis |
|----------|----------------------|-------|
| Conservative | 8 | Curated, low-noise product |
| **Planning basis** | **15** | Mid-range social app |
| Aggressive | 30 | High-engagement product |

**Notification volume is not limited to DAU.** The correct denominator depends on channel:

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU (3M) | Requires app installed |
| In-app | DAU (3M) | Only visible when logged in |
| Email | MAU (10M) + lapsed users | Works regardless of app activity |
| SMS | Event-triggered, any user | Auth events happen to inactive users |

**Planning basis volume:**

| Channel | Recipients | Rate | Volume/Day |
|---------|-----------|------|-----------|
| Push (70%) | 3M DAU | 10.5/day | ~31M |
| In-app (20%) | 3M DAU | 3/day | ~9M |
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

**Planning basis peak:** ~1,530/sec. We size for ~2,000/sec to accommodate the planning-to-aggressive gap without re-architecture.

**On SMS volume specifically:** A 2% SMS share (~1M/day) is irreconcilable with "gated premium channel." For 10M MAU at 30% DAU, 1M/day implies every active user receives one SMS daily. The realistic estimate is ~75K/day: assume 1% of DAU triggers an auth or security SMS event. At $0.0075/message, that's ~$562/day (~$205K/year). Significant, but defensible for a privileged channel. We instrument actual volume from day one and revisit if the 1% trigger rate is wrong.

**Month 2 calibration checkpoint:** If actual volume is outside ±40% of planning basis, we revisit worker sizing and queue capacity before proceeding to month 3.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**Ownership boundaries for cross-cutting components — these must be explicit because the most failure-prone components sit at the E1/E4 boundary:**

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Dead-letter queue handlers, retry logic | E4 | E1 |
| Backpressure and rate limiting | E1 (implementation) | E4 (policy) |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

The principle: E1 owns the path that works; E4 owns the path that fails. Disputes escalate to a 30-minute sync, not a Slack thread.

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a deliberate risk given the timeline, partially mitigated by phased delivery.

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

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure, not a performance degradation.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately one engineer-day to set up. The failure isolation benefit is worth it at any non-trivial scale.

### 2.3 In-App Notifications — Queued, Not Direct Write

**Why not direct writes:** PostgreSQL under write pressure during a spike — a large batch job, a slow migration, or simply peak load — will block the router if in-app notifications write synchronously. When that write times out, the notification is dropped with no retry path. This contradicts the reliability goals that motivated per-channel queues for other channels.

**Revised approach:** In-app notifications use a Redis List queue (FIFO; no priority needed within this channel). Workers dequeue and write to PostgreSQL asynchronously. If the write fails, the worker retries with backoff. The router is never blocked.

The "immediate consistency" argument for direct writes is overstated: a 1–2 second delay through a queue is imperceptible to users reading their notification feed. The operational consistency — one pattern to understand, one failure mode to handle across all channels — is worth more than the marginal latency reduction of a direct write.

```
Queue type:       Redis List (LPUSH/BRPOP — FIFO)
Workers:          4 processes
Retry on failure: exponential backoff, max 3 attempts, then DLQ
Priority tiers:   none — all in-app notifications are equivalent
```

### 2.4 Preference Cache — Version Fencing

**The race condition in naive write-through:** The standard pattern (write DB, delete Redis key) has a window where a concurrent reader can repopulate the cache with stale data before the delete executes:

```
Thread A: writes new prefs to DB
Thread B: reads old prefs from Redis (cache hit, old data)
Thread A: deletes Redis key
Thread B: re-caches old prefs with fresh TTL  ← stale data cached for 60s
```

**Fix: version fencing with atomic compare-and-delete.**

Every preference record carries a `version` integer incrementing on each write. A Lua script atomically checks whether the cached version is stale before deleting:

```python
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
    new_version = db.execute("""
        UPDATE user_preferences
        SET ..., version = version + 1
        WHERE user_id = %s
        RETURNING version
    """, user_id).fetchone()['version']

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
    redis.setex(cache_key, 60, prefs.json_with_version())
    return prefs
```

**Residual acceptable staleness:** Up to 60 seconds in the case where a reader populates the cache legitimately just before a write. This is acceptable — a user who disables push notifications may receive one more push notification. Disclosed in the preference UI: "Changes take effect within 1 minute."

**Note on multi-process workers:** If workers are separate processes, each has its own token manager instance. The threading lock described in Section 3.1 is only needed within a single process; it remains correct (becomes a no-op) in multi-process deployments.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% — ~31M/day)

**Provider:** FCM (Android) and APNs (iOS) via direct API integration. No intermediary (OneSignal, Braze) in v1.

**Tradeoff:** Intermediaries save 4–6 weeks of integration work but cost $50–150K/year at this scale and reduce control over retry behavior and delivery receipts. We accept the upfront engineering cost and revisit if we need advanced segmentation.

**FCM Configuration:**
```
Worker processes:   16 (derived in Section 5)
Connection pool:    50 persistent HTTP/2 connections per worker
Batch size:         500 tokens per FCM v1 batch request
Sustained rate:     400 req/sec (FCM limit ~600/sec; 67% headroom)
Token validation:   validate on first send failure, purge on 404/InvalidRegistration
```

**APNs Configuration and JWT Handling:**

Two distinct concepts that must not be conflated:

- The **signing key** (`.p8` file from Apple Developer portal) does not expire on a timer. Rotate manually when revoked or compromised. Store in AWS Secrets Manager.
- The **JWT token** (signed using that key) expires after 60 minutes per APNs documentation. Regenerate every 55 minutes.

The naive implementation has a check-then-act race condition: two threads can simultaneously find `_token is None`, both generate a JWT, and update state non-atomically, producing intermittent authentication failures that are difficult to diagnose. Fix with a threading lock and double-checked locking:

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
        self._lock = threading.Lock()

    def get_token(self) -> str:
        # Fast path: check without lock
        now = time.time()
        if self._token and (now - self._token_generated_at) < 3300:
            return self._token

        # Slow path: acquire lock, re-check after acquiring
        with self._lock:
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

The signing key is the credential that must be protected. The JWT is ephemeral and regenerated from it. E2 should treat these as distinct operational concerns.

**Additional APNs configuration:**
```
Connection pool:    20 persistent HTTP/2 connections per worker
Priority header:    10 (immediate) for P0/P1; 5 (power-saving) for P2
Collapse key:       notification_type + entity_id
apns-expiration:    P0=300s, P1=3600s, P2=86400s
```

**Payload design:**
```json
{
  "notification": {
    "title": "{{actor}} liked your photo",
    "body": "{{actor}} and 3 others liked your photo"
  },
  "data": {
    "notification_id": "ntf_01H8X...",
    "type": "like",
    "entity_type": "post",
    "entity_id": "pst_01H7Y...",
    "deep_link": "myapp://posts/pst_01H7Y",
    "badge_count": "12"
  },
  "apns": {
    "headers": {
      "apns-collapse-id": "like:pst_01H7Y",
      "apns-priority": "10"
    }
  }
}
```

**Token management:**
- Store in `push_tokens` table with `last_used_at`, `is_valid`, `invalidated_reason`
- On FCM `InvalidRegistration` or APNs 410: mark `is_valid = false` immediately, never retry
- On APNs 410: Apple provides a timestamp; tokens registered *after* that timestamp are valid — do not purge them
- Nightly job: purge tokens where `is_valid = false` or `last_used_at < NOW() - INTERVAL '90 days'`

### 3.2 Email (~3.5M/day — digests plus transactional)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES is cheaper at volume but SendGrid's suppression list management, deliverability tooling, and webhook reliability justify the premium for a 4-engineer team. Revisit at 50M MAU when the cost differential grows.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transact