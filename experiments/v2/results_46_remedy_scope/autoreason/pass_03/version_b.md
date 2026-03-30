# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The revision addresses ten specific failures in the prior draft. Changes that materially affect architecture or cost are called out explicitly.

**What changed from the prior version:**

1. **TTL enforcement is now real** — per-element TTL implemented via a scored expiry set checked at dequeue time, not a fictional `setex` guarantee
2. **Lua script crash window acknowledged** — full-payload storage narrows but does not eliminate loss; the mitigation strategy is honest about what remains
3. **Worker arithmetic reconciled** — a single table maps priority tiers to channel workers; the "28 workers" figure is retired and replaced with explicit per-tier counts
4. **P0 has minimum 2 workers per channel** — no single point of failure on the critical path
5. **APNs throughput recalculated** — HTTP/2 multiplexing accounted for; headroom reassessed
6. **Active-user correction applied consistently** — push to offline users deferred, not treated as equivalent to push to active users
7. **Deduplication is implemented** — the `ntf:{id}` key is checked before enqueue, not just described
8. **Month 2 contingency named** — if push isn't ready, email-only launch is the fallback
9. **OTP volume modeled independently** — the SMS cap and the OTP carve-out are no longer in conflict
10. **WebSocket fanout designed** — sequence numbers, reconnect behavior, and the relationship to PostgreSQL storage are specified

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

### Active User Correction — Applied Consistently

The prior version correctly adjusted in-app demand for active users but then failed to apply the same logic to push and the queue drain analysis. The correction is applied consistently here.

**Logged-in users during peak:** 3M DAU × 20% concurrently active = ~600K users online at peak. This affects two channels differently:

- **In-app:** Delivered only to logged-in users. Peak demand = 10M/day × 3× / 86,400 × (600K / 3M) = **~350/sec**
- **Push:** Push is specifically for *offline* or *background* users. At peak, ~2.4M of 3M DAU are offline. Push peak demand = 35M/day × 3× / 86,400 × (2.4M / 3M) = **~972/sec**, not the full 1,215/sec the prior version used. The 20% reduction is modest but the reasoning matters — push and in-app are complementary channels, not additive ones for the same user at the same moment.

This correction propagates into the capacity table below.

### The SMS Budget Problem — OTP Volume Modeled Separately

The prior version capped SMS at 100K/day but simultaneously declared OTPs "always permitted" without checking whether OTP volume alone could breach the cap.

**OTP volume model:**

- Login events: 10M MAU × ~15% daily login rate = ~1.5M logins/day. Not all trigger SMS OTP — only users without an authenticator app and without a trusted device. Assume 10% of logins trigger SMS OTP: **~150K OTP SMS/day at baseline**.
- Forced re-authentication events (security incident, session expiry policy change) can spike this 5–10×, to **750K–1.5M OTP SMS/day** for 1–3 days.

**Resolution:** The 100K/day cap applies to non-security SMS (marketing, social digests). OTP and security alert SMS are uncapped but separately budgeted. Budget allocation:

| SMS category | Volume estimate | Annual cost at $0.012/msg |
|---|---|---|
| OTP / 2FA (baseline) | ~150K/day | ~$660K/year |
| OTP spike reserve (3 days/year at 10×) | ~4.5M total | ~$54K/year |
| Security alerts | ~20K/day | ~$88K/year |
| Social/digest (hard cap) | ≤100K/day | ≤$438K/year |
| **Total** | **~270K–370K/day baseline** | **~$1.2M–1.4M/year** |

This is higher than the prior version's $365K–550K estimate because OTP volume was previously unmodeled. It is still budgetable and avoids the scenario where a security incident forces a choice between user safety and cost control.

Any product decision to expand social SMS requires explicit budget approval. OTP volume is reviewed monthly against the model above.

### Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2, multiplexed streams | ~2,000 requests/sec/worker (see note) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — corrected calculation:** The prior version calculated 500 requests/sec from "20 connections × 1 request/connection / 40ms RTT," which incorrectly treated HTTP/2 like HTTP/1.1. APNs supports up to 1,000 concurrent streams per HTTP/2 connection. At 20 connections with 500 concurrent streams each and ~40ms RTT, theoretical maximum is 20 × 500 / 0.040 = 250,000/sec — far above what we need. The practical limit is Apple's server-side rate limiting: APNs enforces a per-bundle-ID rate limit, typically ~1,000–2,000 requests/sec in production (varies by account tier and must be confirmed with Apple for production credentials). We plan for **1,000 requests/sec per APNs worker** as a conservative production estimate, with the understanding that this figure must be validated against actual Apple rate limits during month 2 integration testing. This changes the APNs capacity picture significantly from the prior version.

**Revised demand vs. capacity:**

| Channel | Peak demand | Workers per priority tier (P0/P1/P2/P3) | Total workers | Peak capacity | Headroom |
|---------|-------------|------------------------------------------|---------------|---------------|----------|
| FCM push | ~972/sec | 2 / 3 / 2 / 0 | 7 | ~14,000/sec | 14× |
| APNs push | ~243/sec | 2 / 2 / 1 / 0 | 5 | ~5,000/sec | 20× |
| Email | ~138/sec | 0 / 1 / 1 / 2 | 4 | ~4,000/sec | 29× |
| SMS | ~4/sec (capped) | 2 / 1 / 0 / 0 | 3 | ~200/sec | 50× |
| In-app | ~350/sec | 0 / 2 / 2 / 2 | 6 | ~6,000/sec | 17× |

