# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Key design decisions and their explicit tradeoffs:**

- DAU/MAU ratio and per-user notification rate are modeled as **correlated variables**, not independent axes. Higher engagement produces both more DAUs and more notifications per DAU simultaneously. The sensitivity table reflects this.
- Peak provisioning targets are stated first; multiplier labels are derived from them, not assumed from general web traffic patterns.
- Synthetic load testing scope is bounded explicitly to what it can validate; provider constraints are handled via controlled production rollout with defined acceptance criteria and stop thresholds.
- The RDS write bottleneck at base case load is a real constraint, addressed with write batching before launch.
- The Lua SMS cap script has bounded overshoot proportional to concurrent workers per user. We state the actual bound and accept it explicitly.
- In-app notifications bypass the queue for latency reasons but use a dedicated retry store with equivalent delivery semantics.
- The SMS ownership split between E3 and E4 has a defined interface contract and propagation SLA.
- Runbooks require a defined template and backup-engineer review gate before sign-off.
- The 5% production rollout has explicit acceptance criteria and stop thresholds per channel.
- SendGrid IP warming is planned as a prerequisite to launch, not a consequence of it. Email volume ramps over 6 weeks starting month 1.
- No engineer owns more than two channel integrations.
- All scaling triggers have explicit owners, thresholds, and lead times — no "revisit at 50M MAU" deferrals.

We ship a working system by end of month 2, iterate through month 5, and harden in month 6.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts: engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops: 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change.

#### 1.1.1 DAU/MAU and Notification Rate Are Correlated

Modeling DAU/MAU ratio and per-user notification rate as independent variables produces a table that is internally inconsistent: a user base with 20% engagement somehow generates the same 17 notifications/DAU as a user base with 65% engagement. The right model acknowledges the correlation. A 20% DAU/MAU ratio indicates low engagement — those users generate fewer interactions, receive fewer mentions and likes, and produce fewer notification events. A 65% ratio indicates a highly engaged user base generating more content and more cross-user interactions per day.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Peak/sec (burst) | Infrastructure Posture |
|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~4,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~10,000** | **Base provisioning; scale trigger at 35% DAU/MAU** |
| High | 50% | 5M | 28 | 140M | ~25,000 | Scale-up runbook required before launch |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~40,000 | Architectural change required; per-channel queues; 6-week lead time |

The notification rate estimates at each tier are calibrated against public benchmarks, not derived from them precisely. The base case is the median outcome for a social app at this stage. The high and top-quartile tiers are genuinely uncertain — the correlation between engagement and notification volume is real but not linear, and product decisions (notification aggressiveness, content type) dominate the rate at high-engagement tiers.

**How we track DAU/MAU:** Weekly rolling average via the existing analytics pipeline. Monthly review checks the 7-day average against scale triggers. If the 35% threshold is crossed, the scale-up runbook is initiated before the next review cycle, not at it.

#### 1.1.2 Peak Provisioning: Stated Assumptions, Not Derived Precision

A 3× multiplier borrowed from general web traffic patterns is wrong for notification systems. Notification spikes are correlated and event-driven. A single viral post generates simultaneous like/comment/share notifications to all participants. A celebrity join triggers bulk follow-suggestion notifications. We state provisioning targets first and derive labels from them.

- Base average: 590/sec (51M/day ÷ 86,400 seconds)
- Primetime concentration: ~50% of daily volume in a 3-hour window → ~2,360/sec sustained
- Correlated viral spike on top of primetime: 4× primetime rate for 5–10 minutes → ~9,440/sec

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (~2× primetime sustained rate; leaves headroom for multiple simultaneous events)
- **Burst capacity: 10,000/sec** (queue absorbs spikes above 5,000/sec; workers drain the backlog within minutes)

The 4× viral spike multiplier is a planning assumption, not arithmetic. The 5% production rollout (§1.1.4) will surface whether this assumption is adequate. If spikes exceed 10,000/sec in the rollout, we add workers before full launch — horizontal scaling requires no code changes.

