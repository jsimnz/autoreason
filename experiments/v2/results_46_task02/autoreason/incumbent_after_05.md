# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**The core architectural bet:** three priority-partitioned queues with channel fanout per priority tier, backed by a transactional outbox pattern. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure. What it prevents and what it does not:

| Mechanism | Prevents | Does Not Prevent |
|-----------|----------|-----------------|
| Outbox pattern | Lost notifications on crash | Duplicate delivery |
| Idempotency via DB constraint + advisory lock | Duplicate delivery | Lost notifications |

Both mechanisms are fully specified below. They are complementary, not redundant.

**Key design decisions and tradeoffs, stated upfront:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Outbox with read-before-mark on Redis | Poller re-reads Redis before marking relayed; adds ~1ms per batch; eliminates crash-window correctness contradiction |
| P0 workloads on dedicated PostgreSQL instance | Additional cost (~$300–600/month); required because table separation alone does not prevent autovacuum interference from P1/P2 write storms |
| Three priority queues with separate worker pools | ~5 engineer-hours/month operational overhead; simpler failure modes than a shared pool with priority-aware polling |
| P0 poller runs two active instances behind a leader lock | Eliminates single point of failure for auth OTPs; adds coordination complexity, fully specified in Section 3.5 |
| Redis AOF `appendfsync always` for P0 queue only | ~3× write latency vs. `everysec`; accepted because P0 SLA requires it; P1/P2 use `everysec` and tolerate up to 1-second loss, recovered by outbox |
| Synchronous preference check at routing | Couples routing latency to cache health; cache unavailability falls back to DB; fail-closed means queue-for-later, not suppress |
| In-app written in same transaction as outbox entry | If push relay fails permanently, user has in-app record but no push — behavior specified in Section 2.3, not deferred |
| SMS excluded from month-2 launch | Spend caps must exist before channel goes live; architecture supports SMS from day one, toggled off at dispatcher |
| Co-build in month 1 extends launch to month 2.5 | Explicitly acknowledged; unrealistic to maintain month-2 deadline while co-building |

**What requires sign-off before implementation, with owners and consequences if not resolved:**

| Decision | Owner | Deadline | Consequence if missed |
|----------|-------|----------|-----------------------|
| SMS spend caps and daily budget alert thresholds | Finance + Product | End of month 2 | SMS does not launch in month 3; pushed to month 4 |
| OTP escalation path when outbox relay exhausts retries | Product + Security | End of month 1 | Month-2.5 launch delayed; P0 cannot ship without specified failure behavior |
| Behavior for push-enabled/in-app-disabled users when push fails permanently | Product | End of month 1 | Month-2.5 launch delayed; silent DLQ is not acceptable for P0 |

The OTP escalation path is a hard launch blocker. E4 owns driving this decision to closure. If there is no documented decision by week 3 of month 1, the project lead escalates. "We'll figure it out" is not an acceptable state when OTPs are P0 and ship with the initial system.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 average; ~28 for top-20% cohort | See distribution note |
| **Total notifications/day** | **~50M** | Planning baseline |
| Peak multiplier | 3× sustained, 6× burst | See distribution note |
| Peak sustained throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Peak burst throughput | ~3,500/sec | Capacity ceiling design |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2% nominal) | 100K–200K/day actual | See SMS reconciliation below |

**Distribution note — following the logic fully.** The 17 notifications/user/day figure comes from engaged-user benchmarks. Applied uniformly to 3M DAU it produces ~51M/day, used as a planning baseline. The realistic distribution is skewed: the top 20% of users (600K of DAU) are by definition the daily active cohort's most engaged segment, averaging approximately 28 notifications/day. The bottom 80% (2.4M users) average approximately 10/day. The aggregate still produces ~50M/day, so the planning baseline holds.

The burst implication is different. The 6× fleet-average ceiling was described as a hedge against being wrong about the fleet average. It is also insufficient for the high-activity cohort's true burst behavior: if the top 20% spike 8–10× their personal average (28/day baseline), their burst rate is ~224–280 notifications/user/day during the spike window. For 600K users, a localized viral event produces roughly 10,000–14,000 notifications/second.

