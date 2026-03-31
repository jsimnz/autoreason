# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **operational simplicity over theoretical elegance** and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU with a team of 4.

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

**Channel split:**

| Channel | % of Total | Volume/day | Recipient Base | Avg/active user/day |
|---------|-----------|------------|----------------|---------------------|
| Push | 70% | 35M | MAU with app installed (~8M) | ~4.4/active push user |
| In-app | 20% | 10M | DAU only (3M) | ~3.3/active user |
| Email | 8% | 4M | MAU with email (~9M) | — (digest model) |
| SMS | <0.01% | ~2,000 | Opted-in, auth/security only | — (gated, see §3.4) |

**On in-app frequency:** In-app notifications are a near-duplicate of push for active users but serve a distinct purpose — they populate the notification inbox for users already in the app. The in-app store is not a lower-volume channel; it's a persistent record. We keep the 20% allocation because in-app writes are cheap (direct DB writes, no external API calls).

**SMS is not 2% of volume.** At Twilio's $0.0075/message, 1M SMS/day = $225,000/month, which almost certainly exceeds the entire infrastructure budget. Our actual SMS budget ceiling is ~$15,000/month, which caps us at ~2,000 SMS/day. SMS is strictly for authentication codes and security alerts. Social engagement notifications are not sent via SMS at any scale.

### Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting Owner |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email provider, Twilio) | Token/credential lifecycle; APNs 410 detection |
| E3 | Preference management, user-facing API, suppression logic | Deduplication; suppression writes from all feedback sources |
| E4 | Reliability, monitoring, failure handling, DevOps | Scaling triggers; job health monitoring |

**APNs 410 ownership:** APNs 410 responses are detected by E2's delivery worker. The suppression write — marking a token invalid — is E3's domain. Resolution: E2's worker publishes a structured `token.invalidated` event to a dedicated Redis stream; E3's feedback processor consumes it and writes the suppression record. E2 owns detection and publishing; E3 owns suppression state. Neither engineer makes cross-domain writes directly. The same pattern handles FCM `InvalidRegistration`.

**Scaling triggers are throughput-based, not MAU-based.** A viral event can drive 10× normal throughput at 10M MAU. E4 maintains runbooks with throughput-based thresholds, not user count milestones.

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
     └── P2/P3 Worker Pool (10)                (see §3.3 for scaling)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (Postmark or SES)
     └── SMS (Twilio — auth/security only)
          │
          ▼
   [Delivery Log] (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]  ←── token.invalidated stream (from E2)
   (bounces, opens, failures → suppression)
```

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity — 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with Lua-atomic dequeue handles 50M items comfortably.

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They don't need retry logic and benefit from immediate consistency. Routing them through the push queue adds latency with no benefit.

**Preference check at routing time, not delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery wastes queue capacity on notifications that will be discarded.

**Honest statement of operational risk.** This system combines Redis sorted sets with Lua atomicity, PostgreSQL declarative partitioning, Redis Pub/Sub WebSocket fan-out, a custom digest engine, a custom feedback loop, and direct APNs/FCM integrations. None of these components is individually exotic. But this team has never operated this combination together at 50M notifications/day. The risk is not in any single component — it's in the operational surface area of running all of them simultaneously. We mitigate this through phased rollout (§7), explicit runbooks (§6), and E4's dedicated reliability ownership.

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
- On InvalidRegistration: publish token.invalidated event to Redis stream (consumed by E3)
```

**APNs Configuration and JWT Token Management:**

APNs uses `.p8` signing keys to generate short-lived JWT tokens. Three distinct layers:

- **`.p8` signing key:** Does not rotate on a schedule. Stored in AWS Secrets Manager. Rotated manually via Apple Developer Portal only if compromised. E2 owns the rotation runbook.
- **JWT token:** Generated from the `.p8` key. Expires after 1 hour. Regenerated every 45 minutes to stay well inside the expiry window.
- **In-flight requests during regeneration:** Workers fetch the token per-request from a local cache with a 30-second TTL. During regeneration, workers may use a token up to 30 seconds old — still valid since we regenerate at 45 minutes against a 60-minute expiry. No requests are interrupted.

**APNs JWT regeneration — operational design:**

Failure here means complete iOS push delivery failure after the current token expires. It requires the same monitoring rigor as a primary service.

```
Monitoring (owned by E4):
- Heartbeat metric emitted after every successful regeneration
- Alert: PagerDuty page if no successful regeneration in 50 minutes
- Alert: APNs 401 error rate > 1% triggers immediate page
  (401 = token rejected; indicates regeneration failure or clock skew)
- Dashboard: token age, last regeneration timestamp, 401 rate

On alert:
- Runbook: verify Secrets Manager access, verify background job health,
  manually trigger regeneration if job is stuck
- Fallback: if regeneration fails for >10 minutes, pause iOS push delivery
  and queue notifications for retry rather than send with an expired token
```

