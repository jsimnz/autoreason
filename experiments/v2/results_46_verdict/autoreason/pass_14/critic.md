## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.1c ends abruptly: "The allowlist is a versioned configuration file requiring two-engineer PR review to modify. **2. Fall**—" The gate enforcement section is incomplete. This isn't a minor formatting issue; it's a missing specification for a critical security control in a system handling auth/OTP routing.

### 2. The Classifier Is Underspecified Despite Being Named a Contention Point

The executive summary explicitly flags the classifier as a contention point and promises Section 2.3 will analyze its capacity. Section 2.3 doesn't exist in this document. The classifier's throughput ceiling, failure mode, and backpressure propagation strategy are entirely absent. This is the document's most significant structural gap given how much weight the architecture places on it.

### 3. Section 2.4 Is Also Missing

The executive summary references "Section 2.4 analyzes the bounded failure mode of that deferred queue under sustained overload." Section 2.4 doesn't appear. The deferred P2 queue's failure mode under sustained overload—explicitly called out as needing analysis—is never analyzed.

### 4. The Burst Multiplier and the Peak Window Assumption Compound in a Way That's Understated

The document notes the multiplier and DAU/MAU ratio "are not independent" but doesn't follow through on the math. The worst-case compound scenario (50% DAU/MAU + 2-hour window + 3× burst) produces 15,300/sec—2.4× the provisioned ceiling of 6,400/sec. The circuit breaker at 5,500/sec doesn't protect against this; it fires well below even the baseline burst ceiling. The document acknowledges this gap exists but doesn't specify what happens to the system when instantaneous demand exceeds 6,400/sec, which is reachable under non-exotic conditions.

### 5. The Month 3 Load Test Is Structurally Insufficient

The load test is scheduled after the system launches (implied by "the system launches before month 5") but the document doesn't say when launch occurs relative to month 3. If launch is month 2 or early month 3, the load test validates a live production system after real users are on it. The deliverables listed (saturation point identification, go/no-go on burst multiplier) are things you need before launch, not after. The framing that moving load testing to month 3 is safer than month 5 is correct but incomplete—it doesn't address the case where launch precedes month 3 completion.

### 6. The 500K Connections Per Instance Figure Has No Validation Basis

The WebSocket sizing assumes 500K connections per instance at ~4GB RAM. This is a planning estimate for a system that doesn't exist yet. Connection state memory varies significantly based on what's stored per connection, message frequency, and TLS overhead. No load testing, no reference architecture, and no measurement basis is cited. The entire WebSocket scaling path—including the DAU/MAU trigger thresholds—inherits this uncertainty without acknowledging it.

### 7. The P0 Taxonomy Dependency Is Acknowledged but the Consequence Is Understated

The document correctly identifies that P0 classification is a product negotiation with no guaranteed timeline and blocks SMS provisioning. But the same dependency exists for the circuit breaker logic (P0/P1 traffic must be protected before shedding P2), the priority classifier design, and the queue routing rules. None of these can be fully specified without a stable taxonomy. The document treats this as a scheduling risk for SMS budgeting specifically, when it's actually a prerequisite for the entire priority architecture.

### 8. Sticky Sessions for WebSocket Are a Hidden Single Point of Failure

The document specifies sticky sessions via load balancer for WebSocket connections but doesn't address what happens when a WebSocket instance goes down. All connections on that instance need to reconnect, and the load balancer's sticky session table for those users is now invalid. At 500K connections per instance, an instance failure triggers a reconnection storm. This failure mode isn't mentioned, and there's no specification for how the system behaves during it.

### 9. The $15K/$25K Escalation Thresholds Have No Derivation

The Tier 2 escalation thresholds ($15K pages on-call, $25K escalates to leadership) appear without basis. The document is otherwise careful to derive numbers from other numbers. These thresholds determine when human intervention fires in a cost-runaway scenario, but there's no explanation of why these specific values were chosen relative to the $47,250/month worst-case scenario or the $11,250/month fixed floor.

### 10. "Two-Engineer PR Review" Is Not a Runtime Control

The type gate for SMS routing is described as a versioned config file requiring two-engineer PR review. This is a change management control, not a runtime enforcement mechanism. Nothing in the document specifies how the running system validates that the deployed allowlist hasn't been modified outside the PR process, or how the system behaves if a misconfigured allowlist is deployed. For a gate protecting against attacker-triggered OTP suppression (a threat the document explicitly names), relying on process controls without runtime validation is a gap.

### 11. The 60% Peak Concentration Figure Is Uncited

The claim that morning and evening peaks together account for ~60% of daily volume is load-bearing for all throughput calculations but has no source. Unlike the DAU/MAU ratio (which the document acknowledges is uncertain and bounds with a sensitivity table), the 60% figure is presented as a planning input without equivalent uncertainty treatment. If actual peak concentration is 75%, the sustained throughput calculations are wrong by ~25%.

### 12. Sections 3 Through 6 Don't Exist

The document references §3.1 (notification taxonomy), §6.3 (monitoring dashboard), and implies other sections exist. None of them are present. The document is incomplete in ways that affect evaluating the claims made in the sections that do exist—the taxonomy underpins priority routing, and the monitoring dashboard is cited as the mitigation for the escalation gap acknowledged in §1.1c.