# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Document Status and How to Use This Document

**Under incident conditions:** Sections 1.3, 4.3, and 6.2 are self-contained. You do not need to read the full document to respond to an alert. The traffic response matrix (Section 1.3) and runbook CLI commands are written to be used at 3 AM without context.

**What this document does not claim:**
- FCM rate limits are not knowable in advance. The spike analysis (Section 1.4) uses a planning assumption, quantifies sensitivity across the full plausible range, and specifies a required pre-production load test with explicit decision thresholds for each outcome band. Staging load test results inform production planning but are not treated as production guarantees.
- FCM backoff behavior under sustained 429 responses is not publicly documented with contractual precision. The 32-second ceiling figure used in spike calculations is a planning assumption derived from exponential backoff conventions, not a sourced specification. Section 1.4 states the sensitivity of the P1 delay figures to this assumption and specifies what to measure during load testing.
- Post-spike drain rates are variable, not deterministic. Drain timelines are presented as ranges reflecting worker backoff desynchronization.
- DAU/MAU ratio and notifications-per-user are positively correlated, not independent. The sensitivity table reflects joint scenarios. Section 1.1 addresses the power-user pattern separately.
- Deduplication uses an explicit delivered-ID set, not a bloom filter. False-positive rate is zero at the cost of bounded memory. The memory bound, cluster-total scope, and eviction behavior are specified in Section 2.2.

**Three decisions require named humans before production.** Those three decisions are:

1. **Engineering lead and named backup** for the traffic response matrix and deployment authority (Section 1.3).
2. **Redis provisioning option selection** — Option A or Option B — recorded in the deployment checklist (Section 1.3a).
3. **On-call rotation owner** responsible for the runbook and the month-1 checkpoint review (Section 7.1).

The deployment checklist gate mechanism is described in Section 7.1. Placeholder text in any of these three fields causes the automated pre-flight check to return a non-zero exit code, blocking the deployment pipeline. Named individuals are re-confirmed at each 30-day checkpoint. A departure triggers immediate role-based re-assignment per Section 7.2.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. Four core architectural decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses a token bucket that reserves minimum throughput for lower-priority queues, not one that rate-limits higher-priority queues. The mechanism and the precise conditions under which P2/P3 starvation remains possible despite it are specified in Section 3.2.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** Queue entries contain only the notification ID; workers fetch full payloads from PostgreSQL on dequeue. The processing Sorted Set tracks in-flight messages. If a worker container is destroyed, its processing set entries may be orphaned. The consequence is delayed redelivery, not silent loss — the recovery sweep in Section 2.1 reclaims orphaned entries within a bounded window. The worst-case outcome under coincident failure is duplication, not loss, because the system is designed for at-least-once delivery with deduplication at the consumer. PostgreSQL pool exhaustion arithmetic is in Section 2.1. Worst-case P1 delay under coincident failure: **20–40 minutes under a standard spike, 50–80 minutes if a DB issue outlasts the spike** — both derived step-by-step in Section 1.4.

3. **Per-channel, per-priority worker pools** implemented as a single binary with channel-type and priority flags, not 16 separate binaries. The traffic response matrix in Section 1.3 names specific worker configurations at each threshold. Deployment complexity from this approach is discussed in Section 3.3.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput. If pre-production load testing shows the actual FCM limit is below 2,000/sec, the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch. Section 1.4 specifies the conservative fallback operating mode during that period.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated. The sensitivity table reflects this: the low scenario uses both a low DAU/MAU ratio and a low notification rate; the high scenario uses both high values.

**The power-user pattern (low DAU/MAU × high per-user notification rate):** A social app with 15% DAU/MAU but a small cohort of highly active users generating 50+ notifications/day per user is a plausible and common pattern. Total daily volume in this scenario is below the plan figure, which means the volume-based sensitivity table does not flag it as a risk. However, it stresses three specific subsystems:

- **Per-user rate limiting:** A power user generating 50 notifications/day concentrates write load on specific Redis keys. The per-user rate limiter (Section 3.1) uses a sliding window per user ID; the per-user limit is set at 20 notifications/hour with a burst allowance of 5.
- **Deduplication set sizes:** Deduplication is keyed per user. The per-user deduplication window is 60 seconds; entries older than 60 seconds are expired. Memory impact is bounded by the 60-second window, not by per-user notification rate.
- **Recipient fanout:** If a power user's activity triggers notifications to many followers, fanout from a single event can produce thousands of queue entries. Fanout is capped at 10,000 recipients per event at the notification router. Concurrent fanout events and queue depth interaction are addressed in Section 1.5.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The 3× peak multiplier assumes a two-hour evening window. This assumption must be revisited with real traffic data at the month-1 review. **Intraday distribution matters independently of daily totals** — a day with 45M total notifications but a 5× peak in one hour would appear "on plan" in the daily volume column of the traffic response matrix while actually requiring the "significantly above plan" response. Section 1.3 addresses this with a parallel per-second threshold column.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — missed checkpoint default and what "provisioning" means:**

If month-1 traffic data is not reviewed by day 35, the on-call rotation owner (named in Section 7.1) executes the following specific actions within 24 hours of the missed deadline:

