# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling an estimated 20–110M notifications/day across push, email, in-app, and SMS channels. The design makes three foundational bets:

1. **Per-channel queues over a single fanout queue.** FCM rate-limiting should never delay OTP delivery. We pay the monitoring overhead of four queues and accept that cost explicitly.

2. **Proven infrastructure over custom-built components.** Redis, PostgreSQL, SendGrid, and direct APNs/FCM integrations. Debuggable by an on-call engineer at 2am.

3. **Incremental delivery.** Working system in month 2, iterate through month 5, harden in month 6 against the criteria defined in Section 7.

**Two items require explicit sign-off before this design is finalized:**

- **SMS budget (Section 3.4):** Current volume estimates assume ~75K SMS/day. The architectural commitment to an isolated SMS queue and the OTP-isolation argument for per-channel queues both depend on SMS being in scope. If the budget is rejected or SMS is descoped, Section 3.4, the queue justification in Section 2.2, and the volume model in Section 1.1 require revision before work begins. We have not made irreversible architectural commitments contingent on this approval — the per-channel queue design is justified independently by push/email isolation — but the SMS-specific elements are explicitly gated.

- **QA approach (Section 7):** Carries real risk if approved without deliberate acknowledgment.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling with Sensitivity Analysis

The architecture must handle plausible variance, not just the point estimate. Two inputs drive the volume model: notifications per active user per day, and the DAU/MAU ratio. Both are variables, not constants, and we treat them as such.

#### DAU/MAU Ratio Sensitivity

The entire volume model rests on an assumed DAU/MAU ratio. For a social app at 10M MAU, this ratio varies considerably by product maturity and category:

| App Stage / Category | Typical DAU/MAU | DAU at 10M MAU |
|---------------------|----------------|----------------|
| Early-stage social app | 15–20% | 1.5M–2M |
| Mid-stage social app | 25–35% | 2.5M–3.5M |
| Mature, high-retention social | 40–50% | 4M–5M |

We use 25% (2.5M DAU) as our planning basis — conservative for a mature product, realistic for a growth-stage app. We use 15% (1.5M DAU) as the low case and 35% (3.5M DAU) as the high case.

**Why 25% and not 30%:** A new social app at 10M MAU is more likely early-to-mid stage. Using 30% would be optimistic and cause us to under-provision for the more likely scenario. If actual DAU/MAU exceeds 30% in production, we have headroom; if it comes in at 20%, we're sized correctly.

#### Notifications Per Active User Per Day

**Benchmarks for context:**
- Twitter/X (feed-heavy social): ~8–12 notifications/day for active users
- Instagram (engagement-heavy): ~15–25 notifications/day
- Aggressive social apps: 30+ (often with user churn consequences)
- Conservative estimate for a new social app: 10–15

We use 15 as our planning basis, with explicit sensitivity cases:

| Scenario | Notifications/User/Day | Basis |
|----------|----------------------|-------|
| Conservative | 8 | Curated, low-noise product |
| **Planning basis** | **15** | Mid-range social app |
| Aggressive | 30 | High-engagement product |

#### Channel-Appropriate Denominators

Notification volume is not limited to DAU. Active users generate most notifications, but inactive users receive digests, re-engagement emails, and security alerts. The correct denominator depends on channel:

| Channel | Effective Recipient Base | Rationale |
|---------|------------------------|-----------|
| Push | DAU | Requires app installed and active |
| In-app | DAU | Only visible when logged in |
| Email | MAU + lapsed users | Works regardless of app activity |
| SMS | Event-triggered, any user | Auth events happen to inactive users |

#### Full Sensitivity Matrix

| DAU/MAU | Notifs/User/Day | Push + In-app | Email | SMS | **Total/Day** | Peak (3×) | Peak/sec |
|---------|----------------|---------------|-------|-----|---------------|-----------|----------|
| 15% (1.5M DAU) | 8 | 19.5M | 3.5M | 75K | ~23M | ~69M | ~800/sec |
| 15% (1.5M DAU) | 15 | 37.5M | 3.5M | 75K | ~41M | ~123M | ~1,420/sec |
| **25% (2.5M DAU)** | **15** | **37.5M** | **3.5M** | **75K** | **~41M** | **~123M** | **~1,420/sec** |
| 35% (3.5M DAU) | 15 | 52.5M | 3.5M | 75K | ~56M | ~168M | ~1,940/sec |
| 35% (3.5M DAU) | 30 | 105M | 3.5M | 75K | ~109M | ~327M | ~3,780/sec |

