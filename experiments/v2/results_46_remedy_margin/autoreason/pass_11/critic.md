## Real Problems with This Proposal

### 1. The Document Is Incomplete

Section 1.2b cuts off mid-sentence. "Decision criteria:" has no content. This is a synthesis document being reviewed as if it were complete, but it isn't. Any evaluation of the month-3 revisit process is impossible.

### 2. The Circularity Acknowledgment Doesn't Resolve the Circularity

The document correctly identifies that the 17/day ceiling is circular, then proceeds to use it anyway as a "decision gate input." The gate thresholds (17/day, 25/day, 51/day) are all derived from the circular number. Acknowledging a problem in a callout box while embedding the problematic number in every downstream decision is not the same as handling it honestly.

### 3. The 20% Operational Time Budget Is Undefended

The proposal states each engineer allocates approximately 20% of time to operational work, but provides no basis for this figure. With no prior operational history for this system, no comparable system reference, and an explicitly acknowledged absence of SRE support, 20% is an assertion. The document then uses this number as an escalation trigger — if operations exceeds 20%, it becomes a delivery risk. That trigger is only meaningful if the 20% figure is defensible.

### 4. The Engineering Lead Is Simultaneously an Individual Contributor, Primary Architect, On-Call Escalation Path, and Executive Interface

The lead is one of four engineers. They own architecture decisions, vendor relationships, executive escalation, on-call P0 escalation, approval of infrastructure changes exceeding 20%, and coverage for E1 during absence. The proposal notes the lead is "always reachable for P0 escalations" but is never the sole on-call. This creates a person who cannot be unavailable under any circumstances for six months. There is no acknowledgment that this is a single point of failure, nor any condition under which the lead's unavailability is handled.

### 5. The False Positive Protocol Has a Structural Bias It Claims Not to Have

The protocol states the default presumption favors confirming the finding and that a valid artifact requires a specific mechanism, not a general claim of noise. But the two people conducting the review — E1 and the engineering lead — are the same people who designed the system and made the sizing decisions. Confirmation bias operates in both directions here: there is institutional pressure to find artifacts that avoid an expensive escalation, and the protocol's stated default does not neutralize that pressure because it still relies on the judgment of the same reviewers.

### 6. The LIFO Mitigation Is Assigned but Not Designed

The document identifies that Redis Lists using BRPOP exhibit LIFO behavior above approximately 1M items and states this is unacceptable for P1 delivery. The mitigation — round-robin polling across sub-queues partitioned by notification ID modulo N — is described in one sentence and assigned to E2. The value of N is unspecified. The conditions under which workers detect that depth has exceeded 500K and switch modes are unspecified. The behavior during the transition between modes is unspecified. This is a placeholder, not a design.

### 7. The Sparsity Correction Is Referenced But Never Quantified

The document repeatedly invokes a "sparsity correction" as a reason why above-ceiling readings are more alarming than they appear. The decision gate table includes a column called "Sparsity-Corrected Interpretation" with multipliers like "steady-state likely 25–40/day." These numbers appear without derivation. The sparsity correction is treated as a known adjustment when it is actually an unknown of unspecified magnitude. The proposal uses it to justify lowering the escalation threshold from 5× to 3×, but the justification is circular: the correction is unknown, therefore readings are alarming, therefore the threshold should be lower.

### 8. The Beta Cohort Size and the Measurement Window Are in Tension

Section 1.2 states Phase 1 handles a beta cohort up to 500K users. Section 1.2b states that at 200K+ users, social graph density is "materially higher than week-2, making per-T1-user rates more representative." But the measurement window for the month-3 revisit is weeks 9–10, which may correspond to anywhere between 50K and 500K users depending on beta growth rate. The proposal does not specify a minimum cohort size required for the measurement to be valid, meaning the month-3 revisit could be conducted on data that is still sparse-graph-suppressed by the proposal's own reasoning.

### 9. The Coordinated Capacity Review Has a One-Week Completion Window With No Slack

The DAU/MAU trigger initiates a coordinated capacity review that must complete within one week. The review covers Redis node count, RDS write throughput, read replica need, and worker fleet size — evaluated together. The proposal notes this is the scenario most likely to create operational confusion under a 4-engineer constraint. Yet the one-week window assumes no competing incidents, no on-call load, and no other delivery work during that week. There is no acknowledgment of what happens if the review window coincides with a Scenario A or B event, or if it runs long.

### 10. SMS Is Both Cut and Not Cut in Conflicting Ways

Section 7.2 lists "SMS channel expansion beyond auth and P0 alerts" as deferred to month 4+. It also lists "Auth SMS monitoring (required at launch)" as explicitly not cut. But the on-call page conditions include an auth SMS failure rate threshold. The operational surface for SMS is therefore active from launch. The framing of SMS as "cut" except for auth creates a false impression of scope reduction while maintaining the full operational burden of a live channel.

### 11. The 48-Hour Escalation Protocol Involves the Executive Sponsor Without Defining What That Means

A >3× reading triggers a 48-hour technical review involving the engineering lead and the executive sponsor. The proposal does not define what the executive sponsor is expected to contribute to a technical review, what decisions they are empowered to make, or what happens if they are unavailable within the 48-hour window. Executive involvement is listed as a safeguard without any specification of how it functions.