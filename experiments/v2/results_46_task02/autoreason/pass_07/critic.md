Here are the real problems with this proposal.

---

**1. The preference cache invalidation problem is unresolved and consequential.**

The design stores preferences in Redis with a ~2GB cache. There is no specification of TTL, invalidation strategy, or what happens when a user changes their preferences mid-queue. A user who opts out of push notifications could have thousands of already-queued P1 items that will be delivered anyway. The proposal mentions "preference check" at ingestion but is silent on whether workers re-check preferences at delivery time. For a notification system, this is a compliance and user trust issue, not just a latency issue.

---

**2. The P0 queue throughput analysis is referenced but never shown.**

The executive summary says "P0 throughput ceiling calculated; Sentinel retained with specified limits and overflow behavior." The document then specifies that P0 uses `appendfsync always` and has a dedicated Sentinel instance, but the actual throughput ceiling number, the method used to derive it, and the overflow behavior are absent from the visible text. The document claims to have resolved this problem while the resolution is missing.

---

**3. The in-app fan-out after P0 commit creates an unacknowledged consistency hole for security alerts.**

The design states that in-app writes happen via "async fan-out after P0 commit, not in same transaction." For security alerts, this means a user could receive a push notification about a suspicious login but see nothing in the in-app notification center if the fan-out fails. The proposal frames this as a deliberate tradeoff but never specifies what happens on fan-out failure: is it retried, is it logged, does the user ever see the in-app record? This is not a tradeoff that is stated — it is a gap that is named and then dropped.

---

**4. The worker fetch pattern under deep queues creates a PostgreSQL read load spike that is called "acceptable" without justification.**

The proposal explicitly states that during viral events with 3.6M queued items, workers fetch payloads from PostgreSQL read replicas, and that this increased load is "acceptable because PostgreSQL read replicas handle worker fetches." This is circular. At 20 P1 workers and 10 P2 workers each fetching 500-row batches, the read replica is handling a continuous high-rate query load precisely when the system is already under stress. No read replica sizing, replication lag threshold, or degradation behavior is specified.

---

**5. The DLQ drain ownership "rotation" is specified in the executive summary but the actual rotation schedule and escalation path are not present in the visible document.**

The executive summary lists "Ownership rotation and escalation path defined" as a resolved problem. The document as shown does not contain this definition. This is the same pattern as problem 2: a problem is declared resolved in the summary table without the resolution appearing in the body.

---

**6. The 2-hour P1 expiry threshold is justified only by assertion.**

The document states "A social notification about a trending post that arrives 8 minutes late is acceptable. An OTP that arrives 8 minutes late is not." This correctly distinguishes P0 from P1. But the 2-hour threshold for P1 expiry is never connected to any user research, product requirement, or business logic. A like notification that arrives 1 hour and 59 minutes late is kept; one that arrives 2 hours and 1 minute late is logged as `expired_undelivered`. The threshold is presented as a product decision requiring sign-off, but no basis for why 2 hours rather than 30 minutes or 6 hours is offered to the product owner who must sign off on it.

---

**7. The heartbeat SMS fallback for alerting uses the same Twilio account as the main system.**

The proposal describes a "dumb" cron-based heartbeat that sends SMS via "a Twilio number outside the main system." It is described as intentionally independent, but Twilio is the main SMS provider. If the Twilio account is suspended, rate-limited, or experiencing an outage, both the primary alerting path and the backup heartbeat path fail simultaneously. The independence is nominal, not structural.

---

**8. The token/device registry cache has no specified invalidation or consistency model.**

500MB is allocated for a token/device registry cache with no description of how it stays consistent with the authoritative store, what happens on cache miss, or how APNs/FCM token invalidation feeds back into the cache. The feedback processor section is described as "fully specified" in the executive summary, but the cache consistency behavior for invalidated tokens is not addressed in the visible text.

---

**9. The viral event queue growth model assumes a fixed 1,750/second delivery rate that is not validated against worker pool sizing.**

The proposal states sustained delivery throughput is approximately 1,750/second, then uses this to calculate queue growth. But 30 workers (20 P1 + 10 P2) fetching in batches, making network calls to APNs/FCM/SendGrid, and writing delivery receipts cannot be assumed to sustain 1,750 notifications/second. APNs and FCM have their own rate limits and connection pool constraints. The 1,750/second figure appears to be derived from the inbound rate divided by a peak factor, not from the actual delivery pipeline capacity.

---

**10. The month-2.5 launch includes SMS architecture deployed but disabled, with no specification of what "deployed but disabled" means operationally.**

A deployed-but-disabled system still has credentials, IAM roles, Twilio account configuration, and outbound network paths in place. There is no mention of how this is disabled — a feature flag, a worker that is not running, a queue that is not polled — or what the risk surface of a partially deployed SMS system is before Finance has approved the spend cap.

---

**11. The `FOR UPDATE SKIP LOCKED` polling pattern with 4 instances and 500-row batches creates a batch-size-dependent head-of-line problem.**

If one of the 4 poller instances acquires a batch of 500 rows and then stalls — due to a slow PostgreSQL write, a Redis timeout, or a GC pause — those 500 rows are locked and invisible to other pollers until the lock is released or the transaction times out. The proposal does not specify a transaction timeout for the outbox poller, meaning a stalled instance can hold 500 rows indefinitely. The idempotency guarantee on ZADD does not help here because the rows never reach Redis.

---

**12. The escalation chain for OTP failure terminates at VP Product, who has no technical authority over the failure.**

The escalation path for OTP relay exhaustion is "E4 → Engineering Manager → VP Product." VP Product cannot restore a failed outbox relay. The escalation chain correctly identifies who needs to be informed of a business impact, but it does not identify who has authority to make the technical decision about what to do — for example, whether to manually drain the outbox, whether to page an on-call DBA, or whether to switch to a fallback OTP delivery path. Informing VP Product is a communications step, not a resolution step.