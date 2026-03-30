# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we make three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — not a scale decision, a correctness decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct. We spend engineering time on integration quality, not infrastructure plumbing.
3. **Incremental delivery** — working system by month 2, iterated through month 5, hardened in month 6.

One honest statement upfront: the operational surface described here is at the edge of what 4 engineers can safely own. Section 7 names what we cut and why. If scope is added mid-project, something on that list gets dropped — we will name it explicitly rather than silently accept overcommitment.

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

These ratios are estimates. We instrument from day one and adjust channel budgets in month 2.

### SMS Cost Reality

A naive SMS cost estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. This is wrong for a social app with 10M MAU, which will have significant international traffic:

| Region | Rate | Estimated Traffic Share |
|--------|------|------------------------|
| US/Canada | $0.0075 | 40% |
| Western Europe | $0.055 | 25% |
| Southeast Asia | $0.045 | 20% |
| Latin America | $0.065 | 10% |
| Other | $0.070 | 5% |

**Blended rate: ~$0.034/message. At 1M/day: ~$34,000/day.**

This is a 4.5× difference that changes the economic case for SMS entirely. Our SMS gating logic (Section 3.4) is designed around this actual cost. We enforce a hard monthly SMS budget cap in the rate limiter, not just per-user limits.

### Team Allocation

| Engineer | Primary Responsibility | Explicit Exclusions |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic | Delivery workers |
| E4 | Redis HA, Postgres operations, monitoring, alerting | Feature development |

E4's scope is explicitly bounded. Assigning one engineer to "reliability, monitoring, failure handling, DevOps" with no exclusions is a recipe for that engineer being permanently reactive. Section 7 specifies what E4 does not own in the first six months.

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
     ├─► [P0 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P0 Worker Pool (5 workers)
     │
     ├─► [P1 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P1 Worker Pool (15 workers)
     │
     ├─► [P2 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P2 Worker Pool (20 workers)
     │
     └─► [In-App Store] (PostgreSQL — bypasses queue entirely)
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
           (bounces, opens, failures, token invalidation)
```

### Why Separate Queues, Not a Single Priority Queue

The intuitive approach — a Redis sorted set with priority-encoded scores — fails at the worker level in a specific, predictable way. Workers dequeue in batches of 50. A worker that has claimed 50 P2 items will process all 50 before picking up any P0 item that arrives mid-batch. With 20 P2 workers running at peak, you can have 1,000 P2 items in-flight when a P0 security alert arrives. Under our P2 volume (~1,200/sec at peak), this is a near-constant condition.

Separate queues fix this: P0 workers only consume from the P0 queue. A P0 item is processed within one batch cycle of a P0 worker becoming available — typically under 2 seconds. The cost is monitoring 3 queues instead of 1, which is a reasonable price for correct priority semantics.

**We use Redis Lists (LPUSH/BRPOP), not Sorted Sets, for per-priority queues.** Lists give O(1) push and pop with blocking semantics. We don't need score-based ordering within a priority level — FIFO within a priority is correct behavior. Sorted Sets would add complexity without benefit.

### Preference Check Design

**TTL: 5 minutes, write-through on preference update.**

When a user changes a preference:
1. Write to PostgreSQL (source of truth)
2. Immediately invalidate and rewrite the Redis cache key for that user

This means preference changes take effect within seconds for the user who just changed them, and within 5 minutes in the edge case where cache invalidation fails. We accept up to 5 minutes of stale delivery as a known tradeoff — TTL of seconds would add ~1,750 Redis reads/sec at peak for what is functionally a cache, not a consistency boundary.

At 1,750 notifications/sec peak, preference cache reads are 1,750 Redis GET operations/sec. Redis handles >100K ops/sec on a single node. The concern is not Redis capacity — it's avoiding PostgreSQL reads on every routing decision, which at this rate would require significant DB capacity for a non-revenue operation.

### In-App Notifications Bypass the Queue

In-app notifications are writes to a database table that clients poll or receive via WebSocket. They're read-heavy, need random access by user, benefit from immediate consistency, and don't require retry logic. Routing them through the same queue as push adds latency with no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** FCM (Android) and APNs (iOS) direct integrations, not OneSignal or Braze. OneSignal/Braze would save 4–6 weeks of integration work but cost $50–150K/year at our scale and reduce control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation features post-launch.

**APNs Authentication — Precisely**

There are two distinct APNs credentials that must not be conflated:

1. **The .p8 authentication key** — a long-lived private key uploaded to Apple Developer Portal. This is not rotated on any automated schedule. Rotation requires revoking the key in the portal, uploading a new one, and redeploying. We rotate only if the key is compromised or an engineer with access departs.

2. **The JWT bearer token** — generated from the .p8 key at runtime, expires after 1 hour per Apple's spec. We refresh every 45 minutes (not 55 — leaving a 15-minute buffer against clock skew). This is a runtime operation with no Apple Developer Portal interaction.

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: str):
        # private_key loaded from AWS Secrets Manager at startup
        self.key_id = key_id
        self.team_id = team_id
        self.private_key = private_key
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
        payload = {"iss": self.team_id, "iat": int(time.time())}
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={"kid": self.key_id}
        )
```

**FCM Configuration:**
```
Connection pool:  50 persistent HTTP/2 connections
Batch size:       500 tokens per FCM v1 batch request
Rate:             FCM allows ~600 req/sec per project; we operate at 400
Token handling:   Invalidate immediately on 404; never retry invalidated tokens
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

Use `apns-collapse-id` and FCM's `collapse_key` to prevent notification storms — "Alice liked your photo" followed by "Bob liked your photo" replaces rather than stacks on the lock screen until the user opens the app.

**Token management:**
```sql
CREATE TABLE push_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    platform            VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android')),
    token               TEXT NOT NULL,
    is_valid            BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    invalidated_at      TIMESTAMPTZ,
    invalidation_reason VARCHAR(64),
    UNIQUE (platform, token)
);
```

On FCM `InvalidRegistration` or APNs 410: set `is_valid = false`, record reason, never retry. Batch-purge tokens with `last_used_at` older than 90 days in a weekly maintenance job.

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be cheaper (~$400/day cheaper at volume) but SendGrid's deliverability tooling, suppression list management, and webhook reliability are worth the premium for a team of 4 without dedicated deliverability expertise. Revisit at 50M MAU when the cost delta justifies dedicated operations.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, security alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars, versioned in Git, deployed via SendGrid API in CI/CD. Designers edit templates; engineers deploy them. Neither party needs to be in the other's system.

**Digest carry-forward — using explicit storage, not in-memory state:**

The naive approach — carrying forward events in application memory or as a side-effect of the digest job — creates a data loss risk. System restarts, user unsubscribes, and account deletions can silently drop or incorrectly send pending events. We use an explicit table:

```sql
CREATE TABLE digest_pending_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    notification_id     UUID NOT NULL REFERENCES notifications(id),
    event_type          VARCHAR(64) NOT NULL,
    entity_type         VARCHAR(64),
    entity_id           UUID,
    metadata            JSONB,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_digest_date DATE NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'suppressed', 'expired'))
);

