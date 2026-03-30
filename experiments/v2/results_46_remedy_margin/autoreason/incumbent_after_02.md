# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Three deliberate architectural bets:

1. **Separate priority queues over a single scored queue** — a correctness decision, not a scale decision. A single sorted set cannot guarantee P0 latency when P2 workers hold in-flight batches.
2. **Managed providers over custom infrastructure** — SendGrid, Twilio, FCM/APNs direct. Engineering time goes to integration quality, not infrastructure plumbing.
3. **Incremental delivery** — working system by month 2, iterated through month 5, hardened in month 6.

**Two honest statements upfront:**

First, the 17 notifications/user/day figure that drives all sizing is a planning assumption, not a measured fact. Published figures vary enormously by product type and engagement tier. We instrument from day one and recalibrate against production data at month 2. Every sizing decision should be read as "correct at estimated volume, revisable at month 2."

Second, the operational surface described here is at the edge of what 4 engineers can safely own. Section 7 names what we cut and why, and specifically addresses the E4 scope problem. If scope is added mid-project, something on that list gets dropped — we name it explicitly rather than silently accept overcommitment.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Planning assumption; see calibration note |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike multiplier | 20× | 90-second burst; see spike handling |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### The 17/Day Figure: Calibration and Uncertainty

This number drives queue worker counts, Redis sizing, database partitioning, and cost projections. Getting it wrong by 3× means every sizing decision is wrong simultaneously.

**What we do about it:** instrument notification volume per user per day from the first week of beta. At month 2, recalibrate against measured data:

| Actual Volume | Action Required |
|---------------|-----------------|
| ≤ 2× estimate (≤ 100M/day) | Increase P1/P2 worker counts; Redis capacity unchanged |
| 2–5× estimate (100–250M/day) | Add Redis nodes; partition notifications table more aggressively; revisit SendGrid tier |
| > 5× estimate (> 250M/day) | Architecture review required; queue infrastructure may need replacement with Kafka |

We do not treat the 17/day estimate as validated until we have two weeks of production data.

### Spike Handling: Diurnal vs. Event-Driven

These are different problems requiring different solutions.

**Diurnal peaks (3×, ~1,750/sec):** Handled by steady-state worker pool sizing. Workers are always running; they absorb the curve.

**Event-driven spikes (up to 20×, ~11,700/sec, lasting 60–120 seconds):** The queue is the absorber, not the worker pool. During a spike, the router continues accepting events and enqueuing them — queue depth grows, worker pools process at their maximum sustained rate, and the queue drains over the following minutes. At 20× for 90 seconds, we accumulate approximately 1,053,000 additional items. At ~500 bytes per serialized notification, this is ~500MB of queue backlog — within a properly sized Redis instance.

**What we do not do:** auto-scale worker pools to chase a 90-second spike. Worker startup time (30–60 seconds for a container) means auto-scaled workers arrive after the spike has passed. We size for sustained peak and accept that event-driven spikes create queue depth that drains over 2–5 minutes.

**P0 behavior during spikes:** P0 items are never delayed by P2 queue depth. This is the architectural guarantee of separate queues — during a viral spike, P2 queue depth grows while P0 items still reach P0 workers within seconds.

### SMS Cost Reality

A naive estimate using Twilio's US rate ($0.0075/message) produces $7,500/day. This is wrong for a 10M MAU social app with international traffic. The blended rate depends entirely on geographic distribution, which we do not know before launch:

| Scenario | Blended Rate | Daily Cost (1M SMS) | Monthly Cost |
|----------|-------------|---------------------|--------------|
| US-heavy (80% US) | ~$0.008 | ~$8,000 | ~$240K |
| Mixed international | ~$0.034 | ~$34,000 | ~$1M |
| Asia-heavy (80% SEA) | ~$0.046 | ~$46,000 | ~$1.38M |

The range is $240K–$1.38M/month. This is not a rounding error. Our SMS gating logic (Section 3.4) is therefore designed around a hard monthly budget cap rather than a cost-per-message assumption. We set the cap conservatively at launch, measure actual geographic distribution over the first 30 days, and adjust. If the measured rate puts us in the high-cost scenario, SMS volume is restricted further or regional rate negotiation with Twilio is initiated.

