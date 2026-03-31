# Notification System Design Proposal — Version 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling an estimated 20M–170M notification events/day across push, email, in-app, and SMS channels. The wide range reflects a genuine unresolved question about fanout behavior that previous versions papered over with inconsistent arithmetic. We now model fanout explicitly, commit to a specific design point, and acknowledge where we're making assumptions that require empirical validation.

The core architectural choices:

- **Per-channel worker pools** with priority enforced via sorted set score, not worker subdivision. The previous version's "15/30/15 worker subdivision" created a false choice between idle P0 workers and meaningless priority labels. Workers within a channel pool are fungible; priority is a queue property, not a worker property.
- **Redis AOF persistence with fsync=everysec** for all queue sorted sets. The previous version left this unspecified, creating a silent data loss scenario on crash.
- **WebSocket connection registry with explicit gap detection**, replacing the previous version's conflation of "no registry entry" with "offline."
- **Shared suppression cache via Redis** rather than per-worker in-process caches, which only narrowed the race condition they claimed to solve.

**What we're deliberately not building:** A/B testing infrastructure, ML send-time optimization, per-user engagement scoring. These require a functioning baseline. We build the baseline.

---

## 1. Scale Assumptions and Constraints

### 1.1 Fanout Math — Corrected

The previous version contained a contradiction it acknowledged without resolving: it claimed "17 events/DAU/day represents events *received* per active user" but then multiplied 3M DAU × 17 = 51M. If non-DAU users receive notifications from DAU activity, the recipient pool is MAU-scale, not DAU-scale.

We resolve this by separating *event generation* from *notification delivery* and being explicit about which users appear in each count.

**Event generation (actor side):**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio, typical social apps |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows — actions taken |
| Raw social actions/day | ~15M | 3M × 5 |

**Notification fanout (recipient side):**

Each social action generates notifications to one or more recipients. The fanout multiplier is the critical unknown:

| Action Type | Fanout | Basis |
|-------------|--------|-------|
| Follow | 1 | One notification to the followee |
| Comment on your post | 1 | One notification to post author |
| Like on your post | 1 (or 0 if batched) | One notification, or batched into "X and 3 others liked" |
| Mention in comment | 1–N | One per mentioned user |
| Post to followers (feed notification) | 0–F | F = follower count; most social apps don't notify all followers |

**Key design decision we're making now:** We do **not** send per-follower notifications for posts. This is the difference between 15M actions/day and 170M+ notifications/day. Feed-based content discovery is handled by feed ranking, not push notifications. Only direct social interactions (follows, comments, mentions, likes on your content) generate notifications.

With this constraint, the average fanout is approximately 1.2 (accounting for mentions reaching multiple users):

**Recipient-notification events/day: 15M actions × 1.2 fanout = ~18M events/day**

This replaces the previous "51M" figure, which was derived from the wrong direction (events received per DAU, not events generated per DAU with fanout applied to the recipient pool).

**Opt-out and channel filtering — corrected framing:**

The previous version described 40% opt-out as "conservative planning." This is wrong. Higher opt-out means fewer notifications and lower load. For capacity planning, the conservative choice is the scenario that maximizes load — the lowest opt-out rate.

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3× average) |
|-------------|----------|--------------------------|-------------------|
| 20% | **Design ceiling — highest load** | ~14.4M | ~500/sec |
| 40% | Base case | ~10.8M | ~375/sec |
| 60% | Lower bound | ~7.2M | ~250/sec |

**We design for the 20% opt-out scenario (14.4M/day, 500/sec peak) as our capacity ceiling.** This is the conservative choice: if opt-out is higher, we're over-provisioned. If opt-out is lower than 20%, we have a problem — but 20% is already at the optimistic end of the industry range for social apps with reasonable notification quality. If we hit below 20% opt-out, we have a different kind of problem (our notifications are unusually welcome) and can scale workers horizontally within the same architecture.

**Channel distribution — 20% opt-out scenario (14.4M/day):**

| Channel | % | Volume/day | Peak/sec |
|---------|---|------------|----------|
| Push | 65% | ~9.4M | ~325 |
| In-app | 25% | ~3.6M | ~125 |
| Email | 9% | ~1.3M events | ~45 events/sec |
| SMS | <0.01% | ~1,500 | negligible |

