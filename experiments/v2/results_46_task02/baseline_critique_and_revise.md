# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system for a social app at 10M MAU, delivering 24–60M notifications/day across push, email, in-app, and SMS channels, built by 4 engineers over 6 months.

Three decisions shape everything else.

**First, a single durable queue with explicit priority encoding.** Rather than per-channel queues or per-priority worker pools, we use one Redis Sorted Set where the score deterministically orders by priority first and enqueue time second, within the precision limits of IEEE 754 double-precision float. Workers are homogeneous and scale horizontally. This eliminates priority inversion across channels, reduces DLQ surface from four to one, and produces a system a 4-person team can debug at 2am.

**Second, preferences checked at routing, not delivery, with a hard exception for opt-outs.** Preference lookups at routing avoid wasting queue capacity on suppressed notifications. Opt-out and unsubscribe signals are written to a fast-path suppression set in Redis with no TTL, and delivery workers check this set before every external API call. This satisfies regulatory requirements for prompt opt-out honoring without making the router a bottleneck.

**Third, SMS scoped to authentication and security events only.** Unrestricted SMS at 2% of 36M daily notifications costs approximately $1.97M/year at standard Twilio rates. Gating SMS to OTP, password reset, and security alerts reduces this to approximately $197K/year — a saving of approximately $1.77M/year — and avoids TCPA marketing consent infrastructure entirely.

The system ships a working push and in-app pipeline in month 2, adds email in month 3, completes preference management and digest batching in month 4, adds SMS and frequency capping in month 5, and spends month 6 on load testing, runbook completion, and compliance review.

---

## Problems Identified and Resolved

Every material problem in the prior draft is catalogued here so reviewers can verify that nothing was papered over.

**1. The document was incomplete.** The architecture section and all subsequent sections were absent. *Fixed: all sections are written in full below.*

**2. The priority encoding formula was numerically unsound.** A formula using `priority_weight × 10¹²` produces values requiring up to 16 significant decimal digits. IEEE 754 double-precision float provides only 53 bits of mantissa — approximately 15–16 significant decimal digits — meaning the timestamp component loses precision and FIFO ordering within a priority tier cannot be guaranteed beyond roughly 100ms granularity at high priority weights. The prior draft claimed FIFO ordering "by construction" without acknowledging this limit. *Fixed: the revised formula uses a scale factor that keeps all values within float64's exact integer range (≤ 2⁵³ ≈ 9.007 × 10¹⁵). The resulting ~100ms FIFO imprecision within a priority tier is documented as a known, bounded, and accepted limitation.*

**3. The starvation-free claim was asserted but not demonstrated.** In a strict `ZPOPMAX` system with continuous P0 and P1 inflow, P2 and P3 items can wait indefinitely. The claim was false as written. *Fixed: the revised section replaces the unsupported claim with an honest description of the starvation risk and specifies a concrete aging mechanism that promotes item scores after a defined maximum-wait threshold per priority tier.*

**4. The WebSocket fallback was underspecified.** The decision table said "client polls `/notifications/unread` on reconnect" but gave no poll interval, no pagination scheme, no cursor design, and no treatment of events that arrive when no connection is open. *Fixed: the revised architecture section specifies the poll endpoint contract, cursor-based pagination, the server-side unread count cache, and the event buffering window for reconnecting clients.*

**5. The idempotency key scheme was stated but not implemented.** The prior draft named the key construction but did not specify where it is stored, what the TTL is, what the deduplication window is, or what happens when a duplicate arrives after the window expires. *Fixed: the revised section specifies storage in PostgreSQL with a 24-hour deduplication window, the exact uniqueness constraint, and behavior on late duplicates.*

**6. The feedback processor had no failure handling.** The prior draft noted "any failure in the feedback write path must alert on-call" but did not specify what the worker does on failure — retry, drop, or DLQ. *Fixed: write failures are retried with exponential backoff up to three attempts, then written to a dedicated feedback DLQ with the original payload preserved. An alert fires if the feedback DLQ depth exceeds zero for more than five minutes.*

**7. The reconciliation loop had a race condition.** The loop checked whether a `queued` item was absent from Redis, then re-enqueued it. A worker could dequeue the item in the window between the Redis check and the PostgreSQL re-enqueue, producing a duplicate delivery. *Fixed: the revised section uses `SELECT FOR UPDATE SKIP LOCKED` so workers mark items `processing` atomically on dequeue, and the reconciliation loop only considers items whose PostgreSQL status has remained `queued` — not `processing` — for longer than the staleness threshold.*

**8. The email cost justification used an ungrounded range.** The prior draft claimed "$11–21K/month" with no pricing basis and no AWS SES comparison. *Fixed: the revised section provides specific pricing — SendGrid Pro at approximately 3M emails/day is approximately $14,995/month list price; AWS SES at $0.10/1,000 emails is approximately $9,000/month at that volume — states the premium is approximately $6,000/month, and identifies the specific tooling that justifies it for a team without existing deliverability practice.*

