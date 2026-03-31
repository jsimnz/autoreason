# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M MAU.

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

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. Re-engagement campaigns (month 5) are explicitly push and email only — the SMS gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. See Section 3.3.

**On push volume:** 5 notifications/day/installed user is a deliberate product constraint, not a technical one. We monitor opt-out rates weekly. Alert threshold derivation is in Section 1.4.

These are estimates. We instrument from day one and publish a traffic model review in month 2.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** "Cross-training" in the sense of watching someone else work does not constitute coverage ability. The mitigation is paired ownership, documented runbooks, and a demonstrated coverage capability verified before each channel launches — not a checkbox.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 (in-app storage) |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability, verified before the channel goes live:

1. **Runbook authorship:** The primary owner writes the runbook. The coverage partner must be able to execute every step without asking the primary owner for clarification. If they can't, the runbook is incomplete — not the partner.
2. **Independent incident simulation:** Before a channel goes live, the coverage partner independently handles a simulated incident (staging environment, pager goes to coverage partner only, primary owner is unavailable). The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it, the channel does not launch.
3. **Solo on-call rotation:** Each coverage partner carries solo on-call for their partner's channel for at least one week before that channel reaches full traffic. Problems surfaced during solo on-call are fixed before launch.

This means E4 carries solo push on-call during month 1 (before push launches in month 2). E2 carries solo email on-call during months 1–2 (before email digests launch in month 3). E3 carries solo SMS on-call during month 2 (before SMS launches in month 3).

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — not for the authors.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification This Month |
|-------|-------------|----------------------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | E4 completes solo push on-call (before push launches month 2) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E2 completes solo email on-call (before digests launch month 3) |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 completes solo SMS on-call |
| 4 | Full preference management, suppression lists, advanced batching | — |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Validation testing to 3× peak (design envelope) + stress testing to 4× (beyond design); chaos testing on established baselines | — |

**On month 6 testing:** The system is designed for 3× peak throughput. Testing to 3× validates the design envelope is met — this has explicit pass/fail criteria. Testing to 4× is deliberate stress-beyond-design: we expect degradation and want to characterize it (does backpressure engage? does it fail gracefully?). These are different tests with different success criteria, not a single "load test at 4×." Because FCM throughput analysis shows minimal headroom at 3× during FCM degradation, the 4× stress test uses a mocked FCM endpoint to isolate our system's behavior from Google's. Both tests run against a production-mirror staging environment that has been running continuously since month 2. Month 6 formalizes this into a documented capacity envelope. Chaos experiments test specific failure hypotheses against four months of established baselines — not general system behavior.

### 1.4 Opt-Out Rate Threshold Derivation

Setting a fixed opt-out alert threshold without statistical grounding produces either chronic false positives (eroding alert trust) or missed real signals. Here is the approach.

**Establishing a baseline:** For the first 8 weeks of push operation, we measure opt-out rates without alerting on them, building a distribution of weekly rates. After 8 weeks, we compute the mean (μ) and standard deviation (σ) of weekly opt-out rates.

**Alert thresholds:**
- **P2 (investigate):** Weekly opt-out rate exceeds μ + 2σ. At 2σ, we expect a false positive roughly 1 in 20 weeks — acceptable for an investigation-level alert.
- **P1 (page):** Weekly opt-out rate exceeds μ + 3σ. At 3σ, false positive rate is approximately 1 in 370 weeks.

**Pre-baseline interim:** Before 8 weeks of data, we use an absolute threshold of 2% of push-eligible users (140K) opting out in a single week. This is deliberately conservative — it fires only on genuinely anomalous behavior.

**Leading indicator:** We also track opt-out rate by notification type. If "like" notifications drive disproportionate opt-outs, we adjust frequency caps for that type before the aggregate rate crosses the alert threshold. Aggregate opt-out rate is a lagging indicator; per-type opt-out rate is a leading one.

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
  (Redis Sorted Set + Lua scripts)         (PostgreSQL, partitioned by user_id % 64)
  (Redis Sentinel, 3-node cluster)                 │
     │                                             ▼
     ├── P0 Worker Pool (dedicated Redis keyspace) [WebSocket Pub/Sub]
     ├── P1 Worker Pool (20 workers)               (Redis, best-effort)
     └── P2 Worker Pool (10 workers)               │
          │                                        ▼
          ▼                              [Push/In-App Consistency Layer]
   [Channel Dispatcher]                  (see Section 2.3)
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — type allowlist enforced here)
          │
          ▼
   [Delivery Log]
   (PostgreSQL, partitioned by month; S3 archive after 30 days, deleted after 13 months)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures, token invalidation)
