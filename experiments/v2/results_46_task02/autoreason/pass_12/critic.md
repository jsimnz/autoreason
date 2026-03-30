## Real Problems Found

### 1. The delivery floor is below the base stress case, and this is accepted without justification

The document explicitly states the delivery floor (~1,200/sec) is below the 2× stress case inbound (~2,200/sec), then calls the 2× case "the base stress case." This means the system is sized to fail under what the document itself defines as the base expected stress scenario. The response is to page on-call and evaluate scaling. That is not a design — it is a plan to react to a foreseeable failure. The document acknowledges this but treats the acknowledgment as resolution.

### 2. The 800 bytes per queued message figure is asserted, not derived

The per-message breakdown sums to ~555 bytes, then jumps to 800 bytes "with Redis overhead." Redis overhead per key is real, but the specific overhead depends on the data structure used (list vs. sorted set vs. stream), the Redis version, and whether jemalloc fragmentation is accounted for. None of these are specified. The 800-byte figure is doing significant work in the runway arithmetic — it determines the 15.6M message capacity ceiling — and it is not derived from the structure actually specified.

### 3. The idempotency key logic has a circular dependency that is not fully resolved

The document states the idempotency key is written when a notification is "first dispatched to a worker," and that delivery status is determined by checking the APNs receipt before writing the key as "delivered." But during the failover sequence, the receipt system is the thing that has failed — the connection dropped. The document says receipts that haven't arrived are requeued. This means the system must distinguish "receipt not yet arrived" from "receipt lost due to connection failure" in real time, during the failure event. The mechanism for making this distinction is not specified. The assertion that the idempotency layer prevents both duplicate delivery and missed delivery depends on this distinction being reliably made.

### 4. The 30-minute shedding decision window is not operationally grounded

The response table says P2 shedding begins at 30 minutes for the 3× case. At 3× inbound, the queue grows at 2,100/sec. In 30 minutes that is ~3.78M messages queued. The document says P2 shedding reduces inbound by ~20%, bringing growth to ~1,400/sec. No justification is given for why 30 minutes is the right trigger point rather than, say, 10 minutes. The document presents this as a designed threshold but it appears to be an arbitrary one. The consequence of the choice — how much queue depth has accumulated before shedding engages — is not analyzed.

### 5. The stress case multiplier math is not internally consistent

The document states that both inputs being wrong by ~70% simultaneously produces the 2× case. The arithmetic shown for the 2× case uses cohort = 225,000 (50% larger) and multiplier = 12× (50% higher). 50% is not 70%. The 70% figure appears later as a summary claim but does not match the numbers actually used. This is a factual error in the document's own derivation.

### 6. The FCM deduplication is referenced as resolved but not visible in this section

The executive summary states FCM deduplication is "specified in Kafka routing and worker fetch logic." This section does not contain that specification, and the document appears truncated. The claim of resolution cannot be evaluated from what is present.

### 7. The 4.3-hour runway for the 2× case assumes no memory fragmentation or growth in non-queue Redis usage

The runway calculation uses a static 1.2 GB figure for non-queue Redis usage. Under a viral event, idempotency key volume grows faster than steady state (because notification volume is spiking), user preference cache may be warming for new users, and Redis memory fragmentation increases under write pressure. None of these dynamic effects are modeled. The 4.3-hour figure is a best-case calculation presented without that qualification.

### 8. The failover consequence claim of "<5 seconds latency spike" is not derived

The document states that notifications in-flight on APNs-1 at the moment of failure experience "at most one additional delivery attempt latency (the requeue-and-refetch cycle, typically <5 seconds)." The requeue-and-refetch cycle involves: detecting the failure (up to 10 seconds by the document's own trigger definition — "3 errors in 10 seconds"), stopping workers, requeuing in-flight messages, and Workers 2A/2B fetching and dispatching. The detection window alone is up to 10 seconds, which contradicts the "<5 seconds" claim. The document's own failure detection threshold is longer than the latency it claims.

### 9. The viral cohort baseline of 34/day is derived from the average, which the cohort definition excludes

The document defines the viral cohort as "top 5% of DAU" and assigns them a baseline of 34/day described as "2× average." The average of 17/day includes the bottom 95% of users. If the top 5% are already the heaviest users, their baseline is almost certainly more than 2× the all-user average — the all-user average is pulled down by low-engagement users. Using 2× the all-user average as the heavy-user baseline likely underestimates the cohort's actual baseline, which means the viral inbound ceiling is also underestimated. The document acknowledges input uncertainty but does not identify this specific structural issue with the estimate.

### 10. The document is truncated

The APNs validation section ends mid-sentence: "The prior draft deferred validation to month." The document cannot be evaluated as complete. Problems in sections that do not exist — including the FCM deduplication specification, Section 1.4, the tertiary alerting path, and the SMS spend cap design — are all claimed as resolved but partially or entirely absent from what is presented.