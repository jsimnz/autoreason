Here are the real problems:

**1. The spike multiplier is applied to already-concentrated peak, then the design claims it doesn't need to handle that load.** The document calculates 9,624/sec for a Type 2 spike, then sizes the ceiling at 2,650/sec, then says tiered degradation is "the designed response, not a failure mode." This is circular reasoning dressed as architecture. The taxonomy of spike types is borrowed from Twitter-scale events applied to a 10M MAU app with no justification that these multipliers are appropriate at this scale.

**2. The 90% concentration in a 4-hour window is asserted without basis.** This single assumption drives all peak rate calculations. If concentration is 95% or the window is 3 hours instead of 4, the numbers change substantially. The document acknowledges uncertainty in densification rates but treats the concentration assumption as fixed.

**3. Default B activates "automatically" but the mechanism is never specified.** The document says "poll interval configuration" but does not explain what system changes the poll interval, how it detects the 3,800/sec threshold, or what happens if the detection mechanism itself is under load. This is a critical path for Tier 3 users and it's described at the level of a note.

**4. The 11/DAU/day planning basis is not derived.** The raw event range is 7.5–23/DAU/day. The document says batching reduces this to 8–14/DAU/day and then selects 11 as the midpoint. But the batching reduction is not modeled — it is assumed. Whether batching actually achieves a 30–50% reduction depends on implementation decisions not yet made.

**5. The densification alert formula contains an unexplained second condition.** The alert fires only when `current_peak_rate > 1,800/sec`. There is no explanation for why 1,800 is the threshold or what happens if densification is rapid but current load is below 1,800/sec. A fast-growing but currently low-traffic system could miss the alert entirely.

**6. The compliance architecture section describes the risk as "1–2 engineer-weeks of rework" but the engineer-week budget is already described as tight.** The document says the self-hosted email fallback and option (b) batching changes "break the budget" and trigger stakeholder conversations. A third budget-breaking scenario (compliance rework) is mentioned inline without being added to the risk register or the sign-off table consequences.

**7. The document is cut off mid-sentence.** Section 1.1 ends with "The problem this section must solve: The reassessment trigger must fire early enough that capacity can be" — nothing follows. This is not a minor editorial issue; lead time analysis is identified earlier as a structural problem requiring mitigation, and the mitigation is incomplete.

**8. Four engineers for six months is 96 engineer-weeks, but no individual engineer's allocation is shown.** E1 is assigned to implement every compliance path, every channel dispatch path, and schema work. The aggregate budget claim ("fits within 96 engineer-weeks") cannot be verified without per-engineer breakdown, and the document does not provide one.

**9. The Type 4 spike response is "Tier 1 only; all else queued" but no queue bound is specified.** During an 8× spike of 1–6 hours duration, Tier 2 and Tier 3 queues grow unboundedly. The document does not state maximum queue depth, what happens when it is reached, or how backpressure is communicated to upstream producers.

**10. SendGrid enterprise contract is listed as required before launch with an end-of-Month-1 deadline, but the self-hosted fallback is described as having its own cost and timeline in §6.2.** Section 6.2 is not included in this document. A decision with explicit budget consequences references a section that does not exist here.