1. Add 4 push worker instances: `kubectl scale deployment push-worker --replicas=12` (from 8 baseline).
2. Add 2 in-app write worker instances: `kubectl scale deployment inapp-worker --replicas=6` (from 4 baseline).
3. Verify Redis instance is the pre-provisioned 80M/day capacity tier. If not, promote the pre-staged replica per Section 6.2.
4. Record the action and timestamp in the runbook log under "Month-1 default provisioning applied."

**Runbook dependency:** The runbook is a hard prerequisite for this procedure, not a month-1 deliverable. The runbook must exist before production launch. The deployment checklist gate (Section 7.1) blocks launch if the runbook location field is empty. If the month-1 checkpoint is missed, the runbook already exists and step 4 has a location to log against.

These actions are reversible. Step-down requires: traffic review completed and documented, engineering lead sign-off, and 7 days of post-review data confirming volume below 45M/day. The engineering lead is the named decision owner for step-down. If the engineering lead is unavailable, the role-based fallback in Section 7.2 applies.

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

**The matrix uses two threshold columns: daily volume and instantaneous per-second rate.** A day can be "on plan" in total volume while exceeding the per-second threshold during a peak hour. Both columns must be checked. If they disagree, the higher response level applies.

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook and the deployment checklist. Both names must be filled in; placeholder text causes the automated pre-flight check to fail (Section 7.1). If a named individual is unavailable for more than 5 business days, Section 7.2's role-based fallback chain activates immediately.

**Redis resizing is not a same-day operation.** The default is to provision the initial Redis instance at 80M/day capacity. This decision is recorded in the deployment checklist and must be resolved before launch. See Section 1.3a for the cost-tradeoff resolution.

**Sharding pre-staging:** Queue keys use the format `queue:{channel}:{priority}:{shard}` from day one, where shard is `0` initially. Adding shards requires updating a configuration value and restarting workers — no schema migration, no code deployment. If the 80M/day threshold is crossed before month 3, the fallback is to scale workers vertically and accept higher Redis CPU until sharding configuration is ready.

**Auto-scaling implementation (month 2 target):** Auto-scaling is not available at launch. The month-1 response time estimate is manual-only. Month-2 auto-scaling is implemented as a Kubernetes HorizontalPodAutoscaler triggered on a custom metric: `notification_queue_depth_p1` exported via Prometheus. Trigger threshold: queue depth > 5,000 for > 2 minutes. Scale-up step: 2 replicas per interval, max 24 replicas for push workers. Scale-down requires queue depth < 1,000 for 10 minutes. This configuration is a deliverable in the month-2 sprint. Until it is deployed and validated, the manual response times apply.

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

| Measured daily volume | Instantaneous rate | Classification | Response — specific worker configurations | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|---|
| < 7.5M/day | < 260/sec | Well below plan | Scale down push workers: `kubectl scale deployment notification-worker-push --replicas=4` | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | 260–1,575/sec | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | 1,575–2,800/sec | Moderately above plan | Check `queue:push:*` and `queue:inapp:*` first — these co-saturate. Scale push workers: `kubectl scale deployment notification-worker-push --replicas=16`. Scale inapp workers: `kubectl scale deployment notification-worker-inapp --replicas=8`. If email queue also rising, scale email workers: `kubectl scale deployment notification-worker-email --replicas=4`. Redis: if provisioned at 80M/day (Option A), no action needed. If Option B, promote pre-staged replica per Section 6.2; expect 15–30 min degraded window. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | 2,800–7,900/sec | Significantly above plan | Above, plus: if sharding is pre-staged (month 3+), update shard config (`NOTIFICATION_SHARD_COUNT=4`) and restart workers. If not yet pre-staged, scale workers vertically first. Engineering lead makes go/no-go on shard activation. | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | > 7,900/sec | Severely above plan | Defer SMS and email dispatch; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + named backup make go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**

- *Automated (auto-scaling, month 2 onward, after HPA deployment validated):* ~2–3 minutes total.
- *Manual, runbook available, dashboard loading normally:* ~8–10 minutes total.
- *Manual, runbook available, dashboard degraded (realistic incident scenario):* ~10–15 minutes total using CLI fallback above.
- *Manual, no runbook:* This state cannot occur in production. The runbook is a launch prerequisite, not a month-1 deliverable. See Section 7.1.

### 1.3a Redis Provisioning Decision — Cost Tradeoff Resolution

The traffic response matrix for the 45M–80M/day band depends on whether Redis is pre-provisioned at 80M/day capacity. This cannot remain unresolved until a traffic event occurs. The decision must be recorded before production launch.

**Option A (default): Pre-provision at 80M/day capacity.** Cost premium at launch: approximately 2–3× the cost of a minimal instance sized for 45M/day. Benefit: the 45M–80M/day traffic response band requires no Redis action. The matrix is fully executable as written.

**Option B: Launch at 45M/day capacity with a pre-staged replica.** Lower launch cost. The 45M–80M/day traffic response band requires replica promotion, which takes 15–30 minutes on most managed providers. During that window, the