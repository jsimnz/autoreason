## Real Problems with This Proposal

### 1. The Cross-Timezone Smoothing Factor Is Invented

The 0.6× smoothing factor for global peak calculation is presented without any derivation, citation, or data source. The document spends considerable effort justifying other multipliers but simply states this one. Since it directly affects the provisioning target (120/second instead of ~200/second), an unsupported factor at this step has meaningful downstream consequences for whether the system is actually over-provisioned as claimed.

### 2. The Tier 1 Rate Limit Creates a Security Vulnerability

The 1,000 Tier 1 events/minute cap with manual override requirement means that during a genuine large-scale security incident—credential stuffing affecting 50,000 accounts, for example—legitimate security notifications will be throttled and require a human to manually intervene before affected users are notified. The document treats this as a cost control mechanism without acknowledging that it directly conflicts with the stated purpose of Tier 1: reliable delivery of security events. The tension is not named.

### 3. The Digest Job Truncation Is Incomplete

The document cuts off mid-sentence: "A notification received at—" The digest batching section is unfinished. This is not a minor editorial issue; digest behavior at boundaries (what happens to notifications received after the 06:00 snapshot, whether they appear in the current digest or the next one, whether there's a gap) is unspecified. For a section that claims to state limitations explicitly, leaving this undefined is a substantive gap.

### 4. The DAU/MAU Validation Owner Is Not Named

The document states the ratio "must be validated against actual product analytics within 30 days of launch" and describes the validation process as being in §1.8, but §1.8 is never shown. No specific person is named as owning this validation. The batching threshold review names an owner ("the backend engineer designated to the notifications team at project kickoff") but the more foundational load assumption review does not.

### 5. The Twitter Peak/Average Citation Is Misapplied

The document cites Twitter's "approximately 3:1 peak/average ratio for notification volume" as the basis for the 3.5× evening peak multiplier. Twitter's documented peak ratios refer to tweet volume or API request volume, not notification delivery volume—these have different shapes because notifications are triggered by actions but delivered asynchronously and can be batched, delayed by quiet hours, or suppressed. Using action-volume ratios to model delivery-volume ratios introduces an unacknowledged methodological error.

### 6. Hash-Based Jitter Clustering Is Underexamined

The document acknowledges hash-based jitter doesn't produce perfectly uniform distribution but dismisses this as "close enough." For user ID spaces that are sequential integers or UUIDs with structured prefixes, certain hash functions produce non-uniform distributions with clustering. The specific hash function is not named, and no analysis of the actual distribution is provided. For a system where the whole point of jitter is peak reduction, the quality of the distribution matters and "close enough" is asserted rather than demonstrated.

### 7. The 30-Day Replacement of Estimates Is Unenforceable

The document repeatedly states that instrumentation will replace estimates "within the first 30 days." But there is no specification of what instrumentation is required, who reviews it, what decisions are triggered by what findings, or what happens if the estimates turn out to be wrong by a factor that requires infrastructure changes. "Actual numbers replace estimates" is not an action plan; it's a deferral dressed as a commitment.

### 8. The SMS Cost Model Double-Counts Scope

The SMS cost estimate calculates 625 SMS-triggering security events per day, derived from 0.05% of DAU. But the derivation applies two separate filters (30% of security events for 2FA, 20% for suspicious login) and then combines them without clarifying whether these are mutually exclusive populations. If a user triggers both a 2FA SMS and a suspicious login alert in the same session, they may be counted in both buckets, meaning the 625/day figure understates volume. The model doesn't address this.

### 9. APNs/FCM Rate Limit Escalation Is Treated as Risk Mitigation When It Isn't

The document states the team lead will "contact APNs and FCM developer relations in month 1 to document current limits and request information on the increase process." Apple and Google do not negotiate rate limit increases for APNs/FCM on request—these are platform-level constraints that are not generally adjustable through developer relations contact. Naming this as a "pre-launch dependency" implies it can be resolved; it likely cannot, making it a permanent architectural constraint the document mischaracterizes.

### 10. In-App 30-Day Window Archival Is Explicitly Deferred Without a Date

The document states "archival behavior at that boundary is addressed in §1.9" but §1.9 is not included. This is a user-facing behavior gap: users who look for notifications older than 30 days will either find nothing or find something, and the system has no specified behavior for which it is. Deferring this to an unreferenced section while claiming the design is "complete" in the preface is a direct contradiction.

### 11. The Spike Batching Threshold Has No Basis

The 500,000 message queue depth trigger for spike batching is stated without derivation. Unlike the notification volume estimates, which show their work, this number appears without explanation of why 500,000 rather than 100,000 or 1,000,000. Since this threshold determines when user-visible latency increases and DM exclusion becomes relevant, it is a consequential parameter presented as if it were self-evident.