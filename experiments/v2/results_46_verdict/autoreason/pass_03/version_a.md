# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M MAU.

**A note on this revision:** An earlier draft of this document had eleven specific gaps: an unquantified P0 latency SLA, Redis treated as a single point of failure without fallback, a recursive race condition in APNs JWT rotation, an unverifiable FCM throughput calculation, truncated digest batching code, no backpressure mechanism, a cross-training gap that opened before it was closed, understated opt-out compliance risk, unexamined PostgreSQL write amplification, an undefined S3 archival policy, and a month-6 hardening phase that wouldn't produce signal. Each is addressed directly in this revision.

Every tradeoff is explicit. Where we accept risk, we name it. Where we defer complexity, we state the trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

A critical modeling error to avoid upfront: different channels have different eligible populations. Push notifications reach installed-app users regardless of daily activity. In-app notifications only reach logged-in users. Treating DAU as the denominator for all channels produces wrong numbers.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~5 | Aggressive but not opt-out-inducing; industry benchmarks 3–8 |
| **Push volume/day** | **~35M** | 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K** | Auth and security only |
| **Total/day** | **~51M** | Sum across channels |
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput** | **~1,770/sec** | 51M × 3 / 86,400 |

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document.

**On push volume:** 5 notifications/day/installed user is a deliberate product constraint, not a technical one. We monitor opt-out rates weekly and treat any week-over-week increase above 0.5% as a P1 incident.

These are estimates. We instrument from day one and publish a traffic model review in month 2.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** The cross-training schedule below is explicitly designed to close coverage gaps *before* the channels those engineers own go live — not after. See Section 1.3 for the sequencing rationale.

| Engineer | Primary Responsibility | Channel Ownership | Cross-Trained On |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | In-app storage |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | Email |
| E3 | Preference management, user-facing API, suppression logic | In-app | SMS |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | Push |

**Cross-training requirement:** Cross-training rotations complete *before* the channel goes live in production. E4 (cross-trained on push) completes their push rotation during month 1, before push launches in month 2. E2 (cross-trained on email) completes their email rotation during month 1–2, before email digests launch in month 3. No channel goes live without its cross-trainer having completed at least one production deployment in staging. Runbooks are written by the primary owner and signed off by the cross-trainer before launch.

All engineers rotate on-call. No dedicated QA — engineers own quality. The mitigation is runbooks and observability, not headcount we don't have.

### 1.3 Delivery Milestones

| Month | Deliverable | Cross-Training Completed This Month |
|-------|-------------|-------------------------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | E4 completes push rotation (before push goes live in month 2) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E2 completes email rotation (before digests in month 3) |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 completes SMS rotation |
| 4 | Full preference management, suppression lists, advanced batching | — |
| 5 | Re-engagement campaigns, A/B framework for notification copy | — |
| 6 | Load testing to 4× peak, chaos testing on established baselines | — |

**On month 6:** Chaos testing requires a known steady state. By month 6, the system has been running in production for four months — we have baseline p50/p99 latency, queue drain rates, and error budgets. Chaos experiments test specific failure hypotheses against those baselines, not general system behavior. The load testing target is 4× peak (not 2× — the system is designed for 3× peak throughput, so 2× is below design target and not a useful test). Load testing runs continuously from month 2 onward in a staging environment that mirrors production sizing; month 6 formalizes this into a documented capacity envelope.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Token bucket rate limiting per caller
  - Returns 429 with Retry-After under overload
  - Sheds P2 load before P1; never sheds P0
     │
     ▼
[Notification Router]
  - Preference check (Redis cache with fallback to PostgreSQL)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment (by notification type)
  - Channel selection
     │
     ├─────────────────────────────────────────────┐
     ▼                                             ▼
[Priority Queue]                          [In-App Store]
  (Redis Sorted Set + Lua scripts)         (PostgreSQL, partitioned)
  (Redis Sentinel, 3-node cluster)                 │
     │                                             ▼
     ├── P0 Worker Pool (dedicated Redis keyspace) [WebSocket Pub/Sub]
     ├── P1 Worker Pool (20 workers)               (Redis, best-effort)
     └── P2 Worker Pool (10 workers)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — auth/security only)
          │
          ▼
   [Delivery Log]
   (PostgreSQL write replica + S3 archive)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures, token invalidation)
