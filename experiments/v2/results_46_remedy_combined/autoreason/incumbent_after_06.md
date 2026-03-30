# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling 20–210M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system with a **defined 60-second staleness bound** — chosen specifically to allow legal-compliant opt-out propagation within a single cache TTL cycle.

**Changes from the previous version:** Ten specific problems were identified in review. Each is addressed directly:

1. **FIFO throughput ceiling** — analyzed now, not deferred to a scaling trigger. P1 uses per-conversation message group IDs with a calculated throughput ceiling of ~87M concurrent group IDs before SQS FIFO limits bind. The real ceiling is 3,000 messages/second per queue; we address this with horizontal queue sharding, designed before launch.
2. **Message group ID strategy** — specified explicitly: one group ID per conversation thread for P1, one per user account for P0.
3. **Preference staleness** — defined as 60 seconds maximum, with opt-out writes invalidating cache immediately. Legal compliance implications are named.
4. **Digest volume model** — acknowledged as a pre-launch estimate with no empirical basis; replaced with a range and a Week 1 measurement plan.
5. **Worker sizing** — per-worker throughput assumption stated; $1,200/month delta derived from explicit calculation.
6. **OTP rate limiter logic error** — corrected; Redis increment now occurs only on confirmed send.
7. **Unresolved fallback dependency** — Blocking Decision Point 1 is resolved with a named default and a named owner who can override it.
8. **DAU/MAU inconsistency** — acknowledged and resolved with explicit population definitions throughout.
9. **Team allocation** — shown in full, with the E2 overload redistributed to specific named tasks.
10. **Transactional email latency** — SLA defined (password reset < 30 seconds, security alert < 60 seconds), separate sending infrastructure specified, and latency monitoring described.

Every tradeoff is named. Where a decision requires authorization outside the engineering team, the decision is identified with a named owner, a deadline, and an escalation path.

---

## 1. Scale Model

### 1.1 Population Definitions — Used Consistently Throughout

Two population figures appear in this document. They are not interchangeable and are not used interchangeably.

**MAU (10M):** Monthly active users. Used as the denominator for push opt-in, since push tokens are registered at install and persist across sessions. A user who opens the app once per month still has a push token.

**DAU (3.5M):** Daily active users, modeled at 35% of MAU. Used as the denominator for SMS OTP modeling, since OTP triggers require an active login session. Used also for in-app notification delivery estimates. This figure requires instrumentation from Week 1; 35% is a planning assumption, not a measurement.

**Weekly-active-not-daily (WAND) users:** Modeled at 20% of MAU = 2M users. Used only for digest email modeling. This segment does not exist as a measured cohort before launch — it is the segment most likely to be wrong. See Section 1.3 for how we handle this.

**Where each population applies:**

| Model | Population | Why |
|-------|-----------|-----|
| Push opt-in | MAU (10M) | Push token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Notifications sent to opted-in users |
| SMS OTP | DAU (3.5M) | Requires active login session |
| In-app | DAU (3.5M) | Delivered to active sessions |
| Digest email | WAND (2M estimated) | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Not population-derived |

Any model that switches population without explanation is a bug. This table is the reference.

### 1.2 Push Opt-In Rate — Sources, Uncertainty, and Sensitivity

The 55% blended opt-in rate used in the base scenario is derived from:

- **Airship Mobile Engagement Benchmarks (2023):** Median iOS opt-in of 44% across all categories; social and communication apps trend higher at 52–58%.
- **OneSignal Push Notification Benchmark (2023):** Android opt-in approximately 81% for social apps (opt-out default); iOS approximately 49% across categories.
- **AppsFlyer State of App Marketing (2023):** Delayed permission prompts improve iOS opt-in by 10–15 percentage points.

**Honest uncertainty range:** 40–70% is plausible. The architecture is sized for 70%; costs are modeled at 55%.

**Sensitivity table — opt-in rate × notification rate:**

| Opt-in Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 40% (4M users) | 20M push/day | 60M push/day | 120M push/day |
| 55% (5.5M users) | 27.5M push/day | 82.5M push/day | 165M push/day |
| 70% (7M users) | 35M push/day | 105M push/day | 210M push/day |

**Traffic model — base and high scenarios:**

