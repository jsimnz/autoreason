# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions are:

1. **Three isolated priority queues** (not a single sorted set), because P0 isolation must hold under backpressure — exactly when it matters most
2. **Worker capacity sized from first principles**, not intuition
3. **SMS volume cut 80–90% before launch** — the economics of 1M SMS/day are incompatible with a startup budget
4. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL

We ship a working system in month 2, iterate through month 5, and harden in month 6. Every tradeoff below is named explicitly.

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

All capacity planning is sized against the 1,750/sec peak figure. Ratios are instrumented from day one and reviewed in month 2.

### The SMS Budget Problem

1M SMS/day × 365 days = 365M messages/year. At realistic A2P 10DLC all-in rates ($0.010–0.015/message including carrier surcharges), that is **$3.6M–5.5M/year** — for a channel serving 2% of volume. This is not a rounding error; it is a budget-killing line item.

**Decision: SMS volume is capped at ~100K/day before launch.** Permitted SMS:

- OTP / 2FA codes (always — non-negotiable for security)
- Password reset fallback (if no email open in 10 minutes)
- Security alerts (new device login, suspicious activity)
- Nothing else, regardless of user preference

This targets ~$365K–550K/year — still significant but budgetable. The 1M/day figure is retained as a capacity ceiling. Any product decision to expand SMS eligibility requires explicit budget approval and re-architecture of the rate limiting tier before the change ships.

### Worker Capacity Sizing

The following math justifies every worker count in this design. Nothing is intuited.

**Per-worker throughput assumptions:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2, 20-connection pool, ~100 tokens/req | ~50,000 tokens/sec across pool |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**Demand vs. capacity:**

| Channel | Peak demand | Workers assigned | Peak capacity | Headroom |
|---------|-------------|-----------------|---------------|----------|
| FCM push | ~1,215/sec | 4 | ~8,000/sec | 6.6× |
| APNs push | ~350/sec | 3 (shared pool) | ~50,000/sec | >>10× |
| Email | ~138/sec | 2 | ~2,000/sec | 14× |
| SMS | ~4/sec | 1 | ~67/sec | 16× |
| In-app | ~1,040/sec | 2 | ~2,000/sec | 1.9× |

**Total: 12 workers** with explicit capacity bounds. We provision 2× headroom = **24 workers total**, deployed as separate processes with independent scaling.

**Queue drain analysis:** At 1,750/sec input and combined worker capacity of ~8,000+ notifications/sec, the queue drains ~4.5× faster than it fills during peak. A 2-hour sustained peak at 3× normal produces ~12.6M notifications above baseline. At net drain rate of ~6,250/sec above baseline, the queue clears within 33 minutes of peak ending. Queue depth is monitored with alerts at 500K items.

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, workers | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | Push (FCM + APNs) | Email + SMS | Deliverability, token hygiene |
| E3 | Preferences, API, suppression | Schema, preference API | In-app, WebSocket | User-facing polish |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ | Chaos testing, runbooks |

**E4 scope is bounded by managed services.** "Reliability, monitoring, failure handling, DevOps" is not one engineer's scope for a 50M event/day system — unless the infrastructure is managed. E4 configures and responds; E4 does not operate. Specifically:

- Redis: ElastiCache (not self-managed)
- PostgreSQL: RDS Multi-AZ (not self-managed)
- Monitoring: Datadog (not self-built)
- Deployments: ECS or Kubernetes with Helm (not custom scripts)

All four engineers are on-call. E4 writes the runbooks; everyone executes them. Chaos testing is explicitly deferred to month 5 — E4 does not attempt it while building the system.

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
  - Preference lookup    (Redis cache, 60s TTL)
  - Suppression check    (global + per-user blocklists)
  - Priority assignment  (by notification type, not user)
  - Channel selection    (priority + user preferences)
  - Aggregation check    (Redis, per type/entity/user)
        │
        ├──────────────────────────────────────┐
        ▼                                      ▼
[P0 Queue]  [P1 Queue]  [P2/P3 Queue]    [In-App Store]
(Redis List) (Redis List) (Redis List)    (PostgreSQL)
        │          │           │                │
        ▼          ▼           ▼                │
[P0 Workers]  [P1 Workers]  [P2/P3 Workers]     │
  (4 total)    (12 total)     (8 total)          │
        │          │           │                │
        └────┬─────┘───────────┘                │
             ▼                                  │
     [Channel Dispatcher]                       │
       ├── Push (FCM / APNs)                    │
       ├── Email (SendGrid)                     │
       └── SMS (Twilio)                         │
             │                                  │
             ▼                                  ▼
       [Delivery Log]                  [WebSocket Fanout]
   (PostgreSQL + S3 archive)          (Redis Pub/Sub → clients)
             │
             ▼
    [Feedback Processor]
    (bounces, opens, token invalidity, delivery receipts)
