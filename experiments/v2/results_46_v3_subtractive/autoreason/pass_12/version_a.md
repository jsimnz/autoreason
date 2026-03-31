# Notification System Design Proposal — Revision 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses eleven structural problems identified in the prior version. The most significant corrections are:

**Math corrections:** The 27.2M total routed events figure was wrong because it double-counted in-app users who also have push or email enabled. The corrected model uses additive channel expansion with overlap accounted for. The Poisson batching calculation used DAU as the denominator incorrectly; the corrected calculation uses the full opted-in user base and derives a daily active fraction explicitly.

**Honest architectural reassessment:** The batching window produces a 1.05× volume reduction at current scale. This is nearly zero. The document previously noted this without addressing it. This revision makes an explicit decision: the aggregation window is retained for latency control and digest grouping, not volume reduction, and its complexity is evaluated against that narrower justification. The conclusion is that it remains worth building, but for different reasons than originally stated, and with a simpler implementation path.

**Failure modes now fully specified:** The recovery job specification is complete, including its own failure modes. The catch-all partition's silent correctness problem is addressed with a mandatory remediation SLA and monitoring that treats catch-all traffic as a paging incident, not background noise. The suppression cache durability gap and its TCPA implications are analyzed with an explicit decision about the compliance boundary.

**Design coherence fixes:** Priority enforcement via sorted set score is replaced with per-priority queues with a clear dequeuing model. The WebSocket delivery path is fully specified. The transaction-to-Redis gap is closed. The configuration recalculation job now has an enforcement mechanism, not just a recommendation output.

**What we are deliberately not building:** ML send-time optimization, A/B testing infrastructure, per-user engagement scoring, real-time analytics dashboards.

**What we are explicitly accepting as limitations, with measurement:** Duplicate delivery is possible in crash-recovery scenarios. The target is <0.01% of delivered events. The measurement mechanism is specified in Section 5. In-app delivery to offline clients is best-effort; the reconnect protocol is specified in Section 3.4. TCPA compliance has a bounded durability gap on the suppression cache; the gap, its probability, and the operational response are specified in Section 2.6.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

**Event generation:**

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio, typical social apps |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |
| Fanout multiplier | 1.2 | Direct interactions; excludes viral fanout |
| Raw recipient-notification events/day | ~18M | 15M × 1.2 |
| Global opt-out rate | 20% | Conservative; design for this floor |
| Routed notification events/day | ~14.4M | 18M × 0.80 |

The 14.4M figure is the count of recipient-notification events after global opt-out filtering. This is the input to channel expansion. It is not the total delivery event count.

### 1.2 Channel Distribution — Corrected Model

**The prior version's first error** (v1): treating channel percentages as a partition of users.
**The prior version's second error** (v2, introduced while fixing v1): summing per-channel event counts as if they were independent populations, producing a total (27.2M) that double-counted users who appear in multiple channels.

**Correct model:** Channel expansion is multiplicative per user, not additive across independent populations. A user with push and email enabled generates two delivery events from one routed notification event. The total delivery events equals the sum across users of their enabled channel count. We model this with independent opt-in rates and compute expected delivery events per user.

**Channel opt-in rates** (among the 80% of users who have not globally opted out):

| Channel | Opt-In Rate | Notes |
|---------|------------|-------|
| In-app | 100% | Baseline; cannot be disabled at channel level |
| Push | 65% | Of non-opted-out users |
| Email | 20% | Of non-opted-out users |
| SMS | <0.01% | Opt-in required; negligible population |

**Expected delivery events per routed notification event:**

Each routed event generates delivery events for each channel the recipient has enabled. Expected channels per user = 1 (in-app, always) + 0.65 (push) + 0.20 (email) + ~0 (SMS) = 1.85 channels per user on average.

Total delivery events/day = 14.4M × 1.85 = **~26.6M delivery events/day**.

This is the correct total. It is higher than 14.4M because users receive notifications across multiple channels, but it does not double-count users — it counts delivery attempts, which is the right unit for worker sizing.

**Per-channel delivery event volumes:**

| Channel | Calculation | Delivery Events/Day | Peak (3×avg)/sec |
|---------|------------|--------------------|--------------------|
| In-app | 14.4M × 1.00 | 14.4M | ~500 |
| Push | 14.4M × 0.65 | 9.4M | ~325 |
| Email (pre-batch) | 14.4M × 0.20 | 2.9M | ~100 |
| SMS | 14.4M × 0.0001 | ~1,500 | negligible |