### 1.2 Email Channel — Consistent Numbers

The previous version showed three irreconcilable email figures: 2.8M events, 700K–1.4M emails after batching, and worker sizing implying ~10M emails/day. We establish one consistent figure.

**Email events:** 9% of 14.4M = ~1.3M events/day at the 20% opt-out design ceiling.

**Batching into digests:** Email notifications for likes and comments are batched into digests with a 15-minute aggregation window. A user who receives 20 likes on a post in 15 minutes gets one digest email, not 20 individual emails. Estimated batching reduction: 3–5× for high-engagement users, 1× for low-engagement users. Realistic average: ~2.5× reduction.

**Delivered emails/day:** 1.3M events ÷ 2.5 = ~520K emails/day at the design ceiling.

**Email worker sizing:** 520K/day = ~6 emails/sec average, ~18/sec peak (3×). At 100ms/email (SES API call + template rendering), one worker handles 10 emails/sec. We provision 5 email workers with headroom. This replaces the previous "116/sec peak" figure, which was internally inconsistent with the stated email volume.

### 1.3 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; shared suppression cache |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination (unchanged, included for completeness):** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`). E3 owns suppression state. E2's workers publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes suppression records. Neither engineer writes directly into the other's domain.

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
  - Preference check (Redis cache, TTL=5min, write-through invalidation)
  - Suppression check (shared Redis Hash, see §3.1)
  - Priority assignment
  - Aggregation window check
  - Channel selection → enqueue to channel-specific sorted set
     │
     ├──────────────┬──────────────┬─────────────────┐
     ▼              ▼              ▼                  ▼
[Push Queue]  [Email Queue]  [SMS Queue]    [In-App Store]
(Redis sorted  (Redis sorted  (Redis sorted  (PostgreSQL,
 set, AOF)     set, AOF)      set, AOF)      partitioned)
     │              │              │                  │
     ▼              ▼              ▼            Redis Streams
[Push Workers] [Email Workers] [SMS Workers]  → WebSocket servers
(APNs/FCM)    (SES/Postmark)  (Twilio)       (see §2.3)
     │              │              │
     └──────────────┴──────────────┘
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3)
                    │
                    ▼
           [Feedback Processor]
           (bounces, 410s, invalidity
            → shared suppression cache
            → PostgreSQL suppression records)
```

### 2.2 Queue Persistence — Filling the Gap

The previous version used Redis sorted sets as primary queues without specifying persistence configuration. In a crash-before-persist scenario with default RDB snapshotting (every 60 seconds), up to 60 seconds of enqueued notifications are lost with no recovery path.

**Configuration: AOF with fsync=everysec**

```
redis.conf (notification queue Redis instance):
  appendonly yes
  appendfsync everysec
  no-appendfsync-on-rewrite no
  auto-aof-rewrite-percentage 100
  auto-aof-rewrite-min-size 64mb
```

**What this buys us:** On crash, we lose at most ~1 second of enqueued notifications. At 500/sec peak, that is ~500 notifications. These are recoverable via the originating event log (see below), but the AOF reduces the recovery window to near-zero under normal operation.

**What this costs us:** AOF with fsync=everysec adds ~1–2ms of write latency per enqueue operation on commodity SSDs. At our throughput (500/sec peak), this is acceptable. It also increases disk I/O; E4 provisions SSDs for the queue Redis instance specifically.

**Recovery path for the AOF gap:** The Event Ingestion API writes all incoming events to PostgreSQL before enqueuing to Redis. This is the authoritative event log. On Redis restart, a recovery job (E4 owns) queries the event log for events in state `enqueued` with no corresponding delivery log entry and re-enqueues them. This job runs automatically on Redis reconnect and is idempotent because delivery workers check for existing delivery log entries before processing.

**Why not Redis Cluster for queue durability:** Redis Cluster with replicas provides availability, not durability. A synchronous write to a replica before acknowledging the enqueue (WAIT command) approaches synchronous replication but adds latency proportional to network RTT to the replica. AOF on a single instance with a PostgreSQL event log backstop gives us durability with predictable latency at our scale. Cluster becomes relevant when we exceed single-instance throughput limits, which at 500/sec we do not.

### 2.3 Priority Enforcement — Corrected Design

The previous version claimed "15 P0, 30 P1, 15 P2/P3 workers" where "P0 pool drains its queue before P1 workers pick up P1 work." This is incoherent: either they are separate pools (P0 workers sit idle most of the time, since P0 push notifications essentially don't exist — P0 events go to SMS/email) or they share a pool (the subdivision numbers are meaningless).

**Corrected design: fungible workers with priority-ordered dequeue**

Workers within a channel pool are fungible. Priority is a property of the queue, not the worker. Each push worker executes the same dequeue loop:

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
            # ZPOPMIN returns lowest score (earliest enqueue time) in the set
            result = redis_client.zpopmin(queue, count=1)
            if result:
                notification = result[0]
                break
        if notification:
            process(notification)
        else:
            time.sleep(0.01)  # 10ms backoff when all queues empty
```

