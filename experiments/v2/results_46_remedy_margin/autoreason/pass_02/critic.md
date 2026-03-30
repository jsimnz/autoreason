## Real Problems

### 1. The 17 Notifications/User/Day Figure Is Load-Bearing and Unsupported

The entire system is sized around DAU × 17 = 50M/day. The document calls this "industry avg for engaged social apps" with no citation. This number drives queue worker counts, Redis sizing, database partitioning strategy, and cost projections. If actual volume is 3× higher (which is plausible — some social apps push 50+ notifications/day to engaged users), every sizing decision in the document is wrong simultaneously.

### 2. The Peak Multiplier Is Probably Wrong in a Specific Way

A 3× peak multiplier applied to a daily average gives ~1,750/sec. But social app notification spikes are not smooth morning/evening curves — they're event-driven. A viral post, a breaking news hook, or a celebrity action can produce a near-instantaneous spike across millions of users. The 3× figure describes diurnal variation, not event-driven spikes. The system has no stated mechanism for absorbing a 10× or 20× spike that lasts 90 seconds.

### 3. P0 Worker Count Cannot Guarantee the Stated Latency

The document claims P0 items are processed "typically under 2 seconds" because P0 workers only consume from the P0 queue. But 5 P0 workers is an arbitrary number with no derivation. If P0 volume spikes (a security incident affecting many users simultaneously), 5 workers processing sequentially can queue. There's no analysis of P0 arrival rate, P0 worker throughput, or what happens when P0 queue depth grows. The correctness argument for separate queues is valid; the specific latency claim is not supported.

### 4. The Blended SMS Rate Assumes a Traffic Distribution With No Basis

The document correctly identifies that international rates matter, then produces a specific regional breakdown (40% US, 25% Western Europe, etc.) that is entirely fabricated. A social app with 10M MAU could be 80% US or 80% Southeast Asia depending on the product. The blended rate of $0.034 could be off by 2× in either direction. The document treats this fabricated distribution as if it resolves the cost uncertainty, when it actually just moves the uncertainty one level deeper.

### 5. E4's Scope Is Structurally Impossible

E4 owns Redis HA, Postgres operations, monitoring, alerting, and DevOps for a system doing 50M operations/day. The document acknowledges this is bounded, but the exclusions listed for E4 are "feature development" — not a meaningful reduction in operational load. Redis HA alone (replication, failover testing, capacity management) plus Postgres operations (vacuuming, index maintenance, partition management, query performance) plus on-call response for a system with this many failure modes is more than one engineer's full capacity. Naming the exclusion doesn't change the arithmetic.

### 6. Write-Through Cache Invalidation Has a Race Condition That Is Not Acknowledged

The preference cache design says: write to Postgres, then invalidate and rewrite Redis. Between the Postgres write and the Redis rewrite, another process can read the old value from Redis and cache it with a fresh 5-minute TTL. The document describes this as handling "the edge case where cache invalidation fails" but the race is not a failure case — it's a normal concurrent operation. The result is that preference changes can take up to 5 minutes to propagate even when all systems are healthy, which is described as acceptable, but the race that makes this worse than 5 minutes is not addressed.

### 7. The Digest Carry-Forward Logic Has an Unacknowledged Failure Mode

`mark_events_sent` is called before the email is actually sent. The comment says "if send fails, status stays 'pending'" — but `mark_events_sent` has already been called. These two statements contradict each other. If the intent is to mark sent only after confirmed delivery, the ordering is wrong. If the intent is optimistic marking with rollback on failure, the rollback logic is absent. This is the exact data loss risk the document claims to have solved.

### 8. APNs Token Refresh Has a Multi-Instance Problem

`APNsTokenManager` uses a threading lock that is process-local. With multiple worker processes (the document describes 40 workers across three pools), each process independently manages token state. At the 45-minute refresh boundary, all processes will simultaneously generate new tokens. This is harmless for correctness but means the stated "15-minute buffer against clock skew" is not actually a buffer — it's a window during which some processes are using tokens of different ages. More importantly, if token generation fails in one process, there's no cross-process fallback.

### 9. FCM Batch Rate Has No Burst Handling

"FCM allows ~600 req/sec per project; we operate at 400" is stated as if operating below a limit is sufficient. FCM's rate limits are enforced with exponential backoff requirements on 429 responses. At peak (1,750 notifications/sec, 70% push = 1,225/sec, batched at 500 = ~2.5 req/sec per batch), the math works until a backlog develops. Once workers are retrying with backoff, new items queue behind them, and the effective throughput collapses faster than the rate limit alone suggests. There's no analysis of queue depth growth during a FCM rate-limit event.

### 10. The 90-Day Token Purge Interacts Badly With the Invalidation Logic

Tokens are invalidated immediately on 404/410 responses and marked `is_valid = false`. The weekly maintenance job purges tokens with `last_used_at` older than 90 days. A token that has never been used successfully (registered but user never received a notification) has a null `last_used_at` and will never be purged by the maintenance job. The schema has no fallback condition for null `last_used_at`, so these tokens accumulate indefinitely.

### 11. SendGrid Cost Comparison Is Inverted

The document says AWS SES would be "~$400/day cheaper at volume" than SendGrid Pro at $1,500/month. $400/day is $12,000/month. The cost comparison claims a $12,000/month saving is being passed up for deliverability tooling, while the monthly cost of SendGrid Pro is $1,500. This arithmetic is wrong in a way that undermines the stated justification for the provider choice.

### 12. The Digest Minimum Threshold Creates a Perverse Retention Problem

If a user has fewer than 3 digest items, events carry forward up to 7 days before expiring. A low-engagement user — exactly the user re-engagement emails are meant to reach — will have their activity notifications silently expire before being sent. The re-engagement email trigger (7-day inactivity) and the digest expiry (7 days) operate on the same timescale with no coordination, meaning the system can simultaneously decide a user needs re-engagement and expire the content that would make the re-engagement email relevant.