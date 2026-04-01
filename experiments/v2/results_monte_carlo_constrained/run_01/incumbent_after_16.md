# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. Personal and free-tier AI tools used for company purposes are subject to this policy on the same terms as licensed tools.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and support the pending FedRAMP authorization.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns each of the 80 seats to named individuals through existing GitHub Copilot Business seat controls.
2. Copilot-seated engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must receive human reviewer approval before merge.
4. Any AI-generated code included in a deliverable to a customer must be disclosed to that customer as AI-generated, given outside counsel's finding that such code may not be copyrightable.
5. Additional AI tools require written approval from both Engineering leadership and Legal before any use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text for external distribution requires direct manager approval before sending. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim.]*
3. **No commits with third-party license headers.** Reviewers must reject any pull request carrying an AI-generated third-party license header. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 5. *[Basis: 73% of engineers and 45% of sales staff are already using informal tools with no data-handling controls, creating DPA, GDPR, and IP exposure.]*
5. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to GDPR obligations; Slack AI features are currently disabled; enabling them would jeopardize the pending FedRAMP authorization.]*

---

## Enforcement

1. Each manager reviews direct reports' AI tool use through existing code review and output approval processes.
2. Any violation involving customer data exposure, copyright infringement, or license header incidents must be routed to Legal via the existing Legal intake process within one business day of discovery by any manager or department head.
3. If a manager does not complete that routing within one business day, the obligation transfers to the department head, who must complete routing within one additional business day.
4. A confirmed violation is recorded in the employee's existing HR file and triggers a mandatory manager review within five business days.
5. Where a confirmed violation involves AI tool access, Engineering leadership revokes that access through existing GitHub Copilot Business seat controls or Slack administrator controls as applicable.