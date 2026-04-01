I'll state each change and which problem it fixes before presenting the revised document.

**Problem 1 & 2 (word count; preamble block):** Remove the preamble analysis block entirely. Cut all basis citations to single-sentence references. Compress every item to its minimum enforceable statement.

**Problem 3 (item 4 forward-references item 5):** Remove the vacuous sales permission. Sales has no approved AI writing tool in the base facts; the prohibition on unapproved tools already covers them. Delete item 4 and renumber.

**Problem 4 (department head escalation gap):** Add an explicit obligation binding the department head to the same one-business-day routing requirement.

**Problem 5 (Slack basis adds unevidenced claims):** Replace the invented DPA-agreement claim with citations only to base facts: PII/financial data handling, GDPR obligations, and pending FedRAMP authorization.

**Problem 6 ("licensed environment only" undefined):** Replace with "within GitHub Copilot Business only," which is defined by the tool name and enforceable through existing seat controls.

**Problem 7 (seat sharing unenforceable):** Replace the prohibition on sharing with the affirmative enforceable rule: Engineering leadership assigns seats through existing GitHub Copilot Business seat controls. Sharing is not separately prohibited; it is structurally prevented by named-seat assignment.

**Problem 8 (copyrightability finding unaddressed):** Add a Permitted Uses item requiring that AI-generated code delivered to customers be disclosed as AI-generated, citing outside counsel's finding that such code may not be copyrightable.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. Personal and free-tier AI tools used for company purposes are subject to this policy on the same terms as licensed tools.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and support the pending FedRAMP authorization.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI tool. Engineering leadership assigns each of the 80 seats to named individuals through existing GitHub Copilot Business seat controls.
2. Copilot-seated engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must receive human reviewer approval before merge.
4. Any AI-generated code included in a deliverable to a customer must be disclosed to that customer as AI-generated, given outside counsel's finding that such code may not be copyrightable.
5. Additional AI tools require written approval from both Engineering leadership and Legal before any use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1; outside counsel confirmation that doing so violates existing DPA terms.]*
2. **No AI-generated external content without manager approval.** AI-generated text for external distribution requires direct manager approval before sending. *[Basis: Incident 2—verbatim competitor copyrighted copy distributed by a sales rep.]*
3. **No commits with third-party license headers.** Reviewers must reject any pull request carrying an AI-generated third-party license header. *[Basis: Incident 3—GPL header committed from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 5. *[Basis: 73% of engineers using informal tools; 45% of sales using AI for email drafting; no data-handling controls exist for those tools.]*
5. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to GDPR obligations; Slack AI features are currently disabled; enabling them would jeopardize the pending FedRAMP authorization.]*

---

## Enforcement

1. Each manager reviews direct reports' AI tool use through existing code review and output approval processes.
2. Any violation involving customer data exposure, copyright infringement, or license header incidents must be routed to Legal via the existing Legal intake process within one business day of discovery by any manager or department head.
3. If a manager does not complete that routing within one business day, the obligation transfers to the department head, who must complete routing within one additional business day.
4. A confirmed violation is recorded in the employee's existing HR file and triggers a mandatory manager review within five business days.
5. Where a confirmed violation involves AI tool access, Engineering leadership revokes that access through existing GitHub Copilot Business seat controls or Slack administrator controls as applicable.