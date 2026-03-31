# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3 — Addressing Implementation and Correctness Gaps

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural commitments remain: SQS-backed priority queues, direct channel integrations, and PostgreSQL as the system of record. Revision 3 corrects ten specific problems identified in review: a throughput mischaracterization in the SQS FIFO design, a deduplication logic bug for OTPs, a silent failure mode for P0 push delivery, stale badge counts, unbounded state in digest carry-forward, a single point of failure in team allocation, unacknowledged compliance implications of log deletion, a safety gap in preference cache TTL, an unverifiable FCM rate limit claim, and a collapse-id strategy that contradicts server-side aggregation. Each fix is described at the point of the original decision, with the tradeoff made explicit.

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
| SMS (2%) | 1M/day | Auth and security events only |

SMS volume is driven by auth and security event rates, not a percentage of total notification volume. We budget 100K SMS/day and set a hard system-level cap with alerting at 150K/day.

### Team Allocation

The previous revision assigned all four channel integrations (APNs, FCM, SendGrid, Twilio) to a single engineer (E2). A reviewer correctly identified this as a single point of failure on the critical path: one departure or extended absence stalls the entire delivery layer during the most complex phase of the project.

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary (Cross-trained) |
|----------|----------------------|--------------------------|
| E1 | Core pipeline, SQS queue infrastructure, delivery workers | Push channel integrations |
| E2 | Push integrations (APNs, FCM), token management | Core pipeline |
| E3 | Preference management, user-facing API, suppression logic | Email/SMS integrations |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | Preference API |

The split: E2 owns push (the dominant channel, 70% of volume, highest technical complexity). E4 owns email and SMS alongside reliability work — these integrations are operationally simpler and more stable than push, making them compatible with E4's reliability responsibilities. E1 is cross-trained on push so E2's absence does not halt that workstream. E3 is cross-trained on email/SMS so E4's absence does not halt those integrations.

This does not eliminate the risk of a departure — a 4-person team cannot fully absorb losing a member without schedule impact. It means no single departure makes an entire delivery channel unshippable.

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
  - Preference check (Redis cache, tiered TTL — see Section 5)
  - Suppression check
  - Priority assignment
  - Channel selection
  - Aggregation window check
     │
     ├─────────────────────────────────────────────────┐
     ▼                                                 ▼
[SQS Priority Queues]                        [In-App Store]
  - p0-notifications.fifo                    (PostgreSQL,
  - p1-notifications.fifo                     partitioned)
  - p2-notifications.fifo
  - p3-notifications (standard)
     │
     ├── P0 Worker Pool (10 workers)
     ├── P1 Worker Pool (20 workers)
     └── P2/P3 Worker Pool (10 workers)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
          │
          ▼
   [Delivery Log]
   (PostgreSQL, retention per compliance policy — see Section 6)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, delivery failures)
