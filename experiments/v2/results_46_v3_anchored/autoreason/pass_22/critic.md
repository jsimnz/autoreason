## Real Problems with This Proposal

### 1. The Sign-Off Table Has a Circular Dependency That Isn't Acknowledged

The opt-out compliance architecture sign-off is due "End of Week 2" and schema work begins Week 3. But the queue depth bounds / DM drop policy sign-off is due "End of Month 1" — and DM drop policy explicitly requires Legal input. These two items are not independent: the correct handling of DMs under the opt-out architecture directly affects whether DMs can be dropped at all. Legal may need to evaluate both simultaneously, but the deadlines are five weeks apart. If Legal's Month 1 answer changes the correctness requirements, the Week 3 schema work is potentially invalidated. This dependency is not documented anywhere.

### 2. The Document Is Cut Off Mid-Sentence

Section 1.1 ends abruptly: "If the process fails for 90 seconds" — the sentence is incomplete. This is a proposal being submitted for sign-off. The failure mode specification for the metrics process is literally unfinished. Given that correcting the inverted failure mode was one of the eleven stated improvements from Revision 1, leaving it incomplete is a significant problem. Reviewers are being asked to sign off on behavior that isn't specified.

### 3. The Combined Sensitivity Finding Has No Corresponding Infrastructure Response

The proposal identifies that a 14/DAU rate with a 3-hour concentration window produces 4,083/sec — "inside Default B territory from launch" and "plausible, not extreme." It then says "the infrastructure sizing must account for it as a realistic outcome." But no infrastructure change follows. The worker ceiling, Redis sizing, and connection pool specifications are all built on the 11/DAU baseline. The proposal identifies a realistic scenario that breaks the design and then does not change the design.

### 4. The International Load Case Analysis Is Deferred to Sections That Don't Appear in This Document

The proposal states that Redis memory sizing "uses the sustained load case" (§5) and connection pool sizing "uses continuous operation assumptions" (§6). Neither section appears in this document. Reviewers are told the international case has been handled, but the handling is in sections they cannot read. This is an assertion of correctness, not a demonstration of it.

### 5. Default B Threshold Calibration Is Proposed After Launch, Not Before

The proposal acknowledges that Type 1 spikes — the most common spike type — routinely exceed the Default B threshold, and suggests the threshold "may need to be raised" after the first month of production data. This means the system will spend its first month in a mode that triggers stakeholder notifications (even if reframed as routine), potentially suspending Tier 3 delivery, based on a threshold the team already knows is probably wrong. The calibration exercise is deferred to after the system is in production with real users.

### 6. The Producer Registry Sign-Off Consequence Is Understated

The sign-off table states the consequence of missing the producer registry deadline is "429 responses produce invisible data loss for non-compliant producers." But the proposal also specifies that the enforcement mechanism is owned by E4, and E4's workload is elsewhere committed (broadcast rate limiting, which is also gated on a sign-off). If both sign-offs are late, E4 has two unsequenced implementation dependencies. The interaction between these two E4 items is not analyzed.

### 7. The Workload Reassignment Claims Are Not Verifiable

The change log states "three items reassigned" from E1 and that "where E1 is listed, the workload is accounted for in §1.3." Section 1.3 is referenced but does not appear in this document. The claim that the E1 overloading problem from Revision 1 is resolved cannot be evaluated by a reviewer of this document.

### 8. The Staggered Restart Jitter Analysis Is Incomplete

The thundering herd fix specifies a 30-second jitter window and 50% rate for 5 minutes, but does not specify how many Tier 3 workers there are. The claim that this "distributes wakeup events across a 30-second window" is only meaningful relative to worker count. With a large number of workers, a 30-second window may still produce significant clustering. The analysis asserts the fix works without providing the worker count that would allow that assertion to be evaluated.

### 9. The Monitoring Response Threshold for Per-DAU Rate Has No Owner

The proposal states: "if the 30-day rolling average exceeds 13/DAU, the worker ceiling requires reassessment." This is a defined measurement with a defined response threshold, but no owner is named, no section is referenced for what "reassessment" entails, and no timeline is specified for how quickly the reassessment must complete after the threshold is crossed. Given that 14/DAU produces Default A from launch, a slow reassessment process could mean weeks of misconfigured operation.

### 10. "Correctness Choice, Not Performance Choice" Is Asserted But Not Explained for Legal

The opt-out compliance item tells Legal they "must evaluate both architectures on correctness grounds." But the proposal does not describe what the correctness difference actually is in terms Legal can evaluate — it only names it. Legal is being asked to make a correctness determination about synchronous vs. cached opt-out enforcement without being given the failure scenarios (e.g., what happens to a notification sent in the window between a user opting out and the cache invalidating). The sign-off request is not self-contained.