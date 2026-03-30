# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. We will ship a working system in month 2, iterate through month 5, and spend month 6 on hardening.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

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

**Tradeoff acknowledged:** These ratios are estimates. We instrument from day one and adjust channel budgets in month 2. SMS is expensive (~$0.0075/message at Twilio volume pricing = $7,500/day at 1M); we treat it as a premium channel and gate it aggressively.

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
  - Preference check
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
[Priority Queue]                   [In-App Store]
  (Redis Sorted Set)                (PostgreSQL)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2 Worker Pool (10 workers)
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
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures)
```

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 sets of dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with priority-encoded scores handles 50M items comfortably. We revisit when we need per-channel rate limiting at scale (50M+ MAU).

**Synchronous preference check at routing time, not at delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. The alternative — checking at delivery — means you've already consumed queue capacity for a notification you'll discard. At 50M/day, that waste matters.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They're cheap, don't need retry logic, and benefit from immediate consistency. Putting them through the same queue as push adds latency for no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS. We use FCM's HTTP v1 API and APNs HTTP/2 API directly — no intermediary like OneSignal or Braze initially.

**Tradeoff:** OneSignal/Braze would save 4–6 weeks of integration work but cost ~$50–150K/year at our scale and reduce control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation features.

**Implementation details:**

```
FCM Configuration:
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we stay at 400
- Token validation: validate tokens on first send failure, purge on 404

APNs Configuration:
- HTTP/2 with JWT authentication (rotate keys every 55 min)
- Connection pool: 20 persistent connections
- Priority header: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- Collapse key: use notification_type + entity_id to collapse stale notifications
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

Stale push tokens are the #1 operational headache. Our approach:
- Store tokens in a `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: mark invalid immediately, never retry
- On APNs 410: record the timestamp APNs provides; tokens registered after that timestamp are valid
- Batch-purge tokens unused for 90 days (users uninstall without explicit logout)

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid. At 4M/day, we're in their Pro tier (~$1,500/month). We considered AWS SES ($0.10/1K = ~$400/month) but SendGrid's deliverability tooling, suppression list management, and webhook reliability are worth the premium for a team of 4.

**Email types and templates:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** We use SendGrid Dynamic Templates with Handlebars. Templates are versioned in Git, deployed via SendGrid API in CI/CD. This keeps designers out of the codebase while keeping templates under version control.

**Digest batching logic:**

```python
def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    events = fetch_unbatched_events(user_id, date)

    if len(events) == 0:
        return None

    # Group by type for "X and 3 others liked your posts"
    grouped = group_by_entity_and_type(events)

    # Only send if above threshold — avoid single-event digests
    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        carry_forward_to_next_digest(events)
        return None

    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),  # "You have 12 new notifications"
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id)
    )
