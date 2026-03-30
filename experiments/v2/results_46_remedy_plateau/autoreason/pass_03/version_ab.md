# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–120M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Key design decisions made explicitly:**
- DAU/MAU ratio is modeled as a variable, not a fixed constant — it drives provisioning and scaling triggers
- Peak provisioning targets are stated first; multiplier labels are derived from them, not assumed
- Synthetic load testing scope is bounded to what it can actually validate; provider constraints are handled via controlled production rollout
- SMS caps use `INCR`/`EXPIRE` Lua scripts with explicit atomicity guarantees and bounded overshoot analysis
- Global SMS cap triggers fallback routing and on-call alerts rather than silent drops
- In-app notifications bypass the queue but share unified delivery event log and retry semantics
- Scaling triggers have explicit owners, thresholds, and lead times — no "revisit at 50M MAU" deferrals
- SMS ownership is split cleanly between send path (E4) and suppression/preference handling (E3)
- Runbooks require a defined template and backup-engineer review gate, not just existence

We ship a working system by end of month 2, iterate through month 5, and harden in month 6. No engineer owns more than two channel integrations.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change.

#### 1.1.1 DAU/MAU Sensitivity

DAU/MAU ratio is one of the most volatile metrics in social apps — it ranges from 15% to 65% depending on product stage, notification strategy, and retention curves. Treating it as a fixed constant produces a single-point model that is almost certainly wrong. We model it explicitly:

| DAU/MAU Ratio | DAU (10M MAU) | Total/day (base 17/DAU) | Peak/sec (burst model) | Infrastructure posture |
|---|---|---|---|---|
| 20% (low engagement) | 2M | 34M | ~8,000 | Base provisioning sufficient |
| **30% (base case)** | **3M** | **51M** | **~12,000** | **Base provisioning; scale trigger at 35%** |
| 50% (high engagement) | 5M | 85M | ~20,000 | Scale-up runbook required before launch |
| 65% (top-quartile social) | 6.5M | 110M | ~26,000 | Architectural change required; 6-week lead time |

The base case (30% DAU/MAU) is the median outcome for a social app at this stage, not a conservative one. We provision for the base case and define an explicit trigger at 35% DAU/MAU sustained for 7 days (§1.4). The scale-up path — ElastiCache vertical scaling and horizontal worker scaling — handles the 50% scenario without architectural change. The 65% scenario requires per-channel queues and is a separate architectural decision.

**How we track it:** DAU/MAU is tracked via the existing analytics pipeline. The monthly metrics review (§1.4) checks the 7-day rolling average. If it crosses 35%, the scale-up runbook is triggered before the next review cycle.

#### 1.1.2 Notification Volume Scenarios

| Scenario | Notifs/DAU/day | DAU (30% of MAU) | Total/day | Average/sec |
|---|---|---|---|---|
| Conservative | 5 | 3M | 15M | ~175 |
| **Base case** | **17** | **3M** | **51M** | **~590** |
| High | 40 | 3M | 120M | ~1,390 |

#### 1.1.3 Peak Provisioning: Numbers First, Labels Second

A 3× multiplier is borrowed from general web traffic patterns and is wrong for notification systems. Notification spikes are **correlated and event-driven**. A single viral post generates simultaneous like/comment/share notifications to all participants. A celebrity join triggers bulk follow-suggestion notifications. A breaking news event drives millions of simultaneous app opens.

We state provisioning targets first and derive multipliers from them — not the reverse:

- Base average: 590/sec
- Primetime concentration: ~50% of daily volume in a 3-hour window → ~2,360/sec sustained
- Correlated viral spike on top of primetime: 4–5× primetime rate for 5–10 minutes → ~10,000–12,000/sec

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (8.5× daily average; ~2× primetime sustained rate)
- **Burst capacity: 12,000/sec** (20× daily average; ~5× primetime rate)

Queue depth is the shock absorber for bursts above 5,000/sec — workers drain the backlog after the spike. Over-provisioning workers for 12,000/sec continuous capacity would be wasteful 99% of the time; over-provisioning queue depth costs almost nothing.

**Infrastructure implication:** Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge (benchmarks show >100K ops/sec for simple sorted set operations). Worker pool targets 5,000/sec throughput; bursts above that queue and drain within minutes.

