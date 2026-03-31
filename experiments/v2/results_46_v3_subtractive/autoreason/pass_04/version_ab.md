# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling ~31M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **operational simplicity over theoretical elegance** and **incremental delivery** over a big-bang launch.

The core architectural bet: **per-channel worker pools sharing a priority scoring system**, rather than a single shared queue or a complex event streaming topology. A single shared queue creates head-of-line blocking — APNs degradation starves email delivery within the same priority tier. Per-channel pools isolate channel failures at the cost of slightly more operational surface area. At our team size, that tradeoff is worth it.

**What we're deliberately not building:** A/B testing infrastructure, ML-based send-time optimization, per-user engagement scoring. These require a functioning baseline first. We build the baseline.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Base event generation:**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU, typical social apps |
| Social events per active user per day | ~17 | Likes, comments, follows, mentions |
| Raw notification events/day | ~51M | 3M DAU × 17 |

**Fanout clarification:** The 51M figure is *recipient-notification events*, not actor events. One user's post receiving 100 likes generates 100 notifications to the post author (or a batched aggregate). The 17 events/DAU/day figure represents events *received* per active user. Non-DAU recipients receive notifications triggered by DAU activity — this is why recipient count (MAU-scale) exceeds actor count (DAU-scale).

**Opt-out sensitivity analysis:**

Industry push opt-out rates range from 30–60% depending on app category and notification quality. We don't know our number yet. We model a range.

| Opt-Out Rate | Scenario | Routed Notifications/Day | Peak (3×) |
|-------------|----------|--------------------------|-----------|
| 20% | Optimistic | ~41M | ~1,430/sec |
| 40% | Base case | ~31M | ~1,080/sec |
| 60% | Pessimistic | ~20M | ~700/sec |

**We design for the 40% base case and verify the system remains operable at the 20% scenario.** We measure actual opt-out rates during Phase 1 rollout (§7) and recalibrate before scaling to full MAU. The architecture does not change; only worker pool sizing and Redis provisioning change.

**Channel distribution — base case (31M/day):**

| Channel | % | Volume/day | Notes |
|---------|---|------------|-------|
| Push | 65% | ~20M | Users with push tokens who haven't opted out |
| In-app | 25% | ~7.7M | Written for all DAU; persistent inbox |
| Email | 9% | ~2.8M events → ~700K–1.4M emails | Batched into digests |
| SMS | <0.01% | ~2,000 | Auth/security only; hard cost ceiling |

**SMS cost ceiling:** At $0.0075/message (Twilio), 2,000/day = $450/month. This is a deliberate constraint.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting |
|----------|----------------------|---------------|
| E1 | Core pipeline, queue infrastructure, priority scoring | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email providers, Twilio) | Token lifecycle; invalidity signal detection |
| E3 | Preference management, user-facing API, suppression | Deduplication; preference cache invalidation |
| E4 | Reliability, monitoring, failure handling, DevOps | Worker pool sizing; runbooks; scaling triggers |

**Cross-domain coordination:** E2's delivery workers detect token invalidity signals (APNs 410, FCM `InvalidRegistration`). E3 owns suppression state. E2's workers publish structured `token.invalidated` events to a Redis Stream. E3's feedback processor consumes them via a named consumer group and writes suppression records. Neither engineer writes directly into the other's domain.

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
[Push Workers] [Email Workers] [SMS Workers]
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
           ← token.invalidated stream
           (bounces, 410s, invalidity
            → suppression, token cleanup)
