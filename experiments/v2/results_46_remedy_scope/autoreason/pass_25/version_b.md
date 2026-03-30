# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 2 — Addressing Structural, Technical, and Operational Deficiencies

---

## Revision Notes

This revision addresses specific deficiencies identified in review. Changes are substantial enough that readers familiar with the previous version should treat this as a replacement, not an amendment. Major changes:

- Section 7.1 and Section 7.2 are now present and complete
- Section 1.5 (staffing analysis) is now present and shows its reasoning
- The escalation chain has been redesigned to address systemic failure, not just individual failure
- The correlated sensitivity table methodology has been corrected
- The deduplication architecture now explicitly resolves the sliding window / cross-channel interaction
- The power-user rate limiting is now consistent with the volume model
- The fanout cap now specifies queue priority for batched jobs
- The orphaned entry recovery window is now stated explicitly
- The month-1 response table is complete
- The pre-flight check tooling is scoped and its implementation status is explicit
- The 6-month timeline now has milestone structure

Items that remain open are marked explicitly as open, with the reason they cannot be closed in this document.

---

## How to Use This Document

**Under incident conditions, go directly to what you need:**
- Queue backup or worker failure → **Section 4.3**
- Traffic spike response → **Section 1.3** (self-contained; CLI commands embedded)
- Redis failover → **Section 6.2**
- Dashboard unresponsive → CLI fallback in **Section 1.3**
- After-hours spike in month 1 before auto-scaling is live → **Section 1.3c**
- Scale-down with unavailable lead → **Section 7.2**

**Self-completeness policy:** Every section reference in this document refers to a section that exists in this document. If you find a reference to a section that does not exist, that is a defect. File it against the engineering lead. Do not proceed with the referenced action until the section is produced. This policy is checkable: the table of contents lists every section. A reader can verify completeness without reading the full document.

**What this document cannot guarantee:** FCM rate limits are not contractually specified by Google or Apple. P1 delay figures in Section 1.4 are marked as unverified estimates until the pre-launch FCM rate check procedure in Section 1.4 is complete and signed off by the engineering lead. Do not use P1 delay figures as SLA commitments until that sign-off exists.

**Three decisions require named humans before production.** Placeholder text in any of these fields causes the pre-flight check (Section 7.1) to return a non-zero exit code, blocking the deployment pipeline. The pre-flight check is a shell script; its implementation status and location are specified in Section 7.1.

1. Engineering lead and named backup (Section 7.1)
2. Redis provisioning option — Option A or Option B — resolved in Section 1.3a and recorded in Section 7.1
3. On-call rotation owner (Section 7.1)

**Four items are flagged as unresolved product decisions.** Each appears with a [PRODUCT DECISION REQUIRED] marker. Each has a specific deadline and named owner field in Section 7.1. Deadlines are set relative to the launch date, which is recorded in Section 7.1 when known. If the launch date is not yet recorded, the relative deadlines still apply from the date of first deployment to staging.

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
   - 7.1 Pre-Flight Checklist and Named Owners
   - 7.2 Escalation and Authorization Thresholds
8. Build Timeline

---

## Executive Summary

This design covers a notification system handling approximately 45M notifications/day across push, email, in-app, and SMS channels for a 10M MAU social app, built by 4 engineers in 6 months.

**The staffing constraint is a design input.** Four engineers over 6 months cannot build and safely operate a system of arbitrary complexity. Section 1.5 contains the staffing analysis, including the arithmetic that drove the reduction from a theoretical maximum of 16 worker deployments to 6. That analysis is present and checkable in this document.

**Four core architectural decisions:**

**1. Four isolated priority queues (P0–P3)** with TTL enforcement and a token bucket for starvation prevention. Section 3.2 specifies the conditions under which P2/P3 can still be deferred despite the token bucket.

**2. ID-based queue entries with a Redis Sorted Set for processing state.** Workers fetch full payloads from PostgreSQL on dequeue. Crash recovery reclaims orphaned entries within a 90-second window. This bound is explicit and is derived in Section 4.2. Worst-case delivery outcome is duplication, not loss.

