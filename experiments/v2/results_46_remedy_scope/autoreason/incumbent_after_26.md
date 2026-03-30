# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Synthesis — Incorporates strongest elements from both versions

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3** (self-contained; no cross-references needed)
- Traffic spike response → **Section 1.3** (self-contained; CLI commands embedded)
- Redis failover → **Section 6.2** (includes in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down with unavailable lead → **Section 7.2**

**Self-completeness policy:** Every section referenced in this document exists in this document. The table of contents verifies section titles exist; it does not verify section content is complete. The authoritative completeness check is the section-existence test in Section 7.1, which enumerates every section by number and requires a human reviewer to confirm each is present and non-truncated before the pre-flight check passes. If you find a section that is truncated or absent, that is a defect — file it against the engineering lead and do not proceed with any action that section governs until the defect is resolved.

**What this document cannot guarantee:** FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are marked as unverified estimates until the pre-launch FCM rate check procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

**Three decisions require named humans before production.** These are recorded in Section 7.1. The pre-flight check script (defined in Section 7.1) parses Section 7.1 for these fields. Any value matching the regex `\[.*REQUIRED.*\]` causes the script to exit non-zero, blocking the deployment pipeline. The script location, invocation, and expected output format are specified in Section 7.1.

1. Engineering lead and named backup
2. Redis provisioning option (Option A or Option B, resolved in Section 1.3a and recorded in Section 7.1)
3. On-call rotation owner

**Four items are flagged as unresolved product decisions.** Each appears with a [PRODUCT DECISION REQUIRED] marker. The four decisions are:

1. Burst allowance value (Section 1.1)
2. Fanout cap option (Section 1.1)
3. Cross-channel deduplication retention window (Section 2.2)
4. SMS opt-out compliance owner (Section 5.4)

Each has a deadline and named owner field in Section 7.1. The pre-flight check script treats any unresolved field as a blocking condition.

---

## Table of Contents

1. Scale Assumptions and Constraints
   - 1.1 Traffic Model
   - 1.2 Channel Split and Volume Accounting
   - 1.3 Traffic Response Matrix
   - 1.3a Redis Provisioning Options
   - 1.3b HPA Deployment and Validation
   - 1.3c Month-1 After-Hours Spike Response
   - 1.4 FCM/APNs Rate Limit Verification
   - 1.5 Staffing Analysis
2. Notification Routing and Deduplication
   - 2.1 Routing Logic
   - 2.2 Deduplication Architecture
3. Priority and Batching
   - 3.1 Priority Tiers
   - 3.2 Token Bucket and Starvation Prevention
   - 3.3 Batching Logic
4. Worker Architecture
   - 4.1 Worker Deployments
   - 4.2 Processing State and Recovery
   - 4.3 Queue Backup and Worker Failure Response
5. Delivery Channels
   - 5.1 Push (FCM + APNs)
   - 5.2 In-App
   - 5.3 Email
   - 5.4 SMS
6. Infrastructure
   - 6.1 Queue Infrastructure
   - 6.2 Redis Failover and In-Flight Behavior
   - 6.3 Database
7. Operations
   - 7.1 Pre-Flight Checklist, Named Owners, and Section-Existence Verification
   - 7.2 Escalation and Authorization Thresholds
8. Build Timeline

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**The staffing constraint is a design input, not a label.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing analysis — including the arithmetic — that drove the reduction from a theoretical maximum of 16 worker deployments to 6. Every place in this document where a simpler approach was chosen over a more capable one, the staffing constraint is the explicit reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket are specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window — this bound is derived in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can actually manage. The full tradeoff arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. The binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput — but this claim is contingent on the FCM rate verification in Section 1.4 and is marked unverified until that procedure completes and is signed off by the engineering lead.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions that compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure for a mid-engagement social app.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table reflects joint scenarios: the low row uses both a low ratio and a low rate; the extreme row uses both high values. Treating them as independent understates high-engagement risk.

**Peak multiplier methodology:**

```
peak_rate = (daily_volume × peak_multiplier) / 86,400
```

The multiplier represents the ratio of peak-hour traffic to the per-second daily average. A 3× multiplier means the peak second within the peak hour runs at 3× the daily average per-second rate. Multipliers increase with engagement level because more real-time interaction compresses activity into shorter windows, producing sharper peaks. This means peak rates scale superlinearly relative to daily totals as engagement rises — the extreme row's peak rate is 4.76× the plan row's peak rate while daily volume is only 3.6× higher. That is internally consistent with the methodology, not an error.

**Calibration note:** The multipliers (2.5×, 3×, 3.5×, 4×) are stated assumptions derived from general social-app patterns, not measured values from this system. The superlinear scaling behavior is a consequence of these chosen multipliers — internally consistent, but not yet validated against production data. Multipliers must be recalibrated at the month-1 checkpoint. Until then, the extreme-scenario peak rate of ~7,500/sec should be treated as an order-of-magnitude planning estimate, not a precise bound.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

*Peak rate = (daily_volume × multiplier) / 86,400. Multipliers are assumptions; see calibration note above.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). Validate actual rate and recalibrate multipliers within the first 30 days of production traffic.

---

**Power-user pattern:**

A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems.

**Per-user rate limiting — identified gap:** The 20/hour sustained ceiling exists as a spam-prevention control, not an infrastructure protection mechanism. A user generating 50 notifications/day is not constrained by this ceiling (50/day is well below 480/day, the 20/hour ceiling extrapolated across 24 hours). The rate limit does not address the power-user case in the range that actually occurs.

