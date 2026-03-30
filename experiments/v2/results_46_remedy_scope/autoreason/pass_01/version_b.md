# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The revision addresses twelve specific structural problems in the previous version: queue isolation, worker capacity math, dequeue correctness, priority scoring, partitioning, SMS economics, WebSocket capacity, team scope, digest state management, APNs token handling, aggregation flush logic, and delivery quality standards.

The core architectural change from the previous version: **three isolated queues by priority tier, not a single sorted set.** This costs marginally more operational overhead but eliminates the fundamental problem where P2 volume can delay P0 delivery. Every other design decision flows from an honest accounting of scale, cost, and what four engineers can actually own.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU (social apps) |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes, ~2hr duration |
| **Sustained peak throughput** | **~1,750/sec** | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

These ratios are estimates. We instrument from day one and adjust in month 2. All capacity planning below is sized against the 1,750/sec peak figure, not the daily average.

### The SMS Budget Problem

The previous version acknowledged SMS cost and moved on. This is wrong. 1M SMS/day × 365 days = 365M messages/year. At negotiated A2P 10DLC rates (which must be factored in — Twilio's list price is not what you pay at volume), realistic all-in cost including carrier surcharges is **$0.010–0.015/message** in the US, higher internationally. That is **$3.6M–5.5M/year** for a channel serving 2% of volume.

**Decision: SMS volume must be cut by 80–90% before launch.** Our revised SMS policy:

- OTP/2FA: always allowed (non-negotiable for security)
- Password reset fallback: allowed (if no email open in 10 minutes)
- Security alerts (new device login): allowed
- Everything else: not allowed via SMS, regardless of user preference

This targets **~100K SMS/day** (OTP + security), not 1M. Annual cost ~$365K–550K — still significant but budgetable. The 1M/day figure in the traffic model is retained as a capacity ceiling, not an operating target. Any product decision to expand SMS eligibility requires explicit budget approval and re-architecture of the rate limiting tier.

### Worker Capacity Analysis

The previous version specified 40 workers without verifying they could drain 1,750/sec. We fix that here.

**Per-worker throughput assumptions:**

| Channel | Latency per notification | Notes |
|---------|--------------------------|-------|
| Push (FCM batch) | ~5ms per notification in a 500-batch | FCM processes 500 tokens/request; request RTT ~250ms |
| Push (APNs) | ~8ms per notification in a 100-batch | APNs HTTP/2, smaller practical batch |
| Email | ~2ms per notification | SendGrid async; we fire-and-confirm |
| SMS | ~15ms per notification | Twilio synchronous confirmation |
| In-app | ~1ms | DB write, no external call |

**FCM batch math:** One FCM worker sends 500-token batches with 250ms RTT. That's 2,000 tokens/sec per worker. We need to sustain 35M push/day = 405/sec average, 1,215/sec peak. At 2,000 tokens/sec/worker, **1 FCM worker handles peak comfortably; we run 4 for redundancy and headroom.**

**APNs batch math:** APNs HTTP/2 practical throughput with a 20-connection pool is ~500 requests/sec. At 100 tokens/request that's 50,000 tokens/sec — more than sufficient. The constraint is connection pool size, not worker count. We run **3 APNs workers sharing the connection pool.**

**Email math:** SendGrid's API accepts batches; at 4M/day = 46/sec average, 138/sec peak. One worker handles this. We run **2 email workers.**

**SMS math:** At our revised 100K/day target = 1.2/sec average, 4/sec peak. Trivial. **1 SMS worker.**

**In-app math:** PostgreSQL batch inserts at 1ms/row = 1,000 rows/sec/worker. In-app peak is 10M/day = 347/sec average, ~1,040/sec peak. **2 in-app workers with batched inserts of 100 rows.**

**Total: 12 workers** across all channels, each with well-understood throughput bounds. We provision 2× headroom = **24 workers total.** This is down from the previous 40, but the previous 40 had no math behind them. These 24 have explicit capacity justification.

**Queue depth under sustained peak:** At 1,750/sec input and 24 workers with combined throughput of ~8,000 notifications/sec, the queue drains 4.5× faster than it fills. A 2-hour peak at 3× normal produces ~12.6M notifications above baseline. At net drain rate of ~6,250/sec above baseline, the queue clears in ~33 minutes after peak ends. This is acceptable. If input ever exceeds worker capacity (provider slowdown, deployment), we have queue depth monitoring with alerts at 500K items.

### Team Allocation

| Engineer | Primary Responsibility | Month 1–2 | Month 3–4 | Month 5–6 |
|----------|----------------------|-----------|-----------|-----------|
| E1 | Core pipeline, queue infrastructure | Queue, router, workers | Aggregation, batching | Capacity tuning, load testing |
| E2 | Channel integrations | Push (FCM + APNs) | Email + SMS | Deliverability, token hygiene |
| E3 | Preferences, API, suppression | Schema, preference API | In-app, WebSocket | User-facing polish |
| E4 | Infrastructure, monitoring | Deployment, CI/CD, alerting | Failure handling, DLQ | Chaos testing, runbooks |

**E4 scope acknowledgment:** The previous version assigned E4 "Reliability, monitoring, failure handling, DevOps" — this is not one engineer's scope for a 50M event/day system. We resolve this by:

1. **Using managed services wherever possible.** We do not operate our own Redis cluster — we use ElastiCache. We do not operate our own PostgreSQL — we use RDS with Multi-AZ. We do not build our own monitoring — we use Datadog. E4's job is configuration and response, not operation.
2. **Distributing on-call.** All four engineers are on-call. E4 writes the runbooks; everyone executes them.
3. **Explicitly deferring chaos engineering to month 5.** E4 does not attempt chaos testing while also building the system. The schedule reflects this.
4. **Accepting that some reliability work will be deferred.** We document what's deferred and what the risk is. This is honest scope management, not a hidden risk.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources (app servers, internal services)
     │
     ▼
[Event Ingestion API]  (stateless, horizontally scaled)
     │
     ▼
[Notification Router]
  - Preference lookup (Redis cache, 60s TTL)
  - Suppression check (global + per-user)
  - Priority assignment (by notification type)
  - Channel selection (by priority + user prefs)
  - Aggregation check (Redis, per type/entity/user)
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
[P0 Queue]  [P1 Queue]  [P2/P3 Queue]  [In-App Store]
(Redis List) (Redis List) (Redis List)  (PostgreSQL)
     │           │            │
     ▼           ▼            ▼
[P0 Workers] [P1 Workers] [P2/P3 Workers]
  (4 total)    (12 total)    (8 total)
     │           │            │
     └─────┬─────┘────────────┘
           ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio)
           │
           ▼
   [Delivery Log] (PostgreSQL + S3 archive)
           │
           ▼
   [Feedback Processor] (bounces, opens, failures, token invalidity)
