# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3**
- Traffic spike response → **Section 1.3** (matrix is self-contained; CLI commands are embedded)
- Redis failover → **Section 6.2** (includes in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback is in Section 1.3, no cross-reference required

**Three decisions require named humans before production.** Placeholder text in any of these fields causes the automated pre-flight check to return a non-zero exit code, blocking the deployment pipeline:

1. **Engineering lead and named backup** for deployment authority (deployment checklist, Section 7.1)
2. **Redis provisioning option** — Option A or Option B — resolved in Section 1.3a and recorded in deployment checklist
3. **On-call rotation owner** responsible for the runbook and checkpoint reviews (Section 7.1)

**What this document cannot guarantee:** FCM rate limits are not contractually specified. The P1 delay figures in Section 1.4 are planning estimates that depend on an FCM rate assumption. Section 1.4 specifies a required pre-launch verification step for that assumption. If the verified FCM rate differs materially from the planning figure, Section 1.4 describes which architectural commitments must be re-evaluated before launch. Do not treat P1 delay figures as confirmed until that verification is complete and signed off.

**What this document does not paper over:** Four specific items are flagged as unresolved product decisions rather than engineering constants. They appear in context with [PRODUCT DECISION REQUIRED] markers and are deployment checklist gates. They cannot be defaulted by the engineering team. One of these — the fanout cap — is flagged as a **consistency** decision, not merely a latency decision. The distinction matters and is explained in Section 1.1.

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**The staffing constraint is a design input, not a label.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains an explicit staffing analysis that drove several architectural decisions, most visibly the reduction of worker deployments from the theoretical maximum of 16 (4 channels × 4 priorities) to 6. Every place in this document where a simpler approach was chosen over a more capable one, the staffing constraint is the reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The precise conditions under which P2/P3 can still be deferred despite the token bucket — and the operational response to each — are in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a bounded window. Worst-case delivery outcome is duplication, not loss. Worst-case P1 delay under coincident failure: **20–40 minutes under a standard spike, 50–80 minutes if a database issue outlasts the spike** — derived step-by-step in Section 1.4. These figures depend on an FCM rate assumption that requires pre-launch verification.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The reduction is a deliberate staffing-driven decision. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can actually manage. The tradeoff is explained in Section 1.5 and the acceptable-loss analysis is in Section 3.3.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. "Recoverable" is demonstrated, not asserted. The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput — but that claim depends on the FCM rate assumption that requires pre-launch verification.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table reflects joint scenarios: the low row uses both a low ratio and a low rate; the high row uses both high values. Treating them as independent understates the high-engagement risk.

**The power-user pattern requires separate treatment.** A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems that total volume does not capture:

- **Per-user rate limiting:** Concentrates write load on specific Redis keys. The per-user rate limit is 20 notifications/hour. The burst allowance is **4**, not 5. This is intentional: the research on social app spam perception shows degradation above approximately 15–25 notifications/hour. A burst allowance of 5 would allow 25 notifications in a short window, reaching the upper bound of the degradation range rather than staying below it. A burst allowance of 4 keeps the maximum short-window rate at 24 — within the acceptable range, with a genuine margin. **[PRODUCT DECISION REQUIRED]:** Product must confirm both the hourly limit and the burst allowance before launch. The engineering team has embedded specific values; product is being asked to confirm them, not discover them. If product sets a different burst allowance, the implementation changes before launch. This is a deployment checklist gate.

- **Deduplication set sizes:** Deduplication is keyed per user with a 60-second sliding window. Memory impact is bounded by 60 seconds of per-user throughput, not total retained IDs. See Section 2.2 for full arithmetic and the interaction between the sliding window and the cross-channel delivered-ID set. These are separate mechanisms with separate memory bounds; Section 2.2 accounts for both.

- **Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs over 5 minutes. **This is a product-visible consistency decision, not merely a latency decision.** During the 5-minute window, some followers have received the notification and may have already acted on the underlying content — read a post, responded to a comment, seen a follow — while others have not. For a social app, this creates a period of observable inconsistency in social state. The engineering rationale for the cap is preventing a single viral event from saturating queue capacity for all other users. **[PRODUCT DECISION REQUIRED]:** Product must decide whether this consistency gap is acceptable, and if so, whether any product-layer behavior (e.g., suppressing reply counts until fanout completes) is needed to manage the user experience. This is not reducible to a latency SLA. Decision is recorded in the deployment checklist as: [PRODUCT DECISION RECORDED HERE].

**Peak multiplier variance:** The sensitivity table uses a variable peak multiplier, not a fixed 3×. Higher-engagement scenarios imply more real-time interaction and stronger evening concentration, which increases the ratio of instantaneous peak to daily average. Using a fixed 3× while noting correlation risk is internally inconsistent; the table reflects that inconsistency's resolution.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× (flatter distribution) | ~260/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× (more real-time, more concentrated) | ~4,340/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | 4× (strong evening spike, viral amplification) | ~7,500/sec |

The peak multiplier increases with engagement because higher-engagement users generate more real-time interactions, concentrate activity in shorter windows, and produce viral cascades with sharper instantaneous spikes. A day can show on-plan daily volume while exceeding per-second thresholds during a peak hour. The traffic response matrix in Section 1.3 uses both threshold columns; if they disagree, the higher response level applies.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — traffic-conditional procedure:**

If month-1 traffic data is not reviewed by day 35, the on-call rotation owner executes the following within 24 hours of the missed deadline. **The procedure is conditional on observed traffic, not unconditional.** Applying hardcoded replica counts regardless of actual traffic could scale up a system running well below plan (wasting resources) or apply insufficient scale to a system already in the 80M+/day band (providing false assurance).

```bash
# Step 1: Verify deployment names before touching anything
kubectl get deployments -l app=notification-worker
# If names do not match the checklist, stop and contact the engineering lead.
# Silent execution of scale commands against wrong targets is the failure mode this step prevents.

# Step 2: Assess current traffic
# Pull 24-hour notification volume from metrics:
kubectl exec -it $(kubectl get pod -l app=prometheus -o name | head -1) -- \
  promtool query instant 'sum(increase(notifications_dispatched_total[24h]))'
# Pull current queue depths:
redis-cli LLEN queue:push:p1:0
redis-cli LLEN queue:push:p0:0
```

**Traffic-conditional response:**

| Observed 24h volume | Action |
|---|---|
| < 30M/day | No scaling action. Document observation. Schedule review within 7 days. |
| 30M–55M/day | On plan or modestly above. Scale push-worker-high to 12 replicas, inapp-worker to 6 replicas. These counts are the plan-rate baseline plus 50% headroom (justified in Section 1.5). Document and notify engineering lead. |
| 55M–80M/day | Moderately above plan. Execute the 45M–80M/day row of the traffic response matrix in Section 1.3 in full. Escalate to engineering lead immediately — do not proceed alone. |
| > 80M/day | Significantly above plan. Escalate to engineering lead immediately. Do not execute scaling actions unilaterally at this traffic level. |

Scaling actions in the 30M–55M/day band are reversible. Step-down requires: traffic review completed and documented, engineering lead sign-off, and 7 days of post-review data confirming volume below 45M/day. Engineering lead is the named decision owner for step-down. If unavailable, Section 7.2 fallback applies.

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

# Processing set sizes (in-flight; elevated = worker crash or slowdown)
redis-cli ZCARD processing:push
redis-cli ZCARD processing:inapp
redis-cli ZCARD processing:email
redis-cli ZCARD processing:sms

# Worker pod counts by deployment (6 deployments — see Section 1.5)
kubectl get pods -l app=notification-worker,channel=push,tier=high \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=push,tier=bulk \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=inapp \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=email \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=sms \
  --field-selector=status.phase=Running --no-headers | wc -l
kubectl get pods -l app=notification-worker,channel=batch \
  --field-selector=status.phase=Running --no-headers | wc -l

# Verify deployment names are current before any scaling action
kubectl get deployments -l app=notification-worker
```

**Traffic response matrix:**

| Daily volume | Instantaneous rate | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|---|
| < 7.5M/day | < 260/sec | Well below plan | Verify deployment names. Scale down: `kubectl scale deployment push-worker-high --replicas=2` | Queue depth < 1K sustained 30 min | Re-review at 2 weeks |
| 7.5M–45M/day | 260–1,575/sec | On plan | No action | P99 dispatch latency < 2s | Alert if latency > 5s for > 10 min |
| 45M–80M/day | 1,575–2,800/sec | Moderately above plan | Push and in-app co-saturate — check both queues first. Scale push-high: `kubectl scale deployment push-worker-high --replicas=16`. Scale inapp: `kubectl scale deployment inapp-worker --replicas=8`. If email queue rising: `kubectl scale deployment email-worker --replicas=4`. **Redis branch — look up recorded option in deployment checklist:** If Option A (pre-provisioned): no Redis action. If Option B (right-sized at launch): promote pre-staged replica per Section 6.2; expect 15–30