**Sizing target:** We size for 2,500/sec sustained throughput. This covers the planning basis (1,420/sec) with 75% headroom, handles the 35%/15-notifications scenario (1,940/sec) comfortably, and requires horizontal scaling only if we reach the 35%/30-notifications scenario simultaneously — an outcome that would also mean we've dramatically exceeded revenue projections and would have budget to scale.

**On the 3× peak multiplier:** This reflects observed social app traffic patterns — morning and evening spikes, viral content moments, and coordinated events. It is a planning assumption, not a measured value. We instrument actual peak-to-average ratios from day one and revisit this multiplier at the Month 2 checkpoint.

#### Month 2 Calibration Checkpoint

After 3–4 weeks of production data, we assess actual volume against planning basis. The checkpoint has a defined decision process — it is not a passive review:

| Actual vs. Planned | Action | Owner | Deadline |
|-------------------|--------|-------|----------|
| Within ±30% | Document and continue | E4 | Within 1 week of checkpoint |
| 30–60% above plan | Add workers (horizontal scale, no redesign) | E1 + E4 | Before Month 3 begins |
| >60% above plan | Architectural review; may delay Month 3 scope | All engineers | Synchronous decision within 48 hours |
| >30% below plan | Reduce worker count, update cost projections | E4 | Within 1 week of checkpoint |

The ±30% threshold represents ~400/sec at peak — within our headroom without worker changes. Above 60% requires worker additions that have lead time; we need 2+ weeks notice before Month 3 scope begins. E4 owns the checkpoint report; the team lead owns the go/no-go decision for Month 3 scope.

### 1.2 Team Allocation

| Engineer | Primary Responsibility |
|----------|----------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) |
| E3 | Preference management, user-facing API, suppression logic |
| E4 | Reliability, monitoring, failure handling, DevOps |

**Ownership boundaries for cross-cutting components:**

The boundary between E1 (queue infrastructure) and E4 (reliability) requires explicit definition because the most failure-prone components sit at that boundary:

| Component | Owner | Reviewer |
|-----------|-------|----------|
| Queue implementation, worker process lifecycle | E1 | E4 |
| Dead-letter queue handlers, retry logic | E4 | E1 |
| Backpressure and rate limiting | E1 | E4 |
| Alerting rules for queue depth/lag | E4 | E1 |
| Circuit breakers for external providers | E4 | E2 |

The principle: E1 owns the path that works; E4 owns the path that fails. Where they overlap (backpressure, which is both infrastructure and a reliability mechanism), E1 owns implementation and E4 owns policy. Disputes escalate to a 30-minute sync, not a Slack thread.

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
  - Preference check  (Redis cache, version-fenced write-through, TTL=60s)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment
  - Channel selection
     │
     ├─→ [Push Queue]    (Redis Sorted Set)  → Push Workers   → APNs / FCM
     ├─→ [Email Queue]   (Redis Sorted Set)  → Email Workers  → SendGrid
     ├─→ [SMS Queue]     (Redis Sorted Set)  → SMS Workers    → Twilio
     └─→ [In-App Queue]  (Redis List)        → In-App Workers → PostgreSQL
                                    │
                          [Delivery Log]
                          (PostgreSQL + S3 archive)
                                    │
                          [Feedback Processor]
                          (bounces, opens, failures → suppression list)
