# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural and Correctness Issues

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The previous version made several architectural choices that were either incorrect (the dequeue atomicity bug), internally inconsistent (the SMS volume math), or underspecified to the point of being unimplementable (digest carry-forward, WebSocket capacity, hardening phase).

This revision corrects those problems directly. The major changes:

1. **Per-channel queues replace the single priority queue.** The failure isolation argument is correct — a single queue with channel fanout means an FCM rate limit can starve SMS delivery. We pay the monitoring overhead (four queues vs. one) and accept that it's worth it.

2. **The dequeue Lua script is shown correctly.** The previous pipeline was not atomic. This revision shows the actual Lua implementation.

3. **SMS volume is reconciled with use case restrictions.** 1M/day was inconsistent with "gated premium channel." We specify the realistic volume and its cost implications.

4. **Digest carry-forward is fully specified** with TTL, storage, and edge case handling.

5. **WebSocket capacity is modeled explicitly** with instance counts and failure behavior.

6. **APNs JWT handling is corrected.** The p8 key vs. JWT token distinction is clarified.

7. **Preference cache invalidation is specified** with TTL, write-through strategy, and invalidation on change.

8. **Month 6 hardening is defined** with entry criteria, work items, and exit criteria.

9. **Feedback processor reliability** is given explicit latency targets and failure handling.

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
| SMS (<0.3%) | ~75K/day | Auth and security only — see Section 3.4 |

**On SMS volume:** The previous version estimated 1M SMS/day and simultaneously described SMS as a gated premium channel limited to OTP and security alerts. These are irreconcilable. For 10M MAU with 30% DAU, 1M SMS/day implies every active user receives one SMS per day — inconsistent with "security alerts only." The realistic estimate is ~75K/day: assume 1% of DAU triggers an auth or security SMS event on any given day (login from new device, password reset, 2FA enrollment). 75K × $0.0075 = $562/day, or ~$205K/year. This is significant but defensible for a privileged channel. We will instrument actual volume from day one and revisit if the 1% trigger rate assumption is wrong.

### Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given timeline, partially mitigated by the phased delivery schedule.

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
  - Preference check (Redis cache, write-through)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├──────────────────────────────────────────────┐
     │                                              │
     ├─→ [Push Queue]     (Redis Sorted Set)        │
     ├─→ [Email Queue]    (Redis Sorted Set)        │
     ├─→ [SMS Queue]      (Redis Sorted Set)        │
     └─→ [In-App Store]   (PostgreSQL — no queue)  │
                                                    │
     [Push Workers]    → APNs / FCM                │
     [Email Workers]   → SendGrid                  │
     [SMS Workers]     → Twilio                    │
                                                    │
     [Delivery Log]    (PostgreSQL + S3 archive)   │
                                                    │
     [Feedback Processor]                          ◄┘
     (bounces, opens, failures → suppression list)
```

### Why Per-Channel Queues, Not a Single Queue

The previous version argued that a single queue was simpler to operate. The criticism was correct to reject this. The actual failure mode matters:

**Single queue failure scenario:** FCM begins rate-limiting at 3pm due to a spike. The push queue backs up. Because email and SMS notifications share the same queue, P0 SMS messages (OTPs) are now queued behind thousands of stalled push notifications. A user trying to log in with 2FA waits 4 minutes for their OTP. This is a user-facing correctness failure, not just a performance degradation.

**Per-channel queue failure scenario:** FCM rate-limits. The push queue backs up. Email and SMS queues are unaffected. The push queue's backlog is visible in isolation. The on-call engineer can shed P2 push notifications to reduce the backlog without touching other channels.

The operational overhead of monitoring four queues instead of one is real but small: four dashboards, four dead-letter queues, four alerting rules. We accept this cost for the failure isolation it provides.

**In-app notifications bypass all queues.** In-app notifications are direct writes to PostgreSQL. They're cheap, don't need retry logic, and benefit from immediate consistency. Queue overhead adds latency with no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** FCM (Android) and APNs (iOS) via direct API integration. No intermediary (OneSignal, Braze) in v1. Rationale: intermediaries cost $50–150K/year at this scale and reduce control over retry behavior and delivery receipts. We accept the 4–6 week integration cost.

**FCM Configuration:**
```
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we operate at 400 with headroom
- Token validation: validate on first send failure, purge on 404/InvalidRegistration
```

**APNs Configuration and JWT Handling:**

The previous version stated that "JWT keys rotate every 55 minutes." This was incorrect and conflated two distinct concepts:

- The **signing key** (the `.p8` file downloaded from Apple Developer portal) does not rotate on a timer. It is rotated manually when revoked or compromised. We store it in AWS Secrets Manager and rotate it as an operational procedure, not automatically.
- The **JWT token** (signed using that key) expires after 60 minutes per APNs documentation. We regenerate the JWT every 55 minutes to avoid sending requests with an expired token.

Correct implementation:

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key_path: str):
        self.key_id = key_id
        self.team_id = team_id
        # Load the .p8 signing key once at startup (or from Secrets Manager)
        self.private_key = load_private_key(private_key_path)
        self._token: str | None = None
        self._token_generated_at: float = 0

    def get_token(self) -> str:
        now = time.time()
        # Regenerate JWT if older than 55 minutes
        if self._token is None or (now - self._token_generated_at) > 3300:
            self._token = self._generate_jwt(now)
            self._token_generated_at = now
        return self._token

    def _generate_jwt(self, now: float) -> str:
        payload = {
            "iss": self.team_id,
            "iat": int(now),
        }
        headers = {
            "alg": "ES256",
            "kid": self.key_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="ES256",
                         headers=headers)
```