```

### Why Three Queues, Not One

The previous version used a single Redis sorted set with priority scoring, framed as an operational simplicity win. The critic correctly identified the failure mode: a P0 security alert competes for the same `zrange`/`zrem` lock as thousands of P2 like notifications. Under queue backpressure (provider outage, deployment gap, traffic spike), P0 latency degrades. "P0 always beats P1" is only guaranteed when the queue is draining faster than it fills. That guarantee disappears exactly when you need it most.

**Three separate Redis Lists (LPUSH/BRPOP) give us:**
- **Hard isolation:** P0 workers only touch the P0 queue. A P2 burst that saturates P2 workers does not affect P0 delivery.
- **Independent scaling:** We can add P1 workers without touching P0 configuration.
- **Simpler operations:** Three lists, each with its own dead-letter queue. No priority scoring math to get wrong.

**The cost:** Three sets of workers, three dead-letter queues, three sets of metrics. For a team of 4, this is manageable. We have 24 workers total; we're not adding operational overhead proportional to the worker count.

**What we give up:** Perfect global ordering within a priority band across channels. A P1 push notification might be processed before a P1 email that arrived 5 seconds earlier. This is acceptable — per-channel ordering within a priority band is sufficient.

---

## 3. Queue Implementation

### 3.1 Correct Dequeue Logic

The previous version showed a pipeline (not atomic) and promised a Lua script that was never shown. Here is the actual implementation.

**Enqueue:**

```python
def enqueue(notification: Notification, queue_name: str):
    # Store notification data with TTL matching priority
    ttl = {"P0": 300, "P1": 3600, "P2": 86400, "P3": 172800}
    pipe = redis.pipeline(transaction=True)
    pipe.setex(
        f"ntf:{notification.id}",
        ttl[notification.priority],
        notification.model_dump_json()
    )
    pipe.lpush(queue_name, notification.id)
    pipe.execute()
