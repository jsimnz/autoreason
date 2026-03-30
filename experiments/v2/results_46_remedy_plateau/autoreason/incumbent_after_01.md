# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 15M–120M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

We ship a working system in month 2, iterate through month 5, and spend month 6 on hardening. No engineer owns more than two channel integrations. Every integration has a documented runbook by end of month 1.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling — With Sensitivity Analysis

We do not know our notification rate before launch. Fabricating a precise number and designing to it is a false precision trap. Here are three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change:

| Scenario | Notifs/DAU/day | DAU (30% of MAU) | Total/day | Peak/sec (3×) |
|----------|---------------|-------------------|-----------|---------------|
| Conservative | 5 | 3M | 15M | ~520 |
| **Base case** | **17** | **3M** | **51M** | **~1,750** |
| High | 40 | 3M | 120M | ~4,200 |

**Validation plan:** We instrument event emission from day one. By end of month 1, we have real data. If actual rate exceeds 30/day, we revisit queue infrastructure before month 2 scaling. Worker pool sizes and Redis capacity are explicitly sized to double without architectural change.

**Decision gate:** Do not finalize Redis cluster sizing until we have two weeks of production data. Start with a configuration handling 2,000/sec and maintain a documented runbook for scaling to 5,000/sec.

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications (likes, follows) would produce an absurd cost: 2% of 51M/day = 1M SMS/day × $0.0079 = $2.9M/year. That is not a notification system design problem — that is a business model problem. We avoid it by treating SMS as a privileged channel reserved for authentication and security.

Realistic channel mix for a social app:

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---------|-------------|------------|-----------|------------|-------|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

**Hard SMS cap:** 3 non-auth messages per user per day, plus a global daily cap of 200K messages. If the global cap is reached, non-auth SMS queues to the next day. Auth SMS (OTP) is exempt from all caps. This is enforced at the router, not the delivery worker — we never enqueue SMS we won't send.

### 1.3 Team Allocation

Assigning all four channel integrations to one engineer creates a single point of failure on the critical path. Channel integrations (APNs, FCM, SendGrid, Twilio) are the most likely source of month-1 delays. We distribute them:

| Engineer | Primary Responsibility | Secondary / Backup |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user-facing API, suppression logic, in-app | Backup: E4 |
| E4 | Email (SendGrid) + SMS (Twilio), reliability, monitoring, DevOps | Backup: E2 |

Email and SMS are grouped with reliability/DevOps (E4) because both are webhook-heavy — bounce processing, delivery receipts, STOP handling — which is operationally similar to monitoring and failure handling. APNs and FCM are grouped because they share token management complexity and both require HTTP/2 connection pooling expertise.

**Bus factor mitigation:** Each engineer produces a runbook for their integration by end of month 1. Month 2 includes explicit cross-training. We accept month-1 knowledge silos and address them directly.

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
  ├── Preference check (Redis cache, write-through)
  ├── Suppression check
  ├── Deduplication check
  ├── Priority assignment
  └── Channel selection
     │
     ├──────────────────────────────────────────┐
     ▼                                          ▼
[Priority Queue]                         [In-App Store]
  (Redis — Lua atomic ops)                (PostgreSQL,
     │                                     partitioned)
     ├── P0 Workers (10)                        │
     ├── P1 Workers (20)                        ▼
     └── P2/P3 Workers (10)             [WebSocket Layer]
          │                              (Redis Pub/Sub)
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log + Feedback Processor]
   (PostgreSQL + S3 archive)
