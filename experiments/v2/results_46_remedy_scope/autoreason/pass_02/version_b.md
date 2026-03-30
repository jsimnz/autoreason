# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions are:

1. **Four isolated priority queues** (P0–P3 are genuinely separate), because P3 digest TTL semantics differ from P2 and silently sharing a queue loses data
2. **Two-phase dequeue replaced with atomic payload storage** — the prior design had a crash window between RPOP and payload fetch that caused silent message loss
3. **Worker pools are per-channel, deployed behind per-priority queues** — the capacity math and deployment topology are reconciled into a single model
4. **In-app headroom corrected to match other channels** — the prior 1.9× figure was an asymmetry without justification
5. **Redis failover acknowledged as a P0 delivery risk** with a concrete mitigation strategy
6. **SMS volume cut 80–90% before launch** — the economics of 1M SMS/day are incompatible with a startup budget
7. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL

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

**Per-worker throughput assumptions:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2, 20-conn pool, individual requests | ~500 tokens/sec across pool |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput correction:** The prior version claimed ~50,000 tokens/sec for APNs, which is nonsensical. APNs has no batch API — every notification is an individual HTTP/2 request. At 20 persistent connections with realistic ~40ms RTT per request, the pool delivers approximately 500 requests/second. Peak APNs demand is ~350/sec, giving 1.4× headroom — thin but acceptable because APNs is iOS-only (roughly half of push volume) and we can add connections cheaply. This is monitored with a latency alert at 300/sec sustained.

**Demand vs. capacity:**

| Channel | Peak demand | Workers | Peak capacity | Headroom |
|---------|-------------|---------|---------------|----------|
| FCM push | ~1,215/sec | 4 | ~8,000/sec | 6.6× |
| APNs push | ~350/sec | 3 (shared pool) | ~500/sec | 1.4× |
| Email | ~138/sec | 2 | ~2,000/sec | 14× |
| SMS | ~4/sec | 1 | ~67/sec | 16× |
| In-app | ~350/sec | 4 | ~4,000/sec | 11× |

**In-app demand correction:** The prior version showed in-app at 1,040/sec peak demand against 2,000/sec capacity (1.9× headroom) while every other channel had 6× minimum, with no explanation for the asymmetry. The error was in the demand calculation: in-app notifications are only delivered to logged-in users. At 3M DAU with ~20% concurrently active during peak, ~600K users are online. In-app demand is 10M/day × 3 peak × (600K/3M active fraction) / 86,400 = ~350/sec. We assign 4 workers for 11× headroom, consistent with other channels. The prior 1,040/sec figure incorrectly applied the peak multiplier to total daily volume without accounting for the active-user constraint.

**Total: 14 workers** with explicit capacity bounds. We provision 2× headroom = **28 workers total**, deployed as separate processes with independent scaling. The APNs connection pool is explicitly flagged for monitoring given its thinner headroom.

### Queue Drain Analysis (Corrected)

At 50M/day baseline, normal rate is ~578/sec. During a 3× peak, total throughput is ~1,734/sec. The **excess above baseline** is ~1,156/sec. Over a 2-hour sustained peak (7,200 seconds), the queue accumulates ~8.3M notifications above baseline. (The prior version stated 12.6M, which was total peak volume, not excess — an error that inflated the drain estimate.)

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

All four engineers are on-call. E4 writes the runbooks; everyone executes them. Chaos testing is deferred to month 5.

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

This reconciles the per-channel sizing with the per-priority deployment topology. These are the same workers described from two angles.

| Priority queue | Notification types | Channel workers assigned | Total workers |
|---------------|-------------------|--------------------------|---------------|
| P0 | OTP, security alert, payment confirm | 1 FCM + 1 APNs (shared pool) | 2 |
| P1 | DM, mention, comment reply | 3 FCM + 2 APNs + 2 in-app + 1 SMS | 8 |
| P2 | Comment, like, follow | 1 FCM + 1 email + 2 in-app | 4 (+ shared email) |
| P3 | Digest, re-engagement | 2 email + 2 in-app | 4 (+ shared email) |

**Clarification on "shared" workers:** FCM and APNs workers serve their respective queues in priority order — a P0 FCM worker only dequeues from P0. P1 FCM workers only dequeue from P1. They are separate process instances, not a shared pool with priority-based routing. The per-channel capacity numbers in §1 reflect the aggregate across all priority tiers for that channel.

### Why Four Queues, Not One Sorted Set

The single-queue-with-priority-scoring approach fails under backpressure — exactly when it matters most. A P0 security alert in a Redis sorted set competes for the same lock as thousands of P2 like notifications.

Four separate Redis Lists give us:
- **Hard isolation:** P0 workers only touch the P0 queue. A P2 burst cannot delay P0 delivery.
- **Correct TTL semantics per priority:** P3 digests get 48-hour TTL; P2 notifications get 24-hour TTL. These are different business requirements that cannot share a queue without silent expiry errors (see §3.1).
- **Independent scaling:** Adding P1 workers requires no P0 configuration changes.

**The cost:** Four worker pools, four dead-letter queues, four sets of metrics. Manageable with managed infrastructure.

**What we give up:** Perfect global ordering within a priority band across channels. A P1 push might be processed before a P1 email that arrived 5 seconds earlier. Per-channel ordering within a priority band is sufficient for a social app.

---

## 3. Queue Implementation

### 3.1 Enqueue with Correct TTL Semantics

The prior version aliased P3 to P2's queue (`"P3": "queue:p2"`) while maintaining separate TTL entries for each. This caused P3 notifications to expire on P2's 24-hour schedule because the TTL lookup used the notification's priority but the queue name resolved identically — the distinction existed in the code but not in the data. Digests scheduled for 48-hour delivery would silently expire. The fix is four genuinely separate queues.

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
    "P3": 172800,   # 48 hours — digests and re-engagement need longer window
}

def enqueue(notification: Notification) -> None:
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

### 3.2 Dequeue: Eliminating the Crash Window

The prior version had a two-phase pattern: RPOP the ID from the queue, then fetch the payload in a separate pipeline. Between those two operations, the notification ID was held by no one — removed from the queue but not yet retrieved. A worker crash at that point caused permanent, silent message loss with no DLQ entry and no retry path. The design claimed RPOP atomicity as a delivery guarantee, but the guarantee only covered the dequeue step, not the full receive operation.

**Fix: Store the full payload in the queue, not just the ID.**

This eliminates the second round-trip entirely. There is no window between dequeue and payload retrieval because payload retrieval is the dequeue operation.

```python
def enqueue(notification: Notification) -> None:
    queue_name = PRIORITY_QUEUES[notification.priority]
    ttl = QUEUE_TTLS[notification.priority]
    payload = notification.model_dump_json()

    pipe = redis.pipeline(transaction=True)
    # Store payload keyed by ID for deduplication lookups
    pipe.setex(f"ntf:{notification.id}", ttl, payload)
    # Push full payload onto queue — no separate fetch needed at dequeue time
    pipe.lpush(queue_name, payload)
    pipe.execute()
```

```lua
-- dequeue_batch.lua
-- KEYS[1]: queue name
-- ARGV[1]: batch size
-- Returns: list of notification payloads (full JSON, not IDs)

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