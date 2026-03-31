## Real Problems with This Proposal

### 1. The Weighted Fair Queuing Model Has the Same Concurrency Problem It Claims to Fix

The proposal correctly identifies that strict priority dequeuing breaks under concurrency, then replaces it with weighted round-robin sampling — but the concurrency problem is not actually resolved. With N independent workers each sampling queues according to fixed probability weights, a burst of P0 items still competes with workers already mid-processing P1/P2/P3 items. The 60% weight means that in steady state, 40% of worker cycles are spent on non-P0 work even when P0 is backlogged. The proposal diagnoses the original problem accurately and then does not solve it.

### 2. The 1.02× Reduction Factor Renders the Batching Math Meaningless

The revised email batching model concludes that at average λ, the reduction factor is approximately 1.02× — essentially zero. The proposal then correctly states it sizes for the lower bound and retains the window only for product quality reasons. But this creates an unacknowledged problem: the entire Section 1.3 apparatus (recalculation job, P1 alerting, 30-minute SLA, E4 paging) is now infrastructure built around a parameter (batch window size) that has no meaningful throughput impact at current scale. The operational overhead of this enforcement mechanism is not justified by the math the proposal itself presents.

### 3. The High-Follower Fanout Volume Is Deferred Without Acknowledging the Launch Risk

Section 1.5 states that enabling follower notifications would increase volume by approximately 4× (from ~18M to ~78M events/day) and explicitly says this scenario is not built for. It then says "E1 owns surfacing this dependency to the product team before the feature is enabled." This is a single engineer as a process control for a decision that would invalidate the entire infrastructure plan. There is no documented escalation path, no formal sign-off requirement, and no mechanism preventing the product team from enabling follower notifications without E1's awareness.

### 4. The TCPA Bus Factor Remediation Does Not Address the Actual Risk

The remediation reduces the bus factor from 1 to 2 by having E1 co-author the runbook and execute a simulated incident. The proposal acknowledges this explicitly. But the original risk was not just "two people need to know how to run the suppression cache" — it was that TCPA compliance failures carry legal liability. Having two engineers who can execute a runbook does not address what happens if both are unavailable simultaneously (vacation, illness, turnover), which is the scenario where bus factor risk materializes. The proposal names this a real risk, performs a partial remediation, and then stops without addressing the residual legal exposure.

### 5. The Fanout Rate Limiter of 5,000 Events/Second Is Unvalidated

The high-follower fanout path caps output at 5,000 events/second. This figure has no stated basis — no calculation connecting it to queue capacity, worker throughput, or downstream channel limits. It appears as a round number with no derivation. At the same time, Section 1.5 acknowledges that enabling follower notifications could add 60M events/day. At 5,000 events/second, clearing 60M events takes approximately 3.3 hours of sustained fanout output. The proposal does not address what happens to queue depth or delivery latency during that period.

### 6. Section 3.4 Is Referenced as Corrected but the Document Is Cut Off

The executive summary states "Section 3.4 (in-app/WebSocket) is now included. It was the highest-volume channel and was absent from the visible design." The document ends mid-sentence in Section 2.1. Section 3.4 does not appear in this revision. The highest-volume channel (14.4M delivery events/day, per the proposal's own figures) remains unspecified.

### 7. The P3 TTL and Maximum Queue Depth Are Announced but Never Specified

The executive summary states "P3 items now have a TTL and a maximum queue depth with explicit overflow behavior. The starvation trap is closed." Section 2.1 discusses the dequeuing weight model. No TTL value, no maximum queue depth figure, and no overflow behavior is specified anywhere in the visible document. The fix is announced in the summary and absent from the design.

### 8. The 30% DAU/MAU Ratio Is Asserted Without Basis

The traffic model uses 30% DAU/MAU as "typical for social apps." This ratio varies enormously across social products — from under 10% to over 50% — and is highly sensitive to product type, age, and user base composition. The proposal retracted the DAU denominator error in the email batching model precisely because passive users receive notifications. But the 30% DAU/MAU figure is still used to derive raw social actions/day (3M × 5 = 15M), which anchors the entire traffic model. If DAU/MAU is 20% instead of 30%, raw actions drop to 10M and the model shifts materially. No sensitivity analysis is provided.

### 9. The Token Invalidity Event Stream Ownership Split Creates an Unowned Gap

E2 "publishes structured events to `token.invalidated` stream" and "does not own downstream consumers." E3 owns the "feedback processor (consumes `token.invalidated` stream)." There is no owner for the stream itself — its retention policy, monitoring for consumer lag, dead-letter behavior, or what happens if E3's consumer falls behind. This is a coordination gap between two engineers with no named owner for the infrastructure connecting them.

### 10. The UUID v7 Constraint Enforcement Mechanism Is Insufficient

The proposal states that the cross-node ordering constraint for UUID v7 "is enforced in code review and documented in the architecture decision record." Code review is a manual, per-PR process. There is no automated enforcement — no static analysis rule, no runtime assertion, no test that would catch a component assuming cross-node ordering. For a constraint whose violation would cause silent correctness failures in log correlation and time-bucketing, relying solely on human review during code changes is not adequate enforcement.