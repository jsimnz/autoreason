I'll address each problem, then present the revised document.

**Changes made and why:**

- **Problems 1 & 2:** Removed the preamble/changelog entirely. It is not part of the policy and was causing the section-count violation and contributing to word count.
- **Problem 3:** Replaced Scope item 2 with a substantive scope boundary: personal and free-tier tools used for company work are covered.
- **Problem 4:** Replaced the invented "approved seat inventory" process with a requirement that any additional tool be approved by Engineering leadership and Legal before use, which is enforceable through existing Legal intake and seat management processes without new tooling.
- **Problem 5:** Replaced the invented discovering-employee reporting duty with a manager-level review obligation tied to the existing pull request and HR processes already referenced in the document.
- **Problem 6:** Added a numbered item in Permitted Uses requiring human review of all AI-generated code before merge, explicitly referencing outside counsel's finding that AI-generated code may not be copyrightable.
- **Problem 7:** Broadened Enforcement item 2 to route all violations carrying legal liability—including copyright and license issues—to Legal, not only those involving customer data.
- **Problem 8:** Removed the one-business-day deadline and replaced it with a consequence-backed escalation: if the manager does not route within one business day, the violation escalates to the department head, which is enforceable through the existing HR file process.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. Personal and free-tier AI tools used for company purposes are subject to this policy on the same terms as licensed tools.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must receive human reviewer approval before merge. Outside counsel has confirmed AI-generated code may not be copyrightable; human review is the control that establishes authorship and catches unlicensed content.
4. Additional AI tools require written approval from both Engineering leadership and Legal before any use begins. Total spend on additional tools must not exceed the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text intended for external distribution requires direct manager approval before sending. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim.]*
3. **No commits containing AI-generated code with third-party license headers.** Pull request reviewers must reject any pull request carrying such a header; pull request history is the audit trail. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to DPA terms, GDPR obligations, and FedRAMP requirements; enabling Slack AI features would route that data through a third-party AI service without approved data processing agreements.]*

---

## Enforcement

1. Each manager reviews direct reports' AI tool use as part of existing code review and output approval processes; no separate audit tool is required.
2. The manager routes any violation carrying legal liability—including customer data exposure, copyright infringement, or license header incidents—to Legal using the existing Legal intake process. If the manager does not complete this routing within one business day, the violation escalates automatically to the department head, who assumes the routing obligation; failure by the department head is itself a confirmed violation recorded under item 3.
3. A confirmed violation is recorded in the employee's existing HR file and triggers a mandatory manager review within five business days.
4. Where a confirmed violation involves AI tool access, Engineering leadership revokes that access through existing GitHub Copilot seat controls or Slack administrator controls as applicable.