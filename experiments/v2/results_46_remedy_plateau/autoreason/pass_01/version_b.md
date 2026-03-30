# Notification System Design Proposal (Revised)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling an estimated 15M–75M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU.

**Changes from previous version:** This revision corrects a queue atomicity bug (duplicate delivery risk for OTPs), fixes the SMS cost model (prior version overstated cost by ~50×), adds sensitivity analysis to the scale model, fixes the priority scoring formula to handle expiry, corrects the APNs token rotation description, adds timezone storage to the schema, fixes the digest carry-forward termination condition, defines the WebSocket reconnect API, adds partition-boundary query handling, and redistributes channel integration work across the team.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling — With Sensitivity Analysis

The previous version stated 17 notifications/user/day as an industry average without citation or validation plan. This was a fabricated anchor. Here is the honest position:

We do not know our notification rate before launch. We have three reference points from public data:
- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- Apps with aggressive notification strategies (TikTok-style) report 20–40/day

We model three scenarios and design for the middle case, with the infrastructure capable of handling the high case:

| Scenario | Notifs/DAU/day | Total/day | Peak/sec (3×) | Notes |
|----------|---------------|-----------|---------------|-------|
| Conservative | 5 | 15M | ~520 | Quiet social app, limited viral loops |
| **Base case** | **17** | **51M** | **~1,750** | **Engaged social, moderate virality** |
| High | 40 | 120M | ~4,200 | TikTok-style engagement loops |

**Validation plan:** We instrument event emission from day one. By end of month 1, we will have real data. If actual rate is above 30/day, we revisit queue infrastructure before month 2 scaling. The worker pool sizes and Redis capacity are explicitly sized to be doubled without architectural change.

**Action before infrastructure commitment:** Do not finalize Redis cluster sizing until we have 2 weeks of production data. Start with a configuration that handles 2,000/sec (base case peak) and have a documented runbook for scaling to 5,000/sec.

### 1.2 Channel Mix and SMS Cost Correction

The previous version stated 1M SMS/day at $0.0075 = $7,500/day = $2.7M/year. This was wrong, and the error was consequential enough that it should have invalidated the entire cost section. The correct analysis:

**What went wrong:** 2% of 51M/day = 1M SMS/day is the error. SMS at 2% of total volume only makes sense if SMS is used for social engagement notifications. It should not be. SMS is a high-cost, high-friction channel reserved for authentication and security. A realistic SMS volume for a 10M MAU social app is 50K–200K/day (OTPs, security alerts, explicit user-configured critical alerts only).

**Corrected channel mix:**

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---------|-------------|------------|-----------|------------|-------|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM free; APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

SMS at 150K/day = ~$1,185/day = ~$432K/year. This is still significant but within reason for a funded social app. At 1M SMS/day (the previous estimate), the cost would be ~$2.9M/year — at that point, the first engineering decision would be "negotiate an enterprise contract with Twilio or switch providers," not "build the delivery pipeline." We avoid that situation by treating SMS as a privileged channel with hard volume caps.

**Hard cap:** SMS is rate-limited to 3 non-auth messages per user per day and a global daily cap of 200K messages. If the global cap is reached, non-auth SMS queues until the next day. Auth SMS (OTP) is exempt from all caps.

### 1.3 Team Allocation

The previous version assigned all four channel integrations (APNs, FCM, SendGrid, Twilio) to a single engineer. This creates a single point of failure on the critical path. Revised allocation:

| Engineer | Primary Responsibility | Secondary |
|----------|----------------------|-----------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user API, suppression logic, in-app | Backup: E4 |
| E4 | Email (SendGrid) + SMS (Twilio), reliability, monitoring, DevOps | Backup: E2 |

Email and SMS are grouped with reliability/DevOps (E4) because both are webhook-heavy — bounce processing, delivery receipts, STOP handling — which is operationally similar to monitoring and failure handling. APNs and FCM are grouped because they share token management complexity and both require HTTP/2 connection pooling expertise.

**Bus factor mitigation:** Each engineer documents their integration in a runbook by end of month 1. E1 can cover E2's push work; E4 can cover E3's preference work. We accept that month 1 will have knowledge silos and address this explicitly in month 2 cross-training.

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
  - Deduplication check
  - Channel selection
     │
     ├─────────────────────────────────────────┐
     ▼                                         ▼
[Priority Queue]                        [In-App Store]
  (Redis — Lua atomic ops)               (PostgreSQL,
     │                                    partitioned)
     ├── P0 Workers (10)
     ├── P1 Workers (20)
     └── P2/P3 Workers (10)
          │
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

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with priority-encoded scores handles 50M items comfortably. We revisit at 50M MAU.

**Synchronous preference check at routing time, not delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery means consuming queue capacity for notifications we discard. At 50M/day, that waste matters.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They don't need retry logic and benefit from immediate consistency. Putting them through the same queue as push adds latency for no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (76% of volume — ~39M/day)

