## Real Problems with This Proposal

### 1. The Lua Script Has a Race Condition It Claims to Prevent

The proposal claims atomic token bucket execution, but the Lua script calls `GET` on two separate keys (`KEYS[1]` and `KEYS[2]`) and then `SET` on both. While Lua scripts are atomic in Redis, the script reads `tokens` and `last` as independent keys. If the bucket state is split across two keys, a Redis replica failover mid-script could leave them inconsistent. More concretely: the script doesn't use a single hash or a single key for state, so any tooling that resets or inspects one key without the other (monitoring, manual ops, a botched migration) silently corrupts the bucket state with no detection mechanism.

### 2. The Token Bucket Logic Is Wrong at Fleet Scale

The `refill_rate=200` in `try_consume_token` is specified as a fleet-wide minimum, but each worker calls this independently against a shared Redis key. The refill calculation uses wall-clock elapsed time, meaning every worker that calls the script refills the bucket based on elapsed time since the last call. With 50 push workers all calling this in rapid succession, the bucket gets refilled 50 times per tick — once per worker — compounding the refill rate by worker count. The 200/sec guarantee becomes 200×N/sec, which is not a minimum rate guarantee but an amplification factor. The proposal does not address this.

### 3. The Dispatch Loop Has a Structural P1 Starvation Path

The loop checks P0, then decides P2/P3 slots, then falls through to P1. Under conditions where `try_consume_token("p2")` consistently returns true (bucket full, low P2 volume) and P2 queue is empty, the loop consumes a P2 token, finds nothing, skips P3, then falls to P1. This is just wasted latency. But more seriously: if P2 queue is empty and P3 queue is empty, both token checks still execute and consume tokens, then P1 is serviced. The token consumption happens before confirming there's anything in those queues. At scale this means real P2/P3 token budget is consumed on empty queue checks, and the 200/sec guarantee is not actually delivered to real P2 messages.

### 4. Recovery Lock TTL Argument Is Circular

The proposal states the 90-second lock TTL "closes the gap" against concurrent recovery instances. The actual argument made is: lock TTL (90s) > cycle duration (60s), therefore no overlap. This only holds if the sweep process always completes within 60 seconds. The sweep calls `ZREMRANGEBYSCORE` — on a queue with millions of expired entries this is not instantaneous. If the sweep takes longer than 90 seconds (large expired set, Redis slowdown, network hiccup), the lock expires and a second instance acquires it while the first is still running. The proposal names this risk but then asserts it's closed by the TTL gap, which doesn't follow.

### 5. The Traffic Response Matrix Has No Feedback Mechanism

The matrix specifies responses at volume thresholds, but there is no specified mechanism to actually measure whether the response worked. "Provision additional worker instances (10–15 min)" at the 45–80M/day band has no follow-on: what metric confirms the provisioning was sufficient? What triggers escalation if it wasn't? The matrix reads as a decision tree that terminates at the action, not at a confirmed outcome. For a system with 6-month delivery pressure and 4 engineers, an undetected insufficient response could consume weeks.

### 6. PostgreSQL Connection Pool Exhaustion Is Understated as a Risk

The proposal acknowledges pool exhaustion but treats it as a metric-and-tune problem. At 1,575/sec peak throughput with ID-based dequeue, every message requires a PostgreSQL fetch. With 100 connections and a 5-second acquire timeout, a pool saturation event means workers are blocked for up to 5 seconds before backing off. During that window, queue depth grows. The proposal doesn't address what happens when pool exhaustion and a viral spike coincide — the very moment when fast delivery matters most is when the DB fetch path is most likely to saturate. The proposal mentions this is "a real operational risk" but then moves on without quantifying it against the SLA.

### 7. The 4-Minute Post-Spike Drain Calculation Assumes FCM Immediately Returns to Full Capacity

The viral spike recovery timeline ("cleared in approximately 4 minutes") is derived from 8,000/sec excess capacity after the spike. This assumes FCM rate limits return to full capacity the moment the spike ends. FCM's actual behavior under sustained 429 responses involves backoff windows on the provider side, not just the client side. The exponential backoff applied by the dispatch layer during the spike means workers are not immediately at full dispatch rate when the spike subsides — they're mid-backoff. The 4-minute figure is optimistic by an unspecified factor.

### 8. Worker Specialization Creates a Credential Management Problem That Is Not Addressed

The proposal notes that push workers contain FCM and APNs credentials and email workers contain SendGrid credentials. With per-channel, per-priority worker pools, this means credential rotation requires coordinated redeployment of every instance of the affected binary type. At 2–3 minute automated scaling, there could be many live instances. The proposal does not address how credential rotation is handled, whether workers cache credentials or fetch them at startup, or what happens during the rotation window when some instances have old credentials and some have new ones. For a system handling account recovery (P0), this is not a minor ops concern.

### 9. The "Month 1 Review" Decision Gate Has No Named Owner or Quorum

The proposal states "Team lead makes this call at the month-1 review, not reactively" for the >225M/day scenario. With 4 engineers, it's not specified who the team lead is, whether this is a unilateral decision, or what happens if the team lead is unavailable at the review point. This is not pedantry — the proposal explicitly frames pre-specification as protection against 3 AM reactive decisions, then leaves the highest-stakes decision with an unnamed owner and no backup.

### 10. In-App and Push Are Called Non-Additive Without Justification for All Cases

The proposal states push and in-app are "not additive for the same user at the same moment." This is true for a user actively in the app receiving a real-time in-app notification — you wouldn't also send a push. But the proposal applies this correction to the entire in-app volume figure, not just the overlap case. A user who was active 10 minutes ago, closed the app, and is now offline would receive a push for a new event. The same event also writes an in-app notification for when they return. These are additive in terms of system load even if not simultaneous from the user's perspective. The active-user correction as applied understates total write volume.