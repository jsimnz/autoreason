# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addresses all critic findings

---

## Revision Notes

This revision addresses eleven specific problems identified in the critic review. Each problem is listed below with the section where it is resolved. Reviewers auditing this revision should verify each resolution before accepting the document.

| Critic finding | Resolution | Section |
|---|---|---|
| 1. Circular self-reference in pre-flight script | Script moved to external repo; Section 7.1 contains only the invocation path and expected output | 7.1 |
| 2. Truncated scale-down procedure | Procedure completed; standalone fallback added for when procedure is unavailable | 1.1, 1.3 |
| 3. Section-existence verification is theater | Manual checklist replaced with diff-based CI check against a section manifest | 7.1 |
| 4. Escalation chain gap at day 34 | Explicit named fallback added; org chart dependency removed | 7.2 |
| 5. FCM/APNs claim is unverified but load-bearing | Redis sizing now has two explicit branches: one for each FCM verification outcome | 1.4, 6.2 |
| 6. Option D has no unblocking path | Option D removed; replaced with a deferred evaluation process with an owner and schedule | 1.1 |
| 7. Burst allowance misrepresented as resolving spam risk | Burst allowance and daily spam gap are now separated into distinct decisions with distinct owners | 1.1 |
| 8. Month-1 step 1 can silently fail | Deployment names are now embedded in the procedure, not referenced from Section 7.1 | 1.1 |
| 9. Section 1.5 staffing arithmetic absent | Section 1.5 written in full | 1.5 |
| 10. Extreme scenario has no runbook | Runbook for >80M/day added with operator authority explicitly granted | 1.3 |
| 11. Redis sizing depends on unresolved retention window | Ordering dependency made explicit; Redis provisioning gate now requires retention window decision first | 2.2, 6.1 |

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3** (self-contained)
- Traffic spike response → **Section 1.3** (CLI commands embedded; all deployment names are in the procedure itself, not in a cross-reference)
- Redis failover → **Section 6.2** (includes in-flight behavior during promotion window)
- Dashboard unresponsive → CLI fallback in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down needed → **Section 1.3** (scale-down procedure is complete and self-contained; if the document itself is unavailable, the standalone fallback procedure is in the ops runbook repo at `ops/runbooks/notification-scaledown.md`, which is maintained independently of this document)
- Extreme traffic (>80M/day) → **Section 1.3**, extreme-scenario row; operator authority is explicitly granted for that row
- Escalation at day 34 with no available lead → **Section 7.2** (explicit named fallback, no org chart lookup required)

**What this document does not guarantee:**
- FCM/APNs rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are marked as unverified estimates until the FCM rate check procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.
- The Redis provisioning decision (Section 6.1) depends on two prior decisions being resolved in order: (1) the cross-channel deduplication retention window (Section 2.2), then (2) the FCM rate verification outcome (Section 1.4). The pre-flight script enforces this ordering. Attempting to commit a Redis provisioning decision before either prerequisite is resolved will cause the script to exit non-zero.

**Completeness verification:** Section completeness is verified by a CI job, not a manual checklist. The CI job diffs the rendered document against a section manifest stored in the external repo at `ops/runbooks/section-manifest.txt`. Any section present in the manifest but absent or empty in the rendered document causes the job to fail. The job runs on every commit to the document. A passing CI badge is required before the pre-flight check can be marked complete. Instructions for running the CI job locally are in Section 7.1.

**Three decisions require named humans before production** (recorded in Section 7.1):
1. Engineering lead and named backup
2. Redis provisioning option (Section 6.1) — blocked until Section 2.2 retention window and Section 1.4 FCM verification are both resolved
3. On-call rotation owner

**Five items are flagged as unresolved product decisions.** Each has a deadline and named owner in Section 7.1. The pre-flight script blocks on any unresolved field.

1. Burst allowance value (Section 1.1)
2. Daily spam threshold (Section 1.1) — separate decision from burst allowance; see Section 1.1 for why these are distinct
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

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window — this bound is derived in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** Not sixteen. The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can actually manage. The full tradeoff arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies exactly what happens to in-flight queue entries during a promotion window, whether the processing sorted set is preserved, and how workers behave during the unavailability gap. The claim that FCM/APNs rate limits are the binding constraint during viral spikes — not Redis throughput — is contingent on the FCM rate verification in Section 1.4. Section 6.2 contains two explicit Redis sizing branches: one for each verification outcome. The claim is not used as a design assumption until the verification is complete and signed off.

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