```

### SQS FIFO: Message Group ID Strategy and Throughput Reality

**The problem with the previous revision:** It claimed SQS FIFO queues support 3,000 messages/sec and treated this as comfortable headroom over a 1,750/sec peak. This was misleading. The 3,000 messages/sec figure is a per-queue aggregate limit achievable only with high-throughput mode enabled. More importantly, FIFO ordering guarantees apply *per message group* — messages within the same group are processed in order, but groups are processed in parallel. If you assign all messages to a single group ID, you get strict ordering but serialized throughput — effectively one message at a time per consumer. If you assign each message to its own group ID, you get maximum parallelism but no cross-message ordering. The two goals are in direct tension and the previous revision never resolved it.

**Our resolution:** We do not need cross-user ordering guarantees. The requirement is that a P0 notification is not delayed behind a P2 backlog — that is solved by separate queues per priority tier, not by ordering within a queue. Within a priority tier, there is no correctness requirement that user A's notification be delivered before user B's.

Given this, we assign message group IDs as follows:

```
group_id = user_id % 100  # 100 groups per queue
```

This gives us 100 parallel processing groups per queue, sufficient parallelism for our throughput requirements, and weak per-user ordering within a group (notifications for the same user tend to land in the same group, reducing reordering). It is not a strict per-user ordering guarantee — we do not need one. A user receiving a "like" notification 200ms before a "follow" notification when they were enqueued in the opposite order is acceptable.

**Throughput math with this design:**

With 100 message groups and high-throughput mode enabled, SQS FIFO supports up to 3,000 messages/sec aggregate per queue. Our peak is 1,750/sec across all queues, with push at roughly 1,225/sec (70%). The P1 queue handles the majority of push volume. At 1,225/sec against a 3,000/sec limit with 100 groups, we have real headroom. If we approach the limit — a viral event, a major sports result triggering millions of activity notifications — we add a second P1 FIFO queue and route by `user_id % 2`. This is an operational runbook item, not a code change.

**What we give up:** Strict per-user delivery ordering within a priority tier. We accept this. The alternative — per-user group IDs — gives us ordering but caps aggregate throughput at (number of active users at peak) × (per-group rate), which is not a useful bound and would require constant queue sharding as we grow.

### Deduplication: Separating OTP Logic from General Deduplication

**The bug in the previous revision:** The deduplication key `(user_id, notification_type, entity_id, 5-minute window)` creates a correctness problem for OTPs. If `entity_id` is stable across a resend (same session, same login attempt), the second OTP send within 5 minutes is silently deduplicated and never delivered. If `entity_id` is unique per OTP generation (a new UUID each time), the dedup window provides no protection against duplicates at all for this notification type. The previous design cannot be both correct and useful for OTPs simultaneously.

**Resolution:** OTPs are not routed through the general notification pipeline at all.

OTPs have requirements that are incompatible with the general notification system: they must be delivered exactly once per generation event, they have their own expiry managed by the auth service, and "deduplication" for an OTP means preventing duplicate delivery of the *same OTP*, not suppressing a second OTP when the user requests one. These semantics cannot be expressed in a window-based dedup key.

```
OTP and Auth Code Flow (separate from notification pipeline):

Auth Service
    │
    ├── Generates OTP, stores in Redis with TTL matching OTP validity
    │
    └── Calls SMS/Push OTP Service directly
            │
            ├── Assigns unique delivery_id = uuid4()
            ├── Writes delivery_id to Redis: SET otp_delivery:{delivery_id} "pending" EX 300
            ├── Sends via Twilio (SMS) or APNs/FCM (push)
            └── On success: SET otp_delivery:{delivery_id} "delivered"
                On failure: retry with same delivery_id, Twilio/APNs idempotency key
```

The OTP service uses the `delivery_id` as an idempotency key with Twilio and as the APNs `apns-id` header. Retries of the same OTP send use the same `delivery_id` — the downstream provider deduplicates. A new OTP generation creates a new `delivery_id` and is treated as a distinct send.

**General notification deduplication (non-OTP):**

```
dedup_key = hash(user_id, notification_type, entity_id, floor(timestamp / 300))
```

This applies to social notifications (likes, follows, comments, mentions). The semantics are: "don't send two 'Alice liked your post' notifications for the same post within the same 5-minute window." This is correct for these types — there is no meaningful distinction between a "resend" and a duplicate for a like notification. The dedup window is a UX concern, not a correctness concern.

The dedup check happens at two points:

1. **Router layer:** Check Redis key `dedup:{dedup_key}` before enqueuing. If present, discard. If absent, set with 5-minute TTL and enqueue.
2. **Worker layer:** Check Redis key `sent:{notification_id}` before dispatching to channel. If present, discard (handles at-least-once redelivery from SQS). If absent, set with 24-hour TTL and dispatch.

The two layers catch different failure modes: the first catches duplicate events from upstream; the second catches SQS redelivery after a worker crash mid-dispatch.

---

## 3. Delivery Channels

### 3.1 Push Notifications (35M/day)

#### P0 Expiration and the Silent Delivery Failure Problem

**The problem in the previous revision:** P0 notifications were given `apns-expiration: 300s`. OTPs are now handled outside this pipeline (see Section 2), but P0 still includes security alerts: "your account was accessed from a new device," "your password was changed," "suspicious login detected." A 5-minute APNs expiration means a user with a dead battery or in airplane mode for 6 minutes never receives a security alert about their own account. There is no fallback described. This is not a theoretical edge case — it is the normal behavior for any user who is briefly offline.

**Resolution:**

First, security alerts are not time-bounded the way OTPs are. An APNs expiration of 300 seconds was borrowed from OTP logic and is wrong for security alerts. Security alerts should be stored and delivered when the device comes online. We set:

```
apns-expiration for P0 security alerts: NOW + 24 hours
apns-expiration for P0 OTPs: N/A (OTPs are not in this pipeline)
```

Second, the delivery model for security alerts is: push is the first attempt, in-app is the guaranteed backstop. All P0 security alerts are written to the in-app notification store at the time of routing, before the push is dispatched. If push fails (device offline, token invalid, APNs error), the user sees the alert the next time they open the app. This is not a degraded experience — it is the intended behavior for security information.

Third, for the most critical security alerts (account takeover indicators), the router also enqueues an email via the P0 queue. Push + email + in-app for a "new device login" alert means the user receives it through whichever channel they engage with first.

```
P0 Security Alert Delivery Policy:
  1. Write to in-app store (synchronous, before anything else)
  2. Enqueue push (APNs expiration: 24h, FCM TTL: 86400)
  3. Enqueue email (for account takeover class alerts only)
  4. If push fails with UNREGISTERED/invalid token: in-app is the delivery
  5. If push succeeds: mark in-app notification as "also push-delivered"
