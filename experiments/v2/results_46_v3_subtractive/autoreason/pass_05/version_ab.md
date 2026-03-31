# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling an estimated 14M–18M notifications/day across push, email, in-app, and SMS channels. The range reflects genuine uncertainty about opt-out rates; the architecture is valid across the plausible range.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision. Dedicated priority pools create idle workers for rare high-priority events; fungible workers with priority-ordered dequeue are simpler and correct.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets, with a PostgreSQL event log as recovery backstop.
- **WebSocket connection registry with explicit gap detection**, distinguishing "connecting" from "connected" from "offline."
- **Per-channel queues** isolating channel failures. APNs degradation affects push workers only; email workers continue unaffected.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring. These require a functioning baseline. We build the baseline.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We separate *event generation* from *notification delivery* and are explicit about which users appear in each count.

**Event generation (actor side):**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU, typical social apps |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows — actions taken |
| Raw social actions/day | ~15M | 3M × 5 |

**Notification fanout (recipient side):**

Each social action generates notifications to one or more recipients. Key design decision made now: we do **not** send per-follower notifications for posts. Feed-based content discovery is handled by feed ranking. Only direct social interactions (follows, comments, mentions, likes on your content) generate notifications. With this constraint, average fanout is approximately 1.2 (accounting for mentions reaching multiple users).

**Recipient-notification events/day: 15M actions × 1.2 fanout = ~18M events/day**

**Opt-out sensitivity — correct framing for capacity planning:**

Higher opt-out means lower load. The conservative planning choice is the scenario that maximizes load — the lowest opt-out rate.

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | **Design ceiling — highest load** | ~14.4M | ~500/sec |
| 40% | Base case | ~10.8M | ~375/sec |
| 60% | Lower bound | ~7.2M | ~250/sec |

**We design for the 20% opt-out scenario (14.4M/day, 500/sec peak).** If opt-out is higher, we're over-provisioned. If opt-out is below 20%, we scale workers horizontally within the same architecture.

We measure actual opt-out rates during Phase 1 rollout and recalibrate before scaling to full MAU. Architecture does not change; only worker pool sizing and Redis provisioning change.

**Channel distribution — 20% opt-out design ceiling (14.4M/day):**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events → ~520K emails | ~18/sec peak |
| SMS | <0.01% | ~1,500 | negligible |

**Email batching:** Likes and comments are batched into 15-minute digest windows. Estimated average batching reduction: 2.5×. Delivered emails/day: 1.3M ÷ 2.5 = ~520K.

**SMS cost ceiling:** At $0.0075/message (Twilio), 1,500/day = ~$340/month. Staying well below this ceiling is a deliberate constraint.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`) and publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes suppression records. Neither engineer writes directly into the other's domain.

**Timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §6 for explicit contingencies.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]  ──────────────────────────────────────┐
(writes to PostgreSQL event log before enqueuing)            │
     │                                                        │
     ▼                                                        │
[Notification Router]                                         │
  - Preference check (Redis cache, TTL=5min, write-through)  │
  - Suppression check (shared Redis Hash)                     │
  - Priority assignment                                       │
  - Aggregation window check                                  │
  - Channel selection → enqueue to channel-specific sorted set│
     │                                                        │
     ├──────────────┬──────────────┬─────────────────┐       │
     ▼              ▼              ▼                  ▼       │
[Push Queue]  [Email Queue]  [SMS Queue]    [In-App Store]   │
(Redis sorted  (Redis sorted  (Redis sorted  (PostgreSQL,    │
 set, AOF)     set, AOF)      set, AOF)      partitioned)    │
     │              │              │                  │       │
     ▼              ▼              ▼            Redis Streams │
[Push Workers] [Email Workers] [SMS Workers]  → WebSocket    │
(APNs/FCM)    (SES/Postmark)  (Twilio)         servers      │
     │              │              │                          │
     └──────────────┴──────────────┘                         │
                    │                                         │
                    ▼                                         │
           [Delivery Log]  ◄────────────────────────────────-┘
           (PostgreSQL + S3)    (recovery: re-enqueue events
                    │            in state=enqueued with no
                    ▼            delivery log entry)
           [Feedback Processor]
           (bounces, 410s, invalidity
            → shared suppression cache
            → PostgreSQL suppression records)
```

