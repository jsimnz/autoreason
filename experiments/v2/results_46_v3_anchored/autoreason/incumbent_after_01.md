# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** The failure isolation argument is decisive: FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. No novel streaming topologies. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against defined entry and exit criteria.

The system ships. Elegance is a month-6 concern.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (<0.3%) | ~75K/day | Auth and security only |

**On SMS volume:** A 2% SMS share (1M/day) is irreconcilable with "gated premium channel." For 10M MAU at 30% DAU, 1M/day implies every active user receives one SMS daily — inconsistent with restricting SMS to OTP and security alerts. The realistic estimate is ~75K/day: assume 1% of DAU triggers an auth or security SMS event (new device login, password reset, 2FA enrollment). At $0.0075/message, that's $562/day (~$205K/year). Significant, but defensible for a privileged channel. We instrument actual volume from day one and revisit if the 1% trigger rate is wrong.

**On ratios generally:** These are estimates. We instrument from day one and adjust channel budgets in month 2. The numbers are a planning basis, not a contract.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a deliberate risk given the timeline, partially mitigated by phased delivery.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Preference check  (Redis cache, write-through, TTL=60s)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment
  - Channel selection
     │
     ├─→ [Push Queue]    (Redis Sorted Set)  → Push Workers   → APNs / FCM
     ├─→ [Email Queue]   (Redis Sorted Set)  → Email Workers  → SendGrid
     ├─→ [SMS Queue]     (Redis Sorted Set)  → SMS Workers    → Twilio
     └─→ [In-App Store]  (PostgreSQL)        → WebSocket / poll
                                    │
                          [Delivery Log]
                          (PostgreSQL + S3 archive)
                                    │
                          [Feedback Processor]
                          (bounces, opens, failures → suppression list)
```

### Why Per-Channel Queues

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) are now queued behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a user-facing correctness failure, not a performance degradation.

With per-channel queues, FCM rate-limiting backs up the push queue only. SMS and email queues are unaffected. The on-call engineer can shed P2 push notifications to clear the backlog without touching other channels. The failure domain is contained.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. This is real overhead, and we accept it. For a team of 4, the monitoring cost is approximately one engineer-day to set up; the failure isolation benefit is worth it at any non-trivial scale.

**In-app notifications bypass all queues.** In-app notifications are direct writes to PostgreSQL. They're cheap, don't need retry logic, and benefit from immediate consistency. Queue overhead adds latency with no benefit.

### Preference Cache Invalidation

Preferences are cached in Redis at routing time. Cache behavior:

- **TTL:** 60 seconds. Stale preferences for up to 60 seconds is acceptable; a user who disables notifications may receive one more before the cache expires.
- **Write-through:** When a user updates preferences via the API, we write to PostgreSQL and immediately invalidate (delete) the Redis key. The next routing call repopulates from the database.
- **On cache miss:** Read from PostgreSQL, write to Redis with TTL, proceed. No thundering herd risk at our scale — user_id keys are well-distributed.

```python
def get_user_preferences(user_id: str) -> UserPreferences:
    cache_key = f"prefs:{user_id}"
    cached = redis.get(cache_key)
    if cached:
        return UserPreferences.parse(cached)
    prefs = db.query("SELECT * FROM user_preferences WHERE user_id = %s", user_id)
    redis.setex(cache_key, 60, prefs.json())
    return prefs

def update_user_preferences(user_id: str, updates: dict):
    db.execute("UPDATE user_preferences SET ... WHERE user_id = %s", user_id)
    redis.delete(f"prefs:{user_id}")  # Invalidate; next read repopulates
```

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% — 35M/day)

**Provider:** FCM (Android) and APNs (iOS) via direct API integration. No intermediary (OneSignal, Braze) in v1.

**Tradeoff:** Intermediaries would save 4–6 weeks of integration work but cost $50–150K/year at this scale and reduce control over retry behavior and delivery receipts. We accept the upfront engineering cost and revisit if we need advanced segmentation features.

**FCM Configuration:**
```
Connection pool:  50 persistent HTTP/2 connections
Batch size:       500 tokens per FCM v1 batch request
Rate:             FCM allows ~600 req/sec per project; we operate at 400
Token validation: validate on first send failure, purge on 404/InvalidRegistration
```

**APNs Configuration and JWT Handling:**

There are two distinct concepts that must not be conflated:

- The **signing key** (the `.p8` file from Apple Developer portal) does not rotate on a timer. It is rotated manually when revoked or compromised. Store it in AWS Secrets Manager; rotate it as an operational procedure.
- The **JWT token** (signed using that key) expires after 60 minutes per APNs documentation. We regenerate it every 55 minutes.

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key_path: str):
        self.key_id = key_id
        self.team_id = team_id
        # Load the .p8 signing key once at startup (or from Secrets Manager)
        self.private_key = load_private_key(private_key_path)
        self._token: str | None = None
        self._token_generated_at: float = 0

    def get_token(self) -> str:
        now = time.time()
        # Regenerate JWT if older than 55 minutes
        if self._token is None or (now - self._token_generated_at) > 3300:
            self._token = self._generate_jwt(now)
            self._token_generated_at = now
        return self._token

    def _generate_jwt(self, now: float) -> str:
        payload = {"iss": self.team_id, "iat": int(now)}
        headers = {"alg": "ES256", "kid": self.key_id}
        return jwt.encode(payload, self.private_key,
                         algorithm="ES256", headers=headers)
```

