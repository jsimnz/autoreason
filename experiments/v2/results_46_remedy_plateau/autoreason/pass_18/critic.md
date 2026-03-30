## Real Problems with This Proposal

### Governance and Process

**The "active acknowledgment" requirement is self-contradicting.** The document states non-response doesn't constitute sign-off, then immediately describes what happens automatically when non-response occurs. The mechanism functions as a default-fires-on-silence system regardless of the framing. The elaborate language about "process control, not a veto" doesn't change this.

**Budget penalty enforcement has no mechanism.** The proposal states override costs "are borne by the overriding party's team budget" but provides no authority, process, or person responsible for actually enforcing this charge. This is a made-up consequence with no organizational backing described anywhere in the document.

**The escalation procedure names no one.** "The engineering lead escalates" and "notifies both decision owners' managers" — which managers? This is unspecified. The procedure cannot be executed as written.

**Decision B's "same acknowledgment and escalation requirements" reference is incomplete.** It says "same... requirements as Decision A" but Decision A's escalation procedure involves two joint owners. Decision B has one owner. The procedure doesn't actually transfer cleanly and this is glossed over.

---

### Technical Substance

**The document is truncated mid-sentence.** Section 1.1 ends at "those in active session at routing time receive push or in-" — the email volume construction is incomplete. This is the section flagged as corrected from Revision 1 to fix a circular derivation. The correction is absent.

**The off-hours spike correction creates a new inconsistency that isn't resolved.** The document acknowledges that 3× off-hours load (909/sec) exceeds primetime sustained rate (840/sec) and corrects the delay upward to 49 minutes. But the spike ratio table in §0.3 still uses "3× spike" uniformly across primetime and off-hours without distinguishing that the absolute load differs. If the spike multiplier is applied to different base rates, the table scenarios aren't comparable across time periods.

**The 8× spike is explicitly described as extrapolation beyond cited data, but the operational response trigger is treated as if it's validated.** The 500K message threshold appears with no derivation. At what queue depth does high-priority delivery degrade? What is the relationship between queue depth and the delay figures? The threshold is defined but its adequacy is asserted, not argued.

**Worker capacity range (1,300–3,500/sec) is a 2.7× spread presented as a "planning figure."** Choosing 2,000/sec as the planning figure because it's "approximately the 50th percentile" is statistically reasonable only if the distribution within that range is uniform or known. It isn't stated. The range itself suggests deep uncertainty about the primary capacity figure.

**The SMS SLA interaction is deferred but the dependency is load-bearing.** Section 0.2 states "the SMS direct-dispatch architecture in §3.4 is mandatory" if Sentinel is selected, but §3.4 is not included in this document. The SLA achievability analysis is referenced but not present. A decision with a 14-day window depends on analysis that isn't here.

**The validation sequence has a single-point-of-failure problem.** If any Assumption 2–5 validation fails at week 14 and remediation takes the full available time to week 18, it consumes the buffer for Assumption 1 validation. The document acknowledges this but the stated consequence — "remediation must complete by week 18" — is a requirement, not a contingency. What happens if it doesn't? This is unaddressed.

**The DAU/MAU remediation figures are not derived.** "Reduce to 60 workers" for ratio below 20%, "add 40 workers" for ratio above 50% — these numbers appear without calculation. Given that worker count is the primary capacity lever and the document elsewhere shows detailed queue modeling, these round numbers with no supporting math are inconsistent with the document's own standards.

---

### Internal Consistency

**The interaction table in §0.3 has an asymmetry that isn't explained.** Under "PostgreSQL fallback overloaded," Option A workers "continue retrying Redis" — but this is only true if Redis becomes available again. If Redis is down and PostgreSQL is overloaded, Option A workers are retrying a down system. This scenario isn't the same failure mode as the others in the row.

**"Bounded range" is listed as the confidence level for worker capacity.** Every quantitative estimate has a bounded range by definition. This is not a meaningful confidence descriptor in the way that "±50%" or "queue model" are for other rows in the same table.

**The combined contingency cost of 3.5 engineer-weeks is presented as fitting within the timeline, with the reader directed to §7.1 — but §7.1 isn't in this document.** The claim cannot be evaluated.

**The correction note says the prior planning figure "sat in the upper third of the derived range."** The new figure is described as sitting "at approximately the 50th percentile." But the range is 1,300–3,500/sec and 2,000/sec is at the 32nd percentile of that range if uniform, not the 50th. The percentile claim is wrong on the document's own numbers.