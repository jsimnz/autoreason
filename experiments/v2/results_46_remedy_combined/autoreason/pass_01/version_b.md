# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling **100-250M notifications/day** across push, email, in-app, and SMS channels. The previous version contained a material error in volume estimation, a durability gap in the queue design, and several implementation-level correctness bugs. This revision corrects all of them and is explicit about the tradeoffs introduced by doing so.

The core architectural bets remain: a priority queue with channel fanout, proven managed infrastructure over custom components, and incremental delivery. What changes: the queue is now durable with explicit persistence guarantees, SMS is treated as a cost-controlled exception rather than a default channel, and the specific failure modes identified in review are addressed with concrete mitigations rather than deferred to operations.

---

## 1. Scale Assumptions and Constraints

### 1.1 Corrected Traffic Model

The previous version used DAU (3M) as the multiplier for notification volume. This was wrong. Notifications are sent to opted-in users regardless of whether they opened the app that day — that's the entire point of push and email. The correct multiplier is the opted-in subscriber base.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| Push opt-in rate | 60% | ~6M users; iOS ~50%, Android ~70% |
| Email opt-in rate | 75% | ~7.5M users; most register with email |
| SMS opt-in rate | 15% | ~1.5M users; high-friction opt-in by design |
| Avg notifications/opted-in user/day | ~15 | Industry range: 10–20 for active social apps |
| **Total push/day** | **~90M** | 6M × 15 |
| **Total email/day** | **~4M** | Digest/batch model limits raw volume |
| **Total in-app/day** | **~30M** | Logged-in sessions only; ~3M DAU × 10 |
| **Total SMS/day** | **~150K** | Hard-gated; see Section 3.4 |
| **Total notifications/day** | **~125M** | Central estimate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | **~4,300/sec** | 125M × 3 / 86,400 |

**Compared to previous version:** Volume is roughly 2.5× higher than previously estimated. This changes infrastructure sizing but not architectural approach — the single-queue design still handles this throughput. What it changes concretely: worker pool sizes, Redis memory allocation, and PostgreSQL write capacity for in-app storage.

**Acknowledged uncertainty:** The 15 notifications/user/day figure is an estimate. We instrument actual send rates from week 1 and have a defined scaling trigger: if sustained peak throughput exceeds 8,000/sec, we add worker capacity and evaluate queue backend. We do not wait for an incident.

### 1.2 SMS Cost Correction

The previous version estimated SMS at "$7,500/day." The correct figure at Twilio standard rates ($0.0079/message) for 1M messages/day is **~$7,900/day, or ~$2.9M/year**. This is not a footnote — it is a budget line that requires explicit authorization.

Our revised approach: SMS volume is hard-capped at **150K messages/day**, not 1M. This reduces SMS cost to approximately **$430K/year** — still significant, but defensible for authentication and security use cases. The cap is enforced in code, not policy. If the cap is reached, non-auth SMS is queued to the next day; auth SMS (OTPs) is exempt from the cap but tracked separately.

**Budget owner:** E3 owns the SMS rate limiter. The cap threshold is a configuration value requiring VP-level approval to change. Monthly SMS spend is reported in the engineering dashboard.

### 1.3 Team Allocation

| Engineer | Primary Responsibility | Secondary |
|----------|----------------------|-----------|
| E1 | Core pipeline, queue infrastructure, delivery workers | On-call rotation |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Cross-channel consistency |
| E3 | Preference management, user API, suppression, SMS rate limiting | On-call rotation |
| E4 | Reliability, monitoring, failure handling, infrastructure | On-call rotation |

**Cross-channel consistency is explicitly assigned to E2.** The previous version had no owner for the scenario where a user receives duplicate notifications across channels due to in-flight preference updates. This is now E2's responsibility, with a specific implementation described in Section 5.

