## Real Problems with This Proposal

### 1. The Document Doesn't Actually Exist as Described

The executive summary repeatedly references sections that aren't present in the submitted text. Section 3 (worker pool structure), Section 2.2 (token bucket Lua script), and Section 1.4's sensitivity table are either absent or the document is cut off mid-sentence. The executive summary makes guarantees ("the worker pool structure that makes the guarantee real is specified in Section 3") that cannot be evaluated because those sections aren't here. This is a proposal that describes itself rather than delivers itself.

### 2. The "Named Decision-Maker" Pattern Is Hollow

The document repeatedly escalates risk acceptance to "[Product Lead name] and [Engineering Lead name]" — placeholder text. This appears in at least two critical places: the 20–40 minute DM delay acceptance and the FCM rate limit confirmation. If these decisions genuinely require named humans before production, leaving them as template variables means the document cannot actually gate production. It performs rigor without delivering it.

### 3. The Corrected Arithmetic Is Still Wrong

The document claims to correct a prior "16-minute" figure to "20–40 minutes" and attributes the original error to being "off by 10× on queue accumulation." But the corrected calculation has its own problem: it uses 9,500 messages/sec net accumulation for both the accumulation phase and the drain rate, which means drain time equals coincident failure duration exactly. That's only true if the spike ends precisely when the slow-query event ends. If the spike ends first, drain is faster; if it ends after, drain is slower. The stated range of 20–40 minutes doesn't follow from the arithmetic presented — it's asserted, not derived, which is the same problem the document claims to have fixed.

### 4. The FCM Rate Limit Is Treated as Knowable When It Isn't

The document says to "confirm the actual FCM rate limit by contacting FCM support or load testing." FCM does not publish per-project rate limits and support cannot contractually guarantee them. Load testing a staging project doesn't produce a guarantee for a production project under viral conditions. The sensitivity table implies that knowing this number resolves the spike analysis, but the number cannot be reliably known in advance. The document's "required pre-production action" is not completable in the way it's framed.

### 5. At-Least-Once Delivery Is Declared but Deduplication Is Underspecified

The document states the dispatch layer "must be idempotent" and mentions "a delivered-ID bloom filter" as the deduplication mechanism. Bloom filters have false positive rates — they will occasionally suppress legitimate redeliveries of messages that were never actually delivered. For a DM notification, a false positive means a message the user never received is silently dropped. The document doesn't acknowledge this failure mode, doesn't specify the false positive rate, and doesn't specify bloom filter sizing or rotation policy. "Must be idempotent" is a requirement, not an implementation.

### 6. The Traffic Response Matrix Has an Unresolvable Ambiguity

The matrix instructs engineers to check per-channel queue depth to determine which worker type to provision. But the document also states that push and in-app writes are additive from the same upstream event. A viral spike will likely saturate push workers while in-app queue depth also rises, because they're driven by the same event volume. The matrix's branching logic ("if queue depth alert is push-specific, provision push workers only; if cross-channel, provision push + email workers") doesn't cover the push + in-app saturation case, which is the most probable correlated failure mode given the volume model.

### 7. The 8-Minute Manual Response Time Assumes Things That May Not Hold

The manual response timeline treats "reads per-channel queue depth dashboard" as a 1-minute step. This assumes the dashboard is loading correctly during the incident — which is precisely when dashboards are most likely to be slow, stale, or showing misleading data due to the same Redis or infrastructure pressure causing the alert. The timing estimate is constructed under normal conditions and applied to a degraded-state scenario.

### 8. The Starvation Prevention Claim Cannot Be Evaluated

The executive summary states that starvation prevention uses "an atomic token bucket implemented as a Lua script (Section 2.2)" and that it is "only meaningful if workers are split by priority tier." Section 2.2 is not present. There is no way to evaluate whether the token bucket actually prevents starvation, what its parameters are, or whether the worker split structure is correctly specified. This is the document's central architectural claim for P0/P1 protection, and it's entirely absent.

### 9. The Month-1 Validation Dependency Is Load-Bearing but Unprotected

Multiple planning decisions are explicitly deferred to "validate with real traffic data at month 1." The FCM limit confirmation, the DAU/MAU ratio validation, the traffic response matrix decision ownership — these are all month-1 deliverables. But there's no mechanism specified to prevent the system from going further into production if month-1 validation doesn't happen or produces ambiguous results. The document treats month-1 review as a checkpoint but doesn't specify what happens if the checkpoint is missed.

### 10. Worker Specialization Creates a Credentials Management Problem That's Dismissed

The document acknowledges that specialized binaries require channel-specific credentials in each worker type's environment and calls this a benefit ("credentials are isolated"). But credential rotation now requires coordinated redeployment of specific worker binaries. During a rotation event, if push worker credentials are rotated while a push worker instance is mid-dispatch, in-flight messages fail. The document treats credential isolation as unambiguously positive without addressing the operational complexity of rotation across a multi-binary deployment.