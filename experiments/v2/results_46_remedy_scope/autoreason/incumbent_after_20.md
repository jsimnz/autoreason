# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3**
- Traffic spike response → **Section 1.3** (matrix is self-contained; CLI commands are embedded)
- Redis failover → **Section 6.2**
- Dashboard unresponsive → CLI fallback is in Section 1.3, no cross-reference required

**Three decisions require named humans before production.** Placeholder text in any of these fields causes the automated pre-flight check to return a non-zero exit code, blocking the deployment pipeline:

1. **Engineering lead and named backup** for deployment authority (deployment checklist, Section 7.1)
2. **Redis provisioning option** — Option A or Option B — resolved in Section 1.3a and recorded in deployment checklist
3. **On-call rotation owner** responsible for the runbook and checkpoint reviews (Section 7.1)

**What this document cannot guarantee:** FCM rate limits are not contractually specified. The P1 delay figures in Section 1.4 are planning estimates until the pre-production load test is completed and signed off. The load test owner, schedule, and launch gate are in Section 1.4. If you are reading this before that test has been signed off, treat those figures accordingly.

**What this document does not paper over:** Four specific items are flagged as unresolved product decisions rather than engineering constants. They appear in context with [PRODUCT DECISION REQUIRED] markers and are deployment checklist gates. They cannot be defaulted by the engineering team.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The precise conditions under which P2/P3 can still be deferred despite the token bucket — and the operational response to each — are in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a bounded window. Worst-case delivery outcome is duplication, not loss. Worst-case P1 delay under coincident failure: **20–40 minutes under a standard spike, 50–80 minutes if a database issue outlasts the spike** — derived step-by-step in Section 1.4.

**3. Per-channel, per-priority worker pools** implemented as a single binary with channel and priority flags. Sixteen logical worker types, one deployable binary. Deployment complexity tradeoffs are in Section 3.3.

**4. Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput. If pre-production load testing shows the actual FCM limit is below 2,000/sec, the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table reflects joint scenarios: the low row uses both a low ratio and a low rate; the high row uses both high values. Treating them as independent understates the high-engagement risk.

**The power-user pattern requires separate treatment.** A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems that total volume does not capture:

- **Per-user rate limiting:** Concentrates write load on specific Redis keys. The per-user rate limit is 20 notifications/hour with a burst allowance of 5. This is not derived from average behavior. It is derived from research on social app spam perception showing user satisfaction degradation above approximately 15–25 notifications/hour from a single app, with a conservative margin. **[PRODUCT DECISION REQUIRED]:** Product must confirm this limit is acceptable before launch. This is a deployment checklist gate.

- **Deduplication set sizes:** Deduplication is keyed per user with a 60-second sliding window. Memory impact is bounded by 60 seconds of per-user throughput, not total retained IDs. See Section 2.2 for full arithmetic. Note: the system-wide deduplication memory bound (128 bytes per ID, 10M retained IDs per channel) applies to the delivered-ID set used for cross-channel deduplication; these are separate mechanisms with separate bounds.

- **Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs over 5 minutes. **This is a product-visible behavior:** followers beyond position 10,000 in a large fanout receive their notifications up to 5 minutes later than the first 10,000. The engineering rationale for the cap is preventing a single viral event from saturating queue capacity for all other users. **[PRODUCT DECISION REQUIRED]:** This tradeoff must be presented to and accepted by product before launch. Decision is recorded in the deployment checklist as: [PRODUCT DECISION RECORDED HERE].

These subsystem stresses are independent of whether total daily volume is above or below the plan figure. They are not covered by the low-engagement row in the sensitivity table.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The 3× peak multiplier assumes a two-hour evening window. **A day can show on-plan daily volume while exceeding per-second thresholds during a peak hour.** The traffic response matrix in Section 1.3 uses both threshold columns; if they disagree, the higher response level applies.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — missed checkpoint default:**

If month-1 traffic data is not reviewed by day 35, the on-call rotation owner executes the following within 24 hours of the missed deadline:

1. **Verify deployment names before touching anything:** `kubectl get deployments -l app=notification-worker`. If names do not match the checklist, stop and contact the engineering lead. Silent execution of scale commands against wrong targets is the failure mode this step prevents.
2. If names match: `kubectl scale deployment push-worker --replicas=12` (from 8 baseline)
3. If names match: `kubectl scale deployment inapp-worker --replicas=6` (from 4 baseline)
4. Verify Redis tier against the provisioning decision recorded in Section 1.3a. If tier does not match, promote pre-staged replica per Section 6.2.
5. Record actions and timestamp in the runbook log under "Month-1 default provisioning applied."

These actions are reversible. Step-down requires: traffic review completed and documented, engineering lead sign-off, and 7 days of post-review data confirming volume below 45M/day. Engineering lead is the named decision owner for step-down. If unavailable, Section 7.2 fallback applies.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. Suppression of push when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model — the volume model accounts for worst-case write load. A viral spike drives push and in-app saturation simultaneously because they are triggered by the same upstream events; the traffic response matrix accounts for this correlated failure mode explicitly.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

**This section is self-contained.** All CLI commands needed to respond are embedded here. No cross-references are required under incident conditions.

**Named decision owner:** Engineering lead and named backup are recorded in the runbook and deployment checklist before launch. Placeholder text fails the pre-flight check. If either named individual is unavailable for more than 5 business days, Section 7.2 activates immediately.

