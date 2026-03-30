## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.6 ends with "P3 has two delivery paths:" and nothing follows. The worker matrix references P2/P3 APNs workers for badge updates, but the delivery path for P3 is never completed. The executive summary claims the document covers everything, but it demonstrably doesn't.

### 2. Sections Referenced but Not Present

The executive summary and body reference multiple sections that don't exist in this document:
- Section 1.7 (P1-drains-P2/P3 mechanism, starvation prevention)
- Section 1.8 (Redis failover, P0 behavior during failover)
- Section 1.9 (OTP fallback sub-queue)
- Section 5 (WebSocket sequence numbers and reconnect catch-up logic)

The executive summary makes specific claims about all of these being "fully specified." They are not present.

### 3. The Executive Summary Is a Credibility Problem

The executive summary reads as a defense against a previous reviewer rather than a summary of a design. Phrases like "the previous claim was wrong," "the race condition is solved, not described," "named, not hidden," and "every tradeoff is named explicitly, including the uncomfortable ones" signal that this document is responding to criticism of an earlier draft. A reader encountering this fresh has no context for those claims, and the defensive framing undermines confidence rather than building it.

### 4. The APNs Failure Case Is Named but Not Actually Mitigated

The document acknowledges that at 100 req/sec/worker, 6 workers handle 600/sec against 547/sec peak — "barely adequate, with no headroom." The stated mitigations are (a) use 6 workers instead of 4, and (b) run a load test at month 2. Neither addresses the failure scenario described. If throttling occurs, the system has ~9% headroom at peak. Any spike, any worker restart, any connection renegotiation eliminates that margin. The mitigation is a monitoring plan, not a capacity solution.

### 5. The 50/50 FCM/APNs Split Is Asserted Without Basis

The document states "FCM and APNs each handle approximately 50% of push volume" with no justification. Platform mix (Android vs. iOS) varies enormously by geography, app category, and user demographics. For a social app with no stated market, this could easily be 70/30 or 80/20 in either direction. The sensitivity analysis applied to DAU/MAU and notifications-per-user is not applied here, despite this being an equally uncertain input that directly governs APNs worker sizing.

### 6. The Visibility Timeout Recovery Process Has a Race Condition

The recovery process scans for messages older than 60 seconds and moves them back to the source queue. If a worker is slow but not dead — processing a message that takes 65 seconds — the recovery process will return that message to the queue while the worker is still processing it. The result is duplicate delivery. The document claims deduplication uses atomic SET NX, but deduplication keys have a 5-minute TTL. A message requeued at 65 seconds and reprocessed at 70 seconds would have a dedup key still active, but the document does not demonstrate that dedup is applied at the point of external delivery rather than at dequeue. If dedup is checked at dequeue and the key is set at dequeue, the requeued message gets a new dedup check against the same key — but that only works if the original worker set the key before the recovery window. The interaction is not specified.

### 7. The LREM Operation Does Not Scale

The pruning process uses `LREM queue:<priority> 1 <id>` to remove expired messages from Redis Lists. `LREM` is O(N) where N is the list length. At the provider-outage worst case of 3.9M FCM messages in the queue, each LREM call on an expired message scans up to 3.9M entries. If many messages expire simultaneously — which is likely, since messages enqueued during a burst share similar TTLs — the pruning process issues thousands of O(N) operations against a multi-million-entry list. This is a latency spike that will block other Redis operations. The document does not acknowledge this.

### 8. The Preference Cache Memory Estimate Is Likely Wrong

The document estimates 500B × 3M active users = ~1.5GB for preference cache. 500 bytes per user for notification preferences is plausible for a minimal schema, but a social app with per-type, per-channel, per-time-window preferences (do-not-disturb schedules, per-friend mute settings, category toggles) commonly reaches 2–5KB per user. At 3M users and 2KB average, this is 6GB — nearly double the total normal-operation estimate and approaching the worst-case total. The estimate is presented with false precision.

### 9. The SMS "Capacity Ceiling" Is Not Defined

The document labels 0.9M/day SMS as a "capacity ceiling, not operating target" but never defines what the ceiling actually is or how it's enforced. Twilio pricing at SMS scale is a significant budget item. There is a reference to "SMS budget controls apply to all users" in the executive summary and a reference to an "OTP router" but no specification of what the ceiling is, who sets it, or what happens when it's reached — does the system drop messages, queue them, fall back to email, or alert?

### 10. The Worker Pool Total of 23 Is Not Reconciled with Infrastructure

The document specifies 23 workers across channels and priorities but never states what these workers run on, how they're deployed, or what their resource requirements are. For 4 engineers over 6 months, the operational complexity of 23 worker processes across 5 channels and 4 priority levels — each with its own queue, scaling behavior, and failure mode — is substantial. The staffing risk section is referenced but not present in this excerpt.

### 11. The "Month-2 APNs Milestone as a Non-Optional Gate" Creates an Unacknowledged Project Risk

If the month-2 APNs load test reveals throughput below 200 req/sec/worker, the document says this "is an architecture problem requiring escalation before month 3." In a 6-month project with 4 engineers, discovering a fundamental architecture problem at month 2 that requires escalation leaves 4 months to redesign, reimplement, and revalidate. The document names this as a risk but does not acknowledge that it potentially invalidates the entire delivery timeline.

### 12. The In-App Concurrent User Correction Is Applied Inconsistently

The document applies a 20% concurrent-user correction to in-app delivery (600K/3M) to get 63/sec peak. But in-app delivery for offline users is said to "queue for next login." The document does not address what happens to that queued volume when users log back in after peak — a login surge following peak hours would create a delivery spike for queued in-app notifications that is not captured in the 63/sec figure. The correction reduces the steady-state estimate but ignores the catch-up load pattern.