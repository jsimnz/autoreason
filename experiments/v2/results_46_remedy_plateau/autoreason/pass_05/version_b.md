# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A single priority queue with channel fanout, rather than per-channel queues or event streaming. This is debuggable, replaceable, and sufficient for 10M MAU. The tradeoff: per-channel queues would allow independent scaling and isolation of channel failures, but add operational complexity we cannot staff. We revisit this if we hit the top-quartile engagement tier.

**What this document covers and doesn't:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. What it does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, and analytics beyond delivery tracking.

**Key decisions summarized:**

- We provision for the base case (51M/day) with a defined scale-up path. The high tier (140M/day) requires horizontal scaling only. The top-quartile tier (260M/day) requires architectural change with a 6-week lead time.
- Push handles 76% of volume at near-zero marginal cost. SMS is reserved for authentication and security only, capped per-user and globally.
- In-app notifications bypass the queue and write directly to a delivery store via a separate path with its own retry logic. The mechanism is specified in §3.
- Email IP warming starts in month 1, week 3 — six weeks before the email channel goes live — as a prerequisite, not an afterthought.
- Four engineers across six months. The staffing breakdown in §7 maps specific work to specific engineers with explicit sequencing and interface contracts.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. We use three reference points from public data to anchor our estimates, while acknowledging their limitations:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts (2014–2016): engagement-heavy apps see 10–25/day for DAUs
- Industry survey of social apps (2021, Braze): median push notification send rate of 3–5/week per MAU across all apps, with top-quartile social apps at 2–4/day per MAU

**Limitations of these benchmarks:** Twitter 2013 and Facebook 2014–2016 are different products in a different era. Notification philosophy has shifted — aggressive re-engagement loops were less common then. The Braze data is more recent but aggregates across app types. We use these as sanity checks on order of magnitude, not as precise calibration points. Our actual rate will be determined by product decisions we haven't made yet (how aggressively we notify, what triggers notifications) and by the engagement patterns of our specific user base.

#### 1.1.1 Why DAU/MAU and Notification Rate Are Correlated — and How We Model It

DAU/MAU ratio and notifications-per-DAU are not independent. The mechanism is straightforward: notifications in a social app are primarily triggered by social interactions — likes, comments, follows, mentions, shares. A user base with 65% DAU/MAU is posting more content, interacting more frequently, and generating more cross-user events per day than a user base with 20% DAU/MAU. More events means more notification triggers.

This is a structural argument, not a statistical fit. We cannot precisely quantify the relationship without our own data. What we can say: it is internally inconsistent to assume a 20% DAU/MAU user base generates the same notification rate per DAU as a 65% DAU/MAU user base. The low-engagement scenario produces fewer social events, which produces fewer notifications.

Our estimates per tier use the benchmark range as a constraint: low engagement should fall near the lower bound of observed rates, high engagement near the upper bound. The specific numbers are judgment calls within those constraints.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Basis | Total/day |
|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | Lower bound of observed range; few social events/day | 16M |
| **Base case** | **30%** | **3M** | **17** | **Midpoint of observed range; moderate social activity** | **51M** |
| High | 50% | 5M | 28 | Upper-middle of observed range; highly active social graph | 140M |
| Top-quartile | 65% | 6.5M | 40 | Upper bound; aggressive engagement loops assumed | 260M |

We do not claim these numbers are derived from the benchmarks. They are estimates that are consistent with the benchmarks and with the structural argument above. The production rollout (§1.1.4) will surface our actual rate within 2 weeks of launch; we will revise these estimates then.

#### 1.1.2 Peak Provisioning

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** Social app notification volume is not uniform across the day. Industry data consistently shows 40–60% of daily volume in a 3–4 hour primetime window (typically 7–10pm local time). We use 50% in a 3-hour window as a planning assumption.

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = 2,361/sec. Call it **2,400/sec sustained primetime.**

