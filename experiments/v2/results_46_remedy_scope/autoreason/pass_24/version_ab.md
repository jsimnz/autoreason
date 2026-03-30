# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3** (self-contained; no cross-references needed)
- Traffic spike response → **Section 1.3** (self-contained; CLI commands embedded)
- Redis failover → **Section 6.2** (includes in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback in **Section 1.3**, no cross-reference required
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down with unavailable lead → **Section 7.2**

**What this document is and is not:** This document is complete as written. Every section it references exists in this document. The traffic response matrix in Section 1.3 is self-contained for incident use. If you find a reference to a section that does not exist, that is a defect — file it against the engineering lead and do not proceed with the referenced action until the section is produced.

**What this document cannot guarantee:** FCM rate limits are not contractually specified. P1 delay figures appear only in Section 1.4, are marked as unverified estimates, and must not be used as SLA commitments until the verification procedure in Section 1.4 is complete and signed off by the engineering lead.

**Three decisions require named humans before production.** Placeholder text in any of these fields causes the pre-flight check (defined in Section 7.1) to return a non-zero exit code, blocking the deployment pipeline:

1. Engineering lead and named backup (Section 7.1)
2. Redis provisioning option — Option A or Option B — resolved in Section 1.3a and recorded in Section 7.1
3. On-call rotation owner responsible for the runbook and checkpoint reviews (Section 7.1)

**Four items are flagged as unresolved product decisions.** They appear with [PRODUCT DECISION REQUIRED] markers and are deployment checklist gates. They cannot be defaulted by the engineering team. Each has a deadline and a named owner field in Section 7.1.

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**The staffing constraint is a design input, not a label.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing analysis that drove several architectural decisions, most visibly the reduction of worker deployments from a theoretical maximum of 16 to 6. Every place in this document where a simpler approach was chosen over a more capable one, the staffing constraint is the explicit reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket are in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a bounded window. Worst-case delivery outcome is duplication, not loss. P1 delay estimates under failure conditions are in Section 1.4 and are marked as unverified until the pre-launch FCM rate check is complete.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The reduction is a deliberate staffing-driven decision. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can actually manage. The full tradeoff analysis is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput — but that claim depends on the FCM rate assumption that requires pre-launch verification per Section 1.4.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table reflects joint scenarios: the low row uses both a low ratio and a low rate; the high row uses both high values. Treating them as independent understates the high-engagement risk.

**The power-user pattern requires separate treatment.** A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems:

- **Per-user rate limiting:** Concentrates write load on specific Redis keys. The per-user sustained rate limit is 20 notifications/hour.

  **[PRODUCT DECISION REQUIRED — Burst Allowance]:** Engineering recommends a burst allowance between 3 and 5 (allowing 23–25 notifications in a short window above the sustained hourly rate). The basis for this range is operational judgment about spam perception, not a citable study. Product must select a value in this range. **Deadline:** This value must be confirmed in writing to the engineering lead by the date recorded in Section 7.1. If not confirmed by that date, the engineering lead escalates per Section 7.2. The deployment pipeline will not clear the pre-flight check until a value is recorded in Section 7.1. The engineering team will implement whatever value product selects within the recommended range, or will flag for re-evaluation if product selects a value outside it.

- **Deduplication set sizes:** Deduplication is keyed per user with a 60-second sliding window. Memory impact is bounded by 60 seconds of per-user throughput, not total retained IDs. See Section 2.2 for full arithmetic and the interaction between the sliding window and the cross-channel delivered-ID set.

- **Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs over 5 minutes. **This is a product-visible consistency decision, not merely a latency decision.** During the 5-minute window, some followers have received the notification and may have already acted on the underlying content while others have not. The engineering rationale for the cap is preventing a single viral event from saturating queue capacity for all other users.

  **[PRODUCT DECISION REQUIRED — Fanout Cap]:** Product must select one of the following before launch. **These options are not equivalent in what they require from engineering.** Option D requires a prior engineering deliverable before it can be accepted; that deliverable is not currently scheduled. This asymmetry is disclosed explicitly for each option:

  - **Option A — Accept the consistency gap:** The 5-minute fanout window is acceptable. No product-layer changes needed. No prior engineering deliverable required.
  - **Option B — Accept the gap with UX mitigation:** The gap is acceptable, but reply counts or engagement indicators will be suppressed until fanout completes. No prior engineering deliverable required, but frontend work is needed.
  - **Option C — Reject the cap and set a higher limit:** Product sets the cap. Engineering will re-evaluate queue saturation risk at the chosen value and may require infrastructure changes before the option can be accepted. Allow at least one sprint for the engineering review cycle.
  - **Option D — Reject fanout batching entirely:** All recipients are notified within a single synchronous window. **This option requires engineering to produce a revised capacity estimate for queue infrastructure before it can be accepted.** That estimate is not currently scheduled. Selecting this option without scheduling the estimate work will block the deployment checklist gate. Allow at least two sprints for the estimate and any resulting infrastructure changes.

  This decision is recorded in Section 7.1 as a deployment checklist gate.

**Peak multiplier rationale:** The plan-row uses 3× because the 30% DAU/MAU figure represents mid-engagement behavior, which in comparable social apps produces an evening peak lasting approximately 2–3 hours. A 3× multiplier is consistent with a daily total concentrated such that peak-hour traffic is three times the per-second daily average. This is a defensible estimate for this specific engagement scenario, not a universal constant. The high-engagement rows use higher multipliers because more real-time interaction compresses activity into shorter windows and produces sharper viral spikes. The low-engagement row uses 2.5× because flatter engagement produces flatter intraday distribution.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~260/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,340/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — traffic-conditional procedure:**

The on-call rotation owner reviews month-1 traffic data by day 30. If the review has not occurred by day 33, the engineering lead is responsible for executing the procedure below within 24 hours.

**Escalation chain and symmetric accountability:** The engineering lead is the independent trigger because if the on-call rotation owner is the reason the review was missed, relying on that person to trigger escalation creates a self-referential gap. However, the engineering lead is also the person responsible for the on-call rotation owner's accountability. If the engineering lead is the reason the review did not occur — through inaction, unavailability, or organizational failure — routing escalation through the engineering lead reintroduces the same gap in the opposite direction. To address this symmetric case: if neither the on-call rotation owner nor the engineering lead has initiated the review by day 33, the named backup in Section 7.1 is the escalation trigger and has authority to execute the procedure unilaterally. The backup does not need to determine whose failure caused the gap before acting. The backup's authority is time-triggered (day 33), not permission-triggered. If the named backup is also unreachable by day 34, this is a Section 7.2 escalation event.

```bash
# Step 1: Verify deployment names before touching anything
kubectl get deployments -l app=notification-worker
# If names do not match the checklist in Section 7.1, stop and contact engineering lead.

# Step 2: Assess current traffic
kubectl exec -it $(kubectl get pod -l app=prometheus -o name | head -1) -- \
  promtool query instant 'sum(increase(notifications_dispatched_total[24h]))'

# Step 3: Pull current queue depths
redis-cli LLEN queue:push:p0:0
redis-cli LLEN queue:push:p1:0
```

**Traffic-conditional response:**

| Observed 24h volume | Action |
|---|---|
| < 30M/day | No scaling action. Document observation. Schedule review within 7 days. |
| 30M–55M/day | On plan or modestly above. Scale push-worker-high to 12 replicas, inapp-worker to 6 replicas. Document and notify engineering lead. |
| 55M–80M/day | Moderately above plan. Execute the 55M–80M/day row of the traffic response matrix in Section 1.3 in full. Escalate to engineering lead immediately. |
| > 80M/day | Significantly above plan. Escalate to engineering lead immediately. Do not execute scaling actions unilaterally. |

**Scale-down procedure:** Scaling actions taken during the month-1 checkpoint are reversible. Step-down requires: traffic review completed and documented, engineering lead sign-off, and 7 days of post-review data confirming volume below 45M/day. If the engineering lead is unavailable, Section 7.2 applies. The cost of remaining over-provisioned while awaiting sign-off is quantified in Section 7.2 to give the backup decision-maker a defined authorization threshold.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. Suppression of push when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model — the volume model accounts for worst-case write load.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

**This section is self-contained.** All CLI commands needed to respond are embedded here. No cross-references are required under incident conditions.

**Named decision owner:** Engineering lead and named backup are recorded in Section 7.1 before launch.

**Redis provisioning dependency:** The 55M–80M/day response branch has two paths depending on which Redis option was selected. Operators follow the correct branch by checking the recorded option in Section 7.1 — they do not re-evaluate the tradeoff under pressure. The full Redis option analysis is in Section 1.3a, but operators do not need to read it during an incident.

**Auto-scaling availability:** Not available at launch. Available from month 2 after HPA deployment and validation (Section 1.3b). For month-1 after-hours spike response, see Section 1.3c.

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

# Processing set sizes (elevated values indicate worker crash or slowdown)
redis-cli ZCARD processing:push
redis-cli ZCARD processing:inapp
redis-cli ZCARD processing:email
redis-cli ZCARD processing:sms

# Worker pod counts by deployment
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

| Daily volume | Peak rate | Classification | Response | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|---|
| < 7.5M/day | < 260/sec | Well below plan | Verify deployment names match Section 7.1 checklist. No scaling action. Document and schedule 7-day review. | Prometheus 24h sum stable | Engineering lead review within 