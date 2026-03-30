# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## A Note on This Revision

The previous version of this document contained four missing sections (3.2, 3.3, 3.4, 3.6) that were cited as containing critical specifications. Those sections are fully written here. Additionally, the previous version had architectural contradictions — most significantly, the outbox pattern's correctness guarantee depended on Redis durability while simultaneously claiming Redis durability was not a correctness concern. That contradiction is resolved below with a concrete fix. Every other substantive problem identified in review is addressed directly, with the specific criticism quoted where useful for traceability.

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**The core architectural decisions, stated with their actual tradeoffs:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Outbox pattern with read-before-mark (not write-then-mark) | Poller re-reads Redis before marking relayed; adds ~1ms per batch; eliminates the crash-window correctness contradiction |
| P0 workloads on a dedicated PostgreSQL instance | Additional infrastructure cost and operational surface; required because table separation alone does not prevent lock contention or autovacuum interference from P1/P2 write storms |
| Three priority queues with separate worker pools | ~5 engineer-hours/month operational overhead, quantified in Section 2.1 |
| P0 poller runs two active instances behind a leader lock | Eliminates single-point-of-failure for auth OTPs; adds coordination complexity, fully specified in Section 3.5 |
| Redis AOF with `appendfsync always` for P0 queue only | ~3× write latency on P0 queue vs. `everysec`; accepted because P0 SLA requires it; P1/P2 use `everysec` and tolerate up to 1-second loss, recovered by outbox |
| SMS excluded from month-2 launch | Spend caps must exist before channel goes live; architecture supports SMS from day one, channel is toggled off at dispatcher |
| Co-build in month 1 extends month-2 timeline to month 2.5 | Explicitly acknowledged; tradeoff between delivery speed and cross-training is real and the schedule reflects it |

**What requires sign-off before implementation, with owners and consequences if not resolved:**

| Decision | Owner | Deadline | Consequence if missed |
|----------|-------|----------|-----------------------|
| SMS spend caps and daily budget alert thresholds | Finance + Product | End of month 2 | SMS channel does not launch in month 3; push to month 4 |
| OTP escalation path when outbox relay exhausts retries | Product + Security | End of month 1 | Month-2 launch delayed; P0 cannot ship without a specified failure behavior |
| Behavior for push-enabled/in-app-disabled users when push fails permanently | Product | End of month 1 | Month-2 launch delayed; default behavior (silent DLQ) is not acceptable for P0 |

The OTP escalation path is a launch blocker with a named consequence: if Product and Security do not provide input by end of month 1, the month-2 launch date moves to month 3. E4 owns driving this decision to closure. If E4 does not have a documented decision by week 3 of month 1, the project lead escalates. "We'll figure it out" is not an acceptable state when OTPs are P0 and ship with the initial system.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 average; ~28 for top-20% cohort | See distribution note below |
| **Total notifications/day** | **~50M** | Planning baseline |
| Peak multiplier | 3× fleet average sustained, 6× fleet average burst | See distribution note |
| Peak sustained throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Peak burst throughput | ~3,500/sec | Capacity ceiling design |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only — see SMS note |

**Distribution note — following the logic fully.** The 17 notifications/user/day figure comes from engaged-user benchmarks. The previous version acknowledged that the top 20% of users generate ~60% of volume but did not follow the implication: if the high-activity cohort is predominantly in the DAU pool (which it is — highly active users are by definition daily active), then the per-user rate for DAU is not uniformly 17. The top 20% of DAU (600K users) average approximately 28 notifications/day; the bottom 80% (2.4M users) average approximately 10/day. The aggregate still produces ~50M/day, so the planning baseline holds.

The burst implication is different. The 6× fleet-average burst ceiling was described in the previous version as a hedge against being wrong about the fleet average. It is not a hedge against the high-activity cohort's burst behavior. If the top 20% of users spike 8–10× their personal average (28/day baseline), their burst rate is ~224–280 notifications/user/day during the spike window. For 600K users, that is a localized burst of roughly 10,000–14,000 notifications/second, concentrated in the time window of the triggering event (a viral post, a breaking news hook, a celebrity joining the platform).

