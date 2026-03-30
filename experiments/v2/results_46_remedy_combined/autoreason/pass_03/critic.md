## Real Problems with This Proposal

### 1. The 15 notifications/user/day figure is doing enormous work with no validation

The entire scale model — 90M push/day, worker counts, SQS costs, everything — derives from this single estimate described as "industry range 10–20 for active social apps." This is not a basis. Active social apps vary by orders of magnitude in notification volume. A social app that's primarily a feed product sends far fewer than one that's primarily a messaging product. If the real figure is 5, the architecture is overbuilt. If it's 30, the FIFO queue limits become relevant. The proposal acknowledges uncertainty but then proceeds to build everything on the estimate anyway.

### 2. FIFO queue throughput is dangerously close to limits and the math is wrong

The proposal states P0 and P1 "stay well within" the 3,000 messages/second FIFO limit. But no actual P0/P1 volume breakdown is provided. At 3× peak, total throughput is 12,900/sec. If even 25% of traffic is P1 (high: DMs, mentions on a social app — plausibly much higher), that's 3,225/sec against a 3,000/sec limit. The proposal doesn't model this. A social app where DMs and mentions are primary engagement vectors could easily saturate P1 at peak.

### 3. The Redis idempotency lock has a race condition the proposal doesn't fully resolve

The code comments "Lock holder may have crashed within its TTL; proceed" — but if two workers both reach this branch simultaneously after the TTL expires, both will regenerate the token and both will call `setex`. The last writer wins for token storage, but both will attempt to delete the lock key, and more importantly, both will make a Secrets Manager API call simultaneously. At scale with many workers, this isn't a theoretical problem. The proposal identifies the issue and then effectively shrugs.

### 4. The fallback for APNs token on Redis unavailability creates silent send failures

"Log an error and pause sends" is stated as acceptable behavior when Redis is unreachable. For P0 traffic — OTPs and security alerts — a send pause is not acceptable by the proposal's own definition of P0. The proposal contradicts itself: P0 is described as requiring durability guarantees that Redis doesn't provide, but the APNs token management for P0 depends entirely on Redis availability.

### 5. E2 "owns" cross-channel consistency but has no time to do it

E2's primary responsibility is channel integrations for four channels (APNs, FCM, SendGrid, Twilio) plus cross-channel consistency. Channel integrations alone — handling provider-specific APIs, feedback loops, token invalidation, bounce processing, delivery receipts — is more than one engineer's full-time work for six months. Cross-channel consistency during in-flight preference updates is a genuinely hard distributed systems problem. Naming an owner doesn't allocate time.

### 6. The OTP SMS cost exposure is presented as a decision for Finance and Security, but the engineering default is silence until $5,000/day

The alarm threshold is $5,000/day. The proposal acknowledges a major security incident could cost $79,000/day. Between $0 and $5,000/day — which covers a moderate credential stuffing attack at ~630K forced re-auths — there is no alert and no automated response. This is not "instrumenting everything so consequences are visible." It's a $4,999/day blind spot.

### 7. No DLQ processing strategy is described despite being called out as operational surface

The proposal explicitly acknowledges "four dead-letter queues to monitor." DLQ messages represent notifications that failed all retries. The proposal says DLQs exist and have alarms, but never describes what happens to messages in them — are they retried manually, dropped, sent via fallback channel, or used to trigger user-facing error states? For P0 (OTPs), a message sitting in a DLQ means a user cannot authenticate. This is not a minor omission.

### 8. The 60-second preference cache TTL creates a compliance window that isn't acknowledged as a compliance problem

The proposal frames the 60-second staleness as a UX tradeoff. In jurisdictions with GDPR or CAN-SPAM requirements, sending a notification to a user who has opted out — even for 60 seconds — is a legal violation, not a UX annoyance. The proposal says "legal compliance" decisions require authorization from outside engineering, but it has already made the legal-risk decision by choosing 60-second TTL as the engineering default. The decision point surfaced to legal is not "what TTL should we use" — it's presented as a fait accompli.

### 9. The in-app store on PostgreSQL with hash partitioning has no retention or read scaling strategy

30M in-app notifications/day into PostgreSQL is mentioned and diagrammed but never designed. Hash partitioning is named but partition count, key selection, and the read path for the notification inbox (which is a user-facing latency-sensitive query) are absent. At 30M rows/day, without a retention policy this table becomes unmanageable within weeks. There's no mention of archival, TTL, or how the inbox query performs as the table grows.

### 10. Four engineers building this in six months is not examined critically

The proposal lists what each engineer owns but never examines whether the scope is achievable. E4 alone owns reliability, monitoring, failure handling, infrastructure, a test harness covering six named failure classes, and on-call rotation. The test harness alone is estimated at 15% of E4's time — but the failure classes named (duplicates, missed suppressions, incorrect aggregation, timezone errors, broken unsubscribe links) each represent non-trivial test surface. This is a budget assertion, not a plan.