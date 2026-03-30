## Real Problems With This Proposal

### 1. The 17/day Ceiling Is Still Circular

The derivation multiplies benchmarks from Twitter/Instagram early-scale by tier weights that are themselves unvalidated, then applies a 1.7× multiplier justified partly by "model uncertainty from zero prior product data." The document acknowledges the weights can't be validated before the infrastructure decisions that depend on them, then uses the weights anyway to derive the ceiling. The phased procurement hedge doesn't fix this — Phase 1 sizing (60% of baseline) is still derived from the same unvalidatable number. If the baseline is wrong by the 15/35/50 scenario, Phase 1 is already undersized on day one of beta, not just at month 3.

### 2. The Sparsity Argument Cuts Both Ways and the Document Only Uses One Direction

The document correctly notes that week-2 cohort sparsity causes structural underestimation of steady-state rates. It uses this to discount readings at or below 17/day ("consistent with but doesn't confirm the ceiling"). But the same sparsity argument means a reading *above* 17/day during the sparse-graph phase is even more alarming than the document treats it — if sparse graphs already exceed the ceiling, the dense-graph steady state is substantially higher. The document treats above-ceiling readings as triggers for graduated response, but the sparsity-corrected interpretation of those readings should push the thresholds down, not leave them at 2×/5× multiples of an already-uncertain baseline.

### 3. The 48-Hour Technical Review Replaces One Bad Mechanism With an Underspecified One

The prior version's week-3 confirmatory measurement was correctly identified as too slow. The replacement — a 48-hour review that either "confirms the finding" or "identifies a specific documented artifact" — has no specified methodology for distinguishing a real signal from a real artifact. The document lists valid artifact types (viral event during measurement window, script error, anomalous content event) but doesn't specify what evidence is required to assert any of them. Under deadline pressure, "a viral event probably happened" is indistinguishable from a valid artifact claim. The review has no external validation requirement and is owned by the same people who have an incentive to find an artifact.

### 4. The Month-3 Revisit Assumes Beta Reaches 200–500K Users on Schedule

The decision criteria for month-3 tier weight measurement depend on "social graph density materially higher than week-2 cohort" — specifically, 200K+ users. The document states this is the target "if the beta ramp proceeds on schedule" without specifying what happens if it doesn't. If beta reaches only 80K users by month 3, the measurement has the same sparsity problem as week 2, and the entire month-3 decision framework produces unreliable data while the document treats it as a confirmed trigger for Phase 2 sizing decisions.

### 5. The Queue Equilibrium Analysis Is Cut Off Mid-Sentence

Section 1.2a ends with "= ~945K + (35" — the document is literally incomplete. This is the section that was specifically called out as containing an unacknowledged contradiction in the prior revision, and the correction is missing its conclusion. The document cannot be evaluated on whether the equilibrium analysis is correct because it isn't there. Every downstream claim about queue stability under the interim operating mode rests on an unfinished proof.

### 6. The "Acceptable During Beta" Judgment Is Unexamined

Section 1.2 states that delayed (not dropped) notifications during Scenario B events in beta "is acceptable during beta; it would not be acceptable at full launch." No basis is given for this. Beta users experiencing notification delays during a viral event may churn, may post publicly about the failure, or may be journalists or influencers whose experience shapes perception. The document treats beta as a consequence-free environment for infrastructure shortfalls, which is a business assumption dressed as a technical one, and it's never defended.

### 7. The Cost Estimate Is Underspecified in a Way That Hides Real Risk

The document estimates the Phase 1 vs. Phase 1+2 cost difference as "roughly $8–15K/month depending on exact configuration." This range is a 2× spread, which at 6 months is a $48–90K swing — nearly double the lower bound. For a 4-engineer team on a 6-month budget, this uncertainty matters. More importantly, the estimate covers only managed service costs and ignores engineer-time cost of the month-3 revisit, the 48-hour review process, the coordinated capacity review triggered by DAU/MAU crossing 30%, and the week-1 load test. The "option value" argument for phased procurement implicitly assumes the alternative cost (engineering time for repeated capacity reviews) is zero.

### 8. The LIFO Behavior Fix Is Defined by a Threshold That Isn't Specified

Section 2.2 is referenced as specifying "the queue depth threshold above which LIFO behavior produces unacceptable P1 delivery latency." That section isn't included in this document. The revision notes claim this problem is addressed, but the actual threshold, the actual mitigation, and the actual definition of "unacceptable P1 delivery latency" are all absent from the visible text. The revision note is doing work that the document body isn't.

### 9. The DAU/MAU Trigger Condition Has an Unexamined Dependency

The document specifies that E1 monitors a 7-day rolling DAU/MAU average and triggers a coordinated capacity review if it crosses 30% for three consecutive days. It then notes "the specific threshold should be confirmed with E1 against observed day-of-week variance during beta." This means the trigger condition for a critical capacity review is itself unvalidated at the time the document is written. If day-of-week variance is large enough that 30% is routinely crossed and uncrossed, the three-consecutive-day rule will either fire constantly or fail to fire when it should — and the document acknowledges this without treating it as a problem requiring resolution before deployment.

### 10. Section 7 Is Referenced but Not Included

The executive summary states "Section 7 is now present. It names specifically what is cut from the operational surface, which engineer owns what, and what the on-call structure looks like." Section 7 does not appear in the document. Multiple other sections ground their assumptions against "this staffing reality" — the >5× review is owned by "E1 + lead," the month-3 revisit has a specified decision owner, the DAU/MAU trigger assigns work to E1 — but the staffing model those assignments depend on is missing. The revision explicitly identified the absence of Section 7 as a problem in the prior version. It remains absent.