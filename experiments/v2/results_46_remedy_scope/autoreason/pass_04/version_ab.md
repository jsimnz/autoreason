# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions:

1. **Four isolated priority queues (P0–P3)** with TTL semantics enforced via companion expiry sorted sets and a background pruning process — Redis Lists have no per-element TTL, and without active pruning, expiry sets grow without bound under worker outage
2. **Full payload storage in queue entries** — storing only IDs creates a crash window between dequeue and payload fetch that causes silent, unrecoverable message loss; Redis memory is explicitly sized to justify this choice
3. **Deduplication uses atomic SET NX**, not check-before-set — the race condition is solved, not just described
4. **Worker pools are per-channel and per-priority**, reconciled in a single source-of-truth matrix; any change propagates visibly across both views
5. **APNs capacity planning is range-based until month 2 validation** — using an unvalidated throughput figure as if reliable is not acceptable; workers are sized to a conservative floor with an explicit re-planning gate
6. **SMS volume split into two independent budgets with enforced controls** — "separately budgeted" is not a control mechanism; a circuit breaker with automatic email OTP fallback is specified
7. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL primary
8. **P0 has minimum 2 workers per channel** — no single point of failure on the security-critical path
9. **WebSocket sequence numbers are designed, not deferred** — reconnect catch-up logic is specified in Section 5
10. **The 50M/day estimate is flagged with its uncertainty range** — the capacity plan is stress-tested at a 30M/day lower bound

Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### Traffic Model

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/user/day | ~17 | Industry average; see caveat below |
| **Total notifications/day** | **~50M** | DAU × rate; see uncertainty range |
| Peak multiplier | 3× | Morning/evening spikes, ~2hr duration |
| **Sustained peak throughput** | **~1,750/sec** | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Capacity ceiling, not operating target |

**Caveat on the 50M/day figure:** DAU counts only users active on a given day, who are more engaged than the average user implied by a population-wide rate. Applying a high-engagement rate to an already-filtered active-user count likely overstates volume. The true figure is probably 30–60M/day. The capacity plan uses 50M as the planning number but is stress-tested at 30M/day in the drain analysis below. This uncertainty does not change the infrastructure tier selection because the dominant cost driver is Redis memory, which is sized independently.

### Active-User Correction — Applied Consistently

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This affects two channels differently:

- **In-app:** Delivered only to logged-in users. Peak demand = 10M/day × 3× / 86,400 × (600K / 3M) = **~350/sec**
- **Push:** For offline or background users. At peak, ~2.4M of 3M DAU are offline. Peak demand = 35M/day × 3× / 86,400 × (2.4M / 3M) = **~972/sec**, not the naïve 1,215/sec you get by ignoring channel complementarity

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates both demand figures and leads to over-provisioning. This same correction applies to queue drain analysis and capacity planning throughout.

### Redis Memory Sizing — Required Before Infrastructure Selection

The case for full payload storage requires calculating the memory consequence before any ElastiCache sizing decision.

**Payload size distribution:**

| Notification type | Estimated payload size | % of volume |
|---|---|---|
| Push (title + body + metadata) | 500B–2KB | 70% |
| In-app (full content + action URLs) | 1–3KB | 20% |
| Email (template ID + parameters, not body) | 200–500B | 8% |
| SMS (message text + recipient) | 100–300B | 2% |

Weighted average: ~1KB. Conservative sizing estimate: **2KB** (accounts for JSON overhead, metadata, and the high end of push payloads with media URLs).

**Queue memory at peak accumulation:**

During a 2-hour spike, 8.4M excess notifications accumulate (see drain analysis). At 2KB each:

| Scenario | Queue entries | Memory |
|---|---|---|
| Conservative (2KB/entry) | 8.4M | **16.8GB** |
| Worst case (5KB/entry) | 8.4M | **42GB** |
| Best case (500B/entry) | 8.4M | **4.2GB** |

**Additional Redis memory requirements:**