### 2.2 Why Per-Channel Queues

If APNs is rate-limited or degraded, push notifications back up. In a single shared queue, this blocks email notifications at the same priority tier — head-of-line blocking across channels. Per-channel queues isolate this failure. The operational cost is monitoring four queue depths instead of one: a real but manageable difference.

**What we don't get:** Cross-channel priority enforcement. A P0 email cannot preempt a P1 push in the push worker pool. This is acceptable because P0 events (security alerts, auth codes) are routed to SMS or email, not push. Push is never the sole channel for P0 events.

### 2.3 Queue Persistence

Redis sorted sets as primary queues without persistence configuration create a silent data loss scenario: with default RDB snapshotting (every 60 seconds), up to 60 seconds of enqueued notifications are lost on crash with no recovery path.

**Configuration: AOF with fsync=everysec**

```
redis.conf (notification queue Redis instance):
  appendonly yes
  appendfsync everysec
  no-appendfsync-on-rewrite no
  auto-aof-rewrite-percentage 100
  auto-aof-rewrite-min-size 64mb
```

On crash, we lose at most ~1 second of enqueued notifications (~500 at peak). Cost: ~1–2ms added write latency per enqueue on commodity SSDs, plus increased disk I/O. E4 provisions SSDs for the queue Redis instance. Acceptable at our throughput.

**Recovery path:** The Event Ingestion API writes all incoming events to PostgreSQL before enqueuing to Redis. On Redis restart, a recovery job queries for events in state `enqueued` with no corresponding delivery log entry and re-enqueues them. This job runs automatically on Redis reconnect and is idempotent because delivery workers check for existing delivery log entries before processing.

**Why not Redis Cluster:** Cluster with replicas provides availability, not durability. AOF on a single instance with a PostgreSQL event log backstop gives durability with predictable latency at our scale. Cluster becomes relevant when we exceed single-instance throughput limits; at 500/sec peak we do not.

### 2.4 Priority Enforcement

Workers within a channel pool are fungible. Priority is a property of the queue, not the worker. Each worker executes the same dequeue loop:

```python
def dequeue_loop(redis_client, channel):
    queues = [
        f"notify:{channel}:p0",  # sorted set, score = enqueue_timestamp
        f"notify:{channel}:p1",
        f"notify:{channel}:p2",
        f"notify:{channel}:p3",
    ]
    while True:
        notification = None
        for queue in queues:  # strict priority order
            result = redis_client.zpopmin(queue, count=1)
            if result:
                notification = result[0]
                break
        if notification:
            process(notification)
        else:
            time.sleep(0.01)  # 10ms backoff when all queues empty
```

P0 notifications are always processed before P1, regardless of which worker picks them up. No worker sits idle waiting for P0 events that rarely arrive on the push channel.

**What we give up:** If all push workers are busy on P1 and a P0 push arrives, it waits ~50ms. Acceptable: push P0 events (e.g., "new device login") are not safety-critical at 50ms granularity.

**Worker pool sizing — 20% opt-out design ceiling:**

| Channel | Peak Volume/sec | Time/notification (estimated) | Workers needed | Provisioned |
|---------|----------------|-------------------------------|----------------|-------------|
| Push | ~325 | 50ms | 17 | 30 |
| Email | ~18 | 100ms | 2 | 5 |
| SMS | <1 | 200ms | 1 | 3 |

We provision 30 push workers (versus the calculated minimum of 17) for retry burst headroom and APNs/FCM latency spikes. E4 owns a post-Phase-1 calibration task: measure actual processing times under load, recalculate, and resize. These are starting points.

### 2.5 WebSocket Fan-Out

**The routing problem:** WebSocket connections are stateful. User A's connection lives on server W3. A naive stream consumer group distributes messages across all consumers — W1 and W2 may dequeue a message intended for a user on W3, filter it, and discard it. W3 never receives it.