**On QA:** The previous proposal accepted "no dedicated QA" as a risk. This is more precisely described as a guarantee of specific, enumerable failure modes: duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors, and broken unsubscribe links. We address this not by hiring QA (not feasible in timeline) but by investing 15% of engineering time in a notification-specific test harness that systematically covers these failure classes. See Section 7.

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
  - Preference check (Redis cache, 60s TTL — see Section 5)
  - Suppression check
  - Deduplication check
  - Priority assignment
  - Channel selection
     │
     ├────────────────────────────────────────┐
     ▼                                        ▼
[Durable Priority Queue]              [In-App Store]
  (Amazon SQS — see Section 2.2)       (PostgreSQL, partitioned)
     │
     ├── P0 Queue → Worker Pool (15 workers)
     ├── P1 Queue → Worker Pool (25 workers)
     ├── P2 Queue → Worker Pool (20 workers)
     └── P3 Queue → Worker Pool (5 workers)
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

### 2.2 Queue Backend: Moving from Redis Sorted Set to Amazon SQS

The previous version used a Redis Sorted Set as the queue backend. This introduced two problems that are not fixable without changing the approach:

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between `zadd` and the payload `setex`, or between dequeue and delivery, loses notifications silently. For P0 notifications (OTPs, security alerts), silent loss is unacceptable. We could configure Redis with AOF persistence (`appendfsync always`), but this degrades write throughput significantly and requires a replication topology we'd need to operate ourselves.

**Problem 2 — The dequeue race condition.** The previous code used a Redis pipeline for the `zrange + zrem` operation and incorrectly claimed this was atomic. A pipeline batches commands but does not provide atomicity — two workers executing simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity (Lua scripts must be managed, tested, and reloaded after failover).

**Our choice: Amazon SQS with four separate queues (P0–P3).**

This is a deliberate reversal from the "single queue" bet in the previous version. The reason: SQS provides at-least-once delivery with visibility timeouts, durable storage across availability zones, and correct concurrent dequeue semantics — all without us operating anything. The cost is per-channel priority queues instead of a single sorted structure.

```
Queues:
  notif-p0.fifo   — Critical (security, OTP)
  notif-p1.fifo   — High (DMs, mentions)
  notif-p2        — Normal (likes, follows) — standard queue, not FIFO
  notif-p3        — Batch (digests, re-engagement)

Worker allocation:
  P0: 15 workers polling notif-p0 exclusively
  P1: 25 workers polling notif-p1 exclusively
  P2: 20 workers polling notif-p2
  P3: 5 workers polling notif-p3
```

**Why FIFO for P0/P1 but not P2/P3:** FIFO queues guarantee ordering and exactly-once processing within a message group, which matters for OTPs and DMs. Standard queues have higher throughput and lower cost, which is fine for likes and digests where ordering and deduplication are less critical.

**Tradeoff we're accepting:** Four queues means four sets of dead-letter queues to monitor and four sets of CloudWatch alarms to configure. This is more operational surface than one Redis sorted set. We accept this because the durability and correctness guarantees are non-negotiable for P0 traffic, and SQS's managed operations are less work than operating Redis with AOF replication ourselves.

**SQS cost at our scale:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately **$1,800/month** — acceptable.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~90M/day)

**Provider:** FCM (Android) and APNs (iOS) directly. No intermediary.

**APNs JWT implementation — corrected:**

The previous version stated "rotate keys every 55 min," conflating two distinct concepts:

- **Signing key (.p8 file):** Rotated manually, only when compromised or per security policy. Not on a timer. Stored in AWS Secrets Manager, not on disk.
- **JWT token:** Generated from the signing key. Apple requires tokens be regenerated before they expire (recommended: every 55 minutes). This is a software operation, not a key rotation.

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
            # Regenerate if older than 50 minutes (conservative buffer before 60-min expiry)
            if self._token is None or age > 3000:
                self._token = self._generate_jwt()
                self._token_generated_at = time.time()
            return self._token

    def _generate_jwt(self) -> str:
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

