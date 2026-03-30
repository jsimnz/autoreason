# Notification System Design Proposal (Revised)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The previous version made several correctness errors and underspecified critical failure modes. This revision addresses them directly.

**What changed from the previous version and why:**
- Replaced single priority queue with separate P0/P1/P2 queues to fix head-of-line blocking (not a scale concern — a correctness concern)
- Fixed atomic dequeue implementation to use actual Lua scripts
- Revised SMS cost estimates to account for international traffic
- Specified Redis HA configuration and degradation paths
- Fixed APNs JWT terminology and rotation procedure
- Addressed digest carry-forward data loss
- Specified WebSocket horizontal scaling model
- Addressed Postgres partition query behavior for unread notifications
- Scoped E4's responsibilities to what one engineer can actually own

**One honest statement upfront:** The operational surface described in this document is at the edge of what 4 engineers can safely own. Section 7 describes what we cut and why. If leadership adds scope mid-project, something on this list gets dropped — we will name it explicitly rather than silently accept overcommitment.

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
| SMS (2%) | 1M/day | Auth + high-priority only |

### Revised SMS Cost Model

The previous version estimated SMS at $7,500/day using Twilio's US rate of $0.0075/message. This was wrong. A social app with 10M MAU will have significant international users. Twilio rates for major international markets:

| Region | Rate | Estimated Traffic Share |
|--------|------|------------------------|
| US/Canada | $0.0075 | 40% |
| Western Europe | $0.055 | 25% |
| Southeast Asia | $0.045 | 20% |
| Latin America | $0.065 | 10% |
| Other | $0.07 | 5% |

**Blended rate: ~$0.034/message. At 1M/day: ~$34,000/day.**

This is not a rounding error — it's a 4.5× difference that changes the economic case for SMS as a channel. Our SMS gating logic (Section 3.4) is designed around this actual cost, not the understated US-only figure. We recommend a monthly SMS budget cap enforced in the rate limiter, not just per-user limits.

### Team Allocation

| Engineer | Primary Responsibility | What They Do Not Own |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic | Delivery workers |
| E4 | Redis HA, Postgres operations, monitoring, alerting | Feature development |

E4's scope is explicitly bounded in Section 7. The previous version assigned E4 an undeliverable operational surface. We have made explicit cuts.

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
  - Preference check (Redis cache, write-through, 5-min TTL)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├──────────────────────────────────────────────┐
     │                                              │
     ├─► [P0 Queue] (Redis List)                   │
     │     └── P0 Worker Pool (5 workers)           │
     │                                              │
     ├─► [P1 Queue] (Redis List)                   │
     │     └── P1 Worker Pool (15 workers)          │
     │                                              │
     └─► [P2 Queue] (Redis List)                   │
           └── P2 Worker Pool (20 workers)          │
                                                    ▼
                                           [In-App Store]
                                           (PostgreSQL)
                    │
                    ▼
           [Channel Dispatcher]
             ├── Push (APNs / FCM)
             ├── Email (SendGrid)
             └── SMS (Twilio)
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archive)
```

### Why Separate Queues, Not a Single Priority Queue

The previous version used a single Redis sorted set with priority-encoded scores and claimed "P0 always beats P1." This claim was false at the worker level.

Workers dequeue in batches of 50. A worker that has already claimed a batch of 50 P2 items will process all 50 before picking up any P0 item that arrives during that window. With 20 P2 workers running at peak, you can have 1,000 P2 items in-flight when a P0 security alert arrives. "In-flight" means locked in a worker pipeline — unavailable to any other worker. Under our P2 volume (35M items/day, ~1,200/sec at peak), this is a near-constant condition, not an edge case.

**Separate queues fix this at the cost of slightly more operational surface.** P0 workers only consume from the P0 queue. A P0 item is processed within one batch cycle of a P0 worker becoming available — typically under 2 seconds at our scale. The tradeoff is that we now monitor 3 queues instead of 1. That's a reasonable price for correct priority semantics.

**We use Redis Lists (LPUSH/BRPOP), not Sorted Sets, for the per-priority queues.** Lists give us O(1) push and pop with blocking semantics. We don't need score-based ordering within a priority level — FIFO within a priority is correct behavior. Sorted Sets would add complexity without benefit here.

### Preference Check Cache

**TTL: 5 minutes, write-through on preference update.**

When a user disables push notifications, we:
1. Write the preference to PostgreSQL (source of truth)
2. Immediately invalidate the Redis cache key for that user
3. Write the new preference value to Redis

This means preference changes take effect within seconds for the user who just changed them (cache invalidated on write), and within 5 minutes for any edge case where the invalidation fails. We accept up to 5 minutes of stale delivery as a known tradeoff — the alternative (TTL of seconds) adds ~1,750 Redis reads/sec at peak, which is meaningful load for what is supposed to be a cache.

**Read pressure:** At 1,750 notifications/sec peak, preference cache reads are 1,750 Redis GET operations/sec. Redis handles >100K ops/sec on a single node — this is not a concern. What we avoid is going to PostgreSQL on every routing decision, which at 1,750/sec would require significant DB capacity for a non-revenue operation.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** FCM (Android) and APNs (iOS) direct integrations.

**APNs Authentication — Corrected Terminology**

The previous version said "rotate JWT keys every 55 minutes." This was wrong in a way that would cause operational confusion.

There are two distinct APNs credentials:

1. **The .p8 authentication key** — a long-lived private key uploaded to Apple Developer Portal. This should not be rotated on any automated schedule. Rotation requires revoking the key in the portal, uploading a new one, and redeploying. We rotate this only if the key is compromised or an engineer with access leaves the company.

2. **The JWT bearer token** — generated from the .p8 key, expires after 1 hour per Apple's spec. We refresh this token every 45 minutes (not 55 — leaving a 15-minute buffer against clock skew). This is a runtime operation with no Apple Developer Portal interaction.

What E2 implements: a token cache that checks token age on each request and regenerates from the stored .p8 key when age > 45 minutes. The .p8 key itself lives in AWS Secrets Manager.

**FCM and APNs implementation:**

```python
# APNs token refresh — this is token refresh, not key rotation
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: str):
        self.key_id = key_id
        self.team_id = team_id
        self.private_key = private_key  # loaded from Secrets Manager at startup
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            age = time.time() - self._token_generated_at
            if self._token is None or age > 2700:  # 45 minutes
                self._token = self._generate_token()
                self._token_generated_at = time.time()
            return self._token

    def _generate_token(self) -> str:
        payload = {
            "iss": self.team_id,
            "iat": int(time.time()),
        }
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={"kid": self.key_id}
        )
