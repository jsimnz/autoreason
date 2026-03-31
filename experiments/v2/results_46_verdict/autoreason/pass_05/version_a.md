# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. The trigger criteria for revisiting this decision are defined in Section 2.3 as measurable operational thresholds, not lagging headcount or MAU milestones.

Every tradeoff is explicit. Where we accept risk, we name it and specify the mitigation. Where we defer complexity, we state the measurable trigger for revisiting.

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

**On SMS volume:** At Twilio's volume pricing (~$0.0075/message), 1M SMS/day is $225K/month — an existential budget problem. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month). SMS is treated as a privileged channel with hard gates throughout this document. Re-engagement campaigns (month 5) are explicitly push and email only. The SMS gate is enforced at the channel dispatcher with an allowlist of permitted notification types, not by convention. Allowlist governance is described in Section 3.3 — the allowlist requires two-engineer sign-off to modify and is version-controlled.

**On push volume:** 5 notifications/day/installed user is a deliberate product constraint, not a technical one. We monitor opt-out rates from day one. Threshold derivation and the pre-baseline interim period are described in Section 1.4, including an honest assessment of the interim threshold's risk.

These are estimates. We instrument from day one and publish a traffic model review in month 2.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** "Cross-training" in the sense of watching someone else work does not constitute coverage ability. The mitigation is paired ownership, documented runbooks, and demonstrated coverage capability verified before each channel launches — not a checkbox.

| Engineer | Primary Responsibility | Channel Ownership | Coverage Partner |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | E3 |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | E4 |
| E3 | Preference management, user-facing API, suppression logic | In-app | E1 |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | E2 |

**What "coverage partner" means operationally:**

Coverage is a demonstrated capability, verified before the channel goes live:

1. **Runbook authorship:** The primary owner writes the runbook. The coverage partner must be able to execute every step without asking the primary owner for clarification. If they can't, the runbook is incomplete — not the partner.
2. **Independent incident simulation:** Before a channel goes live, the coverage partner independently handles a simulated incident in staging (pager goes to coverage partner only; primary owner is unavailable). The scenario is drawn from the runbook's documented failure modes. If the coverage partner cannot resolve it, the channel does not launch.
3. **Solo on-call rotation:** Each coverage partner carries solo on-call for their partner's channel for at least one week before that channel reaches full traffic. Problems surfaced during solo on-call are fixed before launch.

**The realistic constraint on E4's month 1 workload:** The coverage verification schedule requires E4 to complete solo on-call in month 1. This is only feasible if scope is bounded. In month 1, E4's solo on-call covers queue health, worker health, and in-app delivery — not FCM/APNs integrations that aren't live yet. E4's email/SMS integration work is scoped to design and scaffolding in month 1, with implementation in month 2. This is a deliberate sequencing choice: E4's DevOps and monitoring work in month 1 directly enables the coverage verification. If month 1 scope proves unachievable, push launch in month 2 slips — not the coverage requirement.

**What this doesn't solve:** If two engineers are simultaneously unavailable, we have a coverage gap. With 4 engineers this is unavoidable. The mitigation is that runbooks are written for a competent backend engineer unfamiliar with the system — not for the authors.

### 1.3 Delivery Milestones

| Month | Deliverable | Coverage Verification This Month |
|-------|-------------|----------------------------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API | E4 completes solo on-call for queue/in-app scope (bounded; FCM/APNs excluded) |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring | E2 completes solo email on-call; E4 extends push coverage to full scope |
| 3 | Email digests, SMS (auth only), aggregation logic | E3 completes solo SMS on-call |
| 4 | Full preference management, suppression lists, advanced batching | — |
| 5 | Re-engagement campaigns (push + email only; SMS gate enforced at dispatcher), A/B framework | — |
| 6 | Validation testing to 3× peak (explicit pass/fail criteria) + stress testing to 4× (characterize graceful degradation); chaos testing against baselines established since month 2 | — |