```

### 2.2 Worker Pool Sizing

Previous drafts specified worker counts with no derivation. Here is the derivation for the base case (31M/day, 1,080/sec peak). Processing time assumptions require measurement and revision after Phase 1.

| Channel | Peak Volume/sec | Time/notification | Workers needed | Provisioned |
|---------|----------------|------------------|----------------|-------------|
| Push | ~702 | 50ms | 36 | 60 |
| Email | ~116 | 100ms | 12 | 20 |
| SMS | <1 | 200ms | 1 | 5 |

Within each channel, workers are divided by priority tier: push has 15 P0, 30 P1, 15 P2/P3. The P0 pool drains before P1 workers pick up P1 work. E4 owns a post-Phase-1 calibration task: measure actual processing times under load and resize.

### 2.3 In-App Notifications and WebSocket Fan-Out

In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They bypass the channel queues — no external API call needed, and routing them through a queue adds latency with no benefit.

**The routing problem:** WebSocket connections are stateful. A naive Redis Stream consumer group distributes messages across all consumers — if W1 and W2 consume a message for a user connected to W3, they discard it and W3 never receives it.

**Solution: connection registry with targeted delivery**

```
Connection Registry (Redis Hash, per-user):
  Key: ws:user:{user_id}
  Value: {server_id: "ws-03", connected_at: timestamp}
  TTL: 90s, refreshed every 60s by WebSocket server heartbeat

Delivery flow:
1. Router writes notification to PostgreSQL
2. Router looks up ws:user:{user_id} to find server_id
   - If no entry: user is offline; skip stream publish
     (client retrieves on reconnect via PostgreSQL inbox)
3. Router publishes to ws:events:{server_id} — server-specific stream
4. Each WebSocket server consumes only its own stream
5. Client ACKs; server marks notification delivered in PostgreSQL
6. No ACK within 30s: notification remains unread; no redelivery via stream
   (client retrieves on next poll or reconnect)
```

**Failure modes:**
- Server crash between publish and ACK: notification remains unread in PostgreSQL; client retrieves on reconnect. No data loss.
- Stale registry entry (server crashed without cleanup): TTL expires in 90 seconds; next connection re-registers.
- Redis unavailable: fall back to client polling at 30-second intervals. In-app inbox is always available from PostgreSQL.

**Why Redis Streams over Pub/Sub:** Streams allow replay after a WebSocket server restart within the 90-second TTL window. After that, the client reconnects and fetches from PostgreSQL. The Streams advantage is specifically for server restarts, not extended offline periods.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~65% of volume, ~20M/day)

**Provider:** FCM for Android, APNs for iOS. Direct integrations — no OneSignal or Braze initially.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work and costs $50K–150K/year at our scale. We build direct integrations and accept the upfront engineering cost. If we slip on the 6-month timeline due to integration complexity, this is the first place we revisit.

**FCM v1 — no batch endpoint:**

FCM v1 is a single-device API. At ~13M Android push/day, that is ~150/sec average, ~450/sec peak. FCM's project-level quota is 600,000 requests/minute. We operate well within quota.

```
FCM runtime config:
- HTTP/2 multiplexed connections: 50 persistent
- ~10 concurrent streams per connection = ~500 in-flight
- On 404 (Unregistered) or InvalidRegistration:
    → publish token.invalidated event to Redis Stream immediately
    → mark pending-suppression in local worker cache (in-process, TTL=5min)
    → do not retry this token
- On 429: exponential backoff starting at 1s; alert E4 if sustained >60s
- On 500/503: retry up to 3 times with backoff, then DLQ
```

**Why local pending-suppression cache:** The feedback processor consumes the Redis Stream asynchronously. Without local marking, the same worker (or another worker with the same token) can issue additional sends before the suppression record is written. The local cache prevents redundant sends during the stream consumer lag window.

**APNs JWT Token Management:**

Three distinct layers:

- **`.p8` signing key:** Does not rotate on a schedule. Stored in AWS Secrets Manager. Rotated only if compromised.
- **JWT token:** Generated from the `.p8` key. Expires after 1 hour. Regenerated every 45 minutes by a single background job and written to a shared Redis key.
- **Worker token cache:** Each worker fetches from the shared Redis key with a local in-process cache (30-second TTL). Workers pick up new tokens within 30 seconds of regeneration. No requests are interrupted during regeneration.

```
APNs JWT regeneration monitoring (E4 owns):
- Heartbeat metric emitted after every successful regeneration
- Alert P1: no successful regeneration in 50 minutes
- Alert P0: APNs 401 error rate > 1% (token rejected; indicates regeneration
  failure or clock skew)