**The gap detection problem:** "No registry entry" conflates two distinct states: (a) user is genuinely offline, and (b) user is mid-handshake and the registry entry hasn't been written yet. Treating both as equivalent causes silent notification loss during connection establishment.

**Connection registry design:**

```
Key: ws:user:{user_id}
Value: {
  server_id: "ws-03",
  connected_at: timestamp,
  last_heartbeat: timestamp,
  state: "connected" | "connecting"
}
TTL: 90 seconds, refreshed every 30 seconds by WebSocket server heartbeat

State transitions:
  - Client initiates handshake: server writes state="connecting"
  - Handshake completes: server updates to state="connected"
  - Client disconnects cleanly: server deletes registry entry
  - Server crash or missed heartbeat: TTL expires after 90s
```

**Delivery flow:**

```
1. Router looks up ws:user:{user_id}

   Case A — state="connected":
     → Publish to ws:events:{server_id} stream
     → WebSocket server consumes only its own stream (no cross-server filtering)
     → Client ACKs; server marks delivered in PostgreSQL
     → No ACK within 30s: notification remains unread in PostgreSQL inbox

   Case B — state="connecting":
     → Write notification to PostgreSQL inbox (persistent)
     → Enqueue deferred check: after 5 seconds, re-check registry
     → If now "connected": publish to stream
     → If still "connecting" after 10s: treat as offline; client retrieves on reconnect

   Case C — no registry entry (genuinely offline):
     → Write to PostgreSQL inbox; client retrieves on reconnect
```

**Failure modes:**
- Server crash between publish and client ACK: notification remains unread in PostgreSQL; no data loss.
- Stale registry entry (server crashed without cleanup): TTL expires in 90 seconds; next connection re-registers. Messages during this window go to offline path.
- Redis unavailable: client polls PostgreSQL inbox at 30-second intervals.

**Why Streams over Pub/Sub:** Streams allow replay of missed messages after a WebSocket server restart within the 90-second TTL window. After TTL expiry, the client reconnects and fetches from PostgreSQL. The Streams advantage is specifically for server restarts.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~65% of volume, ~9.4M/day)

**Provider:** FCM for Android, APNs for iOS. Direct integrations.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work and costs $50K–150K/year at our scale. We build direct integrations. If we slip on the 6-month timeline due to integration complexity, this is the first place we revisit — see §6.

**FCM v1:** Single-device API only; no batch endpoint. At ~6M Android push/day, that is ~70/sec average, ~210/sec peak. FCM's project-level quota is ~10,000/sec. We operate well within quota.

```
FCM runtime config:
- HTTP/2 multiplexed connections: 50 persistent connections
- On 404 (Unregistered) or InvalidRegistration:
    → publish token.invalidated event to Redis Stream immediately
    → mark token as pending-suppression in shared suppression cache
    → do not retry this token before feedback processor confirms
- On 429: exponential backoff starting at 1s, alert E4 if sustained >60s
- On 500/503: retry up to 3 times with backoff, then DLQ
```

**Shared suppression cache (not per-worker in-process cache):**

The previous approach used per-worker in-process caches to prevent redundant sends during the stream consumer lag window. This only narrows the race: two different workers with the same token in flight both check their local cache, find nothing, and both send. A shared Redis Hash (`suppress:tokens`, keyed by token) is checked by all workers before sending and written immediately on invalidity detection. The feedback processor then writes the durable PostgreSQL suppression record asynchronously.

```
Suppression check order (per notification):
1. Check shared Redis Hash suppress:tokens:{token_hash} — skip if present
2. Send notification
3. On invalidity response: HSET suppress:tokens:{token_hash} 1 EX 86400
4. Publish token.invalidated to Redis Stream for feedback processor
```

**APNs JWT Token Management:**

- **`.p8` signing key:** Does not rotate on a schedule. Stored in AWS Secrets Manager. Rotated only if compromised.
- **JWT token:** Expires after 1 hour. Regenerated every 45 minutes by a single background job writing to a shared Redis key.
- **Worker token cache:** Workers use a local in-process cache with a 30-second TTL, picking up new tokens within 30 seconds of