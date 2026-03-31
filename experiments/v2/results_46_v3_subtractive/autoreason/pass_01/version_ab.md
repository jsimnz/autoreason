# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |

**Channel split — and why it must be modeled carefully:**

The 17 notifications/user/day figure applies to DAU (3M active users). Channels that only reach active users must be sized against DAU, not MAU. Channels that reach inactive users (email, SMS) can reach the full MAU base for certain message types.

| Channel | % of Total | Volume/day | Recipient Base | Avg/active user/day |
|---------|-----------|------------|----------------|---------------------|
| Push | 70% | 35M | MAU with app installed (~8M) | ~4.4 pushes/active user |
| In-app | 20% | 10M | DAU only (3M) | ~3.3 in-app/active user |
| Email | 8% | 4M | MAU with email (~9M) | — (digest model) |
| SMS | 2% | 1M | Opted-in subset | — (gated, see §3.4) |

**SMS cost is a go/no-go risk, not a footnote.** At Twilio's standard rate of $0.0075/message, 1M SMS/day = $7,500/day = **$225,000/month**. This almost certainly exceeds the entire infrastructure budget for a 4-engineer team. Our actual SMS budget target is **under $15,000/month**, which caps us at ~2,000 SMS/day. The 2% channel allocation above is aspirational; Section 3.4 redesigns SMS as a strict authentication and security-alert channel with hard volume gates. We do not offer SMS for social engagement notifications at launch.

### Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting Owner |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Token/credential lifecycle |
| E3 | Preference management, user-facing API, suppression logic | Deduplication; feedback loop (bounces → suppression) |
| E4 | Reliability, monitoring, failure handling, DevOps | Scaling triggers and incident response |

Cross-cutting ownership is explicit because deduplication, aggregation, and the bounce-to-suppression feedback loop fall between team boundaries by default. Scaling triggers are owned by E4 and defined by **throughput, not user count** — a viral event can drive 10× normal throughput at 10M MAU.

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
  - Preference check (Redis cache)
  - Suppression check
  - Priority assignment
  - Channel selection
  - Aggregation window check
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
[Priority Queue]                   [In-App Store]
(Redis — Lua-atomic ops)           (PostgreSQL, partitioned)
     │                                     │
     ├── P0 Worker Pool (10)               └── Redis Pub/Sub fan-out
     ├── P1 Worker Pool (20)                   → WebSocket servers
     └── P2/P3 Worker Pool (10)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — auth/security only)
          │
          ▼
   [Delivery Log] (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures → suppression)
```

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity — 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with correct priority encoding handles 50M items comfortably.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They don't need retry logic and benefit from immediate consistency. Putting them through the push queue adds latency for no benefit.

**Preference check at routing time, not delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery wastes queue capacity on notifications that will be discarded.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS. Direct integrations — no intermediary like OneSignal or Braze initially.

**Tradeoff:** OneSignal/Braze saves 4-6 weeks of integration work but costs ~$50-150K/year at our scale and reduces control over retry behavior and delivery receipts. We build direct integrations and accept the upfront engineering cost. We revisit if we need advanced segmentation features.

**FCM Configuration:**
```
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we operate at 400
- Token validation: validate on first send failure, purge on 404/InvalidRegistration
```

**APNs Configuration:**

APNs uses `.p8` signing keys to generate short-lived JWT tokens. JWT tokens expire after 1 hour and must be regenerated on a schedule — we regenerate every 45 minutes to stay well inside the window. The `.p8` signing key itself does not rotate on a schedule; it is manually revoked via Apple Developer Portal if compromised and stored in AWS Secrets Manager.

```
APNs runtime config:
- HTTP/2 with JWT authentication (token regenerated every 45 min)
- Connection pool: 20 persistent connections
- apns-priority: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- apns-collapse-id: notification_type + entity_id to collapse stale notifications
```

**Token management:**

Stale push tokens are the #1 operational headache.
- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: mark invalid immediately, never retry
- On APNs 410: record the timestamp APNs provides; tokens registered *after* that timestamp are valid
- Batch-purge tokens unused for 90 days (covers users who uninstall without explicit logout)

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be cheaper but SendGrid's deliverability tooling, suppression list management, and webhook reliability are worth the premium for a team of 4 that cannot afford to manage IP reputation manually.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars. Templates versioned in Git, deployed via SendGrid API in CI/CD.

**Digest batching logic — with carry-forward bounded:**

```python
MAX_CARRY_FORWARD_DAYS = 7  # Events older than this are dropped, not deferred

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    carried = fetch_carried_events(user_id)
    fresh = fetch_unbatched_events(user_id, date)
    all_events = carried + fresh

    if not all_events:
        return None

    # Drop events carried too long — prevents unbounded accumulation
    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    dropped = [e for e in all_events if e.created_at.date() < cutoff]
    all_events = [e for e in all_events if e.created_at.date() >= cutoff]
    if dropped:
        mark_events_expired(dropped)  # Logged and counted in metrics
        log.info(f"Dropped {len(dropped)} stale carried events for user {user_id}")

    grouped = group_by_entity_and_type(all_events)

    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        mark_events_carried(all_events)
        return None

    # Clear carried state before sending — if send fails, retry sends again
    # (idempotent: digest_id prevents duplicate sends)
    clear_carried_events(user_id)

    return DigestEmail(
        digest_id=generate_digest_id(user_id, date),
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )
```

Without the `MAX_CARRY_FORWARD_DAYS` bound, a user who never accumulates 3 grouped events would accumulate events indefinitely with no visibility. Events are now dropped after 7 days and tracked in metrics to tune the threshold.

**Deliverability:**
- Dedicated IP pool for transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list synced from SendGrid to our DB daily (owned by E3)

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL with declarative range partitioning on `created_at`. PostgreSQL requires that the partition key be included in the primary key — a bare `UUID PRIMARY KEY` is incompatible with partition pruning. The corrected schema:

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
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    -- created_at included in PK: required for PostgreSQL range partitioning.
    -- UUIDs are globally unique by construction; the composite PK enforces
    -- uniqueness within each partition.
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE notifications_2024_01
    PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX idx_notifications_user_all
    ON notifications (user_id, created_at DESC);
```

