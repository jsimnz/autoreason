## Problems Found

### Constraint Violations

**1. Word count likely exceeds 600 words.**
The document is substantially over 600 words. A rough count puts the body text (excluding the table formatting characters) at approximately 650–700 words. The "What We're Changing" section alone is verbose enough to push it over the limit, particularly the multi-sentence verification criteria for each item.

**2. Timeline contains editorializing.**
The constraint specifies "chronological, no editorializing." The entry "latency does not improve" is an editorial comment on the outcome of an action, not a neutral factual event. Similarly, "latency begins climbing" is interpretive framing rather than a logged observable event.

### Factual / Derivability Problems

**3. "3 hours and 21 minutes elapsed between first response and correct diagnosis" is stated in the Summary, but the math from the timeline is 3 hours and 21 minutes (14:31 to 17:52). That's consistent — but the base facts state "3 hours between first response and correct diagnosis." The document introduces the more precise figure "3 hours and 21 minutes" which is derivable from the timestamps, but the Summary treats it as a standalone fact when it is actually derived. More critically, this precision is added in the Summary section but the base facts only say "3 hours" — the document is adding specificity not directly given, which may or may not be acceptable depending on interpretation of "add nothing that isn't derivable."**

**4. The timeline omits when the migration script was deployed relative to other events.** The base facts do not specify the migration ran at exactly 14:23 — they say the outage window started at 14:23. The document asserts the migration ran at 14:23, conflating outage start with migration execution time. These are not guaranteed to be the same moment.

**5. "Most retried successfully within 2 hours of recovery" is in the Summary.** The base facts say "most retried successfully within 2 hours of recovery." The document reproduces this correctly. No problem here — flagged only to confirm it checks out.

### Remediation Item Problems

**6. Item 5 (tabletop exercise) is not falsifiable as written.**
The verification criterion is that a facilitator posts a written summary. This confirms the exercise was documented but does not confirm it was conducted with "the full on-call rotation" as specified. A summary could be posted without full attendance. The falsifiability requirement is only partially met.

**7. Item 3's verification criterion checks for a merged runbook but does not verify the escalation process is actually operational.** A runbook can be merged without the escalation mechanism being live or tested. The item claims to be falsifiable but the check only confirms documentation exists, not that the 30-minute trigger works.

**8. Item 2's verification criterion is internally inconsistent.** It requires the shadow environment to be "refreshed weekly at no less than 50% of current production data volume" as a standing operational requirement, but the verification criterion only checks a single sample migration run. A one-time passing run does not verify the "refreshed weekly" component of the commitment.

### Structural / Missing Elements

**9. No explicit acknowledgment of the on-call engineer's incorrect scaling action in "What Went Wrong."** The base facts identify this as a contributing factor to the diagnosis delay. The section addresses the wrong hypothesis but attributes it abstractly to the team; it does not identify the absence of query-level diagnostic steps in the initial responder runbook as a distinct failure, even though that is a specific and separate contributing factor from the senior engineer escalation gap.

**10. The "What We're Changing" section has five items but the constraint says nothing about number of items — however, Item 5 (tabletop exercise) does not directly address any of the three stated contributing factors from the base facts.** It is an addition not derivable from the base facts as a necessary corrective action, which may violate the "add nothing that isn't derivable" constraint.