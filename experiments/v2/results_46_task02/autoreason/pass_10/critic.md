## Real Problems with This Proposal

### 1. The Viral Cohort Model Is Internally Contradictory

The document claims the derived inbound ceiling (~1,100/sec) is below expected delivery throughput (~1,400/sec), meaning "the system can absorb a modeled viral event in steady state without queue growth." But the stress case is 2,600/sec, which is explicitly used for queue modeling. The document cannot simultaneously claim the viral model is honest and use a stress case that is 2.4× the derived ceiling with no derivation — it just asserts "2× the derived ceiling" with no justification for why 2× is the right multiplier rather than 3× or 5×. The epistemic honesty claimed in the executive summary is not applied to the stress case.

### 2. The Worker Failover Model Is Underdeveloped for P0

P0 push has 2 workers and 1 APNs connection. The standby worker is described as covering "if the active worker crashes." But APNs HTTP/2 connections have their own failure modes — connection drops, TLS renegotiation, server-side resets. If the APNs connection itself fails, both workers are blocked on the same connection. There is one APNs connection for OTPs and security alerts, and the failover model does not address connection-level failure, only worker-level failure.

### 3. The Idempotency Key TTL Is Asserted Without Support

The document states a 1-hour Redis TTL "covers the window between crash and re-attempt under all realistic failure scenarios." No analysis supports this. What is the maximum time a notification can sit in the outbox before retry? What is the retry backoff schedule? If a worker crashes, the outbox entry is retried — but when? If the retry delay can exceed 1 hour under any failure scenario (e.g., a sustained Redis outage followed by recovery), the idempotency key has expired and the duplicate prevention fails. "All realistic failure scenarios" is asserted, not bounded.

### 4. FCM Throughput Is Treated as Non-Binding Without Verification

The document states FCM handles 10,000/sec "per Google's documentation" and dismisses FCM as a constraint at all priority levels. But FCM rate limits are per sender ID, can be subject to per-device limits, and Google's documentation on sustained throughput is not a contractual guarantee. More importantly, FCM and APNs serve different device populations — the 70% push figure is split between iOS and Android, and the document never states that split. If 80% of users are Android, FCM is the dominant delivery path and deserves the same scrutiny as APNs. Dismissing it as non-binding without stating the iOS/Android split is an unexamined assumption.

### 5. The Receipt Consistency Window Creates an Unacknowledged Audit Problem

The document describes receipts as eventually consistent with a "typically under 60 seconds" lag. For a social app this may be acceptable, but the proposal never addresses what happens when a user disputes whether a notification was delivered — for example, a missed security alert. The receipt write path is decoupled from delivery, so there is a window where the system has dispatched to APNs/FCM but has no record of doing so. The proposal treats this as a pure performance tradeoff but it has compliance and support implications that are not acknowledged.

### 6. The Non-AWS Tertiary Alerting Path Is Named but Not Specified

The executive summary correctly identifies that an AWS-dependent backup for AWS failures is circular, and states the tertiary path must be non-AWS. But nowhere in the visible proposal is the tertiary path actually specified — what service, what integration, what failure mode triggers it. Identifying a structural problem and not specifying the replacement is not a resolution; it is a placeholder labeled as a resolution.

### 7. The Aurora Write Ceiling Benchmark Is Applied Without Accounting for Read Load

The 8,000/sec conservative write floor for the in-app store is derived from a benchmark of "simple single-row inserts." But the in-app store is also read by users viewing their notification feeds. The document states "no joins on the write path," which is true, but Aurora read and write IOPS share the same instance resources. At 10M in-app notifications/day with users actively reading their feeds, read load is not zero and is not modeled. The write ceiling under concurrent read load may be materially lower than the isolated insert benchmark.

### 8. The SMS Spend Cap Is Described as "Mechanically Enforced" Without Specifying the Mechanism

The executive summary states the SMS spend cap is "mechanically enforced." Section 1.1 references it. But the proposal never states where the enforcement lives — is it a counter in Redis, a Twilio spend limit, an application-layer check? "Mechanically enforced" is a claim about implementation correctness that is not backed by a described implementation. If the enforcement mechanism fails, the cost exposure is real.

### 9. The P1 SLA Table Is Cut Off

The P1 SLA table ends mid-sentence: "On-call investigates in" — the document is incomplete at a section that describes operational response to a degraded state. This is not a minor formatting issue; it means the on-call runbook for a Warning state is undefined in the published proposal.

### 10. The 17 Notifications/DAU/Day Figure Drives Everything and Is Validated Against Nothing

The entire scale model derives from 17 notifications per DAU per day, described as an "engaged-user benchmark." The proposal says to validate it against product analytics before launch, but the infrastructure is being sized and provisioned before launch. If the actual figure is 8 or 35, the worker pool, Redis instance, Aurora instance, and queue runway figures are all wrong by a corresponding factor. The proposal acknowledges this needs validation but does not identify what the acceptable range is or what changes if the figure is outside that range.