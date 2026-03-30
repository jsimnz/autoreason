## Real Problems with This Proposal

### 1. The "Architecture is Independent of Sizing" Claim is Partially False

The document repeatedly asserts that architecture decisions don't change regardless of sizing assumptions. This is wrong in at least one important case: at the (60% DAU/MAU, 50 events/DAU) cell — 10,400 events/second burst ceiling — the single-region, SQS-based architecture may not hold. SQS has throughput limits per queue, and the document never addresses whether the queue topology scales to that ceiling. The claim of independence is asserted, not demonstrated.

### 2. The 99.5% Availability Derivation is Circular

The document says 99.5% is "derived from the failure mode analysis in §6.4" and that §6.4 "enumerates failure probability and recovery time for each system component." But §6.4 is not included in this document. The availability target is presented as analytically grounded when the actual analysis is missing. A reader cannot verify the claim.

### 3. Parallel Dispatch Sign-off is Structurally Broken

The document requires Jordan Rivera's sign-off before the Critical path goes to production, but the sign-off mechanism is a placeholder in a design document. There is no defined process for what happens if sign-off never comes, who enforces the gate, or how the recorded approval gets linked to the deployment pipeline. A comment in a doc is not a governance control.

### 4. The SMS Cost Estimate Has an Unexamined Input

The SMS cost calculation depends on "expected Critical events per user per month," which the document estimates at 2. This number has no stated basis. For a security-event-driven trigger like "unrecognized device login," the actual rate depends entirely on user behavior patterns, geographic distribution of login attempts, and whether the product has bot/abuse problems. A platform with significant credential-stuffing exposure could see this number be 10x higher, making the $50–70K/month estimate wildly low.

### 5. The 5-Device Limit Has No Stated Rationale

The document specifies a 5-device limit with a specific eviction policy but never explains why 5. It's not derived from any constraint — not storage, not throughput, not cost. It reads as an arbitrary number that will be questioned in implementation and has no defense in the document.

### 6. Quiet Hours is Mentioned Once and Never Specified

Section 1.2 excludes ML-based send-time optimization in favor of "fixed quiet hours." Quiet hours never appear again in the document — not in the priority schema, not in delivery logic, not in user preferences. It's unclear whether quiet hours suppress Critical notifications, who configures them, whether they're per-user or system-wide, and what timezone logic applies. The exclusion is documented; the replacement behavior is not.

### 7. The Geographic Peak Multiplier Logic Has an Error

The document states that a US+Western Europe deployment produces a *lower* peak multiplier (1.6×) than US-only (2.0×). The explanation is that global distribution smooths peaks. But this comparison is between a US-only user base and a US+Europe user base — two different user distributions, not the same users distributed differently. If the product *adds* European users, total volume increases even if the multiplier decreases. The table conflates "multiplier" with "absolute peak" in a way that could lead to under-provisioning when the product expands geographically.

### 8. Token Refresh "On Each App Open" Creates an Undefined Write Pattern

The document says tokens are refreshed on each app open. At 3M DAU with typical mobile session behavior, this could mean millions of token refresh writes per day with significant spikes at morning wake-up times. The document never accounts for this write load in capacity planning. It also creates an ambiguity: does "refresh" mean a write on every app open regardless of whether the token changed, or only on token change? These have very different database load profiles.

### 9. The `event_type_registry` is Mentioned Without Specification

Section 2.1 states that duplicate-notification UX mitigation "must be enforced in the `event_type_registry` template fields and audited before launch." This registry is never defined anywhere in the document — its schema, ownership, update process, and audit mechanism are all absent. A requirement pointing to an undefined artifact is not actionable.

### 10. Phase Boundaries Are Not Defined

Section 8 is listed as "Phased Delivery Plan" in the table of contents but the section content is not included in this document. Given that §1.1.2 explicitly states "this assumption must be revisited before Phase 2 infrastructure is provisioned," the absence of phase definitions means there is no specified trigger for that revisitation. The governance dependency on phase content is real and unresolved.

### 11. The Burst Ceiling Formula Double-Counts the Geographic Multiplier

The formula in §1.1.3 is:
```
(MAU × DAU/MAU ratio × events/DAU/day / 86,400) × 3.0 × geographic peak multiplier
```

But the 3.0× burst headroom ceiling is already defined in §1.1 as being *above* the geographic peak — it is explicitly described as the infrastructure provisioning target that exceeds the geographic peak. Multiplying by both 3.0 and the geographic peak multiplier compounds them, which contradicts the table in §1.1 where the burst ceiling is 3.0× average (not 3.0× geographic peak). The formula is inconsistent with the table it's meant to encode.