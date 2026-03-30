## Real Problems with This Proposal

### 1. The "Three-Check" Diagnostic Is Still a Tautology Problem

Check 3 requires `optin_source` to be non-null and "recognized." But the proposal never defines what makes a source "recognized" — it gives examples like `onboarding_v2` but provides no mechanism for maintaining a canonical list of valid sources, who updates it, or what happens when a new legitimate source is deployed but not yet registered. A new engineer ships a renamed onboarding flow and suddenly Path B fires on legitimate sends. Worse, the inverse: an attacker or bug that knows to write a recognized source string passes Check 3 trivially. The check is weaker than it appears.

### 2. The Escalation Path for Digest Halt Has No Weekend/Holiday Handling

The 4-business-hour compliance owner sign-off and 8-business-hour escalation to the compliance officer are defined in business hours only. A digest halt triggered Friday at 5pm means the system is halted until at minimum Monday morning — roughly 60+ hours. The proposal never addresses this. For a 10M MAU social app, a multi-day digest halt may be operationally acceptable or catastrophic, but the proposal doesn't acknowledge the scenario exists.

### 3. The FIFO Sharding Strategy Is Named but Never Specified

The executive summary states the FIFO throughput ceiling is "addressed with horizontal sharding designed pre-launch, not deferred." Section 8 is cut off in this document, and nowhere in the visible sections is the sharding design actually specified. The ceiling acknowledgment without the design is worse than silence — it creates the appearance of having solved a problem that hasn't been solved. The 3,000 messages/second per queue figure is stated without a source or verification.

### 4. The Credential Breach Row Creates an Unacknowledged SMS Cost Spike

The proposal correctly explains that credential breach notifications are MAU-bounded (10M users) rather than DAU-bounded. It also notes this is the only place SMS is modeled against MAU. But it never models the cost or infrastructure impact of sending SMS to 10M users simultaneously or in rapid succession. A credential breach notification to the full MAU at standard SMS rates would cost roughly $50,000–$100,000 in a single event. This is not mentioned anywhere in the cost section.

### 5. The Baseline Promotion Logic Has an Undefined "Stable Day" Criterion

The executive summary states the 14-day rolling average promotes to replace the load test baseline "after 7 consecutive stable days — evaluated on a filtered series that excludes days on which Warning-tier or higher alarms fired." But "stable" is never defined beyond the absence of Warning-tier alarms. A day where traffic is 40% below normal due to an outage counts as "stable" under this definition. The baseline can be contaminated by underperformance as easily as overperformance.

### 6. The OTP Email Fallback SLA Is Internally Inconsistent

The proposal states OTP email fallback has a "60 seconds P95" delivery latency SLA. Standard OTP expiry for security-sensitive flows is 30–60 seconds. A P95 of 60 seconds means roughly 5% of OTP emails arrive after the OTP may already be expired, depending on the application's OTP lifetime. The proposal never states what the OTP lifetime is, making it impossible to evaluate whether the 60-second SLA is acceptable or guarantees a meaningful failure rate for users.

### 7. The Consent Ledger Is a Single Point of Failure for Compliance

The proposal states opt-outs are enforced by "writing a suppression flag to the database synchronously on receipt." The compliance gate mechanism and the send pipeline both depend on querying this same database. The proposal acknowledges the cache TTL is not the compliance mechanism — but never addresses what happens if the database is unavailable when a worker checks for suppression. The fail-open vs. fail-closed behavior in this scenario is never specified, and for a CAN-SPAM/GDPR-relevant path, the omission is a real compliance exposure.

### 8. The 40% OTP Fallback Conversion Assumption Has No Basis

The proposal states "fallback conversion modeled at 40% of blocked SMS attempts" and calls it a "full cost model." The 40% figure appears without source, methodology, or sensitivity range. This is the number that determines whether the fallback is a minor cost item or a significant budget line, and it's presented as a fact rather than an assumption requiring a range.

### 9. The Document Is Incomplete and Presented as Complete

The document cuts off mid-sentence in the compliance gate table definition. The executive summary references Section 8 (Team Scope and Feasibility) as containing a phased scope reduction with explicit tradeoffs, but Section 8 is not present. The document claims to address all twelve design decisions explicitly, but at minimum the sharding design and the team feasibility analysis — both load-bearing claims — are missing. A proposal that claims completeness while being incomplete is more dangerous than one that acknowledges gaps.

### 10. The WAND Estimate Problem Is Displaced, Not Solved

The proposal argues the WAND estimate is "irrelevant" during Weeks 1–4 because the eligible population is enumerable from the consent ledger. This is true for the first cohort. But it sidesteps the original problem: the steady-state digest volume model still depends on WAND, and the proposal's own aggressive scenario (1.3M/day) is the threshold that triggers the compliance diagnostic. If the WAND estimate is wrong at steady state, the threshold is calibrated incorrectly. The proposal defers this problem rather than resolving it.

### 11. The Platform Mix Assumption Drives the Core Sizing But Cannot Be Validated Pre-Launch

The proposal acknowledges the 60/40 iOS/Android split is "the most uncertain input in the calculation" but then uses it as the basis for the base cost model. The sensitivity table shows the opt-in rate varies from 58.6% to 68.2% across plausible platform mixes — a meaningful range — but the infrastructure sizing and cost estimates are anchored to the 60% base figure derived from the unverified assumption. The proposal does not specify what measurement will be taken at launch to validate this assumption or what operational response follows if the actual split differs materially.