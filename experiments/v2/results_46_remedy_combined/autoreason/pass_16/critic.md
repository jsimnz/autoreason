## Real Problems

### 1. The GDPR Legal Basis Argument Is Asserted, Not Demonstrated

The document states that GDPR Article 6(1)(b) contractual necessity applies to OTP delivery and that this is "the more defensible basis." It dismisses legitimate interests because it "requires a balancing test." But Article 6(1)(b) contractual necessity is interpreted narrowly by EU regulators and the EDPB — it applies only when processing is *objectively necessary* to perform the contract, not merely useful or convenient. Whether OTP delivery specifically meets that threshold in this jurisdiction, for this product, with this user contract, is a legal determination that cannot be made by engineers in a design document. The document acknowledges it requires "authorization outside the engineering team" in other places but does not apply that same standard here. The legal analysis is missing, not deferred.

### 2. The 30% DAU Assumption Has No Validation Gate Before Infrastructure Commitment

The document says DAU is "modeled at 30% of MAU" and that "all operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline." But the load test itself must be parameterized before production data exists. The 30% assumption therefore directly shapes the load test design, which shapes the baselines, which shapes the alarms. If the actual DAU/MAU ratio is 15% or 50%, the load test was run against the wrong parameters and the baselines are wrong from day one. There is no stated validation gate that checks whether the load test parameters were reasonable before baseline promotion occurs.

### 3. Stable Day Definition Has an Unresolved Edge Case in Condition 3

Condition 3 excludes days where volume is more than 10% below the 7-day rolling average, to prevent outage days from dragging the baseline down. But the rolling average for Day N uses Days N−7 through N−1. If Days N−7 through N−1 themselves include contaminated or excluded days, the rolling average is computed over a sparse or inconsistent window. The document does not specify what happens when fewer than 7 valid days exist in the lookback window — whether the window shrinks, the calculation is skipped, or the threshold holds. This is a real gap in a system where early production days are most likely to have anomalies.

### 4. The Credential Breach 4-Hour Window Has No Basis

Section 2.6 is cited repeatedly for the P-CB capacity analysis, but within the visible portion of this document, the 4-hour delivery window for a 10M-recipient SMS blast is stated without justification. Whether Twilio can sustain the required throughput within that window depends on account tier, short code provisioning, and carrier throughput limits — none of which are mentioned. A 10M SMS blast is not a routine operation for Twilio accounts; it requires advance coordination with the provider. The document treats this as an infrastructure sizing problem when it is partly a vendor relationship and provisioning problem.

### 5. The Consent Ledger Is Both the Sizing Source and the Anomaly Detection Boundary

The Day 7 anomaly threshold is set at 2× the consent-ledger-derived eligible population. The document then acknowledges that if the consent ledger is corrupted by a bot attack, "the threshold derived from it will be wrong." This means the anomaly detection system for digest email volume is directly undermined by the same attack vector it is supposed to help detect. The mitigation is deferred entirely to onboarding fraud controls described as "outside the scope of this document." The notification system therefore has a named, acknowledged failure mode with no internal defense and an external dependency that isn't specified or committed to anywhere in this document.

### 6. IP Pool Warm-Up Has No Fallback If It Fails

The document states that digest and transactional email use separate IP pools and that the warm-up schedule is in Section 3.3. It also states that a spam complaint spike from digest mail blacklisting the password-reset pool is "a direct revenue impact" — which is precisely why the pools are separated. But there is no discussion of what happens if the digest IP pool fails warm-up, is blacklisted during warm-up, or SendGrid throttles it. The separation protects the transactional pool from digest problems, but it does not protect digest deliverability itself. For a new app, digest email deliverability failure in the first weeks would suppress a significant re-engagement mechanism with no stated recovery path.

### 7. The ±5 Point Threshold Justification Is Circular

The document argues that ±10 points is wrong because it would place 50/50 at the trigger boundary while characterizing a 60/40→50/50 shift as within tolerance — calling this an "internal inconsistency." Then it argues ±5 is correct because "shifts producing less than ~5% volume change are within tolerance." But the tolerance level itself (5% volume change) is not derived from anything — not from cost modeling, not from capacity limits, not from SLA requirements. The argument proves that ±5 is internally consistent with the 5% tolerance assumption, but it does not justify why 5% is the right tolerance. The reasoning is self-referential.

### 8. Baseline Promotion Requires 7 Consecutive Stable Days but the Promotion Mechanism Isn't Specified

The document states a 14-day rolling average promotes to replace the load test baseline after 7 consecutive stable days. It defines stable days carefully. But it does not specify what entity performs the promotion, whether it is automatic or requires human approval, what happens if stable days are achieved but the rolling average is still anomalous (e.g., consistently low due to a slow launch), or whether the promotion can be reversed. For a safety-critical baseline that governs alarm thresholds, an unattended automatic promotion is a real operational risk.