We cannot sustain 14,000/sec with this infrastructure. We can absorb it via queue depth. P1 and P2 queues have no hard depth limit; backlog accumulates and drains over minutes to hours. The P0 queue is protected separately (Section 3.5). The correct response to a viral event is to accept latency on P1/P2 delivery and communicate that SLAs are best-effort for non-P0 traffic. We instrument queue depth and age from day one and alert when P1 age exceeds 5 minutes.

**SMS volume — resolving the internal inconsistency.** The 2% channel split (1M SMS/day) and the "auth + high-priority only" use case cannot both be true. Auth OTPs and security alerts for 3M DAU, assuming 5% of users trigger an auth event on a given day, is 150,000 SMS/day — not 1M. The 2% figure is an industry average that includes marketing SMS, which this design explicitly does not use.

**Revised SMS estimate: 100,000–200,000 messages/day.** Twilio domestic US rates are ~$0.0079/message, but international SMS runs $0.05–$0.15/message. For a 10M MAU app with meaningful international distribution, blended cost is $0.02–$0.04/message. At revised volume, daily cost is **$2,000–$8,000/day** ($60K–$240K/month) — a real budget line requiring finance approval, but not the $7–14M/month figure that would make SMS non-viable. The spend cap mechanism (Section 3.4) is still required because international rate variance is enough to cause unexpected cost spikes from a misconfigured event trigger.

All volume estimates are instrumented from day one. We revisit SMS estimates in month 2 with real data.

### Team Allocation and Schedule

**The month-2 launch deadline is incompatible with co-building.** Co-building means two engineers work on one subsystem together rather than two subsystems in parallel, extending total build time. Co-building is the right call for a 4-person team operating a production system without dedicated QA. The schedule reflects this honestly.

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build queue infrastructure and delivery pipeline. E3+E4 co-build preference system and reliability tooling. | No subsystem parallelization. Month-2 deadline moves to month 2.5. |
| 2 | Integration, end-to-end testing, runbook authorship and review. | All four engineers review all runbooks before launch. |
| 2.5 | Launch: push, email, in-app. SMS architecture in place but disabled. | Shared on-call rotation begins. |
| 3 | SMS launch (pending spend cap sign-off by end of month 2). Monitoring refinement. | SMS delayed to month 4 if sign-off not received. |
| 4–5 | Iteration based on production data. Preference UI, digest batching, A/B framework. | |
| 6 | Hardening, load testing, runbook updates. | |

| Engineer | Primary Responsibility | Secondary (Cross-Training via Co-Build) |
|----------|----------------------|----------------------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (co-built with E2) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (co-built with E1) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (co-built with E4) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (co-built with E3) |

**The E3/E4 backup asymmetry is a real risk.** E4 owns reliability tooling and alerting — the components most likely to be needed during a production incident. E3's primary domain is preference management, the furthest from reliability tooling of any backup pairing. Mitigation: E3's month-1 co-build work with E4 is weighted toward delivery pipeline failure handling and alerting infrastructure. E3 will not be expert in E4's domain by month 2.5, but will have enough context to execute runbooks and escalate correctly. The shared on-call rotation means E4 is never the sole responder to an incident they authored.

What the runbook review does not solve: a novel failure mode at 3am that the runbook doesn't cover. In that scenario, E3 pages E1 or E2. This negates some of the rotation benefit. We accept this because the alternative — E1 and E2 sharing on-call indefinitely — is worse for retention and error risk. By month 4, after two months of production operation, the rotation should be genuinely effective.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting
  - Per-user rate limiting (sliding window, Redis)
     │
     ▼
[Notification Router]
  - Preference check (Redis cache → DB fallback → fail-pending, not suppress)
  - Suppression check (DND windows, frequency caps)
  - Priority assignment
  - Channel selection
     │
     ├─── P0 path ──────────────────────────────────────────────────┐
     │                                                              │
     ▼                                                              ▼
[PostgreSQL — P1/P2 instance]                    [PostgreSQL — P0 dedicated instance]
  ├── notifications table                           ├── notifications_p0 table
  ├── notification_outbox table (P1, P2)            ├── notification_outbox_p0 table
  └── notification_payloads table                   └── notification_payloads_p0 table
     │                                                              │
     ▼                                                              ▼
