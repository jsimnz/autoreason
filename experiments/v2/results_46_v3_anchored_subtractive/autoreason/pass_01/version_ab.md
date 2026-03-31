# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. We will ship a working system in month 2, iterate through month 5, and spend month 6 on hardening.

The core architectural bet: **a durable message queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This design uses SQS-backed priority queues rather than a Redis Sorted Set — the tradeoff behind that choice is stated explicitly in Section 2.

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
| SMS | ~100K/day | Auth and security events only — see SMS section |

**Tradeoff acknowledged:** These ratios are estimates. We instrument from day one and adjust channel budgets in month 2.

**SMS volume note:** Allocating 2% of total volume (~1M/day) to SMS is inconsistent with restricting SMS to auth codes and security alerts. If SMS is limited to those use cases, realistic volume is 50K–150K messages/day (0.5–1.5% of DAU triggering an auth or security event on a given day). At Twilio's volume pricing (~$0.0075/message), that is **$375–$1,125/day**. We budget for 100K SMS/day and set a hard system-level cap with alerting at 150K/day.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given timeline.

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
  - Preference check (Redis cache, 60s TTL)
  - Suppression check
  - Priority assignment
  - Channel selection
  - Aggregation window check
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[SQS Priority Queues]                        [In-App Store]
  - p0-notifications.fifo                    (PostgreSQL,
  - p1-notifications.fifo                     partitioned)
  - p2-notifications.fifo
  - p3-notifications (standard)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2/P3 Worker Pool (10 workers)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log]
   (PostgreSQL, 90-day retention, then deleted)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, delivery failures)
```

### Why SQS, Not Redis Sorted Set

P0 notifications include OTPs and security alerts. Redis persistence (AOF/RDB) does not provide the same durability guarantee as a purpose-built message queue. Even with AOF `always` fsync mode, Redis failover involves a replication lag window during which writes can be lost — meaning an OTP is silently dropped with no retry. For a team of 4, operating Redis as a durable queue correctly (right persistence config, replication topology, failover testing) is more operational burden than the simplicity benefit justifies.

SQS FIFO queues give us: at-least-once delivery with deduplication IDs, configurable visibility timeout for in-flight messages, dead-letter queues with no additional infrastructure, and zero operational overhead. The cost at our throughput is negligible (~$50/month). SQS FIFO has a throughput limit of 3,000 messages/sec with batching — sufficient for our peak of 1,750/sec with headroom. If we exceed this, we add message group ID sharding across multiple FIFO queues.

**Why four queues, not one.** Separate queues by priority tier mean P0 workers are never blocked behind a P2 backlog. With a single queue and priority scores, a thundering herd of P2 notifications during a viral event can delay P0 delivery even with priority-aware dequeue logic. Separate queues make the isolation structural, not algorithmic. The operational cost is four queues to monitor instead of one — acceptable.

**Synchronous preference check at routing time, not at delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means you've already consumed queue capacity for a notification you'll discard. At 50M/day, that waste matters.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They're cheap, don't need retry logic, and benefit from immediate consistency. Putting them through the same queue as push adds latency for no benefit.

### Deduplication

SQS FIFO deduplication uses a `MessageDeduplicationId` set to a hash of `(user_id, notification_type, entity_id, 5-minute window)`. This prevents duplicate sends when the router retries on ingestion failures. Workers additionally check a Redis key `dedup:{notification_id}` with a 24-hour TTL before dispatching — second line of defense against at-least-once delivery semantics from SQS.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS. Direct integrations, no intermediary.

**Tradeoff:** OneSignal/Braze would save 4–6 weeks of integration work but cost ~$50–150K/year at our scale and reduce control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation features.

**FCM HTTP v1 API:** The v1 API sends one message per request. HTTP/2 multiplexing means we can have 500 in-flight requests per worker over a pool of persistent connections without waiting for responses serially. Error handling is per-message. We do not use the HTTP batch wrapper — it adds complexity and the per-message HTTP/2 approach achieves equivalent throughput with simpler error handling.

```
FCM Configuration:
- Connection pool: 50 persistent HTTP/2 connections
- Concurrency: 500 in-flight requests per worker process
- Rate: FCM allows ~600 req/sec per project; we target 400 with auto-backoff
- Token validation: validate tokens on first send failure, purge on UNREGISTERED/404
- Retry policy: exponential backoff, max 3 retries, jitter ±20%
```

**APNs JWT Token Management:** APNs JWT tokens have a hard 1-hour expiry enforced by the protocol. If a token expires mid-flight, APNs returns 403 `ExpiredProviderToken` and rejects all pushes on that connection. We refresh proactively at 55 minutes using a centralized token manager shared across all 20 pooled connections:

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: bytes):
        self._key_id = key_id
        self._team_id = team_id
        self._private_key = private_key
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        if self._token and (time.time() - self._token_generated_at) < 3000:
            return self._token
        async with self._lock:
            if self._token and (time.time() - self._token_generated_at) < 3000:
                return self._token
            return await self._refresh_token()

    async def _refresh_token(self) -> str:
        now = int(time.time())
        payload = {"iss": self._team_id, "iat": now}
        headers = {"alg": "ES256", "kid": self._key_id}
        new_token = jwt.encode(payload, self._private_key,
                               algorithm="ES256", headers=headers)
        self._token = new_token
        self._token_generated_at = now
        logger.info("apns_token_refreshed", generated_at=now)
        return new_token

    async def handle_expired_token_error(self):
        async with self._lock:
            self._token = None
            self._token_generated_at = 0
        logger.warning("apns_token_expired_forced_refresh")
```

