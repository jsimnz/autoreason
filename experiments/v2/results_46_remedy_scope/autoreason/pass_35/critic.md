## Real Problems

### 1. The Fanout Cap Section Is Truncated

Section 1.1 ends mid-sentence: "Excess recipients are" — nothing follows. This is not a minor editorial issue. The fanout cap is listed as Decision 3 in the Unresolved Decisions table, with a fallback of "Option A — accept consistency gap," but Option A is never defined anywhere in the visible document. A reader cannot evaluate the fallback they are being asked to accept because the content describing it was cut off.

### 2. Section 7.1 Is Referenced Constantly But Never Shown

The document references Section 7.1 approximately 20 times for named owners, deadlines, authority, co-sign requirements, the runbook gate, engineering's answer on feed architecture, and the pre-flight checklist. None of that content is present. Every governance mechanism in this document — the entire accountability structure — bottoms out in a section that does not exist in this document. Readers cannot verify whether any named owner actually exists, whether deadlines are real, or whether the pre-flight checklist contains what the document claims it contains.

### 3. The Co-Sign Requirement Has No Enforcement Path

The document states that if the SMS budget owner and product owner disagree, "the more restrictive threshold applies until the disagreement is resolved in writing." It also states that if the SMS budget owner role is not filled, engineering deploys the conservative fallback. But the document also states explicitly that "engineering does not resolve organizational gaps." There is no mechanism described for what happens if the SMS budget owner role exists, is filled, but that person simply does not respond before the deadline. This is the most likely failure mode and it is unaddressed.

### 4. The Fallback Authority Framing Has an Internal Contradiction

The preface states that "engineering owns the fallback selection" and "product owners own the consequences of not deciding." But Decision 3 (fanout cap, Option A) and Decision 4 (deduplication window) have fallbacks with consequences that are explicitly architectural — consistency gaps and Redis capacity tradeoffs — not just product outcomes. Calling these "engineering constraints" while simultaneously saying the product owner "owns the consequences" misrepresents what is actually happening: engineering is making product-affecting choices and then assigning consequence ownership to someone who had no input into the choice.

### 5. The Deduplication Window Decision Is Contingent on an Engineering Question That Has No Deadline

The document states that engineering must answer whether the feed deduplicates at read time before framing Decision 4 as a product decision, and that this answer must be recorded in Section 7.1 before the pre-flight checklist closes. There is no deadline for engineering to answer this question, no owner named for answering it, and no fallback if engineering cannot answer it before the product owner's deadline. The product owner is being asked to make or accept a decision whose framing depends on an upstream answer that may not arrive in time.

### 6. The ±25% Uncertainty Acknowledgment Is Applied Inconsistently

The document states all peak rate figures carry ±25% uncertainty until month-1 recalibration. This uncertainty is acknowledged in the traffic model but does not appear to propagate into the infrastructure sizing branches in Section 6.1, the Redis sizing derivation, or the worker capacity analysis in Section 1.5. The document presents specific sizing numbers derived from figures that are admitted to be uncertain by ±25%, without stating whether the sizing includes margin for that uncertainty or assumes the plan figures are correct.

### 7. "Option A" and "Option B" for Fanout Are Phantom References

The Unresolved Decisions table refers to "Option A — accept consistency gap" and implies an Option B exists. Neither option is defined anywhere in the visible document. A decision table that lists fallbacks referencing undefined options gives reviewers no way to evaluate whether the fallback is acceptable.

### 8. The Runbook Gate Fallback Undermines the Stated Purpose of the Separation

The preface spends considerable effort explaining why the runbook must be separate from the design document, arguing that operators under incident conditions cannot afford to discover that section references no longer exist. Decision 6's fallback is that the on-call rotation owner can accept in writing the risk of operating without documented procedures. This directly contradicts the operational safety argument made in the preface — the document argues the runbook matters enough to separate it, then provides a named path to skip it entirely.

### 9. The Staffing Arithmetic Is Referenced But Not Present

The executive summary states that Section 1.5 contains the staffing arithmetic that derived the reduction from 16 to 6 worker deployments, and that "the arithmetic starts from a fixed budget of engineer-weeks." Section 1.5 is listed in the table of contents but its content is not shown. The executive summary's claim that architectural decisions follow from staffing bounds cannot be evaluated without seeing that arithmetic.

### 10. The Sensitivity Table Contains an Unlabeled Assumption Embedded in a Calculation Presented as Fact

The extreme scenario peak rate of ~9,643/sec is described as approximately 4.9× the plan row, and the document states "this is not a methodology error." But the peak multiplier of 3.0× in the extreme row is itself an assumption with no derivation or source. A 3.0× peak multiplier applied to a viral scenario may be conservative or may be a significant underestimate — viral traffic characteristically produces much higher multipliers. The document defends the arithmetic without acknowledging that the input to that arithmetic is unvalidated.