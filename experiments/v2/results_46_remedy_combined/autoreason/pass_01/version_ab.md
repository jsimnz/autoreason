# Notification System Design — Synthesis
## Social App: 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles **~125M notifications/day** across push, email, in-app, and SMS channels. The core architectural bets: a **durable priority queue with channel fanout** (Amazon SQS, not Redis Sorted Set), **proven managed infrastructure over custom-built components**, and **incremental delivery** — working system in month 2, hardened by month 6.

Three principles guide every tradeoff: correctness over cleverness (a silent failure in a security notification is worse than slower delivery of a like), operational simplicity for a team of 4 (managed services over self-operated infrastructure), and explicit cost control (SMS is a budget line requiring authorization, not a default channel).

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

The correct volume multiplier for notification systems is the **opted-in subscriber base**, not DAU. Notifications are sent to users regardless of whether they opened the app that day — that is the entire point of push and email.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| Push opt-in rate | 60% → 6M users | iOS ~50%, Android ~70% |
| Email opt-in rate | 75% → 7.5M users | Most register with email |
| SMS opt-in rate | 15% → 1.5M users | High-friction opt-in by design |
| Avg notifications/opted-in user/day | ~15 | Industry range: 10–20 for active social apps |
| **Total push/day** | **~90M** | 6M × 15 |
| **Total email/day** | **~4M** | Digest model limits raw volume |
| **Total in-app/day** | **~30M** | ~3M DAU × 10 events/session |
| **Total SMS/day** | **~150K** | Hard-gated; see Section 3.4 |
| **Total/day** | **~125M** | Central estimate |
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput** | **~4,300/sec** | 125M × 3 / 86,400 |

**Acknowledged uncertainty:** We instrument actual send rates from week 1. Defined scaling trigger: if sustained peak throughput exceeds 8,000/sec, we add worker capacity and evaluate queue backend. We do not wait for an incident.

### 1.2 SMS Cost — Explicit Budget Line

At Twilio standard rates ($0.0079/message), 1M messages/day = **~$2.9M/year**. This is not a footnote. SMS volume is hard-capped at **150K messages/day** (~$430K/year), enforced in code. Auth SMS (OTPs) is exempt from the cap but tracked separately. The cap threshold is a configuration value requiring VP-level approval to change. Monthly SMS spend is reported in the engineering dashboard.

### 1.3 Team Allocation

| Engineer | Primary Responsibility | Secondary |
|----------|----------------------|-----------|
| E1 | Core pipeline, queue infrastructure, delivery workers | On-call rotation |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio); cross-channel consistency | Deduplication logic |
| E3 | Preference management, user-facing API, suppression, SMS rate limiter | On-call rotation |
| E4 | Reliability, monitoring, failure handling, infrastructure | On-call rotation |

**Cross-channel consistency is explicitly assigned to E2.** The failure mode — a user receiving duplicate notifications across channels due to in-flight preference updates — needs an owner, not just a policy. E2 owns the deduplication implementation described in Section 5.

**On QA:** No dedicated QA is feasible in this timeline. We address this not by accepting the risk silently but by investing 15% of engineering time in a notification-specific test harness that covers the enumerable failure classes: duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors, and broken unsubscribe links. This is cheaper than debugging production incidents.

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
  - Preference check (Redis cache, 60s TTL)
  - Suppression + deduplication check
  - Priority assignment
  - Channel selection
     │
     ├──────────────────────────────────────┐
     ▼                                      ▼
[Durable Priority Queues]           [In-App Store]
  (Amazon SQS)                       (PostgreSQL, hash-partitioned)
     │
     ├── notif-p0.fifo → 15 workers
     ├── notif-p1.fifo → 25 workers
     ├── notif-p2      → 20 workers
     └── notif-p3      →  5 workers
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log]          [Feedback Processor]
   (PostgreSQL + S3)       (bounces, opens, failures,
                            token invalidation)
```

### 2.2 Queue Backend: Amazon SQS, Not Redis Sorted Set

The intuitive choice is a Redis Sorted Set — compact, fast, priority-native. We reject it for P0/P1 traffic for two reasons that are not fixable without changing the approach.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between `zadd` and the payload `setex`, or between dequeue and delivery, loses notifications silently. For OTPs and security alerts, silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput significantly and requires a replication topology we'd need to operate ourselves.

**Problem 2 — Dequeue atomicity.** A `ZRANGE` + `ZREM` pipeline is not atomic — two concurrent workers will dequeue overlapping items. The correct fix is a Lua script, which adds operational complexity (scripts must be managed, tested, and reloaded after failover) without solving the durability problem.

**Our choice: Amazon SQS with four separate queues.**

```
notif-p0.fifo   — Critical (security alerts, OTPs)
notif-p1.fifo   — High (DMs, mentions)
notif-p2        — Normal (likes, follows) — standard queue
notif-p3        — Batch (digests, re-engagement)
```

SQS provides at-least-once delivery with visibility timeouts, durable storage across availability zones, and correct concurrent dequeue semantics — without us operating anything. FIFO queues for P0/P1 guarantee ordering and exactly-once processing within a message group, which matters for OTPs and DMs. Standard queues for P2/P3 have higher throughput and lower cost, which is appropriate for likes and digests.

**Tradeoff we're accepting:** Four queues means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept it because the durability and correctness guarantees are non-negotiable for P0 traffic, and SQS's managed operations are less work than operating Redis with AOF replication ourselves.

**Cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately **$1,800/month**.

**Where Redis is still used:** Preference caching (60s TTL), unread counts (30s TTL), aggregation windows, rate limiting counters, and WebSocket pub/sub for in-app real-time delivery. Redis is excellent for these use cases — low-latency reads with acceptable loss tolerance. It is not appropriate as the authoritative queue for durable delivery.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~90M/day)

**Provider:** FCM (Android) and APNs (iOS) directly. No intermediary like OneSignal or Braze. Reason: intermediaries cost $50–150K/year at our scale and reduce control over retry behavior and delivery receipts. We accept the upfront integration cost and revisit if we need advanced segmentation.

**APNs JWT — implementation note:**

Two distinct concepts are often conflated:
- **Signing key (.p8 file):** Rotated manually, only when compromised or per security policy. Stored in AWS Secrets Manager, never on disk.
- **JWT token:** Generated from the signing key. Apple requires tokens be regenerated before expiry. Recommended refresh: every 50 minutes (conservative buffer before the 60-minute expiry).

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: str):
        self.key_id = key_id
        self.team_id = team_id
        self.private_key = private_key
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            age = time.time() - self._token_generated_at
            if self._token is None or age > 3000:  # 50 minutes
                self._token = self._generate_jwt()
                self._token_generated_at = time.time()
            return self._token

    def _generate_jwt(self) -> str:
        payload = {"iss": self.team_id, "iat": int(time.time())}
        return jwt.encode(
            payload,
            self.private_key,
            algorithm="ES256",
            headers={"kid": self.key_id}
        )
```

