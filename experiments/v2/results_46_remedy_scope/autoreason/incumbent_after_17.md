# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status and How to Use This Document

**Under incident conditions:** Sections 1.3, 4.3, and 6.2 are self-contained. You do not need to read the full document to respond to an alert. The traffic response matrix (Section 1.3) and runbook CLI commands are written to be used at 3 AM without context.

**What this document does not claim:**
- FCM rate limits are not knowable in advance. The spike analysis uses a planning assumption, quantifies sensitivity across the full plausible range, and specifies a required pre-production load test with explicit decision thresholds for each outcome band.
- Post-spike drain rates are variable, not deterministic. Drain timelines are presented as ranges reflecting worker backoff desynchronization.
- DAU/MAU ratio and notifications-per-user are positively correlated, not independent. The sensitivity table reflects joint scenarios; treating them as independent would understate joint variance.
- Deduplication uses an explicit delivered-ID set, not a bloom filter. False-positive rate is zero at the cost of bounded memory. The tradeoff is stated in Section 2.2.

**Three decisions require named humans before production.** Placeholder text is not acceptable and blocks the deployment checklist gate (Section 7.1). Not recording a decision is treated the same as recording the conservative option. Named individuals are re-confirmed at each 30-day checkpoint; a departure triggers immediate role-based re-assignment per Section 7, not deferred resolution.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. Four core architectural decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script. The token bucket rate-limits P0/P1 consumption — it does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation. The conditions under which starvation occurs despite the token bucket are specified in Section 3.2.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** Queue entries contain only the notification ID; workers fetch full payloads from PostgreSQL on dequeue. The processing Sorted Set tracks in-flight messages and is the crash recovery mechanism. If the worker instance hosting the recovery goroutine crashes and the container is destroyed, processing set entries for that instance may be orphaned. The mitigation is a cross-instance recovery sweep in Section 2.1. PostgreSQL pool exhaustion risk is quantified with full arithmetic in Section 2.1. Worst-case P1 delay under coincident failure is **20–40 minutes under a standard spike, and 50–80 minutes if a DB issue outlasts the spike** — both figures are derived step-by-step in Section 1.4.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. The traffic response matrix in Section 1.3 names specific worker types at each threshold.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput. If pre-production load testing shows the actual FCM limit is below 2,000/sec, the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch. Section 1.4 specifies the conservative fallback operating mode during that period.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%. Facebook historically ~65%; newer apps often 15–25%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both metrics simultaneously. The sensitivity table reflects this: the low scenario uses both a low DAU/MAU ratio and a low notification rate; the high scenario uses both high values. Cross-scenarios (high DAU/MAU × low notification rate) are architecturally favorable — lower notification volume at any DAU level reduces system load, producing an over-provisioned but reliable system. This is a cost problem, not a reliability problem. The sensitivity table is used to size for risk; favorable cross-scenarios do not affect the risk envelope. The unfavorable cross-scenario (low DAU/MAU × high notification rate) at 10M MAU produces volumes below the plan figure and is covered by the low-engagement row. These omissions are modeling choices, not oversights.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The extreme scenario is included because the architecture must degrade predictably under viral growth, not silently fail. The traffic response matrix in Section 1.3 covers through ~225M/day.

The 3× peak multiplier assumes a two-hour evening window. If the app has strong international distribution, the ratio may be lower (rolling timezone distribution) or higher (synchronized global event). This assumption must be revisited with real traffic data at the month-1 review.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — missed checkpoint default and exit criteria:**

If month-1 traffic data is not reviewed by day 35, the engineering lead defaults to provisioning for the high engagement scenario (100M/day) until the review occurs. This elevated provisioning persists until all three of the following are true: (a) the traffic review is completed and documented in the runbook; (b) the engineering lead or named backup signs off on the step-down; and (c) 7 days of post-review traffic data confirm actual volume is below the 45M/day plan figure. Meeting only one or two conditions does not trigger automatic step-down. The runbook records the date each condition was met.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record and queues a push notification. Suppression of push when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model. The volume model accounts for worst-case write load.

**A viral spike will drive push and in-app saturation simultaneously** because they are triggered by the same upstream events. The traffic response matrix accounts for this correlated failure mode explicitly.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

Decisions are pre-specified to avoid reactive calls made under pressure. Workers are specialized by channel type (Section 3), so the matrix names specific worker types at each threshold.

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook. Both names are filled in before production; placeholder text blocks the deployment checklist gate. If a named individual is unavailable for more than 5 business days, Section 7's role-based fallback chain activates immediately.

**Redis resizing is not a same-day operation.** In most managed cloud environments (ElastiCache, Memorystore, Upstash), resizing requires pre-provisioned replica promotion or instance replacement with a brief failover. The default is to provision the initial Redis instance at 80M/day capacity, accepting the cost of over-provisioning at launch. If this is not acceptable for cost reasons, a larger replica must be pre-provisioned and promotion scripted before production launch. This decision is recorded in the deployment checklist.

**Sharding pre-staging (for the 80M–225M/day band):** The traffic response matrix specifies namespace sharding by user ID range for the 80M–225M/day band. This cannot be executed as an incident response without pre-staging. By month 3, queue keys must be named `queue:{channel}:{priority}:{shard}` from the start, where `shard` is `0` for all traffic initially. Adding shards requires updating a configuration value and restarting workers — no schema migration, no code deployment. If the 80M/day threshold is crossed before month 3, the fallback is to scale worker instances vertically and accept higher Redis CPU until the sharding configuration is ready. The matrix entry for this band includes this fallback explicitly.