| Component | Estimate |
|---|---|
| Expiry sorted sets (40B/entry × 8.4M) | ~340MB |
| Deduplication keys (50B/key × 50M/day, 5-min TTL) | ~1.5GB active at any time |
| Preference cache (500B/user × 3M active users) | ~1.5GB |
| Aggregation state (200B/entry × 500K active windows) | ~100MB |
| Pub/Sub overhead | ~500MB |
| **Total Redis memory requirement** | **~20–46GB** |

**ElastiCache selection:** r7g.4xlarge (128GB RAM, Multi-AZ) provides 3× headroom over worst case. This is a single-node logical view with Multi-AZ replication — not a cluster, which adds operational complexity a 4-person team should not absorb. If worst-case payload sizes materialize, we scale to r7g.8xlarge without architectural changes.

**Why not store only IDs in queues:** Reduces queue memory to ~840MB (8.4M × 100B). The cost is a crash window: if a worker dequeues an ID and the payload fetch fails (database unavailable, network partition), the notification is lost with no recovery path. At 50M/day, even a 0.01% loss rate is 5,000 lost notifications/day, including potentially OTP messages. Full payload storage is correct; the memory cost is the honest price of that correctness. We pay it with appropriate hardware.

### Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2 multiplexed streams | **300–1,000 req/sec/worker** (unvalidated range; see below) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — range-based planning with a re-planning gate:**

Apple does not publish per-bundle-ID rate limits. Production reports range from 300 to 2,000 req/sec depending on account age, app category, and Apple's opaque throttling policy. Using a single unvalidated figure as if reliable is not acceptable for a P0 delivery path.

- **Month 1–2:** Size for the conservative floor of **300 req/sec/worker**. Over-provisioning is recoverable; under-provisioning OTP delivery is not.
- **Month 2 milestone:** E2 runs APNs load tests against the production bundle ID and measures actual throughput.
- **Month 2 re-planning gate:** If measured throughput ≥ 600 req/sec, reduce APNs workers. If < 300 req/sec, escalate — this is an architecture problem, not a tuning problem.

**Worker matrix — single source of truth:**

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 0 | 2 | 0 | **6** |
| **P1** | 3 | 3 | 1 | 1 | 2 | **10** |
| **P2** | 2 | 2 | 1 | 0 | 2 | **7** |
| **P3** | 0 | 0 | 2 | 0 | 2 | **4** |
| **Col total** | **7** | **7** | **4** | **3** | **6** | **27** |

Any change to a single cell must update both the row total and the column total. The architecture diagram and capacity narrative derive from this table, not vice versa.

**Demand vs. capacity summary:**

| Channel | Peak demand | Total workers | Peak capacity | Headroom |
|---------|-------------|---------------|---------------|----------|
| FCM push | ~972/sec | 7 | ~14,000/sec | 14× |
| APNs push | ~243/sec | 7 | ~2,100/sec (at 300/sec floor) | 8× |
| Email | ~138/sec | 4 | ~4,000/sec | 29× |
| SMS | ~4/sec (capped) | 3 | ~200/sec | 50× |
| In-app | ~350/sec | 6 | ~6,000/sec | 17× |

**P0 minimum redundancy:** P0 has 2 workers per channel. A single worker crash eliminates P0 processing for that channel until ECS restarts it — typically 30–60 seconds. The second worker handles load during the restart window. Email is absent from P0 by design: OTPs must not route through a channel with 5–30 minute delivery latency.

**APNs worker count after month 2 validation:**
- Measured throughput ≥ 1,000 req/sec: reduce APNs workers from 7 to 5
- Measured throughput ≥ 600 req/sec: reduce to 6
- Measured throughput = 300 req/sec: keep 7, investigate Apple account standing

### Queue Drain Analysis

At baseline 578/sec input and 3× peak of ~1,750/sec, excess accumulates at ~1,172/sec. Over a 2-hour spike: ~8.4M excess notifications.

Combined worker capacity across all channels: ~26,300/sec (using conservative APNs floor). Net drain rate post-peak: ~25,700/sec. The 8.4M excess clears in approximately **5.5 minutes** after peak ends.