When a token is within 5 minutes of its refresh threshold, the manager proactively regenerates before any P0 batch begins. Workers check token age before acquiring a connection from the pool, preventing mid-send expiry on critical notifications.

**Connection pools and send configuration:**

```
FCM:
  - 50 persistent HTTP/2 connections
  - Batch size: 500 tokens per request
  - Max rate: 400 req/sec (FCM limit is 600; we maintain headroom)

APNs:
  - 20 persistent HTTP/2 connections per worker node
  - Priority header: 10 (immediate) for P0/P1; 5 (power-saving) for P2
  - Collapse ID: {notification_type}:{entity_id}
    Suppresses stale notifications of the same type on the same entity
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

```sql
CREATE TABLE push_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    platform            VARCHAR(8) NOT NULL CHECK (platform IN ('ios', 'android')),
    token               TEXT NOT NULL,
    is_valid            BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    invalidated_at      TIMESTAMPTZ,
    invalidation_reason TEXT,
    UNIQUE (platform, token)
);
```

On FCM `InvalidRegistration` or APNs 410: set `is_valid = false`, record reason, never retry that token. On APNs 410, record the timestamp Apple provides — tokens registered after that timestamp on the same device are valid. Batch-purge tokens unused for 90 days.

### 3.2 Email (~4M/day)

**Provider:** SendGrid Pro (~$1,500/month). The deliverability tooling, suppression list management, and webhook reliability justify the cost premium over AWS SES for a team of 4.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Dedicated IP warming:** Two pools — transactional and marketing — warmed separately over the first 4 weeks. Transactional warms first; marketing sends do not go out until week 3. SPF, DKIM, and DMARC configured on day 1.

**Template system:** SendGrid Dynamic Templates with Handlebars, versioned in Git, deployed via CI/CD. Template changes require review and a staging send to a seed list before production.

**Digest batching — with bounded carry-forward:**

A naive carry-forward implementation accumulates events indefinitely for low-activity users and has undefined behavior on unsubscribe. The correct implementation bounds staleness and handles unsubscribe explicitly:

```python
MAX_CARRY_FORWARD_DAYS = 3
MIN_DIGEST_ITEMS = 3

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    events = fetch_unbatched_events(user_id, date)
    carried = fetch_carried_forward_events(user_id)
    all_events = carried + events

    if not all_events:
        return None

    grouped = group_by_entity_and_type(all_events)

    # Force send if oldest carried event exceeds staleness limit
    oldest_carried = min((e.created_at for e in carried), default=None)
    staleness_forced = (
        oldest_carried is not None and
        (date - oldest_carried.date()).days >= MAX_CARRY_FORWARD_DAYS
    )

    if len(grouped) < MIN_DIGEST_ITEMS and not staleness_forced:
        mark_carried_forward(events)
        expire_stale_carried_events(user_id, MAX_CARRY_FORWARD_DAYS)
        return None

    mark_all_as_batched(all_events)
    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )

def handle_unsubscribe(user_id: str):
    # Expire carried events immediately — they exist as in-app notifications
    # and will not be held indefinitely against a user who has unsubscribed
    expire_all_carried_events(user_id)
    update_preference(user_id, channel="email", enabled=False)
```

**Deliverability targets:** Bounce rate <2%, spam rate <0.1%. If either threshold is breached, an automated alert fires and marketing sends pause pending review.

### 3.3 In-App Notifications (~30M/day)

**Storage: PostgreSQL, partitioned by user_id hash.**

The intuitive partitioning strategy is by `created_at` (time-based). This is wrong for this access pattern. In PostgreSQL declarative partitioning, indexes are local to each partition. A query for a user's unread notifications spanning two months requires scanning both monthly partitions — PostgreSQL will use partition pruning only if the query includes a `created_at` filter, which "show me all unread" does not provide.

The correct strategy is **hash partitioning by `user_id`**, which co-locates all of a user's notifications in one partition and makes user-scoped queries partition-local:

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
    is_