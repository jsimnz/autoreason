## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.4 ends abruptly: "High end (70% capacity): 90" — the P1 delay derivation is incomplete. The document promises step-by-step arithmetic and then doesn't deliver it. The "20–40 minutes" and "50–80 minutes" figures cited in the executive summary have no visible derivation. A reader cannot verify the core latency claims the architecture depends on.

### 2. FCM Backoff Model Is Asserted, Not Sourced

The document states FCM's documented backoff "reaches approximately 32 seconds between retry attempts (5 doublings from a 1-second base)." FCM's actual retry behavior under sustained 429s is not publicly documented with this precision. The document treats this as a known engineering fact when it is an assumption. The entire post-spike drain timeline — and therefore the P1 delay figures — depends on this number being correct.

### 3. The Starvation Claim Is Internally Contradicted

The executive summary says the token bucket "does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation" and promises the conditions are specified in Section 3.2. Section 3.2 is never shown in this document. A critical safety property — when starvation actually occurs — has no specification visible to the reader. The promise to specify it is not the same as specifying it.

### 4. Orphaned Processing Set Entries: Mitigation Is Circular

The document acknowledges that if the worker hosting the recovery goroutine crashes and the container is destroyed, processing set entries may be orphaned. The mitigation is described as "a cross-instance recovery sweep in Section 2.1." Section 2.1 is about the processing Sorted Set design and PostgreSQL pool exhaustion — it does not describe a cross-instance recovery sweep in what is shown. The mitigation for a named failure mode points to content that either doesn't exist or isn't shown.

### 5. The "Named Humans" Requirement Has No Enforcement Mechanism

The document states three decisions require named humans and that placeholder text blocks the deployment checklist gate. But the deployment checklist itself (Section 7.1) is not shown. There is no visible mechanism that actually blocks deployment. The gate is asserted to exist but cannot be verified. This is a governance claim with no supporting structure.

### 6. Month-1 Checkpoint Default Is Operationally Vague

If the traffic review is missed, the system defaults to provisioning for 100M/day. But "provisioning" is not defined here — it's unclear whether this means adding workers, resizing Redis, both, or something else. The default is stated as automatic but requires human action to implement. Who takes that action, and how, is unspecified.

### 7. The Conservative Fallback Mode Has a Silent User Impact Buried as a "Product Decision"

The document states users do not receive notification that their P2/P3 notifications are delayed, and calls this "a product decision recorded here so the product team is aware." This framing treats a potentially multi-hour user-facing degradation as an internal note. The 48-hour threshold before notifying the product team means users could experience significant silent notification loss before anyone outside engineering is informed. The document does not specify what "engineering review within 24 hours" of hitting queue bounds actually entails or who conducts it.

### 8. The 80M/Day Redis Provisioning Decision Is Deferred Incorrectly

The document says the default is to provision Redis at 80M/day capacity but then says "if this is not acceptable for cost reasons, a larger replica must be pre-provisioned and promotion scripted before production launch." This creates a situation where the cost decision — which may not be made until late in the project — determines whether the traffic response matrix is executable. If the cost decision goes the other way, the matrix entries for the 45M–80M/day band become invalid. The dependency is acknowledged but not resolved.

### 9. DAU/MAU Correlation Modeling Excludes One Quadrant Without Full Justification

The document dismisses the low DAU/MAU × high notification rate scenario as "covered by the low-engagement row" and calls this a "modeling choice, not an oversight." But a social app where a small fraction of users is extremely active (power users generating high notification volume) is a plausible and common pattern. Dismissing it because total volume is below the plan figure ignores that it could stress specific subsystems — per-user rate limiting, deduplication set sizes, or recipient fanout — in ways the plan figure doesn't capture.

### 10. The Deduplication Memory Bound Is Stated But Not Quantified

The document states deduplication uses an explicit delivered-ID set with "bounded memory" and that the tradeoff is stated in Section 2.2. Section 2.2 is not shown. The actual memory bound — how many IDs, at what size, for what retention window — is never specified in visible content. "Bounded" is not a number.

### 11. The Viral Spike Pre-Production Load Test Has No Staging Environment Validity Argument

The document requires load testing against a staging FCM project to determine rate limits, then applies those results to production. FCM rate limits are per-project and may differ substantially between a staging project and a production project with a large user base. The document acknowledges FCM limits are not knowable in advance but then treats staging load test results as decision-relevant for production. This gap is not addressed.

### 12. Worker Pool Specialization Creates Undiscussed Deployment Complexity

The document states workers are implemented as "specialized binaries per channel type." With four channels and four priority levels, this implies up to 16 binary variants. Operational complexity — deployment coordination, version skew between binaries, incident diagnosis across binary types — is not discussed. The traffic response matrix tells engineers which worker type to scale but says nothing about how to deploy or update those workers under incident conditions.