## Real Problems with This Proposal

### 1. The 30-Day Validation Window Is Too Late for Its Own Purpose

The document provisions infrastructure at 2× projected peak to cover DAU/MAU uncertainty, then waits 30 days to validate. But the escalation trigger for manual scaling ceiling increases is also tied to the 30-day review or specific threshold breaches. If actual DAU/MAU is 45% but sustained peak throughput never exceeds 200/second (perhaps because notification volume per user is lower than estimated), the review trigger never fires early, and the team learns nothing actionable until day 30. The document treats these as independent safety nets but doesn't address the case where neither trigger activates despite the core assumption being substantially wrong.

### 2. The Decision Rules Contain an Internal Contradiction

The downward deviation rule says: reduce baseline to handle 1.5× measured peak. The upward deviation rule at 50–100% above estimate says: increase baseline by the ratio of actual to estimated peak. That ratio could produce a new baseline with less than 1.5× headroom over measured peak if the "ratio" scaling is applied mechanically. The document never reconciles these two rules into a consistent headroom standard.

### 3. APNs "Per-Device" Rate Limit Is Mischaracterized

The document states APNs limits are "3 notifications per second per app per device" and calls this the binding constraint for users who receive many notifications quickly. Apple's actual documentation describes this limit as applying to the *provider server* sending to a device, with consequences being queued or dropped notifications — not a hard 429 response with Retry-After. The document's described error-handling behavior (honoring Retry-After, exponential backoff) is the correct FCM pattern, not the APNs pattern. APNs uses HTTP/2 and handles backpressure differently. Building worker retry logic on an incorrect model of how APNs signals rate limiting will produce a broken implementation.

### 4. The SMS Cost Model Double-Counts Without Justification

The "session overlap" adjustment adds 30 SMS/day for users who receive both a 2FA SMS and a suspicious login alert in the same session. But the base 2FA estimate (375/day) already includes all users with SMS-2FA enabled who initiate logins requiring 2FA — which includes the suspicious login sessions. The 250 suspicious login events/day are a subset of all login events. The document hasn't established that the 375 2FA events and 250 suspicious login events are drawn from independent populations. If suspicious logins are already captured in the 375, the overlap adjustment may be adding events that are already counted, not correcting for double-counting.

### 5. The Legal Review Dependency Is Structurally Misplaced

Legal review is scheduled for "no later than month 3 of 6." The retention policy, deletion API design, and cold storage architecture are all specified in this document as if the policy is settled. If legal review in month 3 requires changes — a different retention period, a different deletion workflow, additional data categories to suppress — the cold storage schema, the deletion API contract, and potentially the in-app store schema all need rework. Month 3 of 6 leaves one sprint of buffer at best before the legal finding becomes a launch blocker. The document acknowledges this risk in one sentence but the schedule doesn't reflect it.

### 6. The "Load Older Notifications" UX Contradicts the Stated Rationale

The document justifies cold storage by saying users reading notifications older than 30 days is a low-frequency use case. It then builds a dedicated UI control, a rate-limiting system, a circuit breaker, and a user-facing error message for that low-frequency use case. The engineering investment described is inconsistent with the stated frequency. If the use case is genuinely rare, the infrastructure protecting against it is overbuilt. If it's common enough to warrant that infrastructure, the frequency assumption underlying the cold storage tradeoff is wrong.

### 7. Ownership Transfer Language Creates a Gap

The document says if team composition changes after kickoff, load validation ownership "transfers explicitly in writing to a named individual — it does not transfer by default." It provides no mechanism for ensuring this transfer happens. There is no defined trigger, no fallback owner if the transfer doesn't occur, and no process for detecting that the transfer was missed. "Explicit in writing" with no enforcement means the gap it's designed to prevent can still occur — it just also produces a documentation failure.

### 8. The Peak Throughput Derivation Compounds Unsupported Assumptions

The 63/second peak figure is derived by multiplying three figures in sequence: the DAU/MAU ratio (assumed), the notification rate per DAU (assumed per event type), and the 3× evening peak multiplier (explicitly flagged as unsupported). The document correctly flags the 3× multiplier but treats the upstream assumptions as if they've already been validated. Compounding three independent assumptions produces a figure whose actual confidence interval is never stated. The 2× provisioning headroom is applied to the output of compounded assumptions, not to the uncertainty in the assumptions themselves. The headroom may be insufficient if multiple assumptions are simultaneously wrong in the same direction.

### 9. The In-App Fallback Guarantee Is Unenforceable as Stated

The document states "every Tier 2 notification is written to the in-app store regardless of push status." This is a behavioral guarantee that requires either synchronous dual-write (introducing latency and coupling) or a reconciliation process. Neither is specified. The document describes push delivery and in-app storage as if they're handled by the same worker, but the architecture section (if it exists beyond what's shown) would need to specify how a push failure triggers or confirms the in-app write. Without that, this guarantee is a statement of intent with no implementation backing.

### 10. The Document Cuts Off Mid-Sentence

The SMS cost section ends mid-sentence: "If the user base is skewed toward high-cost markets, the international—". This is not a minor editorial issue. The incomplete sentence precedes what appears to be a cost escalation warning or decision rule. Whatever constraint or action that sentence was introducing is absent from the document. Anyone using this document for budget planning or infrastructure decisions is missing that content with no indication of what it contained.