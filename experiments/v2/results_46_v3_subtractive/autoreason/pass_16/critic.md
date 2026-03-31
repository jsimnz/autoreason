Here are real problems with this proposal:

**1. The 1.05 fanout multiplier explanation is circular and unfalsifiable.**
The document says the multiplier "accounts for actions that notify slightly more than one person on average" and that high-follower users are removed. But it never shows the math. What fraction of users are high-follower? What is their average follower count? What is the remaining population's actual distribution? Without this, the 1.05 figure cannot be validated, and the claim that the previous 1.2 was wrong cannot be verified either. The correction is asserted, not demonstrated.

**2. The DAU trigger condition (35% for two consecutive weeks) has no enforcement mechanism.**
The document says the trigger condition is measured "in the analytics dashboard," but no one is named as responsible for monitoring it, no alerting is specified, and no escalation path exists if it is missed. Given that the scaling operations take two weeks, a missed trigger means the system is already under-provisioned before work begins.

**3. The email worker arithmetic is internally inconsistent.**
The document calculates that at a 30-minute window, processing time per worker is ~1,953 seconds against an available window of 1,800 seconds — a ratio of 1.08 — and then concludes that "4 workers" leaves ~1,310 seconds of margin. This does not follow. If one worker's share takes 1,953 seconds, four workers sharing the load still take 1,953 seconds unless work is parallelized across emails, which is not stated. The margin calculation appears to conflate per-worker load with total pool throughput without stating the parallelism model.

**4. The TCPA residual risk is escalated but the escalation has no resolution.**
The document says the simultaneous unavailability of E1 and E3 is "named, quantified, and escalated to a business decision." But no quantification appears in this excerpt, no business decision is recorded, and no owner is named. Escalation without a recorded decision is not risk closure — it is risk deferral with documentation.

**5. The SMS volume assumption is load-bearing but unexamined.**
1,500 SMS/day is derived from "<0.01% of 8M users." That is a floor, not a measured figure. For a new app, SMS opt-in rates could be higher during launch promotions or if SMS is used for account verification flows that inadvertently create marketing consent. The document dismisses SMS as negligible without examining whether the opt-in rate assumption holds at launch.

**6. The in-app channel being non-disableable is stated as a constraint but not justified.**
The document says "in-app is not disableable at the channel level" as an architectural fact. This has product and potentially legal consequences — some jurisdictions require users to be able to suppress all non-transactional notifications. The document does not examine whether this constraint is legally acceptable or whether it was a deliberate product decision versus an implementation shortcut.

**7. The SES p95 latency alert threshold is arbitrary.**
E4 is told to page if SES p95 exceeds 200ms sustained for 5 minutes. But the processing time calculation uses 150ms per email as the ceiling. If p95 reaches 201ms, the alert fires, but processing is already over budget at p95. The alert threshold and the capacity model are not aligned.

**8. Actions-per-DAU sensitivity is one-directional.**
The document flags that if actions-per-DAU exceeds 8, the traffic model must be recalculated. But the baseline assumption is 5 actions/DAU with no lower bound sensitivity. If engagement is lower than expected, the provisioned infrastructure is over-built, which is a cost concern worth at least acknowledging, particularly given the 6-month timeline.

**9. The "two weeks of E1 and E4 time" scaling estimate has no basis.**
The optimistic volume scaling operations are described as "execution work, not design work" requiring approximately two weeks. No breakdown is given. Given that the scaling requires recounting worker pools, re-deriving rate limits, revalidating SLAs, and validating queue infrastructure, two weeks is a specific claim that should have a task-level basis, especially for a 4-engineer team where two engineers being consumed for two weeks is a significant resource event.

**10. UUID v7 ordering enforcement via CI static analysis is not described.**
The document says UUID v7 cross-node ordering assumptions are "enforced via CI static analysis rule," which is a strong claim. Static analysis can catch explicit comparisons of UUID fields, but it cannot catch semantic ordering assumptions embedded in query logic, sort keys, or cache invalidation strategies. The enforcement claim overstates what static analysis can guarantee.