**At 30M/day lower bound:** Peak is ~1,050/sec. Excess accumulates at ~472/sec. 2-hour excess: ~3.4M items. Clears in ~2.2 minutes post-peak. Infrastructure remains appropriately sized — no changes needed at the lower bound. The system is not embarrassingly over-provisioned at lower volume, which validates the tier selection.

Queue depth alerts: 500K items for P1–P3; **1,000 items for P0** (P0 accumulation is an incident, not a capacity event).

### The SMS Budget Problem — Two Independent Budgets With Enforced Controls

A single SMS cap conflates security-critical messages with discretionary social messages. They require separate treatment — and separate controls, not just separate accounting.

**Budget allocation:**

| SMS category | Volume estimate | Annual cost at $0.012/msg |
|---|---|---|
| OTP / 2FA (baseline) | ~150K/day | ~$660K/year |
| OTP spike reserve (3 days/year at 10×) | ~4.5M total | ~$54K/year |
| Security alerts | ~20K/day | ~$88K/year |
| Social/digest (hard cap) | ≤100K/day | ≤$438K/year |
| **Total** | **~270K–370K/day baseline** | **~$1.2M–1.4M/year** |

**OTP spike cost control — circuit breaker required:**

"Separately budgeted" is not a control mechanism. During a security incident spike to 1.5M OTP SMS/day, Twilio costs reach ~$18,000/day. The architecture must prevent this from being a surprise.

1. **Twilio spending alert at $500/day** (~2× normal daily SMS spend). Alert fires to on-call and engineering lead within 5 minutes.
2. **Automatic email OTP fallback at 500K SMS/day** (~3× baseline). When the daily SMS counter exceeds 500K, the OTP router switches to email delivery for users who have a verified email address. SMS continues only for users without a verified email.
3. **Manual override required to exceed 1M SMS/day.** The system will not automatically exceed this threshold. An on-call engineer must acknowledge the spend and explicitly enable the higher tier. This is a deliberate speed bump, not an automatic circuit breaker, because a genuine security incident may require it — but it should not happen without human awareness.
4. **Incident post-mortem trigger:** Any day exceeding 300K OTP SMS generates a required post-mortem item examining whether the authentication policy change that caused the spike was intentional.

**Permitted SMS:** OTP/2FA (always, subject to controls above), password reset fallback (if no email open within 10 minutes), security alerts (new device login, suspicious activity). Social notifications: never, without explicit budget approval and rate-limit re-architecture.

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, atomic deduplication, TTL enforcement + background pruning | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | FCM (weeks 1–6), APNs (weeks 5–8) + month 2 APNs load test, email OTP fallback (week 3 start) | Email + SMS + circuit breaker | Deliverability, token hygiene, feedback processor |
| E3 | Preferences, in-app, WebSocket | Schema, preference API, in-app store | WebSocket fanout with sequence numbers (Section 5) | User-facing polish, reconnect testing |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ, feedback processor data model | Chaos testing, runbooks |

**Month 2 contingency — with backup:**

Primary contingency: If FCM and APNs are not both ready by month 2, launch proceeds with email-only for non-critical notifications and SMS for OTP.

**Backup contingency:** If SMS integration is also delayed, OTP delivery falls back to email with a forced re-authentication flow — users click a link in their email to complete authentication rather than entering a code. This is a degraded but functional experience. E2 begins this implementation in week 3 regardless of SMS integration status. The month 2 launch therefore has a guaranteed OTP path: SMS (preferred) → email link (fallback). There is no scenario in which OTP delivery is unavailable at launch.

**E4 scope is bounded by managed services:** ElastiCache Multi-AZ (not self-managed Redis), RDS Multi-AZ (not self-managed PostgreSQL), Datadog (not self-built monitoring), ECS with Fargate (not custom deployment scripts). Chaos testing is deferred to month 5 — E4 does not attempt it while building the system.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources (app servers, internal services)
        │
        ▼
[Event Ingestion API]   ← stateless, horizontally scaled, rate-