# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A single priority queue with channel fanout, rather than per-channel queues or event streaming. This is debuggable, replaceable, and sufficient for 10M MAU. The tradeoff: per-channel queues allow independent scaling and failure isolation but add operational complexity we cannot staff. We revisit this if we reach the top-quartile engagement tier, with a defined 6-week lead time for that architectural change.

**What this document covers and doesn't:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. What it does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, and analytics beyond delivery tracking.

**Key decisions summarized:**

- We provision for the base case (51M/day) with a defined scale-up path. The high tier (140M/day) requires horizontal scaling only. The top-quartile tier (260M/day) requires architectural change with a 6-week lead time.
- DAU/MAU ratio and per-user notification rate are modeled as correlated variables. The sensitivity table reflects this — a low-engagement user base generates fewer social events and therefore fewer notifications per DAU.
- Push handles 76% of volume at near-zero marginal cost. SMS is reserved for authentication and security only, enforced at the router level with an atomically-enforced per-user cap.
- In-app notifications bypass the queue for latency reasons and write directly to a dedicated delivery store via a separate path with its own retry logic. The mechanism is specified in §3.
- Email IP warming starts in month 1, week 3 — six weeks before the email channel goes live — as a prerequisite, not an afterthought.
- The 5% production rollout has explicit acceptance criteria and per-channel stop thresholds. "Controlled exposure" without thresholds is just launching and watching.
- Four engineers across six months. The staffing breakdown in §7 maps specific work to specific engineers with explicit sequencing and interface contracts.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. We use three reference points from public data to anchor estimates, while acknowledging their limitations:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts (2014–2016): engagement-heavy apps see 10–25/day for DAUs
- Industry survey of social apps (2021, Braze): median push send rate of 3–5/week per MAU across all apps; top-quartile social apps at 2–4/day per DAU

**Limitations of these benchmarks:** The Twitter and Facebook data are from a different era with different notification philosophies. The Braze data is more recent but aggregates across app types. We use these as sanity checks on order of magnitude, not precise calibration. Our actual rate will be determined by product decisions not yet made (notification aggressiveness, trigger logic) and the engagement patterns of our specific user base. The production rollout (§1.1.4) will surface our actual rate within two weeks; we will revise estimates then.

#### 1.1.1 Why DAU/MAU and Notification Rate Are Correlated — and How We Model It

The previous approach treated DAU/MAU ratio and per-user notification rate as independent variables, producing a table where every scenario used the same 17 notifications/DAU. This is internally inconsistent. The mechanism is straightforward: notifications in a social app are primarily triggered by social interactions — likes, comments, follows, mentions, shares. A user base with 65% DAU/MAU is posting more content, interacting more frequently, and generating more cross-user events per day than a 20% DAU/MAU user base. More events means more notification triggers.

This is a structural argument, not a statistical fit. We cannot precisely quantify the relationship without our own data. What we can say: it is inconsistent to assume a low-engagement user base generates the same notification rate per DAU as a highly-engaged one. Our estimates use the benchmark range as a constraint — low engagement falls near the lower bound of observed rates, high engagement near the upper bound. The specific numbers are judgment calls within those constraints.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Basis | Total/day | Peak/sec (burst) | Infrastructure Posture |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | Lower bound of observed range; few social events/day | 16M | ~4,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **Midpoint of observed range; moderate social activity** | **51M** | **~8,000** | **Base provisioning; scale trigger at 35% DAU/MAU** |
| High | 50% | 5M | 28 | Upper-middle of range; highly active social graph | 140M | ~25,000 | Scale-up runbook required before launch |
| Top-quartile | 65% | 6.5M | 40 | Upper bound; aggressive engagement loops | 260M | ~40,000 | Architectural change; per-channel queues; 6-week lead time |

We do not claim these numbers are derived from benchmarks. They are estimates consistent with the benchmarks and the structural argument above.

**How we track DAU/MAU:** Weekly rolling average via the existing analytics pipeline. Monthly review checks the 7-day average against scale triggers. If the 35% threshold is crossed, the scale-up runbook is initiated before the next review cycle.

#### 1.1.2 Peak Provisioning: Stated Assumptions, Not Derived Precision

