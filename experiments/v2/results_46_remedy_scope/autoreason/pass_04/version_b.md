# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions and what changed from the prior version:

1. **Deduplication uses atomic SET NX**, not a check-before-set pattern. The prior version described the race condition correctly but failed to solve it.
2. **Redis memory is explicitly sized**: full payload storage requires 8–42GB for queue contents at peak, which determines ElastiCache tier selection. This is now calculated, not assumed.
3. **Expiry sorted sets have a background pruning process**: without it, the sorted sets grow without bound under worker outage — the exact problem TTL enforcement was meant to prevent.
4. **APNs capacity planning is range-based until month 2 validation**: the prior version acknowledged the 1,000 req/sec figure was unvalidated, then used it as if it were reliable. Worker counts now reflect a conservative floor with an explicit re-planning gate.
5. **Worker decomposition is shown explicitly**: the per-channel and per-priority views are reconciled in a single table so any change propagates visibly.
6. **OTP spike costs have a circuit breaker**: "separately budgeted" is not a control mechanism. A Twilio spending alert and automatic fallback to email OTP are now specified.
7. **WebSocket sequence numbers are designed**, not deferred. The prior version assigned this to E3 in month 3 with no design basis.
8. **Feedback Processor is specified**: token invalidity handling, bounce processing, and delivery receipt ingestion are designed, not just named in a diagram.
9. **The month 2 contingency has a backup**: if both push and SMS are delayed, the contingency path is identified and handled.
10. **The 50M/day estimate is flagged with its uncertainty range**: the DAU × engagement-rate conflation is acknowledged, and the capacity plan is stress-tested against a lower bound.

Every tradeoff is named, including the uncomfortable ones.

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

**Caveat on the 50M/day figure:** DAU counts only users active on a given day, who are more engaged than the average user implied by a population-wide rate. Applying a high-engagement rate to an already-filtered active-user count likely overstates volume. The true figure is probably 30–60M/day. The capacity plan uses 50M as the planning number but is stress-tested at 30M/day in Section 1.4 — if the system is over-provisioned at 30M, we note where to trim; if it fails at 30M, the design is wrong. This uncertainty does not change the infrastructure tier selection because the dominant cost driver is Redis memory, which is sized independently.

### Active-User Correction

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This affects two channels differently:

- **In-app:** Delivered only to logged-in users. Peak demand = 10M/day × 3× / 86,400 × (600K / 3M) = **~350/sec**
- **Push:** For offline or background users. At peak, ~2.4M of 3M DAU are offline. Peak demand = 35M/day × 3× / 86,400 × (2.4M / 3M) = **~972/sec**

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand and leads to over-provisioning.

### Redis Memory Sizing — Required Before Infrastructure Selection

The prior version argued for full payload storage without calculating the memory consequence. That calculation must happen before any ElastiCache sizing decision.

**Payload size distribution:**

| Notification type | Estimated payload size | % of volume |
|---|---|---|
| Push (title + body + metadata) | 500B–2KB | 70% |
| In-app (full content + action URLs) | 1–3KB | 20% |
| Email (template ID + parameters, not body) | 200–500B | 8% |
| SMS (message text + recipient) | 100–300B | 2% |

**Weighted average payload size:** ~1KB. Conservative estimate for sizing: **2KB** (accounts for JSON overhead, metadata, and the high end of push payloads with media URLs).

**Queue memory at peak accumulation:**

During a 2-hour spike, 8.4M excess notifications accumulate (see Section 1.4). At 2KB each:

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

**ElastiCache selection:** r7g.4xlarge (128GB RAM, Multi-AZ) provides 3× headroom over the worst case. This is a single-node logical view with Multi-AZ replication — not a cluster, which would add operational complexity. If worst-case payload sizes materialize, we scale to r7g.8xlarge without architectural changes.

**The alternative — store only IDs in queues:** Reduces queue memory to ~100B/entry (8.4M × 100B = ~840MB). The cost is a crash window: if a worker dequeues an ID and the payload fetch fails (database unavailable, network partition), the notification is lost with no recovery path. At 50M/day, even a 0.01% loss rate is 5,000 lost notifications/day, including potentially OTP messages. Full payload storage is the correct choice; the memory cost is the honest price of that correctness. We pay it with appropriate hardware.

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

The prior version stated 1,000 req/sec/worker, acknowledged this was unvalidated, and then used it throughout. That is not acceptable. Apple does not publish per-bundle-ID rate limits. Production reports in the community range from 300 to 2,000 req/sec depending on account age, app category, and Apple's opaque throttling policy.

**Planning approach:**
- **Month 1–2:** Size for the **conservative floor of 300 req/sec/worker**. This may mean more APNs workers than necessary, but over-provisioning is recoverable; under-provisioning OTP delivery is not.
- **Month 2 milestone:** E2 runs APNs load tests against the production bundle ID. Actual throughput is measured.
- **Month 2 re-planning gate:** If measured throughput is ≥ 600 req/sec, reduce APNs workers. If < 300 req/sec, escalate — this is an architecture problem, not a tuning problem.

**Worker counts using conservative APNs floor:**

| Channel | Peak demand | P0 | P1 | P2 | P3 | Total | Peak capacity | Headroom |
|---------|-------------|----|----|----|----|-------|---------------|----------|
| FCM push | ~972/sec | 2 | 3 | 2 | 0 | 7 | ~14,000/sec | 14× |
| APNs push | ~243/sec | 2 | 3 | 2 | 0 | 7 | ~2,100/sec (at 300/sec floor) | 8× |
| Email | ~138/sec | 0 | 1 | 1 | 2 | 4 | ~4,000/sec | 29× |
| SMS | ~4/sec (capped) | 2 | 1 | 0 | 0 | 3 | ~200/sec | 50× |
| In-app | ~350/sec | 0 | 2 | 2 | 2 | 6 | ~6,000/sec | 17× |
| **Total** | | **6** | **10** | **7** | **4** | **27** | | |

