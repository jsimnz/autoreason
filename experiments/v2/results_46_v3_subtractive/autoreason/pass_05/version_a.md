# Notification System Design Proposal — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling an estimated 15M–30M notifications/day across push, email, in-app, and SMS channels. The wide range is intentional: we don't know our opt-out rate yet, and the architecture must be valid across the plausible range rather than optimized for a single point estimate.

The core architectural bet: **per-channel worker pools sharing a priority scoring system**, rather than a single shared queue or a complex event streaming topology. The previous design's "single queue" framing created a real head-of-line blocking problem — APNs degradation would starve email delivery within the same priority tier. Per-channel pools isolate channel failures at the cost of slightly more operational surface area. At our team size, that tradeoff is worth it.

**What we're deliberately not building:** A/B testing infrastructure, ML-based send-time optimization, per-user engagement scoring. These are real features with real value; they're also features that require a functioning baseline first. We build the baseline.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling — Honest About Uncertainty

The previous version derived 50M notifications/day from a 2% opt-out assumption with no cited basis. Industry figures for mobile push opt-out rates range from 30% to 60% depending on app category, platform, and notification quality. We don't know our number. We model a range.

**Base event generation:**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU, typical social apps |
| Social events per active user per day | ~17 | Likes, comments, follows, mentions |
| Raw notification events/day | ~51M | 3M DAU × 17 |

**Fanout clarification:** The 51M figure is *recipient-notification events*, not actor events. One user's post receiving 100 likes generates 100 notifications to the post author (or a batched aggregate). One follow generates one notification to the followee. The 17 events/DAU/day figure represents events *received* per active user, not events generated. Non-DAU recipients receive notifications triggered by DAU activity — this is why recipient count (MAU-scale) exceeds actor count (DAU-scale).

**Opt-out sensitivity analysis:**

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | Optimistic | ~41M | ~1,430/sec |
| 40% | Base case | ~31M | ~1,080/sec |
| 60% | Pessimistic | ~20M | ~700/sec |

**We design for the 40% base case and verify the system remains operable at the 20% optimistic scenario.** If we're wrong in the pessimistic direction, we're over-provisioned; if we're wrong in the optimistic direction, we have a real capacity problem. The 40% base case is the conservative planning choice.

We will measure actual opt-out rates during the Phase 1 rollout (§7) and recalibrate before scaling to full MAU. The architecture does not change; only worker pool sizing and Redis provisioning change.

**Channel distribution — base case (31M/day):**

| Channel | % | Volume/day | Notes |
|---------|---|------------|-------|
| Push | 65% | ~20M | Users with push tokens who haven't opted out |
| In-app | 25% | ~7.7M | Written for all DAU; persistent inbox |
| Email | 9% | ~2.8M events → ~700K–1.4M emails | Batched into digests |
| SMS | <0.01% | ~2,000 | Auth/security only; hard cost ceiling |

**SMS cost ceiling:** At $0.0075/message (Twilio), 2,000/day = $450/month. Staying far below this ceiling is a deliberate constraint, not an optimization.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; preference cache invalidation |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`). E3 owns suppression state. E2's workers publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes suppression records. Neither engineer writes directly into the other's domain.

**Honest timeline risk:** APNs provisioning, FCM project configuration, and email IP warming all involve external parties. See §7 for explicit contingencies.

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
  - Suppression check
  - Priority assignment
  - Aggregation window check
  - Channel selection → enqueue to channel-specific queue
     │
     ├──────────────┬──────────────┬─────────────────┐
     ▼              ▼              ▼                  ▼
[Push Queue]  [Email Queue]  [SMS Queue]    [In-App Store]
(Redis sorted  (Redis sorted  (Redis sorted  (PostgreSQL,
 set, per-     set, per-      set, per-      partitioned)
 priority)     priority)      priority)           │
     │              │              │         Redis Streams
     ▼              ▼              ▼         → WebSocket servers
[Push Workers] [Email Workers] [SMS Workers]  (see §2.3)
(APNs/FCM)    (Postmark/SES)  (Twilio)
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
            → suppression, token cleanup)
```

### 2.2 Why Per-Channel Queues, Not a Single Queue

