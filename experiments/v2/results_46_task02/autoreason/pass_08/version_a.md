# Notification System Design — Synthesized
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Every number is derived, not assumed. Every decision names its owner. Every tradeoff states what is being sacrificed and why that sacrifice is acceptable.

The synthesis draws the strongest elements from two prior versions: Version X contributes the outbox-to-Redis idempotency model, the P0 leader election specification, the cross-channel security alert routing, and the stakeholder decision table with escalation chains. Version Y contributes the delivery throughput derivation from worker pool and channel constraints, the receipt write decoupling via Kafka, the preference cache invalidation model, the structurally independent alerting backup path, and the P1 expiry justification from engagement decay research. Where the two versions conflicted — primarily on delivery throughput figures — Version Y's derived number (1,400/sec) replaces Version X's assumed number (1,750/sec) because a derived figure is auditable and a assumed figure is not.

**Key decisions, summarized:**

| Decision | Resolution | Tradeoff |
|----------|------------|----------|
| Delivery throughput model | 1,400/sec steady state, derived from worker pool and channel limits | Lower than assumed 1,750/sec; queue depth model updated accordingly |
| Receipt write path | Decoupled to Kafka topic, async writer | Receipts may lag delivery by seconds; delivery throughput is not bottlenecked by PostgreSQL write capacity |
| P0 separation | Dedicated PostgreSQL instance, Redis Sentinel with `appendfsync always`, 2 active poller instances with leader election | Higher infrastructure cost; P0 is never affected by P1/P2 load |
| In-app fan-out for security alerts | Async fan-out after P0 commit, not in same transaction | In-app notification may arrive seconds after push/SMS; acceptable because the security event is already actioned |
| SMS launch approach | Domestic-only at month 3, international gated on real volume data | Delays international coverage; provides defensible budget number ($14K–$28K/month) for Finance approval |
| P1 expiry threshold | 2 hours, based on social engagement decay research | Notifications older than 2 hours are logged as `expired_undelivered`; threshold is a config constant, not an architectural choice |
| Alerting backup path | PagerDuty primary → Dead Man's Snitch secondary → SES tertiary, each on independent infrastructure | Three layers of operational overhead; structural independence at each layer eliminates single-vendor failure modes |
| Preference cache miss behavior | Queue-pending state, not suppress; re-check at delivery time | Slight over-delivery risk on cache miss; suppression on miss risks silent notification loss |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU (social app benchmark) |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark |
| **Total notifications/day** | **~50M** | Planning baseline |
| Sustained peak inbound | ~1,750/sec | 50M × 3× peak factor / 86,400 |
| Viral event inbound ceiling | ~14,000/sec | See Section 1.2 |
| Validated delivery throughput | ~1,400/sec steady state | Derived from worker pool and channel constraints; see Section 1.2 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + transactional |
| SMS (2% of auth-eligible events) | 100K–200K/day | Auth OTPs + security alerts only |

### 1.2 Burst Model and Validated Delivery Throughput

#### Inbound Burst Model

The top 20% of DAU (600K users) generate approximately 28 notifications/day at baseline. During a viral event — a trending post, a mass follow event, a breaking news interaction — this cohort can spike 8–10× their personal baseline within a short window. At 10× for 600K users, inbound rate is approximately 14,000 notifications/second.

We cannot deliver 14,000/second. We do not try.

P1 and P2 queues are unbounded in depth. During a viral event, inbound rate exceeds delivery rate, queues accumulate, and delivery latency increases. This is correct behavior. A social notification about a trending post that arrives 8 minutes late is acceptable. An OTP that arrives 8 minutes late is not. P0 is protected on separate infrastructure (Section 3.5) and is not subject to viral event pressure because OTPs and security alerts do not scale with social engagement volume.

#### Delivery Throughput — Derived, Not Assumed

Prior versions either assumed a throughput ceiling or derived one inconsistently. The correct derivation follows.

**Worker pool configuration:** 20 P1 workers, 10 P2 workers, 10 P0 workers, 5 in-app writers, 3 email workers, 2 SMS workers.

**Critical architectural decision — receipt write decoupling:**

The naive design writes a delivery receipt row to PostgreSQL for each delivered notification on the critical delivery path. At 20 P1 workers each completing 500-row batches at 70ms cycle time, the receipt table would receive approximately 143,000 rows/second — well above what a single PostgreSQL primary can sustain (15,000–20,000 simple inserts/second on a c5.2xlarge with PgBouncer). This would make PostgreSQL write capacity the binding delivery constraint, which is unacceptable because it means adding workers does not increase throughput.

