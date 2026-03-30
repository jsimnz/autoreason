# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. Working system ships in month 2, iterated through month 5, hardened in month 6.

The core architectural bet: **three priority-partitioned queues with channel fanout per priority tier**. Per-priority worker pools require per-priority queues. We say this clearly rather than claiming a simplicity we don't have.

The most important correctness decision: **the transactional outbox pattern** bridges the atomicity gap between PostgreSQL and Redis. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure, but not all failure modes:

| Mechanism | Prevents | Does Not Prevent |
|-----------|----------|-----------------|
| Outbox pattern | Lost notifications on crash | Duplicate delivery |
| Idempotency via DB constraint + advisory lock | Duplicate delivery | Lost notifications |

Both are fully specified in this document.

**Key design decisions and tradeoffs, stated upfront:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Outbox pattern over dual writes | ~100ms added latency on P1/P2; accepted in exchange for correctness |
| Three priority queues, not one | Real operational overhead — quantified in Section 2.1 |
| PostgreSQL as system of record | Redis durability becomes a performance decision, not a correctness one |
| Synchronous preference check at routing | Couples routing latency to cache health; cache unavailability falls back to DB; fail-closed means queue-for-later, not suppress |
| 4-instance poller fleet | 17× headroom over peak sustained load; full calculation in Section 3.2 |
| In-app written in same transaction | If push relay fails permanently, user has in-app record but no push — behavior specified in Section 2.3, not deferred |
| P0 rows isolated via separate outbox table | Eliminates contention between dedicated P0 poller and general fleet |
| Redis payload TTL is 24 hours | Covers realistic P2 backlog scenarios; worker falls back to PostgreSQL on cache miss |

**What requires sign-off before implementation:**

- **SMS spend caps and daily budget alert thresholds** (Section 3.4). SMS is excluded from the month-2 launch. Push, email, and in-app ship in month 2. SMS ships in month 3 after finance and product define caps. The architecture supports SMS from day one; the channel is toggled off at the dispatcher until caps are in place. SMS without a spend cap is not a risk to acknowledge and defer — it is a risk that prevents channel launch.
- **Escalation path when outbox relay exhausts retries for auth OTPs** (Section 3.6). This must be resolved before month 2 because OTPs are P0 and launch with the system. Silent failure is not acceptable for auth flows; what the escalation path is requires product and security input.
- **Behavior for push-enabled, in-app-disabled users when push relay fails permanently** (Section 2.3). The system's current behavior is specified; product must confirm it is acceptable.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 | Industry avg for engaged users — see caveat |
| **Total notifications/day** | **~50M** | Planning baseline |
| Peak multiplier | 3× sustained, 6× burst | See distribution caveat |
| Peak sustained throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Peak burst throughput | ~3,500/sec | Capacity ceiling design |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

**Distribution caveat.** The 17 notifications/user/day figure comes from engaged-user benchmarks. Applied uniformly to 3M DAU it produces ~51M/day, used as a planning baseline. The realistic distribution is skewed: the top 10–20% of users likely generate 50–60% of notification volume. This means:

1. The 50M/day aggregate is approximately correct — high-volume users compensate for low-volume ones.
2. The 3× sustained peak multiplier underestimates burst load for the high-activity cohort, which may spike 8–10× their personal average.
3. We design for a **6× burst ceiling** at the infrastructure layer even though the fleet average is 3×.

We instrument notification volume per-user-percentile from day one and revisit these assumptions in month 2. The 6× burst ceiling is the hedge against being wrong.

### SMS Cost Reality

Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is likely $0.02–$0.04/message. At 1M SMS/day, realistic daily cost is **$20,000–$40,000** — not the $7,500 a domestic-only estimate implies. This is why SMS is treated as a tightly controlled premium channel with hard spend caps, and why it does not ship until those caps exist.

### Team Allocation

| Engineer | Primary Responsibility | Secondary (Cross-Training) |
|----------|----------------------|---------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (E2 backup) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (E1 backup) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (E4 backup) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (E3 backup) |

**Cross-training and the month-2 gap.** The working system ships in month 2. Cross-training through paired on-call is planned for month 3. This creates a real window where engineers are on-call for a live production system before their designated backups are qualified.

