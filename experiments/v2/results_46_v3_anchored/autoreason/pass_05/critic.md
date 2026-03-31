Here are real problems with this proposal:

**1. The peak/sec calculation is wrong or unexplained.**
The table shows 1,300/sec for the planning basis (41.1M/day). But 41.1M/day ÷ 86,400 sec/day = ~476/sec average. Even applying the 3× peak multiplier gives ~1,430/sec, not 1,300/sec. The document never explains how peak/sec is derived from daily volume, and the numbers don't reconcile. The sizing target of 2,500/sec is therefore unanchored.

**2. The sensitivity matrix mixes daily averages and peaks incoherently.**
The "Peak/sec" column appears to be calculated from peak daily volume (after 3× multiplier), but the document doesn't state this. If peak volume is 112.5M push+in-app events, that's 112.5M/day ÷ 86,400 = ~1,302/sec — which matches the table only if the peak is sustained for a full 24 hours. That's not what a peak is. The column is meaningless without specifying the peak window duration (1 hour? 15 minutes?).

**3. The SMS volume estimate is never justified.**
75K SMS/day appears in every row of the sensitivity matrix regardless of DAU. The document claims SMS is event-triggered by login events, but login event volume scales with DAU. A 35% DAU scenario (3.5M DAU) would not produce the same SMS volume as a 15% DAU scenario (1.5M DAU). This inconsistency undermines the cost modeling the document relies on to justify the isolated SMS queue.

**4. The $3,375 SMS cost figure is presented as a deterrent but not evaluated.**
The document mentions a $3,375 single-period Twilio cost from a login spike as if it's alarming, then immediately moves on. It never states what "single period" means, whether that cost is acceptable, or how it compares to the SMS budget being sought. This number is doing rhetorical work without analytical support.

**5. The preference cache section documents an unfixed race condition and then proceeds anyway.**
The document explicitly describes a scenario where stale data gets re-cached with a fresh TTL after invalidation, calls it "a structural property we cannot fix," and then continues to use the cache design. There is no discussion of the business impact of delivering notifications to users who have opted out — which is a legal and trust problem, not just a consistency inconvenience. The document treats this as an honest acknowledgment when it's actually an unresolved correctness problem.

**6. The replica lag problem in cache population is acknowledged and then ignored.**
The document notes that cold cache reads under write pressure will populate from a lagged replica, bypassing version fencing entirely. It describes this as "the most vulnerable moment." It then ends the section mid-sentence (the document is cut off), with no mitigation, acceptance criteria, or measurement plan for how often this actually occurs.

**7. The 92% headroom claim is misleading.**
Sizing for 2,500/sec against a planning basis of 1,300/sec is described as "92% headroom." But headroom should be measured against the peak case being planned for, not the average. If the 35%/15 scenario produces 1,820/sec peak, the headroom against that scenario is 37%, not 92%. The framing inflates the apparent safety margin.

**8. The Month 2 escalation path contradicts itself.**
The document corrects the previous version's "architectural review in 48 hours" framing and replaces it with "a capacity decision, not an architectural one." But then it lists "scope reduction in Month 3 to absorb the operational load" as a response — which is a project scope decision requiring stakeholder sign-off, not something four engineers can resolve in 48 hours. The corrected framing is still incomplete.

**9. E3 has no representation in the ownership table for cross-cutting components.**
E3 owns preference management and suppression logic, but appears nowhere in the ownership table for cross-cutting components. Suppression logic directly affects what enters the queues. The ownership boundary between E3's suppression decisions and E1's queue implementation is undefined.

**10. The "one engineer-day to set up four queues" estimate is not credible in context.**
The document claims four queues, four DLQs, and four sets of alerting rules take approximately one engineer-day. The same document then dedicates substantial space to DLQ triage ownership, retry logic, circuit breakers, and backpressure — all of which are non-trivial. The one-day figure appears to be justifying the architectural choice rather than estimating actual work.