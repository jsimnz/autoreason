# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

**Version:** 15.0 | **Status:** Proposed | **Authors:** Engineering Team
**Last Updated:** 2024-01 | **Review Required By:** Engineering Lead, Product, Finance, Legal

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Scale Assumptions and Constraints](#1-scale-assumptions-and-constraints)
3. [System Architecture](#2-system-architecture)
4. [Delivery Channels](#3-delivery-channels)
5. [Priority and Batching Logic](#4-priority-and-batching-logic)
6. [User Preference Management](#5-user-preference-management)
7. [Infrastructure Choices and Cost Model](#6-infrastructure-choices-and-cost-model)
8. [Failure Handling and Reliability](#7-failure-handling-and-reliability)
9. [Observability and Alerting](#8-observability-and-alerting)
10. [Security and Compliance](#9-security-and-compliance)
11. [Delivery Timeline and Milestones](#10-delivery-timeline-and-milestones)
12. [Risks and Open Questions](#11-risks-and-open-questions)
13. [Appendix](#12-appendix)

---

## Executive Summary

This proposal designs a notification system capable of handling approximately 50M notifications per day across push, email, in-app, and SMS channels for a social application with 10M monthly active users. The system must be built by a team of 4 backend engineers and reach full production readiness within 6 months.

Every architectural decision is evaluated against a single filter: **can a team of 4 engineers build it, operate it at 3am, and extend it without heroics?** Where that filter conflicts with theoretical elegance, we choose operational simplicity. This is not a compromise — it is the correct engineering judgment for this team size and timeline.

### The Three Core Architectural Bets

**1. A single priority queue with channel fanout** rather than per-channel queues or a complex event-streaming topology. This shape is debuggable, replaceable, and sufficient for 10M MAU with meaningful headroom. The queue topology is the single hardest structural decision to reverse later, so we choose the simplest shape that handles our load. Per-channel queues give independent scaling and backpressure isolation — a genuine advantage at 100M MAU — but add operational complexity not justified at our scale. We revisit this decision explicitly at the 50M MAU threshold, approximately 18 months away at current growth trajectories.

**2. Managed infrastructure for undifferentiated heavy lifting.** Redis for queuing, PostgreSQL for storage, SendGrid for email, FCM/APNs direct for push. We do not build what we can buy at reasonable cost. The savings in engineering time exceed the service costs by a factor of 5–10× at our scale. The tradeoff is vendor dependency and cost-predictability risk as volume grows; we address this with explicit cost ceilings and migration triggers in Section 6.

**3. Instrument from day one, optimize from month 3.** We do not tune what we have not measured. The monitoring and feedback infrastructure ships in month 1 alongside the core pipeline. Teams that defer observability spend month 4 debugging problems they could have seen in month 2. This is a documented failure mode, not a theoretical risk.

### Delivery Commitment

A working end-to-end system ships in month 2. Every subsequent month adds capability without breaking what is already running. Month 6 is dedicated to hardening, load testing, and eliminating operational debt before the system carries full production traffic. We do not declare production readiness until the load test in month 5 passes and all P0/P1 runbooks have been executed in staging by every on-call engineer.

### What This Proposal Covers

- Scale assumptions and team constraints with explicit uncertainty acknowledgment and sensitivity analysis
- System architecture, data flow, and architecture decision records for every major structural choice
- All four delivery channel implementations with provider-specific configuration, failure modes, and operational guidance
- Priority classification, batching logic, TTL management, collapse key strategy, and digest scheduling
- User preference management, suppression rules, frequency capping, quiet hours, and preference propagation guarantees
- Infrastructure choices with detailed cost model, scaling thresholds, and migration triggers
- Failure handling, retry strategy, circuit breaker configuration, dead-letter handling, and P0 fast path
- Observability stack, alerting thresholds, SLO definitions, and on-call runbooks for every alert class
- Security, compliance, and data handling requirements including GDPR, CAN-SPAM, and TCPA
- Six-month delivery timeline with milestone definitions, risk gates, and explicit go/no-go criteria
- Known risks, open questions, and non-goals with owners and resolution dates

### What This Proposal Does Not Cover

Notification content strategy, A/B testing infrastructure, ML-based send-time optimization, and segmentation campaigns. These are phase 2 concerns that require the measurement foundation this system provides. We explicitly exclude them to protect the delivery commitment. Scope additions to a 4-engineer, 6-month program have a well-documented history of causing the core system to ship late or ship with unacceptable operational debt.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio, typical for social apps |
| Notifications/user/day | ~17 | Industry benchmark for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning (7–9am) and evening (7–10pm) spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Sustained baseline | ~580/sec | 50M / 86,400 |
| Push (70%) | 35M/day | Dominant channel; most users enable push |
| In-app (20%) | 10M/day | Logged-in users only; no direct delivery cost |
| Email (8%) | 4M/day | Digests and critical transactional |
| SMS (2%) | 1M/day | Auth and high-priority only; cost-constrained |

**Sensitivity analysis — the assumptions that matter most:**

The 17 notifications/user/day figure is the most consequential assumption in this model. Industry ranges for social apps run from 8 to 40 per engaged user per day. If our app skews toward high-frequency interaction patterns — short-form content, real-time reactions — we could see 2–3× this baseline. We size the worker pool and queue to handle 2× baseline without re-architecture. The queue depth and worker count are the only two parameters that change at 2×; the topology does not. At 3×, we add a second Redis instance and expand the worker fleet — a half-day infrastructure change, not a redesign.

The channel ratios are industry benchmarks, not empirical data from this application. Push opt-in rates on iOS are particularly volatile. Apple's App Tracking Transparency precedent has conditioned users to deny permissions more readily; real iOS push opt-in rates for social apps currently run 40–55%, not the 70% assumed above. If push opt-in is materially lower, volume shifts to email and in-app, which reduces cost but increases in-app inbox load. We instrument opt-in rates from day one and revisit the channel budget at the month 2 milestone review.

The 30% DAU/MAU ratio assumes a moderately engaged user base. If DAU/MAU reaches 50%, total daily volume approaches 85M notifications and peak throughput approaches 3,000/sec. Our 2× headroom accommodates this without re-architecture.

**Sizing headroom summary:**

| Layer | Nominal Capacity | 2× Headroom | Re-Architecture Trigger |
|-------|-----------------|-------------|------------------------|
| Queue ingestion | 5,000 events/sec | 10,000 events/sec | > 8,000/sec sustained |
| Push workers | 2,000 deliveries/sec | 4,000 deliveries/sec | > 3,500/sec sustained |
| Email workers | 600 deliveries/sec | 1,200 deliveries/sec | > 1,000/sec sustained |
| SMS workers | 100 deliveries/sec | 200 deliveries/sec | > 150/sec sustained |
| PostgreSQL writes | 8,000 rows/sec | 16,000 rows/sec | > 12,000/sec sustained |
| Redis queue depth | 500K items | 1M items | > 750K items sustained |

Re-architecture triggers are monitored by E4 and reviewed at monthly architecture reviews. Hitting a trigger initiates a scoping conversation and capacity planning exercise; it does not automatically authorize engineering work.

### 1.2 Team Allocation

| Engineer | Primary Responsibility | Secondary | On-Call Start |
|----------|----------------------|-----------|---------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | On-call lead, cross-training on channel integrations | Month 1 |
| E2 | Channel integrations (APNs, FCM, SendGrid, Twilio), push token management | Digest batching logic | Month 3 |
| E3 | Preference management, user-facing API, suppression logic | Digest batching logic | Month 3 |
| E4 | Reliability, monitoring, failure handling, infrastructure as code | Load testing, deployment pipelines | Month 1 |

**Explicit allocation risks and mitigations:**

*No dedicated QA.* Engineers own quality end-to-end. Mitigation: integration tests are required for every channel integration before merge; canary deployments are mandatory for all production changes; E4 owns the test harness and load testing infrastructure; the definition of done for every milestone includes minimum test coverage thresholds (unit: 80%, integration: 100% of happy paths and top 3 failure modes per channel).

*E2 is the sole initial owner of all four provider integrations.* This is a bus factor of 1 for a high-risk area. Provider integrations fail in ways that are specific and poorly documented — APNs certificate expiry, FCM token migration from legacy HTTP to HTTP v1, SendGrid IP warming schedules, Twilio carrier filtering. Mitigation: E2 writes an implementation guide and operational runbook for each integration by end of month 3; E1 reviews all four and must be able to operate each independently before month 3 go-live. Cross-training is a milestone gate, not a recommendation.

*Preference management (E3) is a hidden dependency for every notification.* A bug in preference evaluation silently suppresses notifications or delivers them when they should be suppressed — both outcomes are serious. Silent suppression generates user complaints; over-delivery generates regulatory exposure under GDPR and CAN-SPAM. Mitigation: preference evaluation logic has its own unit test suite with 95% branch coverage as a merge requirement; changes to suppression logic require a second review from E1; a shadow evaluation mode runs in staging for two weeks before any preference logic change reaches production.

*E1/E4 scope overlap on reliability.* Explicit resolution: E4 owns infrastructure reliability (deployment, capacity planning, alerting thresholds, runbooks, SLO dashboards); E1 owns application reliability (retry logic, dead-letter handling, idempotency, circuit breakers). Ownership is documented in the service catalog and reviewed at each milestone.

**On-call structure:**

*Months 1–2:* E1 and E4 only. The system is not in production; on-call covers staging incidents and pre-production integration failures.

*Month 3 onwards:* All four engineers rotate weekly. The on-call engineer has a 15-minute acknowledgment SLA for P0 pages and a 4-hour response SLA for P1 pages. Every alert must have a corresponding runbook before the system enters production. E4 is responsible for runbook coverage completeness before the month 3 milestone review.

*Escalation path:* On-call engineer → Engineering Lead (15 minutes if no acknowledgment) → CTO (30 minutes for P0 if Engineering Lead unreachable). This path is documented in PagerDuty and tested with a dry run in month 2.

### 1.3 Non-Functional Requirements

| Requirement | Target | Measurement Method | Rationale |
|-------------|--------|--------------------|-----------|
| P0 notification latency | < 5 seconds end-to-end | Provider delivery receipt timestamp | Security alerts, OTPs — delay causes direct user harm |
| P1 notification latency | < 30 seconds end-to-end | Provider delivery receipt timestamp | DMs, mentions — users expect near-real-time |
| P2 notification latency | < 5 minutes end-to-end | Sampled delivery receipt | Likes, follows — best-effort social feedback |
| P3 notification latency | < 4 hours | Batch completion timestamp | Digest content — batched by design |
| System availability | 99.9% | Uptime on ingestion API and queue workers | ~8.7 hours downtime/year acceptable |
| P0 path availability | 99.95% | Independent health check on P0 fast path | Gates user account access |
| Delivery rate | > 98% for P0/P1 after retries | Sent / (enqueued − suppressed) | Measured against eligible sends, not raw enqueued |
| Preference update propagation | < 10 seconds | Cache invalidation timestamp to next evaluation | User disabling notifications must take effect quickly |
| In-app inbox read latency | < 500ms p99 | APM trace on read endpoint | Synchronous user-facing read path |
| Duplicate delivery rate | < 0.1% | Idempotency key collision tracking | Duplicates erode trust faster than delays |
| Data retention — in-app messages | 90 days active, 1 year cold | Automated partition drops and S3 archival | Compliance and user experience |
| Data retention — delivery logs | 1 year active, 7 years cold | Automated archival to S3 Parquet | Audit trail for regulated notification types |
| GDPR deletion SLA | User data purged within 30 days of request | Deletion job completion log | Legal requirement in applicable jurisdictions |

**On the 99.9% availability target:** Notification delivery is not the application's core transaction path — users can still post, comment, and interact during a notification outage. However, P0 notifications (security alerts, OTPs) gate user access and carry a stricter implicit availability requirement. We address this with a dedicated P0 fast path that bypasses the main queue and has independent failure behavior (see Section 7.3).

**On the < 0.1% duplicate delivery rate:** Duplicate notifications are more damaging to user trust than delayed notifications. A user who receives the same "Alice liked your post" notification three times will disable push notifications entirely — a permanent loss that cannot be recovered through re-engagement. Our idempotency strategy (Section 7.1) is designed to make duplicates structurally impossible under normal operation and detectable within 60 seconds under failure conditions.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Event Sources                               │
│  Application Services │ Scheduled Jobs │ Admin Tools │ Webhooks      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  HTTP POST /v1/notifications/enqueue
                                │  Headers: Authorization, Idempotency-Key
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Ingestion API (stateless)                      │
│  • JSON schema validation, strict mode, 4KB payload limit            │
│  • Idempotency enforcement: Redis SET NX, 24-hour window             │
│  • Per-service rate limiting: token bucket, configurable per caller  │
│  • Internal mTLS authentication between services                     │
│  • Response: 202 Accepted / 400 Invalid / 409 Duplicate / 429 Rate   │
│  • No business logic — thin by design                                │
└──────────────┬───────────────────────────────┬───────────────────────┘
               │ Priority == P0                │ Priority P1/P2/P3
               ▼                               ▼
┌─────────────────────────┐   ┌────────────────────────────────────────┐
│   P0 Direct Dispatch    │   │           Notification Router          │
│                         │   │                                        │
│ • Bypasses main queue   │   │ • Reads user preferences (Redis cache, │
│ • Dedicated Redis list  │   │   5-min TTL, write-through on change)  │
│ •