**In-app clarification:** In-app events are generated for all non-opted-out users regardless of other channel preferences. In-app is the baseline product experience. A user who has push and email enabled receives three delivery events per routed notification: one in-app, one push, one email. The 14.4M in-app events and 9.4M push events share the same 9.4M users — this is intentional and not a double-count, because they are distinct delivery attempts to distinct channels.

**Worker sizing uses per-channel delivery event volumes. These numbers are the correct inputs.**

### 1.3 Email Batching Math — Corrected

**The prior version's error:** Used DAU (3M) as the denominator when computing events per opted-in user, then applied the result to the full opted-in user base without reconciling the two populations.

**Correct approach:** Derive the per-user daily event rate from the full opted-in user base, then apply a daily active fraction to get the effective rate for active users.

```
Email opted-in users (of 10M MAU):
  10M × 0.80 (non-opted-out) × 0.20 (email opt-in) = 1.6M opted-in users

Email opted-in DAU:
  1.6M × 0.30 (DAU/MAU) = 480K email-opted-in DAU

Email delivery events/day (from above): 2.9M
Events distributed across opted-in DAU (active users receive events):
  2.9M ÷ 480K ≈ 6.0 events/active-opted-in-user/day
```

Why use DAU in the denominator here: notifications are generated by social actions, which only active users perform and receive. An opted-in user who is not active on a given day generates and receives no notification events that day. The per-user event rate is therefore correctly computed over the active opted-in population, not the full opted-in population.

**Poisson batching model (30-minute aggregation window):**

```
λ = 6.0 events/active-opted-in-user/day
  = 6.0 / 48 = 0.125 events per 30-minute window

Expected emails sent per active user per day:
  = 48 × P(at least one event in window)
  = 48 × (1 - e^(-0.125))
  = 48 × 0.1175
  ≈ 5.64 emails/active-user/day

Reduction factor: 6.0 / 5.64 ≈ 1.06×
Delivered emails/day: 480K × 5.64 ≈ 2.71M
Peak delivered email rate: 2.71M ÷ 86,400 × 3 ≈ 94/sec
```

**The 1.06× reduction factor means the batching window reduces email volume by approximately 6%.** This is nearly zero. The prior version acknowledged this without addressing it. This version makes an explicit decision.

**Decision: Retain the aggregation window, but justify it correctly.**

The aggregation window is not justified by volume reduction at current scale. It is justified by two narrower reasons:

1. **Latency control for digest grouping.** Without an aggregation window, a user who receives five likes in 30 seconds gets five separate emails. With a window, they get one email listing all five. This is a product quality requirement, not a throughput optimization. The window size (30 minutes) is a product decision, not an engineering one.

2. **Headroom for scale.** At 10× current scale (100M MAU), λ increases to ~1.25 events/window, and the reduction factor becomes 1 - e^(-1.25) ≈ 0.71, meaning the window reduces volume by 29%. The batching infrastructure built now becomes load-bearing later.

**What we are not claiming:** Volume reduction at current scale. The complexity of the aggregation window is not justified by current throughput numbers. Teams evaluating whether to build this should weigh the product quality benefit (digest grouping) against the implementation complexity, not the throughput benefit.

**The batching window is a configurable product parameter.** The value (30 minutes) is stored in a configuration service. When product changes this parameter, a configuration-change event triggers a recalculation job that outputs revised worker count recommendations and updated alert thresholds. The recalculation job output is not automatically applied — it produces a recommendation that requires human approval. To prevent silent drift, an alert fires if the current worker count deviates from the recommended count by more than 20% for more than 24 hours without an acknowledged override. E4 owns this alert. E1 owns the recalculation job. The override acknowledgment is a manual step that requires a comment explaining why the deviation is intentional.

### 1.4 SMS Cost

At $0.0075/message, 1,500/day = ~$340/month. Negligible. Does not constrain design.

### 1.5 Team Allocation

**Resolved ownership conflicts from prior version:**

The prior version had two conflicts: E1 and E4 both claimed recovery job threshold calibration; and E3's feedback processor depended on E2's token invalidity stream with E4's consumer group configuration creating an ambiguous three-engineer dependency. These are resolved by separating design ownership from operational ownership, and by making the E2→E3 dependency explicit with no intermediate owner.