```

### 2.2 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues mean 4 queues to monitor, 4 dead-letter queues, and priority inversions between channels. A Redis sorted set with priority-encoded scores handles 50M items comfortably at our scale. We revisit at 50M MAU when per-channel rate limiting becomes a genuine need rather than a theoretical concern.

**Synchronous preference check at routing time, not delivery time.**
User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means consuming queue capacity for notifications we then discard. At 50M/day, that waste is ~10M wasted dequeues for a 20% preference-suppression rate.

**In-app notifications bypass the queue entirely.**
In-app notifications are writes to a partitioned PostgreSQL table. They're read-heavy, need random access by user, and benefit from immediate consistency. Retry logic adds complexity without benefit — if the DB write fails, we retry at the application layer, not through a queue. Putting them through the same queue as push adds latency for no gain.

**We use managed services throughout.**
Redis (ElastiCache), PostgreSQL (RDS), and third-party delivery providers (FCM, APNs, SendGrid, Twilio). A team of 4 does not operate Kafka or Cassandra in month 1. We accept the cost premium for operational simplicity and revisit at scale.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~39M/day, 76% of volume)

**Provider:** FCM for Android, APNs for iOS. Direct integrations — no OneSignal or Braze initially.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work but costs $50–150K/year at our scale and reduces control over retry behavior and delivery receipts. We build direct integrations, accept the upfront cost, and revisit if we need advanced segmentation features later.

**FCM configuration:**
- 50 persistent HTTP/2 connections in the connection pool
- Batch size: 500 tokens per FCM v1 batch request
- Target throughput: 400 req/sec (FCM allows ~600; we leave headroom)
- Token invalidation: mark invalid on first `InvalidRegistration`; purge on 404

**APNs configuration:**
- HTTP/2 with JWT authentication
- **Important distinction:** APNs uses a long-lived private key (.p8 file) to *sign* short-lived JWT tokens. The JWT must be regenerated before its 1-hour expiry — we regenerate every 55 minutes. We do **not** rotate the .p8 key itself; that is a manual App Store Connect operation that breaks all push delivery and requires a coordinated client update. These are different operations and must not be conflated in runbooks.
- 20 persistent HTTP/2 connections
- Priority header: `10` (immediate) for P0/P1; `5` (power-saving) for P2
- Collapse key: `notification_type:entity_id` to suppress stale notifications of the same type on the same entity

**Push payload design:**

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

Stale push tokens are the primary operational headache. Our approach:
- `push_tokens` table with `last_used_at` and `is_valid` columns
- FCM `InvalidRegistration` or APNs 410: mark invalid immediately, never retry
- APNs 410: record Apple's provided timestamp; tokens registered *after* that timestamp remain valid (this handles reinstalled apps)
- Batch-purge tokens unused for 90 days — users uninstall without explicit logout

### 3.2 Email (~1.9M/day, 3.7% of volume)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be cheaper (~$190/month) but SendGrid's suppression list management, deliverability tooling, and webhook reliability justify the premium for a 4-person team. We revisit this tradeoff at 50M MAU when the cost differential becomes material.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars, versioned in Git, deployed via SendGrid API in CI/CD. Designers can update templates without touching the codebase; changes are tracked in version control.

**Digest batching with explicit termination condition:**

A carry-forward mechanism without a termination condition creates an unbounded accumulation bug: a user receiving 2 events/day accumulates indefinitely and eventually receives a digest containing weeks-old notifications. We bound this explicitly:

```python
MAX_CARRY_FORWARD_DAYS = 7  # Events older than this are dropped, not carried

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    
    # Fetch events within retention window
    events = fetch_unbatched_events(user_id, since=cutoff, until=date)
    
    # Hard purge anything older than cutoff, regardless of send decision
    purge_events_before(user_id, cutoff)
    
    if not events:
        return None
    
    grouped = group_by_entity_and_type(events)
    
    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        # Only carry forward events still within the window
        carry_forward_to_next_digest(events)
        return None  # Don't send; accumulate toward threshold
    
    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id)
    )
```

**Accepted tradeoff:** Users generating fewer than 3 grouped events/day will receive a digest at most once per week (when 7-day accumulation crosses the threshold) or not at all. This is correct behavior — a user generating 2 events/day is not highly engaged and should not receive a weekly email containing 14 stale notifications.

**Deliverability requirements:**
- Dedicated IP pool for transactional vs. marketing (warm separately over 4 weeks)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list synced from SendGrid to our DB daily

### 3.3 In-App Notifications (10M/day, 20% of volume)

**Storage schema with timezone column:**

```sql
CREATE TABLE notifications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    type         VARCHAR(64) NOT NULL,
    priority     SMALLINT NOT NULL DEFAULT 1,
    title        TEXT NOT NULL,
    body         TEXT,
    entity_type  VARCHAR(64),
    entity_id    UUID,
    metadata     JSONB,
    is_read      BOOLEAN NOT NULL DEFAULT FALSE,
    read_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ,
    user_tz      VARCHAR(64)  -- e.g. 'America/New_York'; used for digest scheduling
) PARTITION BY RANGE (created_at);

CREATE TABLE notifications_2024_01
    PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Index per partition; PostgreSQL creates these automatically with declarative partitioning
CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;
```

**Partition boundary handling:**

Without a `created_at` filter, PostgreSQL scans all partitions. At 10M rows/day, this becomes expensive quickly. We enforce a filter at the application layer:

```sql
-- BAD: scans all partitions — forbidden by linter rule
SELECT * FROM notifications
WHERE user_id = $1 AND is_read = FALSE
ORDER BY created_at DESC LIMIT 20;

-- GOOD: partition pruning kicks in; scans at most 2 partitions
SELECT * FROM notifications
WHERE user_id = $1
  AND is_read = FALSE
  AND created_at > NOW() - INTERVAL '90 days'
ORDER BY created_at DESC LIMIT 20;
```

We enforce the `created_at` filter in all application queries via a data access layer wrapper and a code review linter rule. The 90-day filter matches our retention policy, so no valid unread notification is excluded.

**Partition maintenance:**
- Pre-create the next 3 months' partitions via monthly cron
- Drop partitions older than 90 days — this is a metadata operation, not a row-by-row delete
- Monitoring alert fires if the current month's partition does not exist

**Real-time delivery:**

```
Client connects → WebSocket server → subscribes to user:{user_id} channel in Redis Pub/Sub
Notification created → write to DB → publish to Redis channel → WebSocket server → client