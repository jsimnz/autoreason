# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

**The core architectural bet:** three priority-partitioned queues with channel fanout per priority tier, backed by a transactional outbox pattern. At 50M/day, even a 0.01% crash rate between two non-atomic writes is 5,000 lost or duplicated notifications per day. The outbox eliminates this class of failure.

**What the reliability mechanisms prevent and do not prevent:**

| Mechanism | Prevents | Does Not Prevent |
|-----------|----------|-----------------|
| Outbox pattern | Lost notifications on crash | Duplicate delivery |
| Idempotent ZADD (score = outbox row ID) | Redis duplicates from relay crash window | Lost notifications |
| Idempotency key at channel dispatcher | Duplicate delivery to external provider | Lost notifications |

These three mechanisms are complementary. The outbox prevents loss. Idempotent ZADD prevents Redis duplicates. The dispatcher idempotency key prevents double-sends to APNs, FCM, and SendGrid. None of them is redundant with the others.

**Key design decisions and tradeoffs, stated upfront:**

| Decision | Tradeoff Accepted |
|----------|-------------------|
| Sorted set score = outbox row ID (monotonically increasing) | Duplicate ZADD is a no-op; relay crash window cannot produce Redis duplicates; adds no latency |
| P0 workloads on dedicated PostgreSQL instance | ~$300–600/month additional cost; required because autovacuum pressure from P1/P2 write storms on a shared instance can delay P0 poller reads by hundreds of milliseconds — enough to miss an OTP SLA |
| Three priority queues with separate worker pools | ~5 engineer-hours/month operational overhead; simpler failure modes than a shared pool with priority-aware polling |
| P0 poller runs two active instances behind a PostgreSQL advisory lock | Eliminates single point of failure for auth OTPs; full failover spec in Section 3.5 |
| Redis AOF `appendfsync always` for P0 only; `everysec` for P1/P2 | ~3× write latency on P0 writes; accepted because P0 SLA requires it; P1/P2 tolerate up to 1-second loss, recovered by outbox |
| P1/P2 queues unbounded in depth | Cannot sustain 14,000/sec viral burst at delivery; accept latency on P1/P2 rather than shed items; P0 protected separately |
| Preference check synchronous at routing, fail-pending not fail-suppress | Couples routing latency to cache health; cache unavailability queues the notification rather than silently dropping it |
| In-app written via async fan-out after P0 commit, not in same transaction | Avoids cross-instance consistency gap for security alerts; if push relay fails permanently, in-app record still exists |
| SMS excluded from month-2.5 launch; domestic-only in month 3 | Spend caps must exist before channel goes live; international expansion gated on real volume data from month 3 |
| Co-build in month 1 extends launch to month 2.5 | Explicitly acknowledged; month-2 deadline requires stakeholder sign-off on the slip |

**What requires sign-off before implementation, with owners, deadlines, and escalation paths:**

| Decision | Owner | Deadline | Consequence if missed | Escalation path |
|----------|-------|----------|-----------------------|----------------|
| OTP escalation path when outbox relay exhausts retries | Product + Security | End of month 1, week 3 | Month-2.5 launch delayed; P0 cannot ship without specified failure behavior | E4 → Engineering Manager by week 3; VP Product looped in by week 4 if unresolved |
| Behavior for push-enabled/in-app-disabled users when push fails permanently | Product | End of month 1 | Month-2.5 launch delayed | Same chain |
| P1 notification expiry threshold (proposed: 2 hours) | Product | End of month 1 | 2-hour default used; Product accepts implicitly if no response | E4 → Engineering Manager |
| SMS domestic spend cap ($35K/month ceiling, $1,200/day alert) | Finance (owns the number) | End of month 2 | SMS delayed to month 4 | Engineering Manager → CFO |
| SMS use case scope (auth OTPs + security alerts only, no marketing) | Product (owns the scope) | End of month 2 | SMS delayed to month 4 | Engineering Manager → VP Product |
| Month-2.5 launch date alignment with external commitments | Engineering Manager | End of month 1, week 1 | Schedule conflict discovered late; not an engineering team decision to resolve |