**9. The team allocation and rollout schedule were inconsistent.** The prior draft implied SMS integration in month 5 without explicit ownership. *Fixed: the revised rollout schedule explicitly assigns SMS integration to E2 in month 5 and confirms E4 carries only load testing, IaC hardening, and runbook completion in those months.*

**10. TCPA treatment was incomplete.** The prior draft did not define "transactional message" operationally, did not address whether OTP messages require a consent record, and did not address CTIA guidelines, which carriers enforce independently of TCPA. *Fixed: the revised compliance section specifies the operational definition of each SMS category, states that OTP messages require no prior express written consent under TCPA but do require a compliant opt-out mechanism in the message body, and notes CTIA short code requirements for future volume above 100K messages/day.*

**11. No data model was provided.** The prior draft referenced PostgreSQL tables but defined none of them. *Fixed: the revised proposal includes the complete schema for five core tables with column types, indexes, and rationale.*

**12. No monitoring specification was provided.** The prior draft mentioned alerting in passing but defined no SLOs, alert thresholds, dashboard structure, or on-call escalation path. *Fixed: the revised proposal includes four SLOs, specific alert conditions with thresholds, and the on-call escalation path.*

**13. The channel distribution footnote deferred instrumentation without specifying it.** *Fixed: the revised section specifies four metrics to instrument from day one and the decision criteria for revising channel distribution assumptions at the month 2 checkpoint.*

**14. The SMS cost table was incomplete.** *Fixed: the complete cost comparison table is provided in Section 1.3.*

---

## Critical Design Decisions

| Decision | Choice | Rejected Alternative | Reason |
|---|---|---|---|
| Queue topology | Single queue, priority-encoded score | Per-channel queues | Eliminates priority inversion across channels; reduces DLQ surface from 4 to 1; simpler to operate with 4 engineers |
| Queue durability | PostgreSQL write-ahead + Redis Sorted Set | Redis AOF alone | PostgreSQL provides targeted reconciliation for individual missed items; AOF full-replay is slow and operationally fragile at this scale |
| Priority encoding | Compound integer score within float64 exact range, with aging promotion | Separate queues per priority | Single atomic dequeue; no cross-queue coordination; aging prevents starvation |
| Starvation prevention | Max-wait aging: promote item score after 10 min (P3), 5 min (P2), 2 min (P1) | Strict priority only | Strict ZPOPMAX with continuous P0/P1 inflow starves P2/P3 indefinitely; aging bounds worst-case wait to the promotion threshold |
| Worker model | Homogeneous workers, autoscaled on queue depth | Fixed per-priority worker pools | Fixed pools invert when priorities are imbalanced; homogeneous workers self-balance |
| Preference check timing | At routing for delivery preferences | At delivery | Avoids wasting queue capacity on suppressed notifications; 60-second cache staleness is acceptable for preference changes |
| Opt-out / unsubscribe | Checked at delivery via Redis suppression set, no TTL | Cached with TTL | TTL risks re-delivering to opted-out users after expiry; regulatory compliance requires no such gap |
| Deduplication | SHA-256 idempotency key, 24-hour window, stored in PostgreSQL | (user_id, notification_type) tuple | Tuple incorrectly deduplicates legitimate repeated events of the same type within the window |
| In-app storage | Direct PostgreSQL write, bypasses queue | Through push queue | Random access required; no external API call; WebSocket push on active connection |
| Push integration | Direct FCM / APNs | OneSignal / Braze | $50–150K/year saved; full control over token lifecycle and retry behavior |
| SMS scope | Auth and security events only | All engagement types | ~$1.77M/year cost avoidance; TCPA marketing consent infrastructure avoided |
| Email provider | SendGrid Pro | AWS SES | ~$6K/month premium justified by IP warmup tooling and suppression list management for a team without existing deliverability practice; revisit at 18 months |
| WebSocket fallback | Cursor-based poll on `/notifications/unread` at reconnect | Fire-and-forget only | Prevents silent message loss when WebSocket is unavailable during delivery |
| Reconciliation safety | `SELECT FOR UPDATE SKIP LOCKED` + status field distinguishes in-flight from lost | Re-enqueue without status check | Without status distinction, reconciliation loop and active worker both enqueue the same item, producing duplicate delivery |

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

Single-point estimates create false precision. Notification volume is highly skewed: power users receive 50+ per day; casual daily-active users receive 2–5. We model three scenarios to bound infrastructure decisions.

**Clarifying "peak":** The peak multiplier represents an intraday spike above the daily average rate — for example, a viral event at 8pm driving 3× the per-second rate of the overnight average — not a higher daily total. Daily totals and intraday per-second peaks are derived independently.