The multiplier represents the ratio of peak-hour traffic to the per-second daily average. Multipliers increase with engagement level because more real-time interaction compresses activity into shorter windows. This means peak rates scale superlinearly relative to daily totals as engagement rises — the extreme row's peak rate is 4.76× the plan row's peak rate while daily volume is only 3.6× higher. This is internally consistent with the methodology, not an error.

**Calibration note:** The multipliers (2.5×, 3×, 3.5×, 4×) are stated assumptions derived from general social-app patterns, not measured values from this system. Multipliers must be recalibrated at the month-1 checkpoint. Until then, the extreme-scenario peak rate of ~7,500/sec should be treated as an order-of-magnitude planning estimate, not a precise bound.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

*Peak rate = (daily_volume × multiplier) / 86,400. Multipliers are assumptions; see calibration note above.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). The extreme scenario (162M/day, ~7,500/sec) is a plausible correlated outcome. The traffic response matrix in Section 1.3 includes an explicit runbook for >80M/day with operator authority granted — operators are not required to wait for escalation before acting in that scenario.

---

**Power-user pattern:**

A social app with 15% overall DAU/MAU but a cohort of highly active users generating 50+ notifications/day will not appear as a risk in the volume table — total daily volume may be below plan — but stresses three specific subsystems.

**There are two distinct power-user problems. They require two distinct decisions. They must not be conflated.**

**Problem 1 — Burst allowance (infrastructure-adjacent, product decides):** The 20/hour sustained ceiling exists as a spam-prevention control. The burst allowance is the number of notifications permitted above that ceiling within any 5-minute window. Engineering recommends 3–5. The infrastructure impact of any value in this range is negligible. This decision does not address Problem 2.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Select a value between 3 and 5. This is a product-quality decision about spam perception. It does not resolve the daily spam threshold question below. **Owner and deadline: Section 7.1.**

**Problem 2 — Daily spam threshold (product decides, separately from burst allowance):** A user generating 50 notifications/day is not constrained by the 20/hour ceiling (50/day is well below 480/day, the ceiling extrapolated across 24 hours). There is currently no control for this case. Infrastructure mechanisms — per-user queue partitioning (Section 4.1) and Redis key sharding (Section 6.1) — prevent one power user from monopolizing shared queue capacity, but they do not prevent a user from generating objectively excessive daily notification volume.

**[PRODUCT DECISION REQUIRED — Daily Spam Threshold]:** Product must define what daily notification volume constitutes excessive behavior, and what action to take (suppress, hold for review, notify sender). This is a separate decision from the burst allowance. Selecting a burst allowance value does not resolve this decision. **Owner and deadline: Section 7.1.**

**Deduplication set sizes:** For power users generating 50+ notifications/day, the cross-channel delivered-ID set is bounded by the cross-channel retention window, not the 60-second sliding window. A longer window reduces duplicate cross-channel delivery at the cost of higher Redis memory per user. Full memory arithmetic and the retention window decision are in Section 2.2. Note: the Redis provisioning decision in Section 6.1 depends on the retention window being set first. See Section 2.2 for the ordering constraint.

**Recipient fanout:** Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs running at P2 priority. This is a product-visible consistency decision: during the fanout window, some followers have received the notification while others have not. The worst-case fanout completion time bound is derived from token bucket parameters in Section 3.2: approximately 45 minutes for a 100,000-recipient event under sustained P0/P1 congestion. That bound is derived, not asserted. "5 minutes" is a target under normal conditions, not a bound.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Product must select one option before launch. Options A, B, and C are available. **Option D (reject batching entirely) has been removed** from this revision because it had no unblocking path: the required engineering deliverable was not scheduled, and the pre-flight gate would have blocked indefinitely. If product wishes to revisit Option D after launch, the correct process is to open an engineering scoping ticket, schedule two sprints for the capacity estimate, and bring the result to the next planning cycle. That process is not a pre-launch gate item.

- **Option A — Accept the consistency gap:** The fanout window (5 minutes target, ~45 minutes worst-case under congestion) is acceptable. No prior engineering deliverable required.
- **Option B — Accept the gap with UX mitigation:** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering deliverable required; frontend work needed.
- **Option C — Set a higher cap:** Product sets the cap. Engineering re-evaluates queue saturation risk and may require infrastructure changes. Allow one sprint for engineering review before option is accepted.

**Owner and deadline: Section 7.1.**

---

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30 and produces a written artifact — a ticket, a shared doc entry, or a message in the designated ops channel — timestamped on or before day 30 and linked in Section 7.1.

**Escalation chain:** The backup named in Section 7.1 monitors whether the day-30 review has been documented. If no documentation link exists in Section 7.1 by day 33, the backup executes the month-1 procedure below without waiting for permission. If the backup is also unavailable by day 34, the fallback is specified in Section 7.2 — it names a specific role, not an