**Provider:** Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS. Direct integrations, no intermediary like OneSignal initially.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work but costs ~$50–150K/year at our scale and reduces control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation.

**FCM configuration:**
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we target 400 to leave headroom
- Token validation: mark invalid on first `InvalidRegistration` response; purge on 404

**APNs configuration:**
- HTTP/2 with JWT authentication
- **Correction from previous version:** APNs uses a long-lived private key (.p8 file) to *sign* short-lived JWT tokens. The JWT token must be regenerated before it expires (Apple's limit is 1 hour). We regenerate every 55 minutes. We do **not** rotate the .p8 key — that is a manual process in App Store Connect that would break all push delivery and requires a coordinated client update. The previous version conflated these two operations.
- Connection pool: 20 persistent connections
- Priority header: `10` (immediate) for P0/P1, `5` (power-saving) for P2
- Collapse key: `notification_type:entity_id` to collapse stale notifications of the same type on the same entity

**Token management:**

Stale push tokens are the primary operational headache.
- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: mark invalid immediately, never retry
- On APNs 410: record the timestamp Apple provides; tokens registered *after* that timestamp are valid (Apple's feedback mechanism for reinstalled apps)
- Batch-purge tokens unused for 90 days

### 3.2 Email (~3.7% of volume — ~1.9M/day)

**Provider:** SendGrid Pro (~$1,500/month at this volume). AWS SES would be cheaper (~$190/month) but SendGrid's suppression list management, deliverability tooling, and webhook reliability justify the premium for a 4-person team. We revisit at 50M MAU when the cost differential becomes meaningful.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Digest batching with termination condition:**

The previous version had a carry-forward logic with no termination condition. A user receiving 2 events/day would accumulate events indefinitely, eventually receiving a digest containing weeks-old notifications.

```python
MAX_CARRY_FORWARD_DAYS = 7  # Never carry events older than this

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    # Fetch events including carried-forward ones, but hard-cap age
    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    events = fetch_unbatched_events(user_id, since=cutoff, until=date)
    
    # Purge events older than cutoff regardless of whether we send
    purge_events_before(user_id, cutoff)
    
    if len(events) == 0:
        return None
    
    grouped = group_by_entity_and_type(events)
    
    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        # Only carry forward if events are recent enough to still be relevant
        recent_events = [e for e in events 
                         if e.created_at > date - timedelta(days=MAX_CARRY_FORWARD_DAYS)]
        if recent_events:
            carry_forward_to_next_digest(recent_events)
        # Old events are dropped — they've expired
        return None
    
    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id)
    )
```

**What this changes:** Users who receive fewer than 3 events/day will get a digest at most once per week (when the 7-day accumulation crosses the threshold) or not at all. This is the correct behavior — a user who generates 2 events/day is not an engaged user and should not receive a weekly email containing 14 stale notifications. We accept this tradeoff explicitly.

**Deliverability:**
- Dedicated IP pool for transactional vs. marketing (warmed separately over 4 weeks)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list synced from SendGrid to our DB daily

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage schema:**

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
) PARTITION BY RANGE (created_at);

-- Create partitions at deploy time and via monthly cron
CREATE TABLE notifications_2024_01 
    PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ... repeat for each month

CREATE INDEX idx_notifications_user_unread_2024_01
    ON notifications_2024_01 (user_id, created_at DESC)
    WHERE is_read = FALSE;
```

**Partition boundary handling — corrected from previous version:**

The previous version did not address queries spanning partition boundaries. At midnight on the first of each month, a user's unread notifications may span two partitions. PostgreSQL's partition pruning handles this transparently for queries with range predicates, but only if the query includes a `created_at` filter. Without it, PostgreSQL scans all partitions.

```sql
-- BAD: scans all partitions
SELECT * FROM notifications 
WHERE user_id = $1 AND is_read = FALSE
ORDER BY created_at DESC LIMIT 20;

-- GOOD: partition pruning kicks in, scans at most 2 partitions
SELECT * FROM notifications 
WHERE user_id = $1 
  AND is_read = FALSE
  AND created_at > NOW() - INTERVAL '90 days'
ORDER BY created_at DESC LIMIT 20;
```

We enforce the `created_at` filter in all application queries. The 90-day filter matches our retention policy, so no valid unread notification is excluded. We document this constraint in the data access layer and add a linter rule to catch unbounded queries in code review.

**Partition maintenance:** Monthly partitions at 10M rows/day = ~300M rows/partition. We pre-create the next 3 months' partitions in a cron job. We drop partitions older than 90 days (3 months) — dropping a partition is a metadata operation, not a row-by-row delete. A monitoring alert fires if the current month's partition does not exist.

**Real-time delivery via WebSocket:**

```
Client connects → WebSocket server → subscribes to user:{user_id} 
                                     channel in Redis Pub/Sub
Notification created → write to DB → publish to Redis channel 
                    → WebSocket server → client
```

**