## Real Problems with This Design

### 1. The Outbox Poller Is a Correctness Bottleneck Nobody Addresses

The poller runs `FOR UPDATE SKIP LOCKED` with a `LIMIT 100` and a 100ms sleep. At 50M notifications/day, that's ~578/second average, ~1,750/second peak. The poller needs to process 175 rows per 100ms interval to keep pace at average load, and 350 rows at peak. The design shows a batch size of 100. At peak load, the outbox table accumulates unbounded backlog. The document acknowledges none of this and provides no analysis of whether a single poller thread can sustain the required throughput, what happens to latency as the backlog grows, or what "two poller instances" actually buys when both are hitting the same PostgreSQL table.

### 2. The In-App Bypass Breaks the Atomicity Guarantee Being Sold

The document's central correctness claim is that the outbox pattern ensures atomic writes. But in-app notifications are explicitly routed to a separate path that "bypasses the delivery queue." The transaction shown writes both `notifications` (in-app) and `notification_outbox` (for push/email/SMS) atomically. This means the in-app record commits but if the outbox relay fails permanently (5 retry exhaustion), push/email/SMS never deliver. The user sees the in-app notification but receives no push. Conversely, if the in-app write fails partway through, neither commits — but the document frames in-app as "cheap, don't need retry logic," which contradicts putting it inside the atomicity-critical transaction.

### 3. The Payload Storage Design Is Absent

The worker code does `redis.get(f"ntf:{notif_id}")` but nowhere in the design is there any description of where this payload is written, when, or by whom. The outbox row contains `payload JSONB`, and the Lua script moves `notif_id` references around — but the actual payload-to-Redis write step is never shown. The worker already has a code path for `payload is None` (TTL expiry), but the TTL is never defined. This is a missing piece of the system, not a minor omission.

### 4. The Visibility Timeout Recovery Has a Race Condition

The sweeper runs every 60 seconds and scans `inflight:worker:*` keys. If a worker crashes mid-batch with 50 items in flight, those items sit unprocessed for up to 60 seconds. For P0 notifications (authentication OTPs, security alerts), a 60-second delay is a user-visible failure. More critically, the sweeper moves items "back to the main queue with their original priority" — but there is no described mechanism ensuring the sweeper and a restarted worker don't both try to process the same item simultaneously. The Lua script handles dequeue atomicity, but the recovery path is described in prose without equivalent atomicity guarantees.

### 5. The 100M PostgreSQL Writes/Day Claim Is Treated as Trivially Acceptable

The document says "100M writes/day total. Within range for a properly configured Postgres instance." This is approximately 1,157 writes/second average and ~3,500/second at peak, across outbox inserts, outbox updates, delivery log writes, and notification inserts — all on the same instance. No connection pooling configuration is specified (PgBouncer is mentioned nowhere). No read/write separation is discussed. No disk I/O budget is analyzed. "Properly configured" is doing enormous work here with no supporting detail, on a team of 4 with no dedicated DBA.

### 6. The Circuit Breaker for P0 Is Not Actually a Circuit Breaker

The P0 queue depth check alerts on-call and enqueues anyway. This means P0 has no actual load protection — it will grow unboundedly under any sustained overload scenario. Meanwhile the alert fires continuously, creating alert fatigue for the on-call engineer. The document frames this as intentional ("P0 never shed") but provides no analysis of what happens to system stability when P0 grows without bound.

### 7. The Team Allocation Creates a Single Point of Failure for Critical Path Components

E1 owns "core pipeline, queue infrastructure, delivery workers." E2 owns "channel integrations." There is no overlap. If E1 is unavailable during a queue infrastructure incident, E2–E4 have no described ownership of the most critical system components. With 4 engineers and no QA, on-call rotation means any engineer can be paged for any incident, but the design assigns specialized knowledge to individuals without cross-training or documentation requirements.

### 8. The SMS Cost Analysis Contradicts the Traffic Model

The document correctly identifies blended international SMS costs of $0.02–$0.04/message and flags "$20,000–$40,000/day" as the realistic cost for 1M SMS/day. That's $600K–$1.2M/month. No social app with 10M MAU sustains this on SMS alone. The design's response is "hard spend caps described in Section 3.4" — but Section 3.4 is not present in the document. The cost problem is identified and then deferred to a section that doesn't exist.

### 9. The DLQ Has No Operational Path

The dead-letter queue holds items for 7 days. E4 gets a daily alert on DLQ depth. There is no described process for what happens next: no replay mechanism, no triage criteria, no escalation path, no user communication if a notification is permanently lost. "Forensic analysis and manual replay" is mentioned but not designed. For a system sending authentication OTPs, permanently lost notifications in the DLQ are a security and user-trust problem, not just an operational metric.

### 10. The Preference Check Timing Creates a Stale Data Window

Preferences are checked at routing time against a Redis cache. The document does not specify cache TTL or invalidation strategy. A user who opts out of push notifications may continue receiving them for the duration of the cache TTL after opting out. For a notification system, this is a compliance issue (CAN-SPAM, GDPR Article 21 right to object), not just a product quality issue. The design acknowledges none of this.

### 11. The Document Ends Mid-Sentence

The last visible line is `USER_RATE_` — the document is incomplete. Section 3.4 (SMS spend caps) is referenced but absent. The user-level rate limiting design is cut off. Any evaluation of the backpressure system is impossible because Layer 3 is not present.