Here are the real problems with this proposal:

## Structural / Self-Referential Problems

**The document validates itself.** The introduction says "If you find a reference to a section that does not exist, that is a defect." But the reviewer cannot know which sections exist until they read the entire document, which is not provided here. The self-completeness claim is unverifiable from what's been shared.

**The escalation chain has a logical flaw it acknowledges but doesn't resolve.** The document identifies the symmetric accountability problem (engineering lead can't trigger escalation if engineering lead caused the failure) and adds a named backup. But the named backup has the same structural problem — if organizational failure caused both the lead and the on-call owner to miss the review, the same organizational failure likely affects the backup. The solution assumes individual failure, not systemic failure.

**Section 7.2 is referenced repeatedly but not present.** "Section 7.2 applies" appears multiple times as the resolution for unavailability of the engineering lead, scale-down authorization, and escalation events. The document cannot be self-contained if this section is absent.

## Technical Problems

**The correlated sensitivity table doesn't match the stated methodology.** The document says high-engagement rows use higher multipliers "because more real-time interaction compresses activity into shorter windows." But the extreme row (65% DAU/MAU, 25 notif/user) produces 162M/day at 4× = ~7,500/sec. The plan row is 45M at 3×. The jump from plan to extreme is 3.6× in daily volume but only 4.75× in peak rate — implying the multiplier scaling doesn't actually capture the claimed compression effect. The math is internally inconsistent with the stated rationale.

**The deduplication design has an unresolved interaction.** Section 1.1 mentions "the interaction between the sliding window and the cross-channel delivered-ID set" and refers to Section 2.2 for the arithmetic. But the 60-second sliding window for per-user deduplication and a cross-channel delivered-ID set are architecturally different mechanisms with different purposes. The document never explains what happens when a notification is deduplicated by the sliding window but not by the cross-channel set, or vice versa. This is a correctness gap, not just a documentation gap.

**The power-user rate limiting is inconsistent with the volume model.** The sustained rate limit is 20 notifications/hour for power users. That's 480/day. But the "extreme" scenario uses 25 notifications/day as the per-user average. These figures don't interact — the rate limit applies per-user, the volume model uses population averages — but the document presents both without acknowledging that a 20/hour limit makes the 25/day average trivially achievable and provides essentially no protection against the power-user stress case it's meant to address.

**The fanout cap creates an unacknowledged ordering problem.** The 5-minute batched processing window for recipients beyond 10,000 is described as a consistency issue (some users see the notification before others). But it's also a queue priority problem: the batched fanout jobs compete with organic P0–P3 traffic. The document doesn't specify what priority batched fanout jobs receive, which means under sustained high load, the 5-minute window is not actually bounded — it expands indefinitely.

**FCM rate limits are described as "not contractually specified" but the architecture depends on them.** The claim that "the binding constraint during viral spikes is FCM/APNs rate limits, not Redis throughput" is presented as a key architectural justification. If FCM rate limits aren't contractually specified and the pre-launch verification in Section 1.4 hasn't been completed, this architectural claim has no foundation. The system could be correctly sized for Redis and completely wrong for FCM.

**The Redis sorted set for processing state has an unspecified recovery window.** The document says crash recovery reclaims orphaned entries "within a bounded window" but the bound is never stated in the visible text. The Section 6.2 reference covers in-flight behavior during promotion, but orphaned entry recovery is a different failure mode. "Bounded" without a value is not a guarantee.

## Operational Problems

**The month-1 traffic-conditional response table is truncated.** The last row of the table cuts off mid-cell: "Engineering lead review within" — the escalation condition for the < 30M/day row is incomplete. This is a defect in a section explicitly designated as incident-ready.

**The CLI commands assume label stability that isn't guaranteed.** The dashboard fallback commands use label selectors like `channel=push,tier=high`. These labels are set at deployment time and could drift if deployments are recreated, renamed, or if the label schema changes during the 6-month build. The document's own warning ("Verify deployment names before touching anything") acknowledges this risk but the CLI commands don't include any verification step before the scaling commands.

**The pre-flight check blocking mechanism is described but not defined.** The document says placeholder text in three named fields "causes the pre-flight check (defined in Section 7.1) to return a non-zero exit code, blocking the deployment pipeline." This implies tooling exists or will exist to parse Section 7.1 and enforce this. That tooling is never described, its implementation is not scoped, and it's not clear whether it exists at writing time or is aspirational.

**The named backup's authority is "time-triggered, not permission-triggered" but this is unenforceable.** The document grants the backup unilateral authority on day 34. In practice, executing `kubectl scale` commands on production infrastructure without organizational authorization is a personnel and security policy question, not just a runbook question. Declaring authority in a design document doesn't grant it.

## Scope and Staffing Problems

**The staffing analysis is referenced as justification but its conclusions are not checkable.** Multiple decisions are justified by "the staffing analysis in Section 1.5." The reduction from 16 to 6 worker deployments is the most significant. But the visible text never shows the analysis — only its conclusion. A reader cannot evaluate whether the tradeoff is correct.

**The 6-month timeline has no milestone structure.** The document mentions HPA deployment and validation happening in month 2, and the month-1 checkpoint, but there's no visible schedule for when the other components are built, tested, or deployed. For a 4-engineer team, sequencing is a real constraint — if Redis provisioning isn't resolved before workers are built, or if the FCM rate verification requires production traffic, the timeline dependencies could be blocking.

**The four [PRODUCT DECISION REQUIRED] items have deadlines recorded in Section 7.1** — a section not shown. This means all four deployment gates have unknown deadlines. If any of those deadlines have already passed or are set after the planned launch date, the deployment checklist gates are either already failed or meaningless.