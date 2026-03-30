# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Revision notes:** This version addresses eleven structural and content problems identified in review. Changes are substantive, not cosmetic. The epistemic hedging in the prior document status section has been compressed to a single paragraph and moved out of the operational path. Section 1.3a is now complete. Section 3.2 now contains the starvation analysis. Section 1.4 now contains the P1 delay derivation. The deduplication arithmetic inconsistency is resolved. The fanout tradeoff has been escalated to product. The load test now has an owner and a launch gate. Section 7.2 is now included.

---

## How to Use This Document Under Incident Conditions

**At 3 AM:** Go directly to the section you need.
- Queue backup or worker failure → **Section 4.3**
- Traffic spike response → **Section 1.3** (traffic response matrix)
- Redis failover → **Section 6.2**
- Dashboard unresponsive → CLI commands are embedded in Section 1.3, no cross-reference required

Three decisions require named humans before production. Placeholder text in any of these fields causes the automated pre-flight check to return a non-zero exit code, blocking the deployment pipeline:

1. **Engineering lead and named backup** for deployment authority (recorded in deployment checklist, Section 7.1)
2. **Redis provisioning option** — Option A or Option B — resolved in Section 1.3a and recorded in deployment checklist
3. **On-call rotation owner** responsible for the runbook and checkpoint reviews (Section 7.1)

**What this document cannot guarantee:** FCM rate limits are not contractually specified. The architecture is validated by a pre-production load test with explicit go/no-go thresholds. The load test owner and launch gate are in Section 1.4. If you are reading this before that test has been run and signed off, the P1 delay figures in Section 1.4 are planning estimates, not validated claims.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**Four core architectural decisions:**

1. **Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket, and the operational response to each condition, are in Section 3.2.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a bounded window. Worst-case delivery outcome is duplication, not loss. Worst-case P1 delay under coincident failure is **20–40 minutes under a standard spike, 50–80 minutes if a database issue outlasts the spike** — derived step-by-step in Section 1.4.

3. **Per-channel, per-priority worker pools** implemented as a single binary with channel and priority flags. Sixteen logical worker types, one deployable binary. Deployment complexity tradeoffs are in Section 3.3.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput. If pre-production load testing shows the actual FCM limit is below 2,000/sec, the P1 protection claims in this document are materially wrong and the architecture requires re-evaluation before launch. The load test owner, schedule, and launch gate are in Section 1.4.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated. The sensitivity table reflects joint scenarios — the low row uses both a low ratio and a low rate; the high row uses both high values.

**The power-user pattern:** A social app with low overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day does not appear as a risk in the volume table but stresses three specific subsystems:

- **Per-user rate limiting:** Concentrates write load on specific Redis keys. The per-user rate limit is 20 notifications/hour with a burst allowance of 5. This figure is not derived from average behavior. It is derived from spam-perception research on social apps showing user satisfaction degradation above approximately 15–25 notifications/hour from a single app, combined with a conservative margin. Product must confirm this is acceptable before launch — it is a product decision, not an engineering constant. The confirmation is a deployment checklist item (Section 7.1).
- **Deduplication set sizes:** Deduplication is keyed per user with a 60-second window. Memory impact is bounded by 60 seconds of per-user throughput, not total retained IDs. See Section 2.2 for the corrected arithmetic.
- **Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs over 5 minutes. **This is a product-visible behavior:** followers beyond position 10,000 in a large fanout receive their notifications up to 5 minutes later than the first 10,000. This tradeoff was presented to product on [DATE] and accepted/modified as follows: [PRODUCT DECISION RECORDED HERE]. This field must be filled before launch; it is a deployment checklist item. The engineering rationale for the cap is preventing a single viral event from saturating queue capacity for all other users.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The 3× peak multiplier assumes a two-hour evening window. A day can show on-plan daily volume while exceeding per-second thresholds during a peak hour. The traffic response matrix in Section 1.3 uses both columns; if they disagree, the higher response level applies.

**Month-1 checkpoint — missed checkpoint default:**

If month-1 traffic data is not reviewed by day 35, the on-call rotation owner executes within 24 hours:

1. Verify current deployment names match the checklist: `kubectl get deployments -l app=notification-worker`
2. If names match: `kubectl scale deployment push-worker --replicas=12` (from 8 baseline)
3. If names match: `kubectl scale deployment inapp-worker --replicas=6` (from 4 baseline)
4. Verify Redis tier against the provisioning decision recorded in Section 1.3a. If the tier does not match, promote the pre-staged replica per Section 6.2.
5. Record actions and timestamp in the runbook log under "Month-1 default provisioning applied."

**Step 1 is mandatory before steps 2–3.** If deployment names do not match the checklist, stop and contact the engineering lead before scaling anything. Silent execution of wrong-target scale commands is the failure mode this step prevents.

Step-down requires: traffic review completed and documented, engineering lead sign-off, 7 days of post-review data below 45M/day. Engineering lead is the named decision owner. If unavailable, Section 7.2 fallback applies.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The volume model accounts for worst-case write load. A viral spike drives push and in-app saturation simultaneously because they are triggered by the same upstream events. The traffic response matrix accounts for this explicitly.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

The matrix is complete and self-contained. All CLI commands needed to respond are embedded here. Dashboard CLI fallback is included because incident conditions frequently involve degraded dashboards.

