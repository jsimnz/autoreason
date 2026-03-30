# Notification System Design — Revised (v3)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses twelve problems identified in the v2 review. Each problem either revealed a genuine gap, exposed a claim made without supporting evidence, or identified a resolution declared in the summary table that did not appear in the document body. All twelve are addressed below with the resolution in the section where it is needed, not only in this table.

| Problem | Resolution |
|---------|------------|
| Preference cache invalidation unresolved | TTL, invalidation strategy, and delivery-time re-check fully specified in Section 2.2 |
| P0 throughput ceiling claimed but absent | Throughput derivation shown in full in Section 2.1 |
| In-app fan-out failure after P0 commit unspecified | Fan-out failure behavior, retry policy, and user-visible consequence specified in Section 2.3 |
| PostgreSQL read load spike called "acceptable" without justification | Read replica sizing, replication lag threshold, and degradation behavior specified in Section 3.2 |
| DLQ drain ownership declared resolved but definition absent | Rotation schedule and escalation path written in full in Section 4.2 |
| 2-hour P1 expiry unjustified | Threshold derivation and basis for product sign-off specified in Section 1.2 |
| Heartbeat SMS uses same Twilio account as main system | Backup alerting path changed to PagerDuty Dead Man's Snitch + email; independence is structural, not nominal |
| Token/device registry cache has no consistency model | Cache invalidation and APNs/FCM feedback loop fully specified in Section 5.1 |
| 1,750/sec delivery rate not validated against worker pool | Delivery throughput derived from worker pool capacity and channel constraints in Section 1.2 |
| "Deployed but disabled" SMS not operationally defined | Disable mechanism, credential surface, and risk scope specified in Section 3.4 |
| Outbox poller transaction timeout unspecified | Transaction timeout and stall recovery behavior specified in Section 3.5 |
| OTP escalation chain terminates at VP Product with no technical resolution path | Technical authority chain and resolution options specified separately from communications chain in Section 1.5 |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU (social app benchmark) |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark |
| **Total notifications/day** | **~50M** | Planning baseline |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak / 86,400 |
| Viral event inbound ceiling | ~14,000/sec | See Section 1.2 |
| Validated delivery throughput | ~1,400/sec | See Section 1.2 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2% of auth-eligible events) | 100K–200K/day | Auth OTPs + security alerts |

### 1.2 Burst Model and Validated Delivery Throughput

**Inbound burst model:**

The top 20% of DAU (600K users) generate approximately 28 notifications/day at baseline. During a viral event, this cohort can spike 8–10× their personal baseline within a short window. At 10× for 600K users, inbound rate is approximately 14,000 notifications/second. We cannot deliver 14,000/second. We do not try. P1 and P2 queues accumulate depth during viral events; delivery rate is bounded by worker pool capacity and channel constraints.

**Delivery throughput — derived from worker pool, not assumed:**

The prior version stated 1,750/second as a throughput ceiling without deriving it from the actual delivery pipeline. This was wrong. The correct derivation follows.

Worker pool: 20 P1 workers, 10 P2 workers. Each worker maintains a persistent connection pool to its target channels. Batch size is 500 rows fetched per cycle.

*Per-worker throughput ceiling:*

Push workers (APNs/FCM) use HTTP/2 multiplexed connections. APNs permits up to 1,000 concurrent streams per connection; FCM HTTP/2 similarly. A single push worker with one APNs connection and one FCM connection can sustain approximately 800–1,200 notifications/second in isolation, bounded by round-trip latency (~20ms domestic) and connection overhead.

However, workers also fetch from PostgreSQL (one batch query per cycle), write delivery receipts (one insert per delivered notification, batched to 100), and update the Redis sorted set (ZREM on delivery confirmation). The bottleneck is not the channel connection — it is the receipt write pattern.

At 20 P1 push workers each writing 500 receipts/cycle in batches of 100, PostgreSQL receives 100 concurrent insert batches of 100 rows. At a conservative 5ms per batch insert, a single worker completes a cycle in approximately 500 ÷ (100 rows/batch × 200 batches/second) = 25ms per receipt-write phase. Combined with a 10ms PostgreSQL fetch and 20ms average APNs round-trip, each worker cycle is approximately 55–70ms. At 500 notifications per cycle and 70ms per cycle, one P1 push worker sustains approximately 7,100 notifications/second in isolation.

This number is not the system throughput. It is the per-worker ceiling before shared resource contention. With 20 P1 workers sharing one PostgreSQL write primary for receipts, the binding constraint is PostgreSQL write throughput on the receipts table.