**Worker decomposition reconciliation** — both views must produce the same totals:

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 0 | 2 | 0 | **6** |
| **P1** | 3 | 3 | 1 | 1 | 2 | **10** |
| **P2** | 2 | 2 | 1 | 0 | 2 | **7** |
| **P3** | 0 | 0 | 2 | 0 | 2 | **4** |
| **Col total** | **7** | **7** | **4** | **3** | **6** | **27** |

Any change to a single cell must update both the row total and the column total. This table is the single source of truth — the architecture diagram and capacity narrative derive from it, not vice versa.

**APNs worker count after month 2 validation:**
- If measured throughput = 1,000 req/sec: reduce APNs workers from 7 to 5 (same as prior version)
- If measured throughput = 600 req/sec: reduce to 6
- If measured throughput = 300 req/sec: keep 7, investigate Apple account standing

### Queue Drain Analysis

At 50M/day baseline (578/sec average) and 3× peak (1,750/sec), excess accumulates at ~1,172/sec. Over a 2-hour spike: ~8.4M excess notifications.

Combined worker capacity across all channels: ~26,300/sec (using conservative APNs floor). Net drain rate post-peak: ~25,700/sec. The 8.4M excess clears in approximately **5.5 minutes** after peak ends.

**At 30M/day lower bound:** Peak is ~1,050/sec. Excess accumulates at ~472/sec. 2-hour excess: ~3.4M items. Clears in ~2.2 minutes post-peak. Infrastructure remains appropriately sized — no changes needed at the lower bound.

Queue depth alerts: 500K items for P1–P3; **1,000 items for P0** (P0 accumulation is an incident, not a capacity event).

### The SMS Budget Problem — Two Independent Budgets With Controls

A single SMS cap conflates security-critical messages with discretionary social messages. They require separate treatment — and separate controls, not just separate accounting.

**OTP volume model:**

| SMS category | Volume estimate | Annual cost at $0.012/msg |
|---|---|---|
| OTP / 2FA (baseline) | ~150K/day | ~$660K/year |
| OTP spike reserve (3 days/year at 10×) | ~4.5M total | ~$54K/year |
| Security alerts | ~20K/day | ~$88K/year |
| Social/digest (hard cap) | ≤100K/day | ≤$438K/year |
| **Total** | **~270K–370K/day baseline** | **~$1.2M–1.4M/year** |

**OTP spike cost control — circuit breaker required:**

"Separately budgeted" is not a control mechanism. During a security incident spike to 1.5M OTP SMS/day, Twilio costs reach ~$18,000/day. The architecture must prevent this from being a surprise.

**Controls:**
1. **Twilio spending alert at $500/day** (roughly 2× normal daily SMS spend). Alert fires to on-call and engineering lead within 5 minutes.
2. **Automatic email OTP fallback at 500K SMS/day** (roughly 3× baseline). When the daily SMS counter exceeds 500K, the OTP router switches to email delivery for users who have a verified email address. SMS continues only for users without a verified email.
3. **Manual override required to exceed 1M SMS/day**. The system will not automatically exceed this threshold. An on-call engineer must acknowledge the spend and explicitly enable the higher tier. This is a deliberate speed bump, not an automatic circuit breaker, because a genuine security incident may require it — but it should not happen without human awareness.
4. **Incident post-mortem trigger:** Any day exceeding 300K OTP SMS generates a required post-mortem item examining whether the authentication policy change that caused it was intentional.

**Permitted SMS:** OTP/2FA (always, subject to controls above), password reset fallback (if no email open within 10 minutes), security alerts (new device login, suspicious activity). Social notifications: never, without explicit budget approval and rate-limit re-architecture.

### Team Allocation

| Engineer | Primary Responsibility | Months 1–2 | Months 3–4 | Months 5–6 |
|----------|----------------------|------------|------------|------------|
| E1 | Core pipeline, queues, workers | Queue, router, atomic deduplication, TTL enforcement + background pruning | Aggregation, batching | Load testing, capacity tuning |
| E2 | Channel integrations | FCM (weeks 1–6), APNs (weeks 5–8, overlapping) + month 2 APNs load test | Email + SMS + circuit breaker | Deliverability, token hygiene, feedback processor |
| E3 | Preferences, in-app, WebSocket | Schema, preference API, in-app store | WebSocket fanout with sequence numbers (designed in Section 5) | User-facing polish, reconnect testing |
| E4 | Infrastructure, monitoring | Managed service setup, CI/CD, alerting | Failure handling, DLQ, feedback processor data model | Chaos testing, runbooks |

**Month 2 contingency — with backup:**

Primary contingency: If FCM and APNs are not both ready by month 2, launch proceeds with **email-only for non-critical notifications and SMS for OTP**.

**Backup contingency:** If SMS integration is also delayed, OTP delivery falls back to **email with a forced re-authentication flow** — users are required to click a link in their email to complete authentication, rather than entering a code. This is a degraded but functional experience. It requires E2 to implement the email-based re-auth flow in parallel with SMS integration, not as an afterthought. E2 begins this implementation in week 3 regardless of SMS integration status.

This means the month 2 launch has a guaranteed OTP path: SMS (preferred) → email link (fallback). There is no scenario in