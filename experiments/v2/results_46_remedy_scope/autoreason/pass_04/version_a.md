# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions:

1. **Four isolated priority queues (P0–P3)** with TTL semantics enforced via companion expiry sorted sets — Redis Lists have no per-element TTL, and the `setex`-only approach leaves stale entries in queues indefinitely
2. **Full payload storage in queue entries** — storing only IDs creates a crash window between dequeue and payload fetch that causes silent, unrecoverable message loss
3. **Worker pools are per-channel and per-priority**, deployed as separate process instances with independent scaling
4. **SMS volume split into two independent budgets** — OTP/security SMS are uncapped but separately modeled; social SMS is hard-capped at ~100K/day
5. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL primary
6. **P0 has minimum 2 workers per channel** — no single point of failure on the security-critical path
7. **APNs throughput based on HTTP/2 multiplexing**, not HTTP/1.1 assumptions; validated against Apple rate limits in month 2
8. **Active-user correction applied consistently** — push and in-app are complementary channels, not additive ones for the same user at the same moment

We ship a working system in month 2, with an explicit email-only fallback contingency if push integration is delayed. Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### Traffic Model

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry average for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes, ~2hr duration |
| **Sustained peak throughput** | **~1,750/sec** | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Capacity ceiling, not operating target |

### Active-User Correction — Applied Consistently

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This affects two channels differently:

- **In-app:** Delivered only to logged-in users. Peak demand = 10M/day × 3× / 86,400 × (600K / 3M) = **~350/sec**
- **Push:** Push is specifically for *offline or background* users. At peak, ~2.4M of 3M DAU are offline. Peak demand = 35M/day × 3× / 86,400 × (2.4M / 3M) = **~972/sec**, not the naïve 1,215/sec you get by ignoring channel complementarity

Push and in-app are not additive for the same user at the same moment. Treating them as such overstates both demand figures and leads to over-provisioning. The reasoning matters as much as the number — this same correction applies to queue drain analysis and capacity planning throughout.

### The SMS Budget Problem — Two Independent Budgets

A single SMS cap conflates two categories with fundamentally different constraints: security-critical messages that must send regardless of cost, and social messages that are discretionary. They require separate treatment.

**OTP volume model:**

- ~1.5M logins/day, ~10% triggering SMS OTP (users without authenticator apps and without trusted devices) = **~150K OTP SMS/day baseline**
- Forced re-authentication events (security incident, session expiry policy change) can spike this 5–10×, to **750K–1.5M OTP SMS/day** for 1–3 days. This must be budgeted separately — a security incident is the worst time to face a cost-versus-safety tradeoff

**Budget allocation:**

| SMS category | Volume estimate | Annual cost at $0.012/msg |
|---|---|---|
| OTP / 2FA (baseline) | ~150K/day | ~$660K/year |
| OTP spike reserve (3 days/year at 10×) | ~4.5M total | ~$54K/year |
| Security alerts | ~20K/day | ~$88K/year |
| Social/digest (hard cap) | ≤100K/day | ≤$438K/year |
| **Total** | **~270K–370K/day baseline** | **~$1.2M–1.4M/year** |

This is higher than a single-cap approach implies, because OTP volume was previously unmodeled. It is still budgetable, and it avoids the scenario where a security incident forces a choice between user safety and cost control.

**Permitted SMS:** OTP/2FA (always), password reset fallback (if no email open within 10 minutes), security alerts (new device login, suspicious activity). Social notifications regardless of user preference: never, without explicit budget approval and rate-limit re-architecture.

### Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2 multiplexed streams | ~1,000 req/sec/worker (see note) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput note:** APNs supports up to 1,000 concurrent streams per HTTP/2 connection. The prior approach of treating APNs like HTTP/1.1 (20 connections × 1 request / 40ms RTT = 500/sec) was wrong. HTTP/2 multiplexing means the practical limit is Apple's server-side per-bundle-ID rate limit, typically ~1,000–2,000 requests/sec in production. We plan conservatively at **1,000 req/sec/worker** pending validation against actual Apple rate limits during month 2 integration testing. This figure must be confirmed — it cannot be assumed.