**Handling token refresh during in-flight P0 sends:** When a JWT token is within 5 minutes of its 50-minute refresh threshold, the token manager proactively generates a new token before any P0 batch begins. Workers check token age before acquiring a connection from the pool. This avoids the scenario where a P0 notification is mid-send when a token expires.

**FCM and APNs connection pools:**

```
FCM:
  - 50 persistent HTTP/2 connections
  - Batch size: 500 tokens per request
  - Max send rate: 400 req/sec (FCM limit: 600; we maintain headroom)

APNs:
  - 20 persistent HTTP/2 connections per worker node
  - Priority header: 10 (immediate) for P0/P1; 5 (power-saving) for P2
  - Collapse ID: {notification_type}:{entity_id} — suppresses stale
    notifications of the same type on the same entity
```

**Token management:**

```sql
CREATE TABLE push_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    platform        VARCHAR(8) NOT NULL CHECK (platform IN ('ios', 'android')),
    token           TEXT NOT NULL,
    is_valid        BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    invalidated_at  TIMESTAMPTZ,
    invalidation_reason TEXT,
    UNIQUE (platform, token)
);
```

On FCM `InvalidRegistration` or APNs 410: set `is_valid = false`, record reason, never retry. On APNs 410, record the timestamp Apple provides; tokens registered after that timestamp on the same device are valid.

### 3.2 Email (~4M/day)

**Provider:** SendGrid Pro. The deliverability tooling, suppression list management, and webhook reliability justify the cost premium over AWS SES for a team of 4.

**Dedicated IP warming:** Two IP pools — transactional and marketing — warmed separately over the first 4 weeks. Warm transactional first; marketing emails do not send until week 3.

**Template versioning:** SendGrid Dynamic Templates, managed in Git, deployed via CI/CD. Template changes require review and a staging send to a seed list before production.

**Digest batching — corrected carry-forward logic:**

The previous version had `carry_forward_to_next_digest()` with no defined maximum age. A user generating fewer than 3 notable events per day would never receive a digest — their notifications would accumulate indefinitely, and if they unsubscribed, those carried-forward events would have undefined behavior.

```python
MAX_CARRY_FORWARD_DAYS = 3

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    events = fetch_unbatched_events(user_id, date)
    carried = fetch_carried_forward_events(user_id)
    all_events = carried + events

    if len(all_events) == 0:
        return None

    grouped = group_by_entity_and_type(all_events)

    # Check if any carried events have hit the staleness limit
    oldest_carried = min((e.created_at for e in carried), default=None)
    staleness_forced = (
        oldest_carried is not None and
        (date - oldest_carried.date()).days >= MAX_CARRY_FORWARD_DAYS
    )

    if len(grouped) < MIN_DIGEST_ITEMS and not staleness_forced:
        # Carry forward, but only events within the staleness window
        mark_carried_forward(events)
        expire_stale_carried_events(user_id, MAX_CARRY_FORWARD_DAYS)
        return None

    # Either enough items, or forced by staleness — send what we have
    mark_all_as_batched(all_events)
    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )

def handle_unsubscribe(user_id: str):
    # On unsubscribe: expire all carried-forward events immediately
    # They will not be sent; they are not lost — they exist as in-app notifications
    expire_all_carried_events(user_id)
    update_preference(user_id, channel="email", enabled=False)
```

**Deliverability targets:** Bounce rate <2%, spam rate <0.1%. If either is breached, automated alert fires and marketing sends pause pending review.

### 3.3 In-App Notifications (~30M/day)

**Storage: PostgreSQL with corrected partitioning strategy**

The previous version partitioned by `created_at` and defined a `(user_id, created_at DESC)` index, then claimed this solved cross-partition query performance. It does not. In PostgreSQL declarative partitioning, indexes are local to each partition. A query for a user's unread notifications spanning 2 months requires scanning both monthly partitions with their local indexes — PostgreSQL will use partition pruning only if the query includes a `created_at` filter, which a "show me all unread" query does not.

**Revised approach: partition by `user_id` hash, not by time.**

```sql
CREATE TABLE notifications (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,