Mitigations:
- Month 1: E1 and E2 co-build queue infrastructure together, not in parallel. E1 does not own it alone. Same for E3 and E4 on the preference system.
- Month 2 launch: All four engineers share on-call rotation. No solo on-call until month 3.
- Runbooks for all critical components are written by the primary engineer and reviewed by the secondary **before** month 2 launch, not after.

**The E3/E4 backup asymmetry is a real risk.** E4 owns reliability tooling, runbooks, and alerting — the components most likely to be needed during a production incident. E3's primary domain is preference management, the furthest from reliability tooling of any backup pairing. Mitigation: E3's month-1 co-build work with E4 is weighted toward delivery pipeline failure handling and alerting infrastructure. E3 will not be expert in E4's domain by month 2, but will have enough context to execute runbooks and escalate correctly. The shared month-2 on-call rotation means E4 is never the sole responder to an incident they authored.

No dedicated QA. All engineers rotate on-call.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting
  - Per-user rate limiting
     │
     ▼
[Notification Router]
  - Preference check (Redis cache → DB fallback → fail-pending, not suppress)
  - Suppression check
  - Priority assignment
  - Channel selection
     │
     ▼
[PostgreSQL — single transaction]
  ├── notifications table (in-app record + system of record)
  ├── notification_outbox_p0 table (P0 rows only — isolated from general fleet)
  ├── notification_outbox table (P1 and P2 rows)
  └── notification_payloads table (payload store)
     │
     ▼
[Outbox Poller Fleet]
  ├── 1 dedicated P0 poller (polls notification_outbox_p0 exclusively)
  └── 4 general instances (poll notification_outbox for P1/P2 rows)
  - FOR UPDATE SKIP LOCKED, batch 500
  - Writes payload to Redis with 24-hour TTL
  - Enqueues notif_id to priority sorted set
  - Marks outbox row relayed
  - On Redis failure: does NOT mark relayed; retries next cycle
     │
     ▼
[Priority Queues — 3 Redis Sorted Sets, AOF-persisted, Sentinel HA]
  notification_queue:p0  (auth OTPs, security alerts)
  notification_queue:p1  (direct messages, mentions)
  notification_queue:p2  (likes, follows, digests)
     │
     ├── P0 Worker Pool (10 workers — drain p0 only)
     ├── P1 Worker Pool (20 workers — drain p1 only)
     └── P2 Worker Pool (10 workers — drain p2, assist p1 above threshold)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     ├── SMS (Twilio — spend-capped, disabled until month 3)
     └── In-app (already written; dispatcher marks delivered)
          │
          ▼
   [Delivery Log]              [Dead-Letter Queue per priority]
   (PostgreSQL + S3)           (Redis sorted set + runbook)
          │
          ▼
   [Feedback Processor]
   (bounces, delivery receipts, token invalidations)