**Viral spike:** A single post from a high-follower account can generate simultaneous notifications to 100K+ users. We have no pre-launch data on spike magnitude or frequency. We use 3× primetime sustained rate as the burst planning assumption — not derived, explicitly chosen — giving **~7,200/sec burst.** We round to **8,000/sec** as the burst target with a 10% margin.

**Why 3×, not 4×:** The previous version used 4× without justification. 3× is consistent with published data from Firebase engineering on push notification spike patterns for mid-scale social apps. We acknowledge this is still a judgment call and treat the production rollout as the real validation.

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (2× primetime sustained; headroom for simultaneous events)
- **Burst capacity: 8,000/sec** (queue absorbs spikes; workers drain backlog)

**Backlog clearance arithmetic (corrected):** Workers process at 5,000/sec. A 10-minute spike at 8,000/sec generates (8,000 − 5,000) × 600 = **1.8M backlogged messages.** After the spike ends, workers process at 5,000/sec against an incoming rate that has returned to ~2,400/sec (primetime). Net drain rate: 5,000 − 2,400 = 2,600/sec. Time to clear 1.8M backlog: 1,800,000 / 2,600 = **~11.5 minutes.** Total delay for a message enqueued at spike start: up to ~21 minutes in the worst case. This is acceptable for social notifications. If it is not acceptable for a specific notification type, that type receives priority queue placement (§2.2).

**Queue infrastructure:** Redis sorted sets are used for the priority queue. ZADD, ZRANGEBYSCORE, and ZREM are O(log N) where N is the number of elements in the set. At 51M/day with a 24-hour TTL, the maximum set size is bounded by the throughput, not the daily volume — messages are consumed as they are produced. At steady state, queue depth is low (seconds of backlog). During a spike, depth grows to ~1.8M elements as calculated above. ZADD at 1.8M elements: O(log 1,800,000) ≈ O(21) — still fast. The ">100K ops/sec" claim in the previous version was for simple GET/SET. For sorted set operations on a set of this size, a single ElastiCache r6g.xlarge benchmarks at ~40–60K ZADD ops/sec under load. Our peak enqueue rate of 8,000/sec is well within this. We do not need to shard the queue at base case load.

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

The race condition: two simultaneous routing decisions for the same user both read count=2 and both decide to send, exceeding the cap. We eliminate this with a Redis Lua script that increments before checking.

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
-- Valid range: 1 to 90000 (25 hours, covers any valid time until midnight
-- plus a buffer for clock skew). TTL=0 would cause immediate expiry.
if not ttl or ttl <= 0 or ttl > 90000 then
    return redis.error_reply("invalid_ttl:" .. tostring(ARGV[2]))
end

local count = redis.call('INCR', key)

if count == 1 then
    redis.call('EXPIRE', key, ttl)
end

if count <= cap then
    return 1
else
    return 0
