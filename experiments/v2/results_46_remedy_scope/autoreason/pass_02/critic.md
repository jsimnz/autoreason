## Real Problems

### 1. P3 Is Silently Aliased to P2

```python
PRIORITY_QUEUES = {
    "P2": "queue:p2",
    "P3": "queue:p2",  # P3 shares queue with P2
}
```

But `QUEUE_TTLS` has separate entries for P2 (24h) and P3 (48h), and the worker table lists "P2/P3 Workers (8 total)" as a combined pool. The TTL logic will apply P2's 24-hour TTL to P3 notifications because the queue name resolves identically and there's no per-notification TTL differentiation after enqueue. Digests and re-engagement messages will expire on P2's schedule, not P3's. This is a silent data loss bug, not a documented tradeoff.

### 2. The Dequeue Script Is Not Actually Atomic in the Way That Matters

The Lua script batches RPOPs atomically, but the payload fetch immediately after is a separate non-atomic pipeline. Between the RPOP and the `pipe.get(f"ntf:{id}")`, a notification ID is held by no one — it has been removed from the queue but not yet retrieved. If the worker crashes at this exact point, the notification is permanently lost with no DLQ entry, no retry, and no visibility. The design claims RPOP gives atomicity guarantees but the actual at-least-once delivery guarantee is broken by the two-phase fetch pattern.

### 3. In-App Worker Headroom Is Dangerously Thin

The table shows in-app at 1,040/sec peak demand against 2,000/sec capacity — 1.9× headroom. Every other channel has 6× minimum. The document states "All capacity planning is sized against the 1,750/sec peak figure" and uses a 3× peak multiplier, but in-app headroom was apparently calculated differently. A moderate traffic event beyond the modeled peak saturates in-app workers while push workers sit largely idle. There's no acknowledgment of this asymmetry or explanation for why in-app was treated differently.

### 4. The Queue Drain Analysis Contains a Math Error

"A 2-hour sustained peak at 3× normal produces ~12.6M notifications above baseline." At 50M/day baseline, normal rate is ~578/sec. The excess above baseline at 3× peak is ~1,156/sec for 7,200 seconds = ~8.3M notifications, not 12.6M. The 12.6M figure appears to be the total volume during peak, not the excess above baseline. The drain time calculation then uses the wrong numerator, making the "clears within 33 minutes" claim unreliable.

### 5. APNs Throughput Claim Is Nonsensical

The worker table claims APNs throughput of "~50,000 tokens/sec across pool" with ">10× headroom" against 350/sec demand. APNs has no batch API — the design itself states "Individual requests per device." 20 connections at even optimistic HTTP/2 performance cannot approach 50,000 individual requests per second. This number appears to have been fabricated or copied from a batching context that doesn't apply. The headroom claim is therefore meaningless.

### 6. No Acknowledgment of Redis as a Single Point of Failure for All Priority Isolation

The entire priority isolation argument rests on three Redis Lists. ElastiCache is mentioned as managed infrastructure, but Redis failover (even with Multi-AZ) involves a promotion period of 20–60 seconds during which writes fail or block. The design's strongest architectural claim — "P0 isolation must hold under backpressure, exactly when it matters most" — is undermined by having all three queues in the same Redis instance/cluster. A Redis failover during a traffic spike is precisely the scenario where P0 isolation is most needed and least guaranteed.

### 7. Preference Cache TTL Creates a User-Visible Correctness Problem

60-second TTL on preference cache means a user who disables a notification type (e.g., turns off SMS after receiving unwanted messages) continues receiving that notification type for up to 60 seconds. For security alerts and OTPs this is fine, but the suppression check also runs against the same cached preferences. A user who adds themselves to a suppression list won't be suppressed for up to 60 seconds. The document names tradeoffs explicitly as a stated value but doesn't name this one.

### 8. The APNs Token Manager Code Is Cut Off

The document ends mid-class definition with `_lock = threading.Lock()` and no closing. The rotation logic — which the document specifically calls out as "corrected" and contrasts with a prior wrong version — is never shown. A reader cannot evaluate whether the correction is actually correct.

### 9. Worker Count Inconsistency

The capacity table shows "4 FCM workers, 3 APNs workers, 2 email, 1 SMS, 2 in-app = 12 workers" then "24 total with 2× headroom." But the queue architecture diagram shows "P0 Workers (4 total), P1 Workers (12 total), P2/P3 Workers (8 total) = 24 workers." These are two different decompositions of the same 24 workers with no reconciliation. The per-channel sizing and the per-priority sizing are never shown to be the same workers, creating ambiguity about whether the capacity math applies to the actual deployment topology.