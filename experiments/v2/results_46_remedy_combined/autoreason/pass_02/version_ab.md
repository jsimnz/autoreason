# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 125M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system that trades occasional staleness for throughput.

This document is explicit about every tradeoff. Where a decision requires authorization from outside the engineering team — budget, product behavior, legal compliance — that decision point is named and the engineering default is stated. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so the consequences of those decisions are visible.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Notifications are sent to opted-in users regardless of whether they opened the app that day. The correct volume multiplier is the opted-in subscriber base, not DAU.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| Push opt-in rate | 60% | ~6M users; iOS ~50%, Android ~70% |
| Email opt-in rate | 75% | ~7.5M users; most register with email |
| SMS opt-in rate | 15% | ~1.5M users; high-friction opt-in by design |
| Avg notifications/opted-in user/day | ~15 | Industry range 10–20 for active social apps |
| **Total push/day** | **~90M** | 6M × 15 |
| **Total email/day** | **~4M** | Digest/batch model limits raw volume |
| **Total in-app/day** | **~30M** | ~3M DAU × 10 |
| **Total SMS/day (capped)** | **~150K** | Hard-gated; see Section 3.4 |
| **Total notifications/day** | **~125M** | Central estimate |
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput** | **~4,300/sec** | 125M × 3 / 86,400 |

**Acknowledged uncertainty:** The 15 notifications/user/day figure is an estimate. We instrument actual send rates from week one. Defined scaling trigger: if sustained peak throughput exceeds 8,000/sec for more than 15 minutes, we add worker capacity and evaluate queue backend. We do not wait for an incident.

### 1.2 SMS Cost — Full Exposure

The 150K/day cap covers engagement and marketing SMS only. OTP and security SMS is exempt from the cap but tracked separately.

| Scenario | OTP Volume | Daily Cost (Twilio $0.0079/msg) |
|----------|-----------|----------------------------------|
| Baseline (2FA logins, ~5% of DAU) | ~150K/day | ~$1,185 |
| Credential stuffing (forced re-auth, 20% MAU) | ~2M/day | ~$15,800 |
| Major security incident (all MAU forced re-auth) | ~10M/day | ~$79,000 |

Capped engagement SMS costs approximately $430K/year. OTP SMS cost is incident-dependent and uncapped.

**Decision required from Finance and Security before launch:** Establish a monthly OTP SMS budget ceiling and define the fallback when that ceiling is approached — options include falling back to email-based OTP or temporarily disabling new 2FA enrollments. Engineering will implement whatever ceiling and fallback is authorized.

**What engineering implements regardless:** OTP SMS is metered separately in the dashboard. A CloudWatch alarm fires when OTP SMS spend exceeds $5,000/day. On-call is notified; response procedure is in the runbook. Silent absorption of a $79,000/day event is not acceptable.

### 1.3 Team Allocation

| Engineer | Primary Responsibility | Secondary |
|----------|----------------------|-----------|
| E1 | Core pipeline, queue infrastructure, delivery workers | On-call rotation |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), cross-channel consistency | On-call rotation |
| E3 | Preference management, user API, suppression, SMS rate limiting | On-call rotation |
| E4 | Reliability, monitoring, failure handling, infrastructure, test harness | On-call rotation |

**Cross-channel consistency is explicitly owned by E2.** The scenario where a user receives duplicate notifications across channels due to in-flight preference updates has a named owner and a concrete mitigation in Section 5.

**On QA:** No dedicated QA is feasible in this timeline. The known failure classes this creates are: duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors, and broken unsubscribe links. E4 owns a notification-specific test harness that systematically covers these failure classes, consuming 15% of E4's time throughout the project. This is not a risk we accept silently — it is a risk we instrument and surface.

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
  - Preference check (Redis cache, 60s TTL — see Section 5)
  - Suppression check
  - Deduplication check
  - Priority assignment
  - Channel selection
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
[Durable Priority Queues]           [In-App Store]
  (Amazon SQS — see Section 2.2)     (PostgreSQL, hash-partitioned)
     │
     ├── P0 Queue → 15 workers
     ├── P1 Queue → 25 workers
     ├── P2 Queue → 20 workers
     └── P3 Queue →  5 workers
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log]          [Feedback Processor]
   (PostgreSQL + S3)       (bounces, opens, token
                            invalidation, failures)
