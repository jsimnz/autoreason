# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling 16M–260M notifications/day across push, email, in-app, and SMS channels, with a base case of 51M/day. Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

**Core architectural decision:** A tiered priority queue (critical, high, standard) with channel fanout, rather than per-channel queues or event streaming. The executive summary previously described this as a "single priority queue" — that was imprecise. The queue is a single Redis sorted set using priority-weighted scores, not three separate queues. Priority determines dequeue order within one data structure. The tradeoff: per-channel queues allow independent scaling and failure isolation but add operational complexity we cannot staff. We revisit this if we reach the top-quartile engagement tier, with a defined 6-week lead time for that architectural change. Priority tiers are fully specified in §2.2.

**The 21-minute delay is a product decision, not an infrastructure default.** The backlog clearance arithmetic produces a 21-minute worst-case delay for standard-priority social notifications under sustained spike conditions. Whether this is acceptable depends on product requirements we do not own. §2.2 states the tradeoff explicitly and requires product sign-off, not infrastructure assumption. Time-sensitive notification types — direct messages, mentions — are assigned high priority and clear within 3 minutes under the same spike conditions. The 21-minute figure applies only to standard-priority notifications (likes, generic activity) that product may reasonably decide can tolerate batching.

**What this document covers and doesn't:** Sections 1–7 cover scale modeling, channel design, queue architecture, infrastructure, failure handling, preference management, and staffing. What it does not cover: notification content generation (upstream responsibility), A/B testing of notification copy, and analytics beyond delivery tracking.

**Key decisions summarized:**

- We provision for the base case (51M/day) with a defined scale-up path. The high tier (140M/day) requires horizontal scaling only. The top-quartile tier (260M/day) requires architectural change with a 6-week lead time.
- DAU/MAU ratio and per-user notification rate are modeled as correlated variables. The sensitivity table reflects this. The specific numbers are judgment calls anchored by industry benchmarks, not derived from them — §1.1.1 is explicit about this distinction.
- Push handles 76% of volume at near-zero marginal cost. Email at $1,500/day represents 48% of channel cost for 3.7% of volume; §1.2.3 addresses whether this cost is justified and whether SendGrid Pro is the right tier. SMS is reserved for authentication and security only, enforced at the router level with atomically-enforced per-user and global caps — both fully specified in §1.2.1 and §1.2.2.
- In-app notifications bypass the queue for latency reasons and write directly to a dedicated delivery store via a separate path with its own retry logic. The mechanism is specified in §3.
- Email IP warming starts in month 1, week 3 — but only if SendGrid account provisioning, dedicated IP allocation, and DNS configuration are complete. §1.2.3 identifies these as procurement prerequisites with explicit contingency if they slip.
- The 5% production rollout has explicit acceptance criteria, per-channel stop thresholds, and defined recovery criteria. Stop thresholds without recovery criteria are not criteria — they are delegated decisions. §1.1.4 specifies what "resolved" means before resuming.
- The 5% rollout validates steady-state behavior, not burst behavior. Burst validation requires a dedicated load injection test run concurrently with the rollout. §1.1.3 specifies both.
- Redis handles the notification queue, SMS cap enforcement, and preference cache — three critical functions with different failure modes. §4.2 specifies separate Redis deployments for each function, their failure behavior, and degraded-mode operation when unavailable.
- Four engineers across six months. §7 maps specific work to specific engineers with explicit sequencing, interface contracts, and the feasibility argument that can actually be evaluated.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

We do not know our notification rate before launch. We use three reference points from public data to anchor estimates, while acknowledging their limitations:

- Twitter/X internal data (2013, leaked): ~8 notifications/day for active users
- Facebook engineering posts (2014–2016): engagement-heavy apps see 10–25/day for DAUs
- Industry survey of social apps (2021, Braze): median push send rate of 3–5/week per MAU across all apps; top-quartile social apps at 2–4/day per DAU

**Limitations of these benchmarks:** The Twitter and Facebook data are from a different era with different notification philosophies. The Braze data is more recent but aggregates across app types. We use these as sanity checks on order of magnitude, not precise calibration. Our actual rate will be determined by product decisions not yet made and the engagement patterns of our specific user base. The production rollout (§1.1.4) will surface our actual rate within two weeks; we will revise estimates then.

#### 1.1.1 Why DAU/MAU and Notification Rate Are Correlated — and the Limits of That Claim

Notifications in a social app are primarily triggered by social interactions — likes, comments, follows, mentions, shares. A user base with 65% DAU/MAU is posting more content, interacting more frequently, and generating more cross-user events per day than a 20% DAU/MAU user base. More events means more notification triggers. This is a structural argument about causation, not a statistical fit to data.