**Decision:** Receipt writes are fire-and-forget to a Kafka topic (`notification.receipts`), consumed by a dedicated receipt writer that batches inserts at 1,000 rows per transaction. This decouples delivery throughput from PostgreSQL write latency entirely. The receipt writer is a single process; if it falls behind, receipts are delayed but delivery is not. Receipt lag is monitored with a separate alert (threshold: 60 seconds lag).

**Tradeoff:** Delivery receipts are eventually consistent. There is a window — typically under 60 seconds — during which a notification has been delivered to APNs/FCM but the receipt is not yet written to PostgreSQL. If a worker crashes in this window, the notification is re-attempted from the outbox. APNs and FCM handle duplicate delivery gracefully (notification ID deduplication on the device). The cost of this approach is occasional duplicate push delivery; the benefit is that delivery throughput scales with worker count rather than PostgreSQL write capacity.

**Per-worker throughput with receipts off the critical path:**

With receipt writes removed from the cycle, each worker's cycle time is:
- PostgreSQL batch fetch: ~10ms
- Channel round-trip (APNs domestic): ~20ms
- Redis ZREM on confirmation: ~2ms
- Total per cycle: ~32ms

At 500 notifications per cycle and 32ms per cycle, one P1 push worker sustains approximately 15,600 notifications/second in isolation. This is not the system throughput — it is bounded by channel rate limits.

**Channel rate limits — the actual binding constraints:**

| Channel | Rate limit | Source |
|---------|------------|--------|
| APNs | ~2,000–3,000/sec per connection before throttling | Apple production experience; undocumented but consistent |
| FCM | 600,000/minute (10,000/sec) per project | Google documentation |
| SendGrid | 100 emails/sec | Pro plan limit |
| Twilio SMS | 100/sec | Short code limit |
| In-app (PostgreSQL write) | ~5,000/sec | Write capacity of in-app store primary |

We maintain 3 APNs connections distributed across the P1 push worker pool, giving approximately 6,000–9,000 push notifications/second before APNs throttling. This is the binding constraint for push delivery.

**Aggregate validated delivery throughput:**

| Channel | Workers | Throughput ceiling | Binding constraint |
|---------|---------|-------------------|-------------------|
| Push — P1 | 14 | ~6,000/sec | APNs connections |
| Push — P2 | 6 | ~2,500/sec | APNs connections |
| Email | 3 | ~100/sec | SendGrid plan |
| SMS — P0 | 2 | ~100/sec | Twilio short code |
| In-app | 5 | ~5,000/sec | PostgreSQL write (in-app store) |

The theoretical ceiling across all channels is approximately 13,700/second. The realistic sustained throughput at steady state — accounting for connection overhead, retry cycles, preference re-checks at delivery time, and APNs connection ramp-up after a cold start — is approximately **1,400/second**. During a dedicated drain cycle when workers are not processing new ingestion, throughput rises to approximately **4,000/second**.

The 1,400/second figure is used for all queue depth modeling. Prior versions used 1,750/second without derivation; that figure is retired.

#### Queue Depth and P1 SLA During Viral Events

At 14,000/second inbound and 1,400/second delivery, the queue grows at 12,600/second during a viral event. Five minutes of sustained viral inbound produces approximately 3.78M queued items. Redis memory impact: at 50–80 bytes per sorted set entry (notification ID as member, outbox row ID as score, payload stored in PostgreSQL not Redis), 3.78M items consumes approximately 190–300MB — within the Redis memory budget.

**P1 SLA during viral events:**

| Queue depth | Expected P1 tail latency | Alert state |
|-------------|--------------------------|-------------|
| < 10,000 items | < 30 seconds | Normal |
| 10,000–100,000 items | 1–10 minutes | Warning: page on-call |
| 100,000–1,000,000 items | 10–90 minutes | Critical: page on-call + notify Product |
| > 1,000,000 items | > 90 minutes | Incident: evaluate shedding lowest-score P1 items |

Items older than 2 hours in P1 are expired at the worker — checked against creation timestamp in the payload — and logged to the delivery log as `expired_undelivered` rather than delivered. The 2-hour threshold is a product decision; the justification follows.

#### P1 Expiry Threshold — Basis for the 2-Hour Number

