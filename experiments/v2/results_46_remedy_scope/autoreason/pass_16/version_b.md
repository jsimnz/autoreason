# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The architecture is built around four core decisions:

1. **Four isolated priority queues (P0–P3)** with TTL enforcement via a dedicated sweep process and worker-side backstop. Starvation prevention uses an atomic token bucket implemented as a Lua script with explicit bucket parameters (Section 3). The token bucket does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation — it rate-limits, not protects. The conditions under which P2/P3 starvation occurs despite the token bucket are specified in Section 3.2.

2. **ID-based queue entries with a Redis Sorted Set for processing state.** The processing Sorted Set tracks in-flight messages and is the mechanism for crash recovery. The crash recovery mechanism has a documented gap: if the worker instance hosting the recovery goroutine crashes and the container is destroyed, processing set entries for that instance may be orphaned. The mitigation is a cross-instance recovery sweep described in Section 2.1. PostgreSQL pool exhaustion risk is quantified with arithmetic shown in full in Section 2.1. The worst-case P1 delay under coincident failure is **20–40 minutes under a standard spike, and 50–70 minutes if a DB issue outlasts the spike** — both figures are derived step-by-step.

3. **Per-channel, per-priority worker pools** implemented as specialized binaries per channel type. The traffic response matrix in Section 1.3 names the specific worker type to provision at each threshold. Redis resizing is not a same-day operation in most managed environments; the matrix now specifies what to do when it is not.

4. **Redis primary/replica with bounded failover.** The binding constraint during viral spikes is FCM/APNs rate limits. The FCM rate limit used in the spike analysis (10,000/sec) is a planning assumption. If pre-production load testing shows the actual limit is below 2,000/sec, the architecture requires re-evaluation. Because this document cannot specify a replacement architecture without knowing the actual limit, Section 1.4 specifies what the re-evaluation must address and what the conservative fallback operating mode is during that re-evaluation period.

**Decisions requiring named humans before production.** Three decisions require recorded sign-off. The mechanism is a deployment checklist gate. For each decision, this document now specifies the default action if the decision is not recorded — not recording a decision is treated the same as recording the conservative option.

**Personnel change protocol.** The four-person team creates real risk that named decision-makers leave or become unavailable. Section 7 specifies the role-based fallback chain (not person-based) that activates when a named individual is no longer available. Named individuals are re-confirmed at each 30-day checkpoint; a departure triggers immediate re-assignment, not deferred resolution.

**What this document does not claim:**
- FCM rate limits are not knowable in advance. The spike analysis uses a planning assumption, quantifies sensitivity, and specifies a required pre-production load test. If the load test invalidates the assumption, Section 1.4 specifies the fallback operating mode and what the re-evaluation must cover.
- The backoff ramp-up during post-spike drain is not a synchronized fleet-wide event. Individual workers desynchronize. The drain rate during the ramp window is variable, not a clean percentage. Section 1.4 now presents the drain timeline as a range, not a point estimate.
- The DAU/MAU ratio and notifications-per-user are correlated, not independent. The sensitivity table now presents joint scenarios reflecting this correlation.
- Deduplication is specified in full in Section 2.2, including memory bounds at stated traffic volumes.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** 30% planning figure. Valid range for unspecified social apps: 15–50%.

**Notifications per active user per day:** 15/day as a planning figure for a mid-engagement social app.

**Correlation note:** DAU/MAU ratio and notifications-per-user are positively correlated — higher engagement drives both metrics simultaneously. The sensitivity table reflects this: the low scenario uses both a low DAU/MAU ratio and a low notification rate; the high scenario uses both high values. Treating them as independent would understate the joint variance. The cross-scenarios (high DAU/MAU × low notification rate) are plausible but less likely than the correlated cases and are omitted to avoid false precision.

**Average-peak sensitivity table — correlated scenarios:**

| Scenario | DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---|---|---|---|---|---|
| Low engagement | 15% | 1.5M | 10 | 15M | ~525/sec |
| **Plan** | **30%** | **3M** | **15** | **45M** | **~1,575/sec** |
| High engagement | 50% | 5M | 20 | 100M | ~3,500/sec |
| Extreme (viral growth) | 65% | 6.5M | 25 | 162M | ~5,670/sec |

The extreme scenario is included because the team has 6 months to build this. If the app grows faster than expected, the architecture must not silently fail — it must degrade predictably. The traffic response matrix in Section 1.3 covers through ~225M/day.

**Planning decision:** Size for 45M/day (~1,575/sec sustained peak). Validate actual rate within the first 30 days of production traffic.

**Month-1 checkpoint — missed checkpoint default:** If month-1 traffic data is not reviewed by day 35, the engineering lead defaults to provisioning for the high engagement scenario (100M/day) until the review occurs. This default is recorded in the runbook before production launch.