**3. Six worker deployments covering four channels and two priority tiers.** The cost is some loss of priority isolation within non-push channels. The benefit is an operational surface area that 4 engineers can manage. The full arithmetic is in Section 1.5.

**4. Redis primary/replica with bounded failover.** Section 6.2 specifies what happens to in-flight queue entries during a promotion window. The binding constraint during viral spikes is FCM/APNs throughput, not Redis throughput. This claim is contingent on the FCM rate verification in Section 1.4 and is marked as unverified until that procedure completes.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day planning figure for a mid-engagement social app.

**Correlation between inputs:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both simultaneously. The sensitivity table reflects joint scenarios. Treating them as independent understates high-engagement risk.

**Peak multiplier methodology:** The multiplier converts daily volume to peak per-second rate. The correct formula is:

```
peak_rate = (daily_volume × peak_multiplier) / 86,400
```

The multiplier represents the ratio of peak-hour traffic to the per-second daily average, scaled to reflect how many hours of daily volume concentrate into the peak hour. A 3× multiplier means the peak hour contains 3× the traffic of an average hour — equivalently, the peak second within that hour runs at 3× the daily average per-second rate.

**Multiplier calibration by engagement level:**

- **Low engagement (15% DAU/MAU):** Flatter intraday distribution. Social activity spread across the day rather than concentrated in an evening window. Multiplier: 2.5×.
- **Plan (30% DAU/MAU):** Mid-engagement behavior. Evening peak lasting approximately 2–3 hours. Multiplier: 3×. This is the planning target.
- **High engagement (50% DAU/MAU):** More real-time interaction. Activity compresses into a shorter peak window. Multiplier: 3.5×.
- **Extreme (65% DAU/MAU):** Viral growth scenario. Sharp, short peaks. Multiplier: 4×.

**Consistency check on the extreme scenario:** The extreme row produces 162M/day at 4× = ~7,500/sec peak. The plan row produces 45M/day at 3× = ~1,575/sec peak. The ratio of peak rates is 7,500/1,575 = 4.76×. The ratio of daily volumes is 162/45 = 3.6×. The peak rate grows faster than daily volume (4.76× vs. 3.6×) because the multiplier increases from 3× to 4× simultaneously with the volume increase. This is consistent with the stated rationale: higher engagement compresses activity, so peak rates scale superlinearly relative to daily totals. The math is internally consistent with the methodology.

**Correlated sensitivity table:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak multiplier | Peak rate |
|---|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | 2.5× | ~434/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **3×** | **~1,563/sec** |
| High engagement | 50% | 5M | 20 | 100M | 3.5× | ~4,051/sec |
| Extreme (viral) | 65% | 6.5M | 25 | 162M | 4× | ~7,500/sec |

*Peak rate = (daily_volume × multiplier) / 86,400. Previous version had arithmetic errors in the low and high rows; corrected here.*