The signing key (`.p8`) is the credential that must be protected. The JWT is ephemeral and regenerated from it. E2 should treat these as distinct operational concerns.

**APNs Additional Configuration:**
```
- Connection pool: 20 persistent HTTP/2 connections
- Priority header: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- Collapse key: notification_type + entity_id to suppress stale notifications
- apns-expiration: set to TTL per priority level (P0=300s, P1=3600s, P2=86400s)
```

**Token management:**

Stale push tokens are the primary operational headache at scale:

- Store tokens in `push_tokens` table with `last_used_at`, `is_valid`, `invalidated_reason`
- On FCM `InvalidRegistration` or APNs 410: mark invalid immediately, set `is_valid = false`
- On APNs 410: Apple provides a timestamp; tokens registered *after* that timestamp are valid and should not be purged
- Batch-purge tokens with `is_valid = false` or `last_used_at < NOW() - INTERVAL '90 days'` in a nightly job

### 3.2 Email (8% of volume — 4M/day)

**Provider:** SendGrid Pro (~$1,500/month). AWS SES would be ~$400/day cheaper at this volume but SendGrid's suppression list management, deliverability tooling, and webhook reliability are worth the premium for a 4-engineer team. We revisit at 50M MAU when the cost differential becomes harder to ignore.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars. Templates are versioned in Git and deployed via SendGrid API in CI/CD. This keeps designers out of the codebase while maintaining version control.

**Digest batching and carry-forward logic (fully specified):**

The previous version mentioned `carry_forward_to_next_digest` without defining it. This is the full specification:

```python
@dataclass
class PendingDigestEvent:
    user_id: str
    event_id: str
    event_type: str
    entity_id: str
    actor_id: str
    created_at: datetime
    carry_forward_count: int  # How many digest cycles this has been deferred

# Storage: PostgreSQL table, not Redis — these are durable pending items
# Schema:
# CREATE TABLE pending_digest_events (
#     id              UUID PRIMARY KEY,
#     user_id         UUID NOT NULL,
#     event_type      VARCHAR(64) NOT NULL,
#     entity_id       UUID,
#     actor_id        UUID,
#     payload         JSONB NOT NULL,
#     created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     carry_forward_count INT NOT NULL DEFAULT 0,
#     expires_at      TIMESTAMPTZ NOT NULL,  -- hard TTL
#     INDEX (user_id, created_at)
# );

MIN_DIGEST_ITEMS = 3
MAX_CARRY_FORWARD_CYCLES = 7   # 7 days for daily digest users
DIGEST_EVENT_TTL_DAYS = 14     # Hard expiry regardless of carry-forward count

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    # Fetch all pending events for this user, including carried-forward ones
    events = fetch_pending_digest_events(user_id)

    # Hard expiry: drop events older than TTL regardless of count
    # This is handled by the expires_at column and a nightly cleanup job,
    # but we filter here defensively
    events = [e for e in events if e.expires_at > datetime.utcnow()]

    if len(events) == 0:
        return None

    grouped = group_by_entity_and_type(events)

    if len(grouped) < MIN_DIGEST_ITEMS:
        # Carry forward: increment counter, but only up to the max
        for event in events:
            if event.carry_forward_count >= MAX_CARRY_FORWARD_CYCLES:
                # Force-send regardless of threshold to avoid silent loss
                # This user has had pending events for 7+ days with no digest
                # sent. Force the digest even below threshold.
                return build_digest_regardless_of_threshold(user_id, events)
            else:
                increment_carry_forward_count(event.id)
        return None

    # Mark events as consumed before sending (not after) to avoid
    # double-send if the process crashes between send and mark
    mark_events_consumed(event_ids=[e.event_id for e in events])

    return DigestEmail(
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )
```

**Key decisions made explicit:**
- Carry-forward events are stored in PostgreSQL, not Redis. They are durable state.
- Hard TTL of 14 days: events that haven't been sent in 14 days are dropped by a nightly cleanup job. We log these drops for monitoring.
- After 7 carry-forward cycles, we force-send below threshold rather than silently discard. A user who generates 1–2 events/day for a week should receive a digest even if they never hit 3 grouped events.
- Events are marked consumed *before* the send call to prevent double-send on crash. SendGrid's idempotency key handles the case where the send fails after marking.

**Deliverability:**
- Dedicated IP pool: transactional and marketing on separate pools, warmed separately
- SPF, DKIM, DMARC configured on day 1
- Bounce rate target: <2%; spam rate target: <0.1%
- Suppression list sync: see Section 6 (Feedback Processor)

### 3.3 In-App Notifications (20% of volume — 10M/day)

**Storage:** PostgreSQL with monthly range partitioning on `created_at`. However, the previous version's partitioning design had a critical query performance problem.

**The partitioning problem and fix:**

The primary access pattern is:
```sql
SELECT * FROM notifications
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 20;
```

With range partitioning on `created_at`, PostgreSQL cannot prune partitions using the `user_id` predicate. Every query scans all active partitions. For 900M rows/quarter across three monthly partitions, this is a full multi-partition scan for every user's notification list — unacceptable.

**Correct approach:** Partition by `user_id` hash, not by `created_at`. Use 16 hash partitions (expandable later). Time-based archival is handled separately via a background job that moves rows older than 90 days to an archive table (or S3 via COPY), not via partition dropping.

```sql
-- Parent table
CREATE TABLE notifications (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    type        VARCHAR(64) NOT NULL,
    priority    SMALLINT NOT NULL DEFAULT 1,
    title       TEXT NOT NULL,
    body        TEXT,
    entity_type