#### 1.1.4 Synthetic Load Testing: Scope and Limits

We provision infrastructure from the model above before launch and validate with synthetic load testing. Synthetic testing has real limits; we are explicit about both what it validates and what it cannot.

**What the month-1 load test validates:**
- Queue throughput: can the Redis sorted set handle 3,500 enqueue/dequeue ops/sec without latency degradation?
- Worker throughput: can 40 workers process 3,500 messages/sec without backlog accumulation?
- Database write rate: can RDS handle delivery event log writes at 3,500/sec × 3 events/notification = ~10,500 inserts/sec? (This is the critical constraint — see §2.4)
- Preference cache hit rate: does the Redis preference cache sustain >95% hit rate under synthetic load?

**What the month-1 load test cannot validate:**
- **FCM/APNs behavior under load.** FCM throttles new senders at ~2,000/sec; APNs has per-certificate rate limits. These only appear with real tokens and real provider connections.
- **SendGrid IP warming constraints.** A new IP sending 1.9M emails/day immediately will be throttled or blacklisted. IP warming is a 4–6 week process, not something a load test validates.
- **Twilio carrier rate limits.** Per-long-code (~1 msg/sec) and per-short-code (~100 msg/sec) caps are tested against Twilio's sandbox in month 2.
- **Real token distribution.** Expired and invalid tokens in production generate failure patterns a synthetic test cannot replicate.

**Resolution:** Month 2 includes a 5% production rollout specifically designed to surface provider-side limits before full launch. Provider constraints are not validated by staging; they are validated by controlled production exposure.

**Provisioning timeline:**
- End of month 1: ElastiCache r6g.xlarge, RDS db.r6g.2xlarge, 40 delivery workers provisioned and synthetic load tested
- Weeks 1–2 post-launch (5% rollout): Instrument actual provider error rates; adjust worker concurrency per channel
- Scale-up path: ElastiCache vertical scaling with <60-second failover; worker count scales horizontally; neither requires code changes

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications would cost ~$2.9M/year at 2% volume. We treat SMS as a privileged channel reserved for authentication and security.

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---|---|---|---|---|---|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

#### 1.2.1 Hard SMS Cap — Atomically Enforced

The naive approach has a race condition: two simultaneous routing decisions for the same user both read a count of 2 and both decide to send, exceeding the per-user cap. We eliminate this with a Redis Lua script. The script uses `INCR` with conditional `EXPIRE` rather than `GET`/`SET`/`INCR` — simpler and correct:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded
-- KEYS[1]: "sms_cap:{user_id}:{date_utc}"
-- ARGV[1]: cap (integer, e.g. 3)
-- ARGV[2]: ttl in seconds until midnight UTC

local key  = KEYS[1]
local cap  = tonumber(ARGV[1])
local ttl  = tonumber(ARGV[2])

local count = redis.call('INCR', key)

if count == 1 then
    -- First increment: set expiry so key resets at midnight UTC.
    -- Only set on first call to avoid resetting TTL on subsequent calls.
    redis.call('EXPIRE', key, ttl)
end

if count <= cap then
    return 1
else
    return 0