### 1.2 Channel Split and Volume Accounting

Push and in-app are not additive from the user's perspective when a user is actively connected, but they are additive in system write load. The same event writes an in-app notification record and queues a push notification. Push suppression when a user is connected via WebSocket is an optimization at the notification router, not an assumption baked into the volume model.

A viral spike drives push and in-app saturation simultaneously because they are triggered by the same upstream events. The traffic response matrix accounts for this correlated failure mode.

| Channel | Share | Daily volume | Peak demand |
|---|---|---|---|
| Push (FCM + APNs) | 70% | 31.5M/day | ~1,094/sec |
| In-app (write to store) | 20% | 9M/day | ~315/sec |
| Email | 8% | 3.6M/day | ~125/sec |
| SMS | 2% | 0.9M/day | ~31/sec |

FCM and APNs each handle approximately 50% of push volume: ~547/sec each at peak.

### 1.3 Traffic Response Matrix

Decisions are pre-specified to avoid reactive calls made under pressure. Workers are specialized by channel type (Section 3), so the matrix names the specific worker type to provision at each threshold.

**Named decision owner:** Before production launch, the engineering lead and their named backup are recorded in the runbook. Both names are filled in before production; placeholder text blocks the deployment checklist. If a named individual leaves the team or is unavailable for more than 5 business days, Section 7's role-based fallback chain activates immediately.

**Redis resizing is not a same-day operation.** In most managed cloud environments (ElastiCache, Memorystore, Upstash), resizing a Redis instance requires either pre-provisioned replica promotion or instance replacement with a brief failover. The "same day" response for the 45M–80M/day band requires one of the following to already be true: (a) a larger Redis instance is pre-provisioned as a replica and promotion is scripted, (b) the primary instance was initially provisioned with headroom for this band, or (c) the team accepts 15–30 minutes of Redis unavailability during resizing. Option (b) is the default: the initial Redis instance is provisioned at the 80M/day capacity level, accepting the cost of over-provisioning at launch. If this is not acceptable for cost reasons, option (a) must be prepared before production launch. This is a pre-production decision recorded in the deployment checklist.

**Identifying which worker type is saturated:** Each worker type emits a `queue_depth` metric tagged by channel and priority. The runbook instructs on-call engineers to check the per-channel queue depth dashboard before provisioning.

**Dashboard reliability during incidents:** The per-channel queue depth dashboard may be slow or stale during the same Redis pressure event causing the alert. The runbook specifies a CLI fallback if the dashboard is unresponsive for more than 2 minutes:

```bash
LLEN queue:push:p1
LLEN queue:push:p2
LLEN queue:inapp:p1
LLEN queue:email:p1
```

The engineer does not need to reason from first principles at 3 AM. This CLI fallback is a runbook requirement, not a suggestion.

| Measured daily volume | Classification | Response — specific worker types | Confirmation metric | Escalation if unconfirmed |
|---|---|---|---|---|
| < 7.5M/day | Well below plan | Scale down push worker instances (largest pool) | Queue depth < 1K sustained | Re-review at 2 weeks |
| 7.5M–45M/day | On plan | No action | P99 dispatch latency < 2s | Alert if latency exceeds 5s for >10 min |
| 45M–80M/day | Moderately above plan | Check `queue_depth{channel=push}` and `queue_depth{channel=inapp}` first — these co-saturate. Provision push workers + in-app write capacity. If email queue also rising, add email workers. Redis resizing: use pre-provisioned replica promotion (option a) or accept 15–30 min unavailability (option c). Option (b) — pre-provisioned headroom — means no action needed here. | Queue depth returning to baseline within 30 min | Escalate to engineering lead |
| 80M–225M/day | Significantly above plan | Above, plus shard queue namespace by user ID range — 1 week of engineering. Engineering lead makes go/no-go. | Throughput > 80M/day sustained with P99 < 2s | Convene architectural review if not confirmed within 2 weeks |
| > 225M/day | Severely above plan | Defer SMS and email to month 4; one engineer assigned to re-architecture | Re-architecture delivering > 225M/day with P99 < 2s | Engineering lead + role-based backup make go/no-go at 3-week checkpoint |

**Manual response timing — honest estimates under degraded conditions:**

*Automated trigger (auto-scaling rule, month 2 onward):*
- Metric evaluation + instance boot + worker start: ~2–3 minutes

*Manual, runbook available, dashboard loading normally:*
- Engineer wakes, reads alert, opens runbook: ~2 minutes
- Queries per-channel queue depth: ~1–3 minutes
- Executes scaling command: ~2 minutes
- Instance boot + confirmation: ~3 minutes
- **Total: ~8–10 minutes**