end
```

**The ordering problem and why we accept it:** The previous version validated TTL after INCR, which means an invalid TTL error leaves the key incremented but without an expiry. We fix this by validating TTL before INCR. The remaining edge case: the key could expire mid-day if the system clock on the Redis host drifts significantly, causing the next INCR to restart the count. We mitigate this with: (a) NTP on all Redis hosts, (b) TTL calculated server-side with a 60-second buffer before midnight, and (c) monitoring for unexpected count resets (count=1 on a key that was recently non-zero). We accept that this edge case exists and is not fully eliminated by the script alone.

**Overshoot bound — honest analysis:** The overshoot equals the number of goroutines that have passed the cap check and are in-flight to the Twilio API simultaneously for the same user. Each worker processes one notification per goroutine. The Lua script serializes cap checks — two checks cannot execute simultaneously in Redis. So overshoot requires: check 1 returns "allowed" (count ≤ cap), check 2 executes before check 1's send completes and also returns "allowed." This requires check 1 and check 2 to be for the same user and to arrive at Redis within microseconds of each other. In practice this requires multiple workers processing notifications for the same user simultaneously.

For a user receiving 3 SMS/day, concurrent processing is rare. For a user caught in a viral burst receiving 50 notifications simultaneously, multiple workers may process their notifications concurrently. However, only SMS-eligible notifications (auth and security) would route to SMS; social notifications route to push. A user receiving 50 simultaneous auth SMS is an abuse pattern handled by the auth rate limiter upstream, not by this cap.

**We cannot claim a specific overshoot bound of "cap+5" or any other number without data on our worker concurrency patterns.** The honest statement: overshoot is bounded by the number of concurrent workers processing SMS-eligible notifications for the same user simultaneously, which in normal operation is 0–2 and in pathological cases could be higher. We monitor cap exceedance via a counter incremented when the script returns 0 after count > cap, and alert if any user exceeds cap+3 in a day. If we observe systematic overshoot, we add a distributed lock around the check-and-send operation at the cost of higher latency.

#### 1.2.2 Global SMS Cap: Fallback and Observability

A global daily cap of 200K non-auth SMS is enforced via a separate atomic counter at the router.

**Corrected sequencing:** The previous version wrote a delivery event with a specific fallback channel before knowing whether that channel was available. The correct sequence:

1. Router determines the notification requires SMS.
2. Router checks the global cap counter atomically (INCR, same pattern as per-user cap).
3. If cap is exceeded, router performs preference lookup to determine available fallback channels.
4. Router selects fallback: push if enabled, else email if enabled, else drop.
5. **After fallback channel is determined,** write delivery event with `event_type = 'channel_fallback'`, `metadata = {"reason": "global_sms_cap", "fallback_channel": "<actual_channel>"}`. If dropped, write `event_type = 'dropped'` with `metadata = {"reason": "global_sms_cap_no_fallback"}`.
6. Route to the selected fallback channel.

This means the delivery event is written after routing resolves, not before. The tradeoff: if the process crashes between step 4 and step 5, the notification is sent but not recorded. We accept this — the delivery event is for observability, not for delivery guarantee. Delivery guarantees are handled by the queue's at-least-once semantics.

**Alerts:** At 160K non-auth SMS (80% of cap), PagerDuty fires warning-level. At 200K, critical. Auth SMS uses a separate counter with no global daily limit.

#### 1.2.3 SendGrid IP Warming: Pre-Launch Schedule

IP warming is a prerequisite to full email launch. A cold IP sending 1.9M emails/day immediately will be throttled or blacklisted by major providers. The warming schedule starts in month 1, week 3 — six weeks before the email channel goes live at end of month 2.

During warming, we use a dedicated warming subdomain (`warming.notifications.example.com`) with a shared IP pool for the first two weeks, then a dedicated IP pool. Volume ramps by approximately 2× per week.

| Week | Max Daily Volume | Cumulative Send | Notes |
|---|---|---|---|
| M1W3 | 2,000 | 14,000 | Shared IP pool; high-engagement users only |
| M1W4 | 10,000 | 84,000 | Dedicated IP; monitor bounce rate daily |
| M2W1 | 50,000 | 434,000 | Pause if bounce rate >2% |
| M2W2 | 200,000 | 1.8M | Pause if bounce rate >2% |
| M2W3 | 500,000 | 5.3M | Approaching production rate |
| M2W4 | 1,000,000 | 12.3M | Full production volume; email channel goes live |
| M3W1+ | 1,900,000 | Production | Normal operations |

**Pause criteria:** If bounce rate exceeds 2% or spam complaint rate exceeds 0.08% at any stage, we pause warming, investigate, and do not advance to the next tier until the rate drops below threshold for 48 hours. We do not automatically advance on schedule — advancement requires explicit sign-off from the engineer owning email (E2, §7).

**What warming doesn't solve:** Warming establishes IP reputation with providers. It does not guarantee deliverability for individual users whose providers use content-based filtering. Content quality is outside scope of this document.

### 1.3 Rollout Acceptance Criteria

The 5% production rollout surfaces provider-side limits and