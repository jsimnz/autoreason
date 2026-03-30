# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status and How to Use This Document

**Under incident conditions:** Sections 1.3, 4.3, and 6.2 are self-contained. You do not need to read the full document to respond to an alert. The traffic response matrix (Section 1.3) and runbook CLI commands are written to be used at 3 AM without context.

**What this document does not claim:**
- FCM rate limits are not knowable in advance. The spike analysis uses a planning assumption, quantifies sensitivity across the full plausible range, and specifies a required pre-production load test with explicit decision thresholds for each outcome band. Staging load test results inform production planning but are not treated as production guarantees — Section 1.4 addresses this gap explicitly.
- FCM backoff behavior under sustained 429 responses is not publicly documented with contractual precision. The 32-second ceiling figure used in spike calculations is a planning assumption derived from exponential backoff conventions, not a sourced specification. Section 1.4 states the sensitivity of the P1 delay figures to this assumption and specifies what to measure during load testing.
- Post-spike drain rates are variable, not deterministic. Drain timelines are presented as ranges reflecting worker backoff desynchronization.
- DAU/MAU ratio and notifications-per-user are positively correlated, not independent. The sensitivity table reflects joint scenarios. Section 1.1 addresses the power-user pattern (low DAU/MAU × high per-user notification rate) separately because it stresses different subsystems than total volume alone.
- Deduplication uses an explicit delivered-ID set, not a bloom filter. False-positive rate is zero at the cost of bounded memory. The memory bound is quantified in Section 2.2: 128 bytes per ID, 10M retained IDs per channel, ~1.3 GB per channel at maximum retention. The tradeoff is stated there.

**Three decisions require named humans before production.** The deployment checklist gate mechanism is described in Section 7.1. Placeholder text in those three fields causes the automated pre-flight check to return a non-zero exit code, blocking the deployment pipeline. Named individuals are re-confirmed at each 30-day checkpoint; a departure triggers immediate role-based re-assignment per Section 7, not deferred resolution.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. Four core architectural decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script. The token bucket rate-limits P0/P1 consumption but does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation. The precise conditions under which starvation occurs despite the token bucket are specified in Section 3.2.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** Queue entries contain only the notification ID; workers fetch full payloads from PostgreSQL on dequeue. The processing Sorted Set tracks in-flight messages and is the crash recovery mechanism. If the worker instance hosting the recovery goroutine crashes and the container is destroyed, processing set entries for that instance may be orphaned. The mitigation is a cross-instance recovery sweep described fully in Section 2.1. PostgreSQL pool exhaustion risk is quantified with full arithmetic in Section 2.1. Worst-case P1 delay under coincident failure is **20–40 minutes under a standard spike, and 50–80 minutes if a DB issue outlasts the spike** — both figures are derived step-by-step in Section 1.4.

3. **Per-channel, per-priority worker pools** implemented as a single binary with a channel-type and priority flag, not 16 separate binaries. The traffic response matrix in Section 1.3 names specific worker configurations at each threshold. Deployment complexity from this approach is discussed in Section 3.3.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput. If pre-production load testing shows the actual FCM limit is below 2,000/sec, the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch. Section 1.4 specifies the conservative fallback operating mode during that period.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both metrics simultaneously. The sensitivity table reflects this: the low scenario uses both a low DAU/MAU ratio and a low notification rate; the high scenario uses both high values.

**The power-user pattern (low DAU/MAU × high per-user notification rate):** A social app with 15% DAU/MAU but a small cohort of highly active users generating 50+ notifications/day per user is a plausible and common pattern. Total daily volume in this scenario is below the plan figure, which means the volume-based sensitivity table does not flag it as a risk. However, it stresses three specific subsystems in ways total volume does not capture:

- **Per-user rate limiting:** A power user generating 50 notifications/day concentrates write load on specific Redis keys. The per-user rate limiter (Section 3.1) uses a sliding window per user ID; a 50-notification-per-day user hits the per-hour limit more frequently than the plan assumes. The per-user limit is set at 20 notifications/hour with a burst allowance of 5, not derived from average behavior.
- **Deduplication set sizes:** Deduplication is keyed per user, not per notification type. A power user generating many notifications in a short window produces a larger deduplication set for that user. The per-user deduplication window is 60 seconds; entries older than 60 seconds are expired. Memory impact is bounded by the 60-second window, not by per-user notification rate.
- **Recipient fanout:** If a power user's activity triggers notifications to many followers, fanout from a single event can produce thousands of queue entries. Fanout is capped at 10,000 recipients per event at the notification router. Events exceeding this cap are split into batched jobs processed over 5 minutes, not dropped.

These subsystem stresses are independent of whether total daily volume is above or below the plan figure. The power-user pattern is not covered by the low-engagement row in the sensitivity table; it is covered by the per-subsystem limits above.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The 3× peak multiplier assumes a two-hour evening window. This assumption must be revisited with real traffic data at the month-1 review.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — missed checkpoint default and what "provisioning" means:**

If month-1 traffic data is not reviewed by day 35, the engineering lead executes the following specific actions within 24 hours of the missed deadline:

1. Add 4 push worker instances (largest pool, most likely bottleneck) via the deployment configuration. Command: `kubectl scale deployment push-worker --replicas=12` (from 8 baseline).
2. Add 2 in-app write worker instances. Command: `kubectl scale deployment inapp-worker --replicas=6` (from 4 baseline).
3. Verify Redis instance is the pre-provisioned 80M/day capacity tier. If not, promote the pre-staged replica per the runbook in Section 6.2.
4. Record the action and timestamp in the runbook under "Month-1 default provisioning applied."