```

### 2.1 Queue Design: Three Queues, Operational Cost Quantified

We use three separate Redis sorted sets with separate worker pools. The operational overhead is real and quantified here so the team makes an informed decision about whether it is worth carrying.

**Full operational surface of three queues:**

| Component | Count | Maintenance burden |
|-----------|-------|-------------------|
| Redis sorted sets | 3 | Schema is trivial; no ongoing cost |
| Dead-letter queues | 3 | Each requires its own backlog alert, runbook, and drain procedure |
| Backlog metric dashboards | 3 | Independent depth, age, and throughput panels per queue |
| Retry policies | 3 | P0 retries aggressively; P1/P2 use exponential backoff — must be tuned independently |
| Capacity scaling decisions | 3 | Worker pool sizes set independently; resizing one does not automatically rebalance others |
| Starvation mitigation logic | 1 | P2 workers assist P1 above threshold — fully specified below |

**Estimated ongoing maintenance load:** Approximately 4–6 engineer-hours/month for alert tuning, DLQ drain reviews, and retry policy adjustments across all three queues. With 4 engineers, this is roughly 1–1.5 hours/engineer/month — a real cost, not a negligible one, but manageable.

**Why we accept this cost.** Per-priority worker pools require per-priority queues. The alternative — a single queue with priority scores and a shared worker pool — requires workers to implement priority-aware polling logic that is more complex to reason about under backlog conditions. The operational overhead is higher with three queues; the failure mode complexity is lower. Given the team's size, we prefer simpler failure modes over simpler operations. We revisit per-channel queues at 50M MAU.

**P0 isolation via separate table.** P0 rows are written to `notification_outbox_p0`, a separate table polled exclusively by the dedicated P0 poller. General fleet instances poll `notification_outbox` only, which contains P1 and P2 rows. This eliminates the contention problem where general pollers grab P0 rows before the dedicated P0 poller sees them. The P0 poller never competes with general pollers on the same table. This adds one table and one poller process to the operational surface; it removes a class of correctness ambiguity that would otherwise require careful index design and monitoring to detect.

**P2-to-P1 starvation mitigation — fully specified.**

P2 workers assist P1 when P1 is backlogged. The mechanism answers four questions: what triggers migration, how many workers migrate, how they coordinate, and what triggers return.

*Trigger:* Each P2 worker checks P1 queue depth at the start of each poll cycle via a single `ZCARD notification_queue:p1` call (~0.5ms). If depth exceeds `P1_ASSIST_THRESHOLD` (default: 10,000 items, configurable via environment variable), the worker enters assist mode.

*How many workers migrate:* P2 workers independently check the threshold and independently enter assist mode. We do not coordinate migration centrally. The consequence is that all 10 P2 workers may simultaneously enter assist mode, leaving P2 unserved. This is the correct behavior: if P1 has 10,000+ items backlogged, P2 should be fully deprioritized. P2 contains likes, follows, and digests — a multi-minute delay is acceptable. If the threshold is set too low and P2 starvation becomes user-visible, raise the threshold.

*Return trigger:* A worker in assist mode returns to P2 after completing one P1 batch if P1 depth has fallen below `P1_ASSIST_THRESHOLD / 2` (5,000 items by default). The hysteresis prevents oscillation when depth hovers near the threshold.

*What P2 workers do in assist mode:* They pull from `notification_queue:p1` using the same `ZRANGEBYSCORE` + `ZREM` pattern as P1 workers. There is no special coordination. P2 workers in assist mode are functionally identical to P1 workers for the duration of the assist.

*Monitoring:* A metric `worker_assist_mode{pool="p2", target="p1"}` is emitted each cycle a P2 worker is in assist mode. An alert fires if more than 5 P2 workers are in assist mode for more than 10 minutes continuously — this indicates a P1 backlog the worker pool cannot drain and requires human attention.

### 2.2 What the Outbox Pattern Does and Does Not Guarantee

The outbox pattern guarantees: a notification written to PostgreSQL will eventually be enqueued for delivery. It prevents the failure mode where the application crashes after writing to PostgreSQL but before writing to Redis — without the outbox, that notification is lost permanently. With the outbox, the poller recovers it on the next cycle.

The outbox pattern does **not** guarantee: a notification is enqueued exactly once. If the poller writes to Redis successfully but fails to commit the `UPDATE SET relayed_at = NOW()` transaction, the same outbox row is processed again on the next cycle, producing a duplicate enqueue.

Duplicates are handled at the worker layer via idempotency keys. The mechanism — including the race condition that a naive constraint-only approach does not handle — is specified completely in Section 3.3. The two mechanisms are complementary, not redundant.

### 2.3 In-App Notification Failure Mode — Behavior Specified, Product Confirmation Required

In-app notifications are written in the same PostgreSQL transaction as the outbox entry. This is the correct default: in-app is the most reliable channel (no external dependency), so if outbox relay fails permanently, the user has an in-app record rather than being completely dark.

**The failure mode that requires product sign-off:** A user with push notifications enabled and in-app notifications disabled has an in-app record in the database that is permanently invisible to them by their own preference. Their push notification failed. They receive nothing visible.

**What the system does in this state, specifically:**

1. The outbox row is dead-lettered with reason `relay_exhausted`.
2. The dead-letter record includes user_id, notification type, and channel.
3. For P0 notifications (OTPs, security alerts), the dead-letter event triggers an operator alert and escalation to a secondary channel if configured — specified in Section 3.6.
4. For P1/P2 notifications, no automatic escalation occurs