**Dashboard reliability during incidents:** The per-channel queue depth dashboard may be slow or stale during the same Redis pressure event causing the alert. CLI fallback if the dashboard is unresponsive for more than 2 minutes:

```bash
# Queue depths
redis-cli LLEN queue:push:p0
redis-cli LLEN queue:push:p1
redis-cli LLEN queue:push:p2
redis-cli LLEN queue:inapp:p1
redis-cli LLEN queue:email:p1

# Processing set size (in-flight messages)
redis-cli ZCARD processing:push
redis-cli ZCARD processing:inapp
```

The engineer does not need to reason from first principles at 3 AM. This CLI fallback is a runbook requirement, not a suggestion.

| Measured daily volume | Classification | Response — specific worker types | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|
| < 7.5M/day | Well below plan | Scale down push worker instances (largest pool) | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | Moderately above plan | Check `queue:push` and `queue:inapp` first — these co-saturate. Add push workers and in-app write workers. If email queue also rising, add email workers. Redis: use pre-provisioned replica promotion, or accept 15–30 min unavailability. If initial instance was provisioned at 80M/day headroom, no Redis action needed. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus: if sharding is pre-staged (month 3+), update shard config and restart workers (~30 min). If not yet pre-staged, scale workers vertically and accept higher Redis CPU until pre-staging is complete. Engineering lead makes go/no-go on shard activation. | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email dispatch; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + named backup make go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**

*Automated (auto-scaling, month 2 onward):* ~2–3 minutes total.

*Manual, runbook available, dashboard loading normally:* ~8–10 minutes total.

*Manual, runbook available, dashboard degraded (realistic incident scenario):* ~10–15 minutes total using CLI fallback above.

*Manual, no runbook, first 30 days:* ~20–30 minutes. This is the risk window. The runbook is a month-1 deliverable with a hard completion date recorded in the deployment checklist. If not complete by day 30, the engineering lead is notified and the system operates under this assumption until complete.

### 1.4 Viral Spike Analysis

**The FCM rate limit cannot be confirmed in advance.** FCM does not publish per-project rate limits with contractual precision, and load testing a staging project produces useful signal but not a production guarantee.

**Pre-production action:** Load test push dispatch against a staging project at 2×, 5×, and 10× planned peak. Record the rate at which 429 responses begin. The observed rate determines which decision band applies.

**Decision bands based on observed load test rate:**

| Observed limit | Decision |
|---|---|
| < 500/sec | Stop. Architecture is invalid for push at any meaningful scale. Re-evaluate whether push is the right primary channel before any further work. |
| 500–2,000/sec | P1 protection claims are materially wrong. Enter conservative fallback mode (defined below). Re-evaluation required before launch. Maximum re-evaluation window: 2 weeks. No decision at 2 weeks = no-launch. |
| 2,000–5,000/sec | P1 delays during a 20× spike will be 30–90 minutes, not 15–25 minutes. Architecture is usable but the spike figures in this document are wrong for this range. Update the spike table with the observed limit before launch. No architecture re-evaluation required, but figures must be corrected. |
| 5,000–10,000/sec | P1 delays during a 20× spike are 15–30 minutes. Architecture proceeds as designed. Use the observed figure, not the 10,000/sec planning assumption, in the spike table. |
| > 10,000/sec | Architecture proceeds as designed. Planning assumption is conservative. |

**Conservative fallback mode (triggered when observed limit is 500–2,000/sec):**

- P0 (security/auth) dispatched immediately.
- P1 (direct messages, critical alerts) dispatched at the observed rate limit with no other traffic competing.
- P2 and P3 queued but not dispatched.
- Queue bounds: P2 queue max depth is 500,000 entries (~16 hours of P2 volume at plan rate). P3 queue max depth is 200,000 entries. When a queue reaches its bound, new entries are dropped and a counter is incremented. A non-zero P2 or P3 drop counter requires engineering review within 24 hours.
- Users do not receive notification that their P2/P3 notifications are delayed. This is a product decision recorded here so the product team is aware. If the re-evaluation window extends beyond 48 hours, the product team must be notified.

**Spike analysis — arithmetic:**

Planning assumption: FCM limit 10,000/sec. 20× demand spike producing ~21,000/sec push demand.

Accumulation during a 10-minute spike:
- FCM can dispatch: 10,000/sec
- Demand: ~21,000/sec
- Net accumulation: ~11,000/sec
- Over 10 minutes (600 seconds): 11,000 × 600 = **6,600,000 messages queued**

**Post-spike drain — backoff desynchronization:**

During a sustained spike, individual worker instances accumulate FCM backoff state independently. FCM's documented backoff under sustained 429 responses reaches approximately 32 seconds between retry attempts (5 doublings from a 1-second base). Different workers reach this ceiling at different times depending on when they started retrying. The fleet does not reset uniformly.

- **0–32 seconds post-spike:** Workers are mid-backoff at varying positions. Effective dispatch rate: ~30–70% of 10,000/sec = 3,000–7,000/sec net.
- **32–90 seconds post-spike:** Workers progressively reset backoff. Effective dispatch rate ramps toward ~80% of capacity.
- **90 seconds onward:** Full dispatch capacity, ~10,000/sec net.

**P1 delay derivation — step-by-step:**

Drain rate after 90s: 10,000/sec net. Queued messages: 6,600,000.

During the first 90 seconds post-spike:
- Low end (30% capacity): 90 × 3,000 = 270,000 messages drained. Remaining: 6,330,000.
- High end (70% capacity): 90 