```
APNs runtime config:
- HTTP/2 with JWT authentication (token regenerated every 45 min)
- Connection pool: 20 persistent connections
- apns-priority: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- apns-collapse-id: notification_type + entity_id (collapses stale notifications)
- On 410: publish token.invalidated event with Apple-provided timestamp
```

**Token management:**

- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: E2 worker publishes `token.invalidated` event; E3 feedback processor marks invalid and suppresses future sends
- On APNs 410: record Apple's provided timestamp; tokens registered *after* that timestamp for the same device are valid and must not be suppressed
- Batch-purge tokens unused for 90 days (covers uninstalls without explicit logout)

### 3.2 Email (8% of volume — 4M/day)

**Provider selection — cost-honest analysis:**

At 4M emails/day (~120M/month), SendGrid's entry-level pricing does not apply. Actual costs at this volume:

| Provider | Estimated Cost/Month | Deliverability Tooling | Ops Burden |
|----------|---------------------|----------------------|------------|
| SendGrid (enterprise) | ~$20,000-40,000 | Excellent | Low |
| AWS SES | ~$12,000 | Minimal | High |
| Postmark | ~$15,000-25,000 | Good | Low-Medium |
| Mailgun | ~$15,000-20,000 | Good | Low-Medium |

**Recommendation: Postmark for transactional, SES for digest/marketing.** Postmark has strong deliverability for transactional email (password resets, security alerts) where failure has direct user trust impact. SES handles high-volume digest and marketing sends at lower cost, where per-message economics matter more than premium deliverability tooling. Tradeoff: E2 maintains two email integrations. If budget constrains us to one provider, use SES with significant investment in IP warming, bounce monitoring, and suppression list management — tasks that will consume meaningful E3 time.

**Email types:**

| Type | Provider | Trigger | Frequency Cap |
|------|---------|---------|---------------|
| Transactional | Postmark | Immediate (password reset, account alert) | No cap |
| Activity digest | SES | Daily or weekly batch | User-controlled |
| Re-engagement | SES | 7-day inactivity | Max 1/week |
| Marketing | SES | Product announcements | Max 1/week |

**Digest batching logic — data loss window closed:**

The naive approach calls `clear_carried_events` before the send attempt and relies on idempotency to handle failures. But if the process crashes after clearing and before sending, events are neither carried nor sent — a silent data loss window. The fix: send first, then clear. The `digest_id` provides idempotency against duplicate sends on retry.

```python
MAX_CARRY_FORWARD_DAYS = 7

def build_and_send_daily_digest(user_id: str, date: date) -> SendResult:
    carried = fetch_carried_events(user_id)
    fresh = fetch_unbatched_events(user_id, date)
    all_events = carried + fresh

    if not all_events:
        return SendResult.SKIPPED_EMPTY

    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    valid_events = [e for e in all_events if e.created_at.date() >= cutoff]
    expired_events = [e for e in all_events if e.created_at.date() < cutoff]

    if expired_events:
        mark_events_expired(expired_events)
        log.info(f"Expired {len(expired_events)} stale carried events for {user_id}")

    if not valid_events:
        return SendResult.SKIPPED_ALL_EXPIRED

    grouped = group_by_entity_and_type(valid_events)

    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        mark_events_carried(valid_events)
        return SendResult.CARRIED_FORWARD

    digest = DigestEmail(
        digest_id=generate_digest_id(user_id, date),  # Idempotency key
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )

    # SEND FIRST, then clear carried state
    result = send_email(digest)
    if result.success:
        clear_carried_events(user_id)
    return result
```

**Deliverability:**
- Dedicated IP pool for transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list synced to our DB daily (owned by E3 as part of the feedback loop)

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL with declarative range partitioning on `created_at`. A `UUID PRIMARY KEY` alone creates a global unique index incompatible with PostgreSQL partition pruning. The schema includes `created_at` in the primary key, which PostgreSQL requires for partitioned tables.

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
    -- UUIDs are globally unique by construction; composite PK enforces
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

**Tradeoff of composite PK:** Application code that looks up notifications by `id` alone must now include `created_at` in the query. We accept this because a global unique index defeats partition pruning and makes the 90-day partition drop expensive. The only case where we look up by bare `id` is the mark-as-read endpoint, where we include `created_at` in the request payload.

**Partition maintenance:** A nightly job (owned by E4)