Token refresh is serialized by the lock — only one coroutine refreshes at a time, others wait and receive the new token. We alert if token refresh fails 3 consecutive times.

```
APNs Configuration:
- HTTP/2 connection pool: 20 persistent connections
- Priority header: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- apns-expiration: P0=300s, P1=3600s, P2=86400s
- apns-collapse-id: {notification_type}:{entity_id}
- On 410 (Unregistered): record APNs-provided timestamp; tokens registered
  after that timestamp remain valid
```

**Payload design:**

```json
{
  "aps": {
    "alert": {
      "title": "{{actor}} liked your photo",
      "body": "{{actor}} and 3 others liked your photo"
    },
    "badge": 12,
    "sound": "default",
    "mutable-content": 1
  },
  "notification_id": "ntf_01H8X...",
  "type": "like",
  "entity_type": "post",
  "entity_id": "pst_01H7Y...",
  "deep_link": "myapp://posts/pst_01H7Y"
}
```

**Token management:**

```sql
CREATE TABLE push_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    platform            VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android')),
    token               TEXT NOT NULL,
    device_id           UUID,
    is_valid            BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    invalidated_at      TIMESTAMPTZ,
    invalidation_reason VARCHAR(64)
);

CREATE UNIQUE INDEX idx_push_tokens_token ON push_tokens (token) WHERE is_valid = TRUE;
CREATE INDEX idx_push_tokens_user ON push_tokens (user_id) WHERE is_valid = TRUE;
```

Nightly job: purge tokens with `is_valid = FALSE` and `invalidated_at < NOW() - INTERVAL '30 days'`. Purge valid tokens with `last_used_at < NOW() - INTERVAL '90 days'` — these represent uninstalls without explicit logout.

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro tier (~$1,500/month). AWS SES would be cheaper at volume but SendGrid's suppression list management, deliverability dashboard, and webhook reliability reduce operational burden for a team of 4. We revisit SES at 50M MAU when the cost delta justifies the operational investment.

**Email types and frequency caps:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week, separate unsubscribe |

**Template system:** SendGrid Dynamic Templates with Handlebars. Templates are versioned in Git, deployed via SendGrid API in CI/CD. Designers work in the SendGrid UI against a staging template ID; production deploys require a PR.

**Digest batching logic:**

```python
def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    events = fetch_unbatched_events(user_id, date)

    if not events:
        return None

    grouped = group_by_entity_and_type(events)

    # Avoid sending a digest for a single low-signal event.
    # Carry forward to next digest window rather than suppress permanently.
    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        carry_forward_to_next_digest(events)
        return None

    mark_events_as_batched(events)

    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )
```

**Deliverability requirements:**
- Dedicated IP pool for transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Sync SendGrid suppression list to our DB daily

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL table, not a queue. In-app notifications are read-heavy and need random access by user.

```sql
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    type        VARCHAR(64) NOT NULL,
    priority    SMALLINT NOT NULL DEFAULT 1,
    title       TEXT NOT NULL,
    body        TEXT,
    entity_type VARCHAR(64),
    entity_id   UUID,
    metadata    JSONB,
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);

CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX idx_notifications_user_all
    ON notifications (user_id, created_at DESC);
```

**Partitioning:** Partition by `created_at` monthly. Drop partitions older than 90 days. At 10M notifications/day we accumulate ~900M rows/quarter — partitioning makes vacuum and archival tractable.

**Real-time delivery:** WebSocket for active users.

```
Client connects → WebSocket server → subscribes to user:{user_id} channel in Redis Pub/Sub
Notification created → write to DB → publish to Redis channel → WebSocket server → client
```

We use Redis Pub/Sub (not Streams) because we don't need persistence — the DB is the source of truth. If the WebSocket message is missed, the client polls on reconnect.

**API:**

```
GET  /v1/notifications?limit=20&cursor=<cursor>&filter=unread
POST /v1/notifications