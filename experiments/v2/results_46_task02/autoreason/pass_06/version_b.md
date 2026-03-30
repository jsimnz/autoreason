# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design handles ~50M notifications/day across push, email, in-app, and SMS channels. The revision addresses fourteen specific problems identified in review. Where a problem required a decision rather than a specification, the decision is made explicitly and the tradeoff is stated. Where a problem revealed a genuine gap, the gap is filled. Where a problem exposed an assumption that was wrong, the assumption is corrected.

**Changes from the prior version, summarized:**

| Problem | Resolution |
|---------|------------|
| Outbox-to-Redis relay crash window produces Redis duplicates | Sorted set score is the outbox row ID; duplicate ZADD is a no-op; idempotency moves to ingestion, not just delivery |
| P0 Redis Sentinel throughput never analyzed | P0 throughput ceiling calculated; Sentinel retained with specified limits and overflow behavior |
| P0 poller leader election underspecified | Section 3.5 written in full: failover timing, in-flight batch handling, lock release sequence |
| P2 starvation "correct behavior" claim unjustified | P2 contents defined; starvation threshold justified against defined contents |
| Cross-instance consistency gap for security alerts | Security alerts route to P0 instance only; in-app written via async fan-out after P0 commit, not in same transaction |
| Burst analysis contradicts 6× ceiling | 6× ceiling replaced with honest queue-depth model; P1 SLA during viral events specified |
| Redis memory sizing absent | Memory estimate added with payload size assumptions |
| Sections 3.5 and 3.6 referenced but missing | Both sections written in full |
| E3/E4 backup inadequate for alerting failure | Alerting infrastructure ownership split; E3 cross-trains on alert configuration specifically |
| Feedback processor has no internals | APNs/FCM token invalidation, bounce handling, and receipt processing fully specified |
| DLQ drain ownership unspecified | Ownership rotation and escalation path defined |
| OTP escalation path has no escalation target | Escalation chain named: E4 → Engineering Manager → VP Product |
| SMS spend cap has no tiebreaker | Finance owns the number; Product owns the use case scope; Engineering holds the veto on unsafe configurations |
| SMS cost estimate too wide for budget approval | Phased approach: month-2 launch with domestic-only SMS at a defensible narrow estimate; international expansion gated on real data |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU (social app benchmark) |
| Notifications/DAU/day | ~17 average | Engaged-user benchmark |
| **Total notifications/day** | **~50M** | Planning baseline |
| Sustained peak throughput | ~1,750/sec | 50M × 3× peak / 86,400 |
| Queue absorption ceiling | ~14,000/sec inbound | Viral event model; see Section 1.2 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2% of auth-eligible events) | 100K–200K/day | See Section 1.3 |

### 1.2 Burst Model — Corrected

The prior version retained a 6× fleet-average burst ceiling while demonstrating the ceiling was already wrong. That contradiction is resolved here.

**The honest model:**

The top 20% of DAU (600K users) generate approximately 28 notifications/day at baseline. During a viral event — a trending post, a mass follow event, a breaking news interaction — this cohort can spike 8–10× their personal baseline within a short window. At 10× personal baseline for 600K users, inbound rate is approximately 14,000 notifications/second during the spike.

Sustainable delivery throughput with this infrastructure is approximately 1,750/second. We cannot deliver 14,000/second. We do not try.

**What we do instead:**

P1 and P2 queues are unbounded in depth. During a viral event, inbound rate exceeds delivery rate, queues accumulate, and delivery latency increases. This is the correct behavior. A social notification about a trending post that arrives 8 minutes late is acceptable. An OTP that arrives 8 minutes late is not. P0 is protected separately (Section 3.5) and is not subject to viral event pressure because OTPs and security alerts do not scale with social engagement.

**P1 SLA during sustained viral events, specified:**

| Queue depth | Expected P1 tail latency | Alert state |
|-------------|--------------------------|-------------|
| < 10,000 items | < 30 seconds | Normal |
| 10,000–100,000 items | 1–10 minutes | Warning: page on-call |
| 100,000–1,000,000 items | 10–90 minutes | Critical: page on-call + notify product |
| > 1,000,000 items | > 90 minutes | Incident: consider shedding lowest-score P1 items |