**The circular reasoning problem:** The benchmarks cited above constrain the plausible range of notifications/DAU/day. The specific numbers in the table below (8, 17, 28, 40) are judgment calls within that range, chosen to be consistent with the structural argument. They are not derived from the benchmarks. We are not claiming the benchmarks validate these numbers — we are claiming the numbers are plausible given the benchmarks and the structural argument. The distinction matters: if we are wrong about the specific numbers, we will discover this in the production rollout and revise. The benchmarks are not a defense of the numbers; they are a sanity check on the order of magnitude.

| Engagement Tier | DAU/MAU | DAU | Notifs/DAU/day | Basis | Total/day | Peak/sec (burst) | Infrastructure Posture |
|---|---|---|---|---|---|---|---|
| Low | 20% | 2M | 8 | Lower bound of observed range; judgment call | 16M | ~4,500 | Base provisioning sufficient |
| **Base case** | **30%** | **3M** | **17** | **Midpoint of observed range; judgment call** | **51M** | **~8,000** | **Base provisioning; scale trigger at 35% DAU/MAU** |
| High | 50% | 5M | 28 | Upper-middle of range; judgment call | 140M | ~25,000 | Scale-up runbook required before launch |
| Top-quartile | 65% | 6.5M | 40 | Upper bound; judgment call | 260M | ~40,000 | Architectural change; per-channel queues; 6-week lead time |

**How we track DAU/MAU:** Weekly rolling average via the existing analytics pipeline. Monthly review checks the 7-day average against scale triggers. If the 35% threshold is crossed, the scale-up runbook is initiated before the next review cycle.

#### 1.1.2 Peak Provisioning: Stated Assumptions, Not Derived Precision

**Base average rate:** 51M ÷ 86,400 = 590/sec

**Primetime concentration:** Industry data consistently shows 40–60% of daily social notification volume in a 3–4 hour primetime window. Using 50% in a 3-hour window:

Primetime sustained rate: (51M × 0.50) / (3 × 3,600) = **~2,360/sec sustained**

**Viral spike:** A single post from a high-follower account can generate simultaneous notifications to 100K+ users. We use 3× primetime sustained rate as the burst planning assumption — consistent with published Firebase engineering data on push spike patterns for mid-scale social apps, and explicitly a judgment call. This gives **~7,100/sec**, rounded to **8,000/sec** with a 10% margin.

**Provisioning targets:**
- **Sustained capacity: 5,000/sec** (~2× primetime sustained; headroom for simultaneous events)
- **Burst capacity: 8,000/sec** (queue absorbs spikes; workers drain backlog)

**Backlog clearance arithmetic and its product implications:**

Workers process at 5,000/sec. A 10-minute spike at 8,000/sec generates (8,000 − 5,000) × 600 = 1.8M backlogged messages. After the spike, net drain rate is 2,640/sec. Time to clear: ~11.5 minutes. Total worst-case delay for a message enqueued at spike start: **~21 minutes**.

This number has different implications for different notification types:

| Notification Type | Priority Tier | Max Acceptable Delay | 21-Minute Delay Acceptable? |
|---|---|---|---|
| Auth/security SMS | Critical | <30 seconds | No — receives dedicated worker pool |
| Direct messages | High | <3 minutes | No — high-priority dequeue; clears in ~3 min |
| Mentions, replies | High | <3 minutes | No — same as above |
| Likes, follows | Standard | Product decision | **Requires product sign-off** |
| Digest/batch | Standard | Product decision | Likely yes by design |

**We are not declaring 21 minutes acceptable for social notifications.** We are identifying it as the worst-case delay for standard-priority notifications and requiring product to make that call explicitly. If product determines that likes and follows must deliver within 5 minutes, we provision additional workers to sustain 7,000/sec — eliminating the backlog faster at ~$800/month additional compute cost. This is a product decision with a known infrastructure cost; it should not be made silently inside an infrastructure document.

**Queue infrastructure note:** Redis sorted set operations are O(log N). At a spike-peak depth of 1.8M elements, O(log 1,800,000) ≈ O(21). A single ElastiCache r6g.xlarge handles ~40–60K sorted set ops/sec under load. Our peak enqueue rate of 8,000/sec is well within this; we do not need to shard the queue at base case load.

#### 1.1.3 Validation Strategy: Synthetic Load Testing and Burst Injection

**The 5% rollout limitation:** A 5% production rollout generates 5% of real traffic. A viral spike at 5% scale is not a viral spike — a high-follower account with 100K followers reaches 5,000 users in the rollout cohort. The burst behavior we need to validate cannot manifest at 5% exposure. The rollout validates steady-state behavior, provider error rates, token validity, and preference cache performance. It does not validate burst assumptions.

**Two-track validation:**