The OTP escalation path is a hard launch blocker. "We'll figure it out" is not an acceptable state when OTPs are P0 and ship with the initial system. E4 owns driving this to documented closure.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social app benchmark) |
| Notifications/DAU/day | ~17 average; ~28 for top-20% cohort | Engaged-user benchmark; see distribution note |
| **Total notifications/day** | **~50M** | Planning baseline |
| Sustained peak throughput | ~1,750/sec | 50M × 3× peak / 86,400 |
| Queue absorption ceiling | ~14,000/sec inbound | Viral event model; see Section 1.2 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS | 100K–200K/day | Auth OTPs and security alerts only; see Section 1.3 |

**Distribution note.** The 17 notifications/user/day figure applied uniformly to 3M DAU produces ~51M/day, used as a planning baseline. The realistic distribution is skewed: the top 20% of DAU (600K users) average approximately 28 notifications/day; the bottom 80% (2.4M users) average approximately 10/day. The aggregate still produces ~50M/day, so the planning baseline holds. The burst implication is different and is addressed directly in Section 1.2.

### 1.2 Burst Model — Honest Queue-Depth Approach

The top 20% of DAU (600K users) average 28 notifications/day at baseline. During a viral event, this cohort can spike 8–10× their personal baseline within a short window. At 10× for 600K users, inbound rate is approximately 14,000 notifications/second during the spike.

Sustainable delivery throughput with this infrastructure is approximately 1,750/second. We cannot deliver 14,000/second. We do not try to.

**What we do instead:** P1 and P2 queues are unbounded in depth. During a viral event, inbound rate exceeds delivery rate, queues accumulate, and delivery latency increases. This is the correct behavior. A social notification about a trending post that arrives 8 minutes late is acceptable. An OTP that arrives 8 minutes late is not. P0 is protected separately (Section 3.5) and is not subject to viral event pressure because OTPs and security alerts do not scale with social engagement.

**P1 SLA during sustained viral events:**

| Queue depth | Expected P1 tail latency | Alert state |
|-------------|--------------------------|-------------|
| < 10,000 items | < 30 seconds | Normal |
| 10,000–100,000 items | 1–10 minutes | Warning: page on-call |
| 100,000–1,000,000 items | 10–90 minutes | Critical: page on-call + notify product |
| > 1,000,000 items | > 90 minutes | Incident: consider shedding lowest-score P1 items |

At 14,000/sec inbound and 1,750/sec delivery, the queue grows at ~12,000/sec. Five minutes produces ~3.6M items, crossing the critical threshold in under 10 minutes. The response is to notify product that P1 SLA is degraded, continue draining at maximum rate, and not shed items unless queue age exceeds 2 hours. Items older than 2 hours in P1 are expired at the worker (checked against creation timestamp in the payload) and logged to the delivery log as `expired_undelivered`.

The 2-hour expiry threshold is a product decision listed in Section 1.1's sign-off table.

**Redis memory at depth:**

Sorted set entries store only the notification ID as member and the outbox row ID as score. Payload is not stored in Redis; workers fetch from PostgreSQL by ID. A sorted set entry is approximately 50–80 bytes. At 3.6M items, peak Redis memory for the P1 queue is approximately 180–290MB.

**Full Redis memory budget:**

| Component | Estimated memory |
|-----------|-----------------|
| P0 queue (Sentinel primary) | ~10MB steady state; ~50MB at peak |
| P1 queue | ~50MB steady state; ~300MB at viral peak |
| P2 queue | ~20MB steady state |
| P0, P1, P2 dead-letter queues | ~5MB each |
| Sliding window rate limit state (3M DAU × 2 windows) | ~150MB |
| Preference cache (10M users × ~200 bytes) | ~2GB |
| Token/device registry cache | ~500MB |
| **Total** | **~3.1GB steady state; ~3.5GB at peak** |

A 6GB Redis instance provides adequate headroom. P1/P2 use a shared Redis Cluster (two primaries, two replicas each). P0 uses Redis Sentinel (one primary, two replicas). Separate instances are maintained because P0 uses `appendfsync always` and P1/P2 use `appendfsync everysec`; mixing them on the same instance would impose `always` latency on all writes.

### 1.3 SMS Volume and Budget

**Revised volume:** 100,000–200,000 messages/day, consisting of auth OTPs and security alerts for users with no alternative auth channel. The "2% of total notifications" industry figure includes marketing SMS, which this design explicitly excludes.

**Budget approach — phased to enable Finance sign-off:**

The prior estimate produced a $60K–$240K/month range, too wide for budget approval. The range was wide because of international rate variance. Resolution: launch SMS as domestic-only in month 3, then expand internationally in month 5 after real volume data exists.

**Domestic-only SMS cost model (month 3 launch):**

