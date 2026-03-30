## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.6 ends with "P3 has two delivery paths:" and nothing follows. The worker matrix references P3 having email and in-app workers, but the justification for those choices is never completed. The document is unfinished.

### 2. The Executive Summary Overclaims Completeness

The summary says "every tradeoff is named explicitly, including the uncomfortable ones," but Section 5 (WebSocket sequence numbers and reconnect catch-up logic) is referenced but never shown in the document. The reader cannot verify whether it exists or what it specifies.

### 3. The Deduplication Analysis Is Superficial

The document claims "the race condition is solved, not described" using atomic SET NX, but never actually shows the key structure, the TTL selection rationale, or what happens when two identical notifications arrive 6 minutes apart (just outside the 5-minute window). It also doesn't address whether deduplication is per-user-per-notification-type or per-exact-payload, which determines the false-positive and false-negative rates entirely.

### 4. The APNs Failure Case Is Named But Not Actually Mitigated

The document acknowledges 100 req/sec/worker gives "barely adequate" capacity with "no headroom," then lists the mitigation as "6 workers instead of 4" and "a load test at month 2." But 6 workers × 100 req/sec = 600/sec against a 547/sec peak with zero headroom for any spike, worker restart, or network jitter. The mitigation doesn't solve the problem it identifies. Naming a failure case without a real mitigation is not the same as addressing it.

### 5. The Visibility Timeout Recovery Process Has an Unacknowledged Race Condition

The recovery process "runs every 30 seconds" and scans for messages older than 60 seconds. A worker that is slow (not crashed) but still processing can have its message reclaimed by the recovery process and re-enqueued while the original worker is still working on it. The heartbeat interval (10 seconds) versus recovery threshold (60 seconds) provides a 50-second buffer, but this assumes the heartbeat is perfectly reliable. The document doesn't address what happens if the heartbeat process itself is delayed or if the worker is blocked on a slow database call during heartbeat time.

### 6. The 99.99% PostgreSQL Availability Claim Does the Work of an Argument It Doesn't Make

The document uses "managed PostgreSQL with 99.99% availability" to justify the ID-based hot-path database dependency. 99.99% is ~52 minutes of downtime per year. The document never specifies what happens during those 52 minutes — do notifications queue indefinitely, get dropped, or fall back to some other path? The SLA figure is cited as a justification but doesn't actually answer the behavior question.

### 7. The Redis Failover Window for P0 Is Referenced but Never Quantified

Section 1.8 is referenced for failover implications but is not present in the document. The executive summary says "P0 behavior during failover is specified," but no specification is visible. This is the most operationally critical gap — P0 covers security alerts and OTPs, and the behavior during the primary/replica failover window is exactly what an on-call engineer needs to know.

### 8. The Staffing Math Is Not Shown

The document mentions "4 engineers, 6 months" and says staffing risk is "addressed directly," but no staffing analysis appears in the visible document. 23 worker pool types, a custom Redis visibility timeout implementation, a multi-channel routing system, WebSocket reconnect logic, and APNs HTTP/2 multiplexing are non-trivial to build and operate. The claim that staffing risk is addressed is asserted, not demonstrated.

### 9. The P1-Drains-P2/P3 Starvation Prevention Mechanism Is Referenced but Not Specified

The executive summary says the "P1-drains-P2/P3 mechanism is fully specified, including starvation prevention." The visible document does not contain this specification. Section 1.7 is referenced in the worker matrix table but doesn't appear in the document.

### 10. The SMS Budget Controls Are Mentioned Without Any Detail

The executive summary claims "SMS budget controls apply to all users, including those without verified email" and "the OTP router handles the no-email case explicitly." None of this appears in the visible document. What the budget is, how it's enforced, what the no-email OTP path actually does — all absent.

### 11. The Peak Calculation Assumes a Clean 2-Hour Window That May Not Reflect Reality

The 3× peak multiplier applied over a 2-hour window is used throughout, but social apps often have sharper spikes — a viral post, a breaking news event, or a celebrity action can generate notification bursts that are 10–20× baseline over 5–10 minutes, not 3× over 2 hours. The sensitivity table tests volume uncertainty but not temporal concentration uncertainty.

### 12. The In-App Active-User Correction Is Applied Inconsistently

The document correctly applies the 20% concurrent-user correction to in-app delivery demand (reducing it to ~63/sec). But the in-app worker count (5 workers at ~1,000 rows/sec/worker = 5,000/sec capacity) is sized against the uncorrected 9M/day figure implicitly, providing ~79× overcapacity. This isn't necessarily wrong, but the document never acknowledges the inconsistency or explains why the workers weren't sized down accordingly.