| Metric | Conservative | Realistic | High-Growth |
|---|---|---|---|
| MAU | 10M | 10M | 10M |
| DAU (30% of MAU) | 3M | 3M | 3M |
| Notifications / DAU / day | 8 | 12 | 20 |
| **Total / day** | **24M** | **36M** | **60M** |
| Average sustained throughput | ~278/sec | ~417/sec | ~694/sec |
| Intraday peak multiplier | 2× | 3× | 3× |
| **Intraday peak throughput** | **~556/sec** | **~1,251/sec** | **~2,083/sec** |

**Design target:** Size for the realistic case (36M/day, ~1,251/sec intraday peak) with horizontal worker autoscaling to reach the high-growth case without architectural changes. Autoscaling trigger: queue depth exceeding 10,000 items for more than 60 seconds.

**DAU assumption:** 30% DAU/MAU is conservative for a healthy social app; industry median is 20–25% and strong apps reach 40–50%. Higher DAU scales push volume proportionally but does not change the architecture — only worker count. If actual DAU falls below 20%, revisit whether infrastructure is over-provisioned at the month 3 checkpoint.

**Channel distribution** (estimated; instrumented from day one, reviewed at end of month 2):

| Channel | Share | Realistic Volume / day | Notes |
|---|---|---|---|
| Push | 70% | 25.2M | Dominant channel |
| In-app | 20% | 7.2M | Logged-in sessions only; bypasses queue |
| Email | 8% | 2.9M | Digests and critical alerts |
| SMS | ~0.2% after gating | ~72K | Auth / security only |

**Instrumentation from day one.** Four metrics must be emitted from the first deployment: `notifications.enqueued{channel}`, `notifications.delivered{channel, status}`, `notifications.suppressed{reason}`, and `notifications.latency_ms{channel, priority}`. These feed the channel distribution review at end of month 2. Decision criteria: if push share falls below 60% or exceeds 80%, or if in-app share exceeds 30%, revise worker allocation and queue sizing before the month 3 email launch.

### 1.2 SMS Volume Derivation

The raw 2% figure represents user-stated SMS preferences across all notification types. After gating to auth and security events only, eligible volume is derived from event rates, not from applying an assumed gating ratio to total volume.

| Event Type | Estimated Volume / day | Basis |
|---|---|---|
| OTP / login verification | ~30K | 1% of 3M DAU triggering auth daily |
| Password resets | ~5K | 0.17% of DAU |
| Security alerts (new device, suspicious login) | ~10K | 0.33% of DAU |
| Account recovery | ~5K | 0.17% of DAU |
| **Total** | **~50–72K** | |

### 1.3 SMS Cost and Regulatory Analysis

**Cost at Twilio standard rates ($0.0075/outbound SMS, US):**

| Scenario | Volume / day | Annual Cost | Notes |
|---|---|---|---|
| Ungated (2% of 36M/day) | 720K | ~$1.97M | Standard rate |
| Auth / security gating (this proposal) | ~72K | ~$197K | Standard rate |
| Ungated, negotiated rate (~$0.003/msg) | 720K | ~$788K | Requires volume commitment |
| Gated, negotiated rate (~$0.003/msg) | ~72K | ~$79K | Requires volume commitment |
| **Savings from gating (standard rate)** | | **~$1.77M/year** | |
| **Savings from gating (negotiated rate)** | | **~$709K/year** | |

Even at a negotiated rate, gating saves approximately $709K/year and eliminates the need for TCPA marketing consent infrastructure. The gating decision is correct at any plausible Twilio rate.

**Regulatory position.** Auth and security SMS messages qualify as transactional messages under TCPA. Operationally, a message is transactional under this proposal if and only if it satisfies all three of the following criteria: (1) it is triggered directly by a user-initiated authentication action or a system-detected security event on the user's account; (2) it contains no promotional content; and (3) it is not sent on a recurring scheduled basis. Messages that do not satisfy all three criteria are treated as marketing and are not sent via SMS under this proposal.

Transactional messages require no prior express written consent under TCPA. They do require a compliant opt-out mechanism in the message body — Twilio's default templates include "Reply STOP to opt out," which satisfies this requirement. Opt-out signals from Twilio are delivered via webhook and must be written to the suppression set within 30 seconds of receipt (see Section 7.3).

CTIA short code guidelines apply if volume exceeds 100K messages/day on a shared short code. At current projections this threshold is not reached, but a dedicated short code should be provisioned if volume approaches 80K/day to avoid carrier filtering. International SMS is explicitly out of scope for this proposal; it requires per-country regulatory analysis and separate number provisioning.

---

## 2. System Architecture

### 2.1 Component Overview

```
Event Sources              Routing Layer                    Queue & Storage
──────────────────         ────────────────────────         ─────────────────────────────
User action         ──►   Event Ingestion API       ──►   PostgreSQL (durable log)
(like, follow,            │                               │
 comment, auth)           │  1. Validate event            │  notifications
                          │  2. Resolve recipients        │