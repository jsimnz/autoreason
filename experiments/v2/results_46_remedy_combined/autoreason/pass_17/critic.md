## Real Problems with This Proposal

### 1. The GDPR Legal Basis Argument Is Asserted, Not Demonstrated

The document states that GDPR Article 6(1)(b) contractual necessity is "the more defensible basis" for OTP carve-outs and that "the full analysis is in Section 7.2." Section 7.2 is referenced but not included in this document. The legal reasoning is load-bearing — it justifies the entire fail-open path for OTP and security alerts — but reviewers cannot evaluate it. "More defensible" is a conclusion without visible premises.

### 2. The Consent Ledger Is Both the Control and the Anomaly Detector

In Section 1.3, the consent ledger is used to derive the eligible digest population, and the anomaly threshold is set at 2× that same ledger count. If the ledger is compromised (the document acknowledges a bot-attack scenario), both the send list and the threshold that would catch the problem are corrupted simultaneously. The document names fraud controls as a "hard dependency" outside scope, but this circular dependency means the notification system provides no independent check — it will faithfully send to a fraudulently inflated population and not alarm because the threshold grew with it.

### 3. P0 Worker Sizing Derivation Is Referenced but Absent

The executive summary states "The derivation is in Section 2.5" for why P0 workers are fixed at 8 always-on instances. Section 2.5 is not present in this document. The claim that 8 instances is sufficient cannot be evaluated. The document also says this capacity "must first be demonstrated sufficient through load testing before launch" — which means the number is not yet validated, yet it is presented as a settled architectural decision.

### 4. The Credential Breach Subsystem Capacity Analysis Is Missing

Section 2.6 is referenced multiple times for the P-CB capacity analysis — the throughput model for a 10M-recipient SMS blast within a 4-hour window. That section is not included. This is the highest-consequence single event the system must handle, and the sizing basis is entirely absent from review.

### 5. The Resharding Migration Procedure Creates an Undisclosed Ordering Risk

The document states that SQS FIFO is used for P1 (direct messages) because per-conversation ordering matters, and that a resharding migration procedure exists in Section 2.4. Section 2.4 is not present. SQS FIFO ordering is scoped to a message group ID, and resharding — changing how conversations map to message group IDs — can cause messages in flight during migration to be delivered out of order. The document asserts ordering matters for P1 but provides no analysis of ordering guarantees during the migration itself.

### 6. IP Pool Warm-Up Operational Ownership Is Deferred, Not Resolved

The executive summary says "operational ownership" of the IP pool warm-up schedule is "in Section 3.3." Section 3.3 is not included. IP pool warm-up is time-sensitive and sequencing-dependent; if it is not completed before transactional email volume ramps, the password-reset pool can be blacklisted by the digest pool's complaint rate — the exact failure mode the design claims to prevent. The ownership gap is not a documentation problem; it is an unresolved operational dependency.

### 7. The 30% DAU Assumption Has No Feedback Mechanism Before It Matters

The document states that all operational thresholds depending on DAU are expressed as "multiples of a load-test-anchored baseline" rather than absolute figures — which is correct. But the load test parameters themselves (Section 2.7, not included) presumably encode a DAU assumption. If the actual DAU is significantly below 30%, the load test baseline will be calibrated to a higher-than-actual traffic level, and the alarm thresholds derived from it will be too permissive. There is no stated protocol for adjusting load test parameters if pre-launch registration volume indicates the DAU assumption is wrong.

### 8. The OTP Email Fallback Volume Is Unmodeled

The transactional email table lists "OTP email fallback" as "Variable; see Section 3.4" and notes it is "Activated when SMS rate-limited." The 750K/day planning bound for transactional email is stated without including this variable. If SMS rate-limiting coincides with a high-DAU period, OTP email fallback volume could be substantial and is entirely unaccounted for in the SendGrid plan tier sizing. The document acknowledges the variability but provides no bounding analysis.

### 9. The Stable Day Definition Has an Unresolved Edge Case at Volume Condition 3

Condition 3 requires volume to be within +20%/−10% of the rolling average of the preceding 7 days. The rolling average for Day N uses Days N−7 through N−1. If Days N−7 through N−1 include contaminated (unstable) days, those days' volumes still contribute to the rolling average — the definition does not exclude them. A week with several outage days produces a depressed rolling average, making it easier for subsequent days to satisfy condition 3 at lower-than-normal volume. The baseline can drift downward through a sequence of contaminated days even though the asymmetric bounds were explicitly designed to prevent downward drift.

### 10. The 4-Engineer / 6-Month Feasibility Assessment Is Entirely Absent

Section 8 is titled "Team Scope and Feasibility" and is referenced as specifying exactly what ships in Phase 1, Phase 2, and what is deferred. It is not present in this document. For a proposal explicitly scoped around a 4-engineer constraint, the feasibility argument is the central claim that needs review — and it is missing entirely.