| Engineer | Primary Responsibility | Explicit Ownership |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, priority scoring, batching logic, partition pre-creation job | Recovery job: staleness threshold definition, scheduling, implementation. Recalculation job for batching window changes. Priority queue schema. |
| E2 | Channel integrations (APNs, FCM, SES, Twilio), token lifecycle | Token invalidity detection; publishes structured events to `token.invalidated` stream. Does not own downstream consumers. |
| E3 | Preference management, user-facing API, suppression, TCPA compliance | Feedback processor (consumes `token.invalidated` stream, configures and operates consumer group). Suppression cache write path. Preference API opt-out synchronous cache write. |
| E4 | Reliability, monitoring, failure handling, DevOps, WebSocket infrastructure | Recovery job: runbook, operational response, threshold-breach alerting. Partition pre-creation monitoring. Archival job. Worker pool autoscaling. WebSocket server infrastructure. Catch-all partition migration runbook. Duplicate rate monitoring. |

**Bus factor on TCPA compliance path:** E3 owns every component in the compliance chain. This is a bus-factor-one risk. Mitigation: E1 is designated secondary owner of the suppression cache write path and is required to review all PRs touching suppression logic. The TCPA compliance runbook (owned by E3, reviewed by E1) is stored in the team wiki and reviewed quarterly. This does not eliminate the bus factor but makes it explicit and partially mitigated.

**Event type classification table:** Owned by E1. Modifications require a PR with E1 approval. The enforcement mechanism is a CI check that validates the classification table schema and rejects PRs that add event types without a priority assignment. The table lives in the application repository as a versioned configuration file, not in the database, so the PR requirement is enforced by the repository's required-reviewer policy, not by process alone.

---

## 2. System Architecture

### 2.1 Priority Classification and Queue Model

**Priority enforcement mechanism — corrected from prior version.**

The prior version stated "priority enforced via sorted set score" with score = Unix timestamp in milliseconds. This is incorrect: a P3 bulk notification enqueued at time T has score T, and a P0 critical notification enqueued at T+1ms has score T+1ms. The P3 is dequeued first because it has a lower (earlier) score. Timestamp-as-score does not enforce priority.

**Correct model: per-priority queues with strict priority dequeuing.**

There are four Redis sorted sets per channel, one per priority level. Workers dequeue from queues in strict priority order: always drain P0 before touching P1, always drain P1 before touching P2, always drain P2 before touching P3. Within a single priority queue, score is Unix timestamp in milliseconds (FIFO within priority).

```
Push channel:
  push:p0  (Redis sorted set, score = enqueue timestamp ms)
  push:p1
  push:p2
  push:p3

Email channel:
  email:p0
  email:p1
  email:p2
  email:p3

SMS channel:
  sms:p0
  sms:p1   (in practice, nearly empty)
  sms:p2
  sms:p3

In-app: handled via Redis Streams, not sorted sets (see Section 3.4)
```

**Dequeuing logic (pseudo-code):**

```python
def dequeue_next(channel: str) -> Optional[EventId]:
    for priority in ['p0', 'p1', 'p2', 'p3']:
        queue_key = f"{channel}:{priority}"
        # ZPOPMIN returns lowest score (earliest timestamp) from queue
        result = redis.zpopmin(queue_key, count=1)
        if result:
            return result[0]
    return None  # All queues empty
```

**Starvation risk:** Strict priority dequeuing means P3 is never processed while P0/P1/P2 queues are non-empty. At current scale, P0 and P1 queues drain quickly (target latencies of 2s and 30s respectively). P3 starvation would only occur under sustained overload conditions where P0/P1 queues never drain. We accept this: P3 (digest summaries, promotional) should be starved during overload. If P3 starvation exceeds 2 hours, E4's monitoring alerts. The operational response is to add worker capacity, not to artificially advance P3 items.

**P0 SMS fast path:** P0 SMS events bypass the aggregation window check and are enqueued directly to `sms:p0`. They do not bypass suppression checks. The suppression check for all SMS reads from the 30-second TTL cache (see Section 2.6).

| Priority | Label | Event Types | Target Delivery Latency |
|----------|-------|-------------|------------------------|
| P0 | Critical | Auth codes, account compromise alerts, payment failures | <2 seconds |
| P1 | High | Direct messages, mentions, replies to your content | <30 seconds |
| P2 | Normal | Likes, new followers, comments on your posts | <5 minutes |
| P3 | Bulk | Digest summaries, weekly recaps, promotional | <1 hour |

**New event types:** Require a PR modifying the classification configuration file. The CI check rejects unclassified event types. The router rejects unclassified events at runtime with HTTP 422 and a logged error. There is no silent defaulting.

### 2.2 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
  - Assigns event_id (UUID v7, time-ordered)
  - Validates event type; rejects unknowns (HTTP 422)
  - Single DB