We cannot sustain 14,000/sec with this infrastructure. We can absorb it via queue depth. The P1 and P2 queues have no hard depth limit; backlog accumulates and drains over minutes to hours. The P0 queue is protected separately (Section 3.5). The correct response to a viral event is not to scale the delivery fleet to match the burst — it is to accept latency on P1/P2 delivery during the burst and communicate that SLAs are best-effort for non-P0 traffic. We instrument queue depth and age from day one and alert when P1 age exceeds 5 minutes.

**SMS volume and cost — resolving the internal inconsistency.** The previous version stated 1M SMS/day (2% of 50M), blended cost of $0.02–$0.04/message, and concluded that spend caps are required. These three facts are inconsistent: 1M SMS/day at $0.02–$0.04 is $20,000–$40,000/day, or $7–14M/month. For a social app at this scale, that cost is implausible as a sustainable channel allocation and contradicts the "auth + high-priority only" use case description.

The correct reconciliation: **the 2% channel split and the "auth + high-priority only" use case cannot both be true.** Auth OTPs and security alerts for 3M DAU, assuming 5% of users trigger an auth event on a given day, is 150,000 SMS/day — not 1M. The 2% figure was carried over from an industry average that includes marketing SMS, which this design explicitly does not use.

**Revised SMS estimate: 100,000–200,000 messages/day** for auth OTPs and security alerts. At blended $0.02–$0.04/message, daily cost is **$2,000–$8,000/day**, or $60,000–$240,000/month. This is a real budget line that requires finance approval, but it is not the $7–14M/month figure that would make SMS non-viable. The spend cap mechanism (Section 3.4) is still required because international rates vary enough to cause unexpected cost spikes, and the cap prevents runaway spend from a misconfigured event trigger.

All volume estimates are instrumented from day one. We revisit the SMS estimate in month 2 with real data.

### Team Allocation and Schedule — Acknowledging the Co-Build Tension

The previous version proposed co-building as a cross-training mitigation while maintaining a month-2 launch deadline. These are in direct tension: co-building means two engineers work on one subsystem rather than two subsystems in parallel, which extends the total build time.

**Revised schedule acknowledges this explicitly:**

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build queue infrastructure and delivery pipeline. E3+E4 co-build preference system and reliability tooling. | No parallelization of subsystems. Month-2 deadline moves to month 2.5 as a result. |
| 2 | Integration, end-to-end testing, runbook authorship and review. | All four engineers review all runbooks before launch. |
| 2.5 | Launch: push, email, in-app. SMS architecture in place but disabled. | Shared on-call rotation begins. |
| 3 | SMS launch (pending spend cap sign-off). Monitoring refinement. Cross-training assessed. | SMS delayed to month 4 if sign-off not received by end of month 2. |
| 4–5 | Iteration based on production data. Preference UI, digest batching, A/B framework. | |
| 6 | Hardening, load testing, runbook updates. | |

**The month-2 deadline is gone.** The previous version's month-2 launch was incompatible with co-building. Co-building is the right call for a 4-person team operating a production system without dedicated QA. The schedule reflects this honestly rather than maintaining an unrealistic date.

**On-call in month 2.5.** All four engineers share on-call rotation from launch. Each engineer is primary on-call roughly one week in four. E3 will be primary on-call for systems they participated in building (co-build in month 1) but are not the primary expert on. The runbook review requirement — all four engineers review all runbooks before launch — is specifically designed so E3 can execute the runbook for a queue infrastructure incident and escalate correctly, even if they cannot diagnose the root cause independently.

