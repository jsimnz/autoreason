## Real Problems with This Proposal

### 1. The 30% DAU/MAU Ratio Is Treated as Validation, Not Assumption
The document uses "industry average" for DAU/MAU without acknowledging that social apps vary enormously — 30% is reasonable for mature Western social apps but could be 15% or 60% depending on the product. The proposal correctly flags the 17 notifications/user/day figure but accepts the DAU figure itself without equivalent skepticism. Both numbers compound into the 50M estimate.

### 2. The Active Concurrency Correction Is Mathematically Inconsistent
The proposal applies a 20% concurrent activity factor to in-app delivery (reducing demand) but does not apply the same logic to push. It argues push serves "offline or background users" and uses 2.4M/3M as the adjustment. But background users still receive push — the 70% push allocation in the traffic model already represents the full DAU, not just offline users. The channel split percentages and the concurrent-user correction are being applied to the same population twice, which means the push demand figure is understated, not corrected.

### 3. Deduplication Key Memory Estimate Is Wrong by an Order of Magnitude
The proposal estimates 50M deduplication keys at 5-minute TTL means "~1.5GB active at any time." But 50M notifications/day at 5-minute TTL means only 50M × (5/1440) ≈ 174K keys active simultaneously — roughly 8.7MB, not 1.5GB. The figure appears to assume all daily keys are simultaneously active, which contradicts the stated TTL. This error does not affect the final hardware selection (128GB has headroom regardless) but undermines confidence in the sizing methodology.

### 4. The FCM Headroom Figure Is Nonsensical
14,000/sec capacity against ~972/sec demand is 14× headroom — the proposal flags this as acceptable. But 7 workers at 2,000/sec each means FCM workers are running at roughly 7% utilization during peak. This is not a tradeoff being named; it's a provisioning error that the document presents as a feature. The worker matrix does not explain why FCM needs 7 workers when 1 would handle peak demand with margin.

### 5. P0 Email Absence Is Justified by Latency but the Reasoning Has a Gap
The proposal correctly excludes email from P0 because of delivery latency. But OTP SMS is in P0, and the fallback path (email OTP) routes through the email channel when SMS exceeds 500K/day. The fallback therefore delivers OTP through a non-P0 channel. The proposal does not address what priority queue the email OTP fallback uses, meaning the security-critical path has an unexamined priority hole.

### 6. The SMS Annual Cost Estimate Appears Miscalculated
OTP baseline: 150K/day × 365 × $0.012 = $657K. The document rounds this to $660K — fine. But "OTP spike reserve (3 days/year at 10×)" is listed as $54K/year. 150K × 10 × 3 × $0.012 = $54K. This is correct in isolation but the table presents it as an annual cost line item alongside daily-rate items, mixing daily-normalized costs with total-event costs in a way that makes the annual total misleading. The $1.2–1.4M/year total cannot be derived from the table as presented.

### 7. The Circuit Breaker Threshold Contradicts the Budget Table
The automatic email OTP fallback triggers at 500K SMS/day. But the budget table shows OTP baseline at 150K/day and social/digest capped at 100K/day, with a total baseline of 270K–370K/day. The 500K trigger is above the stated total daily budget ceiling, meaning the circuit breaker only activates after the system has already exceeded its own budget. The control fires too late relative to the numbers in the same document.

### 8. WebSocket Sequence Numbers Are "Designed" but Section 5 Is Not Present
The executive summary claims "WebSocket sequence numbers are designed, not deferred — reconnect catch-up logic is specified in Section 5." The document ends mid-sentence after Section 2. Section 5 does not exist in the submitted proposal. This is the most direct internal contradiction in the document.

### 9. The Worker Matrix Has Unexplained Zeroes That Create Priority Gaps
P0 has 0 email workers and 0 in-app workers. P3 has 0 FCM, APNs, and SMS workers. The proposal explains the P0 email absence but does not explain why in-app notifications have no P0 path (a security alert displayed in-app would seem to warrant one), nor why P3 has no push path (bulk notifications presumably need some push delivery). These zeroes may be intentional but are not justified.

### 10. E3's WebSocket Scope Is Assigned to Months 3–4 but Depends on Infrastructure Not Built Until Then
E3 builds the WebSocket fanout with sequence numbers in months 3–4, but the in-app store schema and preference API are built in months 1–2. The fanout implementation depends on E4's failure handling and DLQ work, also scheduled for months 3–4. Two engineers with interdependent deliverables in the same two-month window, with no slack, is a scheduling risk the proposal does not acknowledge.

### 11. "Managed Infrastructure Throughout" Does Not Eliminate Operational Complexity
The proposal presents managed services as a solution to team-size constraints. ElastiCache Multi-AZ, RDS Multi-AZ, and ECS with Fargate still require configuration, failover testing, parameter group tuning, and incident response. The proposal assigns all of this to E4 alongside CI/CD, alerting, chaos testing, and the feedback processor data model. The managed-service framing obscures that E4's scope is the largest and least bounded on the team.