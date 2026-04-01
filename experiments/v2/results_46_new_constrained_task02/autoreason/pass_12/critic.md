## Problems Found

### Constraint Violations

**Word count:** The document exceeds 600 words. The body text alone (excluding the table formatting characters and header syntax) runs approximately 620–640 words depending on how table rows are counted. This is a direct constraint violation.

**Timeline editorializes by omission with a structural implication problem:** The constraint says "no editorializing" in the timeline, but the timeline silently collapses the 3-hour 21-minute gap between 14:31 and 17:52 into nothing. The base facts explicitly state the team assumed it was a traffic spike due to Black Friday proximity — this is a factual event (a diagnostic decision was made) that occurred in the timeline window and is omitted entirely. The constraint says to use ALL base facts; the Black Friday misdiagnosis reasoning does not appear in the timeline and appears only nowhere in the document at all. It is mentioned in "What Went Wrong" only implicitly via "wrong hypothesis" — but the specific Black Friday reasoning, which is a provided base fact, is never stated anywhere.

### Missing Required Elements

**The Black Friday contributing factor is absent.** The base facts state: "the team initially assumed it was a traffic spike (Black Friday was 2 days away)." This specific causal reasoning for the 3-hour delay is a provided fact the document is required to use. The document says "wrong hypothesis" and "no escalation threshold" but never states the team diagnosed a traffic spike or that Black Friday proximity drove that assumption. This is a direct violation of "use ALL of these."

**The timeline is missing the wrong-diagnosis action's consequence.** The base facts state scaling replicas "did not help." The timeline entry at 14:31 records the action but not the outcome (did not help). The outcome is a base fact and is absent from the timeline.

### Factual Accuracy Issues

**"Index rebuild complete" at 18:41 is not supported by the base facts.** The base facts say "latency recovered by 18:41" — not that the rebuild completed at that moment. These are potentially different events (the index could have been rebuilt earlier with recovery lagging, or the rebuild could have been ongoing). The document conflates them in a single timeline entry, asserting completion at 18:41 when the source fact only confirms recovery at 18:41.

**The summary says "Correct diagnosis did not occur until 3 hours after first response."** First response was 14:31; diagnosis was 17:52. That is 3 hours and 21 minutes, not "3 hours." The base fact says "3 hours between first response and correct diagnosis" but the actual numbers in the document contradict this when calculated from the document's own timeline.

### Remediation Item Issues

**"Production-scale shadow database at no less than 50% of production data volume" is not derivable from the base facts.** The base facts state staging had 1/1000th the data volume. The 50% figure is invented — it appears nowhere in the provided facts. The constraint says "add nothing that isn't derivable from them." This is a fabricated specification.

**December 22 deadline for the shadow database** is similarly invented with no basis in the provided facts. While deadlines must be assigned, the specific date introduces fabricated content beyond what is derivable.

### Minor Structural Issue

**The "What We're Changing" verification sentences are written in italic inside the action items.** The constraint specifies the structure must follow Summary / Timeline / Root Cause / What Went Wrong / What We're Changing — it does not accommodate a sub-element called "Verified when…" within each item. These italic lines are not part of the specified structure and constitute added elements not required by the constraints.