The previous version argued for a single priority queue on grounds of operational simplicity. That argument has a real flaw: if APNs is rate-limited or degraded, push notifications back up in the shared queue and block email notifications at the same priority tier from being processed. This is head-of-line blocking across channels within a priority level.

Per-channel queues isolate this failure. APNs degradation affects push workers only; email workers continue draining their queue unaffected. The operational cost is monitoring four queue depths instead of one — a real but manageable difference.

**What we don't get with per-channel queues:** Cross-channel priority enforcement. A P0 email cannot preempt a P1 push in the push worker pool. In practice, this is acceptable: P0 notifications (security alerts, auth codes) go to SMS or email, not push. Push is never the sole channel for P0 events.

**Worker pool sizing — derived, not guessed:**

Previous version specified 20/40/20 workers with no derivation. Here is the derivation for the base case (31M/day, 1,080/sec peak):

Assumptions requiring measurement and revision after Phase 1:
- Push: 50ms average end-to-end per notification (FCM/APNs API call + overhead)
- Email: 100ms average (SES/Postmark API call + template rendering)
- SMS: 200ms average (Twilio API call)

At 50ms/notification, one push worker handles 20 notifications/sec. At 1,080/sec peak with 65% going to push (702/sec), we need at minimum 36 push workers. We provision 60 to maintain headroom and absorb retry bursts.

| Channel | Peak Volume/sec | Time/notification | Workers needed | Provisioned |
|---------|----------------|------------------|----------------|-------------|
| Push | ~702 | 50ms | 36 | 60 |
| Email | ~116 | 100ms | 12 | 20 |
| SMS | <1 | 200ms | 1 | 5 |

These numbers are estimates based on assumed processing times. E4 owns a post-Phase-1 calibration task: measure actual processing times under load, recalculate, and resize. **We treat these as starting points, not targets.**

Within each channel, workers are divided by priority tier: push has 15 P0, 30 P1, 15 P2/P3 workers. Priority within a channel is enforced by sorted set score; the P0 pool drains its queue before P1 workers pick up P1 work.

### 2.3 WebSocket Fan-Out — Routing Problem Acknowledged and Solved

The previous version cited Redis Streams over Pub/Sub for acknowledged delivery but did not explain how a stream consumer group routes a message to the specific WebSocket server holding a user's connection. This is a real architectural gap. Here is the explicit design:

**The problem:** WebSocket connections are stateful. User A's connection lives on WebSocket server W3. A Redis Stream consumer group distributes messages across all consumers — but if W1 and W2 consume a message intended for a user connected to W3, they filter it out and do nothing. This is O(servers × messages) processing at worst, and it means W3 never receives the message unless it's the consumer that happens to dequeue it.

**The solution: connection registry with targeted delivery**

```
Connection Registry (Redis Hash, per-user):
  Key: ws:user:{user_id}
  Value: {server_id: "ws-03", connected_at: timestamp, ttl: 90s}
  TTL: refreshed every 60s by the WebSocket server heartbeat

Delivery flow:
1. In-App Store writes notification to PostgreSQL
2. Router publishes to Redis Stream: stream key = ws:events:{server_id}
   - Looks up ws:user:{user_id} to find server_id
   - If no registry entry: user is offline; skip stream publish
     (client polls on reconnect, or receives on next connection)
3. Each WebSocket server consumes only its own stream (ws:events:{server_id})
   - No cross-server message filtering
   - O(messages_for_this_server) processing, not O(total_messages)
4. WebSocket server delivers to connected client
5. Client ACKs; server marks notification delivered in PostgreSQL
6. If no ACK within 30s: message remains unread in PostgreSQL inbox
   (client retrieves on next poll or reconnect — no redelivery attempt via stream)
```

**Failure modes:**
- Server crash between stream publish and client ACK: notification remains unread in PostgreSQL; client retrieves on reconnect. No data loss.
- Registry entry stale (server crashed without cleanup): TTL expires in 90 seconds; next connection attempt re-registers. Messages during this window go to offline path.
- Redis unavailable: fall back to client polling at 30-second intervals. In-app inbox is always available from PostgreSQL.

