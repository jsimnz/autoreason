## Real Problems with This Proposal

### 1. The Idempotency Key Construction Is Broken

The proposal says the key must change on every attempt to avoid defeating provider-side deduplication. But the key is constructed as `event_id:attempt_number` *after* reading back the incremented value. If the worker crashes between delivery and recording completion, the recovery path re-enqueues the same `event_id`. On the next attempt, `attempt_number` increments again — but the *previous* delivery was made with `event_id:N`, and the new attempt uses `event_id:N+1`. The provider sees a *different* key and does **not** deduplicate. The proposal describes this as the desired behavior, but then claims provider-side idempotency keys "bound the duplicate window." They don't — they only deduplicate within a single attempt's retry window from the provider's perspective. The design conflates two different problems: provider-side deduplication of network retries (which this solves) and system-level duplicate delivery across crash recovery (which this explicitly cannot solve and the proposal incorrectly implies it mitigates).

### 2. The Claim Protocol Has a Race Condition the Proposal Doesn't Acknowledge

`zpopmin` removes the item from Redis atomically, but the subsequent `UPDATE ... WHERE state = 'enqueued'` is a separate operation. If two workers somehow receive the same item (e.g., during a Redis failover or Lua script absence), the `rows_updated == 0` check handles it. But the proposal uses `zpopmin` as if it's the concurrency primitive, then adds a database claim as a correctness backstop — without acknowledging that between `zpopmin` and the `UPDATE`, the worker can crash, leaving the item removed from Redis but never claimed in the database. The recovery query finds it in `state = 'enqueued'` and re-enqueues it, which is correct, but the proposal presents this as a clean design rather than identifying it explicitly as a crash window that the recovery path must cover. The AOF with `fsync=everysec` means up to 1 second of Redis queue state can be lost — during which `zpopmin` operations that succeeded are gone, and the database is the only recovery source. This dependency is not called out.

### 3. Dynamic Table Name Construction Is a SQL Injection Vector

The partition table name is constructed via string formatting from `partition_date`, which is parsed from a Redis sorted set member. The proposal shows:

```python
table = f"notification_events_{partition_date.replace('-', '_')}"
```

The `partition_date` value comes from a Redis member written at ingestion time. If Redis is compromised or a bug writes a malformed member, `partition_date` becomes attacker-controlled input in a raw SQL string. The proposal never mentions sanitizing or validating this value before interpolation. This applies to both the claim query and the read-back query.

### 4. The Email Volume Math Is Internally Inconsistent

The executive summary states "9% email, ~1.3M events/day." The detailed table in §1.1 shows 1.07M delivered emails/day at 20% opt-in. But 9% of 14.4M is 1.296M *events routed to email*, not delivered emails — and the batching analysis shows those events collapse to 1.07M actual sends. The executive summary conflates routed events with delivered messages. The peak rate calculation (`1.07M/day ÷ 86,400 × 3 ≈ 37/sec`) uses delivered volume but the channel distribution table uses event volume. These are different numbers being used interchangeably in different places.

### 5. The In-App Channel Has No Specified Delivery Guarantee

Push, email, and SMS all have explicit at-least-once delivery with idempotency key handling. In-app is stored in PostgreSQL and delivered via Redis Streams to WebSocket servers. The proposal never specifies what happens when a WebSocket server crashes after reading from the stream but before delivering to the client, or when the client is offline. Redis Streams with consumer groups provide at-least-once delivery to the WebSocket server, but delivery to the *client* is a separate problem entirely. The proposal doesn't address it. For a social app, in-app is 25% of volume (~3.6M/day) — this is not a minor gap.

### 6. The Preference Cache Invalidation Is Underspecified for the Suppression Case

§2.2 mentions a suppression cache (Redis Hash) with a reference to §3.3 for invalidation — but §3.3 is not included in this excerpt. The feedback processor writes to the suppression cache after receiving invalidity signals. The preference cache has TTL=5min. During those 5 minutes, a user whose token was just invalidated (e.g., uninstalled the app) can still receive routing decisions that send to the push worker, which will then hit APNs, get a 410, and re-trigger the feedback loop. This is described as an acceptable operational condition nowhere in the proposal. The duplicate suppression feedback loop rate is unquantified.

### 7. The Recovery Query Scope Is Not Defined

The proposal mentions "a PostgreSQL event log as recovery backstop" and shows indexes for `(state, created_at) WHERE state IN ('enqueued', 'claimed')`. But the recovery query itself is never shown. Specifically: what is the staleness threshold for re-enqueuing a `claimed` item? A worker that is slow (not crashed) could have a row in `claimed` state for 30 seconds. If the recovery job re-enqueues after 60 seconds, that's fine. If the threshold is wrong, the recovery job races with live workers. The proposal specifies the index but not the query, the threshold, the frequency of the recovery job, or how it avoids re-enqueuing items that are actively being processed.

### 8. The SMS P0 Fast Path Bypasses Aggregation But Not Suppression

The proposal states the SMS P0 fast path "bypasses the standard aggregation window check and uses a pre-warmed preference cache entry." It does not state whether the suppression check is also bypassed. For auth codes and account compromise alerts (the stated P0 use cases), sending to a suppressed number (e.g., one that replied STOP to Twilio) is a regulatory violation under TCPA, not just an operational issue. The proposal is silent on this.

### 9. Partition Pre-Creation Has No Failure Handling Specified

E4 is responsible for creating partitions 7 days ahead. The proposal notes that indexes are created on child partitions at creation time. But there is no specified behavior if the partition job fails and a partition doesn't exist when ingestion tries to write to it. PostgreSQL will throw an error — the insert fails, the event is lost unless the ingestion API handles it. With a 7-day buffer this is unlikely, but the proposal presents it as a solved operational concern when it's an unhandled failure mode.

### 10. The `event_id:YYYY-MM-DD` Format Breaks at Partition Boundaries

Events ingested just before midnight are assigned `created_at` of, say, `2024-01-22 23:59:59`. The Redis member encodes `2024-01-22`. If the item sits in the queue past midnight and is dequeued by a worker on `2024-01-23`, the worker constructs `notification_events_2024_01_22` as the target table — which is correct. But if the ingestion API's clock and the worker's clock disagree by even a second across a date boundary (NTP drift, timezone misconfiguration), the encoded date may not match the actual partition the row landed in. The worker queries the wrong partition, gets zero rows, discards the item silently (`rows_updated == 0`), and the notification is lost with no error. This is a silent correctness failure at a predictable daily boundary.