```

### 2.2 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues create operational complexity: N queues to monitor, N dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set handles 51M items comfortably. The tradeoff is that per-channel rate limiting requires logic in the dispatcher rather than queue topology. Acceptable at 10M MAU; revisited at 50M.

**P0 isolation within the queue.**
P0 notifications (security alerts, auth codes) use a dedicated Redis keyspace — a separate sorted set processed by dedicated workers — rather than competing with P1/P2 in the same sorted set. This is a narrow exception to the single-queue principle: P0 volume is small (<0.1% of total), the isolation is operationally simple (same Redis cluster, different key prefix), and it prevents a P1/P2 backlog event from degrading P0 latency. P0 SLA: delivered within 10 seconds of routing or paged as a P1 incident. P1 SLA: delivered within 60 seconds under normal load. P2 (digests, marketing): best-effort within the batch window.

**Redis is used for multiple functions — this is the primary infrastructure risk.**
Redis serves as the priority queue, preference cache, WebSocket pub/sub channel, APNs JWT store, and worker coordination locks. A Redis outage or memory exhaustion event degrades all of these simultaneously. We treat this explicitly:

- **Deployment:** Redis Sentinel with 3 nodes (1 primary, 2 replicas). Automatic failover in ~30 seconds. This does not eliminate downtime; it bounds it.
- **Preference cache fallback:** On Redis unavailability, the router falls back to PostgreSQL for preference reads. This is slower (5–10ms vs. <1ms) but correct. See Section 5.
- **Queue fallback:** If Redis is unavailable, the ingestion API queues to a PostgreSQL overflow table. Workers drain this table when Redis recovers. This adds latency but prevents data loss. P0 notifications bypass the overflow table and are delivered synchronously via a direct database write + worker poll.
- **APNs JWT fallback:** The JWT manager maintains an in-process cache with a 50-minute TTL. If Redis is unavailable, workers use their in-process cached token until expiry, then page if Redis hasn't recovered. See Section 3.1.
- **WebSocket pub/sub:** WebSocket delivery is best-effort. A Redis outage means in-app notifications are not pushed in real time; clients poll on a 30-second interval as fallback. This is acceptable — in-app notifications are stored in PostgreSQL and never lost.
- **Memory sizing:** Redis is provisioned at 2× the expected working set. We alert at 70% memory utilization and page at 85%.

**Synchronous preference check at routing time, with compliance caveat.**
User preferences are cached in Redis with explicit 5-minute TTLs and write-through invalidation on any preference update (see Section 5). Checking at routing keeps workers stateless and fast, and avoids consuming queue capacity for notifications we'll discard.

**The compliance risk is real and bounded:** A user who opts out after a notification is routed but before it is delivered will still receive that notification — a window of up to 5 minutes under normal conditions, potentially longer during a queue backlog. For GDPR and CAN-SPAM compliance, we treat this as follows: (1) marketing and re-engagement notifications perform a second preference check immediately before dispatch, paying the latency cost for the channel with the highest compliance exposure; (2) transactional and social notifications do not perform the second check — the 5-minute window is documented in our privacy policy as consistent with "reasonable technical delay"; (3) any user who contacts support about receiving a notification after opting out receives an immediate suppression and a manual review. This is not a perfect solution; it is a documented, bounded risk that we accept for all but the highest-compliance-exposure channel.

**In-app notifications bypass the queue.**
In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They're read-heavy, need random access by user, and benefit from immediate consistency. Routing them through the push queue adds latency with no benefit. The tradeoff is two code paths to maintain; we accept this because the operational profiles are genuinely different.

**Managed providers over self-hosted.**
We use FCM/APNs directly, SendGrid for email, and Twilio for SMS. We do not self-host SMTP, build our own push infrastructure, or run our own message broker beyond Redis. The tradeoff is vendor dependency and cost; the benefit is that 4 engineers don't spend 6 months building infrastructure instead of product.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~35M/day)

**Provider:** FCM HTTP v1 API for Android, APNs HTTP/2 for iOS. Direct integrations.

**Tradeoff vs. OneSignal/Braze:** A managed push platform saves 4–6 weeks of integration work but costs $50–150K/year at our scale and reduces control over retry behavior, delivery receipts, and token management. We build direct integrations. We revisit if we need advanced segmentation features in year 2.

#### FCM Throughput — Verified Calculation

**Critical implementation note:** FCM HTTP v1 API does not support multi-token batch requests — that was a feature of the legacy API, deprecated June 2024. The v1 API requires one HTTP request per device token.

At 35M push/day with a 70/30 Android/iOS split: approximately 24.5M FCM requests/day, or ~850/sec average and ~2,550/sec at 3× peak.

**Throughput calculation with explicit latency assumption:**

FCM p99 round-trip latency in Google's published benchmarks and operator experience is approximately 100–300ms under normal conditions. We plan for 200ms p99.

At 200ms p99 latency, a single HTTP/2 stream can sustain 5 requests/second (1000ms / 200ms). With 50 persistent connections and 100 concurrent streams per connection = 5,000 concurrent streams. At 5 req/sec per stream: theoretical maximum ~25,000 req/sec. We target 3,000 req/sec sustained to maintain headroom.

Across 20 P1 workers: ~150 req/sec per worker, requiring ~30 concurrent streams per worker at 200ms latency. Well within the per-worker connection budget.

**If FCM p99 degrades to 1,000ms** (which happens during Google incidents): throughput per stream drops to 1 req/sec, total capacity drops to ~5,000 req/sec — still above our 2,550 peak target, but with no headroom. We alert when FCM p99 exceeds 500ms and shed P2 push traffic during degraded FCM performance.

```
FCM Configuration:
- HTTP/2 multiplexing: 50 persistent connections, ~100 streams each
- Throughput target: 3,000 req/sec sustained (headroom above 2,550 peak)
- FCM quota: default 600,000 req/min (~10,000/sec); well within limit
- Workers are stateless; each maintains its own connection pool
- Latency assumption: 200ms p99; alert at 500ms; shed P2 at 1,000ms

Error handling:
- InvalidRegistration / NotRegistered: mark token invalid, never retry
- 429 / 500: exponential backoff, max 3 retries for P1/P2
- P0: up to 10 retries with 1s initial backoff
- 503: treat as transient, retry with backoff
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

#### APNs JWT Rotation — Race Condition Fixed

APNs JWTs must be generated with an `iat` claim and are rejected after 60 minutes. We rotate at 55 minutes. JWT rotation failure means all APNs delivery stops — this is a single point of failure requiring explicit