```

### Why Three Queues, Not One Sorted Set

The single-queue-with-priority-scoring approach offers operational simplicity in the easy case. It fails in the case that matters: when the queue is under backpressure due to a provider outage, deployment gap, or traffic spike.

A P0 security alert in a Redis sorted set competes for the same `ZRANGE`/`ZREM` lock as thousands of P2 like notifications. "P0 always beats P1" is only guaranteed when the queue drains faster than it fills. That guarantee disappears exactly when you need it most.

**Three separate Redis Lists with `LPUSH`/`RPOP` give us:**
- **Hard isolation:** P0 workers only touch the P0 queue. A P2 burst that saturates P2 workers cannot delay P0 delivery.
- **Independent scaling:** Adding P1 workers requires no P0 configuration changes.
- **Simpler operations:** Three lists, each with its own dead-letter queue. No priority scoring arithmetic to get wrong.

**The cost:** Three worker pools, three dead-letter queues, three sets of metrics. For a team of 4 using managed infrastructure, this is manageable — we are not adding operational overhead proportional to worker count.

**What we give up:** Perfect global ordering within a priority band across channels. A P1 push notification might be processed before a P1 email that arrived 5 seconds earlier. This is acceptable — per-channel ordering within a priority band is sufficient for a social app.

---

## 3. Queue Implementation

### 3.1 Enqueue

```python
PRIORITY_QUEUES = {
    "P0": "queue:p0",
    "P1": "queue:p1",
    "P2": "queue:p2",
    "P3": "queue:p2",  # P3 shares queue with P2; separate worker allocation
}

QUEUE_TTLS = {
    "P0": 300,      # 5 minutes  — stale OTPs are worse than no OTPs
    "P1": 3600,     # 1 hour
    "P2": 86400,    # 24 hours
    "P3": 172800,   # 48 hours
}

def enqueue(notification: Notification):
    queue_name = PRIORITY_QUEUES[notification.priority]
    ttl = QUEUE_TTLS[notification.priority]
    
    pipe = redis.pipeline(transaction=True)
    pipe.setex(
        f"ntf:{notification.id}",
        ttl,
        notification.model_dump_json()
    )
    pipe.lpush(queue_name, notification.id)
    pipe.execute()
```

### 3.2 Dequeue (Atomic via Lua)

The previous version promised a Lua script and never showed it. Here it is.

```lua
-- dequeue_batch.lua
-- KEYS[1]: queue name
-- ARGV[1]: batch size
-- Returns: list of notification IDs (empty list if queue is empty)

local queue = KEYS[1]
local batch_size = tonumber(ARGV[1])
local results = {}

for i = 1, batch_size do
    local id = redis.call('RPOP', queue)
    if id == false then
        break
    end
    table.insert(results, id)
end

return results
```

```python
DEQUEUE_SCRIPT = redis.register_script(open("dequeue_batch.lua").read())

def dequeue_batch(queue_name: str, batch_size: int = 50) -> list[Notification]:
    ids = DEQUEUE_SCRIPT(keys=[queue_name], args=[batch_size])
    if not ids:
        return []
    
    # Fetch notification payloads in a single pipeline
    pipe = redis.pipeline()
    for id in ids:
        pipe.get(f"ntf:{id}")
    raw_results = pipe.execute()
    
    notifications = []
    for id, data in zip(ids, raw_results):
        if data is None:
            # TTL expired before processing — notification too stale to deliver
            metrics.increment("notification.expired", tags={"queue": queue_name})
            continue
        notifications.append(Notification.model_validate_json(data))
    
    return notifications
```

**Why `RPOP` not `ZRANGE`/`ZREM`:** `RPOP` is O(1) and atomic by definition — exactly one caller receives each element. The Lua script batches multiple `RPOP` calls into a single round-trip, preserving atomicity without a distributed lock. No two workers can receive the same notification ID.

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
    "mention":          "P1",
    "comment_reply":    "P1",
    
    # P2 — Normal, <5 minute target latency
    "comment":          "P2",
    "like":             "P2",
    "follow":           "P2",
    
    # P3 — Batch, scheduled delivery
    "digest":           "P3",
    "reengagement":     "P3",
}
```

---

## 4. Delivery Channels

### 4.1 Push Notifications (70% — 35M/day)

**Provider decision:** FCM HTTP v1 (Android) and APNs HTTP/2 (iOS), direct integrations — not OneSignal, Braze, or another managed push provider.

**Tradeoff:** Managed push providers save 4–6 weeks of integration work and cost $50–150K/year at our scale. We build direct integrations because: (a) we need precise control over retry behavior to avoid duplicate sends; (b) delivery receipt webhooks from intermediaries add latency and a failure surface we don't control; (c) we have engineers capable of owning this. We revisit if we need A/B testing on push copy or advanced segmentation that justifies the cost.

**FCM configuration:**

```
API:            HTTP v1 (not legacy FCM — legacy is deprecated)
Connection pool: 50 persistent HTTP/2 connections
Batch size:      500 tokens/request (FCM v1 maximum)
Send rate:       400 req/sec (below FCM's 600 req/sec project limit — 33% headroom)
Effective throughput: 200,000 tokens/sec (peak demand: ~1,215/sec)
Workers:         4 (redundancy + connection pool management)
```

**APNs configuration:**

```
API:             HTTP/2 with JWT authentication
Connection pool: 20 persistent connections
Batch approach:  Individual requests per device (APNs has no batch API)
                 Parallelized across connection pool
Priority header: 10 (immediate delivery) for P0/P1
                 5  (power-saving, opportunistic) for P2
Collapse key:    {notification_type}:{entity_id}
                 Collapses stale like/follow notifications on same entity
Workers:         3 (sharing the connection pool)
```

**APNs JWT token rotation (corrected):**

APNs JWT tokens expire after 60 minutes. The correct rotation strategy is proactive, not reactive:

```python
class APNsTokenManager:
    def __init__(self, key_id: str, team_id: str, private_key: bytes):
        self.key_id = key_id
        self.team_id = team_id
        self.private_key = private_key
        self._token: str | None = None
        self._token_issued_at: float = 0
        self._lock = threading.Lock()