- On P0 alert: pause iOS push delivery, queue for retry, page E2 and E4
- On P1 alert: trigger manual regeneration runbook; do not yet pause delivery
```

```
APNs runtime config:
- apns-priority: 10 (immediate) for P0/P1; 5 (power-saving) for P2/P3
- apns-collapse-id: notification_type + entity_id
- On 410: publish token.invalidated with Apple-provided timestamp
  AND mark pending-suppression in local worker cache
```

**Token lifecycle:**

```
1. On FCM 404/InvalidRegistration or APNs 410:
   - Mark pending-suppression in local worker cache (immediate)
   - Publish token.invalidated event to Redis Stream
   - Feedback processor writes suppression record within seconds

2. APNs 410 timestamp handling:
   - Apple provides the timestamp when the token became invalid
   - Tokens registered for the same device AFTER that timestamp are valid
   - Feedback processor records invalidity timestamp; suppresses only tokens
     with registered_at <= apple_invalidity_timestamp

3. Time-based backstop (30 days):
   - Nightly batch: purge tokens with last_used_at > 30 days and no valid
     registration in the past 30 days
   - Catches uninstalls on platforms without explicit invalidity signals
   - Owned by E4

4. Silent probe validation:
   - Weekly: send a silent push (content-available: 1, no alert) to tokens
     unused in the past 14 days
   - APNs throttles background pushes and does not guarantee delivery for
     battery-optimized devices; FCM similarly does not guarantee data-only
     message delivery. Non-delivery cannot be used as a validity signal.
     We use these probes only to collect explicit invalidity responses (410,
     InvalidRegistration), not to infer validity from silence.
```

### 3.2 Email (9% of volume — ~2.8M events/day, not 2.8M individual sends)

The 2.8M/day figure is notification events routed to email. Actual send volume is ~700K–1.4M emails/day depending on digest frequency distribution.

**Provider — cost-honest analysis:**

At ~30M–60M emails/month:

| Provider | Estimated Cost/Month | Deliverability Tooling | Ops Burden |
|----------|---------------------|----------------------|------------|
| SendGrid (enterprise) | ~$15,000–30,000 | Excellent | Low |
| AWS SES | ~$5,000–8,000 | Minimal | High |
| Postmark | ~$8,000–15,000 | Good | Low–Medium |
| Mailgun | ~$8,000–12,000 | Good | Low–Medium |

**Recommendation: Postmark for transactional, SES for digest.** Postmark has strong deliverability for transactional email (password resets, security alerts) where failure has direct user trust impact. SES handles high-volume digest sends at lower cost. Tradeoff: E2 maintains two email integrations. If budget constrains us to one provider, use SES with significant investment in IP warming, bounce monitoring, and suppression list management.

**Email types:**

| Type | Provider | Trigger | Frequency Cap |
|------|---------|---------|---------------|
| Transactional | Postmark | Immediate (password reset, account alert) | No cap |
| Activity digest | SES | Daily or weekly batch | User-controlled |
| Re-engagement | SES | 7-day inactivity | Max 1/week |
| Marketing | SES | Product announcements | Max 1/week |

**Digest batching logic:**

SES does not support idempotency keys. A retry after a network timeout produces a duplicate email. We use a two-phase commit pattern: record the send attempt before sending, use that record to detect and suppress duplicates on retry.

**Low-activity user problem:** Carry-forward logic silently fails for users who generate fewer than `MIN_DIGEST_ITEMS` events per week — events accumulate to the expiry and are dropped without sending. Fix: the 7-day expiry triggers a send regardless of item count.

```python
MIN_DIGEST_ITEMS = 3
MAX_CARRY_FORWARD_DAYS = 7

def build_and_send_daily_digest(user_id: str, date: date) -> SendResult:
    carried = fetch_carried_events(user_id)
    fresh = fetch_unbatched_events(user_id, date)
    all_events = carried + fresh

    if not all_events:
        return SendResult.SKIPPED_EMPTY

    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    valid_events = [e for e in all_events if e.created_at.date() >= cutoff]
    expired_events = [e for e in all_events if e.created_at.date() < cutoff]

    if expired_events:
        mark_events_expired(expired_events)

    if not valid_events:
        return SendResult.SKIPPED_ALL_EXPIRED

    oldest_carried = min(e.created_at.date() for e