**Why not Pub/Sub:** Pub/Sub is appropriate here if we accept that offline users simply miss the real-time signal and retrieve on reconnect. We use Streams because the consumer group semantics allow us to replay missed messages after a WebSocket server restart — but only for the 90-second window before the connection registry TTL expires. After that, the client reconnects and fetches from PostgreSQL. The Streams advantage is specifically for server restarts, not for extended offline periods.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~65% of volume, ~20M/day base case)

**Provider:** FCM for Android, APNs for iOS. Direct integrations.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work and costs $50K–150K/year at our scale. We build direct integrations. If we slip on the 6-month timeline due to integration complexity, this is the first place we revisit — see §7.

**FCM v1 — no batch endpoint:**

FCM v1 is a single-device API. There is no v1 batch endpoint. We send one HTTP/2 request per device. At ~13M Android push/day (65% of 20M), that is ~150/sec average, ~450/sec peak. FCM's project-level quota is 600,000 requests/minute (~10,000/sec). We operate well within quota.

```
FCM runtime config:
- HTTP/2 multiplexed connections: 50 persistent connections
- Target: ~10 concurrent streams per connection = ~500 concurrent in-flight
- On 404 (Unregistered) or error code InvalidRegistration:
    → publish token.invalidated event to Redis Stream immediately
    → mark token as pending-suppression in local worker cache
    → do not retry this token even before feedback processor confirms
- On 429: exponential backoff starting at 1s, alert E4 if sustained >60s
- On 500/503: retry up to 3 times with backoff, then DLQ
```

**Why mark pending-suppression in local worker cache:** The feedback processor consumes the Redis Stream asynchronously. Without local marking, the same worker (or another worker with the same token) can issue additional sends before the suppression record is written. The local cache (in-process, TTL=5 minutes) prevents redundant sends during the stream consumer lag window.

**APNs JWT Token Management:**

Three distinct layers:

- **`.p8` signing key:** Does not rotate on a schedule. Stored in AWS Secrets Manager. Rotated only if compromised.
- **JWT token:** Generated from the `.p8` key. Expires after 1 hour. Regenerated every 45 minutes.
- **Worker token cache:** Each worker fetches the current JWT from a shared Redis key (not per-worker regeneration). The Redis key is updated by a single background job. Workers use a local in-process cache with a 30-second TTL, ensuring they pick up new tokens within 30 seconds of regeneration.

```
APNs JWT regeneration monitoring (E4 owns):
- Heartbeat metric: emitted after every successful regeneration
- Alert P1: no successful regeneration in 50 minutes
- Alert P0: APNs 401 error rate > 1% (token rejected; indicates regeneration
  failure or clock skew)
- On P0 alert: pause iOS push delivery, queue notifications for retry,
  page E2 and E4 immediately
- On P1 alert: trigger manual regeneration runbook, do not yet pause delivery
```

```
APNs runtime config:
- apns-priority: 10 (immediate) for P0/P1; 5 (power-saving) for P2/P3
- apns-collapse-id: notification_type + entity_id
  (collapses redundant notifications of same type for same entity)
- On 410: publish token.invalidated with Apple-provided timestamp
  AND mark pending-suppression in local worker cache (same as FCM)
```

**Token lifecycle — active cleanup, not passive 90-day purge:**

```
Token lifecycle:
1. On FCM 404/InvalidRegistration or APNs 410:
   - Mark pending-suppression in local worker cache (immediate)
   - Publish token.invalidated event to Redis Stream
   - Feedback processor writes suppression record (within seconds under normal lag)

2. APNs 410 timestamp handling:
   - Apple provides timestamp of when the token became invalid
   - Tokens registered for the same device AFTER that timestamp are valid
   - Feedback processor records invalidity timestamp; suppresses only tokens
     with registered_at <= apple_invalidity_timestamp
   - New token registrations for the same device are not affected

3. Time-based backstop (30 days, not 90):
   - Nightly batch: purge tokens with last_used_at > 30 days AND no valid
     registration in the past 30 days
   - Catches uninstalls on platforms without explicit invalidity signals

4. Silent probe validation — platform restrictions acknowledged:
   APNs throttles background pushes aggressively and does not guarantee
   delivery for battery-optimized or background-restricted devices. FCM
   similarly does not guarantee data-only message delivery.

   Using non-delivery as a validity