*Track 1 — Synthetic load testing (month 1):*
- Queue throughput: Redis sorted set at 5,000 enqueue/dequeue ops/sec without latency degradation
- Worker throughput: 40 workers processing 5,000 messages/sec without backlog accumulation
- Database write rate: RDS handling delivery event writes at base case load
- Preference cache hit rate: Redis sustaining >95% hit rate under synthetic load
- **Burst injection:** Synthetic spike to 8,000/sec for 10 minutes; measure backlog depth, drain time, and per-priority-tier latency. This is the only way to validate burst behavior before launch.

*Track 2 — Production rollout (weeks 1–2 post-launch):*
- Provider error rates (FCM, APNs, SendGrid, Twilio) under real device tokens and real email addresses
- Token invalidity rates
- Actual notification rate per DAU (primary calibration of our estimates)
- Steady-state latency under real load

**What synthetic testing cannot validate:**
- FCM/APNs behavior under load (provider-side rate limits require real device tokens)
- SendGrid IP warming constraints
- Twilio carrier rate limits (tested against Twilio sandbox in month 2)
- Real token distribution patterns

**Burst injection test acceptance criteria:**
- Backlog clears within 15 minutes of spike end at standard priority
- High-priority notifications deliver within 3 minutes at peak spike depth
- Critical notifications deliver within 30 seconds regardless of spike depth
- No worker crashes or queue corruption during or after spike

#### 1.1.4 Production Rollout: Stop Thresholds and Recovery Criteria

Stop thresholds without recovery criteria are delegated decisions, not engineering criteria. Under launch pressure, "the on-call engineer and EM decide" reliably produces optimistic calls. The following table specifies both when to stop and what must be true before resuming.

| Channel | Metric | Warning | Stop Threshold | Recovery Criteria Before Resuming |
|---|---|---|---|---|
| Push (FCM) | Error rate (4xx + 5xx) | >2% over 15 min | >5% over 5 min | Error rate <1% sustained for 30 minutes; root cause identified and documented |
| Push (APNs) | Invalid token rate | >5% over 1 hour | >15% over 15 min | Token cleanup job run and verified; invalid rate <3% for 1 hour |
| Email | Bounce rate | >2% over 1 hour | >5% over 15 min | Bounce rate <1% for 2 hours; suppression list updated |
| Email | Spam complaint rate | >0.08% over 1 hour | >0.3% over 15 min | Complaint rate <0.05% for 2 hours; content or list quality issue identified |
| SMS | Carrier error rate | >3% over 30 min | >10% over 10 min | Error rate <2% for 30 minutes; carrier routing verified |
| All channels | P99 end-to-end latency | >30 sec | >120 sec | P99 <20 sec for 30 minutes; worker count and queue depth verified |
| Queue | Sustained depth (non-spike) | >50K messages | >200K messages | Queue depth <10K for 15 minutes; worker autoscaling verified |

**Rollout gates:** 5% → 25% → 100%. Advancement requires:
1. 24 hours at current tier with no stop-threshold breaches
2. No open P1 incidents
3. All recovery criteria met for any previously triggered stop
4. Explicit written sign-off from on-call engineer in the incident log — not verbal, not assumed

Advancement does not happen automatically on schedule. The default is to stay at the current tier until sign-off is given.

**Rollout abort criteria:** If the same stop threshold is triggered three times within 48 hours after recovery, the rollout is aborted and does not resume until a design review is completed. Three triggers of the same threshold indicates a systemic problem, not a transient one.

### 1.2 Channel Mix and Cost Model

| Channel | % of Volume | Volume/day | Unit Cost | Daily Cost | Notes |
|---|---|---|---|---|---|
| Push | 76% | ~39M | ~$0.00001 | ~$390 | FCM/APNs free; infra cost only |
| In-app | 20% | ~10M | ~$0.000005 | ~$50 | DB write cost only |
| Email | ~3.7% | ~1.9M | ~$0.0008 | ~$1,500 | See §1.2.3 for vendor evaluation |
| SMS | ~0.3% | ~150K | $0.0079 | ~$1,185 | Auth + security only |
| **Total** | | **~51M** | | **~$3,125/day** | ~$94K/month |

#### 1.2.1 Hard SMS Cap — Atomically Enforced (Per-User)

The race condition: two simultaneous routing decisions for the same user both read count=2 and both decide to send, exceeding the cap. We eliminate this with a Redis Lua script that increments before checking:

```lua
-- sms_cap_check.lua
-- Returns 1 if send is allowed, 0 if cap exceeded, error on invalid input
-- KEYS[1]: "sms_cap:{user_id}:{date_utc}"
-- ARGV[1]: cap (integer, e.g. 3)
-- ARGV[2]: ttl in seconds until midnight UTC (pre-calculated by caller)

local key = KEYS[1]