The gap between 5,000/sec sustained and 10,000/sec burst is intentional. Over-provisioning workers for continuous 10,000/sec wastes ~50% of compute 99% of the time. Queue depth is the shock absorber: Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge (benchmarks show >100K ops/sec for simple sorted set operations). A 10-minute spike at 10,000/sec generates a backlog of ~3M messages, cleared within ~10 minutes of spike end.

#### 1.1.3 Synthetic Load Testing: Scope and Limits

Month-1 load testing validates infrastructure behavior, not provider behavior. We are explicit about both.

**What the month-1 load test validates:**
- Queue throughput: Redis sorted set handling 3,500 enqueue/dequeue ops/sec without latency degradation
- Worker throughput: 40 workers processing 3,500 messages/sec without backlog accumulation
- Database write rate: RDS handling delivery event writes at base case load (write batching in §2.4 makes this tractable)
- Preference cache hit rate: Redis preference cache sustaining >95% hit rate under synthetic load

**What it cannot validate:**
- **FCM/APNs behavior under load.** FCM throttles new senders at ~2,000/sec; APNs has per-certificate rate limits. These only appear with real tokens and real provider connections.
- **SendGrid IP warming constraints.** A new IP sending 1.9M emails/day immediately will be throttled or blacklisted. IP warming is a 4–6 week process addressed in §1.2.3.
- **Twilio carrier rate limits.** Per-long-code (~1 msg/sec) and per-short-code (~100 msg/sec) caps are tested against Twilio's sandbox in month 2.
- **Real token distribution.** Expired and invalid tokens in production generate failure patterns a synthetic test cannot replicate.

**Resolution:** The 5% production rollout in weeks 1–2 post-launch surfaces provider-side limits before full launch.

#### 1.1.4 Production Rollout Acceptance Criteria

"Controlled production exposure" without thresholds is just launching and watching. The following thresholds govern the 5% rollout. Breaching any stop threshold pauses the rollout; the on-call engineer and EM decide whether to investigate and resume or abort.

| Channel | Metric | Warning Threshold | Stop Threshold | Rationale |
|---|---|---|---|---|
| Push (FCM) | Error rate (4xx + 5xx from provider) | >2% over 15 min | >5% over 5 min | FCM returns 429 when rate-limited; >5% indicates systemic throttling |
| Push (APNs) | Invalid token rate | >5% over 1 hour | >15% over 15 min | High invalid rate indicates token management bug, not normal churn |
| Email | Bounce rate (hard + soft) | >3% over 1 hour | >8% over 15 min | SendGrid warns at 5%; staying below 3% protects IP reputation during warming |
| Email | Spam complaint rate | >0.1% over 1 hour | >0.3% over 15 min | Google/Yahoo require <0.1% sustained; >0.3% risks blacklisting |
| SMS | Carrier error rate | >3% over 30 min | >10% over 10 min | Carrier errors above 10% indicate routing or formatting problems |
| All channels | P99 end-to-end latency (enqueue to provider ACK) | >30 sec | >120 sec | Notifications older than 2 minutes are significantly less valuable |
| Queue | Sustained depth (non-spike) | >50K messages | >200K messages | Sustained backlog indicates worker capacity problem |

**Rollout gates:** The rollout proceeds from 5% → 25% → 100% only after 24 hours at each tier with no active stop-threshold breaches and no open P1 incidents.

### 1.2 Channel Mix and Cost Model

SMS cost deserves explicit scrutiny. Using SMS for social engagement notifications would cost ~$2.9M/year at 2% volume. We treat SMS as a privileged channel reserved for authentication and security.

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---|---|---|---|---|---|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

#### 1.2.1 Hard SMS Cap — Atomically Enforced, Realistic Overshoot Bound

The naive approach has a race condition: two simultaneous routing decisions for the same user both read a count of 2 and both decide to send, exceeding the per-user cap. We eliminate this with a Redis Lua script:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded
-- KEYS[1]: "sms_cap:{user_id}:{date_utc}"
-- ARGV[1]: cap (integer, e.g. 3)
-- ARGV[2]: ttl in seconds until midnight UTC (pre-calculated by caller)

local key   = KEYS[1]
local cap   = tonumber(ARGV[1])
local ttl   = tonumber(ARGV[2])