```

### 2.2 Why Per-Channel Queues

**The decisive failure mode:** FCM begins rate-limiting at 3pm due to a traffic spike. With a single shared queue, P0 SMS messages (OTPs) queue behind thousands of stalled push notifications. A user attempting 2FA waits 4 minutes for their code. This is a correctness failure, not a performance degradation.

With per-channel queues, FCM rate-limiting backs up the push queue only. The on-call engineer can shed P2 push notifications without touching other channels. The failure domain is contained.

This justification holds independently of whether SMS is in scope. Push and email have sufficiently different rate-limiting profiles, latency requirements, and failure modes to warrant isolation on their own. SMS isolation is an additional benefit, not the primary argument.

**The cost:** Four queues to monitor, four dead-letter queues, four sets of alerting rules. Approximately one engineer-day to set up; the failure isolation benefit is worth it.

### 2.3 In-App Notifications — Queued, Not Direct Write

In-app notifications use a Redis List queue (FIFO; no priority tiers needed within this channel). Workers dequeue and write to PostgreSQL asynchronously. The router is never blocked by PostgreSQL write pressure.

**The actual failure mode of direct writes:** PostgreSQL is under write pressure during a spike — a large batch job, a slow migration, or simply peak load. With direct synchronous writes, the in-app write path blocks the router. When it times out, the notification is dropped with no retry path. This contradicts the reliability goals that motivated per-channel queues for other channels.

The "immediate consistency" argument for direct writes is overstated: a 1–2 second delay through a queue is imperceptible to users reading their notification feed. Operational consistency with other channels — one pattern to understand, one failure mode to handle — is worth more than the marginal latency reduction.

```
Queue type:       Redis List (LPUSH/BRPOP — FIFO)
Workers:          4 processes (derivation in Section 5)
Retry on failure: exponential backoff, max 3 attempts, then DLQ
Priority tiers:   None — all in-app notifications are equivalent
```

### 2.4 Preference Cache — Version Fencing

**The race condition we're solving:** The write-through pattern (write DB, delete Redis key) has a window where a concurrent reader can repopulate the cache with stale data before the delete executes:

```
Thread A: writes new prefs to DB (version 4 → 5)
Thread B: reads old prefs from Redis (cache hit, version 4)
Thread A: deletes Redis key
Thread B: re-caches version 4 prefs with fresh TTL  ← stale data cached for 60s
```

**Fix: version fencing with compare-and-delete.**

Every preference record carries a `version` integer (monotonically incrementing on each write). The cache stores both preferences and version. On invalidation, a Lua script atomically deletes the cache entry only if the stored version is strictly less than the version we just wrote.

**The comparison must be strictly less than (`<`), not less than or equal to (`<=`).**

The `<=` condition is subtly wrong. Consider two writes in rapid succession: write 1 produces version 4, write 2 produces version 5. Write 2's invalidation fires with `new_version=5`. The cache currently holds version 5 (populated by a reader after write 2 completed). With `<=`, the script evaluates `5 <= 5` — true — and deletes a valid, current cache entry. This forces an unnecessary cache miss. More critically, if the reader that re-populates the cache reads from a replica with replication lag, it may cache version 4 despite version 5 having been written — producing exactly the staleness we were trying to prevent. The correct condition deletes only entries that are strictly older than what we just wrote, leaving same-version or newer entries untouched.

```python
# Lua script: delete key only if stored version is strictly older than new_version
INVALIDATE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current then
    local data = cjson.decode(current)
    if data.version < tonumber(ARGV[1]) then
        redis.call('DEL', KEYS[1])
        return 1
    end
end
return 0
"""

def update_user_preferences(user_id: str, updates: dict) -> int:
    new_version = db.execute("""
        UPDATE user_preferences
        SET ..., version = version + 1
        WHERE user_id = %s
        RETURNING version
    """, user_id).fetchone()['version']

    # Evict only if cache holds something strictly older than new_version
    redis.eval(INVALIDATE_SCRIPT, 1, f"prefs:{user_id}", new_version)
    return new_version

def get_user_preferences(user_id: str) -> UserPreferences:
    cache_key = f"prefs:{user_id}"
    cached = redis.get(cache_key)
    if cached:
        return UserPreferences.parse(cached)

    prefs = db.query(
        "SELECT *, version FROM user_preferences WHERE user_id = %s", user_id
    )
    redis.setex(cache_key, 60, prefs.json_with_version())
    return prefs
```

**Honest assessment of residual staleness:** The 60-second TTL is not a narrow edge case — it is the common case for any user who changes preferences while active notification routing is occurring. The sequence "reader caches stale data 1ms before write, invalidation fires, reader's entry survives for its full TTL" is normal operation of any cache with a TTL longer than the invalidation window. A user who disables push notifications may receive push notifications for up to 60 seconds afterward. This is acceptable behavior, but it is the typical case, not the exceptional one. The preference UI must reflect this accurately: "changes take effect within 1 minute."

---

## 3. Delivery Channels

### 3.1 Push Notifications (~31M/day at planning basis)

**Provider:** FCM (Android) and APNs (iOS) via direct API integration. No intermediary (OneSignal, Braze) in v1. Intermediaries save 4–6 weeks of integration work but cost $50–150K/year at this scale. We accept the upfront engineering cost and revisit at 50M MAU.

**FCM Configuration:**
```
Worker processes:   8 (derivation in Section 5)
Connection pool:    50 persistent HTTP/2 connections per worker
Batch size:         500 tokens per FCM v1 batch request
Sustained rate:     400 req/sec (FCM limit ~600/sec; we operate at 67% to maintain headroom)
Token validation:   validate on first send failure, purge on 404/InvalidRegist