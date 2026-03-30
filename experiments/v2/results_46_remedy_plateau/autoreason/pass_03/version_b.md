# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–120M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Substantive changes from previous version:**
- Peak multiplier labels now match the actual provisioning numbers (they didn't before)
- Synthetic load test scope is narrowed to what it can actually validate; external provider constraints are handled separately
- SMS cap Lua script is rewritten with `INCR`/`EXPIRE` instead of `GET`/`SET`/`INCR`; the atomicity guarantee is explained correctly
- Global SMS cap now has an explicit `dropped` delivery event, push/email fallback logic, and an on-call alert
- Delivery event log write rate is analyzed; async write path added for burst conditions with defined consistency tradeoff
- In-app WebSocket delivery defines polling interval, poll query, and maximum staleness explicitly
- E4 overlap is resolved by moving SMS STOP handling to E3 (preference/suppression owner); E2 cross-training is removed from month-1 scope
- Scaling trigger for self-operated infrastructure is rewritten as a leading indicator with a lower threshold
- DAU/MAU sensitivity analysis added; base case is recalibrated as median, not conservative
- Runbook template and review gate defined; "runbook exists" is separated from "runbook is verified"

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change.

#### 1.1.1 DAU/MAU Sensitivity

The previous version treated DAU = 30% of MAU as a fixed constant. It is not. DAU/MAU ratio is one of the most volatile metrics in social apps — it ranges from 15% to 65% depending on product stage, notification strategy, and retention curves. We model it explicitly:

| DAU/MAU Ratio | DAU (10M MAU) | Total/day (base 17/DAU) | Peak/sec (burst model) | Infrastructure posture |
|---------------|---------------|------------------------|------------------------|----------------------|
| 20% (low engagement) | 2M | 34M | ~8,000 | Base provisioning sufficient |
| **30% (base case)** | **3M** | **51M** | **~12,000** | **Base provisioning; scale trigger at 35%** |
| 50% (high engagement) | 5M | 85M | ~20,000 | Requires scale-up runbook before launch |
| 65% (top-quartile social) | 6.5M | 110M | ~26,000 | Architectural change required |

**What this means for provisioning:** The base case (30% DAU/MAU) is the median outcome for a social app at this stage, not a conservative one. We provision for base case and define an explicit trigger at 35% DAU/MAU sustained for 7 days (§1.4). The scale-up path (horizontal worker scaling, ElastiCache vertical scaling) handles up to the 50% scenario without architectural change. The 65% scenario requires per-channel queues and is a separate architectural decision with a 6-week lead time.

**How we measure it:** DAU/MAU is tracked via the existing analytics pipeline. The monthly metrics review (§1.4) checks this ratio. If the 7-day rolling average crosses 35%, the scale-up runbook (§7) is triggered before the next metrics review.

#### 1.1.2 Notification Volume Scenarios

| Scenario | Notifs/DAU/day | DAU (30% of MAU) | Total/day | Average/sec |
|----------|---------------|-------------------|-----------|-------------|
| Conservative | 5 | 3M | 15M | ~175 |
| **Base case** | **17** | **3M** | **51M** | **~590** |
| High | 40 | 3M | 120M | ~1,390 |

#### 1.1.3 Peak Provisioning: Numbers First, Labels Second

The previous version named a "10× multiplier" and then provisioned for different numbers. We state the provisioning targets first and derive the multipliers from them.

Notification spikes are correlated and event-driven. A single viral post generates simultaneous like/comment/share notifications. A celebrity join triggers bulk follow-suggestion notifications. These patterns concentrate volume:

- Base average: 590/sec
- Primetime concentration: ~50% of daily volume in a 3-hour window → ~2,360/sec sustained
- Correlated viral spike on top of primetime: 4–5× primetime rate for 5–10 minutes → ~10,000–12,000/sec

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (8.5× daily average, ~2× primetime sustained rate)
- **Burst capacity: 12,000/sec** (20× daily average, ~5× primetime rate)

We do not label these as "10×." The sustained target is 8.5× average; the burst target is 20× average. Queue depth is the shock absorber for bursts above 5,000/sec — workers drain the backlog after the spike. Over-provisioning workers for 12,000/sec continuous capacity would be wasteful 99% of the time; over-provisioning queue depth costs almost nothing.

**Infrastructure implication:** Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge (benchmarks show >100K ops/sec for simple sorted set operations). Worker pool targets 5,000/sec throughput; bursts above that queue and drain within minutes.

#### 1.1.4 Infrastructure Provisioning: Synthetic Load Testing Scope

We provision infrastructure from the model above before launch and validate with synthetic load testing. The previous version overstated what synthetic testing can validate. We are specific:

**What the month-1 load test validates:**
- Queue throughput: can the Redis sorted set handle 3,500 enqueue/dequeue ops/sec without latency degradation?
- Worker throughput: can 40 workers process 3,500 messages/sec without backlog accumulation?
- Database write rate: can RDS handle delivery event log writes at 3,500/sec × 3 events/notification = 10,500 inserts/sec? (See §2.4 for why this is the critical constraint)
- Preference cache hit rate: does the Redis preference cache sustain >95% hit rate under synthetic load?

**What the month-1 load test cannot validate:**
- FCM/APNs behavior under load. FCM throttles new senders at ~2,000/sec; APNs has per-certificate rate limits. These constraints only appear with real tokens and real provider connections. We test this separately in month 2 with a limited production rollout (§6.2).
- SendGrid IP warming constraints. A new IP sending 1.9M emails/day immediately will be throttled or blacklisted. IP warming is a 4–6 week process that begins in month 2, not something a load test validates (§4.2).
- Twilio carrier rate limits. Carrier throughput caps per long code (~1 msg/sec) or short code (~100 msg/sec) are tested against Twilio's sandbox in month 2.
- Real token distribution. Expired/invalid tokens in production will generate a failure pattern the synthetic test cannot replicate.

**Resolution for provider constraints:** Month 2 includes a 5% production rollout specifically designed to surface provider-side limits before full launch (§6.2). Provider limits are not validated by staging; they are validated by controlled production exposure.

**Provisioning timeline:**
- End of month 1: ElastiCache r6g.xlarge, RDS db.r6g.2xlarge, 40 delivery workers provisioned and synthetic load tested
- Weeks 1–2 post-launch (5% rollout): Instrument actual provider error rates and adjust worker concurrency per channel
- Scale-up path without architectural change: ElastiCache vertical scaling with <60-second failover; worker count scales horizontally

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications would cost ~$2.9M/year at 2% volume. We treat SMS as a privileged channel reserved for authentication and security.

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---------|-------------|------------|-----------|------------|-------|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

**Hard SMS cap — atomically enforced:**

The previous version used a `GET` → conditional `SET`/`INCR` sequence and claimed it eliminated race conditions. The actual reason Lua scripts are race-condition-free is that Redis executes them atomically — no other command runs between any two operations in the script. The script structure was also unnecessarily complex. We rewrite it using `INCR` with conditional `EXPIRE`:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded
-- KEYS[1]: "sms_cap:{user_id}:{date_utc}"
-- ARGV[1]: cap (integer, e.g. 3)
-- ARGV[2]: ttl in seconds until midnight UTC

local key = KEYS[1]
local cap = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local count = redis.call('INCR', key)

if count == 1 then
    -- First increment: set expiry so key resets at midnight UTC
    redis.call('EXPIRE', key, ttl)
end

if count <= cap then
    return 1
else
    return 0
end
```

**Why this is correct:** `INCR` creates the key if it doesn't exist (initializing to 1) and increments atomically. The `EXPIRE` is set only on the first increment to avoid resetting the TTL on subsequent calls. Two simultaneous routing decisions serialize on this script because Redis Lua execution is single-threaded — one script completes before the other begins. If count exceeds cap, the increment has already happened, meaning the counter is slightly over cap, not under. This is acceptable: at a cap of 3, the counter may reach 4 or 5 under high concurrency before all in-flight scripts return 0, but the overshoot is bounded by the number of concurrent workers routing for this user simultaneously, which is typically 1–2. For SMS cost control, a 1–2 message overshoot per user per day is acceptable. If exact enforcement is required, use a `GET`-then-`INCR` pattern with optimistic locking, which adds latency.

**Global daily cap** of 200K non-auth SMS is enforced via a separate atomic counter at the router. When the global cap is reached, non-auth SMS is not silently dropped — see §1.2.1 for the full handling.

#### 1.2.1 Global SMS Cap: Fallback and Observability

The previous version dropped notifications silently when the global cap was hit. A notification that passes per-user checks and then vanishes will appear in no failure metric. We define explicit behavior:

1. **Delivery event written first.** Before the drop decision, a `delivery_events` row is written with `event_type = 'channel_fallback'` and `metadata = {"reason": "global_sms_cap", "fallback_channel": "push"}`. This ensures the notification is traceable.

2. **Fallback to push, then email.** If the recipient has push enabled, the notification is re-routed to push. If not, to email. If neither is available, the event is written as `dropped` with `metadata = {"reason": "global_sms_cap_no_fallback"}`.

3. **On-call alert fires at 80% of cap.** At 160K non-auth SMS sent in a day, PagerDuty fires a warning-level alert. At 100% (200K), it fires a critical alert. The on-call engineer decides whether to raise the cap (requires EM approval, documented in runbook §7.2) or let the fallback logic handle remaining volume.

4. **Auth SMS is always exempt.** Auth SMS uses a separate counter with a cap of 10/day per user and no global daily limit. OTP abuse is handled by rate limiting at the auth layer, not the notification layer.

### 1.3 Team Allocation

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary / Backup |
|----------|----------------------|--------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers, reliability/monitoring infrastructure | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user-facing API, suppression logic, in-app notifications, WebSocket layer, **SMS STOP/carrier suppression handling** | Backup: E4 |
| E4 | Email (SendGrid) + SMS send path (Twilio), webhook processing for email events, deployment pipelines | Backup: E2 |

**Why SMS is split between E3 and E4:**

The previous version had E4 own all of SMS. SMS has two distinct concerns that map cleanly to existing ownership boundaries:

- **Send path** (Twilio API calls, carrier error handling, delivery receipts): This is a webhook-heavy delivery integration, adjacent to email. E4 owns it.
- **STOP handling and carrier suppression lists**: A user texting STOP to our short code is a preference change. It belongs in the same system as email unsubscribes, push opt-outs, and user-managed preferences. E3 owns it.

This split eliminates the E4 overlap problem: E4's month-1 work is email webhooks; SMS send path is month-2 work. E3's STOP handling work is month 2, after the preference management system (month 1) is stable. The two workstreams no longer compete.

**E2 cross-training removed from month-1 scope.** The previous version proposed documenting E2 on email webhook schema by end of month 1 as a mitigation for E4 overload. This created an unanalyzed workload conflict with E2's own month-1 deliverable (APNs + FCM integration). Cross-training is deferred to month 3, after both integrations are stable. Month-1 bus factor risk is accepted and mitigated by runbooks (§1.3.1) rather than cross-training.

#### 1.3.1 Runbook Standard

The previous version required runbooks by end of month 1 with no definition of what a runbook must contain and no review gate. A runbook written under delivery pressure without a template is likely to be a list of commands with no context. We define a minimum standard:

**Required sections for every integration runbook:**
1. **Service overview**: What this integration does, what breaks if it's down, and which notifications are affected
2. **Health checks**: Specific commands or dashboard links to verify the integration is functioning; expected outputs
3. **Common failure modes**: At least 3 documented failure scenarios with observed symptoms, root cause, and resolution steps
4. **Escalation path**: Who to page, at what severity, and what information to gather before paging
5. **Rollback procedure**: How to disable this channel without affecting others (circuit breaker location, feature flag name)
6. **External provider contacts**: Support URLs, SLA commitments, and account credentials location (not in the runbook — pointer to secrets manager)

**Review gate:** Runbooks are reviewed by the backup engineer (see allocation table above) before end-of-month-1 sign-off. A runbook is not "done" until the backup engineer confirms they could execute it without the primary engineer present. E1 tracks runbook completion status