```

**Dequeue (Lua script for atomicity):**

```lua
-- dequeue_batch.lua
-- KEYS[1]: queue name (e.g., "queue:p0")
-- ARGV[1]: batch size
-- Returns: list of notification IDs, or empty list

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
# Load script at startup, use SHA for subsequent calls
DEQUEUE_SCRIPT = redis.register_script(open("dequeue_batch.lua").read())

def dequeue_batch(queue_name: str, batch_size: int = 50) -> list[Notification]:
    ids = DEQUEUE_SCRIPT(keys=[queue_name], args=[batch_size])
    if not ids:
        return []
    
    # Fetch notification data; filter missing (expired TTL)
    pipe = redis.pipeline()
    for id in ids:
        pipe.get(f"ntf:{id}")
    raw = pipe.execute()
    
    notifications = []
    for id, data in zip(ids, raw):
        if data is None:
            # TTL expired — notification too old, discard
            metrics.increment("notification.expired", tags={"queue": queue_name})
            continue
        notifications.append(Notification.model_validate_json(data))
    
    return notifications
```

**Why RPOP (not zrange/zrem):** Redis `RPOP` is O(1) and atomic by definition — only one caller gets each element. The Lua script batches multiple RPOPs into a single round-trip while preserving atomicity. No two workers can receive the same notification ID.

**Why not BRPOP:** We use polling workers with a short sleep rather than blocking RPOP. This gives us more control over batch size and prevents thundering herd on reconnect. Workers sleep 50ms when the queue is empty.

### 3.2 Priority Routing

```python
PRIORITY_QUEUES = {
    "P0": "queue:p0",
    "P1": "queue:p1",
    "P2": "queue:p2",
    "P3": "queue:p3",  # P3 shares queue with P2, different worker allocation
}

NOTIFICATION_TYPE_PRIORITY = {
    "otp":              "P0",
    "security_alert":   "P0",
    "payment_confirm":  "P0",
    "direct_message":   "P1",
    "mention":          "P1",
    "comment_reply":    "P1",
    "comment":          "P2",
    "like":             "P2",
    "follow":           "P2",
    "digest":           "P3",
    "reengagement":     "P3",
}
```

Priority is assigned by notification type at routing time. Users cannot escalate priority. Users can suppress channels or delay delivery windows, but a "like" notification is always P2 regardless of user settings.

---

## 4. Delivery Channels

### 4.1 Push Notifications (70% — 35M/day)

**Provider:** FCM HTTP v1 (Android) and APNs HTTP/2 (iOS), direct integrations.

**Tradeoff vs. OneSignal/Braze:** Managed push providers save 4–6 weeks of integration work and cost $50–150K/year at our scale. We build direct integrations because: (a) we need precise control over retry behavior to avoid duplicate sends; (b) delivery receipt webhooks from intermediaries add latency and failure surface; (c) we have engineers who can own this. We revisit if we need A/B testing or advanced segmentation that justifies the cost.

**FCM configuration:**

```
- HTTP/2 persistent connection pool: 50 connections
- Batch size: 500 tokens/request (FCM v1 maximum)
- Target send rate: 400 req/sec (below FCM's 600 req/sec project limit)
- Throughput: 400 req/sec × 500 tokens = 200,000 tokens/sec
  (peak demand: ~1,215 push/sec — well within capacity)
- Worker count: 4 FCM workers (redundancy + connection pool management)
```

**APNs configuration:**

```
- HTTP/2 persistent connection pool: 20 connections
- Throughput: ~500 req/sec × 100 tokens ≈ 50,000 tokens/sec
- Worker count: 3 APNs workers sharing the connection pool
- Priority header: 10 (immediate) for P0/P1; 5 (power-saving) for P2
- Collapse key: {notification_type}:{entity_id} — collapses stale like/follow
  notifications of the same type on the same entity
```

**APNs JWT Token Handling (corrected from previous version):**

The previous version said "rotate keys