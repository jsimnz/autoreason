## Real Problems with This Proposal

### 1. The Team Size Is Never Actually Reckoned With

The document opens by naming "4 Engineers, 6 Months" and then never returns to it. The design specifies: four isolated priority queues, per-channel per-priority worker pools, a two-list visibility timeout implementation, a companion sorted set expiry system, an independent recovery process, a heartbeat coroutine system with alerting, a deduplication layer, an OTP Redis cache, a pruning process, and a PostgreSQL hot path — all requiring coordination, testing, monitoring, and operational runbooks. There is no staffing breakdown, no acknowledgment that this is a large surface area for four engineers, and no prioritization of which components are load-bearing versus nice-to-have. The executive summary claims completeness as a virtue without asking whether completeness is achievable.

### 2. The APNs Throughput Section Is Cut Off Mid-Sentence

The document ends abruptly: "New bundle IDs with no established Apple relationship have been observed to be throttled to 50–150" — and stops. This is the exact failure case the document promises to name honestly. The section heading claims "the failure case that must be named" and then does not name it. Whatever mitigation or analysis was supposed to follow is absent. For a document that explicitly positions itself against vague SLA citations, leaving the most operationally dangerous external dependency unresolved is a direct contradiction of its stated standard.

### 3. The Viral Spike Math Is Circular

The document argues the system handles 20× spikes because worker capacity (~26,000/sec) exceeds the spike demand (~10,500/sec). But the worker capacity figure is derived from the planning-volume worker pool, which was sized for 1,575/sec peak. The document does not establish that the planned worker count is actually provisioned at that capacity or that it can be reached quickly enough during an unpredictable viral event. The argument assumes the conclusion: the workers can handle the spike because there are enough workers, and there are enough workers because the plan says so.

### 4. The Deduplication Key Design Has an Unacknowledged Semantic Problem

The chosen key structure — `user_id + notification_type + content_hash` — is presented as solving the "new message from A vs. new message from B" problem. But for many social notification types, the content hash will be identical across distinct events. "X liked your post" for two different likes on the same post by two different users may produce the same content hash if the notification text is templated identically. The document does not address how content_hash is computed or what fields it covers, which means the key design's correctness is unverifiable as written.

### 5. The 99.99% PostgreSQL Availability Figure Is Used as a Planning Input Without Justification

The document treats 99.99% as given for the managed PostgreSQL instance and builds failure analysis on it. But 99.99% is a contractual SLA, not an empirical availability figure, and SLAs typically exclude scheduled maintenance, customer-caused outages, and events outside the provider's defined scope. The actual experienced availability of RDS Multi-AZ in production is not cited. More importantly, the hot-path dependency means PostgreSQL availability directly gates notification delivery — a dependency this tight warrants more than a vendor SLA as its reliability foundation.

### 6. The Recovery Process Has an Unaddressed Concurrency Problem

The recovery process runs every 30 seconds and reclaims stale entries by doing a multi-step sequence: ZRANGEBYSCORE, then LREM, then RPUSH, then ZREM. This is not atomic. If two recovery process instances run concurrently — possible during a deployment, a crash-restart loop, or if the recovery process is run on multiple nodes — the same message can be reclaimed twice, resulting in double-enqueue without a corresponding dedup key (since the dedup key is set at original enqueue, not re-enqueue). The document acknowledges the slow-worker race but does not acknowledge the recovery-process concurrency race.

### 7. The Priority Starvation Prevention Mechanism Is Promised but Not Shown

The executive summary states the "P1-drains-P2/P3 mechanism is fully specified with starvation prevention." The document as presented does not include this specification. There is no description of how starvation prevention works, what the promotion logic is, or how aging is tracked. Claiming full specification for something not present in the document is a credibility problem, not just an omission.

### 8. The In-App Worker Overcapacity Justification Is Weak

The document acknowledges 79× overcapacity for in-app workers and offers three justifications: ancillary workload, concurrency uncertainty, and low cost. None are quantified. "Ancillary workload" — read-state updates and delivery confirmations — is not estimated. If those workloads are significant enough to justify the worker count, they should appear in the sizing model. If they are not significant, the justification is post-hoc. The document's own standard is to state tradeoffs honestly, and "it's cheap" is not a capacity argument.

### 9. The OTP Mitigation Redefines the Problem Rather Than Solving It

The document acknowledges that a 60–120 second PostgreSQL failover delay is "not acceptable for OTPs with users waiting at a login screen," then offers as mitigation that the OTP remains valid because it's stored in Redis. This addresses OTP expiry but not the user experience problem the document itself identified. A user waiting 60–120 seconds for a login code is a product failure regardless of whether the code is still technically valid when it arrives. The mitigation is presented as resolving the concern when it only resolves one dimension of it.

### 10. The Month-1 Validation Plan Has No Defined Response Path

The document states that if measured traffic diverges from the 15M–100M/day range by more than 2×, the team should "re-plan before month 3." This means the system could be running at 10× or 0.1× expected load for up to two months before action is required. There is no description of what re-planning involves, who decides, what the trigger for emergency intervention (versus scheduled re-planning) is, or what partial mitigations are available in the interim. "Re-plan" is not an operational response.