# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural Issues from Design Review

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU.

**What changed in this revision:** The previous version contained a broken queue scoring formula, a non-atomic dequeue operation incorrectly described as atomic, an SMS cost figure that would destroy the infrastructure budget, a PostgreSQL partitioning scheme incompatible with the schema, a digest carry-forward function with silent data loss risk, and several architectural gaps around WebSocket scaling, cross-channel ownership, and APNs token management. Each of these is corrected below. Where a correction requires a meaningful tradeoff, it is called out explicitly.

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

The 17/user/day aggregate rate is consistent with these per-channel averages. In-app notifications are lower-frequency per user than push, which is correct — in-app surfaces a curated subset of events to users who are already in the app.

**SMS cost is a go/no-go risk, not a footnote.** At Twilio's standard rate of $0.0075/message, 1M SMS/day = $7,500/day = **$225,000/month**. This number almost certainly exceeds the entire infrastructure budget for a 4-engineer team. The previous version acknowledged this as "expensive" and moved on. That was wrong.

Our actual SMS budget target: **under $15,000/month**, which at $0.0075/message caps us at ~2,000 SMS/day — not 1M. The 2% channel allocation in the original model was aspirational, not operational. Section 3.4 redesigns SMS as a strict authentication and security-alert channel with hard volume gates. We do not offer SMS for social engagement notifications at launch.

### Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting Owner |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Aggregation/batching logic (spans routing → delivery) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Token/credential lifecycle |
| E3 | Preference management, user-facing API, suppression logic | Deduplication across channels; feedback loop (bounces → suppression) |
| E4 | Reliability, monitoring, failure handling, DevOps | Scaling triggers and incident response |

**Cross-cutting ownership is explicit.** The previous version described deduplication, aggregation, and the bounce-to-suppression feedback loop in detail but assigned no owner. These features fall between team boundaries by default; making ownership explicit prevents them from being built inconsistently by whoever gets to them first.

**Scaling triggers are owned by E4 and defined by throughput, not user count.** "Revisit at 50M MAU" was the wrong signal — the Redis contention problem, WebSocket fan-out problem, and queue bottleneck are all throughput problems. A viral event can drive 10× normal throughput at 10M MAU. E4 maintains a runbook with throughput-based thresholds (see §6).

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

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity — 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with correct priority encoding handles 50M items comfortably. The atomicity requirement is met with Lua scripts, not pipelines (see §4.2).

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

The previous version said "rotate keys every 55 min." This was incorrect and would cause production auth failures. Here is the correct model:

- APNs uses `.p8` **signing keys** to generate short-lived **JWT tokens**
- JWT tokens expire after **1 hour** and must be **regenerated** on a schedule (we regenerate every 45 minutes to stay well inside the window)
- The `.p8` signing key itself does **not** rotate on a schedule — it is manually revoked via Apple Developer Portal if compromised
- Operationally: E2 owns a background job that regenerates the JWT token every 45 minutes and updates it in the shared credential store; the `.p8` key is stored in AWS Secrets Manager and rotated manually per our key management policy

```
APNs runtime config:
- HTTP/2 with JWT authentication (token regenerated every 45 min)
- Connection pool: 20 persistent connections
- apns-priority header: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- apns-collapse-id: notification_type + entity_id to collapse stale notifications
```

**Token management:**

Stale push tokens are the #1 operational headache.
- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: mark invalid immediately, never retry
- On APNs 410: record the timestamp APNs provides; tokens registered *after* that timestamp are valid
- Batch-purge tokens unused for 90 days (covers users who uninstall without explicit logout)

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be cheaper (~$400/day less) but SendGrid's deliverability tooling, suppression list management, and webhook reliability are worth the premium for a team of 4 that cannot afford to manage IP reputation manually.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars. Templates versioned in Git, deployed via SendGrid API in CI/CD.

**Digest batching logic — with carry-forward bounded:**

The previous version called `carry_forward_to_next_digest` without defining it or bounding the deferral period. The result was silent indefinite deferral: a user who never accumulates 3 grouped events would never receive a digest, and their events would pile up invisibly. This is corrected below.

```python
MAX_CARRY_FORWARD_DAYS = 7  # Events older than this are dropped, not deferred

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    # Fetch both today's events and any carried-forward events
    carried = fetch_carried_events(user_id)  # Events deferred from prior days
    fresh = fetch_unbatched_events(user_id, date)
    all_events = carried + fresh

    if not all_events:
        return None

    # Drop events that have been carried too long — avoids stale content
    # and prevents unbounded accumulation
    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    all_events = [e for e in all_events if e.created_at.date() >= cutoff]
    dropped = [e for e in (carried + fresh) if e.created_at.date() < cutoff]
    if dropped:
        mark_events_expired(dropped)  # Logged and counted in metrics
        log.info(f"Dropped {len(dropped)} stale carried events for user {user_id}")

    grouped = group_by_entity_and_type(all_events)

    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        # Carry forward, but only within the MAX_CARRY_FORWARD_DAYS window
        mark_events_carried(all_events)
        return None

    # Clear carried state before sending — if send fails, retry sends again
    # (idempotent: digest_id prevents duplicate sends)
    clear_carried_events(user_id)
    
    return DigestEmail(
        digest_id=generate_digest_id(user_id, date),  # For idempotency
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )
```

**What this fixes:** Events are carried forward for at most 7 days. After that they are marked expired and logged (not silently dropped — we track this in metrics to tune the threshold). If a user unsubscribes, `fetch_carried_events` returns nothing because their preference is checked before digest generation begins.

**Deliverability:**
- Dedicated IP pool for transactional vs. marketing (warm separately)
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list synced from SendGrid to our DB daily (owned by E3 as part of the feedback loop)

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL with declarative range partitioning on `created_at`. The previous schema defined `id UUID PRIMARY KEY`, which creates a global unique index incompatible with partition pruning in PostgreSQL. The corrected schema includes `created_at` in the primary key, which is the PostgreSQL requirement for partitioned tables.

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

-- Monthly partitions, created in advance by a maintenance job
CREATE TABLE notifications_2024_01
    PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Indexes per partition (PostgreSQL creates these automatically
-- when defined on the parent with CREATE INDEX ... ON notifications ...)
CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX idx_notifications_user_all
    ON notifications (user_id, created_at DESC);
```

**Tradeoff of composite PK:** Application code that looks up notifications by `id` alone must now include `created_at` in the query, or use a lookup table that maps `id → (id, created_at)`. We accept this because the alternative — a global unique index — defeats partition pruning and makes the 90-day partition drop operation expensive. All internal lookups are by `(user_id, created_at)` range anyway; the only case where we look up by bare `id` is the mark-as-read endpoint, where we include `created_at` in the request payload.

**Partition maintenance:** A nightly job (owned by E4) creates next month's partition and drops partitions older than 90 days. At 10M notifications/day, 90-day retention = ~900M rows across 3 active partitions. Dropping a partition is a metadata operation — it does not require scanning rows.

**Real-time delivery via WebSocket — horizontal scaling addressed:**

The previous version described a Redis Pub/Sub fan-out architecture without acknowledging the scaling problem: with multiple WebSocket servers, every server receives every published message and must check whether it holds that user's connection. At 10M in-app notifications/day (~115/sec average, ~350/sec peak), every WebSocket server processes every message. With 10 WebSocket servers, that's