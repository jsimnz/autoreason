## Real Problems

### 1. The Circuit Breaker Math Is Internally Inconsistent

The document states the circuit breaker fires at 5,500/sec, described as "85% of the 6,400/sec provisioned ceiling." 85% of 6,400 is 5,440, not 5,500. The document explicitly claims this threshold is "derived from the throughput analysis in §1.1b, not chosen independently," but the arithmetic doesn't support the claim. This undermines the credibility of the derivation argument.

### 2. The 2-Hour Window Scenario Is Misclassified

The document says "The 2-hour window scenario is not a tail risk. It is the result of morning and evening peaks not overlapping—a plausible structure for a social app." But then the compound worst-case (50% DAU/MAU + 2-hour window + 3× burst at 15,300/sec) is accepted "as a tail risk rather than a provisioning target." You cannot have the 2-hour window be simultaneously "not a tail risk" and a component of an accepted tail risk. The classification is contradictory.

### 3. The Classifier Backpressure Analysis Is Promised but Not Delivered

The executive summary explicitly states: "Section 2.3 analyzes classifier capacity under this scenario with numbers, not assertions, and specifies the backpressure propagation strategy." Section 2.3 does not appear in the document. The document is incomplete on a point it specifically calls out as having numbers, not assertions.

### 4. The P0 Fallback SMS Volume Is Unanalyzed

Section 1.1c cuts off mid-sentence. Category 2 is never defined. More critically, the P0 SMS fallback scenario—where push fails and the system falls back to SMS for security notifications—is referenced but the volume and cost implications are never calculated. Given that the document identifies P0 delivery as protected by the circuit breaker architecture, the fallback SMS spike during a push outage could be a budget and capacity problem that is simply absent from the analysis.

### 5. The WebSocket Baseline Sizing Is Circular

The document states the 500K connections-per-instance figure is "a planning estimate derived from general reference architectures" and "not validated for this specific application." It then uses this unvalidated figure to derive the 6-instance baseline, the 40% headroom calculation for reconnection storm absorption, and the fan-out scaling triggers. The document acknowledges the estimate could be 2× off, which would cut headroom from 40% to approximately nothing—but the scaling triggers and provisioning decisions are not adjusted to account for this uncertainty. The acknowledgment of the problem does not propagate into the decisions that depend on it.

### 6. The Sticky Session Failure Mode Analysis Has a Calculation Error

"At 500K connections per instance and 6 instances, one failure adds ~120K connections to each remaining instance." 500K connections redistributed across 5 remaining instances is 100K additional connections per instance, not 120K. The headroom margin argument is built on this figure.

### 7. The Fan-Out Trigger Is Defined Against an Unvalidated Assumption

The cross-instance fan-out trigger is "if month 2 review shows DAU/MAU ≥ 40%." But the document also states the per-connection memory figure must be validated in the month 3 load test before acting on scaling triggers. The fan-out trigger is in month 2; the validation it depends on is in month 3. The document requires acting on a trigger before the validation that would inform whether acting on that trigger is safe.

### 8. The Burst Multiplier Independence Problem Is Named but Not Acted Upon

The document acknowledges that the DAU/MAU ratio and burst multiplier are correlated—"a viral event is more likely on a high-engagement day." It then uses these as if they were independent inputs in separate rows of the sensitivity table. The compound scenario at the bottom adds them together but the sustained throughput figures in the table do not reflect the correlation. The acknowledgment is present; the analysis does not change because of it.

### 9. The 3-Hour Taxonomy Timebox Has No Stated Basis

The P0 taxonomy session is "timeboxed to 3 hours" with a 48-hour escalation deadline if it stalls. The document says the taxonomy is "a prerequisite for the entire priority architecture"—circuit breaker logic, classifier routing, and queue configuration all depend on it. No basis is given for why 3 hours is sufficient to achieve consensus on a classification system that determines what gets delivered during outages. The timebox appears arbitrary against the stated criticality.

### 10. The Document References Its Own Sections That Don't Exist

Beyond §2.3, the document references §2.4 (deferred queue bounded failure mode under sustained overload), §2.5 (behavior when demand exceeds 6,400/sec), §3.1 (taxonomy specification), §4.2 (mobile SDK contract), §6.3 (instance utilization alert), and §7 (delivery plan). None of these sections are present. The executive summary is written as though the full document exists, but the document provided ends partway through §1.1c. Evaluating the architecture requires trusting that the referenced analyses exist and are sound, which cannot be verified.