| Channel | Base (55%, 15/day) | High (70%, 30/day) | Notes |
|---------|-------------------|-------------------|-------|
| Push/day | 82.5M | 210M | |
| Email — transactional | ~500K | ~500K | Action-driven; does not scale with opt-in |
| Email — digest | ~526K estimated | ~526K estimated | Pre-launch estimate; see Section 1.3 |
| In-app/day | ~1.75M–3.5M | ~3.5M–7M | DAU-based; stored, not pushed |
| SMS — OTP/security | ~175K | ~175K | DAU-based; see Section 1.4 |
| Peak throughput | ~4,500/sec | ~9,700/sec | |

**Note on in-app volume:** In-app notifications are stored in a database and fetched on session open, not pushed. Volume is DAU × average unread notifications, not MAU × notification rate. The cost impact is read/write load on the notification store, not delivery throughput. This is modeled separately in Section 5.

### 1.3 Email Volume — Transactional and Digest Modeled Separately, With Honest Uncertainty

**Transactional email** is event-driven, time-sensitive, and subject to delivery SLAs (see Section 6.4). It cannot be capped by batching logic.

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable | Activated when SMS rate-limited; see Section 1.4 |
| **Transactional total** | **~230K–500K/day** | |

We model 500K/day and alert if it exceeds 750K/day sustained. 50% above baseline signals either a security incident or an instrumentation error.

**Digest email** is explicitly opt-in and explicitly batched. The 526K/day figure in the traffic table is a pre-launch estimate derived from a model with no empirical foundation. It should be treated as a planning assumption, not a forecast.

**What we know before launch:** Nothing. The WAND segment (2M users) is not measured. The digest opt-in rate (40% assumed) is not measured. These are the two largest unknowns in the entire volume model.

**What we do instead of pretending to know:**

| Scenario | WAND Segment | Digest Opt-in | Daily Digest Volume |
|----------|-------------|---------------|-------------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**Week 1 measurement plan:** Instrument WAND segment size from actual session data in the first week of production traffic. Instrument digest opt-in rate from the first week of preference UI exposure. Update the digest volume model with real numbers before Month 2. Until then, infrastructure is provisioned for the aggressive scenario at SendGrid to avoid re-provisioning during early growth.

**Alert threshold:** If digest volume exceeds 1.5M/day sustained, investigate whether a bug is sending digests to non-opted-in users before attributing it to organic growth.

### 1.4 SMS Cost — DAU-Based Throughout, Tiered Alarms

SMS uses DAU (3.5M) as its population basis throughout. The worst-case breach scenario uses MAU because a credential breach forces re-authentication for all accounts including inactive ones — this exception is noted explicitly where it appears.

**SMS cost model:**

| Scenario | Population Basis | Volume | Daily Cost (~$0.0079/msg) |
|----------|-----------------|--------|--------------------------|
| Baseline (5% of DAU trigger 2FA) | DAU (3.5M) | 175K/day | ~$1,383 |
| Elevated (10% of DAU, campaign period) | DAU (3.5M) | 350K/day | ~$2,765 |
| Credential stuffing (20% of DAU forced re-auth) | DAU (3.5M) | 700K/day | ~$5,530 |
| Major incident (50% of DAU forced re-auth) | DAU (3.5M) | 1.75M/day | ~$13,825 |
| Full breach (all accounts, inactive included) | **MAU (10M)** | 10M/day | ~$79,000 |

**Why the final row uses MAU:** A full credential breach requires resetting all accounts regardless of session activity. This is the one exception to the DAU-based model, and it is labeled as such.

**Alarm tiers — calibrated against ~$1,383/day baseline:**

| Tier | Threshold | Automated Response |
|------|-----------|-------------------|
| Advisory | $2,000/day | Log to dashboard; no page |
| Warning | $4,000/day | Page on-call; investigate source |
| Critical | $6,000/day | Page on-call + security team; rate limiting activates |
| Emergency | $10,000/day | Fallback protocol activates; security incident declared |

### 1.5 Infrastructure Cost — Base and High Scenarios

