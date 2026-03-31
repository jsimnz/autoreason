# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M MAU.

**What this revision fixes:** The previous draft had eleven named gaps. Revision 2 addressed nine of them but left two unresolved (APNs JWT rotation fix was truncated mid-sentence; PostgreSQL write amplification was claimed fixed but never addressed) and introduced two new problems (S3 archival policy still undefined despite being claimed fixed; compliance mitigation was legally unsound). This revision also addresses seven additional problems identified in review: an underdefined PostgreSQL overflow table, a bus factor mitigation that doesn't survive scrutiny, an internally inconsistent load test target, an unstatistical opt-out threshold, re-engagement campaigns that potentially contradict the SMS constraint, an unacknowledged push/in-app consistency gap, and preference cache invalidation that was asserted but never designed.

Every tradeoff is explicit. Where we accept risk, we name it. Where we defer complexity, we state the trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

A critical modeling error to avoid upfront: different channels have different eligible populations. Push notifications reach installed-app users regardless of daily activity. In-app notifications only reach logged-in users. Treating DAU as the denominator for all channels produces wrong numbers.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~5 | Aggressive but not opt-out-inducing; industry benchmarks 3–8 |
| **Push volume/day** | **~35M** | 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K** | Auth and security only |
| **Total/day** | **~51M** | Sum across channels |
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput** | **~1,770/sec** | 51M × 3 / 86,400 |

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. Re-engagement campaigns (month 5) are explicitly push and email only — the SMS gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. See Section 3.3.

**On push volume:** 5 notifications/day/installed user is a deliberate product constraint, not a technical one. We monitor opt-out rates weekly. The alert threshold derivation is in Section 1.4.

These are estimates. We instrument from day one and publish a traffic model review in month 2.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** "Cross-training" in the sense of watching someone else work does not constitute coverage ability. The mitigation here is not a checkbox — it is paired ownership, documented runbooks, and a specific coverage test before each channel launch. See the requirements below.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 (in-app storage) |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**What "coverage partner" means operationally:**

Coverage is not a rotation. It is a demonstrated capability, verified before the channel goes live:

1. **Runbook authorship:** The primary owner writes the runbook. The coverage partner must be able to execute every step without asking the primary owner for clarification. If they can't, the runbook is incomplete.
2. **Independent incident simulation:** Before a channel goes live, the coverage partner independently handles a simulated incident (staging environment, pager goes to coverage partner only, primary owner is unavailable). The incident is drawn from the runbook's failure scenarios. If the coverage partner cannot resolve it, the channel does not launch.
3. **On-call solo:** Each coverage partner carries solo on-call for their partner's channel for at least one week before that channel reaches full traffic. Problems that surface during solo on-call are fixed before launch.

This means E4 carries solo push on-call during month 1 (before push launches in month 2). E2 carries solo email on-call during months 1–2 (before email digests launch in month 3). E3 carries solo SMS on-call during month 2 (before SMS launches in month 3).

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are sufficiently detailed that a competent backend engineer unfamiliar with the system can follow them — we write runbooks for that audience, not for ourselves.

All engineers rotate on-call. No dedicated QA — engineers own quality.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification This Month |
|-------|-------------|----------------------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | E4 completes solo push on-call (before push launches month 2) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E2 completes solo email on-call (before digests launch month 3) |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 completes solo SMS on-call |
| 4 | Full preference management, suppression lists, advanced batching | — |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced), A/B framework | — |
| 6 | Load testing to 3× peak (design envelope) + stress testing to 4× (beyond design); chaos testing on established baselines | — |

**On month 6 load testing:** The system is designed for 3× peak throughput. Testing to 3× validates that the design envelope is met. Testing to 4× is deliberate stress-beyond-design — we expect degradation and want to characterize it (does it fail gracefully? does backpressure engage correctly?). These are different tests with different pass criteria, not a single "load test at 4×." FCM throughput analysis shows minimal headroom at 3× during FCM degradation; the 4× stress test uses a mocked FCM endpoint to isolate our system's behavior from Google's. Both tests run against a production-mirror staging environment. Load testing runs continuously from month 2 in staging; month 6 formalizes this into a documented capacity envelope with explicit pass/fail criteria.

### 1.4 Opt-Out Rate Threshold Derivation

The previous draft set a 0.5% week-over-week opt-out rate increase as a P1 threshold without statistical justification. Here is the derivation.

**Establishing a baseline:** We cannot set a meaningful threshold before we have a baseline. For the first 8 weeks of push operation, we measure opt-out rates without alerting on them, building a distribution of weekly rates. We expect this to follow a roughly normal distribution with seasonal variance. After 8 weeks, we compute the mean (μ) and standard deviation (σ) of weekly opt-out rates.