```

### 2.2 Queue Backend: Amazon SQS

We use Amazon SQS with four priority queues rather than a Redis sorted set. This is a deliberate choice driven by two correctness problems with the Redis approach.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. For P0 traffic (OTPs, security alerts), silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput and requires a replication topology we would need to operate ourselves.

**Problem 2 — Dequeue atomicity.** A Redis pipeline batches commands but does not provide atomicity. Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity we do not need to take on when SQS solves the problem natively.

**Queue configuration:**

```
notif-p0.fifo   — Critical (OTP, security alerts)
notif-p1.fifo   — High (DMs, mentions)
notif-p2        — Normal (likes, follows, comments) — standard queue
notif-p3        — Batch (digests, re-engagement) — standard queue
```

P0 and P1 use FIFO queues for ordering and exactly-once processing guarantees within a message group. P2 and P3 use standard queues — higher throughput, lower cost, and ordering is not semantically meaningful for likes or digests. FIFO queues are limited to 3,000 messages/second with batching; P0 and P1 traffic at 3× peak stays well within this.

**Worker allocation:**

```
P0: 15 workers — exclusive poll of notif-p0.fifo
P1: 25 workers — exclusive poll of notif-p1.fifo
P2: 20 workers — polling notif-p2
P3:  5 workers — polling notif-p3
```

Standard queue throughput at 65 workers polling with 10-message batches: ~32,500 messages/poll cycle, well above our 4,300/sec peak.

**Idempotency on standard queues:** Standard queues provide at-least-once delivery. Duplicate delivery is possible. We suppress duplicates with idempotency keys in Redis:

```python
class NotificationDispatcher:
    def dispatch(self, message: SQSMessage) -> None:
        notification_id = message.body["notification_id"]
        lock_key = f"sent:{notification_id}"

        # SET NX: only the first worker to acquire this key proceeds
        acquired = self.redis.set(lock_key, "1", nx=True, ex=86400)

        if not acquired:
            # Already dispatched — delete from queue, do not resend
            message.delete()
            self.metrics.increment("dispatch.duplicate_suppressed",
                                   tags={"priority": message.body["priority"]})
            return

        try:
            self._send_to_channel(message.body)
            message.delete()
        except Exception:
            if self._is_max_retries_exceeded(message):
                # Clear idempotency key so DLQ processor can retry cleanly
                self.redis.delete(lock_key)
            raise  # SQS visibility timeout returns message to queue
