# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3** (self-contained; no cross-references needed)
- Traffic spike response → **Section 1.3** (self-contained; CLI commands and deployment names embedded)
- Redis failover → **Section 6.2** (includes in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down needed → **Section 1.3** (procedure is complete and self-contained; if this document is unavailable, the standalone fallback is at `ops/runbooks/notification-scaledown.md`, maintained independently)
- Extreme traffic (>80M/day) → **Section 1.3**, extreme-scenario row; operator authority is explicitly granted for that row
- Escalation at day 34 with no available lead → **Section 7.2** (names a specific role, not an org chart lookup)

**What this document cannot guarantee:** FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are marked as unverified estimates until the pre-launch FCM rate check procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

**Completeness verification:** Section completeness is verified by a CI job that diffs the rendered document against a section manifest stored at `ops/runbooks/section-manifest.txt`. Any section present in the manifest but absent or empty in the rendered document causes the job to fail. The job runs on every commit. A passing CI badge is required before the pre-flight check can be marked complete. Instructions for running the CI job locally are in Section 7.1.

**Three decisions require named humans before production** (recorded in Section 7.1). The pre-flight script parses Section 7.1 for these fields; any value matching `\[.*REQUIRED.*\]` causes the script to exit non-zero, blocking the deployment pipeline.

1. Engineering lead and named backup
2. Redis provisioning option (Section 6.1) — blocked until Section 2.2 retention window and Section 1.4 FCM verification are both resolved, in that order
3. On-call rotation owner

**Five items are flagged as unresolved product decisions.** Each has a deadline and named owner in Section 7.1. The pre-flight script blocks on any unresolved field.

1. Burst allowance value (Section 1.1) — separate from daily spam threshold
2. Daily spam threshold (Section 1.1) — separate from burst allowance; see Section 1.1 for why these are distinct decisions
3. Fanout cap option (Section 1.1)
4. Cross-channel deduplication retention window (Section 2.2) — must be resolved before Redis provisioning
5. SMS opt-out compliance owner (Section 5.4)

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
   - 7.1 Pre-Flight Checklist, Named Owners, and CI Verification
   - 7.2 Escalation and Authorization Thresholds
8. Build Timeline

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**The staffing constraint is a design input, not a label.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing analysis — including the full arithmetic — that drove the reduction from a theoretical maximum of 16 worker deployments to 6. Every place in this document where a simpler approach was chosen over a more capable one, the staffing constraint is the explicit reason.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. The token bucket guarantees minimum throughput for lower-priority queues under sustained high-priority load. The conditions under which P2/P3 can still be deferred despite the token bucket are specified in Section 3.2.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window — this bound is derived in Section 4.2, not asserted. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can actually manage. The full tradeoff arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. The claim that FCM/APNs rate limits are the binding constraint during viral spikes — not Redis throughput — is contingent on the FCM rate verification in Section 1.4. Section 6.2 contains two explicit Redis sizing branches: one for each verification outcome. This claim is not used as a design assumption until verification is complete and signed off by the engineering lead.

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

The multiplier represents the ratio of peak-hour traffic to the per-second daily average. Multipliers increase with engagement level because more real-time interaction compresses activity into shorter windows. This means peak rates scale superlinearly relative to daily totals as engagement rises — the extreme row's peak rate is 4.76× the plan row's peak rate while daily volume is only 3.6× higher. That is internally consistent with the methodology, not an error.

**Calibration note:** The multipliers (2.5×, 3×, 3.5×, 4×) are stated assumptions derived from general social-app patterns, not measured values from this system. The superlinear scaling behavior is a consequence of these chosen multipliers — internally consistent, but not yet validated against production data. Multipliers must be recalibrated at the month-1 checkpoint. Until then, the extreme-scenario peak rate of ~7,500/sec should be treated as an order-of-magnitude planning estimate, not a precise bound.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

*Peak rate = (daily_volume × multiplier) / 86,400. Multipliers are stated assumptions; see calibration note above.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). The extreme scenario (162M/day, ~7,500/sec) is a plausible correlated outcome. The traffic response matrix in Section 1.3 includes an explicit runbook for >80M/day with operator authority granted — operators are not required to wait for escalation before acting in that scenario.

---

**Power-user pattern:**