| Cost Component | Base/month | High/month | Delta |
|----------------|-----------|-----------|-------|
| SQS (all queues, see Section 2.3 for calculation) | ~$1,100 | ~$2,800 | +$1,700 |
| FCM / APNs | $0 | $0 | Free |
| SendGrid — transactional (dedicated IP pool) | ~$300 | ~$300 | — |
| SendGrid — digest/marketing (shared IP pool) | ~$200 | ~$200 | — |
| Twilio (SMS baseline) | ~$1,383 | ~$1,383 | — |
| ECS compute (workers, see Section 2.4 for sizing) | ~$800 | ~$2,000 | +$1,200 |
| ElastiCache (Redis) | ~$300 | ~$600 | +$300 |
| RDS (PostgreSQL) | ~$400 | ~$600 | +$200 |
| **Monthly total** | **~$4,483** | **~$7,883** | **+$3,400** |

**SendGrid line is now split:** Transactional and digest/marketing email use separate sending infrastructure and separate IP pools. This is a deliverability decision, not a cost optimization — see Section 6.4.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems make Redis the wrong choice for the primary queue tier.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. Configuring Redis with `appendfsync always` degrades write throughput to approximately 10K writes/second and requires a replication topology the team would need to operate.

**Problem 2 — Dequeue atomicity.** Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix requires a Lua script; SQS solves this natively with visibility timeouts.

**Tradeoff accepted:** Four queue families means four DLQs and four sets of CloudWatch alarms — more operational surface than a single Redis sorted set. We accept this because SQS durability and correct concurrent dequeue are non-negotiable for P0 traffic.

### 2.2 FIFO Queue Throughput Ceiling — Analyzed Now, Not Deferred

SQS FIFO queues are capped at **3,000 messages/second with batching** (10 messages/batch = 300 API calls/second) per queue. This is a hard AWS limit. It is not a future scaling concern — it is a constraint that exists at launch and must be designed around before launch.

**P0 traffic analysis:**

P0 (OTP, security alerts) is triggered by authentication events. At 35% DAU = 3.5M daily active users, with 5% triggering OTP SMS per day = 175K OTP events/day. Spread across 24 hours, average P0 throughput is approximately 2 messages/second. Even during a concentrated attack generating 700K forced re-auths, peak P0 throughput is approximately 8 messages/second. P0 is nowhere near the 3,000/second FIFO ceiling. A single FIFO queue is sufficient for P0 with substantial headroom.

**P1 traffic analysis — this is where the ceiling matters:**

P1 (DMs, mentions, replies) is the problematic tier. At base scenario (82.5M push/day), P1 is estimated at 20% of push traffic = 16.5M P1 notifications/day = approximately 190 messages/second average. At high scenario (210M push/day), P1 at 20% = 42M/day = approximately 485 messages/second average. Peak factor of 5× (social apps have pronounced evening peaks) gives approximately 950–2,425 messages/second at peak.

**950 messages/second is within the 3,000/second FIFO ceiling at base. 2,425 messages/second approaches the ceiling at high scenario peak.** This is not comfortable headroom. The design must account for this before launch.

**Solution: Horizontal FIFO queue sharding by user ID hash:**

Rather than one P1 FIFO queue, we deploy a sharded pool of FIFO queues. Each queue handles a partition of the user space, determined by `hash(conversation_id) % N_SHARDS`. At launch, N_SHARDS = 4, giving a combined ceiling of 12,000 messages/second — sufficient for the high scenario with 5× headroom. Shards can be added without architectural changes; workers are assigned to shards by configuration.

```
P1 queue pool:
  p1-fifo-shard-0  →  conversation_id hash % 4 == 0
  p1-fifo-shard-1  →  conversation_id hash % 4 == 1
  p1-fifo-shard-2  →  conversation_id hash % 4 == 2
  p1-fifo-shard-3  →  conversation_id hash % 4 == 3
```

**Cost implication:** Four P1 FIFO shards instead of one adds approximately $150/month in SQS API costs at base scenario. This is included in the Section 1.5 cost table.

**Scaling Trigger A (revised):** If sustained peak per-shard throughput exceeds 2,000 messages/second, double the shard count. This is a configuration change, not an architectural change. Time budget: 4 hours.

### 2.3 Priority Queue Structure with Message Group ID Design

Four queue families, each with a main queue and a