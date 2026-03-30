## Real Problems with This Proposal

### 1. The FCM Rate Limit Is Load-Bearing But Unverified

The document explicitly states FCM rate limits are not contractually specified, then builds P1 delay estimates (20–40 minutes, 50–80 minutes) and the core architectural claim that "the binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput" on a specific figure of 2,000/sec. If that figure is wrong — and the document admits it might be — the priority queue design, worker pool sizing, and P1 protection claims are all potentially invalid. The document acknowledges this but treats it as a caveat rather than a blocking unknown. The architecture is not actually validated until the load test, but the load test is scheduled after design finalization, not before.

### 2. The Document Is Cut Off

Section 1.3b ends mid-sentence: "At 10,000 depth, the backlog represents ~9". Whatever follows — likely a time estimate or arithmetic — is missing. This is not a minor formatting issue. The threshold justification is explicitly presented as non-arbitrary and load-bearing for HPA configuration. The reasoning is incomplete in a section operators will consult during incidents.

### 3. The "One Binary, Sixteen Logical Types" Claim Creates Undisclosed Operational Risk

The proposal describes 16 logical worker types deployed as one binary with flags. The deployment complexity tradeoffs are deferred to Section 3.3, which is not included in this document. The traffic response matrix contains explicit `kubectl scale` commands targeting specific deployment names (`push-worker`, `inapp-worker`, `email-worker`). If the single-binary deployment model means these are not separate deployments — or if the flag-based differentiation means they share resource pools — the scaling commands in Section 1.3 may not achieve the intended isolation. The reader cannot verify this without Section 3.3.

### 4. The Month-1 Default Provisioning Procedure Assumes Deployment Name Stability It Cannot Guarantee

The missed-checkpoint procedure instructs operators to verify deployment names against the checklist before executing scale commands. But the checklist is a document, and deployment names can drift through routine operations, renaming, or infrastructure changes. The procedure's safety mechanism — "stop and contact the engineering lead if names don't match" — requires the engineering lead to be reachable, which is explicitly the condition that triggers Section 7.2. Section 7.2 is not included in this document.

### 5. Section 7.2 Is Referenced Three Times But Not Present

The document references Section 7.2 as a fallback for engineering lead unavailability in three distinct contexts: named decision ownership, the traffic response matrix, and the month-1 step-down procedure. Section 7.2 is not included. For a document that explicitly states "Manual, no runbook: blocked by launch gate — this state cannot occur in production," the absence of a referenced fallback procedure is a direct contradiction of that guarantee.

### 6. The Deduplication Mechanism Description Is Internally Inconsistent

The document describes two separate deduplication mechanisms with separate memory bounds: a per-user 60-second sliding window, and a system-wide delivered-ID set for cross-channel deduplication. It states these are "separate mechanisms with separate bounds" but does not specify how they interact. If a notification is deduplicated by the per-user window, does it get written to the cross-channel delivered-ID set? If not, cross-channel deduplication has gaps. If yes, the memory arithmetic for the cross-channel set (128 bytes × 10M IDs per channel) does not account for the suppressed-but-recorded entries, and the bound is understated.

### 7. The Fanout Cap Behavior Is Described as Product-Visible But the Batching Mechanism Is Not Specified

The 10,000-recipient fanout cap is flagged as requiring product sign-off, and the user-visible consequence (up to 5-minute delay beyond position 10,000) is noted. But the document does not specify what queue priority the batched overflow jobs receive, how they are scheduled, or whether they are subject to the same TTL enforcement as regular notifications. During a viral spike — exactly the condition that triggers the cap — the batch overflow jobs would be competing with the spike traffic that caused the cap to activate. This interaction is not addressed.

### 8. The Correlated Sensitivity Table Extreme Row Is Implausible as Stated

The "Extreme (viral growth)" row uses 65% DAU/MAU. The document correctly notes the valid range for unspecified social apps is 15–50%. A 65% DAU/MAU ratio is outside the stated valid range and is used without justification. If the table is meant to cover worst-case planning scenarios, using a figure the document itself identifies as outside the plausible range undermines the table's credibility as a planning tool rather than strengthening it.

### 9. The Pre-Flight Check Enforcement Mechanism Is Asserted, Not Demonstrated

The document states that placeholder text in three named fields causes the automated pre-flight check to return a non-zero exit code, blocking deployment. This is a strong operational guarantee. Nothing in the document describes what system implements this check, how it parses the deployment checklist, or what happens if the checklist is stored in a format the check cannot parse. The guarantee is load-bearing — it is cited as the reason certain failure modes "cannot occur in production" — but it is entirely unsubstantiated.

### 10. The Token Bucket Starvation Prevention Claim Is Not Parameterized

The executive summary states the token bucket "guarantees minimum throughput for lower-priority queues under sustained high-priority load." The specific conditions under which P2/P3 can still be deferred despite the token bucket are deferred to Section 3.2, which is not included. A guarantee without parameters is not a guarantee. Under the severe traffic scenario (>225M/day), the document instructs operators to "defer SMS and email dispatch" — which are lower-priority channels. Whether this manual deferral overrides or interacts with the token bucket guarantee is not addressed.