### Team Allocation

| Engineer | Primary Responsibility | Explicit Exclusions |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel-specific provider APIs |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure |
| E3 | Preference management, user-facing API, suppression logic | Delivery workers |
| E4 | Redis HA, Postgres operations, monitoring, alerting | See note below |

**The E4 scope problem, stated directly:** Redis HA plus Postgres operations plus on-call response for a system at this scale is more than one engineer's full-time capacity. Listing "feature development" as the exclusion does not change this arithmetic.

**What we actually cut to make E4's scope viable:**

- *No custom alerting infrastructure.* PagerDuty + Datadog with pre-built integrations. E4 configures thresholds, not alerting pipelines.
- *No self-managed Redis cluster.* AWS ElastiCache. E4 manages configuration and capacity planning, not replication or failover mechanics.
- *No self-managed Postgres.* RDS with read replicas. E4 manages schema changes and query performance, not replication or backup infrastructure.
- *Postgres partition management is automated.* A scheduled job creates next-month's partitions and drops partitions older than the retention window. E4 monitors, not operates, this job.
- *On-call rotation includes all 4 engineers.* E4 is not the sole on-call.

With these cuts, E4's actual scope is: ElastiCache configuration and capacity planning, RDS query performance and schema operations, Datadog dashboard and alert configuration, and on-call rotation participation. This is a full-time job; it is not two full-time jobs.

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
  - Preference check (Redis cache, write-through, 5-min TTL)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ├─► [P0 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P0 Worker Pool (8 workers)
     │
     ├─► [P1 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P1 Worker Pool (15 workers)
     │
     ├─► [P2 Queue] (Redis List, LPUSH/BRPOP)
     │     └── P2 Worker Pool (20 workers)
     │
     └─► [In-App Store] (PostgreSQL — bypasses queue entirely)
                    │
                    ▼
           [Channel Dispatcher]
             ├── Push (APNs / FCM)
             ├── Email (SendGrid)
             └── SMS (Twilio)
                    │
                    ▼
           [Delivery Log]
           (PostgreSQL + S3 archive)
                    │
                    ▼
           [Feedback Processor]
           (bounces, opens, failures, token invalidation)
```

### Why Separate Queues, Not a Single Priority Queue

Workers dequeue in batches of 50. A worker that has claimed 50 P2 items will process all 50 before picking up any P0 item that arrives mid-batch. With 20 P2 workers running at peak, you can have 1,000 P2 items in-flight when a P0 security alert arrives. Under P2 volume at peak (~1,200/sec), this is a near-constant condition.

Separate queues fix this: P0 workers only consume from the P0 queue. A P0 item is processed within one batch cycle of a P0 worker becoming available — typically under 2 seconds. The cost is monitoring 3 queues instead of 1, which is a reasonable price for correct priority semantics.

**We use Redis Lists (LPUSH/BRPOP), not Sorted Sets.** Lists give O(1) push and pop with blocking semantics. FIFO within a priority level is correct behavior. Sorted Sets would add complexity without benefit.

### P0 Worker Sizing — Derivation

P0 notifications are security alerts, account compromise notices, and safety-critical messages. Expected volume: <0.1% of total, or ~50,000/day at estimate, with bursts during security incidents potentially reaching 100,000 in a short window.

P0 latency target: 95th percentile under 5 seconds end-to-end.

A single worker processing APNs push can handle approximately 200–400 requests/second using HTTP/2 connection multiplexing. At 100,000 P0 items arriving over 60 seconds (~1,667/sec), we need approximately 5–8 workers to maintain throughput.

**Starting allocation: 8 P0 workers.** This handles normal P0 volume with significant headroom and handles a 60-second mass incident at ~1,600 items/sec. We do not auto-scale P0 workers — container startup latency (30–60 seconds) is too long, and a mass security incident is the wrong time to be debugging auto-scaling behavior. The runbook for manual expansion is written before launch, with a circuit breaker that alerts immediately if P0 queue depth exceeds 10,000 items.

### Preference Check Design

**TTL: 5 minutes, write-through on preference update.**

The write-through sequence:
1. Write to PostgreSQL (source of truth)
2. Immediately invalidate and rewrite the Redis cache key for that user

**The race condition this does not fully prevent:** between steps 1 and 2, a concurrent read can fetch the old value from Redis and cache it with a fresh TTL. The result is that a preference change can take up to 10 minutes to propagate in the worst case. We accept this. The consequence is a user receiving one notification they had just disabled — annoying, not dangerous.

**Blocking and suppression are always Postgres-authoritative, never cache-only.** When a user blocks another user, we add an explicit suppression check against Postgres, bypassing the cache entirely. The cache is for delivery preference optimization; safety enforcement is never delegated to it.

At 1,750 notifications/sec peak, preference cache reads are 1,750 Redis GET operations/sec. Redis handles >100K ops/sec on a single node. The concern is not Redis capacity — it is avoiding PostgreSQL reads on every routing decision, which at this rate would require significant DB capacity for a non-revenue operation.

### In-App Notifications Bypass the Queue

In-app notifications are writes to a database table that clients poll or receive via WebSocket. They need random access by user, immediate consistency, and no retry logic. Routing them through the push queue adds latency with no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** FCM (Android) and APNs (iOS) direct integrations. OneSignal/Braze would save 4–6 weeks of integration work but cost $50–150K/year at this scale and reduce control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost. We revisit if we need advanced segmentation post-launch.

**APNs Authentication — Two Distinct Credentials**

1. **The .p8 authentication key** — a long-lived private key stored in AWS Secrets Manager. Rotated only on compromise or engineer departure. Rotation requires Apple Developer Portal interaction and redeployment.

2. **The JWT bearer token** — generated from the .p8 key at runtime, expires after 1 hour per Apple's spec. We refresh every 45 minutes (not 55 — 15-minute buffer against clock skew).

**Multi-process token management:** A threading lock is process-local. With 43 worker processes across three pools, each process independently manages token state. If token generation fails in one process, there is no cross-process fallback. We address this with a shared token store in Redis:

```python
class APNsTokenManager:
    REDIS_KEY = "apns:bearer_token"
    REDIS_META_KEY = "apns:bearer_token:generated_at"
    REFRESH_INTERVAL = 2700  # 45 minutes
    LOCK_TTL = 30            # seconds

    def __init__(self, key_id: str, team_id: str, secrets_client):
        self.key_id = key_id
        self.team_id = team_id
        self.secrets_client = secrets_client
        self.redis = get_redis_client()
        self._local_token: str | None = None
        self._local_generated_at: float = 0

    def get_token(self) -> str:
        # Fast path: local cache still valid
        if self._local_token and (time.time() - self._local_generated_at) < self.REFRESH_INTERVAL:
            return self._local_token

        # Check Redis for a recently generated token from any process
        token = self.redis.get(self.REDIS_KEY)
        generated_at_raw = self.redis.get(self.REDIS_META_KEY)

        if token and generated_at_raw:
            generated_at = float(generated_at_raw)
            if (time.time() - generated_at) < self.REFRESH_INTERVAL:
                self._local_token = token.decode()
                self._local_generated_at = generated_at
                return self._local_token

        # Acquire distributed lock to prevent thundering herd on refresh
        lock_key = "apns:bearer_token:lock"
        if self.redis.set(lock_key, "1", nx=True, ex=self.LOCK_TTL):
            try:
                private_key = self.secrets_client.get_secret_value("apns_private_key")
                payload = {"iss": self.team_id, "iat": int(time.time())}
                new_token = jwt.encode(
                    payload,
                    private_key,
                    algorithm="ES256",
                    headers={"kid": self.key_id}
                )
                now = time.time()
                pipe = self.redis.pipeline()
                pipe.set(self.REDIS_KEY, new_token, ex=3600)
                pipe.set(self.REDIS_META_KEY, str(now), ex=3600)
                pipe.execute()
                self._local_token = new_token
                self._local_generated_at = now
                return new_token
            finally:
                self.redis.delete(lock_key)
        else:
            # Another process is refreshing; use stale local token if available
            if self._local_token:
                return self._local_token
            # No local token at all — wait briefly and retry