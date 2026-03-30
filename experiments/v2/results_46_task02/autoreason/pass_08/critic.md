## Real Problems with This Proposal

### 1. The Core Throughput Derivation Is Internally Contradictory

The document claims steady-state throughput of 1,400/sec, derived from worker pool and channel constraints. But the per-worker calculation shows one P1 push worker sustains 15,600/sec in isolation, and the aggregate channel ceiling is ~13,700/sec. The document never actually derives 1,400/sec from these numbers—it asserts it as a "realistic" figure accounting for "connection overhead, retry cycles, preference re-checks." No math is shown for how those factors reduce 13,700/sec to 1,400/sec (a 90% reduction). The document claims to replace an "assumed" number with a "derived" number, but the final figure is still asserted.

### 2. The Viral Inbound Model Is Fabricated

"600K users can spike 8–10× their personal baseline" is presented as a derivation, but no basis is given for why the top 20% of DAU are the relevant cohort, why 8–10× is the spike multiplier, or why the spike is sustained long enough to matter. The 14,000/sec ceiling is arithmetic applied to an assumed spike factor, not a derivation. This is exactly the problem the document claims to avoid.

### 3. APNs Rate Limit Claims Are Undocumented and Possibly Wrong

The document cites "2,000–3,000/sec per connection before throttling" for APNs and labels the source as "Apple production experience; undocumented but consistent." APNs HTTP/2 connections support up to 1,500 concurrent streams, but the actual throughput ceiling depends on payload size, connection handling, and server-side behavior that Apple does not publish and that varies. Basing the binding delivery constraint on an undocumented, unverifiable claim is a serious reliability risk. If the real limit is lower, the throughput model is wrong; if higher, workers are under-provisioned.

### 4. Receipt Deduplication Logic Is Broken at the Crash Window

The document acknowledges a crash window where a notification is delivered to APNs/FCM but the receipt is not yet written. It claims APNs and FCM "handle duplicate delivery gracefully (notification ID deduplication on the device)." APNs does not deduplicate by notification ID on the device in the general case—it deduplicates by `apns-collapse-id` only if that header is explicitly set, and only for collapse-eligible notifications. FCM has a similar `collapse_key` mechanism that is opt-in. Without explicit use of these mechanisms, duplicate push delivery to users is not "occasional"—it is guaranteed for any notification in the crash window.

### 5. The Preference Cache Miss Behavior Creates a Correctness Problem

The document states that on a preference cache miss, notifications go to "queue-pending state, not suppress; re-check at delivery time." But the Redis memory budget allocates ~2GB for a preference cache covering all 10M users. Cache misses at scale are not a rare edge case—cold start, rolling deploys, and Redis failover all produce mass cache misses simultaneously. "Slight over-delivery risk" understates this: during a Redis failover or restart, the entire preference cache is cold, and the system delivers notifications to users who have opted out until the cache warms. For a notification system serving security alerts, this is a compliance and user trust problem, not a slight risk.

### 6. The P0 Separation Does Not Actually Isolate P0 from Viral Events

The document claims P0 is protected because "OTPs and security alerts do not scale with social engagement volume." This is true for the happy path. It is not true for the failure path. During a viral event, the application servers generating notifications are under elevated load. If auth OTP generation is triggered by a login surge (which correlates with viral events—users logging in to see trending content), P0 volume increases precisely when the system is under maximum stress. The document does not model this correlation.

### 7. The Kafka Receipt Writer Is a Single Point of Failure with No Recovery Model

The receipt writer is described as "a single process." If it fails, receipts stop being written. The document says "receipts are delayed but delivery is not" and mentions a 60-second lag alert. But it does not specify: what happens if the receipt writer is down for 10 minutes? For 1 hour? The Kafka topic presumably retains messages, but the document does not state retention policy, consumer group configuration, or what happens to the outbox state for notifications whose receipts are never written. The outbox-to-Redis idempotency model depends on receipts eventually being written to close the delivery loop—a prolonged receipt writer outage means the outbox never clears, workers re-attempt delivered notifications indefinitely, and users receive duplicates at scale.

### 8. The SMS Budget Model Has a Unit Error Risk

The document states daily domestic volume of "60,000–120,000 messages" for "60% of DAU." 60% of 3M DAU is 1.8M users. The SMS channel is scoped to "auth OTPs + security alerts only"—not all DAU generate auth OTPs daily. The volume figure of 60,000–120,000/day implies 3–7% of the eligible user base triggers an SMS event per day. This is not derived anywhere. If actual auth OTP trigger rates are higher—for example, if the app forces re-authentication frequently—the budget model is wrong by a factor that could be significant, and the spend cap of $35,000/month may be breached on day one.

### 9. The 2-Hour P1 Expiry Threshold Applies Twitter Research to a Different Product

The justification cites "Twitter content engagement studies." Twitter is a public broadcast medium with a fundamentally different engagement pattern than a social app with a private social graph. Engagement decay on a direct message notification, a friend activity notification, or a group mention does not follow Twitter content decay curves. The document acknowledges "if Product has data indicating a longer engagement window"—but the default is set to a number from an inapplicable source, and the implicit sign-off mechanism ("Product accepts it implicitly" if no response by end of month 1) means a potentially wrong default becomes permanent through inaction.

### 10. Worker Pool Allocation Does Not Add Up Correctly

The document lists: 20 P1 workers, 10 P2 workers, 10 P0 workers, 5 in-app writers, 3 email workers, 2 SMS workers = 50 workers total. The throughput table then shows "14 P1 push workers" and "6 P2 push workers." The earlier specification of 20 P1 workers and 10 P2 workers is inconsistent with the throughput table's 14 and 6. The document never explains this discrepancy or how workers are allocated across channels within each priority tier.

### 11. The Dead Man's Snitch Backup Depends on a "Separate VM" That Is Undefined

The tertiary alerting path requires "a cron job on a separate VM — not on the application fleet, with no dependency on the application database, Redis, or Twilio." This VM is never provisioned, owned, or monitored in the schedule. With 4 engineers and a 6-month timeline, an undocumented VM running a critical heartbeat job is an operational liability. If it silently fails—its own disk fills, its cron daemon crashes, its network route breaks—the backup alerting path is gone and no one knows.

### 12. The Document Is Incomplete

The document ends mid-sentence: "A Twilio account suspension or regional outage takes both the primary SMS delivery system and any Tw—". This is not a minor formatting issue—it means the rationale for a stated architectural decision (why Twilio was excluded from the backup path) is missing from the final document. Any review or approval based on this document is based on an incomplete specification.