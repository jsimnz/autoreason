## Problems Found

### Constraint Violations

**1. Word count exceeds 500 words.**
The policy body alone (excluding the "Changes made" section, the header block, and signature line) runs well over 500 words. Prohibited Use items 1–3 are each multi-sentence paragraphs with embedded citations. The document does not comply with the maximum 500-word constraint.

**2. Sections do not consistently use numbered items — Scope item 2 is borderline prose.**
Scope item 2 reads as a conditional prose statement directing readers elsewhere rather than a discrete policy item. It contains no operative rule of its own; it exists only to explain the structure of the document. This is closer to a navigational note than a numbered policy item, which undermines the constraint requiring numbered items rather than prose paragraphs.

### Enforcement Problems

**3. "Prior written approval" for sales communications is not enforceable with existing tooling as described.**
The document claims in its own changelog that email and messaging threads satisfy the "no new tooling" constraint. However, the policy requires this documentation be "retained for audit." Neither standard email nor Slack (which has AI features disabled per the base facts, but is not described as an archiving system) is established in the base facts as an audited retention system. The claim that this is enforceable through existing access controls is asserted but not supported by the base facts.

**4. "PR disclosure and license-identifier review" relies on engineer self-reporting with no verification mechanism.**
The prohibition requires engineers to self-identify AI-generated code in the PR description. There is no existing access control or review process in the base facts that can detect non-disclosure. The reviewing manager can only confirm disclosure was documented, not that all AI-generated code was disclosed. Undisclosed AI use is undetectable, making this prohibition unenforceable for the most problematic case — the one that caused Incident 3.

**5. Enforcement item 1 requires same-business-day incident reporting but provides no mechanism to detect violations in the first place.**
The reporting obligation is triggered by discovery, but for Prohibited Uses 2 and 3 in particular, violations may not surface through any existing monitoring. The policy creates a reporting obligation without establishing how violations are discovered, which makes the enforcement chain incomplete.

### Factual / Derivability Problems

**6. Permitted Use 3 grants sales employees broad AI drafting permission beyond what the base facts support.**
The base facts list only GitHub Copilot Business (80 seats, engineering-focused) as an approved tool. No AI drafting tool for sales has been approved or licensed. Permitted Use 3 effectively authorizes an unapproved tool class for 30 sales employees without identifying what tool is permitted or confirming it has passed Legal DPA review. This contradicts Prohibited Use 4, which prohibits unapproved tools.

**7. The 80-seat allocation for GitHub Copilot Business covers fewer than the 120 engineers.**
The policy grants access to engineers "with an assigned seat" but the base facts show only 80 seats for 120 engineers. The policy never addresses who assigns seats or what the 40 unseated engineers are permitted to do, leaving a significant population without clear guidance.