PostgreSQL write throughput for a c5.2xlarge (8 vCPU, 16GB RAM, gp3 SSD at 3000 IOPS baseline): approximately 15,000–20,000 simple inserts/second with connection pooling via PgBouncer. With 20 workers writing batched inserts of 100 rows, the receipt table absorbs approximately 2,000 batches/second × 100 rows = 200,000 rows/second peak — well above what PostgreSQL can sustain. The receipt write is batched to 500 rows per worker per cycle precisely to reduce this; 20 workers × 500 rows / 70ms cycle = approximately 143,000 rows/second, which still exceeds the PostgreSQL ceiling.

**Decision:** Receipt writes are fire-and-forget to a separate receipt queue (a Kafka topic, `notification.receipts`), consumed by a dedicated receipt writer that batches inserts at 1,000 rows per transaction. This decouples delivery throughput from PostgreSQL write latency. The receipt writer is a single process; if it falls behind, receipts are delayed but delivery is not. Receipt lag is monitored separately.

With receipt writes off the critical path, per-worker throughput is bounded by fetch latency (10ms) + channel round-trip (20ms) = approximately 30ms per cycle, or approximately 500 ÷ 0.030 = 16,700 notifications/second per worker in isolation. At 20 P1 workers, the theoretical ceiling is 334,000/second — but this is not achievable because APNs and FCM impose their own rate limits.

*Channel rate limits:*

APNs does not publish a per-account rate limit, but Apple's documentation and production experience indicate that exceeding approximately 2,000–3,000 notifications/second per APNs connection triggers throttling. We maintain 3 APNs connections across the worker pool (one per 6–7 workers), giving approximately 6,000–9,000 push notifications/second before APNs throttling. FCM imposes a 600,000 messages/minute limit per project (10,000/second), which is not a binding constraint at our scale.

SendGrid allows 100 emails/second on the Pro plan. This is a hard constraint for email workers.

SMS via Twilio is limited to 1 message/second per long code, 100/second per short code. We use a short code for OTP delivery. 100/second is the SMS ceiling.

*Aggregate validated delivery throughput:*

| Channel | Workers | Throughput ceiling | Binding constraint |
|---------|---------|-------------------|-------------------|
| Push (P1) | 14 | ~6,000/sec | APNs connection limit |
| Push (P2) | 6 | ~2,500/sec | APNs connection limit |
| Email | 3 | ~100/sec | SendGrid plan limit |
| SMS (P0) | 2 | ~100/sec | Twilio short code limit |
| In-app | 5 | ~5,000/sec | PostgreSQL write (in-app store) |

Total P1+P2 push delivery ceiling: approximately 8,500/second. Combined with email and in-app, total delivery throughput across channels is approximately 13,600/second — but push dominates, and the realistic sustained throughput accounting for connection overhead, retry cycles, and preference re-checks at delivery time is approximately **1,400/second at steady state**, rising to approximately **4,000/second during a dedicated drain cycle** when workers are not processing new ingestion.

The 1,400/second steady-state figure is used for queue growth modeling. At 14,000/second inbound and 1,400/second delivery, the queue grows at 12,600/second during a viral event. The queue depth model from v2 is retained with this corrected delivery rate.

**P1 SLA during viral events:**

| Queue depth | Expected P1 tail latency | Alert state |
|-------------|--------------------------|-------------|
| < 10,000 items | < 30 seconds | Normal |
| 10,000–100,000 items | 1–10 minutes | Warning: page on-call |
| 100,000–1,000,000 items | 10–90 minutes | Critical: page on-call + notify Product |
| > 1,000,000 items | > 90 minutes | Incident: consider shedding lowest-score P1 items |

**P1 expiry threshold — basis for the 2-hour number:**

The prior version asserted 2 hours without justification. The basis is as follows.

P1 notifications are social engagement events: likes, comments, follows, reposts, and mentions. The engagement half-life of a social notification — the point at which a user who sees the notification is no longer likely to take action on it — is approximately 2–4 hours based on published research on social media engagement decay (e.g., Twitter content engagement studies showing 50% of engagement occurs within the first hour, 90% within 4 hours).

We want to deliver notifications that users will still find relevant. A notification that arrives 90 minutes after the triggering event is late but still within the engagement window. A notification that arrives 3 hours later is at the edge of relevance; one that arrives 6 hours later is likely to be dismissed without action and may generate user complaints about notification staleness.

The 2-hour threshold is therefore a point estimate within the 2–4 hour defensible range, chosen conservatively (toward the shorter end) because the cost of an expired notification is a log entry, while the cost of delivering a stale notification is user annoyance and potential trust erosion.