The signing key is the credential that must be protected. The JWT is ephemeral and regenerated from it. E2 should treat these as distinct operational concerns.

**Additional APNs configuration:**
```
Connection pool:    20 persistent HTTP/2 connections
Priority header:    10 (immediate) for P0/P1; 5 (power-saving) for P2
Collapse key:       notification_type + entity_id (suppress stale notifications)
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

Stale tokens are the primary operational headache at scale:
- Store tokens in `push_tokens` table with `last_used_at`, `is_valid`, `invalidated_reason`
- On FCM `InvalidRegistration` or APNs 410: mark `is_valid = false` immediately, never retry
- On APNs 410: Apple provides a timestamp; tokens registered *after* that timestamp are valid — do not purge them
- Nightly job: purge tokens where `is_valid = false` or `last_used_at < NOW() - INTERVAL '90 days'`

### 3.2 Email (8% — 4M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be cheaper at volume but SendGrid's suppression list management, deliverability tooling, and webhook reliability justify the premium for a 4-engineer team. Revisit at 50M MAU when the cost differential grows.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars. Templates versioned in Git, deployed via SendGrid API in CI/CD. Designers stay out of the codebase; templates remain under version control.

**Digest batching — fully specified:**

Carry-forward state is stored in PostgreSQL, not Redis. These are durable pending items that survive process restarts.

```sql
CREATE TABLE pending_digest_events (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL,
    event_type           VARCHAR(64) NOT NULL,
    entity_id            UUID,
    actor_id             UUID,
    payload              JSONB NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    carry_forward_count  INT NOT NULL DEFAULT 0,
    expires_at           TIMESTAMPTZ NOT NULL  -- hard TTL: created_at + 14 days
);
CREATE INDEX ON pending_digest_events (user_id, created_at);
```

```python
MIN_DIGEST_ITEMS = 3
MAX_CARRY_FORWARD_CYCLES = 7   # 7 days for daily-digest users
DIGEST_EVENT_TTL_DAYS = 14     # Hard expiry regardless of carry-forward count

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    events = fetch_pending_digest_events(user_id)
    # Hard expiry enforced by expires_at column + nightly cleanup;
    # filter defensively here too
    events = [e for e in events if e.expires_at > datetime.utcnow()]

    if not events:
        return None

    grouped = group_by_entity_and_type(events)

    if len(grouped) < MIN_DIGEST_ITEMS:
        for event in events:
            if event.carry_forward_count >= MAX_CARRY_FORWARD_CYCLES:
                # User has had pending events for 7+ days without a digest.
                # Force-send below threshold rather than silently discard.
                return build_digest_force(user_id, events)
            else:
                increment_carry_forward_count(event.id)
        return None

    # Mark consumed BEFORE sending to prevent double-send on crash.
    # SendGrid idempotency key handles the case where send fails after marking.
    mark_events_consumed([e.id for e in events])

    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )
```

**Key decisions made explicit:**
- Carry-forward events live in PostgreSQL — durable, survives restarts
- Hard TTL of 14 days: nightly job drops expired events and logs the drops for monitoring
- After 7 carry-forward cycles, force-send below threshold rather than silently lose events
- Mark consumed *before* sending — crash-safe with SendGrid idempotency key as the safety net

**Deliverability:**
- Dedicated IP pools: transactional and marketing on separate pools, warmed independently
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list sync: daily pull from SendGrid to our DB (see Section 6)

### 3.3 In-App Notifications (20% — 10M/day)

**Storage:** PostgreSQL with hash partitioning on `user_id`.

**Why hash partitioning, not range partitioning on `created_at`:**

The primary access pattern is:
```sql
SELECT * FROM notifications
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 20;
```

With range partitioning on `created_at`, PostgreSQL cannot prune partitions using the `user_id` predicate. Every user query scans all active partitions — a full multi-partition scan for every notification list fetch. At 10M notifications/day across monthly partitions, this is unacceptable.

Hash partitioning on `user_id` routes each user's rows to a single partition, making the primary query efficient. Time-based archival is handled by a background job that moves rows older than 90 days to an archive table (or S3 via COPY), not by partition dropping.

```sql
CREATE TABLE notifications (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    type        VARCHAR(64) NOT NULL,
    priority    SMALLINT NOT NULL DEFAULT 1,
    title       TEXT NOT NULL,
    body        TEXT,
    entity_type VARCHAR(64),
    entity_id   UUID,
    metadata    JSONB,
    is_read     BOOLEAN