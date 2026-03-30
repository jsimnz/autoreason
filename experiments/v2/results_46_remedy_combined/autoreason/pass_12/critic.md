## Real Problems with This Proposal

### 1. The Document Is Primarily About Itself

A substantial fraction of the text explains how the document addresses its own prior weaknesses ("the prior blended figure is withdrawn," "the prior version argued... this is true but sidesteps"). This is revision history masquerading as design content. A reader cannot tell what the actual system does without mentally filtering out the self-referential scaffolding. The fifteen decisions in the executive summary are largely commitments to have specified something, not specifications of what was decided.

### 2. Section 1.3 Is Truncated Mid-Sentence

The document ends abruptly: "It." This is not a minor formatting issue. The dynamic threshold recalibration — identified as the resolution to the WAND steady-state problem and cross-referenced from multiple other sections — is never actually stated. Sections 1.3.1, 2.4, 2.5, 3.2, 3.4, 4, 5.3, 6, 7, and 8 are referenced but absent. The document is incomplete in ways that make it impossible to evaluate the majority of its claimed decisions.

### 3. The Fifteen Decisions Are Not Decisions

Nearly every item in the executive summary says "full specification in Section X" where Section X either doesn't exist in this document or contains only a partial description. Decision 11 says the FIFO sharding design "is specified in Section 2.4 and implemented pre-launch" — Section 2.4 does not appear. Decision 12 says a phased scope reduction "is proposed" in Section 8 — Section 8 does not appear. The executive summary functions as a table of contents for a document that was never written.

### 4. The "Fail-Closed on Database Unavailability" Decision Has Unexamined Operational Consequences

The proposal states that during a database outage, no notifications are sent — including OTP and security alerts. For a social app, suppressing a digest email during an outage is acceptable. Suppressing an OTP or security alert during an outage is a product-breaking failure: users cannot log in. The document presents this as a deliberate compliance decision but does not acknowledge that it makes authentication unavailable during any database incident. The compliance framing obscures what is actually a product availability tradeoff.

### 5. The OTP Lifetime Dependency Is Unresolved and Launch-Blocking

Decision 7 states that the 60-second P95 email delivery SLA "is only acceptable if the application's OTP lifetime is ≥90 seconds" and that OTP lifetime is "a required input from the product team." The document identifies this as a dependency with a named owner and deadline — but those details are in Section 3.4, which doesn't exist in this document. A system that cannot deliver OTPs within the application's timeout window is broken at launch. This dependency is not a detail to be resolved later; it determines whether the email fallback design is viable at all.

### 6. The Credential Breach SMS Cost Is Never Modeled

Section 5.3 is referenced as containing the full cost model for a credential breach notification sent to all 10M MAU via SMS. At standard Twilio rates (~$0.0079/SMS in the US), this is approximately $79,000 for a single send — before international rates. This is a material one-time cost that could exceed the entire monthly infrastructure budget. The section does not appear in the document.

### 7. The FIFO Queue Sharding Problem Is Acknowledged but Not Solved

Decision 11 acknowledges that SQS FIFO has a 3,000 messages/second ceiling per queue and states that horizontal sharding is "specified in Section 2.4 and implemented pre-launch." At the aggressive scenario (225M push notifications/day), the average rate is ~2,600/second — already near the ceiling before accounting for peak factors. Section 2.4 does not exist. The document claims to have solved this problem while providing no solution.

### 8. The Registry Ownership Model Has a Circular Failure Mode

Decision 15 states that an unregistered `optin_source` triggers Path B rather than a silent pass, and that the registry update process takes under 30 minutes to minimize false positives. But the document acknowledges this creates a window where valid sends are suppressed. In practice, new acquisition channels (paid campaigns, partner integrations, app store feature placements) are often stood up faster than internal process timelines. The 30-minute SLA is an engineering claim about a process that involves a "named role" — but that role, the process, and the escalation path are all in Section 1.3.1, which does not appear.

### 9. The "Stable Day" Definition Creates a Measurement Problem

Decision 2 defines a stable day as one where no Warning-tier alarms fired AND traffic is within 20% above and 10% below the rolling average. But the rolling average is itself computed from the days being evaluated for stability. A day cannot be assessed for stability until after it completes, and its inclusion or exclusion from the baseline changes the average used to assess the next day. The document does not specify whether stability is assessed prospectively or retrospectively, or how the baseline is initialized when the first 7 days contain mixed stable and unstable days.

### 10. The Compliance On-Call Rotation Is Promised but Undefined

Decision 3 states that a digest halt occurring outside business hours triggers "a named on-call compliance contact with a 2-hour response SLA" and that "the escalation path and on-call rotation are specified in Section 3.2." Section 3.2 does not appear. A compliance on-call rotation is an organizational commitment, not an engineering artifact — it requires staffing, compensation, and agreement from the compliance function. Asserting it exists in a missing section does not make it exist.

### 11. The Document's Own Framing Claims Are Overstated

The introduction states: "Fifteen specific design decisions are addressed explicitly. Each is stated as a named commitment, not a hedged preference." Several of these commitments are actually commitments to specify something in a section that doesn't exist, commitments to make a decision pending input from another team, or commitments to recalibrate a threshold on a schedule that isn't stated. Calling these "named commitments, not hedged preferences" is itself a hedge.