The engagement half-life of a social notification is approximately 2–4 hours based on published research on social media engagement decay (Twitter content engagement studies show 50% of engagement occurs within the first hour, 90% within 4 hours). A notification that arrives 90 minutes after the triggering event is late but within the engagement window. One that arrives 3 hours later is at the edge of relevance; one that arrives 6 hours later is likely dismissed and may generate user complaints about staleness.

The 2-hour threshold is a conservative point estimate within the 2–4 hour defensible range. If Product has data indicating a longer engagement window for this app's specific user behavior — for example, users who batch-check the app across a single timezone — the threshold can be extended to 4 hours by changing a single configuration constant. This is not an architectural decision.

**This threshold requires Product sign-off.** If no sign-off is received by end of month 1, the 2-hour default is used and Product accepts it implicitly. See Section 1.5.

#### Redis Memory Budget

Payload is never stored in Redis. Sorted set members are notification IDs; scores are outbox row IDs. Workers fetch payloads from PostgreSQL read replicas by ID. This keeps Redis memory predictable regardless of payload size.

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

A 6GB Redis instance provides adequate headroom. P1/P2 use a shared Redis Cluster (two primaries, two replicas each). P0 uses Redis Sentinel (one primary, two replicas). These are separate instances because P0 uses `appendfsync always` and P1/P2 use `appendfsync everysec`. Mixing them on the same instance would impose `always` write latency on all queues, degrading P1/P2 throughput for no benefit.

### 1.3 SMS Volume and Budget

**Volume:** 100,000–200,000 messages/day. Auth OTPs and security alerts for users with no alternative auth channel. No marketing SMS.

**Launch approach:** Domestic-only at month 3, international expansion gated on real volume data from month 4. This approach produces a defensible budget number for Finance approval.

**Domestic-only cost model (month 3 launch):**

| Parameter | Value |
|-----------|-------|
| Domestic Twilio rate | $0.0079/message |
| Daily volume (domestic users, ~60% of DAU) | 60,000–120,000 messages |
| Daily cost | $474–$948 |
| **Monthly cost** | **$14,220–$28,440** |

Approximately 2× spread — acceptable for budget approval. Spend cap: $35,000/month with a daily alert at $1,200/day.

**Ownership of the spend cap:**
- Finance owns the number ($35,000/month ceiling).
- Product owns the use case scope (auth OTPs + security alerts only; no marketing).
- Engineering holds veto on configurations that would disable or bypass the circuit breaker.

International SMS is a separate budget decision, made in month 4 with actual domestic volume as a calibration point.

### 1.4 Team Allocation and Schedule

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build: queue infrastructure, delivery pipeline, channel integrations. E3+E4 co-build: preference system, reliability tooling, alerting infrastructure. | E3 cross-trains specifically on alert configuration. Testable milestone: E3 can independently create, modify, and validate alert rules by end of month 1. |
| 2 | Integration, end-to-end testing, runbook authorship. Load testing against viral event model (14,000/sec inbound simulation). All four engineers review all runbooks. | |
| 2.5 | Launch: push, email, in-app. SMS deployed-but-disabled (see Section 3.4). Shared on-call rotation begins. | If external commitments require a month-2 launch, Engineering Manager surfaces this conflict in week 1. A 2-week slip is not self-resolving. |
| 3 | SMS launch (domestic only), pending Finance sign-off by end of month 2. Delayed to month 4 if sign-off not received. | |
| 4 | Production iteration: preference UI, digest batching. International SMS scoping with real volume data. | |
| 5 | International SMS launch (if approved). A/B framework for notification copy and timing. | |
| 6 | Hardening, load testing, runbook updates. | |

**Alerting infrastructure backup — structurally independent:**

The backup alerting path uses three independent layers, each on separate infrastructure from the previous:

1. **Primary:** PagerDuty, receiving alerts from the application monitoring stack (Datadog or equivalent).
2. **Secondary:** PagerDuty Dead Man's Snitch (or equivalent: Cronitor, Healthchecks.io). A cron job on a separate VM — not on the application fleet, with no dependency on the application database, Redis, or Twilio — posts a periodic heartbeat to the Snitch endpoint. If the heartbeat stops, Dead Man's Snitch fires through PagerDuty's own infrastructure. This is structurally independent of our Twilio account; a Twilio outage does not affect it.
3. **Tertiary:** Amazon SES on a separate AWS account, sending to all four engineers' personal email addresses. Triggered if PagerDuty itself is unavailable.

**Why not use Twilio for the backup path:** Twilio is the main SMS provider. A Twilio account suspension or regional outage takes both the primary SMS delivery system and any Tw