end
```

**Why this is correct:** `INCR` creates the key if it doesn't exist (initializing to 1) and increments atomically. Redis Lua execution is single-threaded — one script completes before another begins, so two simultaneous routing decisions serialize correctly. If count exceeds cap, the increment has already happened, meaning the counter may reach cap+1 or cap+2 under high concurrency before all in-flight scripts return 0. This overshoot is bounded by the number of concurrent workers routing for the same user simultaneously — typically 1–2. For SMS cost control, a 1–2 message overshoot per user per day is acceptable. If exact enforcement is required, use a `GET`-then-`INCR` pattern with optimistic locking, which adds latency.

Auth SMS (OTP) bypasses this check entirely, using a separate key with a cap of 10/day. OTP abuse is handled at the auth layer, not the notification layer.

#### 1.2.2 Global SMS Cap: Fallback and Observability

A global daily cap of 200K non-auth SMS is enforced via a separate atomic counter at the router. When the cap is reached, notifications are not silently dropped — a silent drop is invisible to every failure metric and undebuggable after the fact. Explicit behavior:

1. **Delivery event written first.** Before the routing decision resolves, a `delivery_events` row is written with `event_type = 'channel_fallback'` and `metadata = {"reason": "global_sms_cap", "fallback_channel": "push"}`. This ensures the notification is traceable regardless of what happens next.

2. **Fallback to push, then email.** If the recipient has push enabled, the notification is re-routed to push. If not, to email. If neither is available, the event is written as `dropped` with `metadata = {"reason": "global_sms_cap_no_fallback"}`.

3. **On-call alert fires at 80% of cap.** At 160K non-auth SMS sent in a day, PagerDuty fires a warning-level alert. At 200K, it fires a critical alert. The on-call engineer decides whether to raise the cap (requires EM approval, documented in runbook §7.2) or let fallback logic handle remaining volume.

4. **Auth SMS is always exempt.** Auth SMS uses a separate counter with no global daily limit; abuse is rate-limited at the auth layer.

### 1.3 Team Allocation

Assigning all four channel integrations to one engineer creates a single point of failure on the critical path. Grouping email, SMS, reliability, and DevOps together because they're "webhook-heavy" is an organizational rationalization, not a workload analysis. Email alone involves webhook processing, bounce handling, suppression list sync, IP warming, and deliverability monitoring.

SMS has two distinct concerns that map cleanly to different ownership boundaries:
- **Send path** (Twilio API calls, carrier error handling, delivery receipts): webhook-heavy delivery integration, adjacent to email. E4 owns it.
- **STOP handling and carrier suppression lists**: a user texting STOP is a preference change. It belongs in the same system as email unsubscribes and push opt-outs. E3 owns it.

This split also resolves a scheduling conflict: E4's month-1 work is email webhooks; SMS send path is month-2 work. E3's STOP handling work is month 2, after the preference management system is stable. The two workstreams no longer compete.

**Revised allocation:**

| Engineer | Primary Responsibility | Secondary / Backup |
|---|---|---|
| E1 | Core pipeline, queue infrastructure, delivery workers, reliability/monitoring infrastructure | Backup: E3 |
| E2 | Push integrations (APNs + FCM), token management | Backup: E1 |
| E3 | Preference management, user-facing API, suppression logic, in-app notifications, WebSocket layer, SMS STOP/carrier suppression handling | Backup: E4 |
| E4 | Email (SendGrid) + SMS send path (Twilio), webhook processing, deployment pipelines | Backup: E2 |

**Reliability and monitoring moves to E1**, who owns the core pipeline — you should monitor the system you built. **E3 absorbs in-app and WebSocket** because both are user-facing read/write paths, adjacent to preference management E3 already owns. **E2 cross-training on email webhook schema is deferred to month 3** — adding it to month-1 scope creates an unanalyzed workload conflict with E2's APNs/FCM integration. Month-1 bus factor risk is accepted and mitigated by runbooks rather than cross-training.

#### 1.3.1 Runbook Standard

A runbook written under delivery pressure without a template is likely to be a list of commands with no context. We define a minimum standard and a review gate.

**Required sections for every integration runbook:**
1. **Service overview**: What this integration does, what breaks if it's down, which notifications are affected
2. **Health checks**: Specific commands or dashboard links to verify functioning; expected outputs
3. **Common failure modes**: At least 3 documented failure scenarios with observed symptoms, root cause, and resolution steps
4. **Escalation path**: Who to page, at what severity, and what information to gather before paging
5. **Rollback procedure**: How to disable this channel without affecting others (circuit breaker location, feature flag name)
6. **External provider contacts**: Support URLs, SLA commitments, and pointer to credentials in secrets manager (never credentials in the runbook)

**Review gate:** Runbooks are reviewed by the backup engineer (see allocation table) before end-of-month-1 sign-off. A runbook is not "done" until the backup engineer confirms they could execute it without the primary engineer present. E1 tracks runbook completion status in the project tracker.

### 1.4 Scaling Triggers

"Revisit at 50M MAU" is not an action item. It has no owner, no tracking mechanism, and no lead time estimate. If growth is faster than expected, multiple deferred decisions become urgent simultaneously. We replace all deferrals with explicit triggers:

| Decision | Trigger | Owner | Lead Time | Action |
|---|---|---|---|---|
| Per-channel queues | Sustained queue depth >100K during non-spike periods, OR DAU/MAU >