What the runbook review does not solve: a novel failure mode at 3am that the runbook doesn't cover. In that scenario, E3 pages E1 or E2. This negates some of the rotation benefit. We accept this because the alternative — E1 and E2 sharing on-call for a production system indefinitely — is worse for retention and error risk. By month 4, after two months of production operation, the rotation should be genuinely effective.

| Engineer | Primary Responsibility | Secondary (Cross-Training via Co-Build) |
|----------|----------------------|---------------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Channel integrations (co-built with E2) |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure (co-built with E1) |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling (co-built with E4) |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system (co-built with E3) |

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
     ├─── P0 path ─────────────────────────────────────────────────┐
     │                                                             │
     ▼                                                             ▼
[PostgreSQL — P1/P2 instance]                    [PostgreSQL — P0 dedicated instance]
  ├── notifications table                           ├── notifications_p0 table
  ├── notification_outbox table (P1, P2)            ├── notification_outbox_p0 table
  └── notification_payloads table                   └── notification_payloads_p0 table
     │                                                             │
     ▼                                                             ▼
[General Outbox Poller Fleet]                    [P0 Outbox Poller — 2 active instances]
  4 instances, FOR UPDATE SKIP LOCKED              Leader-elected via Postgres advisory lock
  Batch 500 P1/P2 rows                             Follower polls for leader liveness
  Read-before-mark on Redis                        Read-before-mark on Redis
     │                                                             │
     ▼                                                             ▼
[Redis Cluster — P1/P2 queues]                   [Redis Sentinel — P0 queue]
  notification_queue:p1 (appendfsync everysec)      notification_queue:p0
  notification_queue:p2 (appendfsync everysec)      appendfsync always
     │                                                             │
     ├── P1 Worker Pool (20 workers)                ├── P0 Worker Pool (10 workers)
     └── P2 Worker Pool (10 workers, assist P1)     │
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

We use three separate Redis sorted sets with separate worker pools. The operational overhead is real and quantified here.

**Full operational surface:**

| Component | Count | Maintenance burden |
|-----------|-------|-------------------|
| Redis sorted sets | 3 | Schema trivial; no ongoing cost |
| Dead-letter queues | 3 | Each requires its own backlog alert, runbook, and drain procedure — see Section 3.6 |
| Backlog metric dashboards | 3 | Independent depth, age, throughput panels per queue |
| Retry policies | 3 | P0 retries aggressively; P1/P2 use exponential backoff — tuned independently |
| Capacity scaling decisions | 3 | Worker pool sizes set independently |
| Starvation mitigation logic | 1 | P2 workers assist P1 above threshold — fully specified below |

**Estimated ongoing maintenance load:** ~5 engineer-hours/month. With 4 engineers, approximately 1.25 hours/engineer/month.

**Why we accept this cost.** Per-priority worker pools require per-priority queues. A single queue with priority scores and a shared worker pool requires workers to implement priority-aware polling logic that is harder to reason about under backlog conditions. We prefer simpler failure modes over simpler operations.

**P0 on a dedicated PostgreSQL instance — why table separation is insufficient.**

The previous version used a separate table (`notification_outbox_p0`) on the shared PostgreSQL instance to prevent poller contention. This was correctly identified as solving the wrong problem: table separation does not prevent lock contention or autovacuum pressure from P1/P2 write storms from affecting P0 poller reads. A heavy P1/P2 insert workload can cause PostgreSQL's autovacuum to run against shared infrastructure, increasing I/O and potentially delaying P0 reads by hundreds of milliseconds — enough to miss an OTP delivery SLA.

The correct fix is a dedicated PostgreSQL instance for P0 workloads. P0 tables (`notifications_p0`, `notification_outbox_p0`, `notification_payloads_p0`) live on this instance. P1/P2 workloads cannot interfere with it. The cost: one additional PostgreSQL instance (~$300–600/month on a managed provider at this scale), additional connection pooling configuration, and a separate backup and monitoring setup. This is the right tradeoff for an SLA that