A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems.

**There are two distinct power-user problems. They require two distinct decisions and must not be conflated.**

**Problem 1 — Burst allowance (product decides):** The 20/hour sustained ceiling exists as a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible. This decision does not address Problem 2.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. This is a product-quality decision about spam perception. It does not resolve the daily spam threshold question below. **Owner and deadline: Section 7.1.**

**Problem 2 — Daily spam threshold (product decides, separately):** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below 480/day, the ceiling extrapolated across 24 hours). There is currently no control for this case. Infrastructure mechanisms — per-user queue partitioning (Section 4.1) and Redis key sharding (Section 6.1) — prevent one power user from monopolizing shared queue capacity, but they do not prevent a user from generating objectively excessive daily notification volume. That requires a product decision about what daily volume constitutes excessive behavior and what action to take (suppress, hold for review, notify sender).

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Define what daily notification volume constitutes excessive behavior and specify the action to take. This is a separate decision from the burst allowance. Selecting a burst allowance value does not resolve this decision. **Owner and deadline: Section 7.1.**

**Deduplication set sizes:** For power users generating 50+ notifications/day, the cross-channel delivered-ID set is bounded by the cross-channel retention window, not the 60-second sliding window. A longer window reduces duplicate cross-channel delivery at the cost of higher Redis memory per user. Full memory arithmetic and the retention window decision are in Section 2.2. The Redis provisioning decision in Section 6.1 depends on this retention window being resolved first — see Section 2.2 for the ordering constraint.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs running at P2 priority. This is a product-visible consistency decision: during the fanout window, some followers have received the notification while others have not. The worst-case fanout completion time bound is derived from token bucket parameters in Section 3.2 — approximately 45 minutes for a 100,000-recipient event under sustained P0/P1 congestion. That bound is derived, not asserted. "5 minutes" is a target under normal conditions, not a bound.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Product must select one option before launch. Options are not equivalent in what they require from engineering.

- **Option A — Accept the consistency gap:** The fanout window (5-minute target, ~45-minute worst-case under congestion) is acceptable. No prior engineering deliverable required.
- **Option B — Accept the gap with UX mitigation:** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering deliverable required; frontend work needed.
- **Option C — Set a higher cap:** Product sets the cap. Engineering re-evaluates queue saturation risk and may require infrastructure changes. Allow one sprint for engineering review before option is accepted.
- **Option D — Reject batching entirely:** Requires engineering to produce a revised capacity estimate before this option can be accepted. That estimate is not currently scheduled. Allow two sprints. Selecting Option D without scheduling that work blocks the pre-flight gate; it cannot pass until the revised capacity estimate is produced and reviewed. If product wishes to pursue Option D after launch instead, the correct process is to open an engineering scoping ticket, schedule two sprints for the capacity estimate, and bring the result to the next planning cycle.

**Owner and deadline: Section 7.1.**

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**Escalation chain:** The backup named in Section 7.1 monitors whether the day-30 review has been documented. The backup's authority is time-triggered: if no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 procedure below without waiting for permission. The backup does not need to determine whose failure caused the gap before acting.

Residual gap: if the engineering lead is the reason the review did not occur, routing escalation through that lead reintroduces the failure. The backup's time-triggered authority addresses the common case. The uncommon case — all named people simultaneously unavailable or unresponsive by day 34 — is handled by Section 7.2, which names a specific role and explicit authority, not an org chart lookup.

**Month-1 traffic-conditional procedure (self-contained):**

```bash
# Step 1: Verify deployment names match what is recorded in Section 7.1.
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

# Step 4: Verify labels before any scaling command
kubectl get deployment push-worker-high \
  -o jsonpath='{.spec.selector.matchLabels}'
kubectl get deployment push-worker-bulk \
  -o jsonpath='{.spec.selector.matchLabels}'
```

**Traffic-conditional response:**

| Observed 24h volume | Action | Authority |
|---|---|---|
| < 30M/day | No scaling action. Document observation. Schedule review within 7 days. | On-call owner |
| 30M–55M/day | On plan or modestly above. Scale push-worker-high to 12 replicas, inapp-worker to 6. Document and notify engineering lead. | On-call owner |
| 55M–80M/day | Moderately above plan. Execute full 55M–80M/day row of traffic response