We state assumptions explicitly rather than presenting peak numbers as clean arithmetic.

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** Industry data consistently shows 40–60% of daily social notification volume in a 3–4 hour primetime window (typically 7–10pm local time). Using 50% in a 3-hour window:

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Viral spike:** A single post from a high-follower account can generate simultaneous notifications to 100K+ users. We have no pre-launch data on spike magnitude or frequency. We use 3× primetime sustained rate as the burst planning assumption — consistent with published Firebase engineering data on push spike patterns for mid-scale social apps, and explicitly a judgment call, not a derived figure — giving **~7,100/sec**. We round to **8,000/sec** as the burst target with a 10% margin.

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (~2× primetime sustained; headroom for simultaneous events)
- **Burst capacity: 8,000/sec** (queue absorbs spikes; workers drain backlog)

The gap is intentional. Over-provisioning workers for continuous 8,000/sec capacity wastes roughly 50% of compute 99% of the time. Queue depth is the shock absorber.

**Backlog clearance arithmetic:** Workers process at 5,000/sec. A 10-minute spike at 8,000/sec generates (8,000 − 5,000) × 600 = 1.8M backlogged messages. After the spike, workers process at 5,000/sec against an incoming rate that has returned to ~2,360/sec. Net drain rate: 2,640/sec. Time to clear 1.8M backlog: ~11.5 minutes. Total worst-case delay for a message enqueued at spike start: ~21 minutes. This is acceptable for social notifications. Notification types where it is not acceptable receive priority queue placement (§2.2).

**Queue infrastructure note:** Redis sorted set operations (ZADD, ZRANGEBYSCORE, ZREM) are O(log N). At a spike-peak depth of 1.8M elements, O(log 1,800,000) ≈ O(21) — still fast. A single ElastiCache r6g.xlarge handles ~40–60K sorted set ops/sec under load. Our peak enqueue rate of 8,000/sec is well within this; we do not need to shard the queue at base case load.

**What we don't know and accept:** We don't know the actual spike profile before launch. The 5% production rollout (§1.1.4) will surface whether our burst assumption is adequate. If spikes exceed 8,000/sec in the rollout, we add workers before full launch — worker scaling is horizontal and requires no code changes.

#### 1.1.3 Synthetic Load Testing: Scope and Limits

Month-1 load testing validates infrastructure behavior, not provider behavior.

**What the month-1 load test validates:**
- Queue throughput: Redis sorted set at 5,000 enqueue/dequeue ops/sec without latency degradation
- Worker throughput: 40 workers processing 5,000 messages/sec without backlog accumulation
- Database write rate: RDS handling delivery event writes at base case load (write batching per §2.4 makes this tractable)
- Preference cache hit rate: Redis preference cache sustaining >95% hit rate under synthetic load

**What it cannot validate:**
- FCM/APNs behavior under load (provider-side rate limits require real device tokens)
- SendGrid IP warming constraints (a cold IP sending full volume immediately will be throttled — addressed in §1.2.3)
- Twilio carrier rate limits (tested against Twilio sandbox in month 2)
- Real token distribution (expired/invalid tokens generate failure patterns synthetic tests cannot replicate)

**Resolution:** The 5% production rollout in weeks 1–2 post-launch surfaces provider-side limits before full launch. Acceptance criteria and stop thresholds are defined in §1.1.4.

#### 1.1.4 Production Rollout Acceptance Criteria

"Controlled production exposure" without thresholds is just launching and watching. The following thresholds govern the 5% rollout. Breaching any stop threshold pauses the rollout; the on-call engineer and EM decide whether to investigate and resume or abort.

