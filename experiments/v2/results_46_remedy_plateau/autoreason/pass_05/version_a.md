# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 15M–120M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU.

**Key design decisions and their explicit tradeoffs:**

- DAU/MAU ratio and per-user notification rate are modeled as **correlated variables**, not independent axes. Higher engagement produces both more DAUs and more notifications per DAU simultaneously. The sensitivity table reflects this.
- Peak provisioning targets are stated first; multiplier labels are derived from them. Where aggressive assumptions compound, we flag it and justify the resulting number rather than presenting it as clean arithmetic.
- The RDS write bottleneck at base case load is acknowledged as a real constraint, not just a validation target. We address it with write batching before launch.
- The Lua SMS cap script has bounded overshoot proportional to concurrent workers per user, not a fixed "1–2." We state the actual bound and accept it explicitly.
- In-app notifications bypass the queue for latency reasons but use a dedicated retry store with equivalent semantics. The mechanism is specified.
- The SMS ownership split between E3 and E4 has a defined interface contract and propagation SLA.
- The runbook review gate is restructured to avoid circular dependency: primary engineers review each other's runbooks on systems they understand, not systems they haven't seen yet.
- The 5% production rollout has explicit acceptance criteria and stop thresholds per channel.
- SendGrid IP warming is planned as a prerequisite to launch, not a consequence of it. Email volume ramps over 6 weeks starting month 1.
- E3's workload is redistributed. The "two channel integrations" principle in the executive summary is honored in the allocation, not just stated.
- The scaling triggers table is complete.

We ship a working system by end of month 2, iterate through month 5, and harden in month 6.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. Three reference points from public data:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts suggest engagement-heavy apps see 10–25/day for DAU
- TikTok-style engagement loops report 20–40/day

We model three scenarios, design for the base case, and ensure infrastructure can handle the high case without architectural change.

#### 1.1.1 DAU/MAU and Notification Rate Are Correlated

The previous version of this document modeled DAU/MAU ratio and per-user notification rate as independent variables, producing a table where every DAU/MAU scenario used the same 17 notifications/DAU. This is wrong. A 20% DAU/MAU ratio indicates low engagement — those users generate fewer interactions, receive fewer mentions and likes, and produce fewer notification events. A 65% DAU/MAU ratio indicates a highly engaged user base that generates more content and more cross-user interactions per day.

Treating them as orthogonal produces a model that is internally inconsistent: a user base with 20% engagement somehow generates the same 17 notifications/DAU as a user base with 65% engagement. The right model acknowledges the correlation:

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Total/day | Peak/sec (burst) | Infrastructure Posture |
|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | 16M | ~4,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **51M** | **~12,000** | **Base provisioning; scale trigger at 35% DAU/MAU** |
| High | 50% | 5M | 28 | 140M | ~25,000 | Scale-up runbook required before launch |
| Top-quartile | 65% | 6.5M | 40 | 260M | ~40,000 | Architectural change required; per-channel queues; 6-week lead time |

The notification rate estimates at each tier are calibrated against the public benchmarks above, not derived from them precisely. The base case (30% DAU/MAU, 17 notifications/DAU) is the median outcome for a social app at this stage. The high and top-quartile tiers are genuinely uncertain — the correlation between engagement and notification volume is real but not linear, and product decisions (notification aggressiveness, content type) dominate the rate at high-engagement tiers.

**Implication for provisioning:** We provision for the base case. The scale-up path handles the high tier. The top-quartile tier requires architectural change and is a separate decision with a 6-week lead time — the trigger for initiating that decision is defined in §1.4.

**How we track DAU/MAU:** Weekly rolling average via the existing analytics pipeline. Monthly review checks the 7-day average against scale triggers. If the 35% threshold is crossed, the scale-up runbook is initiated before the next review cycle.

#### 1.1.2 Peak Provisioning: Stated Assumptions, Not Derived Precision

The previous version presented peak provisioning numbers as derived from first principles. They were not — they required selecting the most aggressive multiplier at each step simultaneously to reach the stated bounds. We state the assumptions explicitly instead.

- Base average: 590/sec (51M/day ÷ 86,400 seconds)
- Primetime concentration: industry data suggests ~45–55% of social notification volume falls in a 3-hour primetime window. Using 50%: 590 × 86,400 × 0.50 / 10,800 = **~2,360/sec sustained during primetime**
- Correlated viral spike: a single high-follower post generating simultaneous notifications to 100K+ users produces a spike above the primetime baseline. We have no pre-launch data on spike magnitude. We use 4× primetime as a planning assumption — not a derived figure — giving ~9,440/sec. We round to **10,000/sec as the burst target** and accept that this is a judgment call, not arithmetic.

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (~2× primetime sustained rate; leaves headroom for multiple simultaneous events)
- **Burst capacity: 10,000/sec** (queue absorbs spikes above 5,000/sec; workers drain the backlog within minutes)

The gap between 5,000/sec sustained and 10,000/sec burst is intentional. Over-provisioning workers for continuous 10,000/sec capacity wastes ~50% of compute 99% of the time. Queue depth is the shock absorber: Redis sorted set operations at 5,000/sec are well within a single ElastiCache r6g.xlarge (>100K ops/sec for simple sorted set operations). Workers process at 5,000/sec; a 10-minute spike at 10,000/sec generates a backlog of ~3M messages, cleared within ~10 minutes of spike end.

**What we don't know and accept:** We don't know the actual spike profile before launch. The 5% production rollout (§1.1.3) will surface whether our burst assumption is adequate. If spikes exceed 10,000/sec in the rollout, we add workers before full launch. Worker scaling is horizontal and requires no code changes.

#### 1.1.3 Synthetic Load Testing: Scope and Limits

Month-1 load testing validates infrastructure behavior, not provider behavior.