```

### 2.2 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues create operational complexity: N queues to monitor, N dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set handles 51M items comfortably. The tradeoff is that per-channel rate limiting requires logic in the dispatcher rather than queue topology. Acceptable at 10M MAU; revisited at 50M.

**P0 isolation within the queue.**
P0 notifications (security alerts, auth codes) use a dedicated Redis keyspace — a separate sorted set processed by dedicated workers — rather than competing with P1/P2 in the same sorted set. This is a narrow exception to the single-queue principle: P0 volume is small (<0.1% of total), the isolation is operationally simple (same Redis cluster, different key prefix), and it prevents a P1/P2 backlog from degrading P0 latency.

**P0 SLA:** Delivered within 10 seconds of routing, or paged as a P1 incident.
**P1 SLA:** Delivered within 60 seconds under normal load.
**P2 SLA:** Best-effort within the batch window.

**Redis serves multiple functions — this is the primary infrastructure risk.**
Redis is the priority queue, preference cache, WebSocket pub/sub channel, APNs JWT store, and worker coordination layer. A Redis outage degrades all of these simultaneously. We treat this explicitly with per-function fallbacks rather than pretending the risk doesn't exist. See Section 5 for the complete fallback design.

**Synchronous preference check at routing time, with compliance mitigation.**
User preferences are cached in Redis with 5-minute TTLs and write-through invalidation on any preference update. Checking at routing keeps workers stateless and fast, and avoids consuming queue capacity for notifications we'll discard.

The compliance risk is bounded but real: a user who opts out after a notification is routed but before it is dispatched will still receive that notification — a window of up to 5 minutes under normal conditions. We handle this as follows:
- Marketing and re-engagement notifications perform a second preference check immediately before dispatch, paying the latency cost for the channel with the highest compliance exposure.
- Transactional and social notifications do not perform the second check. The 5-minute window is documented in our privacy policy as consistent with "reasonable technical delay."
- Any user who contacts support about receiving a notification after opting out receives immediate suppression and a manual audit.

This is a documented, bounded risk — not a perfect solution. The second check for marketing notifications is the operationally meaningful mitigation; the privacy policy language alone is not sufficient.

**In-app notifications bypass the queue.**
In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They're read-heavy, need random access by user, and benefit from immediate consistency. Routing them through the push queue adds latency with no benefit. The tradeoff is two code paths to maintain; we accept this because the operational profiles are genuinely different. The consistency requirement between push and in-app is addressed in Section 2.3.

**Managed providers over self-hosted.**
We use FCM/APNs directly, SendGrid for email, and Twilio for SMS. We do not self-host SMTP, build custom push infrastructure, or run our own message broker beyond Redis. The tradeoff is vendor dependency and cost; the benefit is that 4 engineers don't spend 6 months building infrastructure instead of product features.

### 2.3 Push/In-App Consistency

**The problem:** A user receives a push notification for event E. They tap it, deep-linking into the app. The app fetches the corresponding in-app notification from PostgreSQL. If the in-app write hasn't completed yet — or if the WebSocket pub/sub was degraded and the client is polling — the user sees a missing notification or an empty state. This is a visible inconsistency that degrades trust in the notification system.

**Root cause:** In-app notifications write directly to PostgreSQL (bypassing the queue), while push notifications go through the queue. Under normal conditions, the in-app write completes before the push notification is delivered. Under load, this ordering can invert.

**Solution: in-app write precedes push dispatch.**

1. The router writes the in-app notification to PostgreSQL *before* enqueuing the push notification. On success, it records `notification_id` and `in_app_written_at`.
2. The router enqueues the push notification with `requires_in_app: true` and `in_app_notification_id`.
3. The push worker, before dispatching, verifies the in-app notification exists via a point lookup on `notification_id` (indexed). If it doesn't exist (write failed or rolled back), the push worker logs an error and does not dispatch. A missing in-app notification with a delivered push creates a worse user experience than a missed push.
4. If the in-app write fails, the router retries up to 3 times with exponential backoff before dropping the notification and logging a P2 alert. We do not enqueue the push if the in-app write cannot be confirmed.

**Latency cost:** The in-app write adds ~5ms to routing latency for notifications that require both channels. Acceptable — this is not on the critical path for P0 notifications (which are push-only or SMS, never in-app).

**WebSocket degradation:** When WebSocket pub/sub is unavailable, clients fall back to polling on a 30-second interval. The in-app notification is always in PostgreSQL first, so polling clients will eventually see it. The push notification is delivered after the in-app write succeeds, so the tap-to-content path is always coherent.

### 2.4 PostgreSQL Write Load Analysis

The write workloads must be examined together, not independently, because they share infrastructure.

**Write sources and estimated volume:**

| Workload | Write Volume | Pattern |
|----------|-------------|---------|
| In-app notification inserts | ~15M rows/day (~175/sec avg, ~525/sec peak) | Bursty, clustered around social events |
| Delivery log inserts | ~51M rows/day (~590/sec avg, ~1,770/sec peak) | Mirrors total notification volume |
| Preference updates | ~100K/day (~1/sec) | Low volume, high-importance |
| Token invalidation updates | ~500K/day (~6/sec) | Bursty after push campaigns |
| Overflow table (Redis fallback) | ~0 normally; up to ~1,770/sec during Redis outage | Exceptional only