| Channel | Metric | Warning Threshold | Stop Threshold | Rationale |
|---|---|---|---|---|
| Push (FCM) | Error rate (4xx + 5xx from provider) | >2% over 15 min | >5% over 5 min | FCM returns 429 when rate-limited; >5% indicates systemic throttling |
| Push (APNs) | Invalid token rate | >5% over 1 hour | >15% over 15 min | High invalid rate indicates a token management bug, not normal churn |
| Email | Bounce rate (hard + soft) | >2% over 1 hour | >5% over 15 min | Staying below 2% protects IP reputation during warming |
| Email | Spam complaint rate | >0.08% over 1 hour | >0.3% over 15 min | Google/Yahoo require <0.1% sustained; >0.3% risks blacklisting |
| SMS | Carrier error rate | >3% over 30 min | >10% over 10 min | Errors above 10% indicate routing or formatting problems |
| All channels | P99 end-to-end latency (enqueue to provider ACK) | >30 sec | >120 sec | Notifications older than 2 minutes are significantly less valuable |
| Queue | Sustained depth (non-spike) | >50K messages | >200K messages | Sustained backlog indicates worker capacity problem |

**Rollout gates:** The rollout proceeds from 5% → 25% → 100% only after 24 hours at each tier with no active stop-threshold breaches and no open P1 incidents. Advancement requires explicit sign-off from the on-call engineer; it does not happen automatically on schedule.

### 1.2 Channel Mix and Cost Model

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---|---|---|---|---|---|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | SendGrid Pro |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | ~$94K/month |

SMS at 2% of volume would cost ~$2.9M/year. We treat SMS as a privileged channel reserved for authentication and security notifications only, enforced at the router level.

#### 1.2.1 Hard SMS Cap — Atomically Enforced

The race condition: two simultaneous routing decisions for the same user both read count=2 and both decide to send, exceeding the cap. We eliminate this with a Redis Lua script that increments before checking:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded, error on invalid input
-- KEYS[1]: "sms_cap:{user_id}:{date_utc}"
-- ARGV[1]: cap (integer, e.g. 3)
-- ARGV[2]: ttl in seconds until midnight UTC (pre-calculated by caller)

local key = KEYS[1]
local cap = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

-- Validate TTL before modifying state.
-- Valid range: 1 to 90000 (25 hours; covers any valid time until midnight
-- plus buffer for clock skew). TTL=0 would cause immediate expiry.
if not ttl or ttl <= 0 or ttl > 90000 then
    return redis.error_reply("invalid_ttl:" .. tostring(ARGV[2]))
end

local count = redis.call('INCR', key)

if count == 1 then
    -- Set expiry only on first increment to avoid resetting TTL on
    -- subsequent calls.
    redis.call('EXPIRE', key, ttl)
end

if count <= cap then
    return 1
else
    return 0
end
```

**Why TTL validation precedes INCR:** Validating after INCR leaves the key incremented without an expiry if TTL is invalid — a persistent, uncapped key. Validating first prevents this. The remaining edge case: if the Redis host clock drifts significantly, the key could expire mid-day, restarting the count. We mitigate this with NTP on all Redis hosts, TTL calculated server-side with a 60-second buffer before midnight, and monitoring for unexpected count resets. We accept that this edge case is not fully eliminated by the script alone.

**Caller behavior on script error:** A script error is treated as a send-blocked state. The caller logs it as a routing error and does not silently allow or deny the SMS. This is tested explicitly in the month-1 integration test suite.

**Honest overshoot bound:** The Lua script serializes cap checks — two checks cannot execute simultaneously in Redis. Overshoot therefore requires multiple workers to have passed the cap check and be simultaneously in-flight to the Twilio API for the same user. For a user receiving 3 SMS/day, concurrent processing is rare; overshoot is practically zero. For a pathological case — a user caught in a viral burst — multiple workers may process notifications concurrently, but only SMS-eligible notifications (auth and security) route to SMS. A user receiving 50 simultaneous auth SMS is an abuse pattern handled by the auth rate limiter upstream.

We cannot claim a fixed overshoot bound of "cap+2" or "cap+5" without data on our worker concurrency patterns. The honest statement: overshoot is bounded by the number of concurrent workers processing SMS-eligible notifications for the same user simultaneously — in normal operation, 0–2; in pathological cases, potentially higher. We monitor cap exceedance and alert if any user exceeds cap+3 in a day. If we observe systematic overshoot, we add a distributed lock around the check-and-send operation at the cost of higher latency.

#### 1.2.2 Global SMS Cap: Fallback Sequencing and Observability

A global daily cap of 200K non-auth SMS is enforced via a separate atomic counter at the router. When the cap is reached, the correct sequencing matters:

1. Router determines the notification requires SMS.