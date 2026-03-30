# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions are:

1. **Four isolated priority queues** (P0–P3 are genuinely separate), because P3 digest TTL semantics differ from P2 and silently sharing a queue causes stale-expiry errors
2. **Full payload storage in queue entries** — storing only IDs creates a crash window between dequeue and payload fetch that causes silent, unrecoverable message loss
3. **Worker pools are per-channel, deployed behind per-priority queues** — capacity math and deployment topology reconciled into a single model
4. **SMS volume cut to ~100K/day before launch** — 1M SMS/day at A2P rates is a $3.6–5.5M/year line item that kills the budget
5. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL
6. **Redis failover acknowledged as a P0 delivery risk** with a concrete mitigation strategy

We ship a working system in month 2, iterate through month 5, and harden in month 6. Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### Traffic Model

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes, ~2hr duration |
| **Sustained peak throughput** | **~1,750/sec** | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Capacity ceiling, not operating target |

All capacity planning is sized against the 1,750/sec peak figure. Ratios are instrumented from day one and reviewed at the month 2 checkpoint.

### The SMS Budget Problem

1M SMS/day × 365 = 365M messages/year. At realistic A2P 10DLC all-in rates ($0.010–0.015/message including carrier surcharges), that is **$3.6M–5.5M/year** — for a channel serving 2% of volume. This is not a rounding error; it is a budget-killing line item.

**Decision: SMS volume is capped at ~100K/day before launch.** Permitted SMS:

- OTP / 2FA codes (always — non-negotiable for security)
- Password reset fallback (if no email open within 10 minutes)
- Security alerts (new device login, suspicious activity)
- Nothing else, regardless of user preference

This targets ~$365K–550K/year — still significant but budgetable. The 1M/day figure is retained in capacity planning as a ceiling. Any product decision to expand SMS eligibility requires explicit budget approval and re-architecture of the rate-limiting tier before the change ships.

### Worker Capacity Sizing

**Per-worker throughput assumptions:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2, 20-conn pool, individual requests | ~500 tokens/sec across pool |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput note:** APNs has no batch API — every notification is an individual HTTP/2 request. At 20 persistent connections with ~40ms RTT per request, the pool delivers approximately 500 requests/second. Peak APNs demand is ~350/sec, giving 1.4× headroom — thin but acceptable because APNs is iOS-only (roughly half of push volume) and connections can be added cheaply. This queue gets a latency alert at 300/sec sustained.

**In-app demand note:** In-app notifications are only delivered to logged-in users. At 3M DAU with ~20% concurrently active during peak, ~600K users are online at any moment. In-app peak demand = 10M/day × 3× peak × (600K/3M active fraction) / 86,400 = **~350/sec** — not 1,040/sec. Applying the peak multiplier to total daily volume without the active-user constraint overstates demand by 3×.

**Demand vs. capacity:**

| Channel | Peak demand | Workers | Peak capacity | Headroom |
|---------|-------------|---------|---------------|----------|
| FCM push | ~1,215/sec | 4 | ~8,000/sec | 6.6× |
| APNs push | ~350/sec | 3 (shared pool) | ~500/sec | 1.4× ⚠️ |
| Email | ~138/sec | 2 | ~2,000/sec | 14× |
| SMS | ~4/sec | 1 | ~67/sec | 16× |
| In-app | ~350/sec | 4 | ~4,000/sec | 11× |

**Total: 14 workers.** We provision 2× headroom = **28 workers total**, deployed as separate processes with independent scaling. APNs headroom is flagged for active monitoring.

### Queue Drain Analysis

At 50M/day baseline, normal rate is ~578/sec. During a 3× peak the excess above baseline is ~1,156/sec. Over a 2-hour sustained peak (7,200 seconds), the queue accumulates ~8.3M notifications above baseline. (Total peak volume is ~12.6M, but only the excess accumulates — the rest drains in real time.)

