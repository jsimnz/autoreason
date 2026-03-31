# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system capable of handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. We will ship a working system in month 2, iterate through month 5, and spend month 6 on hardening.

The core architectural bet: **a durable message queue with channel fanout**, using SQS-backed priority queues. This replaces an earlier Redis Sorted Set design that had an unacceptable durability gap for P0 notifications. The tradeoffs behind every significant decision are stated explicitly.

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
| SMS | 100K/day | Auth and security events only |

SMS volume is driven by auth and security event rates, not a percentage of total notification volume. We budget 100K SMS/day and set a hard system-level cap with alerting at 150K/day. At Twilio's volume pricing (~$0.0075/message), that is ~$750/day — a meaningful cost line, not a rounding error.

These ratios are estimates. We instrument from day one and adjust channel budgets in month 2.

### Team Allocation

The previous revision assigned all four channel integrations (APNs, FCM, SendGrid, Twilio) to a single engineer. That is a single point of failure on the critical path: one departure or extended absence stalls the entire delivery layer during the most complex phase of the project.

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary (Cross-trained) |
|----------|----------------------|--------------------------|
| E1 | Core pipeline, SQS queue infrastructure, delivery workers | Push channel integrations |
| E2 | Push integrations (APNs, FCM), token management | Core pipeline |
| E3 | Preference management, user-facing API, suppression logic | Email/SMS integrations |
| E4 | Email (SendGrid), SMS (Twilio), reliability, monitoring, runbooks | Preference API |

E2 owns push (the dominant channel, 70% of volume, highest technical complexity). E4 owns email and SMS alongside reliability work — these integrations are operationally simpler, making them compatible with E4's reliability responsibilities. E1 is cross-trained on push so E2's absence does not halt that workstream. E3 is cross-trained on email/SMS so E4's absence does not halt those integrations.

This does not eliminate the risk of a departure — a 4-person team cannot fully absorb losing a member without schedule impact. It means no single departure makes an entire delivery channel unshippable.

All engineers rotate on-call. No dedicated QA — engineers own quality.

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

### Why SQS, Not Redis Sorted Set

P0 notifications include security alerts. Redis persistence (AOF/RDB) does not provide the same durability guarantee as a purpose-built message queue. Even with AOF `always` fsync mode, Redis failover involves a replication lag window during which writes are lost — a security alert silently dropped with no retry. For a team of 4 with no dedicated reliability engineer, operating Redis as a durable queue correctly is more operational burden than the simplicity benefit justifies.

SQS FIFO queues give us: at-least-once delivery with deduplication IDs, configurable visibility timeout for in-flight messages, dead-letter queues with no additional infrastructure, and zero operational overhead. The cost at our throughput is negligible (~$50/month).

**Why four queues, not one.** Separate queues by priority tier mean P0 workers are never blocked behind a P2 backlog. With a single queue and priority scores, a thundering herd of P2 notifications during a viral event can delay P0 delivery even with priority-aware dequeue logic. Separate queues make the isolation structural, not algorithmic. The operational cost is four queues to monitor instead of one — acceptable.

### SQS FIFO: Message Group ID Strategy and Throughput

The 3,000 messages/sec aggregate limit on SQS FIFO queues is only achievable with high-throughput mode enabled and requires meaningful parallelism across message groups. FIFO ordering guarantees apply *per message group* — messages within the same group are serialized, groups are processed in parallel. Assigning all messages to a single group gives strict ordering but near-zero throughput. Assigning each message its own group gives maximum parallelism but no ordering. These goals are in direct tension.

**Our resolution:** We do not need cross-user ordering guarantees. The requirement is that P0 notifications are not delayed behind P2 backlogs — solved by separate queues per priority tier, not by intra-queue ordering. Within a priority tier, there is no correctness requirement that user A's notification be delivered before user B's.

```
group_id = user_id % 100  # 100 groups per queue
```

This gives 100 parallel processing groups per queue, sufficient parallelism for our throughput, and weak per-user ordering within a group (a UX nicety, not a requirement). At our peak of ~1,750/sec across all queues, with push at roughly 1,225/sec concentrated in P1, we have real headroom against the 3,000/sec limit. If we approach the limit during a viral event, we add a second P1 FIFO queue and route by `user_id % 2`. This is a runbook item, not a code change.

**What we give up:** Strict per-user delivery ordering within a priority tier. We accept this.

### Deduplication: Separating OTP Logic from General Notifications

A window-based dedup key of `(user_id, notification_type, entity_id, 5-minute window)` creates a correctness problem for OTPs. If `entity_id` is stable across a resend, the second OTP within 5 minutes is silently dropped. If `entity_id` is unique per generation, the dedup window provides no protection against duplicates. The design cannot be both correct and useful for OTPs simultaneously.

**Resolution:** OTPs are not routed through the general notification pipeline.

OTPs must be delivered exactly once per generation event, have their own expiry managed by the auth service, and "deduplication" means preventing duplicate delivery of the *same* OTP — not suppressing a second OTP when the user requests a resend. These semantics cannot be expressed in a window-based dedup key.

```
OTP and Auth Code Flow (separate from notification pipeline):

Auth Service
    │
    ├── Generates OTP, stores in Redis with TTL matching OTP validity
    │
    └── Calls SMS/Push OTP Service directly
            │
            ├── Assigns unique delivery_id = uuid4()
            ├── Writes: SET otp_delivery:{delivery_id} "pending" EX 300
            ├── Sends via Twilio (SMS) or APNs/FCM (push)
            └── On success: SET otp_delivery:{delivery_id} "delivered"
                On failure: retry with same delivery_id (provider idempotency key)
```

