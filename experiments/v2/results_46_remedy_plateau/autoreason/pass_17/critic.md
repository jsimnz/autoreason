## Real Problems

### 1. Internal Numerical Contradiction Left Unresolved

The executive summary table states worker capacity range as "2,200–4,400/sec" but §1.2 explicitly corrects this to 1,300–3,500/sec and labels the original figure wrong. The document acknowledges the contradiction but does not actually fix the executive summary table. A reader who stops at the summary has wrong numbers. The correction is buried in a subordinate clause mid-paragraph.

### 2. The Planning Figure Is Inconsistent With Its Own Justification

§1.2 states the planning figure of 30/sec per worker is "conservative" and sits "closer to the p75 latency estimate," then immediately notes it "sits in the upper third" of the derived range. These are contradictory characterizations. A figure in the upper third of a range is not conservative — it is optimistic. The document does not reconcile this. The spike analysis that follows depends on which characterization is correct.

### 3. Email Volume Construction Is Circular and Unexplained

The derivation states "~6.3 events/day per eligible user" and notes this is "derived from 8 events/day per DAU scaled to the email-eligible population, which skews slightly less active." No scaling methodology is provided. The 6.3 figure appears to be chosen to make the arithmetic produce the 8M/day target rather than derived independently. The prior document used a "78% figure" that "obscured the construction" — the new construction may be obscuring the same problem differently.

### 4. SMS SLA Is Structurally Incompatible With the Architecture

The executive summary commits to SMS p99 delivery under 60 seconds. SMS is described as "auth events only" and "event-limited." However, during a Redis failover (10–30 seconds per §0.2) plus PostgreSQL fallback activation, SMS notifications — if they share the same queue infrastructure — face a mandatory delay before workers even begin processing. No analysis demonstrates the 60-second p99 is achievable through a 10–30 second failover window plus fallback queue polling latency plus external SMS provider latency. §3.4 is referenced but not included in this document.

### 5. The "No Double-Counting" Claim Is Not Demonstrated

The volume summary asserts "No double-counting" between push and email. The routing logic says email is sent only to users with no active session. But session state is evaluated at routing time, not at the moment of the original event. A user who opens the app between event time and routing time could receive both push (queued before session started) and email (routed before session was detected). The double-dispatch validation criterion (pass: <0.5%) is a post-hoc measurement commitment, not a design guarantee. The architecture does not show where session state is checked or how race conditions are prevented.

### 6. The Interaction Table Contains an Unanalyzed Scenario Gap

The §0.3 interaction table covers "Redis failover + 3× spike simultaneously" but the document elsewhere identifies the 8× spike as the critical non-draining scenario. There is no row for "Redis failover + 8× spike simultaneously." Given that the 8× scenario already "may not drain" under normal conditions, the combined scenario is the highest-risk case and is absent from the only place where options are compared.

### 7. Decision Governance Has a Practical Failure Mode

§0.1 states the 14-day window "does not constitute sign-off" if unacknowledged and commits the engineering lead to escalate before the window closes. But the document does not specify what happens if escalation occurs and both decision owners remain non-responsive. The default fires regardless — meaning the governance language about requiring "active acknowledgment" is not actually enforceable. The document creates an expectation it cannot fulfill.

### 8. The Off-Hours Rate Is Used Inconsistently

§1.2 derives an off-hours sustained rate of 303/sec and a primetime rate of 840/sec. The delay figures in the executive summary table list "standard-priority delay, off-hours 3× spike" as 28 minutes. But 3× off-hours = ~909/sec, which is higher than the primetime sustained rate of 840/sec. The spike analysis should produce similar or worse queue dynamics to primetime sustained load, yet the delay figures show off-hours spikes as consistently better. No explanation is provided for why a higher absolute rate produces shorter delays in the off-hours scenario.

### 9. Validation Gate Timing Creates a Launch Risk

Assumption 1 (DAU/MAU ratio) validation is committed at "8 weeks before launch" with a 2-week remediation lead time for worker provisioning. This leaves 6 weeks of buffer. But the document is a 6-month project for a 4-engineer team. If validation happens at week 18 of 24 and reveals a ratio above 50%, the remediation consumes the remaining buffer entirely, with no slack for the validation of other assumptions or for the findings to propagate into dependent analyses (queue model, spike scenarios, SLA review). The assumptions are described as independent but share the same validation timeline compression.

### 10. "May Not Drain" Is Left Quantitatively Undefined

The 8× spike scenario is described as resulting in a "~4 hours; may not drain" delay for standard-priority. "May not drain" is not a metric — it is an admission that the queue could grow without bound. The document does not specify what queue depth triggers an operational response, who owns that response, or what the response is. This is the highest-consequence scenario in the document and it has the least-specified operational handling.