**Demand vs. capacity:**

| Channel | Peak demand | Workers (P0 / P1 / P2 / P3) | Total | Peak capacity | Headroom |
|---------|-------------|------------------------------|-------|---------------|----------|
| FCM push | ~972/sec | 2 / 3 / 2 / 0 | 7 | ~14,000/sec | 14× |
| APNs push | ~243/sec | 2 / 2 / 1 / 0 | 5 | ~5,000/sec | 20× |
| Email | ~138/sec | 0 / 1 / 1 / 2 | 4 | ~4,000/sec | 29× |
| SMS | ~4/sec (capped) | 2 / 1 / 0 / 0 | 3 | ~200/sec | 50× |
| In-app | ~350/sec | 0 / 2 / 2 / 2 | 6 | ~6,000/sec | 17× |

**Total: 25 workers.** Each cell in the priority column represents separate process instances — a P0 FCM worker is a different deployment unit from a P1 FCM worker.

**P0 minimum redundancy:** P0 has 2 workers per channel. A single worker crash eliminates P0 processing for that channel until ECS restarts it — typically 30–60 seconds. The second worker handles load during the restart window. For OTP and security alerts, that restart window is unacceptable with a single worker. Email is absent from P0 by design: OTPs must not be delivered via a channel with 5–30 minute delivery latency.

### Queue Drain Analysis

At baseline 578/sec input and 3× peak input of ~1,750/sec, excess accumulates at ~1,172/sec. Over a 2-hour spike: ~8.4M excess notifications.

Combined worker capacity across all channels: ~29,000/sec. Net drain rate post-peak: ~28,400/sec. The 8.4M excess clears in approximately **5 minutes** after peak ends.

Queue depth alerts: 500K items for P1–P3; **1,000 items for P0** (P0 should never accumulate — a growing P0 queue is an incident, not a capacity event).

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, TTL enforcement, deduplication | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | FCM (weeks 1–6), APNs (weeks 5–8, overlapping) | Email + SMS | Deliverability, token hygiene |
| E3 | Preferences, in-app, WebSocket | Schema, preference API, in-app store | WebSocket fanout with sequence numbers | User-facing polish, reconnect testing |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ | Chaos testing, runbooks |

**Month 2 contingency:** If FCM and APNs are not both ready by month 2, the launch proceeds with **email-only for non-critical notifications and SMS for OTP**. Push is a month 3 milestone dependency, not a month 2 launch dependency. E2 starts FCM before APNs because FCM's HTTP v1 API is simpler to onboard than APNs certificate management; APNs begins week 5, overlapping with FCM stabilization.

**E4 scope is bounded by managed services:** ElastiCache Multi-AZ (not self-managed Redis), RDS Multi-AZ (not self-managed PostgreSQL), Datadog (not self-built monitoring), ECS with Fargate (not custom deployment scripts). Chaos testing is deferred to month 5 — E4 does not attempt it while building the system.

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
  - Deduplication check  (Redis ntf:{id} key — checked BEFORE enqueue)
  - Preference lookup    (Redis cache, 5-min TTL, write-through)
  - Suppression check    (global + per-user blocklists)
  - Priority assignment  (by notification type, not user)
  - Channel selection    (priority + user preferences)
  - Aggregation check    (Redis, per type/entity/user)
        │
        ├──────────────────────────────────────────────────────┐
        ▼                                                      ▼
[P0 Queue]  [P1 Queue]  [P2 Queue]  [P3 Queue]         [In-App Store]
(Redis List  (Redis List) (Redis List) (Redis List)      (PostgreSQL)
 + expiry     + expiry     + expiry     + expiry)              │
 sorted set)  sorted set)  sorted set)  sorted set)            │
     │            │           │           │                    │
     ▼            ▼           ▼           ▼                    │