At combined worker capacity of ~8,000+ notifications/sec and baseline input of ~578/sec, net drain rate above baseline is ~7,400/sec. The 8.3M excess clears in approximately **18 minutes** after peak ends. Queue depth is monitored with alerts at 500K items.

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, workers | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | Push (FCM + APNs) | Email + SMS | Deliverability, token hygiene |
| E3 | Preferences, API, suppression | Schema, preference API | In-app, WebSocket | User-facing polish |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ | Chaos testing, runbooks |

**E4 scope is bounded by managed services.** Specifically:

- Redis: ElastiCache Multi-AZ (not self-managed)
- PostgreSQL: RDS Multi-AZ (not self-managed)
- Monitoring: Datadog (not self-built)
- Deployments: ECS with Fargate (not custom scripts)

All four engineers are on-call. E4 writes the runbooks; everyone executes them. Chaos testing is deferred to month 5 — E4 does not attempt it while building the system.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources (app servers, internal services)
        │
        ▼
[Event Ingestion API]   ← stateless, horizontally scaled, rate-limited
        │
        ▼
[Notification Router]
  - Preference lookup    (Redis cache, TTL discussed in §5)
  - Suppression check    (global + per-user blocklists)
  - Priority assignment  (by notification type, not user)
  - Channel selection    (priority + user preferences)
  - Aggregation check    (Redis, per type/entity/user)
        │
        ├──────────────────────────────────────────────┐
        ▼                                              ▼
[P0 Queue]  [P1 Queue]  [P2 Queue]  [P3 Queue]   [In-App Store]
(Redis List) (Redis List) (Redis List) (Redis List) (PostgreSQL)
     │            │           │           │              │
     ▼            ▼           ▼           ▼              │
[P0 Workers] [P1 Workers] [P2 Workers] [P3 Workers]      │
  (2 total)   (8 total)    (6 total)    (4 total)        │
     │            │           │           │              │
     └────────────┴───────────┴───────────┘              │
                  │                                      │
          [Channel Dispatcher]                           │
            ├── Push (FCM / APNs)                        │
            ├── Email (SendGrid)                         │
            └── SMS (Twilio)                             │
                  │                                      │
                  ▼                                      ▼
           [Delivery Log]                    [WebSocket Fanout]
       (PostgreSQL + S3 archive)           (Redis Pub/Sub → clients)
                  │
                  ▼
        [Feedback Processor]
    (bounces, opens, token invalidity, delivery receipts)
```

### Worker Pool to Queue Mapping

Workers are per-channel and per-priority — a P0 FCM worker only dequeues from P0; a P1 FCM worker only dequeues from P1. They are separate process instances, not a shared pool with priority-based routing. The per-channel capacity numbers above reflect the aggregate across all priority tiers for that channel.

| Priority queue | Notification types | Channel workers assigned | Total workers |
|---------------|-------------------|--------------------------|---------------|
| P0 | OTP, security alert, payment confirm | 1 FCM + 1 APNs (dedicated pool) | 2 |
| P1 | DM, mention, comment reply | 3 FCM + 2 APNs + 2 in-app + 1 SMS | 8 |
| P2 | Comment, like, follow | 1 FCM + 1 email + 2 in-app | 4 |
| P3 | Digest, re-engagement | 2 email + 2 in-app | 4 |

### Why Four Queues, Not One Sorted Set

The single-queue-with-priority-scoring approach fails under backpressure — exactly when it matters most. A P0 security alert in a Redis sorted set competes for the same lock as thousands of P2 like notifications. "P0 always beats P1" is only guaranteed when the queue drains faster than it fills. That guarantee disappears precisely when you need it most.

Four separate Redis Lists give us:

- **Hard isolation:** P0 workers only touch the P0 queue. A P2 burst cannot delay P0 delivery.
- **Correct TTL semantics per priority:** P3 digests get 48-hour TTL; P2 notifications get 24-hour TTL. These are different business requirements. Sharing a queue means either the P3 TTL entry is ignored (silent early expiry) or the P2 TTL is silently extended — both are wrong.
- **Independent scaling:** Adding P1 workers requires no P0 configuration changes.
- **Simpler failure isolation:** Each queue has its own dead-letter queue. No priority scoring arithmetic to get wrong under load.

**The cost:** Four worker pools, four dead-letter queues, four sets of metrics. Manageable with managed infrastructure.

**What we give up:** Perfect global ordering within a priority band across channels. A P1 push might be processed before a P1 email that arrived 5 seconds earlier. Per-channel ordering within a priority band is sufficient for a social app.

---

## 3. Queue Implementation

### 3.1 Enqueue

```python
PRIORITY_QUEUES = {
    "P0": "queue:p0",
    "P1": "queue:p1",
    "P2": "queue:p2",
    "P3": "queue:p3",   # Separate queue — different TTL, different worker pool
}