```

**FCM configuration:**

```
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we operate at 400
- Token validation: validate on first 404 response, purge immediately
```

**Token management:**

```sql
CREATE TABLE push_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    platform    VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android')),
    token       TEXT NOT NULL,
    is_valid    BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at   TIMESTAMPTZ,
    invalidated_at TIMESTAMPTZ,
    invalidation_reason VARCHAR(64),
    UNIQUE (platform, token)
);
```

On FCM `InvalidRegistration` or APNs 410 response: set `is_valid = false`, record `invalidation_reason`. Never retry an invalidated token. Batch-purge tokens with `last_used_at` older than 90 days weekly.

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro tier (~$1,500/month).

**Digest carry-forward — corrected design:**

The previous version described carry-forward logic for digests with fewer than 3 items but provided no storage mechanism. Events in a carry-forward state had no defined home. This is a data loss risk: system restart, user account deletion, or unsubscribe between collection and send could silently drop or incorrectly send these events.

**Corrected approach: explicit pending digest table, not in-memory carry-forward.**

```sql
CREATE TABLE digest_pending_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    notification_id UUID NOT NULL REFERENCES notifications(id),
    event_type      VARCHAR(64) NOT NULL,
    entity_type     VARCHAR(64),
    entity_id       UUID,
    metadata        JSONB,
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_digest_date DATE NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'suppressed', 'expired'))
);

CREATE INDEX idx_digest_pending_user_date 
    ON digest_pending_events (user_id, scheduled_digest_date) 
    WHERE status = 'pending';
```

The digest job at send time:
1. Queries `digest_pending_events` for the user and date
2. If fewer than 3 items: updates `scheduled_digest_date` to tomorrow, keeps `status = 'pending'`
3. If 3+ items: renders and sends the digest, marks events `status = 'sent'`
4. On user unsubscribe or account deletion: marks all pending events `status = 'suppressed'` — triggered by a database-level event or application hook, not a background scan

**Maximum carry-forward age:** 7 days. Events older than 7 days in `pending` status are marked `expired` by a nightly job and never sent. This prevents indefinite accumulation.

```python
def build_daily_digest(user_id: str, target_date: date) -> DigestEmail | None:
    # Check suppression FIRST — before touching any events
    if is_user_unsubscribed(user_id, channel='email_digest'):
        mark_pending_suppressed(user_id)
        return None
    
    events = fetch_pending_digest_events(user_id, target_date)
    
    if len(events) == 0:
        return None
    
    grouped = group_by_entity_and_type(events)
    
    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        # Carry forward: update scheduled date, don't drop
        carry_forward_to_next_date(
            event_ids=[e.id for e in events],
            next_date=target_date + timedelta(days=1),
            max_age_days=7  # enforced: don't carry forward if event > 7 days old
        )
        return None
    
    digest = DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id)
    )
    
    # Mark sent atomically with send — if send fails, status stays 'pending'
    mark_events_sent(event_ids=[e.id for e in events])
    return digest
```

**Deliverability:**
- Dedicated IP pool: transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list: sync SendGrid suppression list to our DB daily; on unsubscribe, write to both simultaneously

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage schema:**

```sql
CREATE TABLE notifications (
    id          UUID NOT NULL,
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
    expires_at  TIMESTAMPTZ,
    PRIMARY KEY (user_id, created_at, id)  -- partition key included in PK
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE notifications_2024_01 
    PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- (automated via pg_partman)
```

**Addressing the unread index problem across partitions:**

At 10M rows/day, a monthly partition is ~300M rows. The previous version proposed a partial index `WHERE is_read = FALSE` on a partitioned table. This has a significant limitation: Postgres cannot use partition pruning with partial