-- Validate TTL to prevent silent breakage from caller bugs
if ttl <= 0 or ttl > 90000 then
    return redis.error_reply("invalid_ttl")
end

local count = redis.call('INCR', key)

if count == 1 then
    -- Set expiry only on first increment to avoid resetting TTL on subsequent calls.
    -- TTL is calculated by the caller as seconds until midnight UTC.
    redis.call('EXPIRE', key, ttl)
end

if count <= cap then
    return 1
else
    return 0
end
```

**Why this is correct:** `INCR` creates the key if absent (initializing to 1) and increments atomically. Redis Lua execution is single-threaded — scripts serialize, so two simultaneous routing decisions for the same user cannot both read the same pre-increment value.

**Actual overshoot bound:** The overshoot is bounded by the number of workers that have passed the cap check and are simultaneously in-flight before their result is returned. For a user receiving 3 SMS/day, this is almost always 1. For a pathological case — a user receiving a burst of 50 notifications simultaneously during a viral event — it could be higher, but such a burst would consist mostly of push notifications, not SMS. We accept a worst-case overshoot of cap+5 as the practical bound and treat it as acceptable for cost control purposes. If exact enforcement is required (e.g., compliance scenarios), replace with a `WATCH`/`MULTI`/`EXEC` optimistic locking pattern at higher latency cost.

**TTL bug mitigation:** A bug producing TTL=0 or a very large TTL would cause incorrect cap reset behavior. The script validates TTL range (>0 and ≤90,000, covering any valid time until midnight) and returns an error on invalid input. The caller treats a script error as a send-blocked state and logs it as a routing error — it does not silently allow or deny the SMS. This is tested explicitly in the month-1 integration test suite.

Auth SMS (OTP) bypasses this check entirely, using a separate key with a cap of 10/day. OTP abuse is handled at the auth layer.

#### 1.2.2 Global SMS Cap: Fallback and Observability

A global daily cap of 200K non-auth SMS is enforced via a separate atomic counter at the router. A silent drop is invisible to every failure metric and undebuggable after the fact. Explicit behavior:

1. **Delivery event written first.** Before routing resolves, a `delivery_events` row is written with `event_type = 'channel_fallback'` and `metadata = {"reason": "global_sms_cap", "fallback_channel": "push"}`.
2. **Fallback to push, then email.** If the recipient has push enabled, re-route to push. If not, to email. If neither is available, write `dropped` with `metadata = {"reason": "global_sms_cap_no_fallback"}`.
3. **On-call alert at 80% of cap.** At 160K non-auth SMS, PagerDuty fires warning-level. At 200K, critical. The on-call engineer decides whether to raise the cap (requires EM approval, documented in runbook §7.2) or let fallback logic handle remaining volume.
4. **Auth SMS is always exempt.** Auth SMS uses a separate counter with no global daily limit; abuse is rate-limited at the auth layer.

#### 1.2.3 SendGrid IP Warming: Pre-Launch Prerequisite

IP warming is a prerequisite to full email launch, not a consequence of it. A new IP sending 1.9M emails/day from day one will be throttled or blacklisted. The warming schedule starts in month 1, week 3, using a dedicated warming subdomain and shared IP pool for initial volume.

| Week | Max Daily Volume | Notes |
|---|---|---|
| 1 | 1,000 | Internal test addresses only |
| 2 | 5,000 | Opt-in beta users only |
| 3 | 25,000 | High-engagement segment |
| 4 | 100,000 | Broad beta population |
| 5 | 500,000 | Staged rollout begins |
| 6+ | Full volume | Warming complete; full launch unblocked |

Email is not fully launched until week 6 of warming is complete. This is a hard dependency in the launch plan, not a soft recommendation.

### 1.3 Team Allocation

Assigning all four channel integrations to one engineer creates a single point of failure on the critical path. Grouping email, SMS, reliability, and DevOps together because they're "webhook-heavy" is an organizational rationalization, not a workload analysis. Email alone involves webhook processing, bounce handling, suppression list sync, IP warming, and deliverability monitoring.

SMS has two distinct concerns that map cleanly to different ownership boundaries:
- **Send path** (