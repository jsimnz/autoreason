## Real Problems with This Proposal

### 1. The "Complete Technical Design" Claim Is False

The preface states this is "a complete technical design." The document cuts off mid-sentence in §1.4. Sections §1.5, §1.6, and beyond are missing entirely. §1.6 is referenced multiple times for critical enforcement mechanisms (SMS boundary enforcement, Tier 1 authorization controls) that never actually appear. The document cannot be evaluated as a design because its most-referenced enforcement section doesn't exist.

### 2. Named Owner Is a Placeholder

The 30-day validation section assigns ownership to "[Name of backend engineer designated to notifications at project kickoff — to be filled in before project start]." This is a template, not a design. The document then builds a dependency chain on this owner — they must instrument specific metrics, conduct the review, apply decision rules, and write an authoritative update. If this document ships without that name filled in, ownership defaults to nobody, which the document itself says is unacceptable.

### 3. The Tier 1 Concurrent Channel Claim Is Unsubstantiated

The design states Tier 1 notifications deliver push, SMS, and email "concurrently — not sequentially" as if this is straightforwardly implemented. But the document never describes what happens when all three channels succeed — does the user receive three redundant password reset notifications? There's no deduplication or acknowledgment mechanism described. For security events, receiving the same alert three times simultaneously is a UX and trust problem. The design treats concurrency as obviously correct and ignores the coordination problem it creates.

### 4. The Batching Section Promises Logic It Doesn't Deliver

§1.4 states direct messages are excluded from batching "by a mechanism described in §1.4" — a self-referential citation that resolves to nothing. The section cuts off before explaining either the batching threshold or the DM exclusion mechanism. The document also states batching serves to reduce load during spikes, but never specifies what the threshold is, what the batch window is, or how batching interacts with the 5-minute delivery target for Tier 2.

### 5. The SMS Cost Model Rests on Unvalidated Assumptions Presented as Analysis

The model applies a geographic distribution ("40% domestic US traffic") with no stated basis. For a social app with 10M MAU, the actual geographic split could vary enormously and is presumably known or estimable from product data. Using an assumed split while flagging only high-cost market sensitivity (Germany, Brazil) ignores that if the user base is majority-international in moderate-cost markets, the estimate is also wrong in the other direction. The model presents a false precision of $6,450–$12,500/year when the inputs are fabricated.

### 6. The APNs/FCM Rate Limit Section Defers the Critical Number

The design correctly reframes platform rate limits as fixed constraints rather than negotiable ones, then instructs the team to "review APNs and FCM public rate limit documentation in month 1 to establish the actual ceiling." APNs and FCM rate limits are publicly documented now. A design that provisions infrastructure and sets alert thresholds at "70% of the known rate limit ceiling" without stating what that ceiling is has deferred the only number that makes the alert threshold meaningful. This isn't a 30-day action item; it's information that should be in the document.

### 7. Cold Storage Rate Limit Is Invented Without Justification

The in-app notification section imposes "a rate limit of 5 such fetches per user per day to prevent cold storage read amplification." No analysis supports this number. What is the cost per cold storage fetch? What read amplification is being prevented at what volume? What happens to a legitimate user who hits the limit — do they see an error? The number appears to have been chosen arbitrarily, and the tradeoff section ("low-frequency use case") doesn't engage with whether 5 fetches/day is the right limit for that use case.

### 8. The Runaway Process Mitigation Depends on §1.6 Which Doesn't Exist

The Tier 1 rate limiting section resolves "Problem 1" (runaway process emitting fraudulent Tier 1 events) by pointing to authorization controls "described in §1.6." That section is absent. The design explicitly states this enforcement "is enforced in code" but provides no specification of what that code does, what the allowlist contains, how service identity is validated, or what the rejection behavior is. The security model's primary control mechanism is a forward reference to a missing section.

### 9. The 30-Day Review Decision Rules Have a Gap

The decision rules cover three cases: within 50%, 50–100% above, and more than 100% above the estimate. There is no rule for actual peak being significantly *below* estimate — which is equally likely given the acknowledged uncertainty. Below-estimate actuals have cost implications (the system is intentionally over-provisioned) and should trigger a defined scaling-down decision, but the review process only addresses upward deviation.

### 10. "Quiet Hours" Is Referenced But Never Defined

The document states Tier 1 notifications are "never subject to quiet hours" as a distinguishing property. Quiet hours are never defined anywhere in the visible document — what hours, configured by whom, applied how, enforced where. Defining a tier property by contrast with an undefined concept provides no actual specification.

### 11. The 12-Month Retention Policy Has No Legal Basis

The document states notifications are "retained in cold storage for 12 months from creation, then permanently deleted" and that users are notified of this in "privacy documentation." There is no analysis of whether 12 months satisfies or conflicts with applicable data retention regulations (GDPR right to erasure, CCPA, etc.) or whether it's insufficient for markets with minimum retention requirements. A social app with 10M MAU almost certainly has EU users, making GDPR compliance non-optional, and this design doesn't engage with it.