This gap is real and currently unresolved at the product level. Infrastructure mechanisms — per-user queue partitioning (Section 4.1) and Redis key sharding (Section 6.1) — address throughput distribution so that one power user cannot monopolize shared queue capacity. They do not address the spam-prevention gap. That gap requires a product decision about what constitutes excessive volume at the daily level, which is separate from the burst allowance decision below.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Engineering recommends a burst allowance of 3–5 notifications above the 20/hour sustained rate within any 5-minute window. This is a product-quality decision about spam perception; the infrastructure impact of any value in the 3–5 range is negligible. Product must select a value. **Owner and deadline: Section 7.1.** The pre-flight check script will not pass until a value is recorded.

**Deduplication set sizes:** Deduplication is keyed per user with a 60-second sliding window for same-channel deduplication. Cross-channel deduplication uses a separate delivered-ID set with a longer retention window. For power users generating 50+ notifications/day, the cross-channel delivered-ID set is not bounded by the 60-second sliding window — it is bounded by the cross-channel retention window, which is a product decision. A longer window reduces duplicate cross-channel delivery at the cost of higher Redis memory per user. Full memory arithmetic and the retention window decision are in Section 2.2.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs running at P2 priority. This is a product-visible consistency decision: during the fanout window, some followers have received the notification and may have acted on the underlying content while others have not. The worst-case fanout completion time bound is derived from token bucket parameters in Section 3.2. Summary: approximately 45 minutes for a 100,000-recipient event under sustained P0/P1 congestion. That bound is derived, not asserted — see Section 3.2 for the arithmetic. "5 minutes" is a target under normal conditions, not a bound.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Product must select one option before launch. **These options are not equivalent in what they require from engineering.** Option D requires a prior engineering deliverable before it can be accepted; selecting it without scheduling that work blocks the pre-flight gate in Section 7.1.

- **Option A — Accept the consistency gap:** The fanout window (5 minutes target, ~45 minutes worst-case under congestion) is acceptable. No prior engineering deliverable required.
- **Option B — Accept the gap with UX mitigation:** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering deliverable required; frontend work needed.
- **Option C — Set a higher cap:** Product sets the cap. Engineering re-evaluates queue saturation risk and may require infrastructure changes. Allow one sprint for engineering review before option is accepted.
- **Option D — Reject batching entirely:** Requires engineering to produce a revised capacity estimate before this option can be accepted. That estimate is not currently scheduled. Allow two sprints. Selecting this option without scheduling the estimate work blocks the pre-flight gate; Option D cannot pass that gate until the revised capacity estimate is produced and reviewed.

**Owner and deadline: Section 7.1.**

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30. Documentation means a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**Escalation chain:** The backup named in Section 7.1 is responsible for monitoring whether the day-30 review has been documented. The backup's authority is time-triggered: if no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 procedure below without waiting for permission from either the on-call owner or the engineering lead. The backup does not need to determine whose failure caused the gap before acting.

This chain has a known residual gap: if the engineering lead is the reason the review did not occur, routing escalation through the engineering lead reintroduces the failure. The backup's time-triggered authority addresses this for the common case. The uncommon case — all three named people simultaneously unavailable or unresponsive by day 34 — cannot be resolved within this runbook. The correct action is to escalate to the person above the engineering lead in the current org chart. This document does not name that person because org charts change; the current org chart is the authoritative source. Anyone who reaches day 34 without a documented review should look up the current org chart and escalate immediately rather than waiting for further instruction from this document.

**Month-1 traffic-conditional procedure (self-contained):**

```bash
# Step 1: Verify deployment names match Section 7.1 before any action.
# If names do not match, stop and contact engineering lead before proceeding.
kubectl get deployments -l app=notification-worker

# Step 2: Assess current traffic
kubectl exec -it $(kubectl get pod -l app=prometheus -o name | head -1) -- \
  promtool query instant 'sum(increase(notifications_dispatched_total[24h]))'

# Step 3: Pull current queue depths
redis-cli LLEN queue:push:p0:0
redis-cli LLEN queue:push:p1:0
redis-cli LLEN queue:push:p2:0
redis-cli LLEN queue:push:p3:0
redis-cli LLEN queue:inapp:p1:0
redis-cli LLEN queue:email:p1:0
redis-cli LLEN queue:sms:p1:0

# Step 4: Verify labels are current before any scaling command
kubectl get deployment push-worker-high \
  -o jsonpath='{.spec.selector.matchLabels}'
kubectl get deployment push-worker-bulk \
  -o jsonpath='{.spec.selector.matchLabels}'
```

**Traffic-conditional response:**

| Observed 24h volume | Action |
|---|---|
| < 30M/day | No scaling action. Document observation. Schedule review within 7 days. |
| 30M–55M/day | On plan or modestly above. Scale push-worker-high to 12 replicas, inapp-worker to 6. Document and notify engineering lead. |
| 55M–80M/day | Moderately above plan. Execute full 55M–80M/day row of traffic response matrix in Section 1.3. Escalate to engineering lead immediately. |
| > 80M/day | Significantly above plan. Escalate to engineering lead immediately. Do not execute scaling actions unilaterally. |

**Scale-down procedure:** Scaling actions taken during the month-1 checkpoint are reversible. Step-down requires