CREATE INDEX idx_digest_pending_user_date
    ON digest_pending_events (user_id, scheduled_digest_date)
    WHERE status = 'pending';
```

The digest job logic:
```python
def build_daily_digest(user_id: str, target_date: date) -> DigestEmail | None:
    # Check suppression FIRST — before touching any events
    if is_user_unsubscribed(user_id, channel='email_digest'):
        mark_pending_suppressed(user_id)
        return None

    events = fetch_pending_digest_events(user_id, target_date)
    if not events:
        return None

    grouped = group_by_entity_and_type(events)

    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        carry_forward_to_next_date(
            event_ids=[e.id for e in events],
            next_date=target_date + timedelta(days=1),
            max_age_days=7  # events older than 7 days are marked 'expired', never sent
        )
        return None

    # Mark sent atomically with send — if send fails, status stays 'pending'
    mark_events_sent(event_ids=[e.id for e in events])
    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id)
    )
```

On unsubscribe or account deletion: mark all `pending` events `suppressed` synchronously in the same transaction, not via a background scan. Maximum carry-forward age is 7 days; a nightly job expires anything older.

**Deliverability:**
- Dedicated IP pools: transactional vs. marketing, warmed separately
- SPF, DKIM, DMARC configured before any email is sent
- Bounce rate target: <2%; spam rate target: <0.1%
- On unsubscribe: write to SendGrid suppression list and our DB simultaneously, not sequentially

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL partitioned table.

```sql
CREATE TABLE notifications (
    id          UUID NOT NULL,
    user_id     UUID NOT NULL,
    type        VARCHAR(64) NOT NULL,
    priority    SMALLINT NOT NULL DEFAULT 1,
    title       TEXT NOT NULL,
    body        TEXT,
    entity_type VARCHAR