At 14,000/sec inbound and 1,750/sec delivery, the queue grows at ~12,000/sec. Five minutes produces ~3.6M items. This crosses the critical threshold in under 10 minutes. The response is to notify product that P1 SLA is degraded, continue draining at maximum rate, and not shed items unless queue age exceeds 2 hours. Items older than 2 hours in P1 are expired at the worker (checked against creation timestamp in the payload) and logged to the delivery log as `expired_undelivered` rather than delivered.

The 2-hour expiry is a product decision. It is listed in the sign-off table in Section 1.5.

**Redis memory at depth:**

Sorted set entries store only the notification ID as the member and the outbox row ID as the score. Payload is not stored in Redis; workers fetch from PostgreSQL by ID. A sorted set entry is approximately 50–80 bytes. At 3.6M items, peak Redis memory for the P1 queue is approximately 180–290MB — well within a standard Redis instance. The payload fetch pattern means PostgreSQL read load increases during deep-queue events; this is acceptable because PostgreSQL read replicas handle worker fetches (Section 3.2).

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

### 1.3 SMS Volume — Revised Estimate and Budget Approach

**Revised volume:** 100,000–200,000 messages/day, consisting of auth OTPs and security alerts for users with no alternative auth channel.

**Budget approach for Finance sign-off:**

The prior version presented a $60K–$240K/month range, which is too wide for budget approval. The range was wide because of international rate variance. The resolution is to launch SMS as domestic-only in month 3, then expand internationally in month 5 after real volume data exists.

**Domestic-only SMS cost model (month 3 launch):**

| Parameter | Value |
|-----------|-------|
| Domestic Twilio rate | $0.0079/message |
| Daily volume (domestic users, ~60% of DAU) | 60,000–120,000 messages |
| Daily cost | $474–$948 |
| **Monthly cost** | **$14,220–$28,440** |

This is a $14K–$28K/month range — approximately 2× spread, acceptable for budget approval. The spend cap (Section 3.4) is set at $35,000/month with a daily alert at $1,200/day. Finance approves this number. Product approves the use case scope (auth OTPs and security alerts only, no marketing). Engineering holds veto on configurations that would disable the spend cap.

International SMS expansion is a separate budget decision, made in month 4 with actual domestic volume data as a calibration point.

### 1.4 Team Allocation and Schedule

**Corrected schedule reflecting co-build reality:**

| Month | Work | Notes |
|-------|------|-------|
| 1 | E1+E2 co-build queue infrastructure, delivery pipeline, channel integrations. E3+E4 co-build preference system, reliability tooling, alerting infrastructure. | E3 specifically cross-trains on alert configuration and monitoring, not just runbook execution. |
| 2 | Integration, end-to-end testing, runbook authorship. All four engineers review all runbooks. Load testing against viral event model. | |
| 2.5 | Launch: push, email, in-app. SMS architecture deployed but disabled. | Shared on-call rotation begins. |
| 3 | SMS launch (domestic only, pending Finance sign-off by end of month 2). | SMS delayed to month 4 if sign-off not received. |
| 4 | Production iteration. Preference UI, digest batching. International SMS scoping with real volume data. | |
| 5 | International SMS launch (if approved). A/B framework. | |
| 6 | Hardening, load testing, runbook updates. | |

**E3/E4 backup — revised mitigation:**

The prior version acknowledged that E4 owns alerting infrastructure and E3's backup capability was limited to runbook execution, which is insufficient if the alerting infrastructure itself fails silently. The revised mitigation:

E3's month-1 co-build with E4 is explicitly weighted toward alert configuration, not just delivery pipeline failure handling. By end of month 1, E3 must be able to independently create, modify, and validate alert rules in the monitoring stack. This is a testable milestone: E3 demonstrates this capability to E4 before month 2 integration begins.

Additionally, alerting infrastructure uses two independent notification paths: PagerDuty (primary) and a separate SMS alert to all four engineers' personal phones via a Twilio number outside the main system. This second path is intentionally dumb — a cron job that checks a heartbeat endpoint and sends SMS if the heartbeat is absent. If E4 is unavailable and the primary alerting infrastructure has a novel failure, the heartbeat SMS fires independently. E3 can then diagnose from a known-good state rather than discovering the failure via user reports.

