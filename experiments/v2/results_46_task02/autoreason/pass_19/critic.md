## Real Problems with This Proposal

### 1. The Document Cannot Be Acted On

The SMS runbook is assigned to "[Engineer Name — to be filled in at project kickoff]" — in a document that is itself presumably produced before or at kickoff. The launch gate mechanism depends on a named engineer, but the document defers naming that engineer to a future moment. If this document is the artifact that kickoff produces, the gate mechanism is circular. If it precedes kickoff, the engineer list doesn't exist yet. Either way, the accountability structure is hollow at the moment it matters most.

### 2. The In-App/Push Substitution Model Is Asserted, Not Derived

The claim that in-app captures exactly 20% of events rests entirely on "working assumption: 20% of events." No reference data is cited for this figure, unlike the DAU/MAU and notifications/day figures which get explicit benchmark sourcing. The document correctly notes that push and in-app are substitutes, then assigns the split without justification. The 80/20 split has direct consequences for worker sizing — push workers handle 36M events/day vs. 9M — but the input driving that split has no sensitivity analysis, no cited range, and no flag indicating it's uncertain. This is inconsistent with the document's stated methodology.

### 3. The Email Volume Model Conflates MAU and DAU

The email opt-in calculation uses "3M engaged users × 8% × 1/day" — treating the DAU figure as the opt-in base. But email opt-in is typically a one-time account setting, not a daily behavior. Users who opted into email digests but haven't opened the app in weeks still receive emails. The correct base is MAU (10M) or total registered users, not DAU. Using DAU understates email volume by roughly 3×. At 10M MAU × 8% opt-in, the correct figure is ~800K digest emails/day, not ~240K. This affects email worker sizing and potentially the email provider tier selection.

### 4. The 2FA Decision Framing Creates a False Binary

The document presents authenticator-first vs. SMS-default as the complete decision space. It omits the most common real-world configuration: SMS-default at signup with a post-enrollment nudge toward authenticator apps. Many apps start SMS-default because it has higher completion rates during onboarding, then nudge users toward TOTP over time. This hybrid configuration has its own cost curve that isn't bounded by either Configuration A or B as described. More importantly, the document says "engineering cannot determine the correct SMS spend cap until the product team makes this choice" — but then sets a default of Configuration A without that decision being made. The spend cap is therefore set based on a unilateral engineering default for a decision the document says engineering cannot make unilaterally.

### 5. The Section Numbering Breaks Mid-Document

There are two sections labeled "1.3" — one for channel split and one for SMS. This isn't cosmetic. In a document that functions as an engineering reference and contains cross-references ("see Section 1.3"), an ambiguous section number creates real navigation failures. The SMS spend cap section is referenced multiple times in the runbook and cap design discussion. Which 1.3 is meant?

### 6. The Provisioned Floor Arithmetic Is Not Closed

Section 1.2 states the 3,200/sec floor "accommodates sustained averages up to 800/sec before viral effects" (4× factor). Section 1.4 begins deriving the peak factor but the document cuts off before completing the worker count derivation or showing how 3,200/sec maps to actual worker instances. The reader is told the floor is 3,200/sec and told it comes from a 4× factor, but the document never shows: how many workers that implies, what each worker's throughput assumption is, or whether the worker count is achievable within the stated engineering constraints. The floor is asserted from the top down without the bottom-up validation that would confirm it's achievable.

### 7. The Redis Operational Isolation Argument Is Incomplete

The document justifies a dedicated Redis instance for the spend counter on two grounds: operational isolation and configuration isolation (no maxmemory eviction policy). The configuration isolation argument is sound. The operational isolation argument — "a failure in the main notification Redis cluster must not take down the spend cap counter" — actually argues for the opposite architecture. If the spend cap counter is on a separate instance and *that* instance fails, the spend cap is gone and SMS billing is uncapped. The document treats main-cluster failure as the only failure mode worth isolating against, but a dedicated t3.micro is a single point of failure with no redundancy mentioned. The isolation argument protects against one failure mode while creating another.

### 8. The Sensitivity Table Stops at the Wrong Boundary

The combined sensitivity table in Section 1.2 shows sustained average inbound rates up to 45% DAU/MAU and 25/day. The document states the provisioned floor handles up to 800/sec sustained average. At 45% DAU/MAU and 25/day, the table shows ~1,302/sec — well above 800/sec. But the document says scenarios requiring re-sizing are "flagged explicitly in Section 1.5," which is cut off. The table presents numbers that exceed the provisioned floor without in-line flags, leaving the reader to mentally compare table values against the 800/sec threshold. For a document that emphasizes making consequences visible, this is a structural gap in the presentation.

### 9. The Spend Cap Multiplier Is Unjustified

The spend caps are set at "~2× upper bound of expected volume" with the explanation that this "provides margin for normal variance." But the upper bounds themselves are already described as upper bounds — not medians or working figures. Doubling an upper bound to set a cap means the cap won't trigger until volume reaches 2× the worst plausible normal case. The document simultaneously says the cap "is designed to catch runaway notification loops and billing accidents" and sets it at a level that by construction won't trigger during anything describable as normal variance. These two goals are in tension and the document doesn't resolve it.