These actions are reversible. Step-down requires all three conditions from the original checkpoint: traffic review completed and documented, engineering lead sign-off, and 7 days of post-review data confirming volume below 45M/day. The engineering lead is the named decision owner for step-down. If the engineering lead is unavailable, the role-based fallback in Section 7 applies.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. Suppression of push when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model. The volume model accounts for worst-case write load.

**A viral spike will drive push and in-app saturation simultaneously** because they are triggered by the same upstream events. The traffic response matrix accounts for this correlated failure mode explicitly.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

Decisions are pre-specified to avoid reactive calls made under pressure. Workers are identified by their flag values (`--channel=push --priority=p1`), not by binary name, since all workers run the same binary.

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook. Both names must be filled in; placeholder text causes the automated pre-flight check to fail (Section 7.1). If a named individual is unavailable for more than 5 business days, Section 7's role-based fallback chain activates immediately.

**Redis resizing is not a same-day operation.** The default is to provision the initial Redis instance at 80M/day capacity. This decision is recorded in the deployment checklist and must be resolved before launch — it cannot be deferred until a traffic event occurs. See Section 1.3a for the cost-tradeoff resolution.

**Sharding pre-staging:** Queue keys use the format `queue:{channel}:{priority}:{shard}` from day one, where shard is `0` initially. Adding shards requires updating a configuration value and restarting workers — no schema migration, no code deployment. If the 80M/day threshold is crossed before month 3, the fallback is to scale workers vertically and accept higher Redis CPU until sharding configuration is ready.

**Dashboard CLI fallback:** If the per-channel queue depth dashboard is unresponsive for more than 2 minutes:

```bash
# Queue depths
redis-cli LLEN queue:push:p0:0
redis-cli LLEN queue:push:p1:0
redis-cli LLEN queue:push:p2:0
redis-cli LLEN queue:inapp:p1:0
redis-cli LLEN queue:email:p1:0

# Processing set size (in-flight messages)
redis-cli ZCARD processing:push
redis-cli ZCARD processing:inapp

# Worker count by type
kubectl get pods -l component=notification-worker \
  --field-selector=status.phase=Running | grep -c push
```

| Measured daily volume | Classification | Response — specific worker configurations | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|
| < 7.5M/day | Well below plan | Scale down push workers: `kubectl scale deployment notification-worker-push --replicas=4` | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | Moderately above plan | Check `queue:push:*` and `queue:inapp:*` first — these co-saturate. Scale push workers: `kubectl scale deployment notification-worker-push --replicas=16`. Scale inapp workers: `kubectl scale deployment notification-worker-inapp --replicas=8`. If email queue also rising, scale email workers: `kubectl scale deployment notification-worker-email --replicas=4`. Redis: if provisioned at 80M/day, no action needed. If not, promote pre-staged replica per Section 6.2. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus: if sharding is pre-staged (month 3+), update shard config (`NOTIFICATION_SHARD_COUNT=4`) and restart workers. If not yet pre-staged, scale workers vertically first. Engineering lead makes go/no-go on shard activation. | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email dispatch; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + named backup make go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**

- *Automated (auto-scaling, month 2 onward):* ~2–3 minutes total.
- *Manual, runbook available, dashboard loading normally:* ~8–10 minutes total.
- *Manual, runbook available, dashboard degraded (realistic incident scenario):* ~10–15 minutes total using CLI fallback above.
- *Manual, no runbook, first 30 days:* ~20–30 minutes. The runbook is a month-1 deliverable with a hard completion date in the deployment checklist.

### 1.3a Redis Provisioning Decision — Cost Tradeoff Resolution

The traffic response matrix for the 45M–80M/day band depends on whether Redis is pre-provisioned at 80M/day capacity. This cannot remain unresolved until a traffic event occurs. The decision must be recorded before production launch.

**Option A (default): Pre-provision at 80M/day capacity.** Cost premium at launch: approximately 2–3× the cost of a minimal instance sized for 45M/day. Benefit: the 45M–80M/day traffic response band requires no Redis action. The matrix is fully executable as written.

**Option B: Launch at 45M/day capacity with a pre-staged replica.** Lower launch cost. The 45M–80M/day traffic response band requires replica promotion, which takes 15–30 minutes on most managed providers. During that window, the system operates at degraded Redis capacity. The matrix entry for this band must be updated to reflect this window and who is responsible for executing the promotion.

**If Option B is chosen:** The matrix entry for 45M–80M/day must be annotated with: "Redis promotion required. Execute per Section 6.2. Expected duration: 15–30 min. Owner: [named individual from deployment checklist]. During promotion window: push and in-app workers will experience increased Redis latency. P0/P1 queues are served from replica reads; writes queue locally in worker memory for up to 60 seconds."

**Decision recorded in deployment checklist.** This field is not optional. If not filled in before launch, Option A is applied automatically.

### 1.4 Viral Spike Analysis

**FCM rate limit: stated as assumption, not fact.** FCM does not publish per-project rate limits with contractual precision. The 10,000/sec planning assumption is based on reported developer experience for large-scale applications. It may be wrong by a factor of 2–5 in either direction.

**FCM backoff model: stated as assumption, not sourced specification.** The 32-second backoff ceiling (5 doublings from 1 second: 1→2→4→8→16→32) is derived from standard exponential backoff conventions. FCM's actual retry behavior under sustained 429 responses is not publicly documented with this precision. The P1 delay figures are sensitive to this assumption. Sensitivity is quantified below.

**Pre-production load test requirement:** Load test push dispatch against a staging FC