A new OTP generation creates a new `delivery_id` and is treated as a distinct send. Retries of the same send use the same `delivery_id` — the downstream provider deduplicates.

**General notification deduplication (non-OTP):**

```
dedup_key = hash(user_id, notification_type, entity_id, floor(timestamp / 300))
```

This applies to social notifications (likes, follows, comments, mentions). The semantics are: don't send two "Alice liked your post" notifications for the same post within the same 5-minute window. This is a UX concern, not a correctness concern — appropriate for a window-based key.

The dedup check happens at two points:

1. **Router layer:** Check Redis key `dedup:{dedup_key}` before enqueuing. If present, discard. If absent, set with 5-minute TTL and enqueue.
2. **Worker layer:** Check Redis key `sent:{notification_id}` before dispatching to channel. If present, discard (handles SQS at-least-once redelivery after worker crash). If absent, set with 24-hour TTL and dispatch.

The two layers catch different failure modes: the first catches duplicate events from upstream; the second catches SQS redelivery after a worker crash mid-dispatch.

---

## 3. Delivery Channels

### 3.1 Push Notifications (35M/day)

**Provider:** FCM for Android, APNs for iOS. Direct integrations, no intermediary.

**Tradeoff:** OneSignal/Braze would save 4–6 weeks of integration work but cost ~$50–150K/year at our scale and reduce control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation features in year 2.

#### P0 Security Alert Delivery Policy

P0 security alerts (new device login, password changed, suspicious login detected) previously had `apns-expiration: 300s`. A user with a dead battery or in airplane mode for 6 minutes would never receive a security alert about their own account, with no fallback. This is not a theoretical edge case.

Security alerts are not time-bounded the way OTPs are. They should be stored and delivered when the device comes online. The correct expiration is 24 hours.

More importantly, push alone is insufficient for security alerts. The delivery model is:

```
P0 Security Alert Delivery Policy:
  1. Write to in-app store (synchronous, before anything else)
  2. Enqueue push (APNs expiration: 24h, FCM TTL: 86400)
  3. Enqueue email (for account takeover class alerts only)
  4. If push fails with UNREGISTERED/invalid token: in-app is the delivery
  5. If push succeeds: mark in-app notification as "also push-delivered"
```

In-app is the guaranteed backstop. Push is the first-touch delivery. Email is the belt-and-suspenders layer for the highest-severity alerts. A user receives the alert through whichever channel they engage with first.

#### FCM Rate Limits: What We Actually Know

FCM does not publish its per-project rate limits publicly. The actual quota depends on the Firebase project tier and whether a quota increase has been requested. Building a connection pool around an undocumented number is an operational risk at 35M push/day.

**Resolution:** We do not design around an assumed rate limit. We design for graceful degradation when we hit whatever limit exists.

```python
class FCMDispatcher:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(200)  # Conservative starting concurrency
        self._rate_limiter = TokenBucketRateLimiter(
            initial_rate=300,   # req/sec — conservative starting point
            max_rate=1000,      # upper bound we increase toward empirically
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
                retry_after = e.retry_after or (2 ** min(self._consecutive_429s, 6))
                await self._rate_limiter.reduce_rate(factor=0.5)
                await asyncio.sleep(retry_after)
                raise
```

**Empirical rate limit discovery:** In the first week of production, we ramp concurrency from 50 to 500 in-flight requests in steps of 50, with a 15-minute hold at each step, monitoring for 429 responses. We set our operational rate limit at 80% of the empirically discovered threshold. This is a required runbook step before full traffic cut-over, not something we discover during an incident.

We contact Firebase support before launch to request a quota increase appropriate for our volume. This is a documented step in the project timeline (Month 1, Week 3).

**FCM HTTP v1 API — Batching Clarification**

The FCM HTTP v1 API sends one message per request. HTTP/2 supports request multiplexing, and Google supports HTTP batch requests bundling up to 500 individual FCM requests into a single connection round-trip — but these are HTTP-level batches, not atomic FCM operations. Each message has its own response, error code, and retry semantics.

We maintain a connection pool of 50 persistent HTTP/2 connections and process each FCM message individually within multiplexed connections. We do not use the HTTP batch wrapper initially — the per-message HTTP/2 approach achieves equivalent throughput with simpler error handling.

#### APNs JWT Token Management

APNs JWT tokens have a hard 1-hour expiry enforced by APNs. If a token expires mid-flight, APNs returns a 403 `ExpiredProviderToken` and rejects all pushes on that connection until a new token is presented. We refresh proactively at 50 minutes.

```python
class APNsTokenManager:
    """
    Centralized JWT token manager shared across all APNs connections.
    Refreshes proactively at 50 minutes to avoid expiry during a request.
    """
    def __init__(self, key_id: str, team_id: str, private_key: bytes):
        self._key_id = key_id
        self._team_id = team_id
        self._private_key = private_key
        self._token: str | None = None
        self._token_generated_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        if self._token and (time.time() - self._token_generated_at) < 3000:
            return self._token
        async with self._lock:
            if self._token and (time.time() - self._token_generated_at) < 3000:
                return self._token
            return await self._refresh_token()

    async def _refresh_token(self) -> str:
        now = int(time.time())
        payload = {"iss": self._team_id, "iat": now}
        headers = {"alg": "ES256", "kid": self._key_id}
        new_token = jwt.encode(payload, self._private_key,
                               algorithm="ES256", headers=headers