```

#### FCM Rate Limits: What We Actually Know

**The problem in the previous revision:** The proposal stated "FCM allows ~600 req/sec per project" as a design input for connection pool sizing. FCM does not publish this limit publicly. The actual per-project quota depends on the Firebase project tier, whether a quota increase has been requested, and the specific API version. Building a connection pool around an undocumented number is an operational risk at 35M push/day.

**Resolution:** We do not design around an assumed rate limit. We design for graceful degradation when we hit whatever limit exists.

```python
class FCMDispatcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(200)  # Conservative starting concurrency
        self._rate_limiter = TokenBucketRateLimiter(
            initial_rate=300,   # req/sec — conservative starting point
            max_rate=1000,      # upper bound we'll increase toward empirically
            min_rate=50,        # floor during backoff
        )
        self._consecutive_429s = 0

    async def send(self, token: str, payload: dict) -> FCMResult:
        await self._rate_limiter.acquire()
        async with self._semaphore:
            try:
                result = await self._do_send(token, payload)
                self._consecutive_429s = 0
                return result
            except FCMRateLimitError as e:
                self._consecutive_429s += 1
                # Respect Retry-After header if present, else exponential backoff
                retry_after = e.retry_after or (2 ** min(self._consecutive_429s, 6))
                await self._rate_limiter.reduce_rate(factor=0.5)
                await asyncio.sleep(retry_after)
                raise  # Re-raise for worker retry logic
```

**Empirical rate limit discovery process:** In the first week of production, we ramp concurrency from 50 to 500 in-flight requests in steps of 50, with a 15-minute hold at each step, monitoring for 429 responses. We set our operational rate limit at 80% of the empirically discovered threshold. This is documented in the runbook as a required step before full traffic cut-over, not something we discover during an incident.

We also contact Firebase support before launch to request a quota increase appropriate for our volume. This is a documented step in the project timeline (Month 1, Week 3).

#### APNs JWT Token Management

```python
class APNsTokenManager:
    """
    Centralized JWT token manager shared across all APNs connections.
    Refreshes proactively at 50 minutes to avoid expiry during a request.
    APNs enforces a hard 1-hour token expiry.
    """
    def __init__(self, key_id: str, team_id: str, private_key: bytes):
        self._key_id = key_id
        self._team_id = team_id
        self._private_key = private_key
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        # Fast path: token is fresh (under 50 minutes old)
        if self._token and (time.time() - self._token_generated_at) < 3000:
            return self._token

        async with self._lock:
            if self._token and (time