[P0 Workers] [P1 Workers] [P2 Workers] [P3 Workers]           │
  (6 total)   (9 total)    (6 total)    (4 total)             │
     │            │           │           │                    │
     └────────────┴───────────┴───────────┘                    │
                  │                                            │
          [Channel Dispatcher]                                 │
            ├── Push (FCM / APNs)                              │
            ├── Email (SendGrid)                               │
            └── SMS (Twilio)                                   │
                  │                                            │
                  ▼                                            ▼
           [Delivery Log]                          [WebSocket Fanout]
       (PostgreSQL + S3 archive)             (sequence-numbered events
                  │                           → Redis Pub/Sub → clients
                  ▼                           with PostgreSQL catch-up
        [Feedback Processor]                  on reconnect)
    (bounces, opens, token invalidity,
     delivery receipts)
```

### Why Four Queues, Not One Sorted Set

The single-queue-with-priority-scoring approach fails under backpressure — exactly when it matters most. A P0 security alert in a Redis sorted set competes for the same lock as thousands of P2 like notifications. "P0 always beats P1" is only guaranteed when the queue drains faster than it fills. That guarantee disappears precisely when you need it most.

Four separate Redis Lists give us:

- **Hard isolation:** P0 workers only touch the P0 queue. A P2 burst cannot delay P0 delivery
- **Correct TTL semantics per priority:** P3 digests get 48-hour TTL; P0 OTPs get 5-minute TTL. These are different business requirements that cannot share a single TTL policy
- **Independent scaling:** Adding P1 workers requires no P0 configuration changes
- **Simpler failure isolation:** Each queue has its own dead-letter queue with no priority-scoring arithmetic to get wrong under load

**The cost:** Four worker pools, four dead-letter queues, four sets of metrics. Manageable with managed infrastructure.

**What we give up:** Perfect global ordering within a priority band across channels. A P1 push might be processed before a P1 email that arrived 5 seconds earlier. Per-channel ordering within a priority band is sufficient for a social app.

---

## 3. Queue Implementation

### 3.1 TTL Enforcement — The Real Problem and Real Solution

Redis Lists have no per-element TTL. A `setex` on the deduplication key `ntf:{id}` expires that key but leaves the queue entry sitting in the list indefinitely. A P0 OTP enqueued during a Redis slowdown would be delivered hours later — the opposite of the stated intent.

**Solution: Companion expiry sorted set per queue.** Each queue has a sorted set keyed `expiry:{queue_name}`. The score is the Unix timestamp at which the notification expires. At dequeue time, workers check the expiry set before processing. Expired notifications are discarded and logged, not sent to the DLQ (a stale OTP is not retryable — it is permanently invalid).

```python
PRIORITY_QUEUES = {
    "P0": "queue:p0",
    "P1": "queue:p1",
    "P2": "queue:p2",
    "P3": "queue:p3",
}

EXPIRY_SETS = {
    "P0": "expiry:p0",
    "P1": "expiry:p1",
    "P2": "expiry:p2",
    "P3": "expiry:p3",
}

QUEUE_TTLS = {
    "P0": 300,      # 5 minutes  — stale OTPs are worse than no OTPs
    "P1": 3600,     # 1 hour
    "P2": 86400,    # 24 hours
    "P3": 172800,   # 48 hours — digests need longer delivery window
}
```

### 3.2 Enqueue with Deduplication

Deduplication must happen at **enqueue time**, before the notification enters the queue. Checking at dequeue time is too late — the duplicate is already in the queue and will be processed by another worker.

```python
def enqueue(notification: Notification) -> None:
    queue_name = PRIORITY_QUEUES[notification.priority]
    expiry_set = EXPIRY_SETS[notification.priority]
    ttl = QUEUE_TTLS[notification.priority]
    expires_at