QUEUE_TTLS = {
    "P0": 300,      # 5 minutes  — stale OTPs are worse than no OTPs
    "P1": 3600,     # 1 hour
    "P2": 86400,    # 24 hours
    "P3": 172800,   # 48 hours — digests need longer delivery window
}

def enqueue(notification: Notification) -> None:
    queue_name = PRIORITY_QUEUES[notification.priority]
    ttl = QUEUE_TTLS[notification.priority]
    payload = notification.model_dump_json()

    pipe = redis.pipeline(transaction=True)
    # Store payload keyed by ID for deduplication lookups
    pipe.setex(f"ntf:{notification.id}", ttl, payload)
    # Push full payload onto queue — eliminates the crash window at dequeue time
    pipe.lpush(queue_name, payload)
    pipe.execute()
```

**Why full payload in the queue, not just the ID:** Storing only the ID requires a second round-trip at dequeue time to fetch the payload. Between RPOP and payload fetch, the notification ID is held by no one — removed from the queue but not yet retrieved. A worker crash at that point causes permanent, silent message loss with no DLQ entry and no retry path. Storing the full payload in the queue entry eliminates this window entirely: the dequeue operation *is* the payload retrieval. The separate `ntf:{id}` key is retained for deduplication checks, not for delivery.

### 3.2 Dequeue: Atomic Lua Script

```lua
-- dequeue_batch.lua
-- KEYS[1]: queue name
-- ARGV[1]: batch size
-- Returns: list of notification payloads (full JSON)

local queue = KEYS[1]
local batch_size = tonumber(ARGV[1])
local results = {}

for i = 1, batch_size do
    local payload = redis.call('RPOP', queue)
    if payload == false then
        break
    end
    table.insert(results, payload)
end

return results
```

```python
DEQUEUE_SCRIPT = redis.register_script(open("dequeue_batch.lua").read())

def dequeue_batch(queue_name: str, batch_size: int = 50) -> list[Notification]:
    raw_payloads = DEQUEUE_SCRIPT(keys=[queue_name], args=[batch_size])
    if not raw_payloads:
        return []

    notifications = []
    for payload in raw_payloads:
        try:
            notifications.append(Notification.model_validate_json(payload))
        except ValidationError:
            metrics.increment("notification.parse_error", tags={"queue": queue_name})
            # Malformed payload — log and discard rather than retry-loop
    return notifications
```

**Why `RPOP` not `ZRANGE`/`ZREM`:** `RPOP` is O(1) and atomic by definition — exactly one caller receives each element. The Lua script batches multiple `RPOP` calls into a single round-trip. No two workers can receive the same notification.

**Why polling not `BRPOP`:** Workers poll with a 50ms sleep on empty queue rather than blocking. This gives explicit control over batch size and avoids thundering herd behavior on reconnect after a Redis failover.

### 3.3 Priority Assignment

Priority is assigned by notification type at routing time. Users cannot escalate priority — they can suppress channels or configure delivery windows, but a "like" is always P2 regardless of preferences.

```python
NOTIFICATION_TYPE_PRIORITY = {
    # P0 — Critical, <5 second target latency
    "otp":              "P0",
    "security_alert":   "P0",
    "payment_confirm":  "P0",

    # P1 — High, <30 second target latency
    "direct_message":   "P1",
    "