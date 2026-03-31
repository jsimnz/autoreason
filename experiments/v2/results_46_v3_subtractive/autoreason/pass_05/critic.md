## Real Problems with This Proposal

### 1. The Fanout Math Is Broken

The proposal says "17 events/DAU/day represents events *received* per active user" but then multiplies 3M DAU × 17 to get 51M. If non-DAU users also receive notifications from DAU activity, the multiplier should be applied to MAU-scale recipients, not DAU-scale. The proposal acknowledges this problem in the same sentence it makes the error. The actual recipient-notification event count could be 10M × 17 = 170M, which blows up every downstream assumption. The document never resolves this contradiction.

### 2. Email Channel Distribution Is Internally Inconsistent

The table shows email at 9% of 31M = ~2.8M events, then says this becomes "700K–1.4M emails" via batching — a 2–4× reduction. No batching logic is described that produces this range. Later, email workers are sized for "116/sec peak," which back-calculates to ~10M emails/day, not 2.8M events or 700K–1.4M emails. The three numbers are irreconcilable and no single consistent figure is ever established.

### 3. Worker Pool Priority Subdivision Doesn't Work as Described

The proposal says "push has 15 P0, 30 P1, 15 P2/P3 workers" and that "P0 pool drains its queue before P1 workers pick up P1 work." These are described as separate worker pools per priority tier, but they're also described as workers within a single per-channel pool. If they're separate pools, P0 workers sit idle during non-P0 periods — which is most of the time, since P0 is security/auth events that explicitly don't go to push. If they share a pool with priority routing, the "15/30/15 subdivision" is meaningless. The design claims both simultaneously.

### 4. The Local Worker Cache Creates a Correctness Problem It Claims to Solve

The proposal introduces a per-worker in-process token suppression cache (TTL=5min) to prevent sends to invalid tokens before the feedback processor writes the suppression record. But with 60 push workers, each has an independent cache. Worker A marks a token invalid; Worker B, which hasn't seen the invalidation event, processes a queued notification for the same token and sends it anyway. The local cache only prevents the *same worker* from re-sending. The proposal presents this as solving the race condition, but it only narrows it.

### 5. The WebSocket Offline Path Has an Unacknowledged Gap

The document says: "If no registry entry: user is offline; skip stream publish." But a user can be online on a WebSocket server whose registry entry hasn't been written yet (race between connection establishment and registry write), or whose entry just expired due to a missed heartbeat. The proposal treats "no registry entry" as equivalent to "offline" with no acknowledgment that this conflates two distinct states. Notifications during this window are silently dropped from the real-time path with no mechanism to detect the drop occurred.

### 6. APNs Silent Probe Section Is Truncated

Section 3.1 ends mid-sentence: "Using non-delivery as a validity" — the document is cut off. This is a submitted proposal with an incomplete section, which means the token validation backstop design is literally unspecified.

### 7. The 40% Opt-Out Framing Is Inverted

The executive summary says "if we're wrong in the pessimistic direction, we're over-provisioned; if we're wrong in the optimistic direction, we have a real capacity problem. The 40% base case is the conservative planning choice." This is backwards. A *higher* opt-out rate means *fewer* notifications, which means the pessimistic scenario (60% opt-out) is actually the lower-load scenario. The "conservative planning choice" for capacity should be the *lowest* opt-out rate (20% = 41M/day), not the middle estimate. The proposal then designs for 40% base case and says it "verifies operability" at 20% — but operability at higher load is exactly what conservative capacity planning should guarantee by design, not verify as an afterthought.

### 8. The APNs Timestamp Suppression Logic Is Incomplete

The proposal says tokens registered *after* Apple's invalidity timestamp are valid and should not be suppressed. But it doesn't address what happens when a user reinstalls the app and gets a new token that is *never* explicitly registered against the old device record in the system — the old token just stops appearing in sends. The timestamp comparison logic assumes a clean device-to-token mapping that the proposal never establishes exists in the data model.

### 9. No Acknowledgment of APNs HTTP/2 Connection Limits

The proposal specifies 50 persistent HTTP/2 connections to FCM with 10 concurrent streams each. For APNs, connection configuration is entirely absent despite APNs having a documented per-connection stream limit (currently 1,500 concurrent streams per connection). At ~7M iOS push/day (35% of 20M), that's ~240/sec average, ~720/sec peak. With no stated connection pool configuration for APNs, the worker pool sizing derivation is incomplete for the iOS path specifically.

### 10. The Redis Sorted Set Queue Design Has No Stated Persistence Configuration

The proposal uses Redis sorted sets as the primary queue for all channels. Redis persistence (RDB vs AOF vs both) is never specified. In a crash-before-persist scenario with RDB snapshotting, notifications enqueued since the last snapshot are lost with no recovery path — they're not in PostgreSQL, not in a DLQ, and the originating events are not described as being replayable. For a notification system, this is a data loss scenario, not just a delay.