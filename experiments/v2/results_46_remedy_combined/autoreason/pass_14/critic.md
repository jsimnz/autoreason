## Real Problems with This Proposal

### 1. The OTP Compliance Justification Is Circular and Legally Unsound

Section 6.3 (referenced but not included) apparently justifies the OTP carve-out from fail-closed behavior by arguing the compliance risk of delivering OTP to an opted-out user is acceptable. But OTP doesn't have an opt-out category — the document acknowledges this. The argument is essentially "the compliance risk is low because there's nothing to violate." This doesn't address the actual compliance exposure: delivering *any* communication during a database outage when consent state is unknown. GDPR and TCPA don't care about your internal opt-out categories; they care about whether you had a lawful basis to send. The document waves this away rather than analyzing it.

### 2. WAND Is Load-Bearing and Undefined Until Week 4, But Week 1 Digest Sends Happen Anyway

The document claims Day 7 digest volume is "directly measurable from the consent ledger, not a WAND estimate." This is technically true but misleading. The *threshold* that determines whether Day 7 volume triggers an anomaly alert still uses the aggressive scenario ceiling (1.3M/day) as a floor — derived from the WAND estimate. If actual Day 7 volume is anomalously high due to an instrumentation error or a bot attack, the threshold won't catch it because the floor was set from an unvalidated estimate. The document presents this as solved when it isn't.

### 3. P0 Fixed at 4 Instances With No Capacity Justification

The document states P0 workers are fixed at 4 instances because "the operational risk of a scaling delay on OTP delivery outweighs the cost." But it never establishes that 4 instances are sufficient for peak P0 load, let alone a credential breach event sending to all 10M MAU. A credential breach SMS blast is explicitly modeled as a P0-adjacent event. If 4 fixed workers can't process 10M messages within an acceptable window, the entire rationale for fixed sizing collapses. The number 4 appears without any derivation.

### 4. The Credential Breach Row Is Architecturally Inconsistent

The proposal routes credential breach SMS through MAU (10M) rather than DAU, correctly noting it's an administrative action. But the queue architecture in Section 2 assigns tiers based on delivery SLA and batching behavior, not trigger type. A 10M-recipient SMS blast has completely different throughput characteristics than an OTP. There's no discussion of how this event interacts with the P0 fixed-worker constraint, Twilio rate limits, or cost ceilings. It's called out in the scale model and then architecturally orphaned.

### 5. SQS FIFO Sharding Breaks the Ordering Guarantee It Claims to Preserve

The document says per-conversation ordering is preserved because all messages for a conversation route to the same shard via consistent hashing on `conversation_id`. This is only true if the shard count never changes. Resharding — which will be necessary if 4 queues prove insufficient — requires rehashing, and during that transition, in-flight messages for a given conversation may route to different queues. The document notes shard count is "4 at launch" with no discussion of what happens when it needs to change. The ordering guarantee is fragile in exactly the scenario where it would be tested.

### 6. The Baseline Stability Definition Has a Measurement Gap

A "stable day" requires no Warning-tier alarms fired during that calendar day. But alarms are assessed "retrospectively at 00:05 UTC each day for the prior calendar day." This means an alarm that fires at 23:55 UTC and clears at 00:10 UTC contaminates the prior day's stability assessment but may not appear in whatever monitoring surface the on-call engineer is watching for that day. The document doesn't specify how alarms that span the UTC day boundary are attributed, creating an ambiguity in the stability counter that could either prematurely promote a baseline or indefinitely delay promotion.

### 7. Separate IP Pools Are Declared "Not Negotiable" Without Operational Ownership

The document states digest and transactional email use separate IP pools and that this "is not negotiable." But IP pool reputation management — monitoring complaint rates, warming new IPs, handling blacklisting — is a continuous operational task. With 4 engineers and a 6-month timeline, there's no discussion of who owns this, what the warm-up schedule looks like, or what happens if SendGrid's shared pool is used initially. Declaring something non-negotiable doesn't make it operationally free.

### 8. The 35% DAU Assumption Is Used to Calibrate Alarms, Then Disclaimed

Section 1.1 says "all operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from this assumption." But Section 1.3 uses DAU-derived figures to set the transactional email alert threshold at >750K/day. That 750K number is derived from the ~230K–500K/day estimate, which is derived from MAU percentages — not DAU directly, but still from population assumptions. The disclaimer in Section 1.1 is broader than what the document actually delivers.

### 9. Engineer C Is a Single Point of Failure for Threshold Recalibration

The digest threshold recalibration job is explicitly owned by Engineer C. On a 4-person team, this is a named individual, not a role. There's no discussion of what happens when Engineer C is unavailable, on leave, or leaves the team. The document identifies this as a critical operational process (the threshold "does not silently reset to a default") and then assigns it to one person with no redundancy.

### 10. The Phase Boundary Is Described But Not Defined in the Included Sections

The executive summary references Phase 1 (months 1–4), Phase 2 (months 5–6), and post-launch deferrals, directing readers to Section 8. Section 8 is not included in the provided document. Every feasibility claim in the earlier sections — particularly around the 4-engineer, 6-month constraint — is therefore unverifiable from what's presented. This isn't a minor gap; the entire "Team Scope and Feasibility" justification is missing.