**Total: 25 workers.** Each row in the priority column represents separate process instances — a P0 FCM worker is a different deployment unit from a P1 FCM worker.

**P0 minimum redundancy:** P0 has 2 workers per channel (FCM and SMS; APNs also gets 2). This means no single worker crash eliminates P0 processing for any channel. The prior version had 1 worker per channel at P0, which was a single point of failure on the security-critical path. Two workers per P0 channel is the minimum; the process supervisor (ECS) restarts crashed workers automatically, but the second worker handles load during the restart window.

**Note on Email at P0:** P0 notifications (OTP, security alert, payment confirm) go to push and SMS, not email. Email is too slow for OTP delivery. P0 has no email workers by design.

### Queue Drain Analysis — Corrected

At 50M/day baseline, normal rate is ~578/sec. During a 3× peak, excess above baseline accumulates over the 2-hour spike window.

Peak input rate: ~1,750/sec. Baseline drain rate: ~578/sec. Net accumulation rate: ~1,172/sec. Over 7,200 seconds: ~8.4M excess notifications.

Combined worker capacity across all channels: ~29,000/sec. At baseline input of ~578/sec, net drain rate post-peak: ~28,400/sec. The 8.4M excess clears in approximately **5 minutes** after peak ends. This is faster than the prior version's 18-minute estimate because APNs capacity was previously miscalculated.

Queue depth alert threshold: 500K items. P0 queue alert threshold: 1,000 items (much lower — P0 should never accumulate).

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, TTL enforcement, deduplication | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | FCM first (weeks 1–6), APNs (weeks 5–8) | Email + SMS | Deliverability, token hygiene |
| E3 | Preferences, in-app, WebSocket | Schema, preference API, in-app store | WebSocket fanout with sequence numbers | User-facing polish, reconnect testing |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ | Chaos testing, runbooks |

**Month 2 contingency:** If FCM and APNs are not both ready by month 2, the launch proceeds with **email-only for non-critical notifications and SMS for OTP**. Push is not a dependency for the initial launch — it is a dependency for the month 3 milestone. This is the explicit contingency the prior version lacked. E2 starts FCM before APNs because FCM's HTTP v1 API is simpler to onboard than APNs certificate management; APNs work begins in week 5, overlapping with FCM stabilization rather than running fully in parallel.

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
  - Deduplication check  (Redis, ntf:{id} key — checked BEFORE enqueue)
  - Preference lookup    (Redis cache, TTL 5 min, write-through)
  - Suppression check    (global + per-user blocklists)
  - Priority assignment  (by notification type, not user)
  - Channel selection    (priority + user preferences)
  - Aggregation check    (Redis, per type/entity/user)
        │
        ├────────────────────────────────────────────────────────┐
        ▼                                                        ▼
[P0 Queue]  [P1 Queue]  [P2 Queue]  [P3 Queue]           [In-App Store]
(Redis List  (Redis List) (Redis List) (Redis List)        (PostgreSQL)
 + expiry     + expiry     + expiry     + expiry)               │
 sorted set)                                                     │
     │            │           │           │                      │
     ▼            ▼           ▼           ▼                      │
[P0 Workers] [P1 Workers] [P2 Workers] [P3 Workers]             │
  (6 total)   (9 total)    (6 total)    (4 total)               │
     │            │           │           │                      │
     └────────────┴───────────┴───────────┘                      │
                  │                                              │
          [Channel Dispatcher]                                   │
            ├── Push (FCM / APNs)                                │
            ├── Email (SendGrid)                                 │
            └── SMS (Twilio)                                     │
                  │                                              │
                  ▼                                              ▼
           [Delivery Log]                            [WebSocket Fanout]
       (PostgreSQL + S3 archive)               (sequence-numbered events
                  │                             → Redis Pub/Sub → clients
                  │                             with PostgreSQL catch-up
                  ▼                             on reconnect)
        [Feedback Processor]
    (bounces, opens, token invalidity, delivery receipts)
```

### Why Four Queues — TTL Semantics Are Now Actually Enforced

The prior version's justification for separate queues partially rested on per-priority TTL semantics, then implemented TTLs only on the `ntf:{id}` key — not on the queue entries themselves. Redis Lists have no per-element TTL. This section describes how TTL enforcement is actually implemented.

---

## 3. Queue Implementation

### 3.1 TTL Enforcement — The Real Problem and Real Solution

Redis Lists have no per-element TTL. The prior version's `setex` on `ntf:{id}` expired the deduplication key but left the queue entry sitting in the list indefinitely. A P0 OTP enqueued during a Redis slowdown would be delivered hours later — the opposite of the stated intent.

**Solution: Expiry sorted set per queue.** Each queue has a companion sorted set keyed by `expiry:{queue_name}`. The score is the Unix timestamp at which the notification expires. At dequeue time, before processing, workers check whether the notification has expired. This adds one Redis operation per batch but enforces TTL semantics that actually work.

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

### 3.2 Deduplication — Implemented, Not Just Described

The prior version described `ntf:{id}` as a deduplication key but the dequeue code never checked it. Deduplication must happen at **enqueue time**, before the notification enters the queue. Checking at dequeue time is too late — the duplicate is already in the queue and will be processed by another worker.

```python
def enqueue(notification: Notification) -> None:
    queue_name = PRIORITY_QUEUES[notification.priority]
    expiry_set = EXPIRY_SETS[notification.priority]
    ttl = QUEUE_TTLS[notification.priority]
    expires_at = time.time() + ttl
    payload = notification.model_dump_json()
    dedup_key = f"ntf:{notification.