| Parameter | Value |
|-----------|-------|
| Domestic Twilio rate | $0.0079/message |
| Daily volume (domestic users, ~60% of DAU) | 60,000–120,000 messages |
| Daily cost | $474–$948 |
| **Monthly cost** | **$14,220–$28,440** |

This ~2× spread is acceptable for budget approval. The spend cap is set at $35,000/month with a daily alert at $1,200/day. Finance approves the number. Product approves the use case scope (auth OTPs and security alerts only, no marketing). Engineering holds veto on configurations that would disable the spend cap. International SMS expansion is a separate budget decision made in month 4 with actual domestic volume data as a calibration point.

### 1.4 Team Allocation and Schedule

**The month-2 launch deadline is incompatible with co-building.** Co-building means two engineers work on one subsystem together rather than two subsystems in parallel, extending total build time. Co-building is the right call for a 4-person team operating a production system without dedicated QA. The schedule reflects this honestly. If there are external commitments to a month-2 launch, the Engineering Manager surfaces this conflict in week 1 of month 1. If the month-2 deadline is genuinely hard, the co-build approach is reconsidered — but the consequence of not co-building is higher operational risk, not a faster safe launch.

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build queue infrastructure, delivery pipeline, channel integrations. E3+E4 co-build preference system, reliability tooling, alerting infrastructure. | E3 specifically cross-trains on alert configuration (testable milestone below), not just runbook execution. |
| 2 | Integration, end-to-end testing, runbook authorship and review. Load testing against viral event model. | All four engineers review all runbooks before launch. |
| 2.5 | Launch: push, email, in-app. SMS architecture deployed but disabled. | Shared on-call rotation begins. |
| 3 | SMS launch (domestic only, pending Finance sign-off by end of month 2). | SMS delayed to month 4 if sign-off not received. |
| 4 | Production iteration. Preference UI, digest batching. International SMS scoping with real volume data. | |
| 5 | International SMS launch (if approved). A/B framework. | |
| 6 | Hardening, load testing, runbook updates. | |

**Engineer responsibilities:**

| Engineer | Primary | Secondary (co-build) | Specific cross-train milestone |
|----------|---------|---------------------|-------------------------------|
| E1 | Core pipeline, queue infrastructure | Channel integrations | Can independently deploy and roll back channel integration config |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure | Can independently modify worker pool sizing |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling, **alert configuration** | Can independently create and validate alert rules — demonstrated to E4 before month 2 integration begins |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system | Can independently modify suppression logic |

**E3/E4 backup — revised mitigation:**

E4 owns alerting infrastructure. E3's backup capability without explicit cross-training is limited to runbook execution, which is insufficient if the alerting infrastructure itself fails silently. Two mitigations:

1. E3's month-1 co-build with E4 is explicitly weighted toward alert configuration. The milestone is testable: E3 demonstrates the ability to independently create, modify, and validate alert rules before month 2 begins.

2. Alerting uses two independent notification paths: PagerDuty (primary) and a separate heartbeat SMS to all four engineers' personal phones via a Twilio number outside the main system. The heartbeat path is intentionally simple — a cron job that checks a heartbeat endpoint and sends SMS if absent. If E4 is unavailable and primary alerting has a novel failure, the heartbeat SMS fires independently. E3 can then diagnose from a known-good state rather than discovering the failure via user reports.

**The E3/E4 backup asymmetry is a real risk that these mitigations reduce but do not eliminate.** A novel failure mode at 3am that no runbook covers will result in E3 paging E1 or E2, partially negating the rotation benefit. By month 4, after two months of production operation, the rotation should be genuinely effective. We accept this because the alternative — E1 and E2 sharing on-call indefinitely — is worse for retention and error risk.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Per-source rate limiting (token bucket, Redis)
  - Per-user rate limiting (sliding window, Redis)
     │
     ▼
[Notification Router]
  - Preference check (Redis cache → DB fallback → queue-pending, not suppress)
  - Suppression check (DND windows, frequency caps)
  - Priority assignment
  - Channel selection
     │
     ├─── P0 path ────────────────────────────────────────────────────────┐
     │                                                                    │
     ▼                                                                    ▼
[PostgreSQL — P1/P2 instance]                        [PostgreSQL — P0 dedicated instance]
  ├── notifications table (P1, P2)                     ├── notifications_p0 table
  ├── notification_outbox table                        └── notification_outbox_p0 table