```

**Deliverability requirements:**
- Dedicated IP pool for transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list: sync SendGrid suppression list to our DB daily

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL table, not a queue. In-app notifications are read-heavy (users check notification center repeatedly) and need random access by user.

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

**Partitioning strategy:** Partition by `created_at` monthly. Drop partitions older than 90 days. At 10M notifications/day, we accumulate ~900M rows/quarter — partitioning makes maintenance operations (vacuum, archival) tractable.

**Real-time delivery:** WebSocket for users who are actively using the app.

```
Client connects → WebSocket server → subscribes to user:{user_id} channel in Redis Pub/Sub
Notification created → write to DB → publish to Redis channel → WebSocket server → client
```

We use Redis Pub/Sub (not Streams) here because we don't need persistence — the DB is the source of truth. If the WebSocket message is missed, the client polls on reconnect.

**API:**

```
GET  /v1/notifications?limit=20&cursor=<cursor>&filter=unread
POST /v1/notifications/{id}/read
POST /v1/notifications/read-all
GET  /v1/notifications/count  (unread count, cached in Redis, TTL 30s)
```

### 3.4 SMS (2% of volume — 1M/day)

**Provider:** Twilio. At 1M/day, we're spending ~$7,500/day — this is the most expensive channel by far. We treat SMS as a privileged channel.

**What gets SMS:**
- Two-factor authentication codes (always)
- Password reset (if no email response in 5 minutes)
- Security alerts (account accessed from new device)
- User-configured critical alerts (e.g., someone mentioned them)

**What never gets SMS:**
- Social engagement (likes, follows, comments) — even if user opts in
- Digests or marketing
- Anything that can wait

**Rate limiting:** Hard limit of 3 SMS/user/day for non-auth messages. Auth messages (OTP) are exempt. Implemented as a Redis counter with 24-hour TTL.

**Compliance:**
- Store consent with timestamp and source ("opted in via settings on 2024-01-15")
- Honor STOP/HELP keywords via Twilio webhook
- Maintain do-not-contact list in our DB, sync to Twilio
- TCPA compliance: no SMS between 9pm–8am in user's local timezone

---

## 4. Priority and Batching Logic

### 4.1 Priority Levels

| Priority | Label | Examples | Target Latency | TTL |
|----------|-------|----------|----------------|-----|
| P0 | Critical | Security alerts, OTPs, payment confirmations | <5 seconds | 5 minutes |
| P1 | High | Direct messages, mentions, replies | <30 seconds | 1 hour |
| P2 | Normal | Likes, follows, comments on old posts | <5 minutes | 24 hours |
| P3 | Batch | Digest triggers, re-engagement | Scheduled | 48 hours |

**Priority is set by notification type, not by user.** Users can suppress channels or delay delivery, but cannot escalate their priority. This prevents abuse and simplifies the model.

### 4.2 Queue Implementation

```python
# Redis Sorted Set: score = priority_weight + (timestamp / 1e10)
# Lower score = higher priority = dequeued first
# This ensures P0 always beats P1, with FIFO within same priority

PRIORITY_WEIGHTS = {
    "P0": 0,
    "P1": 1_000_000,
    "P2": 2_000_000,
    "P3": 3_000_000,
}

def enqueue(notification: Notification):
    score = PRIORITY_WEIGHTS[notification.priority] + (time.time() / 1e10)
    redis.zadd("notification_queue", {notification.id: score})
    redis.setex(f"ntf:{notification.id}", 86400, notification.json())
```

**Why `+ (time.time() / 1e10)` and not `- (time.time() / 1e10)`:** We want lower scores dequeued first (`ZRANGE` returns ascending order). Within the same priority bucket (e.g., all P1 at weight 1,000,000), earlier timestamps produce smaller scores, preserving FIFO. The timestamp contribution is divided by 1e10 so it stays well below 1,000,000 — a timestamp in 2024 is ~1.7 × 10⁹ seconds, so dividing by 1e10 gives ~0.17, which cannot bleed into the next priority bucket.

**Atomic dequeue via Lua script** — a Redis pipeline makes two round trips and is not atomic; a second worker can pop the same items between `ZRANGE` and `ZREM`. Use a Lua script instead:

```lua
-- dequeue_batch.lua
-- KEYS[1]: queue name
-- ARGV[1]: batch size
local results = redis.call('ZRANGE', KEYS[1], 0, ARGV[1] - 1)
if #results > 0 then
    redis.call('ZREM', KEYS[1], unpack(results))
end
return results
```

```python
dequeue_script = redis.register_script(open("dequeue_batch.lua").read())

def dequeue_batch(batch_size: int = 50) -> list[Notification]:
    ids = dequeue_script(keys=["notification_queue"], args=[batch_size])
    return [Notification.parse(redis.get(f"ntf:{id}")) for id in ids]
```

**Tradeoff:** Redis Sorted Set is not a perfect priority queue at very high concurrency — the Lua script serializes dequeue operations on a single Redis shard. At our throughput (1,750/sec peak) across 3 worker pools, this is fine; Redis can handle >100K ops/sec. At 10× this scale, we'd shard by priority level or move to Amazon SQS with priority queues.

### 4.3 Batching and Aggregation Logic

**Aggregation (same notification type, same user, short window):**

"Alice liked your photo" followed 30 seconds later by "Bob liked your photo" should become "Alice, Bob, and 3 others liked your