[General Outbox Poller Fleet]                    [P0 Outbox Poller — 2 active instances]
  4 instances, FOR UPDATE SKIP LOCKED              Leader-elected via PostgreSQL advisory lock
  Batch 500 P1/P2 rows                             Follower polls for leader liveness
  Read-before-mark on Redis                        Read-before-mark on Redis
     │                                                              │
     ▼                                                              ▼
[Redis Cluster — P1/P2 queues]                   [Redis Sentinel — P0 queue]
  notification_queue:p1 (appendfsync everysec)      notification_queue:p0
  notification_queue:p2 (appendfsync everysec)      appendfsync always
     │                                                              │
     ├── P1 Worker Pool (20 workers)                ├── P0 Worker Pool (10 workers)
     └── P2 Worker Pool (10 workers, assists P1)    │
          │                                         │
          └─────────────────────────────────────────┘
                              │
                              ▼
                     [Channel Dispatcher]
                       ├── Push (APNs / FCM)
                       ├── Email (SendGrid)
                       ├── SMS (Twilio — disabled until month 3)
                       └── In-app (already written; mark delivered)
                              │
                        ┌─────┴─────┐
                        ▼           ▼
                  [Delivery Log]  [Dead-Letter Queue per priority]
                  (PostgreSQL     (Redis sorted set + runbook)
                   + S3)
                        │
                        ▼
                  [Feedback Processor]
                  (bounces, receipts, token invalidations)
```

### 2.1 Queue Design: Three Queues, Operational Cost Quantified

We use three separate Redis sorted sets with separate worker pools. The operational overhead is real and quantified so the team makes an informed decision about whether it is worth carrying.

**Full operational surface:**

| Component | Count | Maintenance burden |
|-----------|-------|-------------------|
| Redis sorted sets | 3 | Schema trivial; no ongoing cost |
| Dead-letter queues | 3 | Each requires its own backlog alert, runbook, and drain procedure — see Section 3.6 |
| Backlog metric dashboards | 3 | Independent depth, age, throughput panels per queue |
| Retry policies | 3 | P0 retries aggressively; P1/P2 use exponential backoff — tuned independently |
| Capacity scaling decisions | 3 | Worker pool sizes set independently; resizing one does not rebalance others |
| Starvation mitigation logic | 1 | P2 workers assist P1 above threshold — fully specified below |

**Estimated ongoing maintenance load:** ~5 engineer-hours/month for alert tuning, DLQ drain reviews, and retry policy adjustments. With 4 engineers, approximately 1.25 hours/engineer/month — a real cost, not negligible, but manageable.

**Why we accept this cost.** Per-priority worker pools require per-priority queues. The alternative — a single queue with priority scores and a shared worker pool — requires workers to implement priority-aware polling logic that is harder to reason about under backlog conditions. The operational overhead is higher with three queues; the failure mode complexity is lower. Given the team's size, we prefer simpler failure modes over simpler operations.

**P0 on a dedicated PostgreSQL instance — why table separation is insufficient.** A separate table (`notification_outbox_p0`) on the shared PostgreSQL instance does not prevent lock contention or autovacuum pressure from P1/P2 write storms from affecting P0 poller reads. A heavy P1/P2 insert workload can cause PostgreSQL's autovacuum to run against shared infrastructure, increasing I/O and potentially delaying P0 reads by hundreds of milliseconds — enough to miss an OTP delivery SLA. The fix is a dedicated PostgreSQL instance for P0 workloads. Cost: one additional managed PostgreSQL instance (~$300–600/month), additional connection pooling configuration, and a separate backup and monitoring setup. This is the right tradeoff for an SLA that includes auth OTPs.

**P2-to-P1 starvation mitigation — fully specified.**

*Trigger:* Each P2 worker checks P1 queue depth at the start of each poll cycle via a single `ZCARD notification_queue:p1` call (~0.5ms). If depth exceeds `P1_ASSIST_THRESHOLD` (default: 10,000 items, configurable via environment variable), the worker enters assist mode.

*How many workers migrate:* P2 workers independently check the threshold and independently enter assist mode. No central coordination. The consequence is that all 10 P2 workers may simultaneously enter assist mode, leaving P2 unserved. This is correct behavior: if P1 has 10,000+ items backlogged, P2 should be fully deprioritized.