**What this achieves:** P0 notifications are always processed before P1, P1 before P2, and so on, regardless of which worker picks them up. No worker is dedicated to a priority tier and sits idle waiting for P0 events that rarely arrive on the push channel.

**What we give up:** Guaranteed P0 processing time is now a function of total worker pool utilization, not a dedicated pool. If all 60 push workers are busy processing P1 notifications and a P0 push arrives, it waits until a worker finishes its current P1 notification (~50ms). This is acceptable because, as noted, P0 events (security alerts, auth codes) are routed to SMS and email, not push. Push P0 would be something like "your account has been logged into from a new device" — important, but a 50ms delay behind a P1 notification is not a safety-critical failure.

**Worker pool sizing — revised for corrected volumes:**

At the 20% opt-out design ceiling (14.4M/day, 500/sec peak):

| Channel | Peak Volume/sec | Time/notification (estimated) | Workers needed | Provisioned |
|---------|----------------|-------------------------------|----------------|-------------|
| Push | ~325 | 50ms | 17 | 30 |
| Email | ~18 | 100ms | 2 | 5 |
| SMS | <1 | 200ms | 1 | 3 |

We provision 30 push workers (versus the calculated minimum of 17) to maintain headroom for retry bursts and APNs/FCM latency spikes. E4 owns a post-Phase-1 calibration task: measure actual processing times under load, recalculate, and resize. These are starting points.

### 2.4 WebSocket Fan-Out — Gap Detection Added

The previous version stated: "If no registry entry: user is offline; skip stream publish." This conflates two distinct states: (a) user is genuinely offline, and (b) user is online but the registry entry hasn't been written yet or just expired due to a missed heartbeat. The previous version treated both as equivalent with no mechanism to detect when (b) occurs.

**Corrected design: connection registry with explicit gap handling**

```
Connection Registry (Redis Hash, per-user):
  Key: ws:user:{user_id}
  Value: {
    server_id: "ws-03",
    connected_at: timestamp,
    last_heartbeat: timestamp,
    state: "connected" | "connecting"
  }
  TTL: 90 seconds, refreshed every 30 seconds by WebSocket server heartbeat

Connection state machine:
  - Client initiates WebSocket handshake:
      → Server writes state="connecting", TTL=90s
      → Handshake completes: server updates to state="connected"
      → Gap window: between "connecting" write and "connected" write (~10–50ms)
  - Client disconnects cleanly:
      → Server deletes registry entry immediately
  - Server crash or missed heartbeat:
      → TTL expires after 90 seconds; entry deleted automatically
```

**Delivery flow with explicit gap handling:**

```
1. Router looks up ws:user:{user_id}
2. Three cases:

   Case A — Entry exists, state="connected":
     → Publish to ws:events:{server_id} stream
     → Normal delivery path

   Case B — Entry exists, state="connecting":
     → Do NOT publish to stream yet
     → Write notification to PostgreSQL (in-app inbox, persistent)
     → Enqueue a deferred check: after 5 seconds, re-check registry
     → If now "connected": publish to stream (client will receive it)
     → If still "connecting" after 10s: treat as offline; notification
       already in PostgreSQL inbox, client will retrieve on reconnect

   Case C — No