**On month 6 testing:** Testing to 3× validates the design envelope — this has explicit pass/fail criteria. Testing to 4× is deliberate stress-beyond-design: we expect degradation and want to characterize it (does backpressure engage? does it fail gracefully?). These are different tests with different success criteria, not a single "load test at 4×." The 4× stress test uses a mocked FCM endpoint to isolate our system's behavior from Google's, because FCM quota analysis (Section 6.1) shows minimal headroom at 3× during FCM degradation scenarios. Both tests run against a production-mirror staging environment running continuously since month 2. Month 6 formalizes this into a documented capacity envelope. Chaos experiments test specific failure hypotheses against four months of established baselines — not general system behavior.

### 1.4 Opt-Out Rate Threshold Derivation

Setting a fixed opt-out alert threshold without statistical grounding produces either chronic false positives (eroding alert trust) or missed real signals.

**Establishing a baseline:** For the first 8 weeks of push operation, we measure opt-out rates without alerting on them, building a distribution of weekly rates. After 8 weeks, we compute the mean (μ) and standard deviation (σ) of weekly opt-out rates.

**Alert thresholds post-baseline:**
- **P2 (investigate):** Weekly opt-out rate exceeds μ + 2σ. At 2σ, we expect a false positive roughly 1 in 20 weeks — acceptable for an investigation-level alert.
- **P1 (page):** Weekly opt-out rate exceeds μ + 3σ. At 3σ, false positive rate is approximately 1 in 370 weeks.

**Pre-baseline interim — honest risk assessment:** Before 8 weeks of data, we use an absolute threshold of 2% of push-eligible users (140K) opting out in a single week. This threshold is *permissive*, not conservative. 140,000 opt-outs represents permanent damage to the push-addressable audience — these users do not come back. The threshold is set this high during the pre-baseline period specifically to avoid false positives that would erode alert trust before we have statistical grounding, but we are explicitly accepting audience risk in exchange.

The mitigation for this risk is not the aggregate threshold — it is the per-type leading indicator described below. The aggregate interim threshold is a last-resort backstop, not the primary protection mechanism.

**Leading indicator (primary early warning):** We track opt-out rate by notification type from day one, before the baseline period ends. Per-type alert threshold: if any notification type drives opt-outs at more than 3× the rate of other types in the same week, that is a P2 investigation. If "like" notifications or any other type are driving disproportionate opt-outs, this alert fires before the aggregate 2% threshold is approached, allowing frequency cap adjustment before permanent audience damage accumulates.

---

## 2. System Architecture

### 2.1 Redis Memory Budget

Before describing the architecture that depends on Redis, we establish that Redis can actually support it. Redis serves multiple functions in this system; their memory requirements must be sized together.

**Redis Sentinel cluster configuration:** 3 nodes, each with 32GB RAM allocated to Redis. We target a maximum Redis memory utilization of 70% (22GB), leaving 30% headroom for memory spikes, fragmentation, and replication buffer.

**Memory budget by function:**

| Function | Entries | Bytes/Entry | Total | Notes |
|----------|---------|-------------|-------|-------|
| Priority queue (P1/P2 sorted set) | 5M | 150 bytes | 750MB | Peak in-flight; processed entries are removed. 5M is a ~47× buffer over normal in-flight volume |
| P0 sorted set (dedicated keyspace) | 500 | 150 bytes | <1MB | P0 volume is <0.1% of total; ~1.7/sec at peak |
| Preference cache | 10M users | 200 bytes | 2GB | All MAU cached; TTL 5 min with LRU eviction |
| WebSocket pub/sub channels | 3M active sessions | 100 bytes | 300MB | DAU only; channels expire on disconnect |
| APNs JWT store | 1 JWT per app key | ~500 bytes | <1MB | Rotate every 30 min; minimal entries |
| Worker coordination (locks, heartbeats) | ~100 keys | ~1KB | <1MB | Negligible |
| **Total estimated** | | | **~3.1GB** | |
| **Safety margin (3×)** | | | **~9.3GB** | Accounts for overhead, fragmentation, key expiry lag |
| **Headroom remaining** | | | **12.7GB** | Against 22GB target ceiling |