**What the month-1 load test validates:**
- Queue throughput: Redis sorted set at 3,500 enqueue/dequeue ops/sec without latency degradation
- Worker throughput: 40 workers processing 3,500 messages/sec without backlog accumulation
- Database write rate: RDS handling delivery event writes at base case load (see §2.4 for write batching, which makes this tractable)
- Preference cache hit rate: Redis preference cache sustaining >95% hit rate under synthetic load

**What it cannot validate:**
- FCM/APNs behavior under load (provider-side rate limits require real tokens)
- SendGrid IP warming constraints (a new IP sending full volume immediately will be throttled — addressed in §1.2.2)
- Twilio carrier rate limits (tested against Twilio sandbox in month 2)
- Real token distribution (expired/invalid tokens generate failure patterns synthetic tests cannot replicate)

**Resolution:** The 5% production rollout in weeks 1–2 post-launch surfaces provider-side limits before full launch. Acceptance criteria and stop thresholds are defined in §1.1.4.

#### 1.1.4 Production Rollout Acceptance Criteria

"Controlled production exposure" without thresholds is just launching and watching. The following thresholds govern the 5% rollout. Breaching any threshold pauses the rollout; the on-call engineer and EM decide whether to investigate and resume or abort.

| Channel | Metric | Warning Threshold | Stop Threshold | Rationale |
|---|---|---|---|---|
| Push (FCM) | Error rate (4xx + 5xx from provider) | >2% over 15 min | >5% over 5 min | FCM returns 429 when rate-limited; >5% indicates systemic throttling |
| Push (APNs) | Invalid token rate | >5% over 1 hour | >15% over 15 min | High invalid rate indicates token management bug, not normal churn |
| Email | Bounce rate (hard + soft) | >3% over 1 hour | >8% over 15 min | SendGrid warns at 5%; staying below 3% protects IP reputation during warming |
| Email | Spam complaint rate | >0.1% over 1 hour | >0.3% over 15 min | Google/Yahoo require <0.1% sustained; >0.3% risks blacklisting |
| SMS | Carrier error rate | >3% over 30 min | >10% over 10 min | Carrier errors above 10% indicate routing or formatting problems |
| All channels | P99 end-to-end latency (enqueue to provider ACK) | >30 sec | >120 sec | Notifications older than 2 minutes are significantly less valuable |
| Queue | Sustained depth (non-spike) | >50K messages | >200K messages | Sustained backlog indicates worker capacity problem |

**Rollout gates:** The rollout proceeds from 5% to 25% to 100% only after 24 hours at each tier with no active stop-threshold breaches and no open P1 incidents.

### 1.2 Channel Mix and Cost Model

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---|---|---|---|---|---|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | |

SMS cost at 2% volume would be ~$2.9M/year. We treat SMS as a privileged channel reserved for authentication and security notifications only.

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

**Actual overshoot bound:** The previous version claimed overshoot is "typically 1–2." This was wrong — it described a property of the worker architecture, not the script. The correct statement: overshoot is bounded by the number of workers that have passed the cap check and are simultaneously in-flight before their result is returned. In our architecture, workers process one notification per goroutine, and each worker makes one Lua call per SMS routing decision. The maximum concurrent SMS routing decisions for a single user equals the number of workers processing notifications for that user simultaneously. For a user receiving 3 SMS/day, this is almost always 1. For a pathological case — a user receiving a burst of 50 notifications simultaneously during a viral event — it could be higher, but the burst would consist mostly of push notifications, not SMS. We accept a worst-case overshoot of cap+5 as the practical bound and treat it as acceptable for cost control purposes. If exact enforcement is required (e.g., compliance scenarios), replace with a `WATCH`/`MULTI`/`EXEC` optimistic locking pattern at higher latency cost.

**TTL bug mitigation:** The TTL is calculated by the caller as `seconds_until_midnight_utc`. A bug producing TTL=0 or a very large TTL would cause incorrect cap reset behavior. The script validates TTL range (>0 and ≤90,000, which covers any valid time until midnight) and returns an error on invalid input. The caller treats a script error as a send-blocked state and logs it as a routing error — it does not silently allow or deny the SMS. This is tested explicitly in the month-1 integration test suite.

#### 1.2.2 Global SMS Cap: Fallback and Observability

A global daily cap of 200K non-auth SMS is enforced via a separate atomic counter at the router. When the cap is reached, notifications are not silently dropped:

1. **Delivery event written first.** Before routing resolves, a `delivery_events` row is written with `event_type = 'channel_fallback'` and `metadata = {"reason": "global_sms_cap", "fallback_channel": "push"}`.
2. **Fallback to push, then email.** If the recipient has push enabled, re-route to push. If not, to email. If neither is available, write `dropped` with `metadata = {"reason": "global_sms_cap_no_fallback"}`.
3. **On-call alert at 80% of cap.** At 160K non-auth SMS, PagerDuty fires warning-level. At 200K, critical. The on-call engineer decides whether to raise the cap (requires EM approval, documented in runbook §7.2) or let fallback logic handle remaining volume.
4. **Auth SMS is always exempt.** Auth SMS uses a separate counter with no global daily limit; abuse is rate-limited at the auth layer.

#### 1.2.3 SendGrid IP Warming: Pre-Launch Prerequisite

The previous version acknowledged IP warming as a 4–6 week process but showed email launching at end of month 2 — implying full volume from day one, which would trigger throttling or blacklisting. This is a gap we close explicitly.

**IP warming is a prerequisite to full email launch, not a consequence of it.** The warming schedule starts in month 1, week 3, using a dedicated warming subdomain and shared IP pool for initial volume. We do not attempt 1.9M emails/day from a cold IP.

| Week | Max Daily Volume | Cumulative