**Tradeoff of composite PK:** Application code that looks up by bare `id` must include `created_at` in the query. We accept this because the alternative — a global unique index — defeats partition pruning and makes the 90-day partition drop expensive. The only place we look up by bare `id` is the mark-as-read endpoint, where we include `created_at` in the request payload.

**Partition maintenance:** A nightly job (owned by E4) creates next month's partition and drops partitions older than 90 days. At 10M notifications/day, 90-day retention = ~900M rows across 3 active partitions. Dropping a partition is a metadata operation.

**Real-time delivery:** WebSocket for users actively using the app.

```
Client connects → WebSocket server → subscribes to user:{user_id} channel in Redis Pub/Sub
Notification created → write to DB → publish to Redis channel → WebSocket server → client
```

We use Redis Pub/Sub (not Streams) because we don't need persistence — the DB is the source of truth. If the WebSocket message is missed, the client polls on reconnect.

**API:**
```
GET  /v1/notifications?limit=20&cursor=<cursor>&filter=unread
POST /v1/notifications/{id}/read
POST /v1/notifications/read-all
GET  /v1/notifications/count  (unread count, cached in Redis, TTL 30s)
```

### 3.4 SMS (gated — auth/security only)

**Provider:** Twilio. At volume, SMS costs $0.0075/message. 1M/day would be $225K/month — non-viable. We hard-cap SMS at ~2,000/day ($15K/month budget).

**What gets SMS:**
- Two-factor authentication codes (always)
- Password reset (if no email response in 5 minutes)
- Security alerts (account accessed from new device)

**What never gets SMS:**
- Social engagement (likes, follows, comments) — even if user opts in
- Digests or marketing
- Anything that can wait

**Rate limiting:** Hard limit of 3 SMS/user/day for non-auth messages. Auth messages (OTP) are exempt. Implemented as a Redis counter with 24-hour TTL.

**Compliance:**
- Store consent with timestamp and source
- Honor STOP/HELP keywords via Twilio webhook
- Maintain do-not-contact list in our DB, sync to Twilio
- No SMS between 9pm–8am in user's local timezone (TCPA)

---

## 4. Priority and Batching Logic

### 4.1 Priority Levels

| Priority | Label | Examples | Target Latency | TTL |
|----------|-------|----------|----------------|-----|
| P0 | Critical | Security alerts, OTPs, payment confirmations | <5 seconds | 5 minutes |
| P1 | High | Direct messages, mentions, replies | <30 seconds | 1 hour |
| P2 | Normal | Likes, follows, comments on old posts | <5 minutes | 24 hours |
| P3 | Batch | Digest triggers, re-engagement | Scheduled | 48 hours |

Priority is set by notification type, not by user. Users can suppress channels or delay delivery, but cannot escalate priority. This prevents abuse and simplifies the model.

### 4.2 Queue Implementation

```python
# Redis Sorted Set: score = priority_weight - (timestamp / 1e10)
# Lower score = higher priority = dequeued first
# This ensures P0 always beats P1, with FIFO within same priority

PRIORITY_WEIGHTS = {
    "P0": 0,
    "P1": 1_000_000,
    "P2": 2_000_000,
    "P3": 3_000_000,
}

def enqueue(notification: Notification):
    score = PRIORITY_WEIGHTS[notification.priority] - (time.time() / 1e10)
    redis.zadd("notification_queue