*Manual, runbook available, dashboard degraded:*
- Engineer wakes, reads alert: ~2 minutes
- Dashboard unresponsive; switches to CLI fallback per runbook: ~3 minutes
- Executes scaling command: ~2 minutes
- Instance boot + confirmation via CLI: ~3 minutes
- **Total: ~10–15 minutes**

*Manual, no runbook, 3 AM (first 30 days):*
- **Total: 20–30 minutes.** The runbook is a month-1 deliverable with a specific completion date. If not complete by day 30, the engineering lead is notified and the system operates under this assumption until complete.

### 1.4 Viral Spike Analysis

**The FCM rate limit cannot be confirmed in advance.** FCM does not publish per-project rate limits with contractual precision. Load testing a staging project produces useful signal but not a production guarantee.

**Pre-production action:** Load test push dispatch against a staging project at 2×, 5×, and 10× planned peak. Record the rate at which 429 responses begin. Use the observed rate as the planning assumption.

**If load testing shows the observed limit is below 2,000/sec:** The priority queue structure's P1 protection claims are materially wrong. The architecture requires re-evaluation before launch. This re-evaluation must address: (a) whether to store full payloads in Redis to eliminate the DB dependency, (b) whether to reduce the number of priority tiers to concentrate capacity, and (c) whether SMS and email channels should be deferred entirely until push capacity is understood. During the re-evaluation period, the system operates in a conservative fallback mode: P0 (security/auth) only, all other channels queued but not dispatched, with a maximum re-evaluation window of 2 weeks before a go/no-go decision is made. This is a pre-production gate.

**Sensitivity table:**

| Assumed FCM limit | Binding constraint at 20× spike | P1 DM behavior |
|---|---|---|
| 500/sec | FCM limit | P1 delays measured in hours; architecture re-evaluation required |
| 2,000/sec | FCM limit | P1 delays 15–30 min during sustained spike; re-evaluation gate triggered |
| **10,000/sec (plan)** | FCM limit | P1 largely protected; P2/P3 accumulate |
| > 26,000/sec | Worker capacity | Worker capacity becomes binding before FCM |

**Post-spike recovery — arithmetic with honest uncertainty:**

Assumptions: 10-minute sustained spike, FCM limit 10,000/sec, 20× demand spike producing ~21,000/sec push demand.

Accumulation during spike:
- FCM can dispatch: 10,000/sec
- Demand: ~21,000/sec
- Net accumulation: ~11,000/sec
- Over 10 minutes: 11,000 × 600 = **6,600,000 messages queued**

**Backoff desynchronization:** During a sustained spike, individual worker instances accumulate FCM backoff state independently based on when they started retrying. FCM's documented backoff under sustained 429 responses reaches approximately 32 seconds between retry attempts (5 doublings from a 1-second base), but different worker instances will reach this ceiling at different times depending on their retry history. The fleet does not reset uniformly. 

The consequence is that the drain rate during the 0–90 second post-spike window is **highly variable**, not a clean 20–40% of capacity. Some workers will be near the backoff ceiling; others will have reset already. The practical effect is that the drain timeline has meaningful uncertainty in the early post-spike window. Rather than presenting a clean timeline, the table below presents ranges reflecting this variability:

| Scenario | Spike duration | DB issue duration | Messages queued | Post-spike drain rate (0–90s) | Post-spike drain rate (90s+) | P1 delay range |
|---|---|---|---|---|---|---|
| Spike only, no DB issue | 10 min | 0 | 6.6M | 30–70% of capacity (desync) | ~10,000/sec net | **15–25 min** |
| Spike + DB issue, DB recovers first | 10 min | 8 min | 6.6M | 30–70% of capacity | ~10,000/sec net | **15–25 min** |
| Spike + DB issue, co-terminus | 10 min | 10 min | 6.6M | 30–70% of capacity | ~10,000/sec net | **15–25 min** |
| Spike ends, DB issue persists 20 min more | 10 min | 30 min total | 6.6M + continued accumulation | Partial until DB recovers | Partial then full | **50–80 min** |

The worst case is not the spike — it is a DB slow-query event that outlasts the spike. The 50–80 minute figure for this scenario requires a product decision before production. **Default if decision is not recorded:** treat the 50–80 minute worst case as accepted. This is the conservative default because the alternative (full payload in Redis) requires active provisioning and cost decisions that cannot be made silently. If the product lead and engineering lead want to avoid this worst case, they must actively choose full payload storage and record that decision with names and date before production launch.

---

## 2. Queue Architecture

### 2.1 Queue Storage — ID-Based with Processing Sorted Set

**Decision: ID-based.** Queue entries contain only the notification ID; workers fetch