**Engineer responsibilities:**

| Engineer | Primary | Secondary (co-build) | Specific cross-train milestone |
|----------|---------|---------------------|-------------------------------|
| E1 | Core pipeline, queue infrastructure | Channel integrations | Can independently deploy and roll back channel integration config |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio) | Queue infrastructure | Can independently modify worker pool sizing |
| E3 | Preference management, user-facing API, suppression logic | Reliability tooling, **alert configuration** | Can independently create and validate alert rules by end of month 1 |
| E4 | Reliability, monitoring, failure handling, DevOps | Preference system | Can independently modify suppression logic |

### 1.5 Decisions Required Before Launch

| Decision | Owner | Deadline | Consequence if missed | Escalation path |
|----------|-------|----------|-----------------------|----------------|
| OTP escalation path when outbox relay exhausts retries | Product + Security | End of month 1, week 3 | Month-2.5 launch delayed; P0 cannot ship without specified failure behavior | E4 → Engineering Manager → VP Product. If no documented decision by week 3, E4 emails Engineering Manager. If no resolution by week 4, VP Product is looped in. "We'll figure it out" is not an acceptable state. |
| Behavior for push-enabled/in-app-disabled users when push fails permanently | Product | End of month 1 | Month-2.5 launch delayed | Same chain as above |
| P1 notification expiry threshold (proposed: 2 hours) | Product | End of month 1 | Default of 2 hours is used; Product accepts this implicitly if no response | E4 → Engineering Manager |
| SMS domestic spend cap approval ($35K/month, $1,200/day alert) | Finance (owns the number) | End of month 2 | SMS delayed to month 4 | Engineering Manager → CFO |
| SMS use case scope (auth OTPs + security alerts only) | Product (owns the scope) | End of month 2 | SMS delayed to month 4 | Engineering Manager → VP Product |
| Month-2.5 launch date alignment with external commitments | Product + Engineering Manager | End of month 1 | Schedule conflict discovered late | Engineering Manager owns surfacing this; it is not an engineering team decision |

**On the month-2.5 slip:** The prior version stated this as a consequence of co-building, as though it were self-resolving. It is not. If there are external commitments to a month-2 launch, a 2-week slip requires explicit stakeholder agreement. The Engineering Manager owns surfacing this conflict in week 1. If the month-2 deadline is genuinely hard, the co-build approach is reconsidered — but the consequence of not co-building is higher operational risk, not a faster safe launch.

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
     ├─── P0 path ──────────────────────────────────────────────────────┐
     │                                                                  │
     ▼                                                                  ▼
[PostgreSQL — P1/P2 instance]                      [PostgreSQL — P0 dedicated instance]
  ├── notifications table (P1, P2)                   ├── notifications_p0 table
  ├── notification_outbox table                      └── notification_outbox_p0 table
  └── notification_payloads table                    (No in-app writes here; see Section 2.3)
     │                                                                  │
     ▼                                                                  ▼
[General Outbox Poller Fleet]                      [P0 Outbox Poller — 2 active instances]
  4 instances, FOR UPDATE SKIP LOCKED                Leader-elected via PostgreSQL advisory lock
  Batch 500 rows                                     See Section 3.5 for full failover spec
  Idempotent ZADD (score = outbox row ID)            Idempotent ZADD (score = outbox row ID)
     │                                                                  │
     ▼                                                                  ▼
[Redis Cluster — P1/P2]                            [Redis Sentinel — P0]
  notification_queue:p1 (appendfsync everysec)        notification_queue:p0
  notification_queue:p2 (appendfsync everysec)        appendfsync always
  ~6GB instance, 2 primaries                          See Section 2.1 for throughput analysis
     │                                                                  │
     ├── P1 Worker Pool (20 workers)                  └── P0 Worker Pool (10 workers)
     └── P2 Worker Pool (10 workers)                           │
          │                                                    │
          └────────────────────────────────────────────────────┘
                                   │
                                   ▼
                          [Channel Dispatcher]
                            ├── Push (APNs / FCM)
                            ├── Email (SendGrid)
                            ├── SMS (