**Planning decision:** Size for 45M/day (~1,563/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Power-user pattern:**

A social app with 15% overall DAU/MAU but a cohort of highly active users generates concentrated write load on specific subsystems regardless of total daily volume. Three subsystems are stressed:

- **Per-user rate limiting:** Concentrates write load on specific Redis keys. See interaction with volume model below.
- **Deduplication set sizes:** See Section 2.2.
- **Recipient fanout:** See fanout cap discussion below.

**Rate limiting and volume model consistency:** The per-user sustained rate limit is 20 notifications/hour = 480/day. The extreme scenario uses 25 notifications/day as the population average. These figures operate at different levels of analysis and do not conflict: the 25/day figure is a population mean across all active users including low-activity users; the 480/day figure is the per-user ceiling. However, the previous version presented the 20/hour limit as protection against power-user stress without acknowledging that 20/hour is 480/day — a ceiling that is 19× the extreme scenario's average. A user hitting the rate limit is generating 480 notifications/day; the rate limit provides no meaningful protection against users generating 50–100 notifications/day, which is the actual power-user stress case.

**Revised rate limiting design:** The 20/hour sustained limit is retained as a spam-prevention ceiling. Power-user infrastructure stress is addressed separately through per-user queue partitioning (Section 4.1) and Redis key sharding (Section 6.1), not through rate limiting. The rate limit is a product-quality control, not an infrastructure protection mechanism.

**[PRODUCT DECISION REQUIRED — Burst Allowance]:** Engineering recommends a burst allowance of 3–5 notifications above the 20/hour sustained rate within any 5-minute window. Product must select a value. This is a product-quality decision (spam perception), not an infrastructure decision. The infrastructure impact of any value in the 3–5 range is negligible. **Owner field and deadline: Section 7.1.** The deployment pipeline will not clear the pre-flight check until a value is recorded in Section 7.1.

**Fanout cap:**

Fanout is capped at 10,000 recipients per event. Excess recipients are processed in batched jobs. Batched fanout jobs run at **P2 priority** — below organic P0 (critical) and P1 (time-sensitive) traffic, but above P3 (bulk/marketing). The 5-minute window is a target under normal load conditions. Under sustained high load where P2 queues are congested, the fanout window expands. The token bucket in Section 3.2 guarantees P2 gets minimum throughput even under P0/P1 pressure, which bounds the expansion: at minimum guaranteed P2 throughput (specified in Section 3.2), the worst-case fanout completion time for a 100,000-recipient event is approximately 45 minutes. This is a product-visible consistency gap: some followers receive the notification significantly before others.

This is also an ordering problem, not just a latency problem: batched fanout jobs at P2 compete with other P2 traffic. The token bucket prevents complete starvation but does not guarantee the 5-minute target under congestion. Product must understand that "5 minutes" is a target under normal conditions, not a bound.

**[PRODUCT DECISION REQUIRED — Fanout Cap]:** Product must select one option before launch. Options are not equivalent in engineering requirements:

- **Option A — Accept the consistency gap:** The batched fanout window (5 minutes target, up to ~45 minutes worst-case under congestion) is acceptable. No prior engineering deliverable required.
- **Option B — Accept the gap with UX mitigation:** Gap is acceptable; engagement indicators suppressed until fanout completes. No prior engineering deliverable required; frontend work needed.
- **Option C — Set a higher cap:** Product sets the cap. Engineering re-evaluates queue saturation risk. Allow one sprint for engineering review before option is accepted.
- **Option D — Reject batching entirely:** Requires engineering to produce a revised capacity estimate before this option can be accepted. Allow two sprints. Selecting this option without scheduling the estimate blocks the deployment checklist gate.

**Owner field and deadline: Section 7.1.**

**Month-1 checkpoint:**

The on-call rotation owner reviews month-1 traffic data by day 30.

**Escalation design — systemic failure addressed explicitly:** The previous version added a named backup to handle the case where the engineering lead caused the failure. A reviewer correctly noted that the same organizational failure causing the lead and on-call owner to miss the review likely also affects the backup. This is true. The revised design accepts this limitation and addresses it differently:

The escalation chain (on-call owner → engineering lead → named backup) handles individual and small-group failures, which are the common case. It does not handle organizational failure, which would manifest as all three named people being simultaneously unavailable or compromised. Organizational failure at that level is outside the scope of a runbook — it requires executive intervention and is not something a notification system design document can resolve. The document's job is to handle the common case reliably and to make the organizational failure case visible rather than to pretend it can be resolved within the document.

**Practical implication:** If all three named people have missed the day-33 trigger, the correct action for anyone who notices is to escalate to whoever is above the engineering lead in the org chart. This document cannot name that person because org charts change. The document names the pattern, not the person.

**Month-1 traffic-conditional procedure (self-contained):**

```bash
# Step 1: Verify deployment names match Section 7.1 checklist before any action
kubectl get deployments -l app=notification-worker
# If names do not match, stop and contact engineering lead before proceeding.

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
# Labels can drift if deployments were recreated. Confirm before using label selectors.
kubectl get deployment push-worker-high -o jsonpath='{.spec.selector.matchLabels}'
kubectl get deployment push-worker-bulk -o jsonpath='{.spec.selector.matchLab