```

**Tradeoff explicitly accepted:** If Redis is unavailable, duplicate suppression fails and a user may receive a duplicate notification. For P0 (OTPs), this is acceptable because OTP tokens are single-use regardless of delivery count. For P1/P2, a duplicate mention or like notification is a UX annoyance, not a correctness failure. FIFO queues handle deduplication natively for P0 and P1, so this Redis dependency is only a concern for P2/P3.

**SQS cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately $1,800/month.

**Tradeoff we're accepting:** Four queues means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept this because SQS's durability and correct concurrent dequeue semantics are non-negotiable for P0 traffic, and managed operations are less work than operating Redis with AOF replication ourselves.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~90M/day)

**Provider:** FCM (Android) and APNs (iOS) directly, without an intermediary aggregator. At 90M push/day we are large enough that intermediary margins matter and direct provider APIs are well-documented.

**APNs JWT token management — distributed coordination:**

Two distinct concepts that must not be conflated:

- **Signing key (.p8 file):** Rotated manually, only when compromised or per security policy. Stored in AWS Secrets Manager, never written to disk.
- **JWT token:** Derived from the signing key. Must be regenerated before Apple's 60-minute expiry. This is a software operation, not a key rotation.

With multiple worker nodes, thread locks are insufficient — they are intra-process. We coordinate token generation across nodes using Redis atomic operations:

```python
class APNsTokenManager:
    TOKEN_KEY = "apns:jwt_token"
    REGENERATION_LOCK_KEY = "apns:regen_lock"
    TOKEN_LIFETIME_SECONDS = 3000   # 50 minutes; Apple expires at 60
    LOCK_TTL_SECONDS = 10           # Max time we hold the regen lock

    def __init__(self, key_id: str, team_id: str, secrets_client):
        self.key_id = key_id
        self.team_id = team_id
        self.secrets_client = secrets_client
        self._local_cache: str | None = None
        self._local_cache_at: float = 0
        self._redis = get_redis_client()

    def get_token(self) -> str:
        # Fast path: Redis has a valid token
        token = self._redis.get(self.TOKEN_KEY)
        if token:
            return token.decode()
        return self._regenerate_token()

    def _regenerate_token(self) -> str:
        lock = self._redis.set(
            self.REGENERATION_LOCK_KEY, "1",
            nx=True, ex=self.LOCK_TTL_SECONDS
        )

        if not lock:
            # Another node is regenerating — wait briefly and retry
            time.sleep(0.1)
            token = self._redis.get(self.TOKEN_KEY)
            if token:
                return token.decode()
            # Lock holder may have crashed within its TTL; proceed

        private_key = self.secrets_client.get_secret_value(
            SecretId="apns/signing-key"
        )["SecretString"]

        payload = {"iss": self.team_id, "iat": int(time.time())}
        new_token = jwt.encode(
            payload, private_key, algorithm="ES256",
            headers={"kid": self.key_id}
        )

        self._redis.setex(self.TOKEN_KEY, self.TOKEN_LIFETIME_SECONDS, new_token)
        self._redis.delete(self.REGENERATION_LOCK_KEY)

        # Update local cache
        self._local_cache = new_token
        self._local_cache_at = time.time()
        return new_token
```

**Redis unavailability fallback:** Each worker caches the last known good token in memory with its generation timestamp. If Redis is unreachable, workers use the cached token until it expires, then log an error and pause sends. We do not attempt uncoordinated regeneration — thundering herd against the APNs endpoint is worse than a brief send pause.

**APNs Collapse ID — product decision surfaced:**

Setting Collapse ID to `{notification_type}:{entity_id}` silently drops notifications when multiple users interact with the same entity. Two users commenting on post `abc123` generates Collapse ID `comment:abc123` for both; the second replaces the first on the recipient's device.

| Scheme | Behavior | Tradeoff |
|--------|----------|----------|
| `{type}:{entity_id}` | Latest notification per entity wins | Silent drops on popular content |
| `{type}:{entity_id}:{actor_id}` | One notification per actor per entity | No collapsing for repeat actions |
| `{type}:{entity_id}:{hour}` | Collapse within hourly window | Balances freshness with count |
| No Collapse ID | All notifications delivered | Floods device tray on viral content |

**Engineering default:** `{notification_type}:{entity_id}:{recipient_id}` — functionally equivalent to no Collapse ID for individual notifications, while allowing collapse if the same user generates the same action twice. For digests: `digest:{recipient_id}:{date}` so the latest digest supersedes the previous one.

**Decision required from Product before launch:** Collapse behavior for high-engagement scenarios is a product decision. The engineering default delivers all notifications, which maximizes engagement signal but increases notification fatigue on viral content. The Collapse ID scheme is a one-line configuration change per notification type.

**Connection pools:**

```
FCM:  50 persistent HTTP/2 connections
      Batch size: 500 tokens/request
      Max send rate: 400 req/sec (FCM limit 600; we maintain headroom)

APNs: 20 persistent HTTP/2 connections per worker node
      Priority header: 10 (immediate) for P0/P1; 5 (power-saving) for P2
```

**Token invalidation:**

```sql
CREATE TABLE push_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    platform            VARCHAR(8) NOT NULL CHECK (platform IN ('ios', 'android')),
    token               TEXT NOT NULL,
    is_valid            BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    invalidated_at      TIMESTAMPTZ,
    invalidation_reason TEXT,
    UNIQUE (platform, token)
);
```

On FCM `InvalidRegistration` or APNs 410: set `is_valid = false`, record reason, never retry that token. On APNs 410, record Apple's provided timestamp; tokens registered after that