**Alert threshold:** We alert when the weekly opt-out rate exceeds μ + 2σ. At 2σ, we expect a false positive roughly 1 in 20 weeks under normal conditions — acceptable for a P2 alert (investigate, don't page). We page (P1) at μ + 3σ, which produces a false positive roughly 1 in 370 weeks.

**Pre-baseline interim:** Before we have 8 weeks of data, we use an absolute threshold of 2% of push-eligible users opting out in a single week (140K users). This is deliberately conservative — it will only fire on genuinely anomalous behavior, not normal variance. We do not treat the 0.5% figure from the previous draft as meaningful.

**What this threshold measures:** Opt-out rate is a lagging indicator of notification quality. We also track opt-out rate by notification type, which is a leading indicator — if "like" notifications are driving disproportionate opt-outs, we adjust frequency caps for that type before the aggregate rate crosses the alert threshold.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Token bucket rate limiting per caller
  - Returns 429 with Retry-After under overload
  - Sheds P2 load before P1; never sheds P0
     │
     ▼
[Notification Router]
  - Preference check (Redis cache → PostgreSQL fallback)
  - Suppression check (frequency caps, do-not-contact)
  - Priority assignment (by notification type)
  - Channel selection
     │
     ├─────────────────────────────────────────────┐
     ▼                                             ▼
[Priority Queue]                          [In-App Store]
  (Redis Sorted Set + Lua scripts)         (PostgreSQL, partitioned by user_id)
  (Redis Sentinel, 3-node cluster)                 │
     │                                             ▼
     ├── P0 Worker Pool (dedicated Redis keyspace) [WebSocket Pub/Sub]
     ├── P1 Worker Pool (20 workers)               (Redis, best-effort)
     └── P2 Worker Pool (10 workers)               │
          │                                        ▼
          ▼                                [Push/In-App Consistency Layer]
   [Channel Dispatcher]                    (see Section 2.3)
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — auth/security only; type allowlist enforced here)
          │
          ▼
   [Delivery Log]
   (PostgreSQL, partitioned by date; S3 archive after 30 days)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures, token invalidation)
```

### 2.2 PostgreSQL Write Load Analysis

The previous draft described PostgreSQL workloads independently and never examined their combined write pressure. This section addresses that directly.

**Write sources and estimated volume:**

| Workload | Write Volume | Pattern |
|----------|-------------|---------|
| In-app notification inserts | ~15M rows/day (~175/sec avg, ~525/sec peak) | Bursty, clustered around social events |
| Delivery log inserts | ~51M rows/day (~590/sec avg, ~1,770/sec peak) | Mirrors total notification volume |
| Preference updates | ~100K/day (~1/sec) | Low volume, high-importance |
| Token invalidation updates | ~500K/day (~6/sec) | Bursty after push campaigns |
| Overflow table (Redis fallback) | Near-zero normally; up to ~1,770/sec during Redis outage | Exceptional only |

**Peak combined write load: ~2,300 rows/sec** (in-app + delivery log at 3× peak). This is the number we provision against.

**WAL pressure:** At ~500 bytes/row average, 2,300 rows/sec generates approximately 1.1 MB/sec of WAL. For a well-provisioned PostgreSQL instance (32 vCPU, NVMe storage, 128GB RAM), this is modest — well within the 100–200 MB/sec WAL throughput typical of such instances. The risk is not raw throughput; it is write amplification from index maintenance.

**Index strategy to control write amplification:**

- **Delivery log table:** Index only on `(notification_id)` for lookup and `(created_at)` for archival queries. Do not index on `(user_id, created_at)` — that query pattern belongs to the in-app table, not the delivery log. Fewer indexes = less write amplification.
- **In-app notification table:** Index on `(user_id, created_at DESC)` for the primary read pattern (fetch unread notifications for user). Index on `(created_at)` for archival. No full-text indexes — notification content is not searched.
- **Overflow table:** No indexes beyond primary key. It exists only for recovery; we drain it sequentially, not by priority order. See Section 2.4 for the ordering tradeoff.

**Partitioning strategy:**

- **Delivery log:** Partitioned by `created_at` (monthly partitions). Old partitions are archived to S3 and dropped, eliminating the performance cost of a growing table. See Section 2.5 for the archival policy.
- **In-app notifications:** Partitioned by `user_id % 64` (hash partitioning). This distributes write load evenly and keeps per-user reads on a single partition. We chose hash over range partitioning because in-app reads are almost always by `user_id`, not by time range.

**Read replica usage:** Delivery log reads (analytics, debugging) go to a read replica. In-app notification reads go to the primary — we need read-your-writes consistency for the push/in-app coherence guarantee described in Section 2.3. Preference reads go to Redis cache first, PostgreSQL primary on cache miss. We do not use the read replica for preference reads because a stale preference read has compliance implications.

**Overflow table interaction with normal workloads:** During a Redis outage, the overflow table receives up to ~1,770 rows/sec. This is additive to the normal in-app and delivery log write load, bringing peak combined writes to ~4,000 rows/sec — still within the provisioned instance's capacity. The risk is not throughput; it is lock contention if drain workers and ingestion workers are both hammering the overflow table simultaneously. We mitigate this with a dedicated overflow table connection pool (10 connections, separate from the main pool) and advisory locks on drain batches.

### 2.3 Push/In-App Consistency

The previous draft described push and in-app as having "genuinely different operational profiles" without examining the user-visible consistency requirement between them. Here is the problem and the solution.

**The problem:** A user receives a push notification for event E. They tap the notification, which deep-links into the app. The app fetches the in-app notification for event E from PostgreSQL. If the in-app write hasn't completed yet — or if the WebSocket pub/sub was degraded and the client is polling — the user sees either a missing notification or an empty state. This is a visible inconsistency that degrades trust in the notification system.

**Root cause:** In-app notifications write directly to PostgreSQL (bypassing the queue), while push notifications go through the queue. The in-app write happens at routing time; the push notification is dispatched later, after queue processing. Under normal conditions, the in-app write completes before the push notification is delivered. Under load, this ordering can invert.

**Solution: in-app write precedes push dispatch.**

The router writes the in-app notification to PostgreSQL *before* enqueuing the push notification. The push worker does not dispatch until it receives confirmation that the in-app write succeeded. This is implemented as follows:

1. Router writes in-app notification to PostgreSQL. On success, records `notification_id` and `in_app_written_at` timestamp.
2. Router enqueues push notification with `requires_in_app: true` and `in_app_notification_id: <id>`.
3. Push worker, before dispatching, verifies the in-app notification exists via a point lookup on `notification_id` (indexed, fast). If it doesn't exist (write failed or rolled back), the push worker logs an error and does not dispatch — a missing in