**Named decision owner:** Engineering lead and named backup are recorded in the runbook and deployment checklist before launch. Placeholder text fails the pre-flight check. If either named individual is unavailable for more than 5 business days, Section 7.2 activates immediately.

**Redis provisioning dependency:** The 45M–80M/day response branch depends on which Redis option was selected. That decision is made in Section 1.3a and recorded in the deployment checklist. The matrix references it by option letter so operators can look up the recorded decision and follow the correct branch without re-evaluating the tradeoff under pressure.

**Auto-scaling:** Not available at launch. Available from month 2 after HPA deployment and validation. Until then, manual response times apply. Auto-scaling configuration and trigger threshold justification are in Section 1.3b.

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

# Verify deployment names are current before any scaling
kubectl get deployments -l app=notification-worker
```

**Traffic response matrix:**

| Daily volume | Instantaneous rate | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|---|
| < 7.5M/day | < 260/sec | Well below plan | Scale down: `kubectl scale deployment push-worker --replicas=4`. Verify name first. | Queue depth < 1K sustained 30 min | Re-review at 2 weeks |
| 7.5M–45M/day | 260–1,575/sec | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | 1,575–2,800/sec | Moderately above plan | Push and in-app co-saturate — check both first. Scale push: `kubectl scale deployment push-worker --replicas=16`. Scale in-app: `kubectl scale deployment inapp-worker --replicas=8`. If email queue also rising: `kubectl scale deployment email-worker --replicas=4`. **Redis branch — check deployment checklist for recorded option:** If Option A (pre-provisioned 80M/day): no Redis action needed. If Option B (right-sized at launch): promote pre-staged replica per Section 6.2; expect 15–30 min degraded window during promotion. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | 2,800–7,900/sec | Significantly above plan | All above actions, plus: if sharding is pre-staged (month 3+), update `NOTIFICATION_SHARD_COUNT=4` and restart workers — engineering lead makes go/no-go. If sharding not yet pre-staged, scale workers vertically and accept higher Redis CPU until configuration is ready. | Throughput > 80M/day sustained with P99 < 2s | Architectural review if not confirmed within 2 weeks |
| > 225M/day | > 7,900/sec | Severely above plan | Defer SMS and email dispatch. One engineer assigned full-time to re-architecture. | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + named backup go/no-go at 3-week checkpoint |

**Manual response timing:**
- Automated (HPA, month 2 onward, after validation): ~2–3 minutes
- Manual, runbook available, dashboard loading: ~8–10 minutes
- Manual, runbook available, dashboard degraded: ~10–15 minutes using CLI fallback above
- Manual, no runbook: blocked by launch gate — this state cannot occur in production

### 1.3a Redis Provisioning Decision — Cost Tradeoff Resolution

This decision must be recorded in the deployment checklist before launch. The matrix cannot be executed correctly without it.

**Option A — Pre-provision at 80M/day capacity (ElastiCache r6g.2xlarge or equivalent)**
- Cost: approximately $400–600/month additional versus Option B
- Benefit: no Redis action required in the 45M–80M/day traffic band. Operators follow the simpler branch of the matrix. No degraded window during a traffic event.
- Risk: paying for headroom that may never be used if traffic stays below 45M/day

**Option B — Right-size at launch for 45M/day (ElastiCache r6g.xlarge or equivalent)**
- Cost: approximately $200–300/month lower than Option A
- Benefit: avoids paying for unused capacity in the first months
- Risk: if traffic enters the 45M–80M/day band, operators must execute a replica promotion during an active traffic event, accepting a 15–30 minute degraded window. This is a recoverable, documented procedure (Section 6.2), but it adds operational complexity at the worst possible time.

**Recommendation:** Option A. The cost delta is small relative to engineering time consumed by a degraded-window incident. However, this is a business decision. The engineering team's preference for Option A is noted; the named decision owner records the final choice here before launch.

**Recorded decision:** [ ] Option A / [ ] Option B — decided by [NAME] on [DATE]

**Sharding pre-staging:** Queue keys use `queue:{channel}:{priority}:{shard}` format from day one with shard `0` initially. Adding shards requires a configuration change and worker restart — no schema migration, no code deployment. Pre-staging the configuration is a month-3 deliverable regardless of traffic at that point.

### 1.3b Auto-Scaling Trigger Threshold Justification

The HPA triggers on `notification_queue_depth_p1 > 5,000 for > 2 minutes`. The prior version of this document stated this threshold without justification. Here is the analysis.

**Why 5,000 and not lower:** At plan-rate peak (~1,094 push notifications/sec) with 8 workers processing at rated capacity, transient queue spikes of 1,000–3,000 are normal during burst absorption. A threshold below 5,000 would trigger scale-up during normal traffic variation, adding pods that take 60–90 seconds to become ready and then immediately scale back down. Based on the traffic model, a queue depth of 5,000 represents approximately 4–5 seconds of backlog — shallow enough that scaling is warranted but deep enough to distinguish a real backlog from a transient burst.

**Why not higher:** At 10,000 depth, the backlog represents ~9 seconds of work. Combined with the 2-minute trigger window and 60–90 second pod startup time, P1 notifications could experience 4–5 minutes of elevated latency before new capacity is available. That exceeds the 2-second P99 target by a wide margin.

**False-positive scale-up rate:** Based on the traffic model, evening peaks are expected to hit 2,000–3,000 queue depth transiently