**Key clarification on queue memory:** The sorted set does not hold 51M entries simultaneously. Entries are enqueued and dequeued continuously; the set size reflects in-flight notifications. At peak throughput of 1,770/sec with a P1 SLA of 60 seconds, maximum in-flight entries are ~106K under normal operation. The 5M figure is a conservative 47× buffer for queue backup scenarios.

**The 32GB node specification is the binding constraint.** If Redis memory utilization crosses 80% in production, that is a defined trigger for architectural review — not a MAU milestone. See Section 2.3 for the complete set of review triggers.

### 2.2 High-Level Data Flow

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
  - In-app write BEFORE push enqueue (see Section 2.4)
     │
     ├─────────────────────────────────────────────┐
     ▼                                             ▼
[Priority Queue]                          [In-App Store]
  (Redis Sorted Set + Lua scripts)         (PostgreSQL, partitioned by user_id % 64)
  (Redis Sentinel, 3-node cluster)                 │
     │                                             ▼
     ├── P0 Worker Pool (min 3, dedicated)  [WebSocket Pub/Sub]
     ├── P1 Worker Pool (20 workers)         (Redis, best-effort)
     └── P2 Worker Pool (10 workers)                │
          │                                         ▼
          ▼                               [Push/In-App Consistency Layer]
   [Channel Dispatcher]                   (see Section 2.4)
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — type allowlist enforced here; see Section 3.3)
          │
          ▼
   [Delivery Log]
   (PostgreSQL, partitioned by user_id % 64 + date)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures, token invalidation)
```

### 2.3 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues create operational complexity: N queues to monitor, N dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set handles the in-flight volume comfortably (as demonstrated in Section 2.1). The tradeoff is that per-channel rate limiting requires logic in the dispatcher rather than queue topology. Acceptable at 10M MAU.

**Trigger criteria for revisiting the single-queue design:**
These are measurable thresholds, monitored continuously from month 2 onward. Crossing any threshold triggers an architectural review within 2 weeks — not at a MAU milestone, which is a lagging indicator that arrives after the system is already under stress.

| Metric | Review Trigger | Rationale |
|--------|---------------|-----------|
| Redis memory utilization | >80% of allocated 32GB | Approaching ceiling before headroom is consumed |
| P1 queue depth | >500K entries sustained >5 min | Workers cannot keep up with ingestion |
| P1 worker saturation | >90% CPU sustained >10 min | Worker pool is the bottleneck |
| P1 SLA miss rate | >1% of notifications miss 60s SLA | SLA violated at measurable rate |
| Channel dispatcher error rate | >5% for any channel | Provider integration is saturated |
| PostgreSQL write latency (p99) | >100ms for delivery log inserts | Write path is degrading |

The review is a structured decision: does the data support architectural change, or is the trigger a transient spike? The outcome is documented regardless.

**P0 isolation within the queue.**
P0 notifications (security alerts, auth codes) use a dedicated Redis keyspace — a separate sorted set with a minimum of 3 dedicated workers — rather than competing with P1/P2. P0 volume is <0.1% of total. This is a narrow exception to the single-queue principle: the isolation is operationally simple (same Redis cluster, different key prefix), and it prevents a P1/P2 backlog from degrading P0 latency. P0 SLA: delivered within 10 seconds of routing, or paged as a P1 incident.

**Redis serves multiple functions — this is the primary infrastructure risk.**
Redis is the priority queue, preference cache, WebSocket pub/sub channel, APNs JWT store, and worker coordination layer. A Redis outage degrades all of these simultaneously. We treat this explicitly with per-function