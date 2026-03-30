## Real Problems with This Proposal

### 1. The Document Is Incomplete Mid-Sentence

§1.2.2 ends with "Delivered within 2 minutes of" — the document is truncated. This is submitted as "Draft" status but is missing substantive technical content for at least Tier 2 and Tier 3 delivery behavior, all of §1.3 through §1.10, and presumably the failure handling and infrastructure sections listed in the table of contents. Reviewers cannot evaluate the design because most of it does not exist yet.

### 2. The Validation Schedule Cannot Catch What It Claims to Catch

The 14-day review is described as producing measured replacements for assumed values, but the document simultaneously acknowledges "day-14 data may not represent fully stable steady-state behavior." The 60-day review exists to catch this. However, infrastructure purchasing decisions are gated on the DM clarification deadline set "at least 2 weeks before any infrastructure purchasing commitment" — which could be well before day 14. The validation process is therefore structurally unable to inform the most consequential early purchasing decisions it claims to protect.

### 3. The 2× Headroom Argument Is Circular

The document argues against higher provisioning multiples partly on the grounds that "a 6× worst-case multiplier is an estimate of an estimate, not a measurement." This is true — but the 2× figure has exactly the same epistemic status. The argument for 2× over 6× is not that 2× is better-grounded; it is that 2× is cheaper and the exposure window is short. That is a legitimate cost argument, but the document frames it as a risk argument, which it is not.

### 4. The Escalation Chain Has a Structural Gap

The simultaneous unavailability procedure designates "the most senior available engineer" as temporary decision-maker. On a four-person team, seniority may be ambiguous or contested, particularly if the two most senior engineers are the ones unavailable. "Most senior" is undefined — by tenure, by title, by compensation? This is precisely the kind of ambiguity that causes paralysis during an actual incident.

### 5. The DM Volume Problem Is Larger Than Acknowledged

The document flags that 5 recipients per sender would produce 2.5M DM notifications rather than 500,000, "nearly doubling total estimated volume." The arithmetic is wrong. 1.3M baseline minus 500K DM plus 2.5M DM equals 3.3M, which is a 2.5× increase in total volume, not "nearly doubling." The downstream provisioning target of ~130/second would need to be roughly 325/second. The understatement of this risk is significant given that it is the document's own identified highest-uncertainty variable.

### 6. The Immutable Tier Assignment Has No Change Process

§1.2 states tier assignment is "immutable — it cannot be changed by user preference or batching logic, only by a change to the event type definition itself." But there is no described process for changing event type definitions. Who can initiate it? What review is required? What happens to in-flight notifications of that type during a transition? The immutability guarantee is stated as a safety property but has no governance mechanism behind it.

### 7. The Legal Review Contingency Creates an Unacknowledged Product Risk

The contingency for a missed legal review defers SMS and email to v2 and explicitly accepts this outcome. But Tier 1 security events (§1.2.1) depend on SMS as a fallback channel when push fails. If SMS ships in v2 and a user has no push token or push is unavailable, the Tier 1 delivery sequence silently degrades to email only. The document does not acknowledge this dependency or describe what Tier 1 delivery looks like during the period when SMS is legally uncleared.

### 8. The Kickoff Checklist Is Load-Bearing but Undefined

Multiple critical gates — contact information, named owners, legal counsel identification, DM clarification deadline, review calendar events — are deferred to a "kickoff checklist" that is referenced but never described. The checklist is not an appendix to this document, its contents are not enumerated, and there is no stated owner for ensuring it is complete before it is used as a gate. The document's own distribution precondition depends on a document that does not exist within this proposal.

### 9. Queue Depth Trigger Is Disconnected From the Spike Analysis

The immediate trigger threshold is 500,000 messages in the queue during "non-incident conditions." The spike buffering analysis in §1.1.3 estimates a 6× spike produces approximately 117,000 jobs in queue during the auto-scaling gap. The trigger threshold is more than 4× higher than the worst-case spike estimate. If the threshold is meant to catch capacity problems before they become severe, it is set at a level that would only fire after a problem is already extreme relative to the modeled scenarios.

### 10. "General Benchmark" Is Not a Source

Every per-event rate in the volume table is attributed to "General benchmark" with no citation, no named source, and no indication of what type of social app, at what scale, in what year. The document correctly states these could be off by 2–5× in either direction, but it does not acknowledge that without knowing what the benchmarks actually are, there is no basis for evaluating whether they are applicable to this product at all. A benchmark from a photo-sharing app is not the same as one from a messaging-first app.