**Redis provisioning dependency:** The 45M–80M/day response branch has two paths depending on which Redis option was selected. That decision is made in Section 1.3a and recorded in the deployment checklist. The matrix references it by option letter so operators follow the correct branch without re-evaluating the tradeoff under pressure.

**Auto-scaling:** Not available at launch. Available from month 2 after HPA deployment and validation. Manual response times apply until then. Auto-scaling configuration and trigger threshold justification are in Section 1.3b.

**Dashboard CLI fallback** (use if dashboard is unresponsive for more than 2 minutes):

```bash
# Queue depths by channel and priority
redis-cli LLEN queue:push:p0:0
redis-cli LLEN queue:push:p1:0
redis-cli LLEN queue:push:p2:0
redis-cli LLEN queue:push:p3:0
redis-cli LLEN queue:inapp:p1:0
redis-cli LLEN queue:email:p1:0
redis-cli LLEN queue:sms:p1:0

# Processing set sizes (in-flight messages; elevated = worker crash or slowdown)
redis-cli ZCARD processing:push
redis-cli ZCARD processing:inapp
redis-cli ZCARD processing:email
redis-cli ZCARD processing:sms

# Worker pod counts by channel
kubectl get pods -l app=notification-worker,channel=push \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=inapp \
  --field-selector=status.phase=Running --no-headers | wc -l

# Verify deployment names are current before any scaling action
kubectl get deployments -l app=notification-worker
```

**Traffic response matrix:**

| Daily volume | Instantaneous rate | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|---|
| < 7.5M/day | < 260/sec | Well below plan | Verify deployment names. Scale down: `kubectl scale deployment push-worker --replicas=4` | Queue depth < 1K sustained 30 min | Re-review at 2 weeks |
| 7.5M–45M/day | 260–1,575/sec | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | 1,575–2,800/sec | Moderately above plan | Push and in-app co-saturate — check both queues first. Scale push: `kubectl scale deployment push-worker --replicas=16`. Scale in-app: `kubectl scale deployment inapp-worker --replicas=8`. If email queue also rising: `kubectl scale deployment email-worker --replicas=4`. **Redis branch — look up recorded option in deployment checklist:** If Option A (pre-provisioned 80M/day): no Redis action. If Option B (right-sized at launch): promote pre-staged replica per Section 6.2; expect 15–30 min degraded window. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | 2,800–7,900/sec | Significantly above plan | All above actions. If sharding pre-staged (month 3+): update `NOTIFICATION_SHARD_COUNT=4` and restart workers — engineering lead makes go/no-go. If sharding not yet pre-staged: scale workers vertically; accept higher Redis CPU until configuration is ready. | Throughput > 80M/day sustained with P99 < 2s | Architectural review if not confirmed within 2 weeks |
| > 225M/day | > 7,900/sec | Severely above plan | Defer SMS and email dispatch. One engineer assigned full-time to re-architecture. | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + named backup go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**
- Automated (HPA, month 2 onward, after validation): ~2–3 minutes
- Manual, runbook available, dashboard loading normally: ~8–10 minutes
- Manual, runbook available, dashboard degraded (realistic incident scenario): ~10–15 minutes using CLI fallback above
- Manual, no runbook: blocked by launch gate — this state cannot occur in production

### 1.3a Redis Provisioning Decision — Cost Tradeoff Resolution

This decision must be recorded in the deployment checklist before launch. The traffic response matrix cannot be executed correctly without it.

**Option A — Pre-provision at 80M/day capacity** (ElastiCache r6g.2xlarge or equivalent)
- Cost: approximately $400–600/month additional versus Option B
- Benefit: no Redis action required in the 45M–80M/day traffic band; operators follow the simpler matrix branch; no degraded window during a traffic event
- Risk: paying for headroom that may never be used if traffic stays below 45M/day

**Option B — Right-size at launch for 45M/day** (ElastiCache r6g.xlarge or equivalent)
- Cost: approximately $200–300/month lower than Option A
- Benefit: avoids paying for unused capacity in early months
- Risk: if traffic enters the 45M–80M/day band, operators must execute a replica promotion during an active traffic event, accepting a 15–30 minute degraded window. This is a recoverable, documented procedure (Section 6.2), but it adds operational complexity at the worst possible time

**Engineering recommendation:** Option A. The cost delta ($400–600/month) is small relative to the engineering time consumed by managing a degraded-window incident at peak traffic. This is however a business decision. The engineering team's preference is noted; the named decision owner records the final choice below before launch.

**Recorded decision:** [ ] Option A / [ ] Option B — decided by [NAME] on [DATE]

**Sharding pre-staging:** Queue keys use `queue:{channel}:{priority}:{shard}` format from day one with shard `0` initially. Adding shards requires a configuration change and worker restart — no schema migration, no code deployment. Pre-staging the sharding configuration is a month-3 deliverable regardless of traffic at that point.

### 1.3b Auto-Scaling Trigger Threshold Justification

The HPA triggers on `notification_queue_depth_p1 > 5,000 for > 2 minutes`. This threshold is not arbitrary.

**Why 5,000 and not lower:** At plan-rate peak (~1,094 push notifications/sec) with 8 workers at rated capacity, transient queue spikes of 1,000–3,000 are normal during burst absorption. A threshold below 5,000 triggers scale-up during normal traffic variation, adding pods that take 60–90 seconds to become ready and then immediately scale back down. A queue depth of 5,000 represents approximately 4–5 seconds of backlog — shallow enough that scaling is genuinely warranted, deep enough to distinguish a real backlog from a transient burst.

**Why not higher:** At 10,000 depth, the backlog represents ~9 