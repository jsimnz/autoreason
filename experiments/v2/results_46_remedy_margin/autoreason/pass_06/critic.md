Here are the real problems with this proposal:

## Architectural Problems

**The separate queue guarantee is overstated.** The document claims P0 latency is guaranteed because separate queues prevent P2 workers from blocking P0. But all three queues share the same Redis instance. Under memory pressure, eviction or latency spikes affect all queues simultaneously. The architectural isolation claim doesn't survive the shared infrastructure reality.

**In-app bypasses the queue with no ordering solution.** The document acknowledges "ordering behavior described in Section 2.6" but Section 2.6 is cut off. A direct PostgreSQL write for in-app while related push notifications go through a queue means a user can see a push for an event before the in-app notification exists. This is a real user-facing correctness problem that's deferred to a section that doesn't appear in this document.

**The coordination record design is never explained.** "Coordination record creation (for multi-channel events)" appears in the router description and nowhere else. For a system sending 50M notifications/day across 4 channels, deduplication and multi-channel coordination is a core problem. The document names it and drops it.

**Redis List semantics create a silent ordering problem.** LPUSH/BRPOP gives LIFO behavior. Under queue accumulation during a spike, older notifications are served last. The document discusses queue depth and drain time extensively but never acknowledges that during a 24-minute post-event drain, the oldest notifications are delivered last. For time-sensitive social notifications this inverts the desired behavior.

## Quantitative Problems

**The 350/sec per worker figure for P1 is asserted, not derived.** Section 2.3 is referenced repeatedly as containing the derivation, but the document states "derived Section 2.3" without that section being present or the derivation being shown. The entire spike math — 30 workers, 10,500/sec capacity, the 20% headroom claim, the 24-minute drain calculation — rests on this unshown number.

**The bias correction methodology has a structural flaw.** Applying fixed population tier weights (5/35/60) to cohort measurements assumes the notification rate within each tier is stable across cohort and population. If power users in the general population generate fewer notifications than power users in the early adopter cohort — which is plausible since early adopters are exploring a new product — the correction is incomplete. The document treats tier reweighting as removing systematic bias when it only removes one component of it.

**The 30% DAU/MAU ratio is load-bearing and unexamined.** The entire scale model depends on this figure. A 25% ratio reduces total notifications by 17% and changes worker sizing. A 35% ratio increases load proportionally. For a new social app without historical data, this ratio has substantial uncertainty that is never quantified, yet it's listed as a simple given in the table.

## Operational Problems

**E4 has no slack and owns the reconciliation job that the whole system depends on.** The reconciliation job (Section 2.5, also not shown) is presumably what catches delivery failures and ensures consistency. E4 builds it in month 2 with zero buffer. If E4 is sick, on leave, or encounters unexpected complexity, the job that ensures delivery correctness slips. This is a single-point-of-human-failure that the on-call rotation note doesn't address.

**The overflow valve designation is circular.** The document names the analytics dashboard as the thing that gets dropped if E4 is overwhelmed. But E4's month 4-5 work is "ongoing monitoring, performance investigation, capacity planning" — not analytics. If query performance becomes a crisis in month 4, dropping the analytics dashboard doesn't free up E4's time; E4 is already doing monitoring work. The overflow valve doesn't actually relieve the constrained resource.

**Manual scaling in 3 minutes is not tested until month 5.** The spike response depends on adding 10 workers in ~3 minutes. The runbook exists but the first live test of this capability is the month-5 load test. For the first 4+ months of operation, the manual scaling response time is an assumption.

**The SMS budget gate has a silent failure mode that's described as acceptable.** When the budget cap is hit, users stop receiving authentication codes. The document notes this and says users get a push notification instead. But users who need an SMS authentication code typically need it because they're logging in — meaning they may not have an active session to receive a push notification. The fallback doesn't work for the most critical use case.

## Process and Decision Problems

**The month-3 milestone is used as a deadline for two separate unresolved business decisions.** Both the 10× sizing decision and the SMS geographic strategy decision are deferred to "before month-3." Month 3 is when the multi-channel system is being built. Arriving at month 3 with both decisions unresolved means engineering is building against unknown requirements, not a contingency.

**The >5× contingency honestly describes a 5-7 month rebuild that exceeds the project timeline, but the week-2 gate still only gives 1-2 weeks to decide.** If the corrected estimate comes back at >5× in week 2, the document says the realistic response takes longer than the remaining project. But the decision window is 1-2 weeks. There's no described path between "we have 1-2 weeks to decide" and "this takes 5-7 months to fix." The gap is acknowledged but not resolved.

**The beta cohort bias correction requires segmenting 50K users into behavioral tiers in the first two weeks of instrumentation.** Tier classification requires enough behavioral data to distinguish power users from passive users. Two weeks of data from a 50K cohort, during which users are still discovering the product, is unlikely to produce stable tier assignments. The methodology assumes the measurement is reliable before that's been established.