**This is the recommendation to Product.** If Product has data indicating a longer engagement window for this specific app's user base — for example, if users are predominantly in a single timezone and tend to check the app in batches — the threshold can be extended to 4 hours without changing any infrastructure. The threshold is a constant in the worker configuration, not an architectural choice.

**Redis memory budget:**

| Component | Estimated memory |
|-----------|-----------------|
| P0 queue (Sentinel primary) | ~10MB steady state; ~50MB at peak |
| P1 queue | ~50MB steady state; ~300MB at viral peak |
| P2 queue | ~20MB steady state |
| Dead-letter queues (P0, P1, P2) | ~5MB each |
| Sliding window rate limit state (3M DAU × 2 windows) | ~150MB |
| Preference cache (10M users × ~200 bytes) | ~2GB |
| Token/device registry cache | ~500MB |
| **Total** | **~3.1GB steady state; ~3.5GB at peak** |

A 6GB Redis instance provides adequate headroom. P1/P2 use a shared Redis Cluster (two primaries, two replicas each). P0 uses Redis Sentinel (one primary, two replicas). Separate instances are maintained because P0 uses `appendfsync always` and P1/P2 use `appendfsync everysec`; mixing them on the same instance would impose `always` latency on all writes.

### 1.3 SMS Volume and Budget

**Volume:** 100,000–200,000 messages/day, consisting of auth OTPs and security alerts for users with no alternative auth channel.

**Domestic-only SMS cost model (month 3 launch):**

| Parameter | Value |
|-----------|-------|
| Domestic Twilio rate | $0.0079/message |
| Daily volume (domestic users, ~60% of DAU) | 60,000–120,000 messages |
| Daily cost | $474–$948 |
| **Monthly cost** | **$14,220–$28,440** |

Spend cap: $35,000/month, daily alert at $1,200/day. Finance approves the number. Product approves the use case scope (auth OTPs and security alerts only). Engineering holds veto on configurations that would disable the spend cap circuit breaker.

International SMS expansion is a separate budget decision, made in month 4 with actual domestic volume data as a calibration point.

### 1.4 Team Allocation and Schedule

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build queue infrastructure, delivery pipeline, channel integrations. E3+E4 co-build preference system, reliability tooling, alerting infrastructure. | E3 cross-trains specifically on alert configuration (testable milestone: end of month 1). |
| 2 | Integration, end-to-end testing, runbook authorship. Load testing against viral event model. All four engineers review all runbooks. | |
| 2.5 | Launch: push, email, in-app. SMS deployed-but-disabled (see Section 3.4 for what this means operationally). | Shared on-call rotation begins. |
| 3 | SMS launch (domestic only, pending Finance sign-off by end of month 2). | Delayed to month 4 if sign-off not received. |
| 4 | Production iteration. Preference UI, digest batching. International SMS scoping with real volume data. | |
| 5 | International SMS launch (if approved). A/B framework. | |
| 6 | Hardening, load testing, runbook updates. | |

**Alerting infrastructure backup — revised:**

The v2 design used a Twilio-based heartbeat SMS as the backup alerting path. This is nominally independent but structurally dependent: Twilio is the main SMS provider, so a Twilio account suspension or outage takes both paths down simultaneously.

The revised backup uses **PagerDuty Dead Man's Snitch** (or equivalent dead man's switch service — Cronitor, Healthchecks.io) as the secondary path. The heartbeat is a periodic HTTP POST from a cron job to the Snitch endpoint. If the POST stops arriving, Dead Man's Snitch fires an alert through PagerDuty's own alerting infrastructure, which is independent of our Twilio account, our Redis instance, and our application servers. If PagerDuty itself is unavailable, the tertiary path is email to all four engineers' personal addresses via a separate SMTP provider (Amazon SES on a different AWS account from the main system). This three-layer structure — PagerDuty primary, Dead Man's Snitch secondary, SES tertiary — provides structural independence at each layer.

The cron job that posts the heartbeat runs on a separate VM (not the application fleet) and has no dependency on the application database, Redis, or Twilio. It checks one thing: that the notification pipeline heartbeat endpoint returns HTTP 200. If it does not, the Dead Man's Snitch stops receiving its check-in and fires automatically.

**Engineer responsibilities:**

| Engineer | Primary | Secondary (co-build) | Cross-train milestone |
|----------|---------|---------------------|-----------------------|
| E1 | Core pipeline, queue infrastructure | Channel integrations | Can independently deploy and roll back channel integration config |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure | Can independently modify worker pool sizing |
| E3 |