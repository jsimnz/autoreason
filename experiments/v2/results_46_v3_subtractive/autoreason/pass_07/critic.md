## Real Problems with This Proposal

### 1. The Claim Protocol Has a Distributed Transaction Problem

The worker claim protocol performs two separate database operations: the claim UPDATE and the deliver-then-log sequence. If the worker crashes after `deliver()` succeeds but before writing `state = 'delivered'` to the database, the event stays in `claimed` state. After 10 minutes, the recovery job resets it to `enqueued` and re-enqueues it. The notification gets delivered twice. The proposal explicitly claims this design "eliminates the duplicate-delivery race" — that claim is false. It narrows the race window but does not eliminate it.

### 2. The Recovery Job Has a TOCTOU Race It Claims to Have Fixed

The recovery job reads candidates in one query, then updates each with a conditional UPDATE. Between the SELECT and the per-row UPDATE, a live worker can claim the event. The proposal acknowledges this race for the naive design and claims the fix is the conditional UPDATE — but the conditional UPDATE in the recovery job checks `state = 'enqueued' OR (state = 'claimed' AND claimed_at < threshold)`. A worker that claimed the event 9 minutes ago (within the threshold) is still live and mid-delivery. The recovery job will not touch it. But a worker that claimed it 11 minutes ago and is still legitimately running (slow provider, retry backoff) will have its event reset and re-enqueued while delivery is in progress. The 10-minute threshold is asserted without derivation from actual retry/timeout budgets.

### 3. The Partial Index Is Defined at the Parent Table Level

```sql
CREATE INDEX ON notification_events (state, created_at)
    WHERE state = 'enqueued';
```

In PostgreSQL, partial indexes defined on a partitioned parent table are not automatically created on existing or future child partitions. The DDL will either error or create a non-functional index depending on version. The recovery query relies on this index for performance — without it, the query scans full partitions at exactly the moment it matters most.

### 4. The Dequeue Loop Has a Polling Anti-Pattern at Scale

The worker sleeps 10ms when all queues are empty. With 30 push workers all polling simultaneously on empty queues, that's 30 × 100 ZPOPMIN calls/second against Redis at idle. More importantly, at the moment a burst of P0 notifications arrives, average detection latency is 5ms per worker. The proposal does not acknowledge this or justify it as acceptable — it presents the sleep as straightforward.

### 5. The Email Volume Math Is Internally Inconsistent

The proposal derives 1.0M delivered emails/day from a 1.3× batching reduction factor, then sizes the worker pool against ~35/sec peak. But the 1.3× reduction factor is derived assuming λ=1.3 events/recipient/day. If email is 9% of 14.4M = 1.296M events across ~1M recipients, that's 1.296 events/recipient/day — but only email-opted-in recipients receive email. The denominator should be email-opted-in users, not total recipients. If email opt-in is 20% of 3M DAU = 600K users, λ jumps to ~2.16, the batching reduction increases meaningfully, and the delivered volume and worker sizing both change. The proposal does not identify what fraction of users have email enabled.

### 6. The WebSocket Section Is Incomplete and Cut Off

Section 2.6 ends mid-sentence: "user is mid-handshake and the registry entry hasn—". This is not a minor editorial issue. The WebSocket fan-out is listed as a core architectural choice in the executive summary, and the gap detection logic — distinguishing "connecting" from "connected" from "offline" — is explicitly called out as a design differentiator. The actual mechanism is absent from the document.

### 7. The `token.invalidated` Event Stream Has No Delivery Guarantee Specified

E2 publishes `token.invalidated` events to a Redis Stream; E3 consumes via a named consumer group. Redis Streams with consumer groups require explicit ACK. If E3's feedback processor crashes after reading but before writing the suppression record, the event will be redelivered on restart — but only if the consumer group is configured with a pending entry timeout and a separate recovery consumer. None of this is specified. If the stream is configured with `MAXLEN` trimming, unprocessed events can be lost before E3 consumes them. The proposal treats this as a clean decoupling but leaves the reliability contract undefined.

### 8. The Priority Scheme Is Undefined for the Router

The proposal specifies P0–P3 queues and a dequeue loop that respects them, but §2.1 and §2.2 never define what makes a notification P0 versus P1 versus P2. The router is responsible for priority assignment, but the assignment logic is entirely absent. This matters operationally: if engineers disagree about whether a "like" is P2 or P3, or whether a follow is P1 or P2, the priority system provides no actual latency differentiation.

### 9. The SMS P0 Dedicated Worker Contradicts the Core Architectural Claim

The executive summary states that "dedicated priority pools create idle workers for rare high-priority events" is wrong and that "fungible workers with priority-ordered dequeue are simpler and correct." Section 2.5 then carves out a dedicated P0 SMS worker, acknowledging the general approach fails for latency-sensitive events. This is not just a narrow exception — it is an admission that the core architectural argument in the executive summary is incomplete. The proposal does not reconcile this.

### 10. The AOF Configuration Has an Unacknowledged Rewrite Risk

`no-appendfsync-on-rewrite no` means fsync continues during AOF rewrites. This is safer for durability but can cause latency spikes during rewrite — Redis can pause for tens to hundreds of milliseconds while the OS flushes. At 500 enqueue operations/second, a 200ms pause causes ~100 backed-up operations. The proposal mentions AOF rewrite configuration but does not address the latency impact on the ingestion path or whether the ingestion API has a timeout that would surface these pauses as errors.